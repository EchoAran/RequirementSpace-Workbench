import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.core.llm_context import LLMRequestContext, current_llm_context
from backend.core import config as core_config
from backend.core.generators.blank_project_generator import (
    BlankProjectGenerator,
    BlankProjectGeneratorInput,
)
from backend.core.llm_locale_validation import LLMContentLocaleMismatchError
from backend.services.llm_handler_service import LLMHandler


def _handler() -> LLMHandler:
    return LLMHandler(
        api_url="https://llm.example.com",
        api_key="sk-test",
        model_name="test-model",
        temperature="0.7",
    )


def _context(locale: str) -> LLMRequestContext:
    return LLMRequestContext(
        api_url="https://llm.example.com",
        api_key="sk-test",
        model_name="test-model",
        content_locale=locale,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("entrypoint", ["call_llm", "call_chat"])
async def test_wrong_first_response_triggers_one_correction_for_both_entrypoints(entrypoint):
    handler = _handler()
    wrong = json.dumps(
        {"item_id": "item_1", "status": "open", "description": "这是错误语言的完整中文说明。"},
        ensure_ascii=False,
    )
    corrected = json.dumps(
        {
            "item_id": "item_1",
            "status": "open",
            "description": "This is the corrected English description for the item.",
        }
    )
    handler._call_api = AsyncMock(side_effect=[wrong, corrected])
    token = current_llm_context.set(_context("en-US"))
    try:
        if entrypoint == "call_llm":
            result = await handler.call_llm(
                "Return JSON.",
                "Generate the item.",
                response_format={"type": "json_object"},
            )
        else:
            result = await handler.call_chat(
                [{"role": "user", "content": "Generate the item."}],
                response_format={"type": "json_object"},
            )
    finally:
        current_llm_context.reset(token)

    assert result == corrected
    assert handler._call_api.await_count == 2
    correction_request = handler._call_api.await_args_list[1].kwargs["request_data"]
    assert correction_request["response_format"] == {"type": "json_object"}
    assert correction_request["messages"][-2] == {"role": "assistant", "content": wrong}
    assert "en-US" in correction_request["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_two_wrong_responses_raise_stable_error_after_one_correction():
    handler = _handler()
    wrong = json.dumps(
        {"description": "This response remains entirely in English after correction."}
    )
    handler._call_api = AsyncMock(side_effect=[wrong, wrong])
    token = current_llm_context.set(_context("zh-CN"))
    try:
        with pytest.raises(LLMContentLocaleMismatchError) as error:
            await handler.call_llm(
                "返回 JSON。",
                response_format={"type": "json_object"},
            )
    finally:
        current_llm_context.reset(token)

    assert str(error.value) == "llm_content_locale_mismatch"
    assert handler._call_api.await_count == 2


@pytest.mark.asyncio
async def test_correction_that_changes_identifier_is_rejected():
    handler = _handler()
    wrong = json.dumps(
        {"item_id": "item_1", "description": "This is the original English description."}
    )
    changed_identifier = json.dumps(
        {"item_id": "item_2", "description": "这是纠正后的完整中文说明。"},
        ensure_ascii=False,
    )
    handler._call_api = AsyncMock(side_effect=[wrong, changed_identifier])

    with pytest.raises(LLMContentLocaleMismatchError):
        await handler.call_llm("返回 JSON。", response_format={"type": "json_object"})

    assert handler._call_api.await_count == 2


@pytest.mark.asyncio
async def test_call_chat_revalidates_repeated_wrong_locale_assistant_history():
    handler = _handler()
    wrong_description = "This prior assistant answer is still entirely in English."
    wrong = json.dumps({"description": wrong_description})
    corrected = json.dumps(
        {"description": "这是纠正后的完整中文回答，不再沿用历史中的错误语言。"},
        ensure_ascii=False,
    )
    handler._call_api = AsyncMock(side_effect=[wrong, corrected])

    result = await handler.call_chat(
        [
            {"role": "assistant", "content": wrong_description},
            {"role": "user", "content": "Continue."},
        ],
        response_format={"type": "json_object"},
    )

    assert result == corrected
    assert handler._call_api.await_count == 2


@pytest.mark.asyncio
async def test_plain_text_correction_that_changes_url_is_rejected():
    handler = _handler()
    wrong = "Use https://example.com/items and `POST /api/items` to create the item."
    changed_url = "请改用 https://example.com/v2/items 和 `POST /api/items` 创建项目。"
    handler._call_api = AsyncMock(side_effect=[wrong, changed_url])

    with pytest.raises(LLMContentLocaleMismatchError):
        await handler.call_chat([{"role": "user", "content": "Please proceed."}])

    assert handler._call_api.await_count == 2


@pytest.mark.asyncio
async def test_prompt_embedded_protected_input_is_preserved_when_query_is_empty():
    handler = _handler()
    user_requirements = "Please keep the project name English Product Name unchanged."
    wrong = json.dumps(
        {
            "project_name": "English Product Name",
            "project_description": "This project still has an entirely English description.",
        }
    )
    changed_name = json.dumps(
        {
            "project_name": "中文产品名",
            "project_description": "这是纠正后的完整中文项目描述。",
        },
        ensure_ascii=False,
    )
    handler._call_api = AsyncMock(side_effect=[wrong, changed_name])

    with pytest.raises(LLMContentLocaleMismatchError):
        await handler.call_llm(
            prompt=f"Generate a project from: {user_requirements}",
            query="",
            protected_inputs=(user_requirements,),
        )

    assert handler._call_api.await_count == 2


@pytest.mark.asyncio
async def test_blank_project_generator_forwards_prompt_embedded_user_requirements():
    generator = BlankProjectGenerator()
    generator._llm_handler.call_llm = AsyncMock(
        return_value=json.dumps(
            {"project_name": "English Product Name", "project_description": "Description"}
        )
    )
    user_requirements = "Please keep the project name English Product Name unchanged."

    await generator.generate(BlankProjectGeneratorInput(user_requirements))

    call = generator._llm_handler.call_llm.await_args
    assert call.kwargs.get("query", "") == ""
    assert call.kwargs["protected_inputs"] == (user_requirements,)


@pytest.mark.asyncio
async def test_locale_validation_logs_metadata_without_prompt_or_response_content():
    handler = _handler()
    secret_prompt = "prompt-secret-should-not-be-logged"
    secret_response = json.dumps(
        {"description": "This secret English response must not enter locale logs."}
    )
    corrected = json.dumps(
        {"description": "这是纠正后的中文内容，不应写入诊断日志。"},
        ensure_ascii=False,
    )
    handler._call_api = AsyncMock(side_effect=[secret_response, corrected])

    with patch("backend.services.llm_handler_service.log_event") as log_event:
        result = await handler.call_llm(
            secret_prompt,
            response_format={"type": "json_object"},
        )

    assert result == corrected
    rendered = str(log_event.call_args_list)
    assert secret_prompt not in rendered
    assert secret_response not in rendered
    assert corrected not in rendered
    events = [call.args[3] for call in log_event.call_args_list]
    assert events.count("llm_locale_validation_completed") == 2
    assert events.count("llm_locale_correction_requested") == 1
    assert events.count("llm_locale_correction_completed") == 1
    for call in log_event.call_args_list:
        if call.args[3] == "llm_locale_validation_completed":
            assert set(call.kwargs) == {
                "attempt",
                "expected_locale",
                "detector_outcome",
                "field_count",
                "cjk_count",
                "latin_count",
                "cjk_ratio",
                "duration_ms",
                "call_type",
                "content_locale_source",
                "validation_mode",
            }

    correction_completed = next(
        call
        for call in log_event.call_args_list
        if call.args[3] == "llm_locale_correction_completed"
    )
    assert correction_completed.kwargs["correction_succeeded"] is True
    assert correction_completed.kwargs["correction_request_count"] == 1
    assert correction_completed.kwargs["call_type"] == "call_llm"
    assert correction_completed.kwargs["content_locale_source"] == "default"
    assert secret_prompt not in str(correction_completed)
    assert secret_response not in str(correction_completed)


@pytest.mark.asyncio
async def test_observe_mode_records_mismatch_without_correction_or_rejection(monkeypatch):
    handler = _handler()
    wrong = json.dumps(
        {"description": "This response remains entirely in English for observation."}
    )
    handler._call_api = AsyncMock(return_value=wrong)
    monkeypatch.setattr(core_config, "LLM_LOCALE_VALIDATION_MODE", "observe")

    with patch("backend.services.llm_handler_service.log_event") as log_event:
        result = await handler.call_llm(
            "返回 JSON。",
            response_format={"type": "json_object"},
        )

    assert result == wrong
    assert handler._call_api.await_count == 1
    locale_events = [call.args[3] for call in log_event.call_args_list]
    assert locale_events.count("llm_locale_validation_completed") == 1
    assert "llm_locale_correction_requested" not in locale_events
    validation_call = next(
        call
        for call in log_event.call_args_list
        if call.args[3] == "llm_locale_validation_completed"
    )
    assert validation_call.kwargs["detector_outcome"] == "mismatch"
    assert validation_call.kwargs["validation_mode"] == "observe"
