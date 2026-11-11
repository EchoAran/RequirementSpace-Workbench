import json
from unittest.mock import AsyncMock

import pytest

from backend.api.modules.ai_interaction.ai_add.application.interview_strategy import StubActorInterviewStrategy
from backend.api.modules.project_lifecycle.application.interview_service import ProjectInterviewService
from backend.core.ai_user_text import AI_USER_TEXT_INSTRUCTION, format_ai_user_text


@pytest.mark.parametrize("reference", [
    "(ID:123)", "（ID：123）", "(actor:123)", "feature:123", "flow_id=123",
    '`business_object_id: 123`', '"rule_id": 123', "参与者 ID：123", "数据库主键:123",
    "workspace_logical_uuid:550e8400-e29b-41d4-a716-446655440000",
    "actor_ids: [123, 456]", "参与者 ID 为 123", "feature_id 123", "parent_feature_id=123",
])
def test_user_text_omits_database_references(reference):
    result = format_ai_user_text(f"管理员 {reference} 负责订单，限额 500 元。")
    assert "123" not in result
    assert "550e8400" not in result
    assert "管理员" in result
    assert "500 元" in result


@pytest.mark.parametrize("identifier", ["订单ID:123", "订单 ID:123", "Order ID:123", "Invoice (ID:123)"])
def test_user_text_preserves_business_identifiers_and_numbers(identifier):
    text = f"{identifier}，订单编号 456，2026-11-11 创建，3 个商品，金额 500 元，HTTP 404。"
    assert format_ai_user_text(text) == text


@pytest.mark.asyncio
async def test_object_interview_formats_reply_and_stored_history():
    call = AsyncMock(return_value=json.dumps({
        "assistant_message": "管理员 (actor:123) 的限额为 500 元。",
        "is_ready_to_generate": False,
        "known_facts": [], "missing_facts": [],
    }))
    result = await StubActorInterviewStrategy().interview(
        project_context={"actors": [{"id": 123, "name": "管理员"}]},
        anchor={}, current_summary=None, latest_user_message="说明限额", llm_call_chat=call,
    )
    assert "123" not in result["assistant_message"]
    assert "500 元" in result["assistant_message"]
    assert result["summary"]["chat_history"][-1]["content"] == result["assistant_message"]
    assert AI_USER_TEXT_INSTRUCTION in call.await_args.kwargs["messages"][0]["content"]


@pytest.mark.asyncio
async def test_project_interview_formats_reply_and_summary(monkeypatch):
    handler = AsyncMock()
    handler.call_chat.return_value = json.dumps({
        "assistant_message": "订单系统 (project:123) 支持 500 个订单。",
        "summary": "管理员（ID：123）管理订单编号 456。",
        "is_ready_to_generate": True,
    })
    service = ProjectInterviewService()
    monkeypatch.setattr(service, "_get_llm_handler", lambda: handler)
    result = await service.chat([{"role": "user", "content": "设计订单系统"}])
    assert "123" not in result["reply"] + result["summary"]
    assert "500" in result["reply"] and "456" in result["summary"]
    assert AI_USER_TEXT_INSTRUCTION in handler.call_chat.await_args.kwargs["messages"][0]["content"]
