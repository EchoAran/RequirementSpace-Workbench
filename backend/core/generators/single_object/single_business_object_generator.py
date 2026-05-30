"""SingleBusinessObjectGenerator — generates exactly one BO from interview summary."""

import json
from typing import Dict

from backend.core.generators.single_object.base_single_object_generator import (
    BaseSingleObjectGenerator,
    SingleObjectGeneratorInput,
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

        bos_str = _format_bo_list(existing_bos)
        flows_str = _format_flow_list(existing_flows)

        prompt = SINGLE_BUSINESS_OBJECT_GENERATE_PROMPT.replace(
            "{{user_requirements}}", input_data.user_requirements
        ).replace(
            "{{existing_business_objects}}", bos_str
        ).replace(
            "{{existing_flows}}", flows_str
        )

        conversation_text = _format_conversation_summary(input_data.conversation_summary)

        response = await self._llm_handler.call_llm(
            prompt=prompt,
            query=conversation_text,
            print_log=False,
        )
        return json.loads(response)


def _format_bo_list(bos: list[dict]) -> str:
    if not bos:
        return "（暂无业务数据对象）"
    lines = []
    for b in bos:
        lines.append(f"- ID={b.get('id')}: {b.get('name', '')}")
    return "\n".join(lines)


def _format_flow_list(flows: list[dict]) -> str:
    if not flows:
        return "（暂无流程）"
    lines = []
    for f in flows:
        lines.append(f"- ID={f.get('id')}: {f.get('name', '')}")
    return "\n".join(lines)


def _format_conversation_summary(summary: dict) -> str:
    known_facts = summary.get("known_facts", [])
    parts = ["以下是用户经过访谈确认的需求信息："]
    for fact in known_facts:
        parts.append(f"- {fact.get('key', '')}: {fact.get('value', '')}")
    return "\n".join(parts)
