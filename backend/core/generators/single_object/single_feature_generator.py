"""SingleFeatureGenerator — generates exactly one feature from interview summary."""

import json
from typing import Dict

from backend.core.generators.single_object.base_single_object_generator import (
    BaseSingleObjectGenerator,
    SingleObjectGeneratorInput,
    inject_generator_knowledge_context,
    serialize_prompt_data,
)
from backend.core.generators.single_object.prompts.single_feature_prompt import (
    SINGLE_FEATURE_GENERATE_PROMPT,
)


class SingleFeatureGenerator(BaseSingleObjectGenerator):
    """Generates a single feature (branch or leaf) from an interview conversation summary.

    Produces: {"feature": {"name": "...", "description": "...",
                           "parent_id": ..., "actor_ids": [...], "feature_kind": "leaf|branch"},
               "rationale": "..."}
    """

    async def generate(self, input_data: SingleObjectGeneratorInput) -> Dict:
        existing_features = input_data.project_context.get("features", [])
        existing_actors = input_data.project_context.get("actors", [])

        features_str = serialize_prompt_data(existing_features)
        actors_str = serialize_prompt_data(existing_actors)

        prompt = SINGLE_FEATURE_GENERATE_PROMPT.replace(
            "{{user_requirements}}", input_data.user_requirements
        ).replace(
            "{{existing_features}}", features_str
        ).replace(
            "{{existing_actors}}", actors_str
        )
        prompt = inject_generator_knowledge_context(prompt, input_data.knowledge_context)

        # The conversation summary serves as the user message
        conversation_text = serialize_prompt_data(input_data.conversation_summary)

        response = await self._llm_handler.call_llm(
            prompt=prompt,
            query=conversation_text,
            print_log=False,
            protected_inputs=self._protected_inputs(input_data),
        )
        return json.loads(response)
