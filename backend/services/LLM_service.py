import asyncio
import os
import logging
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_llm_config() -> dict[str, str] | None:
    """Load LLM configuration from backend .env."""

    root_dir = Path(__file__).resolve().parents[2]
    env_path = root_dir / ".env"
    load_dotenv(dotenv_path=env_path)

    config = {
        "api_url": os.getenv("LLM_API_URL", "").strip(),
        "api_key": os.getenv("LLM_API_KEY", "").strip(),
        "model_name": os.getenv("LLM_MODEL_NAME", "").strip(),
        "temperature": os.getenv("LLM_TEMPERATURE", "").strip(),
    }

    if any(not value for value in config.values()):
        return None

    return config


class LLMHandler:
    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
        temperature: str | None = None,
    ):
        config = load_llm_config() or {}

        self.api_url = (api_url or config.get("api_url") or "").rstrip("/")
        self.api_key = api_key or config.get("api_key") or ""
        self.model_name = model_name or config.get("model_name") or ""
        self.temperature = temperature or config.get("temperature") or ""

    def _validate_settings(self) -> bool:
        required_fields = [
            self.api_url,
            self.api_key,
            self.model_name,
            self.temperature,
        ]
        return all(field and str(field).strip() for field in required_fields)

    @staticmethod
    def _log(enabled: bool, message: str) -> None:
        if enabled:
            print(message)

    def _build_request_data(self, prompt: str, query: str) -> dict:
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": query},
        ]

        return {
            "model": self.model_name,
            "messages": messages,
            "temperature": float(self.temperature),
        }

    def _build_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    async def call_llm(
        self,
        prompt: str,
        query: str | None = "",
        print_log: bool = True,
        response_format: dict | None = None,
    ) -> Optional[str]:
        query = query or ""

        if not self._validate_settings():
            logger.error("[LLM ERROR] The LLM settings are incomplete. Please ensure LLM_API_URL, LLM_API_KEY, LLM_MODEL_NAME, and LLM_TEMPERATURE are set correctly.")
            self._log(
                print_log,
                "The LLM settings are incomplete, making it impossible to call the large model.",
            )
            return None

        try:
            request_data = self._build_request_data(prompt, query)
        except ValueError as exc:
            self._log(print_log, f"Invalid LLM temperature value: {self.temperature} \n{exc}")
            return None

        if response_format is not None:
            request_data["response_format"] = response_format

        return await self._call_api(
            request_data=request_data,
            print_log=print_log,
            prompt_label=prompt,
            query_label=query,
        )

    async def call_chat(
        self,
        messages: list[dict],
        print_log: bool = True,
        response_format: dict | None = None,
    ) -> Optional[str]:
        """
        Multi-turn chat LLM call.
        Accepts a full list of messages (system + user + assistant history)
        instead of the single prompt+query pattern used by call_llm.

        Designed for InterviewStrategy where conversation history needs to be preserved.
        """
        if not self._validate_settings():
            logger.error("[LLM ERROR] The LLM settings are incomplete. Please ensure LLM_API_URL, LLM_API_KEY, LLM_MODEL_NAME, and LLM_TEMPERATURE are set correctly.")
            self._log(print_log, "The LLM settings are incomplete, making it impossible to call the large model.")
            return None

        request_data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": float(self.temperature),
        }

        if response_format is not None:
            request_data["response_format"] = response_format

        return await self._call_api(
            request_data=request_data,
            print_log=print_log,
            prompt_label=messages[0]["content"] if messages else "",
            query_label=messages[-1]["content"] if messages else "",
        )

    async def _call_api(
        self,
        request_data: dict,
        print_log: bool,
        prompt_label: str,
        query_label: str,
    ) -> Optional[str]:
        """Shared HTTP call + retry logic for call_llm and call_chat."""
        attempts = 3
        base_delay = 0.8
        last_error_text: str | None = None

        headers = self._build_headers()
        url = f"{self.api_url}/v1/chat/completions"

        for attempt in range(1, attempts + 1):
            self._log(print_log, f"\n[PROMPT] LLM call attempt {attempt}:\n{prompt_label[:200]}")

            if query_label.strip():
                self._log(print_log, f"\n[QUERY] LLM call attempt {attempt}:\n{query_label[:200]}")

            self._log(print_log, f"\n{'---' * 40}")

            try:
                async with httpx.AsyncClient(timeout=100.0) as client:
                    response = await client.post(url, json=request_data, headers=headers)

                if response.status_code != 200:
                    last_error_text = f"{response.status_code} - {response.text}"
                    logger.error(f"[LLM ERROR] Attempt {attempt} failed: {last_error_text}")
                    self._log(print_log, f"The LLM API call failed: {last_error_text}")
                    await self._sleep_before_retry(attempt, attempts, base_delay)
                    continue

                result = response.json()
                content = self._extract_content(result)

                if content is None:
                    last_error_text = f"LLM response format exception: {result}"
                    logger.error(f"[LLM ERROR] Attempt {attempt} returned invalid format: {last_error_text}")
                    self._log(print_log, last_error_text)
                    await self._sleep_before_retry(attempt, attempts, base_delay)
                    continue

                self._log(print_log, f"\n[Response]\n{content}")
                self._log(print_log, f"\n{'---' * 40}")

                return content

            except httpx.ConnectError as exc:
                last_error_text = str(exc)
                logger.error(f"[LLM ERROR] Connection failed on attempt {attempt}: {last_error_text}")
                self._log(print_log, f"The LLM API connection failed: {last_error_text}")

            except httpx.TimeoutException as exc:
                last_error_text = str(exc)
                logger.error(f"[LLM ERROR] Request timed out on attempt {attempt}: {last_error_text}")
                self._log(print_log, f"The LLM API request timed out: {last_error_text}")

            except Exception as exc:
                last_error_text = f"{exc} ({type(exc).__name__})"
                logger.exception(f"[LLM ERROR] Unexpected error on attempt {attempt}: {last_error_text}")
                self._log(print_log, f"An error occurred when invoking the LLM service: {last_error_text}")

            await self._sleep_before_retry(attempt, attempts, base_delay)

        logger.error(f"[LLM ERROR] All {attempts} attempts failed. Last error: {last_error_text}")
        self._log(print_log, str(last_error_text))
        return None

    @staticmethod
    def _extract_content(result: dict) -> str | None:
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return None

        if not isinstance(content, str):
            return None

        content = content.strip()
        return content or None

    @staticmethod
    async def _sleep_before_retry(
        attempt: int,
        attempts: int,
        base_delay: float,
    ) -> None:
        if attempt >= attempts:
            return

        delay = base_delay * (2 ** (attempt - 1))
        await asyncio.sleep(delay)


if __name__ == "__main__":

    async def main():
        llm = LLMHandler()
        response = await llm.call_llm(
            prompt="你好",
            print_log=True,     # 是否打印日志
        )
        print(response)

    asyncio.run(main())
