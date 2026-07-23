import pytest
import logging
import httpx
from unittest.mock import AsyncMock, patch
from backend.services.llm_handler_service import LLMHandler
from backend.core.llm_context import current_llm_context, LLMRequestContext


async def _no_sleep(*args, **kwargs):
    return None


def _llm_records(caplog, event):
    return [record for record in caplog.records if getattr(record, "event", None) == event]


@pytest.mark.asyncio
async def test_llm_non_200_logs_metadata_only(caplog):
    handler = LLMHandler(
        api_url="https://llm.example.com",
        api_key="my-key-123456",
        model_name="test-model"
    )
    
    # Mock context to avoid missing context check
    ctx = LLMRequestContext(
        api_url="https://llm.example.com",
        api_key="my-key-123456",
        model_name="test-model"
    )
    token = current_llm_context.set(ctx)
    
    try:
        # Mock httpx response
        mock_response = httpx.Response(
            status_code=500,
            content=b"secret-database-leak-password-xyz",
            headers={"Content-Type": "text/plain"}
        )
        
        with patch("httpx.AsyncClient.post", return_value=mock_response):
            with patch.object(LLMHandler, "_sleep_before_retry", side_effect=_no_sleep):
                with caplog.at_level(logging.ERROR), caplog.at_level(logging.ERROR, logger="backend"):
                    res = await handler._call_api(
                        request_data={},
                        print_log=False,
                        prompt_label="prompt",
                        query_label="query"
                    )
                
        # Verify result is None
        assert res is None
        
        failed_logs = _llm_records(caplog, "llm_api_call_failed")
        assert len(failed_logs) > 0
        assert any(record.log_fields["provider_host"] == "llm.example.com" for record in failed_logs)
        assert any(record.log_fields["status_code"] == 500 for record in failed_logs)
        assert any("response_chars" in record.log_fields for record in failed_logs)

        rendered = "\n".join(
            record.getMessage() + str(getattr(record, "log_fields", ""))
            for record in caplog.records
        )
        assert "secret-database-leak-password-xyz" not in rendered
            
    finally:
        current_llm_context.reset(token)

@pytest.mark.asyncio
async def test_llm_invalid_format_logs_metadata_only(caplog):
    handler = LLMHandler(
        api_url="https://llm.example.com",
        api_key="my-key-123456",
        model_name="test-model"
    )
    
    ctx = LLMRequestContext(
        api_url="https://llm.example.com",
        api_key="my-key-123456",
        model_name="test-model"
    )
    token = current_llm_context.set(ctx)
    
    try:
        # Invalid response format: doesn't contain 'choices'
        mock_response = httpx.Response(
            status_code=200,
            json={"id": "chatcmpl-123", "object": "chat.completion", "secret_field": "secret-payload-content"},
            headers={"Content-Type": "application/json", "x-request-id": "req-id-abc-123"}
        )
        
        with patch("httpx.AsyncClient.post", return_value=mock_response):
            with patch.object(LLMHandler, "_sleep_before_retry", side_effect=_no_sleep):
                with caplog.at_level(logging.ERROR), caplog.at_level(logging.ERROR, logger="backend"):
                    res = await handler._call_api(
                        request_data={},
                        print_log=False,
                        prompt_label="prompt",
                        query_label="query"
                    )
                
        assert res is None
        
        invalid_logs = _llm_records(caplog, "llm_response_invalid")
        assert len(invalid_logs) > 0
        assert any("invalid structure" in record.getMessage() for record in invalid_logs)
        assert any(record.log_fields["status_code"] == 200 for record in invalid_logs)
        assert any(record.log_fields["provider_request_id"] == "req-id-abc-123" for record in invalid_logs)

        rendered = "\n".join(
            record.getMessage() + str(getattr(record, "log_fields", ""))
            for record in caplog.records
        )
        assert "secret-payload-content" not in rendered
            
    finally:
        current_llm_context.reset(token)

@pytest.mark.asyncio
async def test_llm_exception_is_sanitized(caplog):
    handler = LLMHandler(
        api_url="https://llm.example.com",
        api_key="my-key-123456",
        model_name="test-model"
    )
    
    ctx = LLMRequestContext(
        api_url="https://llm.example.com",
        api_key="my-key-123456",
        model_name="test-model"
    )
    token = current_llm_context.set(ctx)
    
    try:
        # Cause exception containing sensitive details
        with patch("httpx.AsyncClient.post", side_effect=ValueError("connection to postgresql://admin:db-secret@localhost/private failed api_key=plain-secret")):
            with patch.object(LLMHandler, "_sleep_before_retry", side_effect=_no_sleep):
                with caplog.at_level(logging.ERROR), caplog.at_level(logging.ERROR, logger="backend"):
                    res = await handler._call_api(
                        request_data={},
                        print_log=False,
                        prompt_label="prompt",
                        query_label="query"
                    )
                
        assert res is None
        
        failed_logs = _llm_records(caplog, "llm_api_call_failed")
        assert len(failed_logs) > 0
        rendered = "\n".join(
            record.getMessage() + str(getattr(record, "log_fields", ""))
            for record in caplog.records
        )
        assert "db-secret" not in rendered
        assert "plain-secret" not in rendered
        assert "postgresql://admin:****" in rendered
            
    finally:
        current_llm_context.reset(token)
