"""SingleActorGenerator — generates exactly one actor from interview summary."""

import json
from typing import Dict

from backend.core.generators.single_object.base_single_object_generator import (
    BaseSingleObjectGenerator,
    SingleObjectGeneratorInput,
)
from backend.core.generators.single_object.prompts.single_actor_prompt import (
    SINGLE_ACTOR_GENERATE_PROMPT,
)


class SingleActorGenerator(BaseSingleObjectGenerator):
    """Generates a single actor from an interview conversation summary.

    Produces: {"actor": {"name": "...", "description": "..."}, "rationale": "..."}
    """

    async def generate(self, input_data: SingleObjectGeneratorInput) -> Dict:
        existing_actors = input_data.project_context.get("actors", [])
        existing_actors_str = _format_actor_list(existing_actors)

        prompt = SINGLE_ACTOR_GENERATE_PROMPT.replace(
            "{{user_requirements}}", input_data.user_requirements
        ).replace(
            "{{existing_actors}}", existing_actors_str
        )

        # The conversation summary serves as the user message (what the user wants)
        conversation_text = _format_conversation_summary(input_data.conversation_summary)

        response = await self._llm_handler.call_llm(
            prompt=prompt,
            query=conversation_text,
            print_log=False,
        )
        return json.loads(response)


def _format_actor_list(actors: list[dict]) -> str:
    """Format the existing actors list as readable text."""
    if not actors:
        return "（暂无参与者）"
    lines = []
    for a in actors:
        lines.append(f"- ID={a.get('id')}: {a.get('name', '')} — {a.get('description', '')}")
    return "\n".join(lines)


def _format_conversation_summary(summary: dict) -> str:
    """Format the interview summary as a user message for the generator."""
    known_facts = summary.get("known_facts", [])
    parts = ["以下是用户经过访谈确认的需求信息："]
    for fact in known_facts:
        parts.append(f"- {fact.get('key', '')}: {fact.get('value', '')}")
    return "\n".join(parts)
