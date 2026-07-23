"""SingleActorGenerator — generates exactly one actor from interview summary."""

import json
from typing import Dict

from backend.core.generators.single_object.base_single_object_generator import (
    BaseSingleObjectGenerator,
    SingleObjectGeneratorInput,
    inject_generator_knowledge_context,
    serialize_prompt_data,
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
        existing_actors_str = serialize_prompt_data(existing_actors)

        prompt = SINGLE_ACTOR_GENERATE_PROMPT.replace(
            "{{user_requirements}}", input_data.user_requirements
        ).replace(
            "{{existing_actors}}", existing_actors_str
        )
        prompt = inject_generator_knowledge_context(prompt, input_data.knowledge_context)

        # The conversation summary serves as the user message (what the user wants)
        conversation_text = serialize_prompt_data(input_data.conversation_summary)

        response = await self._llm_handler.call_llm(
            prompt=prompt,
            query=conversation_text,
            print_log=False,
            protected_inputs=self._protected_inputs(input_data),
        )
        return json.loads(response)
