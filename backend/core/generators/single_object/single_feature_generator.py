"""SingleFeatureGenerator — generates exactly one feature from interview summary."""

import json
from typing import Dict

from backend.core.generators.single_object.base_single_object_generator import (
    BaseSingleObjectGenerator,
    SingleObjectGeneratorInput,
)
from backend.core.generators.single_object.prompts.single_feature_prompt import (
    SINGLE_FEATURE_GENERATE_PROMPT,
)


class SingleFeatureGenerator(BaseSingleObjectGenerator):
    """Generates a single feature (branch or leaf) from an interview conversation summary.

    Produces: {"feature": {"name": "...", "description": "...",
                           "parent_id": ..., "actor_ids": [...], "feature_kind": "leaf|branch"},
               "rationale": "..."}
    """

    async def generate(self, input_data: SingleObjectGeneratorInput) -> Dict:
        existing_features = input_data.project_context.get("features", [])
        existing_actors = input_data.project_context.get("actors", [])

        features_str = _format_feature_tree(existing_features)
        actors_str = _format_actor_list(existing_actors)

        prompt = SINGLE_FEATURE_GENERATE_PROMPT.replace(
            "{{user_requirements}}", input_data.user_requirements
        ).replace(
            "{{existing_features}}", features_str
        ).replace(
            "{{existing_actors}}", actors_str
        )

        # The conversation summary serves as the user message
        conversation_text = _format_conversation_summary(input_data.conversation_summary)

        response = await self._llm_handler.call_llm(
            prompt=prompt,
            query=conversation_text,
            print_log=False,
        )
        return json.loads(response)


def _format_feature_tree(features: list[dict]) -> str:
    """Format the existing feature tree as readable text."""
    if not features:
        return "（暂无功能）"
    lines = []
    for f in features:
        parent_info = f"parent_id={f.get('parent_id')}" if f.get('parent_id') else "root"
        lines.append(
            f"- ID={f.get('id')}: {f.get('name', '')} "
            f"({f.get('feature_kind', '')}) — {parent_info}"
        )
    return "\n".join(lines)


def _format_actor_list(actors: list[dict]) -> str:
    if not actors:
        return "（暂无参与者）"
    lines = []
    for a in actors:
        lines.append(f"- ID={a.get('id')}: {a.get('name', '')}")
    return "\n".join(lines)


def _format_conversation_summary(summary: dict) -> str:
    known_facts = summary.get("known_facts", [])
    extra = {k: v for k, v in summary.items() if k != "known_facts"}

    parts = ["以下是用户经过访谈确认的需求信息："]
    for fact in known_facts:
        parts.append(f"- {fact.get('key', '')}: {fact.get('value', '')}")
    if extra:
        parts.append(f"\n附加信息: {json.dumps(extra, ensure_ascii=False)}")
    return "\n".join(parts)
