"""AI Solver for FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO (strict limited version).

AI judges whether an existing scenario can be reused by fixing its feature_id.
- Clear reuse candidate → repair_draft (update scenario.feature_id)
- Multiple candidates → choice_group
- No suitable reuse → fallback_to_registry=True → falls back to generation_draft
"""

import json

from sqlalchemy import select

from backend.core.detectors.issue_solvers.ai_issue_solver import (
    BaseIssueAISolver,
    RepairResult,
)
from backend.core.detectors.issue_solvers.prompts.scenario_coverage_repair_prompt import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)
from backend.database.model import ActorModel, FeatureModel, ProjectModel, ScenarioModel


class ScenarioCoverageSolver(BaseIssueAISolver):
    """AI solver for FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO.

    Only reuses existing scenarios by fixing feature_id when clearly wrong.
    Does NOT modify actor_id (higher risk, deferred to P5).
    Falls back to generation_draft when no suitable reuse is found.
    """

    @property
    def supported_issue_codes(self) -> list[str]:
        return ["FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO"]

    def repair_type(self) -> str:
        return "reassign_scenario_feature"

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_user_prompt(self, context: dict) -> str:
        scenarios_json = json.dumps(context.get("scenarios", []), ensure_ascii=False, indent=2)
        return USER_PROMPT_TEMPLATE.format(
            user_requirements=context.get("user_requirements", ""),
            feature_name=context.get("feature_name", ""),
            feature_description=context.get("feature_description", ""),
            actor_name=context.get("actor_name", ""),
            actor_description=context.get("actor_description", ""),
            feature_id=context.get("feature_id", 0),
            scenarios_json=scenarios_json,
            scenario_name="{scenario_name}",
            scenario_id="{scenario_id}",
        )

    async def build_prompt_context(
        self,
        project_id: int,
        issue_code: str,
        target: dict | None,
        session,
    ) -> dict:
        target_id = target.get("target_id") or target.get("targetId") or "" if target else ""
        feature_id, actor_id = None, None
        if isinstance(target_id, str) and ":" in target_id:
            parts = target_id.split(":", 1)
            try:
                feature_id = int(parts[0])
                actor_id = int(parts[1])
            except (ValueError, TypeError):
                pass
        elif target:
            feature_id = int(target.get("feature_id") or target.get("featureId") or 0)
            actor_id = int(target.get("actor_id") or target.get("actorId") or 0)

        project_res = await session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        project = project_res.scalar_one_or_none()

        feature = None
        if feature_id:
            res = await session.execute(
                select(FeatureModel).where(
                    FeatureModel.id == feature_id,
                    FeatureModel.project_id == project_id,
                )
            )
            feature = res.scalar_one_or_none()

        actor = None
        if actor_id:
            res = await session.execute(
                select(ActorModel).where(
                    ActorModel.id == actor_id,
                    ActorModel.project_id == project_id,
                )
            )
            actor = res.scalar_one_or_none()

        # Load all scenarios for context (but only those belonging to the same actor or feature)
        scenarios_res = await session.execute(
            select(ScenarioModel).where(ScenarioModel.project_id == project_id)
        )
        all_scenarios = scenarios_res.scalars().all()
        scenarios = [
            {"id": s.id, "name": s.name, "content": s.content[:200], "feature_id": s.feature_id, "actor_id": s.actor_id}
            for s in all_scenarios
        ]

        return {
            "user_requirements": project.user_requirements if project else "",
            "feature_name": feature.name if feature else "",
            "feature_description": feature.description if feature else "",
            "actor_name": actor.name if actor else "",
            "actor_description": actor.description if actor else "",
            "feature_id": feature_id or 0,
            "scenarios": scenarios,
        }

    def parse_response(self, raw_json: dict) -> RepairResult:
        """Override: when no suitable reuse, set fallback_to_registry=True so
        IssueRepairService falls back to generation_draft via registry."""
        result = super().parse_response(raw_json)

        # If no candidates and fallback is generation_draft → signal registry fallback
        if not result.candidates and result.fallback_reason:
            # Use the raw JSON fallback kind to decide
            fallback_kind = raw_json.get("fallback", {}).get("kind", "manual_action")
            if fallback_kind == "generation_draft":
                return RepairResult(
                    result_type="repair_draft",
                    candidates=[],
                    fallback_to_registry=True,
                    fallback_reason="无合适复用场景，走创建新场景流程",
                )

        return result
