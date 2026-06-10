import pytest
import logging
import httpx
from unittest.mock import AsyncMock, patch
from backend.services.LLM_service import LLMHandler
from backend.core.llm_context import current_llm_context, LLMRequestContext

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
            with caplog.at_level(logging.ERROR):
                res = await handler._call_api(
                    request_data={},
                    print_log=False,
                    prompt_label="prompt",
                    query_label="query"
                )
                
        # Verify result is None
        assert res is None
        
        # Verify log contents
        log_messages = [record.message for record in caplog.records]
        err_logs = [m for m in log_messages if "[LLM ERROR]" in m]
        
        # Ensure we have logs
        assert len(err_logs) > 0
        
        # Check that metadata is logged in at least one attempt log
        assert any("host=llm.example.com" in log for log in err_logs)
        assert any("status_code=500" in log for log in err_logs)
        assert any("response_length=" in log for log in err_logs)
        
        # Check that the secret body must NEVER be in any of the logs
        for log in err_logs:
            assert "secret-database-leak-password-xyz" not in log
            
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
            with caplog.at_level(logging.ERROR):
                res = await handler._call_api(
                    request_data={},
                    print_log=False,
                    prompt_label="prompt",
                    query_label="query"
                )
                
        assert res is None
        
        log_messages = [record.message for record in caplog.records]
        err_logs = [m for m in log_messages if "[LLM ERROR]" in m]
        
        assert len(err_logs) > 0
        
        # Assert that attempt logs contain structure info
        assert any("returned invalid response structure" in log for log in err_logs)
        assert any("status_code=200" in log for log in err_logs)
        assert any("request_id=req-id-abc-123" in log for log in err_logs)
        
        # Raw payload must NEVER be in any of the logs
        for log in err_logs:
            assert "secret-payload-content" not in log
            
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
            with caplog.at_level(logging.ERROR):
                res = await handler._call_api(
                    request_data={},
                    print_log=False,
                    prompt_label="prompt",
                    query_label="query"
                )
                
        assert res is None
        
        log_messages = [record.message for record in caplog.records]
        err_logs = [m for m in log_messages if "[LLM ERROR]" in m]
        
        assert len(err_logs) > 0
        for log in err_logs:
            # Check that credentials are masked
            assert "db-secret" not in log
            assert "plain-secret" not in log
            assert "postgresql://admin:****" in log
            
    finally:
        current_llm_context.reset(token)
