"""ChoiceGroup adapter for bounded flow refinement candidates."""

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.modules.decision_workflow.ports.ports import (
    BaseGenerationChoiceAdapter,
    CandidateContext,
    GenerationCandidate,
    build_strategy_feedback,
)
from backend.api.modules.requirements_core.flow_refinement.application.context_loader import (
    load_flow_refinement_context,
)
from backend.api.modules.requirements_core.flow_refinement.schemas import (
    FlowRefinementCandidatePayload,
)
from backend.api.modules.requirements_core.ports import get_flow_refinement_service
from backend.core.logging.events import (
    FLOW_REFINEMENT_ACCEPTED,
    FLOW_REFINEMENT_FAILED,
    FLOW_REFINEMENT_GENERATED,
    FLOW_REFINEMENT_STALE,
)
from backend.core.observability import emit_how_lifecycle_event


class FlowRefinementChoiceAdapter(BaseGenerationChoiceAdapter):
    """Generates and manages bounded flow path refinement candidates in ChoiceGroup."""

    generation_type = "flow_refinement"

    def __init__(self):
        self._service = get_flow_refinement_service()

    async def generate_candidate(
        self, context: CandidateContext
    ) -> GenerationCandidate:
        """Generate a single refinement candidate package."""
        target = context.target or {}
        focus_step_id = target.get("focus_step_id")
        flow_id = target.get("flow_id")

        if target.get("target_id") or target.get("id"):
            target_id = target.get("target_id") or target.get("id")
            target_kind = target.get("target_kind", "flow_step" if focus_step_id else "flow")
        elif focus_step_id:
            target_kind = "flow_step"
            target_id = focus_step_id
        elif flow_id:
            target_kind = "flow"
            target_id = flow_id
        else:
            raise ValueError("missing_target_id_for_refinement")

        strategy_hint = build_strategy_feedback(context, "深化流程路径与规则")
        feedback = context.user_feedback or ""
        combined = f"{strategy_hint}\n{feedback}".strip()

        try:
            draft_payload, response_payload = await self._service._generate_preview(
                project_id=context.project_id,
                target_kind=target_kind,
                target_id=target_id,
                user_feedback=combined,
                session=context.session,
                workspace_id=context.workspace_id,
                source_finding_id=target.get("source_finding_id"),
            )
        except Exception as error:
            emit_how_lifecycle_event(
                FLOW_REFINEMENT_FAILED,
                capability="flow_refinement",
                project_id=context.project_id,
                workspace_id=context.workspace_id,
                error_code=type(error).__name__,
                level=logging.ERROR,
            )
            raise

        # Strict runtime schema validation (forbid extra fields)
        FlowRefinementCandidatePayload.model_validate(draft_payload)
        emit_how_lifecycle_event(
            FLOW_REFINEMENT_GENERATED,
            capability="flow_refinement",
            project_id=context.project_id,
            workspace_id=context.workspace_id,
            flow_logical_uuid=draft_payload.get("target_flow_logical_uuid"),
            correlation_id=draft_payload.get("context_hash"),
            steps_added=len(draft_payload.get("steps_added", [])),
            transitions_added=len(draft_payload.get("transitions_added", [])),
            rules_added=len(draft_payload.get("rules_added", [])),
        )

        is_done_empty = bool(response_payload.get("done_empty") or draft_payload.get("done_empty"))
        strat_lbl = context.strategy_label or context.strategy
        steps_count = response_payload.get("steps_added_count", 0)
        transitions_count = response_payload.get("transitions_added_count", 0)
        rules_count = response_payload.get("rules_added_count", 0)

        if is_done_empty:
            title = f"{strat_lbl} — 无需细化 (合法空结果)"
            rationale = draft_payload.get("rationale") or "目标范围流程路径与业务规则已完备，无需增补新分支"
            comparison_summary = [
                f"目标流程：{response_payload.get('target_flow_name')}",
                "结论：当前局部范围完备，无新增步骤或规则",
            ]
            apply_desc = "确认当前流程或局部步骤已完备，无需进行额外变更"
        else:
            title = f"{strat_lbl} — +{steps_count} 步骤, +{transitions_count} 转移, +{rules_count} 规则"
            rationale = draft_payload.get("rationale") or f"按 {strat_lbl} 策略细化流程分支"
            comparison_summary = [
                f"目标流程：{response_payload.get('target_flow_name')}",
                f"新增步骤：{steps_count} 个",
                f"新增/更新转移：{transitions_count + response_payload.get('transitions_updated_count', 0)} 条",
                f"细化业务规则：{rules_count} 条",
            ]
            apply_desc = "此方案将在单一事务内原子补充新步骤、转移及关联规则，不删除既有内容"

        return GenerationCandidate(
            title=title,
            rationale=rationale,
            payload=draft_payload,
            preview=response_payload,
            draft_type="flow_refinement",
            apply_mode="draft_payload",
            comparison_summary=comparison_summary,
            apply_behavior="atomic_increment",
            apply_behavior_description=apply_desc,
            strategy_id=context.strategy_id,
            strategy_label=context.strategy_label,
        )

    async def apply_candidate(
        self, payload: dict, session: AsyncSession, **kwargs
    ) -> dict:
        """Apply candidate increment to the official workspace in a single transaction."""
        # Strict runtime schema validation (forbid extra fields)
        FlowRefinementCandidatePayload.model_validate(payload)
        workspace_id = kwargs["workspace_id"]
        expected_version = kwargs.get("expected_workspace_version")

        try:
            result = await self._service.apply_refinement(
                payload=payload,
                session=session,
                workspace_id=workspace_id,
                expected_workspace_version=expected_version,
            )
        except Exception as error:
            emit_how_lifecycle_event(
                FLOW_REFINEMENT_FAILED,
                capability="flow_refinement",
                project_id=payload.get("project_id"),
                workspace_id=workspace_id,
                flow_logical_uuid=payload.get("target_flow_logical_uuid"),
                correlation_id=payload.get("context_hash"),
                error_code=type(error).__name__,
                level=logging.ERROR,
            )
            raise
        emit_how_lifecycle_event(
            FLOW_REFINEMENT_ACCEPTED,
            capability="flow_refinement",
            project_id=payload.get("project_id"),
            workspace_id=workspace_id,
            flow_logical_uuid=payload.get("target_flow_logical_uuid"),
            correlation_id=payload.get("context_hash"),
            steps_added=len(payload.get("steps_added", [])),
            transitions_added=len(payload.get("transitions_added", [])),
            rules_added=len(payload.get("rules_added", [])),
        )
        return result

    def is_duplicate(
        self, candidate: GenerationCandidate, existing: list[GenerationCandidate]
    ) -> bool:
        """Compare all proposed changes without collapsing distinct rule-only refinements."""
        def signature(item: GenerationCandidate) -> tuple:
            return tuple(
                tuple(sorted(json.dumps(value, sort_keys=True, ensure_ascii=False) for value in item.payload.get(key, [])))
                for key in (
                    "steps_added", "transitions_added", "transitions_updated",
                    "rules_added", "rule_links_added", "business_objects_added",
                )
            )

        return any(signature(candidate) == signature(other) for other in existing)

    async def is_context_stale(self, choice, session: AsyncSession) -> tuple[bool, str | None]:
        """Detect if target flow or upstream rules drifted from candidate baseline."""
        payload = choice.payload or {}
        saved_hash = payload["expected_workspace_version"]
        if not saved_hash:
            return True, "flow_refinement_context_hash_missing"

        project_id = payload.get("project_id")
        if project_id is None:
            raise ValueError("flow_refinement_choice_project_missing")
        target_kind = payload["target_kind"]
        target_id = payload["target_id"]
        workspace_id = payload["workspace_id"]

        current_ctx = await load_flow_refinement_context(
            session=session,
            project_id=project_id,
            target_kind=target_kind,
            target_id=target_id,
            workspace_id=workspace_id,
            source_finding_id=payload.get("source_finding_id"),
        )

        is_stale = str(saved_hash) != str(current_ctx.context_hash)
        if is_stale:
            emit_how_lifecycle_event(
                FLOW_REFINEMENT_STALE,
                capability="flow_refinement",
                project_id=project_id,
                workspace_id=workspace_id,
                flow_logical_uuid=payload.get("target_flow_logical_uuid"),
                correlation_id=payload.get("context_hash"),
            )
        return is_stale, "flow_refinement_context_changed" if is_stale else None
