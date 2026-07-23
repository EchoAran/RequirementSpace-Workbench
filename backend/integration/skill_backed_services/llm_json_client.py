from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable
from typing import Any

from backend.services.llm_handler_service import LLMHandler


def render_prompt(template: str, replacements: dict[str, str]) -> str:
    prompt = template
    for flag, value in replacements.items():
        prompt = prompt.replace(flag, value)
    return prompt


class SkillBackedLLMJsonClient:
    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None
    ) -> None:
        self._llm_handler = LLMHandler(
            api_url=api_url,
            api_key=api_key,
            model_name=model_name
        )

    async def ask_json(
        self,
        prompt: str,
        protected_inputs: Iterable[str] = (),
        timeout_seconds: float = 100.0,
    ) -> dict[str, Any]:
        content = await self._llm_handler.call_llm(
            prompt=prompt,
            query="",
            print_log=True,
            response_format={"type": "json_object"},
            protected_inputs=protected_inputs,
            raise_on_failure=True,
            timeout_seconds=timeout_seconds,
        )
        if content is None:
            raise ValueError("invalid_skill_payload")
        try:
            value = json.loads(content)
        except json.JSONDecodeError as error:
            raise ValueError(
                "invalid_skill_json: "
                f"{error.msg} at line {error.lineno} column {error.colno}"
            ) from error
        if not isinstance(value, dict):
            raise ValueError(
                f"invalid_skill_json: expected object, got {type(value).__name__}"
            )
        return value


class SyncSkillBackedLLMJsonClient:
    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None
    ) -> None:
        self._async_client = SkillBackedLLMJsonClient(
            api_url=api_url,
            api_key=api_key,
            model_name=model_name
        )

    def ask_json(
        self,
        prompt: str,
        protected_inputs: Iterable[str] = (),
    ) -> dict[str, Any]:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self._async_client.ask_json(prompt, protected_inputs=protected_inputs)
            )

        raise RuntimeError(
            "SyncSkillBackedLLMJsonClient.ask_json must run outside an active event loop."
        )
