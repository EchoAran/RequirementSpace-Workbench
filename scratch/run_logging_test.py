import asyncio
import os
import httpx
from unittest.mock import patch
from backend.services.llm_handler_service import LLMHandler

async def main():
    os.environ["LOG_ENABLED"] = "true"
    os.environ["LOG_ENABLED_CATEGORIES"] = "llm,llm_content"
    
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
        try:
            result = await handler._call_api(
                request_data={"model": "test-model", "messages": []},
                print_log=False,
                prompt_label="prompt api_key=prompt-secret",
                query_label="query",
            )
            print("SUCCESS! Result:", result)
        except Exception as e:
            import traceback
            traceback.print_exc()

asyncio.run(main())
