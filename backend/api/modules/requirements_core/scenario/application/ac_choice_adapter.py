from backend.api.modules.decision_workflow.ports.ports import (
    GenerationCandidate,
    CandidateContext,
    BaseGenerationChoiceAdapter,
)
from backend.api.modules.requirements_core.ports import get_acceptance_criteria_generation_service
from backend.database.model import ScenarioAcceptanceCriterionModel
from sqlalchemy import delete


class AcceptanceCriteriaGenerationChoiceAdapter(BaseGenerationChoiceAdapter):
    """Generates multiple AC candidates for one or more scenarios."""

    generation_type = "acceptance_criteria"

    def __init__(self):
        self._service = get_acceptance_criteria_generation_service()

    async def generate_candidate(self, context: CandidateContext) -> GenerationCandidate:
        """Generate one AC candidate for a single or batch of scenarios."""
        target = context.target or {}
        mode = target.get("generation_mode", "single")
        scenario_ids = target.get("scenario_ids", [])

        # For choice groups we support single and batch, not full mode
        if mode not in ("single", "batch") or not scenario_ids:
            raise ValueError(
                f"unsupported_ac_generation_mode: {mode}, "
                "choice group supports single/batch only"
            )

        from backend.api.modules.decision_workflow.ports.ports import build_strategy_feedback
        strategy_hint = build_strategy_feedback(context, "生成验收标准")
        feedback = context.user_feedback or ""
        combined = f"{strategy_hint}\n{feedback}".strip()

        draft_payload, response_payload = await self._service._generate_preview(
            project_id=context.project_id,
            generation_mode=mode,
            scenario_ids=scenario_ids,
            user_feedback=combined,
            session=context.session,
        )

        criteria = response_payload.get("acceptance_criteria", [])
        scenario_id = scenario_ids[0] if scenario_ids else None

        # Load scenario name for preview
        scenario_name = target.get("scenario_name", f"scenario_{scenario_id}")

        strat_lbl = context.strategy_label or context.strategy
        return GenerationCandidate(
            title=f"{scenario_name} — {len(criteria)} 条验收标准",
            rationale=f"按 {strat_lbl} 策略生成的验收标准",
            payload=draft_payload,
            preview={
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "mode": mode,
                "criterion_count": len(criteria),
                "criteria": [
                    {
                        "content": c.get("criterion_content", ""),
                        "scenario_id": c.get("scenario_id"),
                    }
                    for c in criteria
                ],
            },
            draft_type="acceptance_criteria",
            apply_mode="draft_payload",
            comparison_summary=self._make_comparison_summary(
                strat_lbl, criteria, scenario_name,
            ),
            apply_behavior="overwrite",
            apply_behavior_description=f"此方案将为 {scenario_name} 新增验收标准",
            strategy_id=context.strategy_id,
            strategy_label=context.strategy_label,
        )

    async def apply_candidate(self, payload: dict, session, **kwargs) -> dict:
        scenario_ids = payload.get("scenario_ids", [])
        if scenario_ids:
            await session.execute(
                delete(ScenarioAcceptanceCriterionModel).where(
                    ScenarioAcceptanceCriterionModel.scenario_id.in_(scenario_ids)
                )
            )
            await session.flush()
        """Persist AC payload — append mode."""
        result = await self._service._persist_acceptance_criteria_generation_draft(
            draft=payload, session=session,
        )
        from backend.api.modules.requirements_core.public import get_notifier
        await get_notifier().mark_stale(
            project_id=payload["project_id"],
            stages={"what"},
            perception_kinds={"ACCEPTANCE_CRITERION"},
            session=session,
        )
        return result

    def is_duplicate(self, candidate: GenerationCandidate, existing: list[GenerationCandidate]) -> bool:
        def _content_set(c: GenerationCandidate) -> frozenset:
            return frozenset(
                ac.get("criterion_content", "")
                for ac in (c.payload or {}).get("acceptance_criteria", [])
            )
        return any(_content_set(e) == _content_set(candidate) for e in existing)

    async def is_context_stale(self, choice, session) -> tuple[bool, str | None]:
        from backend.database.model import ScenarioModel
        payload = choice.payload or {}
        for ac in payload.get("acceptance_criteria", []):
            sid = ac.get("scenario_id")
            if sid:
                s = await session.get(ScenarioModel, sid)
                if not s:
                    return True, f"场景（id={sid}）已被删除，此候选可能不适用"
        return False, None

    @staticmethod
    def _make_comparison_summary(strategy, criteria, scenario_name):
        descriptions = {
            "balanced": "标准覆盖均衡",
            "comprehensive": "全面覆盖验收条件",
            "minimal": "核心验收标准",
            "risk_averse": "保守标准集",
            "workflow_first": "流程驱动标准",
        }
        desc = descriptions.get(strategy, strategy)
        return f"{desc}：{len(criteria)} 条标准（针对 {scenario_name}）"
