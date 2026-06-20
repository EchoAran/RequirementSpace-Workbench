"""AI Solver for LEAF_FEATURE_WITHOUT_ACTOR issue.

Recommends existing actors to bind to a leaf feature that has no actors.
"""

import json

from sqlalchemy import select

from backend.core.issue_resolution.ai.base_ai_solver import BaseIssueAISolver, RepairResult, RepairProposal
from backend.core.issue_resolution.ai.prompts.actor_feature_coverage_repair_prompt import (
    ACTOR_FEATURE_COVERAGE_SYSTEM_PROMPT,
    ACTOR_FEATURE_COVERAGE_USER_PROMPT_TEMPLATE,
)
from backend.database.model import ActorModel, FeatureModel, ProjectModel


class ActorFeatureCoverageSolver(BaseIssueAISolver):
    """AI solver for LEAF_FEATURE_WITHOUT_ACTOR."""

    @property
    def supported_issue_codes(self) -> list[str]:
        return ["LEAF_FEATURE_WITHOUT_ACTOR"]

    def repair_type(self) -> str:
        return "bind_existing_actor"

    def get_system_prompt(self) -> str:
        return ACTOR_FEATURE_COVERAGE_SYSTEM_PROMPT

    def get_user_prompt(self, context: dict) -> str:
        actors_json = json.dumps(context.get("actors", []), ensure_ascii=False, indent=2)
        return ACTOR_FEATURE_COVERAGE_USER_PROMPT_TEMPLATE.format(
            user_requirements=context.get("user_requirements", ""),
            feature_name=context.get("feature_name", ""),
            feature_description=context.get("feature_description", ""),
            actors_json=actors_json,
            feature_id=context.get("feature_id", 0),
        )

    async def build_prompt_context(
        self,
        project_id: int,
        issue_code: str,
        target: dict | None,
        session,
    ) -> dict:
        target_id = None
        if target:
            target_id = int(target.get("target_id") or target.get("targetId") or 0)

        # Load feature
        feature = None
        if target_id:
            res = await session.execute(
                select(FeatureModel).where(FeatureModel.id == target_id, FeatureModel.project_id == project_id)
            )
            feature = res.scalar_one_or_none()

        # Load all actors
        actors_res = await session.execute(
            select(ActorModel).where(ActorModel.project_id == project_id)
        )
        actors = actors_res.scalars().all()

        # Load project
        project_res = await session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        project = project_res.scalar_one_or_none()

        actor_summary = [
            {"id": a.id, "name": a.name, "description": a.description}
            for a in actors
        ]

        return {
            "user_requirements": project.user_requirements if project else "",
            "feature_name": feature.name if feature else "",
            "feature_description": feature.description if feature else "",
            "feature_id": target_id or 0,
            "actors": actor_summary,
        }

    def parse_response(self, raw_json: dict) -> RepairResult:
        """Override: for LEAF_FEATURE_WITHOUT_ACTOR.

        - 0 candidates → manual_action
        - 1 candidate → repair_draft (default)
        - 2+ candidates with 1 high-confidence (>=0.7) → repair_draft with that one
        - 2+ candidates with multiple high-confidence → choice_group (P3)
        - 2+ candidates with no high-confidence → manual_action
        """
        result = super().parse_response(raw_json)

        if len(result.candidates) > 1:
            high_conf = [c for c in result.candidates if c.confidence >= 0.7]
            if len(high_conf) == 1:
                result.candidates = high_conf
                result.result_type = "repair_draft"
            elif len(high_conf) > 1:
                result.candidates = high_conf
                result.result_type = "choice_group"
                result.fallback_reason = "多个角色都合理，请选择"
            else:
                return RepairResult(
                    result_type="manual_action",
                    fallback_kind="manual_action",
                    fallback_reason="未找到高置信度角色匹配",
                )

        return result
