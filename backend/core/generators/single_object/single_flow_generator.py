"""SingleFlowGenerator — generates exactly one flow from interview summary."""

import json
from typing import Dict

from backend.core.generators.single_object.base_single_object_generator import (
    BaseSingleObjectGenerator,
    SingleObjectGeneratorInput,
    inject_generator_knowledge_context,
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

        features_str = _format_leaf_features(existing_features)
        flows_str = _format_flow_list(existing_flows)

        prompt = SINGLE_FLOW_GENERATE_PROMPT.replace(
            "{{user_requirements}}", input_data.user_requirements
        ).replace(
            "{{existing_features}}", features_str
        ).replace(
            "{{existing_flows}}", flows_str
        )
        prompt = inject_generator_knowledge_context(prompt, input_data.knowledge_context)

        conversation_text = _format_conversation_summary(input_data.conversation_summary)

        response = await self._llm_handler.call_llm(
            prompt=prompt,
            query=conversation_text,
            print_log=False,
        )
        return json.loads(response)


def _format_leaf_features(features: list[dict]) -> str:
    """Format leaf features (feature_kind=leaf or unspecified) as readable text."""
    leaves = [f for f in features if f.get("feature_kind") in ("leaf", None)]
    if not leaves:
        return "（暂无叶子功能）"
    lines = []
    for f in leaves:
        lines.append(f"- ID={f.get('id')}: {f.get('name', '')}")
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
