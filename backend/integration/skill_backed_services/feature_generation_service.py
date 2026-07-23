from __future__ import annotations

from typing import Any

from backend.api.modules.requirements_core.public import FeatureGenerationService
from backend.core.llm_protected_inputs import collect_protected_texts
from backend.integration.skill_backed_services.feature_tree_adapter import FeatureTreeAdapter
from backend.integration.skill_backed_services.llm_json_client import SkillBackedLLMJsonClient
from backend.integration.skill_backed_services.skill_imports import import_skill_module


class SkillBackedFeatureGenerationService(FeatureGenerationService):
    def __init__(self):
        super().__init__()
        core = import_skill_module("feature-tree-skill", "feature_tree_skill.core")
        self._skill_generator = core.NL2FeaturesGeneration()
        self._adapter = FeatureTreeAdapter()
        self._llm_json_client = SkillBackedLLMJsonClient()

    async def _generate_preview(
        self,
        project_id: int,
        user_feedback: str | None,
        session,
    ) -> tuple[dict, dict]:
        user_requirements, actor_nodes = await self._load_project_context(
            project_id=project_id,
            session=session,
        )

        requirement_text = user_requirements
        if user_feedback:
            requirement_text = (
                f"{user_requirements}\n\nUser feedback for regeneration:\n{user_feedback}"
            )

        actor_names = [actor.actorName for actor in actor_nodes]
        prompt = self._skill_generator._build_prompt(requirement_text, actor_names)
        raw_feature_tree: dict[str, Any] = await self._llm_json_client.ask_json(
            prompt,
            protected_inputs=collect_protected_texts(
                user_requirements,
                user_feedback,
                actor_names,
            ),
        )

        features = self._adapter.to_current_features(
            raw_feature_tree=raw_feature_tree,
            actors=actor_nodes,
        )
        self._validate_feature_tree_by_number(features)

        actor_name_map = {
            actor.actorId: actor.actorName
            for actor in actor_nodes
        }

        draft_payload = {
            "project_id": project_id,
            "features": features,
            "raw_feature_tree": raw_feature_tree,
        }

        response_payload = {
            "project_id": project_id,
            "features": [
                {
                    "feature_name": feature["feature_name"],
                    "feature_description": feature["feature_description"],
                    "actor_names": [
                        actor_name_map[actor_id]
                        for actor_id in feature.get("actor_ids", [])
                        if actor_id in actor_name_map
                    ],
                }
                for feature in features
            ],
        }

        return draft_payload, response_payload
