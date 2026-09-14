import logging

import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.modules.decision_workflow.ports.ports import (
    BaseGenerationChoiceAdapter,
    CandidateContext,
    GenerationCandidate,
    build_strategy_feedback,
)
from backend.api.modules.requirements_core.ports import get_flow_generation_service
from backend.core.logging.events import (
    FLOW_GENERATION_COMPLETED,
    FLOW_GENERATION_FAILED,
    FLOW_GENERATION_STARTED,
)
from backend.core.observability import emit_how_lifecycle_event
from backend.database.model import (
    ActorModel,
    BusinessObjectModel,
    ChoiceGroupModel,
    FeatureModel,
    FlowModel,
    FlowStepModel,
    FlowTransitionModel,
    RuleLinkModel,
)


async def _get_current_workspace_state_hash(
    session: AsyncSession, project_id: int, workspace_id: int
) -> str:
    from backend.api.modules.requirements_core.generation_context import (
        load_flow_generation_context,
    )

    ctx = await load_flow_generation_context(
        project_id,
        session,
        workspace_id=workspace_id,
    )
    return ctx.context_hash


class FlowGenerationChoiceAdapter(BaseGenerationChoiceAdapter):
    """Generates and manages multi-candidate flow sets and transitions."""

    generation_type = "flow"

    def __init__(self):
        self._service = get_flow_generation_service()

    async def generate_candidate(
        self, context: CandidateContext
    ) -> GenerationCandidate:
        strategy_hint = build_strategy_feedback(context, "生成流程与业务对象")
        feedback = context.user_feedback or ""
        combined = f"{strategy_hint}\n{feedback}".strip()

        emit_how_lifecycle_event(
            FLOW_GENERATION_STARTED,
            capability="flow_generation",
            project_id=context.project_id,
            workspace_id=context.workspace_id,
        )
        try:
            draft_payload, response_payload = await self._service._generate_preview(
                project_id=context.project_id,
                user_feedback=combined,
                session=context.session,
                workspace_id=context.workspace_id,
            )
        except Exception as error:
            emit_how_lifecycle_event(
                FLOW_GENERATION_FAILED,
                capability="flow_generation",
                project_id=context.project_id,
                workspace_id=context.workspace_id,
                error_code=type(error).__name__,
                level=logging.ERROR,
            )
            raise

        ws_state_hash = draft_payload.get("context_hash") or await _get_current_workspace_state_hash(
            context.session, context.project_id, context.workspace_id
        )
        draft_payload["expected_workspace_version"] = ws_state_hash

        flows = response_payload.get("flows", [])
        business_objects = response_payload.get("business_objects", [])
        emit_how_lifecycle_event(
            FLOW_GENERATION_COMPLETED,
            capability="flow_generation",
            project_id=context.project_id,
            workspace_id=context.workspace_id,
            flow_count=len(flows),
            business_object_count=len(business_objects),
        )

        # Count existing flows in workspace to show replacement impact
        existing_flow_stmt = select(sa.func.count(FlowModel.id)).where(
            FlowModel.project_id == context.project_id
        )
        existing_flow_stmt = existing_flow_stmt.where(
            FlowModel.workspace_id == context.workspace_id
        )
        res = await context.session.execute(existing_flow_stmt)
        existing_flow_count = res.scalar_one() or 0

        strat_lbl = context.strategy_label or context.strategy
        return GenerationCandidate(
            title=f"{strat_lbl} — {len(flows)} 个流程, {len(business_objects)} 个业务对象",
            rationale=f"按 {strat_lbl} 策略生成的流程与业务对象",
            payload=draft_payload,
            preview={
                "expected_workspace_version": ws_state_hash,
                "flow_count": len(flows),
                "existing_flows_to_replace": existing_flow_count,
                "flows": [
                    {
                        "flow_name": f.get("flow_name", ""),
                        "feature_names": f.get("feature_names", []),
                        "step_count": len(f.get("flow_steps", [])),
                        "step_names": [
                            s.get("step_name", "") for s in f.get("flow_steps", [])
                        ],
                        "transition_count": len(f.get("transitions", [])),
                        "rule_count": len(set(f.get("rule_refs", [])) | {
                            ref for item in f.get("flow_steps", []) + f.get("transitions", [])
                            for ref in item.get("rule_refs", [])
                        }),
                        "business_objects": list(
                            {
                                num
                                for s in f.get("flow_steps", [])
                                for num in (
                                    s.get("input_business_object_numbers", [])
                                    + s.get("output_business_object_numbers", [])
                                )
                            }
                        ),
                    }
                    for f in flows
                ],
                "business_object_count": len(business_objects),
                "new_business_objects_count": sum(
                    1
                    for bo in business_objects
                    if not (
                        bo.get("object_id")
                        or bo.get("id")
                        or bo.get("logical_uuid")
                    )
                ),
                "reused_business_objects_count": sum(
                    1
                    for bo in business_objects
                    if (
                        bo.get("object_id")
                        or bo.get("id")
                        or bo.get("logical_uuid")
                    )
                ),
                "business_objects": [
                    bo.get("business_object_name", "") for bo in business_objects
                ],
            },
            draft_type="flow",
            apply_mode="draft_payload",
            comparison_summary=self._make_comparison_summary(
                strat_lbl, flows, business_objects
            ),
            apply_behavior="replace_flow_set",
            apply_behavior_description="此方案将替换当前项目/工作区的现有流程，并同步更新业务对象与规则关联",
            strategy_id=context.strategy_id,
            strategy_label=context.strategy_label,
        )

    async def apply_candidate(
        self, payload: dict, session: AsyncSession, **kwargs
    ) -> dict:
        project_id = payload["project_id"]
        workspace_id = kwargs["workspace_id"]

        # The candidate's server-held workspace hash cannot be overridden by the client.
        # Candidate saved hash is the sole authoritative server baseline
        candidate_saved_hash = (
            payload.get("expected_workspace_version")
            or payload.get("context_hash")
        )
        if not candidate_saved_hash:
            raise ValueError("workspace_version_conflict: missing candidate workspace version")

        # Optional client assertion cannot override candidate baseline; if supplied, it must match
        client_version = kwargs.get("expected_workspace_version")
        if client_version is not None and str(client_version) != str(candidate_saved_hash):
            raise ValueError(
                f"workspace_version_conflict: client version {client_version} "
                f"does not match candidate saved baseline {candidate_saved_hash}"
            )

        # Baseline must match current server workspace state hash
        current_hash = await _get_current_workspace_state_hash(
            session, project_id, workspace_id
        )
        if str(candidate_saved_hash) != str(current_hash):
            raise ValueError("workspace_version_conflict")

        # Replacement removes the existing flow aggregate in one transaction.
        flow_stmt = select(FlowModel).where(FlowModel.project_id == project_id)
        flow_stmt = flow_stmt.where(FlowModel.workspace_id == workspace_id)

        existing_flows = (await session.execute(flow_stmt)).scalars().all()
        flow_ids = [f.id for f in existing_flows]

        if flow_ids:
            # Collect step UUIDs and transition UUIDs for cascade RuleLink cleanup
            step_stmt = select(FlowStepModel.logical_uuid).where(
                FlowStepModel.flow_id.in_(flow_ids)
            )
            step_uuids = (await session.execute(step_stmt)).scalars().all()

            trans_stmt = select(FlowTransitionModel.logical_uuid).where(
                FlowTransitionModel.flow_id.in_(flow_ids)
            )
            trans_uuids = (await session.execute(trans_stmt)).scalars().all()

            flow_uuids = [f.logical_uuid for f in existing_flows if f.logical_uuid]
            all_target_uuids = set(flow_uuids + list(step_uuids) + list(trans_uuids))

            if all_target_uuids:
                # Clean up applies_to RuleLinks targeting deleted flow entities
                link_del_stmt = delete(RuleLinkModel).where(
                    RuleLinkModel.project_id == project_id,
                    RuleLinkModel.target_kind.in_(
                        ["flow", "flow_step", "flow_transition"]
                    ),
                    RuleLinkModel.target_logical_uuid.in_(all_target_uuids),
                )
                link_del_stmt = link_del_stmt.where(
                    RuleLinkModel.workspace_id == workspace_id
                )
                await session.execute(link_del_stmt)

            # Explicitly delete child steps and transitions to ensure clean cascading across DB backends
            await session.execute(
                delete(FlowTransitionModel)
                .where(FlowTransitionModel.flow_id.in_(flow_ids))
                .execution_options(synchronize_session="fetch")
            )
            await session.execute(
                delete(FlowStepModel)
                .where(FlowStepModel.flow_id.in_(flow_ids))
                .execution_options(synchronize_session="fetch")
            )

            # Delete existing flows
            for flow in existing_flows:
                await session.delete(flow)
            await session.flush()
            session.expire_all()

        # Confirmed BusinessObjectModel instances are strictly preserved and not deleted!
        result = await self._service._persist_flow_generation_draft(
            draft=payload,
            session=session,
            workspace_id=workspace_id,
        )

        from backend.api.modules.requirements_core.public import get_notifier

        await get_notifier().mark_stale(
            project_id=payload["project_id"],
            stages={"how"},
            perception_kinds={"FLOW"},
            session=session,
            workspace_id=workspace_id,
        )
        return result

    def is_duplicate(
        self, candidate: GenerationCandidate, existing: list[GenerationCandidate]
    ) -> bool:
        def _flow_names(c: GenerationCandidate) -> frozenset:
            return frozenset(
                f.get("flow_name", "") for f in (c.payload or {}).get("flows", [])
            )

        def _rule_scopes(c: GenerationCandidate) -> frozenset:
            scopes = set()
            for flow in (c.payload or {}).get("flows", []):
                targets = [("flow", "", flow)]
                targets.extend(("flow_step", step.get("step_number", ""), step)
                               for step in flow.get("flow_steps", []))
                targets.extend(("flow_transition", (tr.get("source_step_number"), tr.get("target_step_number")), tr)
                               for tr in flow.get("transitions", []))
                for kind, target, item in targets:
                    if item.get("rule_refs"):
                        scopes.add((flow.get("flow_name", ""), kind, target, tuple(sorted(set(item["rule_refs"])))))
            return frozenset(scopes)

        return any(_flow_names(e) == _flow_names(candidate) and _rule_scopes(e) == _rule_scopes(candidate)
                   for e in existing)

    async def is_context_stale(
        self, choice, session: AsyncSession
    ) -> tuple[bool, str | None]:
        payload = choice.payload or {}
        flows = payload.get("flows", [])
        workspace_id = payload["workspace_id"]
        candidate_hash = payload.get("context_hash")

        # Verify context hash if present
        if candidate_hash:
            group = await session.get(ChoiceGroupModel, choice.choice_group_id)
            project_id = group.project_id

            if project_id:
                from backend.api.modules.requirements_core.generation_context import (
                    load_flow_generation_context,
                )

                ctx = await load_flow_generation_context(
                    project_id,
                    session,
                    workspace_id=workspace_id,
                )
                if ctx.context_hash != candidate_hash:
                    return (
                        True,
                        "上游需求、场景或领域规则已变更，此流程候选已过期",
                    )

        for f in flows:
            for fid in f.get("feature_ids", []):
                feature = await session.get(FeatureModel, fid)
                if not feature:
                    return True, f"功能（id={fid}）已被删除，此候选可能不适用"
            for step in f.get("flow_steps", []):
                for aid in step.get("actor_ids", []):
                    actor = await session.get(ActorModel, aid)
                    if not actor:
                        return True, f"参与者（id={aid}）已被删除，此候选可能不适用"
        for bo in payload.get("business_objects", []):
            if bo.get("id"):
                bo_model = await session.get(BusinessObjectModel, bo["id"])
                if not bo_model:
                    return True, "业务对象已被删除，此候选可能不适用"
        return False, None

    @staticmethod
    def _make_comparison_summary(strategy, flows, business_objects):
        descriptions = {
            "balanced": "流程设计均衡",
            "comprehensive": "流程全面覆盖",
            "minimal": "核心流程集",
            "risk_averse": "保守流程设计",
            "workflow_first": "流程驱动编排",
        }
        desc = descriptions.get(strategy, strategy)
        flow_names = ", ".join(f["flow_name"] for f in flows[:3])
        return (
            f"{desc}：{len(flows)} 个流程（{flow_names}），"
            f"{len(business_objects)} 个业务对象"
        )
