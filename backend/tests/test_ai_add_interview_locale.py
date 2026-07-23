import re

import pytest

from backend.api.modules.ai_interaction.ai_add.application.interview_strategy import (
    create_default_registry,
)
from backend.core.llm_context import LLMRequestContext, current_llm_context


TARGET_TYPES = [
    "actor",
    "feature_leaf",
    "feature_branch",
    "flow",
    "business_object",
    "edit_actor",
    "edit_feature",
    "edit_flow",
    "edit_business_object",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", TARGET_TYPES)
async def test_ai_add_interview_uses_english_prompt_resources(target_type):
    captured = {}

    async def call_chat(**kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"]
        return '{"assistant_message":"Please clarify.","is_ready_to_generate":false,"known_facts":[],"missing_facts":[]}'

    context = LLMRequestContext(
        api_url="https://llm.example.test",
        api_key="secret",
        model_name="test-model",
        content_locale="en-US",
    )
    token = current_llm_context.set(context)
    try:
        strategy = create_default_registry().get(target_type)
        await strategy.interview(
            project_context={
                "actors": [{"id": 1, "name": "Administrator"}],
                "features": [{"id": 2, "name": "Reporting", "parent_id": None}],
                "flows": [{"id": 3, "name": "Report delivery"}],
                "business_objects": [{"id": 4, "name": "Report"}],
            },
            anchor={"target_id": 1, "parent_feature_id": 2},
            current_summary=None,
            latest_user_message="Continue",
            llm_call_chat=call_chat,
            knowledge_context="Reports must be retained for 30 days.",
        )
    finally:
        current_llm_context.reset(token)

    assert not re.search(r"[\u4e00-\u9fff]", captured["prompt"])
    assert "{{" not in captured["prompt"]
