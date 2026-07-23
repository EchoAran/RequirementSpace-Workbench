import asyncio
import logging
import os
import httpx
from unittest.mock import patch
from backend.services.llm_handler_service import LLMHandler

async def main():
    os.environ["LOG_ENABLED"] = "true"
    os.environ["LOG_ENABLED_CATEGORIES"] = "llm"
    
    # Print logger levels
    root_logger = logging.getLogger()
    backend_logger = logging.getLogger("backend")
    handler_logger = logging.getLogger("backend.services.llm_handler_service")
    
    print("Root logger level:", logging.getLevelName(root_logger.level))
    print("Backend logger level:", logging.getLevelName(backend_logger.level))
    print("Handler logger level:", logging.getLevelName(handler_logger.level))
    print("Root logger handlers:", root_logger.handlers)
    print("Backend logger handlers:", backend_logger.handlers)
    
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
    
    # Set up a stream handler to capture logs
    import io
    stream = io.StringIO()
    sh = logging.StreamHandler(stream)
    root_logger.addHandler(sh)
    
    with patch("httpx.AsyncClient.post", return_value=response):
        result = await handler._call_api(
            request_data={"model": "test-model", "messages": []},
            print_log=True,
            prompt_label="prompt",
            query_label="query",
        )
        
    print("Result:", result)
    print("Logs captured:")
    print(stream.getvalue())

asyncio.run(main())
