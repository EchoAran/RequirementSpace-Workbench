import pytest
from unittest.mock import AsyncMock

from backend.api.modules.project_configuration.application.generation_strategy_config_service import (
    DEFAULT_STRATEGIES,
    localize_generation_strategy,
    normalize_generation_strategy,
)
from backend.api.modules.project_configuration.public import resolve_generation_strategies
from backend.api.modules.decision_workflow.ports.ports import CandidateContext, build_strategy_feedback
from backend.core.llm_context import LLMRequestContext, current_llm_context
from backend.api.modules.requirements_core.scenario.application.choice_adapter import (
    ScenarioGenerationChoiceAdapter,
)


@pytest.mark.asyncio
async def test_builtin_strategies_follow_content_locale(monkeypatch):
    monkeypatch.setenv("PROJECT_GENERATION_STRATEGIES_ENABLED", "false")
    token = current_llm_context.set(LLMRequestContext(
        api_url="https://example.test",
        api_key="test-key",
        model_name="test-model",
        content_locale="en-US",
        content_locale_source="project",
    ))
    try:
        strategies = await resolve_generation_strategies(
            project_id=1,
            generation_type="scenario",
            session=None,
        )
    finally:
        current_llm_context.reset(token)

    assert [strategy.label for strategy in strategies] == ["Balanced", "Comprehensive"]
    assert "core business actors" in strategies[0].instruction


def test_custom_strategy_text_is_not_translated():
    custom = {
        "id": "custom_1",
        "is_builtin": False,
        "label": "用户原始名称",
        "description": "用户原始描述",
        "instruction": "用户自己输入的策略指令必须保持原样。",
    }
    assert localize_generation_strategy(custom, "en-US") == custom


def test_legacy_default_strategy_is_recognized_as_builtin():
    legacy = {key: value for key, value in DEFAULT_STRATEGIES[0].items() if key != "is_builtin"}
    normalized = normalize_generation_strategy(legacy)
    assert normalized["is_builtin"] is True
    assert localize_generation_strategy(normalized, "en-US")["label"] == "Balanced"


def test_custom_strategy_cannot_claim_builtin_translation():
    normalized = normalize_generation_strategy({
        "id": "custom_1",
        "is_builtin": True,
        "label": "My custom strategy",
        "description": "Custom description",
        "instruction": "Keep this user-authored instruction exactly as entered.",
    })
    assert normalized["is_builtin"] is False
    assert localize_generation_strategy(normalized, "zh-CN")["label"] == "My custom strategy"


def test_strategy_feedback_wrapper_follows_content_locale():
    token = current_llm_context.set(LLMRequestContext(
        api_url="https://example.test",
        api_key="test-key",
        model_name="test-model",
        content_locale="en-US",
        content_locale_source="project",
    ))
    try:
        feedback = build_strategy_feedback(
            CandidateContext(
                index=0,
                strategy="balanced",
                strategy_label="Balanced",
                strategy_description="Balanced description",
                strategy_instruction="Balanced instruction",
            ),
            "生成场景集",
        )
    finally:
        current_llm_context.reset(token)

    assert "Generation strategy for this candidate" in feedback
    assert "generate a scenario set" in feedback
    assert not any("\u4e00" <= char <= "\u9fff" for char in feedback)


@pytest.mark.asyncio
async def test_scenario_candidate_metadata_follows_content_locale():
    adapter = ScenarioGenerationChoiceAdapter()
    adapter._service._generate_preview = AsyncMock(return_value=(
        {},
        {"scenarios": [{
            "feature_name": "Search Music",
            "actor_name": "Listener",
            "scenario_name": "Search by title",
            "scenario_content": "As a Listener, I want to search by title.",
            "acceptance_criteria": ["Matching tracks are shown."],
        }]},
    ))
    token = current_llm_context.set(LLMRequestContext(
        api_url="https://example.test",
        api_key="test-key",
        model_name="test-model",
        content_locale="en-US",
        content_locale_source="project",
    ))
    try:
        candidate = await adapter.generate_candidate(CandidateContext(
            index=0,
            strategy="balanced",
            strategy_id="balanced",
            strategy_label="Balanced",
            project_id=1,
            target={"generation_mode": "pair", "feature_id": 1, "actor_id": 1},
        ))
    finally:
        current_llm_context.reset(token)

    assert candidate.title == "Search Music × Listener — 1 scenarios"
    assert candidate.rationale == "Scenario set generated for Search Music × Listener using the Balanced strategy"
    assert candidate.apply_behavior_description.startswith("This option clears")
