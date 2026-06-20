"""AI Solver for SCENARIO_ACTOR_NOT_IN_FEATURE_ACTORS issue.

Recommends fixes for inconsistency between scenario actor and feature actors.
"""

import json
from sqlalchemy import select

from backend.core.issue_resolution.ai.base_ai_solver import BaseIssueAISolver, RepairResult, RepairProposal
from backend.core.issue_resolution.ai.prompts.scenario_actor_consistency_repair_prompt import (
    SCENARIO_ACTOR_CONSISTENCY_SYSTEM_PROMPT,
    SCENARIO_ACTOR_CONSISTENCY_USER_PROMPT_TEMPLATE,
)
from backend.database.model import ActorModel, FeatureModel, ScenarioModel, feature_actor_table


class ScenarioActorConsistencySolver(BaseIssueAISolver):
    """AI solver for SCENARIO_ACTOR_NOT_IN_FEATURE_ACTORS."""

    @property
    def supported_issue_codes(self) -> list[str]:
        return ["SCENARIO_ACTOR_NOT_IN_FEATURE_ACTORS"]

    def repair_type(self) -> str:
        return "bind_actor_to_feature"  # Default repair type (can be overridden by candidate)

    def get_system_prompt(self) -> str:
        return SCENARIO_ACTOR_CONSISTENCY_SYSTEM_PROMPT

    def get_user_prompt(self, context: dict) -> str:
        feature_actors_json = json.dumps(context.get("feature_actors", []), ensure_ascii=False, indent=2)
        all_project_actors_json = json.dumps(context.get("all_project_actors", []), ensure_ascii=False, indent=2)
        return SCENARIO_ACTOR_CONSISTENCY_USER_PROMPT_TEMPLATE.format(
            scenario_name=context.get("scenario_name", ""),
            feature_name=context.get("feature_name", ""),
            scenario_actor_name=context.get("scenario_actor_name", ""),
            scenario_actor_description=context.get("scenario_actor_description", ""),
            feature_actors_json=feature_actors_json,
            all_project_actors_json=all_project_actors_json,
            feature_id=context.get("feature_id", 0),
            scenario_actor_id=context.get("scenario_actor_id", 0),
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

        # Load parent feature
        feature = None
        feature_actors = []
        if scenario:
            res_feat = await session.execute(
                select(FeatureModel).where(FeatureModel.id == scenario.feature_id, FeatureModel.project_id == project_id)
            )
            feature = res_feat.scalar_one_or_none()

            if feature:
                # Load feature actors
                actors_res = await session.execute(
                    select(ActorModel)
                    .join(feature_actor_table, ActorModel.id == feature_actor_table.c.actor_id)
                    .where(feature_actor_table.c.feature_id == feature.id)
                )
                feature_actors = actors_res.scalars().all()

        # Load scenario actor
        scenario_actor = None
        if scenario and scenario.actor_id:
            res_act = await session.execute(
                select(ActorModel).where(ActorModel.id == scenario.actor_id, ActorModel.project_id == project_id)
            )
            scenario_actor = res_act.scalar_one_or_none()

        # Load all project actors
        all_actors_res = await session.execute(
            select(ActorModel).where(ActorModel.project_id == project_id)
        )
        all_actors = all_actors_res.scalars().all()

        return {
            "scenario_name": scenario.name if scenario else "",
            "scenario_id": target_id or 0,
            "feature_name": feature.name if feature else "",
            "feature_id": feature.id if feature else 0,
            "scenario_actor_name": scenario_actor.name if scenario_actor else "",
            "scenario_actor_description": scenario_actor.description if scenario_actor else "",
            "scenario_actor_id": scenario_actor.id if scenario_actor else 0,
            "feature_actors": [
                {"id": a.id, "name": a.name, "description": a.description}
                for a in feature_actors
            ],
            "all_project_actors": [
                {"id": a.id, "name": a.name, "description": a.description}
                for a in all_actors
            ]
        }

    def parse_response(self, raw_json: dict) -> RepairResult:
        # Consistency repair results always require user decision by definition
        result = super().parse_response(raw_json)
        for c in result.candidates:
            c.requires_user_decision = True
        return result
