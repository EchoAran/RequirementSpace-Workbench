import logging
from unittest.mock import patch

import httpx
import pytest

from backend.services.LLM_service import LLMHandler
from backend.core.logging.context import clear_log_context, set_log_context


async def _no_sleep(*args, **kwargs):
    return None


def _events(caplog):
    return [record for record in caplog.records if hasattr(record, "event")]


@pytest.mark.asyncio
async def test_llm_category_disabled_suppresses_summary_events(monkeypatch, caplog):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "request")

    handler = LLMHandler(
        api_url="https://llm.example.com",
        api_key="test-api-key",
        model_name="test-model",
        temperature="0",
    )
    response = httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"content": "ok"}}]},
    )

    with patch("httpx.AsyncClient.post", return_value=response):
        with caplog.at_level(logging.INFO):
            result = await handler._call_api(
                request_data={"model": "test-model", "messages": []},
                print_log=True,
                prompt_label="secret prompt",
                query_label="secret query",
            )

    assert result == "ok"
    assert not _events(caplog)


@pytest.mark.asyncio
async def test_llm_success_logs_summary_without_content_by_default(monkeypatch, caplog):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "llm")
    clear_log_context()
    set_log_context(request_id="app-req-success")

    handler = LLMHandler(
        api_url="https://llm.example.com",
        api_key="test-api-key",
        model_name="test-model",
        temperature="0",
    )
    response = httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"content": "model answer secret"}}]},
        headers={"x-request-id": "provider-req-1"},
    )

    with patch("httpx.AsyncClient.post", return_value=response):
        with caplog.at_level(logging.INFO):
            result = await handler._call_api(
                request_data={
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "secret prompt"}],
                },
                print_log=True,
                prompt_label="secret prompt",
                query_label="secret query",
            )

    assert result == "model answer secret"
    events = _events(caplog)
    assert any(record.event == "llm_api_call_attempt" for record in events)
    completed = [record for record in events if record.event == "llm_api_call_completed"]
    assert len(completed) == 1
    assert completed[0].log_fields["provider_host"] == "llm.example.com"
    assert completed[0].log_fields["model"] == "test-model"
    assert completed[0].log_fields["status_code"] == 200
    assert completed[0].log_fields["request_id"] == "app-req-success"
    assert completed[0].log_fields["provider_request_id"] == "provider-req-1"
    assert not any(record.event in {"llm_prompt_sample", "llm_response_sample"} for record in events)
    assert "secret prompt" not in "\n".join(record.getMessage() for record in caplog.records)
    clear_log_context()


@pytest.mark.asyncio
async def test_llm_content_requires_category_and_print_log(monkeypatch, caplog):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "llm,llm_content")

    handler = LLMHandler(
        api_url="https://llm.example.com",
        api_key="test-api-key",
        model_name="test-model",
        temperature="0",
    )
    response = httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"content": "answer api_key=response-secret " + "x" * 300}}]},
    )

    with patch("httpx.AsyncClient.post", return_value=response):
        with caplog.at_level(logging.INFO):
            result = await handler._call_api(
                request_data={"model": "test-model", "messages": []},
                print_log=False,
                prompt_label="prompt api_key=prompt-secret",
                query_label="query",
            )

    assert result is not None
    assert not any(record.event in {"llm_prompt_sample", "llm_response_sample"} for record in _events(caplog))

    caplog.clear()
    with patch("httpx.AsyncClient.post", return_value=response):
        with caplog.at_level(logging.INFO):
            result = await handler._call_api(
                request_data={"model": "test-model", "messages": []},
                print_log=True,
                prompt_label="prompt api_key=prompt-secret " + "y" * 300,
                query_label="query",
            )

    assert result is not None
    events = _events(caplog)
    prompt_sample = next(record for record in events if record.event == "llm_prompt_sample")
    response_sample = next(record for record in events if record.event == "llm_response_sample")
    assert "prompt-secret" not in str(prompt_sample.log_fields)
    assert "response-secret" not in str(response_sample.log_fields)
    assert prompt_sample.log_fields["truncated"] is True
    assert response_sample.log_fields["truncated"] is True


@pytest.mark.asyncio
async def test_llm_http_error_logs_metadata_only(monkeypatch, caplog):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "llm")

    handler = LLMHandler(
        api_url="https://llm.example.com",
        api_key="test-api-key",
        model_name="test-model",
        temperature="0",
    )
    response = httpx.Response(
        status_code=429,
        content=b"provider body secret api_key=provider-secret",
    )

    with patch("httpx.AsyncClient.post", return_value=response):
        with patch.object(LLMHandler, "_sleep_before_retry", side_effect=_no_sleep):
            with caplog.at_level(logging.INFO):
                result = await handler._call_api(
                    request_data={"model": "test-model", "messages": []},
                    print_log=True,
                    prompt_label="prompt",
                    query_label="query",
                )

    assert result is None
    events = _events(caplog)
    failed = [record for record in events if record.event == "llm_api_call_failed"]
    assert len(failed) == 3
    assert failed[0].log_fields["status_code"] == 429
    assert failed[0].log_fields["response_chars"] == len(response.text)
    assert any(record.event == "llm_api_call_all_attempts_failed" for record in events)
    rendered = "\n".join(record.getMessage() + str(getattr(record, "log_fields", "")) for record in caplog.records)
    assert "provider-secret" not in rendered
    assert "provider body secret" not in rendered


@pytest.mark.asyncio
async def test_llm_invalid_response_logs_invalid_event(monkeypatch, caplog):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "llm")
    clear_log_context()
    set_log_context(request_id="app-req-invalid")

    handler = LLMHandler(
        api_url="https://llm.example.com",
        api_key="test-api-key",
        model_name="test-model",
        temperature="0",
    )
    response = httpx.Response(
        status_code=200,
        json={"secret": "payload-secret"},
        headers={"x-request-id": "provider-req-invalid"},
    )

    with patch("httpx.AsyncClient.post", return_value=response):
        with patch.object(LLMHandler, "_sleep_before_retry", side_effect=_no_sleep):
            with caplog.at_level(logging.INFO):
                result = await handler._call_api(
                    request_data={"model": "test-model", "messages": []},
                    print_log=True,
                    prompt_label="prompt",
                    query_label="query",
                )

    assert result is None
    events = _events(caplog)
    invalid = [record for record in events if record.event == "llm_response_invalid"]
    assert len(invalid) == 3
    assert invalid[0].log_fields["request_id"] == "app-req-invalid"
    assert invalid[0].log_fields["provider_request_id"] == "provider-req-invalid"
    assert "payload-secret" not in "\n".join(
        record.getMessage() + str(getattr(record, "log_fields", "")) for record in caplog.records
    )
    clear_log_context()


@pytest.mark.asyncio
async def test_llm_success_without_provider_request_id_keeps_context_request_id(monkeypatch, caplog):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "llm")
    clear_log_context()
    set_log_context(request_id="app-req-no-provider")

    handler = LLMHandler(
        api_url="https://llm.example.com",
        api_key="test-api-key",
        model_name="test-model",
        temperature="0",
    )
    response = httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"content": "ok"}}]},
    )

    try:
        with patch("httpx.AsyncClient.post", return_value=response):
            with caplog.at_level(logging.INFO):
                result = await handler._call_api(
                    request_data={"model": "test-model", "messages": []},
                    print_log=True,
                    prompt_label="prompt",
                    query_label="query",
                )
    finally:
        clear_log_context()

    assert result == "ok"
    completed = [record for record in _events(caplog) if record.event == "llm_api_call_completed"]
    assert len(completed) == 1
    assert completed[0].log_fields["request_id"] == "app-req-no-provider"
    assert "provider_request_id" not in completed[0].log_fields
