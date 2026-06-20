"""AI Solver for DUPLICATE_SCENARIO_NAME issue.

Recommends unique names for scenarios with duplicate names under the same feature.
"""

import json
from sqlalchemy import select

from backend.core.issue_resolution.ai.base_ai_solver import BaseIssueAISolver, RepairResult, RepairProposal
from backend.core.issue_resolution.ai.prompts.duplicate_scenario_name_repair_prompt import (
    DUPLICATE_SCENARIO_NAME_SYSTEM_PROMPT,
    DUPLICATE_SCENARIO_NAME_USER_PROMPT_TEMPLATE,
)
from backend.database.model import FeatureModel, ScenarioModel


class DuplicateScenarioNameSolver(BaseIssueAISolver):
    """AI solver for DUPLICATE_SCENARIO_NAME."""

    @property
    def supported_issue_codes(self) -> list[str]:
        return ["DUPLICATE_SCENARIO_NAME"]

    def repair_type(self) -> str:
        return "rename_scenario"

    def get_system_prompt(self) -> str:
        return DUPLICATE_SCENARIO_NAME_SYSTEM_PROMPT

    def get_user_prompt(self, context: dict) -> str:
        other_names_json = json.dumps(context.get("other_names", []), ensure_ascii=False)
        return DUPLICATE_SCENARIO_NAME_USER_PROMPT_TEMPLATE.format(
            feature_name=context.get("feature_name", ""),
            feature_description=context.get("feature_description", ""),
            scenario_name=context.get("scenario_name", ""),
            scenario_content=context.get("scenario_content", ""),
            other_scenario_names_json=other_names_json,
            scenario_id=context.get("scenario_id", 0),
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

        # Load scenario
        scenario = None
        if target_id:
            res = await session.execute(
                select(ScenarioModel).where(ScenarioModel.id == target_id, ScenarioModel.project_id == project_id)
            )
            scenario = res.scalar_one_or_none()

        # Load feature
        feature = None
        other_names = []
        if scenario:
            res_feat = await session.execute(
                select(FeatureModel).where(FeatureModel.id == scenario.feature_id, FeatureModel.project_id == project_id)
            )
            feature = res_feat.scalar_one_or_none()

            # Load other scenario names under the feature
            other_res = await session.execute(
                select(ScenarioModel.name)
                .where(
                    ScenarioModel.feature_id == scenario.feature_id,
                    ScenarioModel.id != target_id,
                    ScenarioModel.project_id == project_id
                )
            )
            other_names = [r[0] for r in other_res.all()]

        return {
            "scenario_name": scenario.name if scenario else "",
            "scenario_content": scenario.content if scenario else "",
            "scenario_id": target_id or 0,
            "feature_name": feature.name if feature else "",
            "feature_description": feature.description if feature else "",
            "other_names": other_names,
        }
