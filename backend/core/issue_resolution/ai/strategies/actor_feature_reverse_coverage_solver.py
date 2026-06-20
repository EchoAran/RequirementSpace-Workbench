"""AI Solver for ACTOR_WITHOUT_FEATURE issue.

Recommends leaf features to associate with an isolated actor.
"""

import json
from sqlalchemy import select

from backend.core.issue_resolution.ai.base_ai_solver import BaseIssueAISolver, RepairResult, RepairProposal
from backend.core.issue_resolution.ai.prompts.actor_feature_reverse_coverage_repair_prompt import (
    ACTOR_FEATURE_REVERSE_COVERAGE_SYSTEM_PROMPT,
    ACTOR_FEATURE_REVERSE_COVERAGE_USER_PROMPT_TEMPLATE,
)
from backend.database.model import ActorModel, FeatureModel, FeatureRelationModel, ProjectModel


class ActorFeatureReverseCoverageSolver(BaseIssueAISolver):
    """AI solver for ACTOR_WITHOUT_FEATURE."""

    @property
    def supported_issue_codes(self) -> list[str]:
        return ["ACTOR_WITHOUT_FEATURE"]

    def repair_type(self) -> str:
        return "bind_existing_actor"

    def get_system_prompt(self) -> str:
        return ACTOR_FEATURE_REVERSE_COVERAGE_SYSTEM_PROMPT

    def get_user_prompt(self, context: dict) -> str:
        features_json = json.dumps(context.get("features", []), ensure_ascii=False, indent=2)
        return ACTOR_FEATURE_REVERSE_COVERAGE_USER_PROMPT_TEMPLATE.format(
            user_requirements=context.get("user_requirements", ""),
            actor_name=context.get("actor_name", ""),
            actor_description=context.get("actor_description", ""),
            features_json=features_json,
            actor_id=context.get("actor_id", 0),
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

        # Load target actor
        actor = None
        if target_id:
            res = await session.execute(
                select(ActorModel).where(ActorModel.id == target_id, ActorModel.project_id == project_id)
            )
            actor = res.scalar_one_or_none()

        # Load parent feature IDs to find leaf features
        relations_res = await session.execute(
            select(FeatureRelationModel.parent_feature_id)
        )
        parent_ids = {r[0] for r in relations_res.all()}

        # Load all features
        features_res = await session.execute(
            select(FeatureModel).where(FeatureModel.project_id == project_id)
        )
        all_features = features_res.scalars().all()
        leaf_features = [f for f in all_features if f.id not in parent_ids]

        # Load project
        project_res = await session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        project = project_res.scalar_one_or_none()

        feature_summary = [
            {"id": f.id, "name": f.name, "description": f.description}
            for f in leaf_features
        ]

        return {
            "user_requirements": project.user_requirements if project else "",
            "actor_name": actor.name if actor else "",
            "actor_description": actor.description if actor else "",
            "actor_id": target_id or 0,
            "features": feature_summary,
        }

    def parse_response(self, raw_json: dict) -> RepairResult:
        """Override: for ACTOR_WITHOUT_FEATURE.

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
                result.fallback_reason = "多个关联功能均合理，请选择"
            else:
                return RepairResult(
                    result_type="manual_action",
                    fallback_kind="manual_action",
                    fallback_reason="未找到高置信度关联功能",
                )

        return result
