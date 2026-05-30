from __future__ import annotations

import asyncio
import json
from typing import Any

from backend.services.LLM_service import LLMHandler


def render_prompt(template: str, replacements: dict[str, str]) -> str:
    prompt = template
    for flag, value in replacements.items():
        prompt = prompt.replace(flag, value)
    return prompt


class SkillBackedLLMJsonClient:
    def __init__(self) -> None:
        self._llm_handler = LLMHandler()

    async def ask_json(self, prompt: str) -> dict[str, Any]:
        content = await self._llm_handler.call_llm(
            prompt=prompt,
            query="",
            print_log=True,
            response_format={"type": "json_object"},
        )
        if content is None:
            raise ValueError("invalid_skill_payload")
        try:
            value = json.loads(content)
        except json.JSONDecodeError as error:
            raise ValueError("invalid_skill_payload") from error
        if not isinstance(value, dict):
            raise ValueError("invalid_skill_payload")
        return value


class SyncSkillBackedLLMJsonClient:
    def __init__(self) -> None:
        self._async_client = SkillBackedLLMJsonClient()

    def ask_json(self, prompt: str) -> dict[str, Any]:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._async_client.ask_json(prompt))

        raise RuntimeError(
            "SyncSkillBackedLLMJsonClient.ask_json must run outside an active event loop."
        )

