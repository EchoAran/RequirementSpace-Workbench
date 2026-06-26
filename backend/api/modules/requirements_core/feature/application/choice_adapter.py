from sqlalchemy import select

from backend.api.modules.decision_workflow.ports.ports import (
    GenerationCandidate,
    CandidateContext,
    BaseGenerationChoiceAdapter,
)
from backend.api.modules.requirements_core.feature.application.feature_generation_service import FeatureGenerationService
from backend.database.model import FeatureModel


class FeatureGenerationChoiceAdapter(BaseGenerationChoiceAdapter):
    """Generates multiple feature tree candidates (initial generation only)."""

    generation_type = "feature"

    def __init__(self):
        self._service = FeatureGenerationService()

    async def generate_candidate(self, context: CandidateContext) -> GenerationCandidate:
        """Generate one feature tree candidate."""
        strategy_hint = f"请按 {context.strategy} 风格生成功能树。"
        feedback = context.user_feedback or ""
        combined = f"{strategy_hint}\n{feedback}".strip()

        draft_payload, response_payload = await self._service._generate_preview(
            project_id=context.project_id,
            user_feedback=combined,
            session=context.session,
        )

        features = response_payload.get("features", [])

        return GenerationCandidate(
            title=f"{context.strategy.capitalize()} — {len(features)} 项功能",
            rationale=f"按 {context.strategy} 策略生成的功能树",
            payload=draft_payload,
            preview={
                "feature_count": len(features),
                "features": features,
            },
            draft_type="feature",
            apply_mode="draft_payload",
            comparison_summary=self._make_comparison_summary(
                context.strategy, features,
            ),
            apply_behavior="overwrite",
            apply_behavior_description="此方案将替换项目的完整功能树",
        )

    async def apply_candidate(self, payload: dict, session, **kwargs) -> dict:
        """Persist feature tree — overwrite mode, rejects if features already exist."""
        try:
            result = await self._service._persist_feature_generation_draft(
                draft=payload, session=session,
            )
        except ValueError as e:
            if "features_already_exist" in str(e):
                raise ValueError(
                    "项目已有功能列表，此候选与当前项目状态不兼容。"
                    "请重新生成或先删除现有功能。"
                ) from e
            raise

        from backend.api.modules.requirements_core.public import get_notifier
        await get_notifier().mark_stale(
            project_id=payload["project_id"],
            stages={"what", "how", "scope"},
            perception_kinds={"FEATURE", "SCENARIO", "ACCEPTANCE_CRITERION", "FLOW"},
            session=session,
        )
        return result

    def is_duplicate(self, candidate: GenerationCandidate, existing: list[GenerationCandidate]) -> bool:
        def _feature_names(c: GenerationCandidate) -> frozenset:
            return frozenset(
                f.get("feature_name", "") for f in (c.payload or {}).get("features", [])
            )
        return any(_feature_names(e) == _feature_names(candidate) for e in existing)

    async def is_context_stale(self, choice, session) -> tuple[bool, str | None]:
        from backend.database.model import FeatureModel
        project_id = choice.payload.get("project_id") or choice.choice_group.project_id
        existing = await session.execute(
            select(FeatureModel).where(FeatureModel.project_id == project_id)
        )
        existing_features = existing.scalars().all()
        # If project had no features at generation time but now has some
        generated_features = (choice.payload or {}).get("features", [])
        if not generated_features:
            return False, None
        if existing_features:
            return True, (
                f"项目已包含 {len(existing_features)} 项功能。"
                "此完整树候选可能不再适用。请重新生成。"
            )
        return False, None

    @staticmethod
    def _make_comparison_summary(strategy, features):
        descriptions = {
            "balanced": "功能树均衡",
            "comprehensive": "功能全面覆盖",
            "minimal": "最小功能集",
            "risk_averse": "保守功能定义",
            "workflow_first": "流程驱动功能",
        }
        desc = descriptions.get(strategy, strategy)
        feature_names = ", ".join(f["feature_name"] for f in features[:4])
        return f"{desc}：{len(features)} 项功能（{feature_names}）"
