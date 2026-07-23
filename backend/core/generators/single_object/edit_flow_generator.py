"""EditFlowGenerator — produces edit diff for an existing flow."""

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

from backend.core.generators.single_object.prompts.edit_flow_prompt import (
    EDIT_FLOW_GENERATE_PROMPT,
)
from backend.core.rules import EDITABLE_FIELDS


class EditFlowGenerator(BaseEditGenerator):
    """Generates an edit diff for an existing flow.

    Output: {"diff": {"name": {"old": "...", "new": "..."},
                       "feature_ids": {"old": [...], "new": [...]}},
             "unchanged": [...], "rationale": "..."}
    """

    target_object_type = "flow"
    editable_fields = EDITABLE_FIELDS.get("flow", [])

    async def generate(self, input_data: EditGeneratorInput) -> Dict[str, Any]:
        existing_features = input_data.project_context.get("features", [])
        existing_flows = input_data.project_context.get("flows", [])

        prompt = EDIT_FLOW_GENERATE_PROMPT.replace(
            "{{user_requirements}}", input_data.user_requirements
        ).replace(
            "{{existing_features}}", serialize_prompt_data(
                [f for f in existing_features if f.get("feature_kind") in ("leaf", None)]
            )
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
