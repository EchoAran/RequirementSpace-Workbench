"""EditFeatureGenerator — produces edit diff for an existing feature."""

import json
from typing import Dict, Any

from backend.core.generators.single_object.base_edit_generator import (
    BaseEditGenerator,
    EditGeneratorInput,
)
from backend.core.generators.single_object.base_single_object_generator import (
    inject_generator_knowledge_context,
    serialize_prompt_data,
)

from backend.core.generators.single_object.prompts.edit_feature_prompt import (
    EDIT_FEATURE_GENERATE_PROMPT,
)
from backend.core.rules import EDITABLE_FIELDS


class EditFeatureGenerator(BaseEditGenerator):
    """Generates an edit diff for an existing feature.

    Output: {"diff": {"name": {"old": "...", "new": "..."},
                       "actor_ids": {"old": [...], "new": [...]}},
             "unchanged": [...], "rationale": "..."}
    """

    target_object_type = "feature"
    editable_fields = EDITABLE_FIELDS.get("feature", [])

    async def generate(self, input_data: EditGeneratorInput) -> Dict[str, Any]:
        existing_features = input_data.project_context.get("features", [])
        existing_actors = input_data.project_context.get("actors", [])

        prompt = EDIT_FEATURE_GENERATE_PROMPT.replace(
            "{{user_requirements}}", input_data.user_requirements
        ).replace(
            "{{existing_features}}", serialize_prompt_data(existing_features)
        ).replace(
            "{{existing_actors}}", serialize_prompt_data(existing_actors)
        ).replace(
            "{{original_object}}", serialize_prompt_data(input_data.original_object)
        )
        prompt = inject_generator_knowledge_context(prompt, input_data.knowledge_context)

        conversation_text = serialize_prompt_data(input_data.conversation_summary)

        response = await self._llm_handler.call_llm(
            prompt=prompt,
            query=conversation_text,
            print_log=False,
            protected_inputs=self._protected_inputs(input_data),
        )
        return json.loads(response)
