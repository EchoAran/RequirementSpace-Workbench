"""AI Solver for BUSINESS_OBJECT_WITHOUT_USAGE issue.

Analyzes business object attributes and project flows to recommend step bindings manually.
"""

import json
from sqlalchemy import select

from backend.core.issue_resolution.ai.base_ai_solver import BaseIssueAISolver, RepairResult, RepairProposal
from backend.core.issue_resolution.ai.prompts.business_object_without_usage_prompt import (
    BUSINESS_OBJECT_WITHOUT_USAGE_SYSTEM_PROMPT,
    BUSINESS_OBJECT_WITHOUT_USAGE_USER_PROMPT_TEMPLATE,
)
from backend.database.model import BusinessObjectAttributeModel, BusinessObjectModel, FlowModel, FlowStepModel, ProjectModel


class BusinessObjectWithoutUsageSolver(BaseIssueAISolver):
    """AI solver for BUSINESS_OBJECT_WITHOUT_USAGE."""

    @property
    def supported_issue_codes(self) -> list[str]:
        return ["BUSINESS_OBJECT_WITHOUT_USAGE"]

    def repair_type(self) -> str:
        return "design_usage"

    def get_system_prompt(self) -> str:
        return BUSINESS_OBJECT_WITHOUT_USAGE_SYSTEM_PROMPT

    def get_user_prompt(self, context: dict) -> str:
        bo_attributes_json = json.dumps(context.get("bo_attributes", []), ensure_ascii=False, indent=2)
        flows_and_steps_json = json.dumps(context.get("flows_and_steps", []), ensure_ascii=False, indent=2)
        return BUSINESS_OBJECT_WITHOUT_USAGE_USER_PROMPT_TEMPLATE.format(
            bo_name=context.get("bo_name", ""),
            bo_description=context.get("bo_description", ""),
            bo_attributes_json=bo_attributes_json,
            flows_and_steps_json=flows_and_steps_json,
            user_requirements=context.get("user_requirements", ""),
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

        # Load target business object
        bo = None
        bo_attrs = []
        if target_id:
            res = await session.execute(
                select(BusinessObjectModel).where(BusinessObjectModel.id == target_id, BusinessObjectModel.project_id == project_id)
            )
            bo = res.scalar_one_or_none()

            if bo:
                # Load attributes
                attrs_res = await session.execute(
                    select(BusinessObjectAttributeModel).where(BusinessObjectAttributeModel.business_object_id == bo.id)
                )
                bo_attrs = attrs_res.scalars().all()

        # Load project requirements
        project_res = await session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        project = project_res.scalar_one_or_none()

        # Load all flows and steps
        flows_res = await session.execute(
            select(FlowModel).where(FlowModel.project_id == project_id)
        )
        flows = flows_res.scalars().all()

        flows_summary = []
        for f in flows:
            steps_res = await session.execute(
                select(FlowStepModel).where(FlowStepModel.flow_id == f.id).order_by(FlowStepModel.position)
            )
            steps = steps_res.scalars().all()
            flows_summary.append({
                "flow_id": f.id,
                "flow_name": f.name,
                "flow_description": f.description,
                "steps": [
                    {"id": s.id, "name": s.name, "description": s.description}
                    for s in steps
                ]
            })

        return {
            "bo_name": bo.name if bo else "",
            "bo_description": bo.description if bo else "",
            "bo_attributes": [
                {"name": a.name, "data_type": a.data_type}
                for a in bo_attrs
            ],
            "flows_and_steps": flows_summary,
            "user_requirements": project.user_requirements if project else "",
        }

    def parse_response(self, raw_json: dict) -> RepairResult:
        # P3 Flow solvers return manual action suggestions in fallback_reason
        fallback = raw_json.get("fallback", {})
        return RepairResult(
            candidates=[],
            result_type="manual_action",
            fallback_kind="manual_action",
            fallback_reason=fallback.get("reason", "建议手动关联业务对象的使用关系。"),
        )
