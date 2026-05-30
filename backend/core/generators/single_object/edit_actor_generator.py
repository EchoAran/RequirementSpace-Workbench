"""EditActorGenerator — produces edit diff for an existing actor."""

import json
from typing import Dict, Any

from backend.core.generators.single_object.base_edit_generator import (
    BaseEditGenerator,
    EditGeneratorInput,
)
from backend.core.generators.single_object.prompts.edit_actor_prompt import (
    EDIT_ACTOR_GENERATE_PROMPT,
)
from backend.api.services.ai_edit_field_permissions import EDITABLE_FIELDS


class EditActorGenerator(BaseEditGenerator):
    """Generates an edit diff for an existing actor.

    Output: {"diff": {"name": {"old": "...", "new": "..."}},
             "unchanged": [...], "rationale": "..."}
    """

    target_object_type = "actor"
    editable_fields = EDITABLE_FIELDS.get("actor", [])

    async def generate(self, input_data: EditGeneratorInput) -> Dict[str, Any]:
        existing_actors = input_data.project_context.get("actors", [])
        existing_str = _format_items(existing_actors)
        original_str = _format_original(input_data.original_object)

        prompt = EDIT_ACTOR_GENERATE_PROMPT.replace(
            "{{user_requirements}}", input_data.user_requirements
        ).replace(
            "{{existing_actors}}", existing_str
        ).replace(
            "{{original_object}}", original_str
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
