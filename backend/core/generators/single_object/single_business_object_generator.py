"""SingleBusinessObjectGenerator — generates exactly one BO from interview summary."""

import json
from typing import Dict

from backend.core.generators.single_object.base_single_object_generator import (
    BaseSingleObjectGenerator,
    SingleObjectGeneratorInput,
    inject_generator_knowledge_context,
    serialize_prompt_data,
)
from backend.core.generators.single_object.prompts.single_business_object_prompt import (
    SINGLE_BUSINESS_OBJECT_GENERATE_PROMPT,
)


class SingleBusinessObjectGenerator(BaseSingleObjectGenerator):
    """Generates a single business object with optional initial attributes.

    Produces: {"business_object": {"name": "...", "description": "...",
                                    "attributes": [...]},
               "rationale": "..."}
    """

    async def generate(self, input_data: SingleObjectGeneratorInput) -> Dict:
        existing_bos = input_data.project_context.get("business_objects", [])
        existing_flows = input_data.project_context.get("flows", [])

        bos_str = serialize_prompt_data(existing_bos)
        flows_str = serialize_prompt_data(existing_flows)

        prompt = SINGLE_BUSINESS_OBJECT_GENERATE_PROMPT.replace(
            "{{user_requirements}}", input_data.user_requirements
        ).replace(
            "{{existing_business_objects}}", bos_str
        ).replace(
            "{{existing_flows}}", flows_str
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
