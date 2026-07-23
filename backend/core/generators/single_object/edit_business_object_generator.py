"""EditBusinessObjectGenerator — produces edit diff for an existing BO."""

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

from backend.core.generators.single_object.prompts.edit_business_object_prompt import (
    EDIT_BUSINESS_OBJECT_GENERATE_PROMPT,
)
from backend.core.rules import EDITABLE_FIELDS


class EditBusinessObjectGenerator(BaseEditGenerator):
    """Generates an edit diff for an existing business object.

    Output: {"diff": {"name": {"old": "...", "new": "..."}},
             "unchanged": [...], "rationale": "..."}
    """

    target_object_type = "business_object"
    editable_fields = EDITABLE_FIELDS.get("business_object", [])

    async def generate(self, input_data: EditGeneratorInput) -> Dict[str, Any]:
        existing_bos = input_data.project_context.get("business_objects", [])
        existing_flows = input_data.project_context.get("flows", [])

        prompt = EDIT_BUSINESS_OBJECT_GENERATE_PROMPT.replace(
            "{{user_requirements}}", input_data.user_requirements
        ).replace(
            "{{existing_business_objects}}", serialize_prompt_data(existing_bos)
        ).replace(
            "{{existing_flows}}", serialize_prompt_data(existing_flows)
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
