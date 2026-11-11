from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.api.modules.project_lifecycle.application.interview_service import (
    ProjectInterviewService,
)


@pytest.mark.asyncio
async def test_project_interview_returns_welcome_without_user_message():
    service = ProjectInterviewService()
    llm = SimpleNamespace(call_chat=AsyncMock())
    service._get_llm_handler = lambda: llm

    result = await service.chat([{"role": "assistant", "content": "Hello"}])

    assert result["is_ready"] is False
    assert result["summary"] == ""
    llm.call_chat.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected_reply", "expected_ready", "expected_summary"),
    [
        (None, None, False, ""),
        ("plain text", "plain text", False, ""),
        (
            '{"assistant_message":"Ready","is_ready_to_generate":true,"summary":"Scope"}',
            "Ready",
            True,
            "Scope",
        ),
    ],
)
async def test_project_interview_preserves_response_fallbacks(
    monkeypatch,
    response,
    expected_reply,
    expected_ready,
    expected_summary,
):
    llm = SimpleNamespace(call_chat=AsyncMock(return_value=response))
    monkeypatch.setattr(
        ProjectInterviewService,
        "_get_llm_handler",
        staticmethod(lambda: llm),
    )

    result = await ProjectInterviewService().chat(
        [{"role": "user", "content": "Describe the project"}]
    )

    if expected_reply is None:
        assert result["reply"]
    else:
        assert result["reply"] == expected_reply
    assert result["is_ready"] is expected_ready
    assert result["summary"] == expected_summary
