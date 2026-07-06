from backend.api.modules.decision_workflow.ports.ports import (
    GenerationCandidate,
    CandidateContext,
    BaseGenerationChoiceAdapter,
)
from backend.api.modules.requirements_core.ports import get_scope_generation_service


class ScopeGenerationChoiceAdapter(BaseGenerationChoiceAdapter):
    """Generates multiple scope/Kano candidates for features."""

    generation_type = "scope"

    def __init__(self):
        self._service = get_scope_generation_service()

    async def generate_candidate(self, context: CandidateContext) -> GenerationCandidate:
        """Generate one scope/Kano candidate."""
        # Full scope can be heavy; limit to 2 candidates
        from backend.api.modules.decision_workflow.ports.ports import build_strategy_feedback
        strategy_hint = build_strategy_feedback(context, "生成范围分析")
        feedback = context.user_feedback or ""
        combined = f"{strategy_hint}\n{feedback}".strip()

        draft_payload, response_payload = await self._service._generate_preview(
            project_id=context.project_id,
            user_feedback=combined,
            session=context.session,
        )

        scopes = response_payload.get("scopes", [])

        # Build lightweight preview (omit base64 for candidate comparison)
        strat_lbl = context.strategy_label or context.strategy
        return GenerationCandidate(
            title=f"{strat_lbl} — {len(scopes)} 项范围决策",
            rationale=f"按 {strat_lbl} 策略生成的范围分析",
            payload=draft_payload,
            preview={
                "scope_count": len(scopes),
                "scopes": [
                    {
                        "feature_name": s.get("feature_name", ""),
                        "scope_status": s.get("scope_status", ""),
                        "reason": s.get("reason", "")[:200],
                        "kano_category": s.get("kano_category", ""),
                    }
                    for s in scopes
                ],
            },
            draft_type="scope",
            apply_mode="draft_payload",
            comparison_summary=self._make_comparison_summary(strat_lbl, scopes),
            apply_behavior="overwrite",
            apply_behavior_description="此方案将替换当前范围决策",
            strategy_id=context.strategy_id,
            strategy_label=context.strategy_label,
        )

    async def apply_candidate(self, payload: dict, session, **kwargs) -> dict:
        result = await self._service._persist_scope_generation_draft(
            draft=payload, session=session,
        )
        # Update Project Kano Status to generated (completed)
        from backend.database.model import ProjectModel
        project_id = payload["project_id"]
        project = await session.get(ProjectModel, project_id)
        if project:
            project.kano_status = "generated"
            project.unlocked_stages = "what,how,scope"

        from backend.api.modules.requirements_core.public import get_notifier
        await get_notifier().mark_stale(
            project_id=payload["project_id"],
            stages={"scope"},
            perception_kinds={"SCOPE"},
            session=session,
        )
        return result

    def is_duplicate(self, candidate: GenerationCandidate, existing: list[GenerationCandidate]) -> bool:
        def _scope_keys(c: GenerationCandidate) -> frozenset:
            return frozenset(
                (s.get("feature_id"), s.get("scope_status"))
                for s in (c.payload or {}).get("scopes", [])
            )
        return any(_scope_keys(e) == _scope_keys(candidate) for e in existing)

    async def is_context_stale(self, choice, session) -> tuple[bool, str | None]:
        from backend.database.model import FeatureModel
        payload = choice.payload or {}
        for s in payload.get("scopes", []):
            fid = s.get("feature_id")
            if fid:
                feature = await session.get(FeatureModel, fid)
                if not feature:
                    return True, f"功能（id={fid}）已被删除，此候选可能不适用"
        return False, None

    @staticmethod
    def _make_comparison_summary(strategy, scopes):
        descriptions = {
            "balanced": "范围划分均衡",
            "comprehensive": "全面范围分析",
            "minimal": "核心范围定义",
            "risk_averse": "保守范围",
            "workflow_first": "流程驱动范围",
        }
        desc = descriptions.get(strategy, strategy)
        current = sum(1 for s in scopes if s.get("scope_status") == "current")
        postponed = sum(1 for s in scopes if s.get("scope_status") == "postponed")
        excluded = sum(1 for s in scopes if s.get("scope_status") == "exclude")
        return f"{desc}：{len(scopes)} 项（当前={current}, 推迟={postponed}, 不纳入={excluded}）"
