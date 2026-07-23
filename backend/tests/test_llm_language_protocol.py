import pytest

from backend.core.llm_context import LLMRequestContext, current_llm_context
from backend.services.llm_handler_service import CONTENT_LANGUAGE_PROTOCOL_MARKER, LLMHandler


def _handler() -> LLMHandler:
    return LLMHandler(
        api_url="https://llm.example.com",
        api_key="sk-test",
        model_name="test-model",
        temperature="0.7",
    )


async def _capture_outbound(handler: LLMHandler, call):
    captured = []

    async def capture(**kwargs):
        captured.append(kwargs["request_data"])
        return "ok"

    handler._call_api = capture
    await call()
    return captured[0]["messages"]


def _protocol_count(messages: list[dict]) -> int:
    return sum((message.get("content") or "").count(CONTENT_LANGUAGE_PROTOCOL_MARKER) for message in messages)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("existing_locale", "requested_locale", "expected_text"),
    [
        ("zh-CN", "en-US", "English (en-US)"),
        ("en-US", "zh-CN", "中文 (zh-CN)"),
    ],
)
async def test_call_chat_replaces_existing_protocol_for_the_requested_locale(
    existing_locale: str,
    requested_locale: str,
    expected_text: str,
):
    handler = _handler()
    old_system_message = f"Keep the conversation concise.\n\n{handler._language_protocol(existing_locale)}"
    token = current_llm_context.set(
        LLMRequestContext("https://llm.example.com", "sk-test", "test-model", requested_locale)
    )
    try:
        outbound = await _capture_outbound(
            handler,
            lambda: handler.call_chat([
                {"role": "system", "content": old_system_message},
                {"role": "user", "content": "Continue."},
            ]),
        )
    finally:
        current_llm_context.reset(token)

    assert _protocol_count(outbound) == 1
    assert expected_text in outbound[0]["content"]
    assert handler._language_protocol(existing_locale) not in outbound[0]["content"]


@pytest.mark.anyio
async def test_call_llm_replaces_existing_protocol_in_its_outbound_messages():
    handler = _handler()
    old_prompt = f"Generate a summary.\n\n{handler._language_protocol('zh-CN')}"
    token = current_llm_context.set(
        LLMRequestContext("https://llm.example.com", "sk-test", "test-model", "en-US")
    )
    try:
        outbound = await _capture_outbound(handler, lambda: handler.call_llm(old_prompt, "Input text"))
    finally:
        current_llm_context.reset(token)

    assert _protocol_count(outbound) == 1
    assert "English (en-US)" in outbound[0]["content"]
    assert "中文 (zh-CN)" not in outbound[0]["content"]


@pytest.mark.anyio
async def test_repeated_chat_calls_keep_one_protocol():
    handler = _handler()
    token = current_llm_context.set(
        LLMRequestContext("https://llm.example.com", "sk-test", "test-model", "en-US")
    )
    try:
        first_outbound = await _capture_outbound(
            handler,
            lambda: handler.call_chat([{"role": "user", "content": "Hello"}]),
        )
        second_outbound = await _capture_outbound(handler, lambda: handler.call_chat(first_outbound))
    finally:
        current_llm_context.reset(token)

    assert _protocol_count(second_outbound) == 1
    assert "English (en-US)" in second_outbound[0]["content"]
