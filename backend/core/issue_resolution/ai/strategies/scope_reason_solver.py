"""AI Solver for SCOPE_WITHOUT_REASON issue.

Generates a reason text for a scope decision that has no rationale.
"""

from sqlalchemy import select

from backend.core.issue_resolution.ai.base_ai_solver import BaseIssueAISolver, RepairResult
from backend.core.issue_resolution.ai.prompts.scope_reason_repair_prompt import (
    SCOPE_REASON_SYSTEM_PROMPT,
    SCOPE_REASON_USER_PROMPT_TEMPLATE,
)
from backend.database.model import ScopeModel


class ScopeReasonSolver(BaseIssueAISolver):
    """AI solver for SCOPE_WITHOUT_REASON."""

    @property
    def supported_issue_codes(self) -> list[str]:
        return ["SCOPE_WITHOUT_REASON"]

    def repair_type(self) -> str:
        return "fill_scope_reason"

    def get_system_prompt(self) -> str:
        return SCOPE_REASON_SYSTEM_PROMPT

    def get_user_prompt(self, context: dict) -> str:
        return SCOPE_REASON_USER_PROMPT_TEMPLATE.format(
            user_requirements=context.get("user_requirements", ""),
            feature_name=context.get("feature_name", ""),
            scope_status=context.get("scope_status", "CURRENT"),
            scope_id=context.get("scope_id", 0),
        )

    async def build_prompt_context(
        self,
        project_id: int,
        issue_code: str,
        target: dict | None,
        session,
    ) -> dict:
        from backend.database.model import ProjectModel, FeatureModel

        target_id = None
        if target:
            target_id = int(target.get("target_id") or target.get("targetId") or 0)

        # Load scope (ScopeModel has no project_id — join through FeatureModel)
        scope = None
        if target_id:
            from backend.database.model import FeatureModel
            res = await session.execute(
                select(ScopeModel).join(FeatureModel, ScopeModel.feature_id == FeatureModel.id)
                .where(ScopeModel.id == target_id, FeatureModel.project_id == project_id)
            )
            scope = res.scalar_one_or_none()

        # Load project for user_requirements
        project_res = await session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        project = project_res.scalar_one_or_none()

        # Load feature
        feature_name = ""
        if scope and scope.feature_id:
            feat_res = await session.execute(
                select(FeatureModel).where(FeatureModel.id == scope.feature_id)
            )
            feature = feat_res.scalar_one_or_none()
            if feature:
                feature_name = feature.name

        return {
            "user_requirements": project.user_requirements if project else "",
            "feature_name": feature_name,
            "scope_status": scope.status if scope else "CURRENT",
            "scope_id": target_id or 0,
        }
