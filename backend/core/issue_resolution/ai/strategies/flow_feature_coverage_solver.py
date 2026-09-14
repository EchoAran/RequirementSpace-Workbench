"""AI Solver for FLOW_WITHOUT_FEATURE.

Matches flows to leaf features by semantic analysis.
- High-confidence single match → repair_draft (addLinks.flow_feature_relation)
- Multiple matches → choice_group
- No match → manual_action
"""

import json

from sqlalchemy import select

from backend.core.issue_resolution.ai.base_ai_solver import (
    BaseIssueAISolver,
    RepairResult,
)
from backend.core.issue_resolution.ai.prompts.flow_feature_coverage_repair_prompt import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)
from backend.database.model import FeatureModel, FlowModel, ProjectModel


class FlowFeatureCoverageSolver(BaseIssueAISolver):
    """AI solver for FLOW_WITHOUT_FEATURE."""

    @property
    def supported_issue_codes(self) -> list[str]:
        return ["FLOW_WITHOUT_FEATURE"]

    def repair_type(self) -> str:
        return "bind_flow_feature"

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_user_prompt(self, context: dict) -> str:
        matches_json = json.dumps(context.get("matches", []), ensure_ascii=False, indent=2)
        return USER_PROMPT_TEMPLATE.format(
            user_requirements=context.get("user_requirements", ""),
            target_type=context.get("target_type", ""),
            target_name=context.get("target_name", ""),
            target_description=context.get("target_description", ""),
            target_id=context.get("target_id", 0),
            feature_context=context.get("feature_context", ""),
            target_match_label=context.get("target_match_label", ""),
            matches_json=matches_json,
            match_name="{match_name}",
            match_id="{match_id}",
        )

    async def build_prompt_context(
        self,
        project_id: int,
        issue_code: str,
        target: dict | None,
        session,
        workspace_id: int,
    ) -> dict:
        target_id = int(target.get("target_id") or target.get("targetId") or 0) if target else 0

        project_res = await session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        project = project_res.scalar_one_or_none()

        res = await session.execute(self._scope(
            select(FlowModel).where(
                FlowModel.id == target_id,
                FlowModel.project_id == project_id,
            )
        , FlowModel, workspace_id))
        flow = res.scalar_one_or_none()

        features_res = await session.execute(self._scope(
            select(FeatureModel).where(FeatureModel.project_id == project_id)
        , FeatureModel, workspace_id))
        features = features_res.scalars().all()
        # Determine leaf features (no FeatureRelation where they are parent)
        from backend.database.model import FeatureRelationModel
        parent_ids_res = await session.execute(
            select(FeatureRelationModel.parent_feature_id).distinct()
        )
        parent_ids = {row[0] for row in parent_ids_res.fetchall()}
        leaf_features = [f for f in features if f.id not in parent_ids]
        matches = [{"id": f.id, "name": f.name, "description": f.description} for f in leaf_features]

        return {
            "user_requirements": project.user_requirements if project else "",
            "target_type": "flow",
            "target_name": flow.name if flow else "",
            "target_description": flow.description if flow else "",
            "target_id": target_id,
            "feature_context": "",
            "target_match_label": "叶子功能",
            "matches": matches,
        }

    def parse_response(self, raw_json: dict) -> RepairResult:
        """Same pattern as ActorFeatureCoverageSolver:
        - 2+ high-confidence (>0.7) → choice_group
        - 1 high-confidence → repair_draft
        - 0 high-confidence → manual_action
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
                result.fallback_reason = "多个流程都匹配，请选择"
            else:
                return RepairResult(
                    result_type="manual_action",
                    fallback_kind="manual_action",
                    fallback_reason="未找到高置信度匹配",
                )

        return result
