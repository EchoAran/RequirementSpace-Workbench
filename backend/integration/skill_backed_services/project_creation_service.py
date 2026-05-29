from __future__ import annotations

from typing import Any

from backend.api.services.project_creation_service import ProjectCreationService
from backend.core.generators.actors_generator import ActorsGeneratorInput
from backend.integration.skill_backed_services.feature_tree_adapter import FeatureTreeAdapter
from backend.integration.skill_backed_services.llm_json_client import SkillBackedLLMJsonClient
from backend.integration.skill_backed_services.skill_imports import import_skill_module
from backend.schemas import ActorNode


class SkillBackedProjectCreationService(ProjectCreationService):
    def __init__(self):
        super().__init__()
        core = import_skill_module("feature-tree-skill", "feature_tree_skill.core")
        self._feature_tree_skill = core.NL2FeaturesGeneration()
        self._feature_tree_adapter = FeatureTreeAdapter()
        self._llm_json_client = SkillBackedLLMJsonClient()

    async def _generate_actor_and_feature_previews(
        self,
        user_requirements: str,
        user_feedback: str | None,
    ) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
        actors_raw = await self._actors_generator.generate(
            ActorsGeneratorInput(
                user_requirements=user_requirements,
                user_feedback=user_feedback,
            )
        )

        actor_previews_for_draft = []
        actor_nodes = []

        for index, raw_actor in enumerate(
            actors_raw["actors"],
            start=1,
        ):
            actor_number = f"A{index:03d}"
            actor_previews_for_draft.append(
                {
                    "actor_number": actor_number,
                    "actor_name": raw_actor["actor_name"],
                    "actor_description": raw_actor["actor_description"],
                }
            )
            actor_nodes.append(
                ActorNode(
                    actorId=index,
                    actorName=raw_actor["actor_name"],
                    actorDescription=raw_actor["actor_description"],
                )
            )

        requirement_text = user_requirements
        if user_feedback:
            requirement_text = (
                f"{user_requirements}\n\nUser feedback for regeneration:\n{user_feedback}"
            )

        actor_names = [actor.actorName for actor in actor_nodes]
        prompt = self._feature_tree_skill._build_prompt(requirement_text, actor_names)
        raw_feature_tree: dict[str, Any] = await self._llm_json_client.ask_json(prompt)
        raw_features = self._feature_tree_adapter.to_current_features(
            raw_feature_tree=raw_feature_tree,
            actors=actor_nodes,
        )

        self._validate_feature_tree_by_number(raw_features)

        id_to_actor_number = {
            index: actor["actor_number"]
            for index, actor in enumerate(
                actor_previews_for_draft,
                start=1,
            )
        }

        feature_previews_for_draft = []
        for raw_feature in raw_features:
            feature_previews_for_draft.append(
                {
                    "feature_number": raw_feature["feature_number"],
                    "feature_name": raw_feature["feature_name"],
                    "feature_description": raw_feature["feature_description"],
                    "actor_numbers": [
                        id_to_actor_number[actor_id]
                        for actor_id in raw_feature.get("actor_ids", [])
                        if actor_id in id_to_actor_number
                    ],
                }
            )

        actor_number_to_name = {
            actor["actor_number"]: actor["actor_name"]
            for actor in actor_previews_for_draft
        }

        actor_previews_for_response = [
            {
                "actor_name": actor["actor_name"],
                "actor_description": actor["actor_description"],
            }
            for actor in actor_previews_for_draft
        ]

        feature_previews_for_response = [
            {
                "feature_number": feature["feature_number"],
                "feature_name": feature["feature_name"],
                "feature_description": feature["feature_description"],
                "actor_names": [
                    actor_number_to_name[actor_number]
                    for actor_number in feature.get("actor_numbers", [])
                ],
            }
            for feature in feature_previews_for_draft
        ]

        return (
            actor_previews_for_draft,
            actor_previews_for_response,
            feature_previews_for_draft,
            feature_previews_for_response,
        )
