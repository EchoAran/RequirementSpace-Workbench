"""
Project Interview Service — stateless conversation with an AI interview agent.

The interview agent asks questions to gather project requirements.
When enough information is collected, it produces a natural-language summary
that becomes the project's user_requirements field.

No sessions, no drafts. The frontend maintains the message list.
"""

from __future__ import annotations

import json
import logging
from backend.core.generators.prompts.project_interview_prompt import (
    PROJECT_INTERVIEW_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


class ProjectInterviewService:
    """Stateless project interview service. Each chat call is independent."""

    async def chat(self, messages: list[dict]) -> dict:
        """Send the full conversation history and get the AI's next response.

        messages format: [{"role": "user"|"assistant", "content": "..."}, ...]
        The system prompt is prepended automatically.

        Returns: {"reply": "...", "is_ready": false, "summary": ""}
        """
        if not messages or not any(m.get("role") == "user" for m in messages):
            return {
                "reply": "你好！请告诉我你想构建一个什么样的项目？它的核心目标是什么？",
                "is_ready": False,
                "summary": "",
            }

        llm = self._get_llm_handler()
        full_messages = [
            {"role": "system", "content": PROJECT_INTERVIEW_SYSTEM_PROMPT},
        ] + messages

        response = await llm.call_chat(
            messages=full_messages,
            response_format={"type": "json_object"},
        )

        if not response:
            return {
                "reply": "抱歉，我现在有点忙，请稍后再试。",
                "is_ready": False,
                "summary": "",
            }

        try:
            parsed = json.loads(response)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Project interview LLM returned non-JSON: %s", response[:100])
            return {
                "reply": response or "请继续描述你的项目需求。",
                "is_ready": False,
                "summary": "",
            }

        return {
            "reply": parsed.get("assistant_message", ""),
            "is_ready": bool(parsed.get("is_ready_to_generate", False)),
            "summary": parsed.get("summary", ""),
        }

    @staticmethod
    def _get_llm_handler():
        from backend.services.LLM_service import LLMHandler
        return LLMHandler()
