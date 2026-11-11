"""Application service orchestrating bounded flow path refinement and atomic persistence."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.modules.requirements_core.flow.application.path_projection_service import (
    PathProjectionService,
)
from backend.api.modules.requirements_core.flow_refinement.application.context_loader import (
    FlowRefinementContext,
    load_flow_refinement_context,
)
from backend.api.modules.requirements_core.flow_refinement.application.normalizer import (
    normalize_and_validate_refinement,
    normalize_refinement_rule_links,
)
from backend.api.modules.requirements_core.flow_refinement.schemas import (
    FlowRefinementCandidatePayload,
)
from backend.core.findings.how_finding_policy import HowFindingPolicy
from backend.core.generators.flow_refinement_generator import (
    FlowRefinementGenerator,
    FlowRefinementGeneratorInput,
)
from backend.database.model import (
    ActorModel,
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    ConfirmationStatus,
    DomainRuleModel,
    FlowStepModel,
    FlowTransitionModel,
    RuleLinkModel,
    RuleLinkPurpose,
    RuleOrigin,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    flow_step_output_business_object_table,
)
from backend.schemas import BlockingScope, IssueSeverity

logger = logging.getLogger(__name__)


class FlowRefinementService:
    """Service providing bounded flow refinement generation, validation, and single-transaction application."""

    def __init__(
        self,
        generator: FlowRefinementGenerator | None = None,
        finding_policy: HowFindingPolicy | None = None,
    ):
        self._generator = generator or FlowRefinementGenerator()
        self._projection_svc = PathProjectionService()
        self._finding_policy = finding_policy or HowFindingPolicy()

    async def generate_raw(
        self,
        session: AsyncSession,
        project_id: int,
        target_kind: str,
        target_id: int,
        workspace_id: int,
        user_feedback: str | None = None,
        source_finding_id: str | int | None = None,
    ) -> tuple[dict[str, Any], FlowRefinementContext]:
        """Generate validated flow path refinement increments using LLM."""
        ctx = await load_flow_refinement_context(
            session=session,
            project_id=project_id,
            target_kind=target_kind,
            target_id=target_id,
            workspace_id=workspace_id,
            focus_text=user_feedback,
            source_finding_id=source_finding_id,
        )

        anchor_info = f"Flow {ctx.target_flow_name} (ID: {ctx.target_flow_id})"
        if ctx.anchor_step:
            anchor_info += f", Step {ctx.anchor_step.get('position')} ({ctx.anchor_step.get('name')})"

        generator_input = FlowRefinementGeneratorInput(
            target_flow_name=ctx.target_flow_name,
            target_flow_description=ctx.target_flow_description,
            anchor_info=anchor_info,
            existing_steps=ctx.existing_steps,
            existing_transitions=ctx.existing_transitions,
            path_projection=ctx.path_projection,
            linked_requirements=ctx.linked_requirements,
            applicable_rules=ctx.applicable_rules,
            finding_context=ctx.finding_context,
            focus_text=user_feedback,
            context_hash=ctx.context_hash,
            knowledge_fragments=ctx.knowledge_fragments,
            refinement_scope={
                "target_kind": ctx.anchor_kind,
                "target_flow_logical_uuid": ctx.target_flow_logical_uuid,
                "allowed_step_positions": sorted(ctx.allowed_step_positions) if ctx.allowed_step_positions is not None else None,
                "allowed_step_uuids": sorted(ctx.allowed_step_uuids) if ctx.allowed_step_uuids is not None else None,
                "allowed_transition_uuids": sorted(ctx.allowed_transition_uuids) if ctx.allowed_transition_uuids is not None else None,
                "actors": ctx.actors,
                "business_objects": ctx.business_objects,
            },
        )

        raw_output = await self._generator.generate(generator_input)

        # Handle empty suggestion gracefully
        has_content = bool(
            raw_output.get("steps_added")
            or raw_output.get("transitions_added")
            or raw_output.get("transitions_updated")
            or raw_output.get("rules_added")
            or raw_output.get("business_objects_added")
            or raw_output.get("rule_links_added")
        )

        existing_step_positions = {s["position"] for s in ctx.existing_steps}
        existing_step_uuids = {s["logical_uuid"] for s in ctx.existing_steps}
        existing_transition_uuids = {t["logical_uuid"] for t in ctx.existing_transitions}
        existing_rule_uuids = {r["logical_uuid"] for r in ctx.applicable_rules}
        confirmed_rule_statements = {
            r["statement"].strip()
            for r in ctx.applicable_rules
            if r.get("confirmation_status") == ConfirmationStatus.CONFIRMED.value
        }

        normalized = normalize_and_validate_refinement(
            raw_output,
            existing_step_positions=existing_step_positions,
            existing_step_uuids=existing_step_uuids,
            existing_transition_uuids=existing_transition_uuids,
            existing_rule_uuids=existing_rule_uuids,
            existing_flow_uuid=ctx.target_flow_logical_uuid,
            confirmed_rule_statements=confirmed_rule_statements,
            target_kind=ctx.anchor_kind,
            allowed_step_positions=ctx.allowed_step_positions,
            allowed_step_uuids=ctx.allowed_step_uuids,
            allowed_transition_uuids=ctx.allowed_transition_uuids,
            allowed_actor_ids=ctx.allowed_actor_ids,
            allowed_bo_numbers=ctx.allowed_bo_numbers,
            context_feature_uuids=ctx.context_feature_uuids,
            context_scenario_uuids=ctx.context_scenario_uuids,
            context_knowledge_uuids=ctx.context_knowledge_uuids,
            existing_transitions=ctx.existing_transitions,
        )
        normalized["done_empty"] = not has_content

        return normalized, ctx

    async def _generate_preview(
        self,
        project_id: int,
        target_kind: str,
        target_id: int,
        user_feedback: str | None,
        session: AsyncSession,
        workspace_id: int,
        source_finding_id: str | int | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Generate preview payloads for ChoiceGroup runner."""
        normalized, ctx = await self.generate_raw(
            session=session,
            project_id=project_id,
            target_kind=target_kind,
            target_id=target_id,
            user_feedback=user_feedback,
            workspace_id=workspace_id,
            source_finding_id=source_finding_id,
        )

        draft_payload = {
            "project_id": project_id,
            "workspace_id": workspace_id,
            "target_flow_id": ctx.target_flow_id,
            "target_flow_logical_uuid": ctx.target_flow_logical_uuid,
            "target_kind": target_kind,
            "target_id": target_id,
            "source_finding_id": source_finding_id,
            "expected_workspace_version": ctx.context_hash,
            "context_hash": ctx.context_hash,
            "rationale": normalized.get("rationale", ""),
            "steps_added": normalized.get("steps_added", []),
            "transitions_added": normalized.get("transitions_added", []),
            "transitions_updated": normalized.get("transitions_updated", []),
            "rules_added": normalized.get("rules_added", []),
            "rule_links_added": normalized.get("rule_links_added", []),
            "business_objects_added": normalized.get("business_objects_added", []),
            "step_object_links_added": normalized.get("step_object_links_added", []),
            "done_empty": normalized.get("done_empty", False),
        }

        # Strict schema validation (forbid extra fields)
        FlowRefinementCandidatePayload.model_validate(draft_payload)

        response_preview = {
            "target_flow_id": ctx.target_flow_id,
            "target_flow_name": ctx.target_flow_name,
            "expected_workspace_version": ctx.context_hash,
            "steps_added_count": len(draft_payload["steps_added"]),
            "transitions_added_count": len(draft_payload["transitions_added"]),
            "transitions_updated_count": len(draft_payload["transitions_updated"]),
            "rules_added_count": len(draft_payload["rules_added"]),
            "steps_added": draft_payload["steps_added"],
            "transitions_added": draft_payload["transitions_added"],
            "transitions_updated": draft_payload["transitions_updated"],
            "rules_added": draft_payload["rules_added"],
            "rule_links_added": draft_payload["rule_links_added"],
            "business_objects_added": draft_payload["business_objects_added"],
            "step_object_links_added": draft_payload["step_object_links_added"],
            "done_empty": normalized.get("done_empty", False),
            "assumptions": [
                r["statement"]
                for r in draft_payload["rules_added"]
                if r.get("confirmation_status") == "ai_assumption"
            ],
        }

        return draft_payload, response_preview

    async def apply_refinement(
        self,
        payload: dict[str, Any],
        session: AsyncSession,
        workspace_id: int,
        expected_workspace_version: str | None = None,
    ) -> dict[str, Any]:
        """Atomically persist refinement candidate in a single transaction savepoint."""
        # Strict runtime schema validation (forbid extra fields)
        FlowRefinementCandidatePayload.model_validate(payload)
        payload = {**payload, **normalize_refinement_rule_links(payload)}

        project_id = payload["project_id"]
        target_flow_id = payload["target_flow_id"]
        ws_id = workspace_id

        # The server-held context hash is verified before any write occurs.
        candidate_saved_hash = (
            payload.get("expected_workspace_version")
            or payload.get("context_hash")
        )
        if not candidate_saved_hash:
            raise ValueError("workspace_version_conflict: missing candidate workspace version")

        if expected_workspace_version is not None and str(expected_workspace_version) != str(candidate_saved_hash):
            raise ValueError(
                f"workspace_version_conflict: client version {expected_workspace_version} "
                f"does not match candidate saved baseline {candidate_saved_hash}"
            )

        # Reload current context to verify hash
        current_ctx = await load_flow_refinement_context(
            session=session,
            project_id=project_id,
            target_kind=payload.get("target_kind", "flow"),
            target_id=payload.get("target_id") or target_flow_id,
            workspace_id=ws_id,
            source_finding_id=payload.get("source_finding_id"),
        )
        if str(candidate_saved_hash) != str(current_ctx.context_hash):
            raise ValueError("workspace_version_conflict")

        # Baseline finding detection before mutations (zero fail-open)
        try:
            baseline_findings = await self._finding_policy.get_findings(
                project_id, session, workspace_id=ws_id
            )
        except Exception as e:
            raise ValueError(f"refinement_quality_check_failed: {e}") from e

        baseline_blocking_ids = {
            f.findingId
            for f in baseline_findings
            if f.severity == IssueSeverity.BLOCKING
            or f.blockingScope != BlockingScope.NONE
        }

        if payload.get("done_empty"):
            return {
                "status": "applied",
                "message": "done_empty_acknowledged",
                "target_flow_id": target_flow_id,
                "steps_added": 0,
                "transitions_added": 0,
                "rules_added": 0,
            }

        async with session.begin_nested():
            # Business objects and attributes are created before step bindings.
            bo_id_map: dict[str, int] = {}
            created_new_bo_ids: set[int] = set()
            for b in current_ctx.business_objects:
                if b.get("number"):
                    bo_id_map[str(b["number"])] = b["id"]
                if b.get("name"):
                    bo_id_map[str(b["name"])] = b["id"]

            for bo_item in payload.get("business_objects_added", []):
                bo_model = BusinessObjectModel(
                    project_id=project_id,
                    workspace_id=ws_id,
                    name=bo_item["business_object_name"],
                    description=bo_item.get("business_object_description", ""),
                    confirmation_status=ConfirmationStatus.AI_ASSUMPTION.value,
                )
                session.add(bo_model)
                await session.flush()
                created_new_bo_ids.add(bo_model.id)
                bo_id_map[str(bo_item["business_object_number"])] = bo_model.id
                bo_id_map[bo_model.name] = bo_model.id

                attrs = bo_item.get("business_object_attributes", [])
                for attr in attrs:
                    attr_name = attr["name"] if isinstance(attr, dict) else attr.name
                    attr_desc = (attr.get("description", "") if isinstance(attr, dict) else attr.description) or ""
                    attr_type = (attr.get("data_type", "string") if isinstance(attr, dict) else attr.data_type) or "string"
                    attr_example = (attr.get("example", "") if isinstance(attr, dict) else attr.example) or ""

                    attr_model = BusinessObjectAttributeModel(
                        workspace_id=ws_id,
                        business_object_id=bo_model.id,
                        name=attr_name,
                        description=attr_desc,
                        data_type=attr_type,
                        example=attr_example,
                        confirmation_status=ConfirmationStatus.AI_ASSUMPTION.value,
                    )
                    session.add(attr_model)
                if attrs:
                    await session.flush()

            def _get_bo_id(b_num: str | int) -> int:
                b_key = str(b_num)
                if b_key in bo_id_map:
                    resolved_id = bo_id_map[b_key]
                    if resolved_id not in current_ctx.allowed_bo_ids and resolved_id not in created_new_bo_ids:
                        raise ValueError(f"step_business_object_outside_local_refinement_radius: business_object {b_num}")
                    return resolved_id
                raise ValueError(f"unresolved_business_object_reference: {b_num}")

            # Step bindings resolve only against validated scoped entities.
            max_pos_stmt = select(func.max(FlowStepModel.position)).where(
                FlowStepModel.flow_id == target_flow_id,
                FlowStepModel.workspace_id == ws_id,
            )
            max_pos_res = await session.execute(max_pos_stmt)
            next_pos = (max_pos_res.scalar_one_or_none() or 0) + 1

            step_temp_to_model: dict[str, FlowStepModel] = {}
            for s_item in payload.get("steps_added", []):
                step_model = FlowStepModel(
                    flow_id=target_flow_id,
                    workspace_id=ws_id,
                    name=s_item["name"],
                    description=s_item.get("description", ""),
                    step_type=s_item.get("step_type", "actorAction"),
                    position=next_pos,
                    confirmation_status=ConfirmationStatus.AI_ASSUMPTION.value,
                )
                session.add(step_model)
                await session.flush()
                step_temp_to_model[s_item["temp_id"]] = step_model
                next_pos += 1

                # Persist actor associations (strict verification against workspace and local radius)
                for aid in s_item.get("actor_ids", []):
                    if aid not in current_ctx.allowed_actor_ids:
                        raise ValueError(f"step_actor_outside_local_refinement_radius: actor {aid}")
                    actor_stmt = select(ActorModel.id).where(
                        ActorModel.id == aid,
                        ActorModel.project_id == project_id,
                        ActorModel.workspace_id == ws_id,
                    )
                    actor_res = await session.execute(actor_stmt)
                    if not actor_res.scalar_one_or_none():
                        raise ValueError(f"unresolved_actor_reference: {aid}")
                    await session.execute(
                        insert(flow_step_actor_table).values(
                            flow_step_id=step_model.id,
                            actor_id=aid,
                        )
                    )

                # Persist input business objects (strict resolution)
                for b_num in s_item.get("input_business_object_numbers", []):
                    b_id = _get_bo_id(b_num)
                    await session.execute(
                        insert(flow_step_input_business_object_table).values(
                            flow_step_id=step_model.id,
                            business_object_id=b_id,
                        )
                    )

                # Persist output business objects (strict resolution)
                for b_num in s_item.get("output_business_object_numbers", []):
                    b_id = _get_bo_id(b_num)
                    await session.execute(
                        insert(flow_step_output_business_object_table).values(
                            flow_step_id=step_model.id,
                            business_object_id=b_id,
                        )
                    )

            # New transitions resolve candidate-local and persisted step references.
            pos_to_step_id: dict[int, int] = {
                s["position"]: s["step_id"] for s in current_ctx.existing_steps
            }

            def _resolve_step_id(ref: str | int) -> int:
                if isinstance(ref, int) and ref in pos_to_step_id:
                    return pos_to_step_id[ref]
                if isinstance(ref, str):
                    if ref in step_temp_to_model:
                        return step_temp_to_model[ref].id
                    for s in current_ctx.existing_steps:
                        if s["logical_uuid"] == ref:
                            return s["step_id"]
                raise ValueError(f"unresolved_step_reference: {ref}")

            # Existing transitions may be updated/redirected first (e.g. updating default path)
            for ut_item in payload.get("transitions_updated", []):
                uuid = ut_item["logical_uuid"]
                existing_trans_stmt = select(FlowTransitionModel).where(
                    FlowTransitionModel.logical_uuid == uuid,
                    FlowTransitionModel.flow_id == target_flow_id,
                    FlowTransitionModel.workspace_id == ws_id,
                )
                existing_trans_res = await session.execute(existing_trans_stmt)
                t_to_update = existing_trans_res.scalar_one_or_none()
                if t_to_update:
                    if ut_item.get("label") is not None:
                        t_to_update.label = ut_item["label"]
                    if ut_item.get("condition_text") is not None:
                        t_to_update.condition_text = ut_item["condition_text"]
                    if ut_item.get("semantic_tags") is not None:
                        t_to_update.semantic_tags = ut_item["semantic_tags"]
                    if ut_item.get("is_default") is not None:
                        t_to_update.is_default = ut_item["is_default"]
                    await session.flush()

            # Track source steps that already have a default outgoing transition in this flow & workspace
            default_trans_stmt = select(FlowTransitionModel.source_step_id).where(
                FlowTransitionModel.flow_id == target_flow_id,
                FlowTransitionModel.workspace_id == ws_id,
                FlowTransitionModel.is_default == True,
            )
            default_trans_res = await session.execute(default_trans_stmt)
            sources_with_default: set[int] = set(default_trans_res.scalars().all())

            # Track max transition position per source_step_id to prevent position collisions
            max_pos_by_src: dict[int, int] = {}

            transition_temp_to_model: dict[str, FlowTransitionModel] = {}
            for t_item in payload.get("transitions_added", []):
                src_id = _resolve_step_id(t_item["source_step_ref"])
                tgt_id = _resolve_step_id(t_item["target_step_ref"])

                if src_id not in max_pos_by_src:
                    max_trans_pos_stmt = select(func.max(FlowTransitionModel.position)).where(
                        FlowTransitionModel.source_step_id == src_id,
                        FlowTransitionModel.workspace_id == ws_id,
                    )
                    max_trans_pos_res = await session.execute(max_trans_pos_stmt)
                    max_cur = max_trans_pos_res.scalar_one_or_none()
                    max_pos_by_src[src_id] = max_cur if isinstance(max_cur, int) else -1

                next_trans_pos = max_pos_by_src[src_id] + 1
                max_pos_by_src[src_id] = next_trans_pos

                # A step can have at most one default outgoing transition.
                # If a default transition already exists for this source step, demote to False.
                requested_default = bool(t_item.get("is_default", False))
                if requested_default and src_id in sources_with_default:
                    logger.info(
                        "Source step %s already has a default transition; demoting new transition %s to is_default=False",
                        src_id,
                        t_item.get("temp_id"),
                    )
                    is_default = False
                else:
                    is_default = requested_default
                    if is_default:
                        sources_with_default.add(src_id)

                trans_model = FlowTransitionModel(
                    flow_id=target_flow_id,
                    project_id=project_id,
                    workspace_id=ws_id,
                    source_step_id=src_id,
                    target_step_id=tgt_id,
                    position=next_trans_pos,
                    label=t_item["label"],
                    condition_text=t_item.get("condition_text", ""),
                    is_default=is_default,
                    semantic_tags=t_item.get("semantic_tags", []),
                )
                session.add(trans_model)
                await session.flush()
                transition_temp_to_model[t_item["temp_id"]] = trans_model

            # Two-pass rule creation makes parent resolution independent of payload order.
            rule_map: dict[str, DomainRuleModel] = {}
            rule_uuid_to_id: dict[str, int] = {}
            pending_parents: list[tuple[DomainRuleModel, str]] = []

            # Pass 1: instantiate and flush all rules without parent_rule_id
            for r_item in payload.get("rules_added", []):
                title = r_item.get("title") or r_item.get("name", "")
                rule_model = DomainRuleModel(
                    project_id=project_id,
                    workspace_id=ws_id,
                    title=title,
                    statement=r_item["statement"],
                    origin=RuleOrigin.FLOW_REFINEMENT.value,
                    confirmation_status=ConfirmationStatus.AI_ASSUMPTION.value,
                    parent_rule_id=None,
                )
                session.add(rule_model)
                await session.flush()
                rule_map[r_item["temp_id"]] = rule_model
                rule_uuid_to_id[rule_model.logical_uuid] = rule_model.id

                parent_ref = r_item.get("parent_rule_ref")
                if parent_ref:
                    pending_parents.append((rule_model, parent_ref))

                # Persist source links declared on this rule
                for sl in r_item.get("source_links", []):
                    skind = sl.get("target_kind")
                    sref = sl.get("target_ref") or sl.get("target_logical_uuid")
                    starget_uuid = sref
                    if skind == "flow_step" and sref in step_temp_to_model:
                        starget_uuid = step_temp_to_model[sref].logical_uuid
                    elif skind == "flow_transition" and sref in transition_temp_to_model:
                        starget_uuid = transition_temp_to_model[sref].logical_uuid

                    source_link = RuleLinkModel(
                        project_id=project_id,
                        workspace_id=ws_id,
                        rule_id=rule_model.id,
                        target_kind=skind,
                        target_logical_uuid=starget_uuid,
                        link_purpose=RuleLinkPurpose.SOURCE.value,
                        context_text=sl.get("context_text") or "",
                    )
                    session.add(source_link)

            # Pass 2: resolve parent_rule_id order-independently
            for rule_model, parent_ref in pending_parents:
                parent_id = None
                if parent_ref in rule_map:
                    parent_id = rule_map[parent_ref].id
                elif parent_ref in rule_uuid_to_id:
                    parent_id = rule_uuid_to_id[parent_ref]
                else:
                    parent_stmt = select(DomainRuleModel.id).where(
                        DomainRuleModel.project_id == project_id,
                        DomainRuleModel.workspace_id == ws_id,
                        DomainRuleModel.logical_uuid == parent_ref,
                    )
                    parent_res = await session.execute(parent_stmt)
                    parent_id = parent_res.scalar_one_or_none()

                if not parent_id:
                    raise ValueError(f"unresolved_parent_rule: {parent_ref}")
                rule_model.parent_rule_id = parent_id

            await session.flush()

            # Rule links resolve against both existing and candidate-local rules.
            for link_item in payload.get("rule_links_added", []):
                r_ref = link_item["rule_ref"]
                if r_ref in rule_map:
                    rule_id = rule_map[r_ref].id
                elif r_ref in rule_uuid_to_id:
                    rule_id = rule_uuid_to_id[r_ref]
                else:
                    exist_rule_stmt = select(DomainRuleModel.id).where(
                        DomainRuleModel.project_id == project_id,
                        DomainRuleModel.workspace_id == ws_id,
                        DomainRuleModel.logical_uuid == r_ref,
                    )
                    exist_res = await session.execute(exist_rule_stmt)
                    rule_id = exist_res.scalar_one_or_none()
                    if not rule_id:
                        raise ValueError(f"unresolved_rule_link_rule: {r_ref}")
                    rule_uuid_to_id[r_ref] = rule_id

                t_kind = link_item["target_kind"]
                t_ref = link_item["target_ref"]
                target_uuid = None

                if t_kind == "flow_transition":
                    if t_ref in transition_temp_to_model:
                        target_uuid = transition_temp_to_model[t_ref].logical_uuid
                    else:
                        target_uuid = t_ref
                elif t_kind == "flow_step":
                    if t_ref in step_temp_to_model:
                        target_uuid = step_temp_to_model[t_ref].logical_uuid
                    else:
                        target_uuid = t_ref
                else:
                    target_uuid = t_ref

                link_purpose = link_item.get("link_purpose") or RuleLinkPurpose.APPLIES_TO.value
                existing_link = (await session.execute(select(RuleLinkModel.id).where(
                    RuleLinkModel.project_id == project_id,
                    RuleLinkModel.workspace_id == ws_id,
                    RuleLinkModel.rule_id == rule_id,
                    RuleLinkModel.target_kind == t_kind,
                    RuleLinkModel.target_logical_uuid == target_uuid,
                    RuleLinkModel.link_purpose == link_purpose,
                ))).scalar_one_or_none()
                if existing_link is not None:
                    continue
                rule_link = RuleLinkModel(
                    project_id=project_id,
                    workspace_id=ws_id,
                    rule_id=rule_id,
                    target_kind=t_kind,
                    target_logical_uuid=target_uuid,
                    link_purpose=link_purpose,
                    context_text=link_item.get("context_text") or "",
                )
                session.add(rule_link)

            await session.flush()

            # Topology validation rejects disconnected results before the savepoint commits.
            all_steps_stmt = select(FlowStepModel).where(
                FlowStepModel.flow_id == target_flow_id,
                FlowStepModel.workspace_id == ws_id,
            )
            all_steps = (await session.execute(all_steps_stmt)).scalars().all()

            all_trans_stmt = select(FlowTransitionModel).where(
                FlowTransitionModel.flow_id == target_flow_id,
                FlowTransitionModel.workspace_id == ws_id,
            )
            all_trans = (await session.execute(all_trans_stmt)).scalars().all()

            if len(all_steps) > 1:
                connected_step_ids = set()
                for t in all_trans:
                    connected_step_ids.add(t.source_step_id)
                    connected_step_ids.add(t.target_step_id)

                isolated_steps = [s for s in all_steps if s.id not in connected_step_ids]
                if isolated_steps:
                    raise ValueError(f"refinement_produced_disconnected_graph: isolated step {isolated_steps[0].id}")

                adj: dict[int, set[int]] = {s.id: set() for s in all_steps}
                for t in all_trans:
                    if t.source_step_id in adj and t.target_step_id in adj:
                        adj[t.source_step_id].add(t.target_step_id)
                        adj[t.target_step_id].add(t.source_step_id)

                start_node = all_steps[0].id
                visited: set[int] = set()
                queue = [start_node]
                while queue:
                    curr = queue.pop(0)
                    if curr not in visited:
                        visited.add(curr)
                        queue.extend(adj[curr] - visited)

                if len(visited) != len(all_steps):
                    raise ValueError("refinement_produced_disconnected_graph")

            # The quality check rejects newly introduced blocking findings and fails closed.
            try:
                post_findings = await self._finding_policy.get_findings(
                    project_id, session, workspace_id=ws_id
                )
            except Exception as e:
                raise ValueError(f"refinement_quality_check_failed: {e}") from e

            for f in post_findings:
                is_blocking = (
                    f.severity == IssueSeverity.BLOCKING
                    or f.blockingScope != BlockingScope.NONE
                )
                if is_blocking:
                    if f.findingId not in baseline_blocking_ids:
                        raise ValueError(f"refinement_introduced_blocking_finding: {f.code} on {f.target}")

        return {
            "flow_id": target_flow_id,
            "target_flow_id": target_flow_id,
            "steps_added_count": len(step_temp_to_model),
            "transitions_added_count": len(transition_temp_to_model),
            "rules_added_count": len(rule_map),
        }
