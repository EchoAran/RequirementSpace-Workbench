"""AI Solver for FLOW_WITHOUT_STEPS issue.

Analyzes flow context and returns structured manual step recommendations.
"""

import json
from sqlalchemy import select

from backend.core.issue_resolution.ai.base_ai_solver import BaseIssueAISolver, RepairResult, RepairProposal
from backend.core.issue_resolution.ai.prompts.flow_without_steps_prompt import (
    FLOW_WITHOUT_STEPS_SYSTEM_PROMPT,
    FLOW_WITHOUT_STEPS_USER_PROMPT_TEMPLATE,
)
from backend.database.model import ActorModel, BusinessObjectModel, FeatureModel, FlowModel, ProjectModel, flow_feature_table


class FlowWithoutStepsSolver(BaseIssueAISolver):
    """AI solver for FLOW_WITHOUT_STEPS."""

    @property
    def supported_issue_codes(self) -> list[str]:
        return ["FLOW_WITHOUT_STEPS"]

    def repair_type(self) -> str:
        return "design_steps"

    def get_system_prompt(self) -> str:
        return FLOW_WITHOUT_STEPS_SYSTEM_PROMPT

    def get_user_prompt(self, context: dict) -> str:
        actors_json = json.dumps(context.get("actors", []), ensure_ascii=False, indent=2)
        business_objects_json = json.dumps(context.get("business_objects", []), ensure_ascii=False, indent=2)
        return FLOW_WITHOUT_STEPS_USER_PROMPT_TEMPLATE.format(
            flow_name=context.get("flow_name", ""),
            flow_description=context.get("flow_description", ""),
            feature_name=context.get("feature_name", ""),
            feature_description=context.get("feature_description", ""),
            user_requirements=context.get("user_requirements", ""),
            actors_json=actors_json,
            business_objects_json=business_objects_json,
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

        # Load target flow
        flow = None
        if target_id:
            res = await session.execute(
                select(FlowModel).where(FlowModel.id == target_id, FlowModel.project_id == project_id)
            )
            flow = res.scalar_one_or_none()

        # Load features linked to this flow
        feature_name = ""
        feature_description = ""
        if flow:
            feats_res = await session.execute(
                select(FeatureModel)
                .join(flow_feature_table, FeatureModel.id == flow_feature_table.c.feature_id)
                .where(flow_feature_table.c.flow_id == flow.id)
            )
            linked_features = feats_res.scalars().all()
            if linked_features:
                feature_name = linked_features[0].name
                feature_description = linked_features[0].description

        # Load project requirements
        project_res = await session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        project = project_res.scalar_one_or_none()

        # Load actors
        actors_res = await session.execute(
            select(ActorModel).where(ActorModel.project_id == project_id)
        )
        actors = actors_res.scalars().all()

        # Load business objects
        bos_res = await session.execute(
            select(BusinessObjectModel).where(BusinessObjectModel.project_id == project_id)
        )
        bos = bos_res.scalars().all()

        return {
            "flow_name": flow.name if flow else "",
            "flow_description": flow.description if flow else "",
            "feature_name": feature_name,
            "feature_description": feature_description,
            "user_requirements": project.user_requirements if project else "",
            "actors": [
                {"id": a.id, "name": a.name, "description": a.description}
                for a in actors
            ],
            "business_objects": [
                {"id": bo.id, "name": bo.name, "description": bo.description}
                for bo in bos
            ]
        }

    def parse_response(self, raw_json: dict) -> RepairResult:
        # P3 Flow solvers return manual action suggestions in fallback_reason
        fallback = raw_json.get("fallback", {})
        return RepairResult(
            candidates=[],
            result_type="manual_action",
            fallback_kind="manual_action",
            fallback_reason=fallback.get("reason", "建议手动为此流程补充步骤。"),
        )
