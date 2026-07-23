"""SingleFlowGenerator — generates exactly one flow from interview summary."""

import json
from typing import Dict

from backend.core.generators.single_object.base_single_object_generator import (
    BaseSingleObjectGenerator,
    SingleObjectGeneratorInput,
    inject_generator_knowledge_context,
    serialize_prompt_data,
)
from backend.core.generators.single_object.prompts.single_flow_prompt import (
    SINGLE_FLOW_GENERATE_PROMPT,
)


class SingleFlowGenerator(BaseSingleObjectGenerator):
    """Generates a single flow (no steps) from an interview conversation summary.

    Produces: {"flow": {"name": "...", "description": "...", "feature_ids": [...]},
               "rationale": "..."}
    """

    async def generate(self, input_data: SingleObjectGeneratorInput) -> Dict:
        existing_features = input_data.project_context.get("features", [])
        existing_flows = input_data.project_context.get("flows", [])

        features_str = serialize_prompt_data(
            [f for f in existing_features if f.get("feature_kind") in ("leaf", None)]
        )
        flows_str = serialize_prompt_data(existing_flows)

        prompt = SINGLE_FLOW_GENERATE_PROMPT.replace(
            "{{user_requirements}}", input_data.user_requirements
        ).replace(
            "{{existing_features}}", features_str
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
