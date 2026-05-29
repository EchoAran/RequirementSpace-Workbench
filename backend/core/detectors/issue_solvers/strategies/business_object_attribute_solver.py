"""AI Solver for BUSINESS_OBJECT_WITHOUT_ATTRIBUTES.

Generates 1-3 attributes for a business object that has none.
Output is always a single candidate (never ChoiceGroup).
"""

from sqlalchemy import select

from backend.core.detectors.issue_solvers.ai_issue_solver import (
    BaseIssueAISolver,
    RepairResult,
)
from backend.core.detectors.issue_solvers.prompts.business_object_attribute_repair_prompt import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)
from backend.database.model import BusinessObjectModel, ProjectModel


class BusinessObjectAttributeSolver(BaseIssueAISolver):
    """AI solver for BUSINESS_OBJECT_WITHOUT_ATTRIBUTES."""

    @property
    def supported_issue_codes(self) -> list[str]:
        return ["BUSINESS_OBJECT_WITHOUT_ATTRIBUTES"]

    def repair_type(self) -> str:
        return "add_attributes"

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_user_prompt(self, context: dict) -> str:
        return USER_PROMPT_TEMPLATE.format(
            user_requirements=context.get("user_requirements", ""),
            bo_name=context.get("bo_name", ""),
            bo_description=context.get("bo_description", ""),
            bo_id=context.get("bo_id", 0),
        )

    async def build_prompt_context(
        self,
        project_id: int,
        issue_code: str,
        target: dict | None,
        session,
    ) -> dict:
        target_id = int(target.get("target_id") or target.get("targetId") or 0) if target else 0

        bo = None
        if target_id:
            res = await session.execute(
                select(BusinessObjectModel).where(
                    BusinessObjectModel.id == target_id,
                    BusinessObjectModel.project_id == project_id,
                )
            )
            bo = res.scalar_one_or_none()

        project_res = await session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        project = project_res.scalar_one_or_none()

        return {
            "user_requirements": project.user_requirements if project else "",
            "bo_name": bo.name if bo else "",
            "bo_description": bo.description if bo else "",
            "bo_id": target_id,
        }

    def parse_response(self, raw_json: dict) -> RepairResult:
        """Ensure exactly one candidate (attributes are bundled in addNodes)."""
        result = super().parse_response(raw_json)
        # Force single candidate even if LLM returns multiple
        if len(result.candidates) > 1:
            result.candidates = result.candidates[:1]
            result.result_type = "repair_draft"
        return result
