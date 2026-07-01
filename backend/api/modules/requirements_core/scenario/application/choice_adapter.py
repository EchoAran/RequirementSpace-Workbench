from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.modules.decision_workflow.ports.ports import (
    GenerationCandidate,
    CandidateContext,
    BaseGenerationChoiceAdapter,
)
from backend.api.modules.requirements_core.ports import get_scenario_generation_service


class ScenarioGenerationChoiceAdapter(BaseGenerationChoiceAdapter):
    """Generates multiple scenario candidates for a feature+actor pair."""

    generation_type = "scenario"

    def __init__(self):
        self._service = get_scenario_generation_service()

    async def generate_candidate(self, context: CandidateContext) -> GenerationCandidate:
        """Generate one scenario candidate for a pair, single, or batch target.

        Target format:
          pair:  {"generation_mode": "pair",  "feature_id": 12, "actor_id": 3}
          single: {"generation_mode": "single", "feature_id": 12}
          batch:  {"generation_mode": "batch",  "feature_ids": [12, 15]}
        """
        target = context.target or {}
        generation_mode = target.get("generation_mode", "pair")
        feature_id = target.get("feature_id")
        feature_ids = target.get("feature_ids")
        actor_id = target.get("actor_id")

        strategy_hint = f"请按 {context.strategy} 风格生成本场景集。"
        feedback = context.user_feedback or ""
        combined = f"{strategy_hint}\n{feedback}".strip()

        if generation_mode == "batch" and feature_ids:
            # Load full project context and filter target pairs for the selected features
            (
                user_requirements,
                actor_node_map,
                feature_node_map,
                target_pairs,
            ) = await self._service._load_generation_context(
                project_id=context.project_id,
                feature_id=None,
                actor_id=None,
                generation_mode="full",
                session=context.session,
            )
            feature_ids_set = set(feature_ids)
            target_pairs = [p for p in target_pairs if p[0] in feature_ids_set]

            generated_scenarios = await self._service._generate_scenarios_concurrently(
                user_requirements=user_requirements,
                actor_node_map=actor_node_map,
                feature_node_map=feature_node_map,
                target_pairs=target_pairs,
                user_feedback=combined,
            )
            scenarios = await self._service._attach_acceptance_criteria_to_generated_scenarios(
                user_requirements=user_requirements,
                actor_node_map=actor_node_map,
                feature_node_map=feature_node_map,
                generated_scenarios=generated_scenarios,
                user_feedback=combined,
            )
            feature_name = "批量功能"
            actor_name = "多角色"
        else:
            draft_payload, response_payload = await self._service._generate_preview(
                project_id=context.project_id,
                feature_id=feature_id,
                actor_id=actor_id,
                generation_mode=generation_mode,
                user_feedback=combined,
                session=context.session,
            )
            scenarios = response_payload.get("scenarios", [])
            feature_name = scenarios[0].get("feature_name", "") if scenarios else ""
            actor_name = scenarios[0].get("actor_name", "") if scenarios else ""

        # Build preview
        preview = {
            "scenario_count": len(scenarios),
            "generation_mode": generation_mode,
            "feature_id": feature_id,
            "feature_ids": feature_ids,
            "feature_name": feature_name,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "scenarios": [
                {
                    "scenario_name": s["scenario_name"],
                    "scenario_content": s["scenario_content"][:100],
                    "acceptance_criteria": s["acceptance_criteria"],
                }
                for s in scenarios
            ],
        }

        # For batch mode, create the payload matching the schema
        draft_payload = {
            "project_id": context.project_id,
            "generation_mode": generation_mode,
            "feature_id": feature_id,
            "feature_ids": feature_ids,
            "actor_id": actor_id,
            "scenarios": scenarios,
        }

        title = f"场景方案 — {len(scenarios)} 个场景" if generation_mode == "batch" else f"{feature_name} × {actor_name} — {len(scenarios)} 个场景"
        rationale = f"按 {context.strategy} 策略批量生成的场景集" if generation_mode == "batch" else f"按 {context.strategy} 策略为 {feature_name} × {actor_name} 生成的场景集"
        comparison_summary = f"批量推演场景：共 {len(scenarios)} 项" if generation_mode == "batch" else self._make_comparison_summary(context.strategy, scenarios, feature_name, actor_name)
        apply_desc = "此方案将为选定功能点新增场景" if generation_mode == "batch" else f"此方案将为 {feature_name} × {actor_name} 新增场景"

        return GenerationCandidate(
            title=title,
            rationale=rationale,
            payload=draft_payload,
            preview=preview,
            draft_type="scenario",
            apply_mode="draft_payload",
            comparison_summary=comparison_summary,
            apply_behavior="append",
            apply_behavior_description=apply_desc,
        )

    async def apply_candidate(self, payload: dict, session: AsyncSession, **kwargs) -> dict:
        """Persist scenario payload to ScenarioModel (append mode), including generated AC."""
        result = await self._service._persist_scenario_generation_draft(
            draft=payload,
            session=session,
        )

        # Invalidate perception jobs
        from backend.api.modules.requirements_core.public import get_notifier
        await get_notifier().mark_stale(
            project_id=payload["project_id"],
            stages={"what"},
            perception_kinds={"SCENARIO", "ACCEPTANCE_CRITERION"},
            session=session,
        )

        return result

    def is_duplicate(self, candidate: GenerationCandidate, existing: list[GenerationCandidate]) -> bool:
        """Detect duplicates by comparing scenario name sets."""
        def _scenario_names(c: GenerationCandidate) -> frozenset:
            return frozenset(
                s.get("scenario_name", "") for s in (c.payload or {}).get("scenarios", [])
            )
        c_names = _scenario_names(candidate)
        return any(_scenario_names(e) == c_names for e in existing)

    async def is_context_stale(self, choice, session) -> tuple[bool, str | None]:
        """Check if feature/actor has been deleted or changed since generation."""
        from backend.database.model import FeatureModel, ActorModel
        payload = choice.payload or {}
        feature_id = payload.get("feature_id") or (choice.choice_group.target or {}).get("feature_id")
        actor_id = payload.get("actor_id") or (choice.choice_group.target or {}).get("actor_id")

        if feature_id:
            feature = await session.get(FeatureModel, feature_id)
            if not feature:
                return True, f"功能（id={feature_id}）已被删除，此候选可能不适用"

        if actor_id:
            actor = await session.get(ActorModel, actor_id)
            if not actor:
                return True, f"参与者（id={actor_id}）已被删除，此候选可能不适用"

        return False, None

    @staticmethod
    def _make_comparison_summary(
        strategy: str, scenarios: list[dict], feature_name: str, actor_name: str,
    ) -> str:
        descriptions = {
            "balanced": "场景覆盖均衡",
            "comprehensive": "全面覆盖正向与异常路径",
            "minimal": "核心主路径场景",
            "risk_averse": "保守场景集",
            "workflow_first": "流程驱动场景编排",
        }
        desc = descriptions.get(strategy, strategy)
        scenario_names = ", ".join(s["scenario_name"] for s in scenarios[:3])
        return (
            f"{desc}：{len(scenarios)} 个场景（{scenario_names}）"
            f" — 针对 {feature_name} × {actor_name}"
        )
