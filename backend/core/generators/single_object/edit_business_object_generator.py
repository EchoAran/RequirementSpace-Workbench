"""EditBusinessObjectGenerator — produces edit diff for an existing BO."""

import json
from typing import Dict, Any

from backend.core.generators.single_object.base_edit_generator import (
    BaseEditGenerator,
    EditGeneratorInput,
)
from backend.core.generators.single_object.prompts.edit_business_object_prompt import (
    EDIT_BUSINESS_OBJECT_GENERATE_PROMPT,
)
from backend.api.services.ai_edit_field_permissions import EDITABLE_FIELDS


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
            "{{existing_business_objects}}", _format_items(existing_bos)
        ).replace(
            "{{existing_flows}}", _format_items(existing_flows)
        ).replace(
            "{{original_object}}", _format_original(input_data.original_object)
        )

        conversation_text = _format_summary(input_data.conversation_summary)

        response = await self._llm_handler.call_llm(
            prompt=prompt,
            query=conversation_text,
            print_log=False,
        )
        return json.loads(response)


def _format_items(items: list[dict]) -> str:
    if not items:
        return "（暂无）"
    return "\n".join(f"- ID={i.get('id')}: {i.get('name', '')}" for i in items)


def _format_original(obj: dict) -> str:
    return "\n".join(f"{k}: {v}" for k, v in obj.items() if v)


def _format_summary(summary: dict) -> str:
    known_facts = summary.get("known_facts", [])
    parts = ["以下是用户确认的编辑需求："]
    for fact in known_facts:
        parts.append(f"- {fact.get('key', '')}: {fact.get('value', '')}")
    return "\n".join(parts)
