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
import time
from backend.core.generators.prompts.project_interview_prompt import (
    PROJECT_INTERVIEW_SYSTEM_PROMPT,
)
from backend.core.logging import get_logger, log_event
from backend.core.logging.events import (
    PROJECT_INTERVIEW_COMPLETE_FAILED,
    PROJECT_INTERVIEW_MESSAGE_PROCESSED,
)

logger = get_logger(__name__)


class ProjectInterviewService:
    """Stateless project interview service. Each chat call is independent."""

    async def chat(self, messages: list[dict]) -> dict:
        """Send the full conversation history and get the AI's next response.

        messages format: [{"role": "user"|"assistant", "content": "..."}, ...]
        The system prompt is prepended automatically.

        Returns: {"reply": "...", "is_ready": false, "summary": ""}
        """
        start_time = time.perf_counter()
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
            log_event(
                logger,
                logging.WARNING,
                "domain",
                PROJECT_INTERVIEW_COMPLETE_FAILED,
                "Project interview completion failed",
                error_type="empty_llm_response",
                duration_ms=int((time.perf_counter() - start_time) * 1000),
                message_count=len(messages),
            )
            return {
                "reply": "抱歉，我现在有点忙，请稍后再试。",
                "is_ready": False,
                "summary": "",
            }

        try:
            parsed = json.loads(response)
        except (json.JSONDecodeError, ValueError):
            log_event(
                logger,
                logging.WARNING,
                "domain",
                PROJECT_INTERVIEW_COMPLETE_FAILED,
                "Project interview completion failed",
                error_type="invalid_json_response",
                response_length=len(response),
                duration_ms=int((time.perf_counter() - start_time) * 1000),
                message_count=len(messages),
            )
            return {
                "reply": response or "请继续描述你的项目需求。",
                "is_ready": False,
                "summary": "",
            }

        is_ready = bool(parsed.get("is_ready_to_generate", False))
        log_event(
            logger,
            logging.INFO,
            "domain",
            PROJECT_INTERVIEW_MESSAGE_PROCESSED,
            "Project interview message processed",
            duration_ms=int((time.perf_counter() - start_time) * 1000),
            message_count=len(messages),
            is_ready=is_ready,
        )
        return {
            "reply": parsed.get("assistant_message", ""),
            "is_ready": is_ready,
            "summary": parsed.get("summary", ""),
        }

    @staticmethod
    def _get_llm_handler():
        from backend.services.llm_handler_service import LLMHandler
        return LLMHandler()
