import asyncio
import logging
import os
import httpx
from unittest.mock import patch
from backend.services.llm_handler_service import LLMHandler
from backend.core.llm_context import current_llm_context, LLMRequestContext

class MockCaplog:
    def __init__(self):
        self.records = []
        self.handler = logging.StreamHandler()
        class MockRecord:
            def __init__(self, record):
                self.record = record
                self.event = getattr(record, "event", None)
                self.log_fields = getattr(record, "log_fields", {})
            def getMessage(self):
                return self.record.getMessage()
        self.MockRecord = MockRecord

    def at_level(self, level, logger=None):
        class Context:
            def __init__(self, level, logger_name):
                self.level = level
                self.logger = logging.getLogger(logger_name)
                self.orig_level = self.logger.level

            def __enter__(self):
                self.logger.setLevel(self.level)
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.logger.setLevel(self.orig_level)

        return Context(level, logger)

async def run_hardening(caplog):
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
        mock_response = httpx.Response(
            status_code=500,
            content=b"secret-database-leak-password-xyz",
            headers={"Content-Type": "text/plain"}
        )
        with patch("httpx.AsyncClient.post", return_value=mock_response):
            with patch.object(LLMHandler, "_sleep_before_retry", return_value=None):
                with caplog.at_level(logging.ERROR):
                    res = await handler._call_api(
                        request_data={},
                        print_log=False,
                        prompt_label="prompt",
                        query_label="query"
                    )
    finally:
        current_llm_context.reset(token)

async def run_logging(caplog):
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
            print("Run logging result:", result)

async def main():
    os.environ["LOG_ENABLED"] = "true"
    os.environ["LOG_ENABLED_CATEGORIES"] = "llm"
    
    # Configure root logger handler
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    log_records = []
    class CaptureHandler(logging.Handler):
        def emit(self, record):
            log_records.append(record)
    ch = CaptureHandler()
    root.addHandler(ch)

    caplog = MockCaplog()
    caplog.records = log_records

    print("Before hardening:")
    print("  Root level:", logging.getLevelName(root.level))
    print("  Backend level:", logging.getLevelName(logging.getLogger("backend").level))

    await run_hardening(caplog)

    print("After hardening / Before logging:")
    print("  Root level:", logging.getLevelName(root.level))
    print("  Backend level:", logging.getLevelName(logging.getLogger("backend").level))

    log_records.clear()
    await run_logging(caplog)

    print("After logging:")
    print("  Log records count:", len(log_records))
    for r in log_records:
        print(f"    {logging.getLevelName(r.levelno)}: {r.getMessage()} event={getattr(r, 'event', None)}")

asyncio.run(main())
