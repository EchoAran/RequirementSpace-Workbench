from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.modules.decision_workflow.ports.ports import (
    GenerationCandidate,
    CandidateContext,
    BaseGenerationChoiceAdapter,
)
from backend.api.modules.requirements_core.ports import get_scenario_generation_service
from backend.database.model import ScenarioModel
from backend.core.prompt_resolver import get_content_locale


class ScenarioGenerationChoiceAdapter(BaseGenerationChoiceAdapter):
    """Generates multiple scenario candidates for a feature+actor pair."""

    generation_type = "scenario"

    def __init__(self):
        self._service = get_scenario_generation_service()

    @staticmethod
    def _build_feedback(
        context: CandidateContext,
        is_english: bool,
    ) -> str:
        from backend.api.modules.decision_workflow.ports.ports import (
            build_strategy_feedback,
        )

        strategy_hint = build_strategy_feedback(
            context,
            "scenario set" if is_english else "生成场景集",
        )
        feedback = context.user_feedback or ""
        return f"{strategy_hint}\n{feedback}".strip()

    async def _generate_batch_content(
        self,
        context: CandidateContext,
        feature_ids: list[int],
        feedback: str,
        is_english: bool,
    ) -> tuple[list[dict], str, str]:
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
        selected_feature_ids = set(feature_ids)
        target_pairs = [
            pair
            for pair in target_pairs
            if pair[0] in selected_feature_ids
        ]
        generated = await self._service._generate_scenarios_concurrently(
            user_requirements=user_requirements,
            actor_node_map=actor_node_map,
            feature_node_map=feature_node_map,
            target_pairs=target_pairs,
            user_feedback=feedback,
            max_concurrency=self._service._batch_max_concurrency,
        )
        scenarios = (
            await self._service
            ._attach_acceptance_criteria_to_generated_scenarios(
                user_requirements=user_requirements,
                actor_node_map=actor_node_map,
                feature_node_map=feature_node_map,
                generated_scenarios=generated,
                user_feedback=feedback,
                max_concurrency=self._service._batch_max_concurrency,
            )
        )
        feature_name = "Batch Features" if is_english else "批量功能"
        actor_name = "Multiple Actors" if is_english else "多角色"
        return scenarios, feature_name, actor_name

    async def _generate_target_content(
        self,
        context: CandidateContext,
        *,
        generation_mode: str,
        feature_id: int | None,
        actor_id: int | None,
        feedback: str,
    ) -> tuple[list[dict], str, str]:
        _, response = await self._service._generate_preview(
            project_id=context.project_id,
            feature_id=feature_id,
            actor_id=actor_id,
            generation_mode=generation_mode,
            user_feedback=feedback,
            session=context.session,
        )
        scenarios = response.get("scenarios", [])
        feature_name = (
            scenarios[0].get("feature_name", "")
            if scenarios
            else ""
        )
        actor_name = (
            scenarios[0].get("actor_name", "")
            if scenarios
            else ""
        )
        return scenarios, feature_name, actor_name

    @staticmethod
    def _build_preview(
        scenarios: list[dict],
        *,
        generation_mode: str,
        feature_id: int | None,
        feature_ids: list[int] | None,
        feature_name: str,
        actor_id: int | None,
        actor_name: str,
    ) -> dict:
        return {
            "scenario_count": len(scenarios),
            "generation_mode": generation_mode,
            "feature_id": feature_id,
            "feature_ids": feature_ids,
            "feature_name": feature_name,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "scenarios": [
                {
                    "scenario_name": item["scenario_name"],
                    "scenario_content": item["scenario_content"][:100],
                    "acceptance_criteria": item["acceptance_criteria"],
                }
                for item in scenarios
            ],
        }

    def _build_candidate_metadata(
        self,
        context: CandidateContext,
        *,
        scenarios: list[dict],
        generation_mode: str,
        feature_name: str,
        actor_name: str,
        is_english: bool,
    ) -> tuple[str, str, str, str]:
        strategy = context.strategy_label or context.strategy
        is_batch = generation_mode == "batch"
        if is_english:
            title = (
                f"Scenario Option — {len(scenarios)} scenarios"
                if is_batch
                else (
                    f"{feature_name} × {actor_name} — "
                    f"{len(scenarios)} scenarios"
                )
            )
            rationale = (
                f"Scenario set generated in batch using the {strategy} strategy"
                if is_batch
                else (
                    f"Scenario set generated for {feature_name} × "
                    f"{actor_name} using the {strategy} strategy"
                )
            )
            summary = (
                f"Batch scenario generation: {len(scenarios)} items"
                if is_batch
                else self._make_comparison_summary(
                    strategy,
                    scenarios,
                    feature_name,
                    actor_name,
                    is_english=True,
                )
            )
            description = (
                "This option clears and rebuilds the scenarios and "
                "acceptance criteria in the target scope"
            )
            return title, rationale, summary, description
        title = (
            f"场景方案 — {len(scenarios)} 个场景"
            if is_batch
            else f"{feature_name} × {actor_name} — {len(scenarios)} 个场景"
        )
        rationale = (
            f"按 {strategy} 策略批量生成的场景集"
            if is_batch
            else (
                f"按 {strategy} 策略为 {feature_name} × "
                f"{actor_name} 生成的场景集"
            )
        )
        summary = (
            f"批量推演场景：共 {len(scenarios)} 项"
            if is_batch
            else self._make_comparison_summary(
                strategy,
                scenarios,
                feature_name,
                actor_name,
            )
        )
        description = "此方案将清空并重建目标范围内的场景与验收标准"
        return title, rationale, summary, description

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
        is_english = get_content_locale() == "en-US"
        feedback = self._build_feedback(context, is_english)

        if generation_mode == "batch" and feature_ids:
            scenarios, feature_name, actor_name = (
                await self._generate_batch_content(
                    context,
                    feature_ids,
                    feedback,
                    is_english,
                )
            )
        else:
            scenarios, feature_name, actor_name = (
                await self._generate_target_content(
                    context,
                    generation_mode=generation_mode,
                    feature_id=feature_id,
                    actor_id=actor_id,
                    feedback=feedback,
                )
            )

        preview = self._build_preview(
            scenarios,
            generation_mode=generation_mode,
            feature_id=feature_id,
            feature_ids=feature_ids,
            feature_name=feature_name,
            actor_id=actor_id,
            actor_name=actor_name,
        )
        draft_payload = {
            "project_id": context.project_id,
            "generation_mode": generation_mode,
            "feature_id": feature_id,
            "feature_ids": feature_ids,
            "actor_id": actor_id,
            "scenarios": scenarios,
        }
        title, rationale, comparison_summary, apply_desc = (
            self._build_candidate_metadata(
                context,
                scenarios=scenarios,
                generation_mode=generation_mode,
                feature_name=feature_name,
                actor_name=actor_name,
                is_english=is_english,
            )
        )
        return GenerationCandidate(
            title=title,
            rationale=rationale,
            payload=draft_payload,
            preview=preview,
            draft_type="scenario",
            apply_mode="draft_payload",
            comparison_summary=comparison_summary,
            apply_behavior="overwrite",
            apply_behavior_description=apply_desc,
            strategy_id=context.strategy_id,
            strategy_label=context.strategy_label,
        )

    async def apply_candidate(self, payload: dict, session: AsyncSession, **kwargs) -> dict:
        project_id = payload["project_id"]
        feature_ids = payload.get("feature_ids") or ([payload["feature_id"]] if payload.get("feature_id") else [])
        statement = select(ScenarioModel).where(ScenarioModel.project_id == project_id)
        if feature_ids:
            statement = statement.where(ScenarioModel.feature_id.in_(feature_ids))
        if payload.get("actor_id"):
            statement = statement.where(ScenarioModel.actor_id == payload["actor_id"])
        existing = await session.execute(statement)
        for scenario in existing.scalars().all():
            await session.delete(scenario)
        await session.flush()
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
        strategy: str,
        scenarios: list[dict],
        feature_name: str,
        actor_name: str,
        is_english: bool = False,
    ) -> str:
        descriptions = ({
            "balanced": "Balanced scenario coverage",
            "comprehensive": "Comprehensive positive and exception-path coverage",
            "minimal": "Core happy-path scenarios",
            "risk_averse": "Risk-averse scenario set",
            "workflow_first": "Workflow-driven scenario organization",
        } if is_english else {
            "balanced": "场景覆盖均衡",
            "comprehensive": "全面覆盖正向与异常路径",
            "minimal": "核心主路径场景",
            "risk_averse": "保守场景集",
            "workflow_first": "流程驱动场景编排",
        })
        desc = descriptions.get(strategy, strategy)
        scenario_names = ", ".join(s["scenario_name"] for s in scenarios[:3])
        if is_english:
            return (
                f"{desc}: {len(scenarios)} scenarios ({scenario_names})"
                f" — for {feature_name} × {actor_name}"
            )
        return (
            f"{desc}：{len(scenarios)} 个场景（{scenario_names}）"
            f" — 针对 {feature_name} × {actor_name}"
        )
