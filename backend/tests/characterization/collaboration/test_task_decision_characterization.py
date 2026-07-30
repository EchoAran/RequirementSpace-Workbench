from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.api.modules.collaboration.application import task_service
from backend.api.modules.collaboration.application.task_service import TaskService
from backend.database.model import ConfirmationStatus, NotificationModel


class _FakeSession:
    def __init__(self, task=None):
        self.task = task
        self.added = []
        self.commit_count = 0

    async def get(self, _model, _task_id):
        return self.task

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commit_count += 1


def _make_task(**overrides):
    values = {
        "id": 41,
        "project_id": 7,
        "task_type": "confirm_node",
        "status": "open",
        "assigned_to_user_id": 11,
        "created_by_user_id": 12,
        "target_type": "feature",
        "target_id": "9",
        "content_hash": "stable-hash",
        "targets": [],
        "payload": {},
        "completed_at": None,
        "decision_note": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_decide_task_keeps_guard_error_precedence():
    service = TaskService()
    session = _FakeSession()

    with pytest.raises(HTTPException) as missing_error:
        await service.decide_task(session, 7, 41, 11, False, "approve")
    assert (missing_error.value.status_code, missing_error.value.detail) == (
        404,
        "Task not found in this project.",
    )

    session.task = _make_task(project_id=8)
    with pytest.raises(HTTPException) as wrong_project_error:
        await service.decide_task(session, 7, 41, 11, False, "approve")
    assert (
        wrong_project_error.value.status_code,
        wrong_project_error.value.detail,
    ) == (404, "Task not found in this project.")

    session.task = _make_task(status="done")
    with pytest.raises(HTTPException) as closed_error:
        await service.decide_task(session, 7, 41, 11, False, "approve")
    assert (closed_error.value.status_code, closed_error.value.detail) == (
        400,
        "Cannot decide on a task in done status.",
    )

    session.task = _make_task(assigned_to_user_id=99)
    with pytest.raises(HTTPException) as permission_error:
        await service.decide_task(session, 7, 41, 11, False, "approve")
    assert (
        permission_error.value.status_code,
        permission_error.value.detail,
    ) == (
        403,
        "Only the assignee or a project admin/owner can decide on this task.",
    )


@pytest.mark.asyncio
async def test_batch_hash_mismatch_commits_superseded_state_before_409():
    task = _make_task(
        task_type="confirm_nodes",
        targets=[
            {
                "node_kind": "feature",
                "node_id": 9,
                "hash": "old-hash",
            },
            {
                "node_kind": "actor",
                "node_id": 3,
                "hash": "deleted-hash",
            },
        ],
    )
    session = _FakeSession(task)
    snapshots = AsyncMock(
        side_effect=[
            {
                "hash": "new-hash",
                "node": SimpleNamespace(
                    confirmation_status=(
                        ConfirmationStatus.NEEDS_CONFIRMATION.value
                    )
                ),
            },
            LookupError("deleted"),
        ]
    )
    audit = AsyncMock()

    with (
        patch.object(
            task_service.snapshot_service,
            "get_snapshot_and_hash",
            snapshots,
        ),
        patch.object(task_service.audit_service, "record", audit),
    ):
        with pytest.raises(HTTPException) as error:
            await TaskService().decide_task(
                session,
                7,
                41,
                11,
                False,
                "approve",
                "请重新确认",
            )

    assert error.value.status_code == 409
    assert error.value.detail == {
        "message": "task_content_changed",
        "mismatches": [
            {
                "node_kind": "feature",
                "node_id": 9,
                "reason": "content_changed",
            },
            {
                "node_kind": "actor",
                "node_id": 3,
                "reason": "deleted",
            },
        ],
    }
    assert task.status == "superseded"
    assert task.decision_note == "请重新确认"
    assert session.commit_count == 1
    assert audit.await_args.kwargs["payload"] == {
        "mismatches": error.value.detail["mismatches"]
    }


@pytest.mark.asyncio
async def test_invalid_batch_decision_keeps_current_partial_mutation():
    node = SimpleNamespace(
        confirmation_status=ConfirmationStatus.NEEDS_CONFIRMATION.value
    )
    task = _make_task(
        task_type="confirm_nodes",
        targets=[
            {
                "node_kind": "feature",
                "node_id": 9,
                "hash": "stable-hash",
            }
        ],
    )
    session = _FakeSession(task)

    with patch.object(
        task_service.snapshot_service,
        "get_snapshot_and_hash",
        AsyncMock(return_value={"hash": "stable-hash", "node": node}),
    ):
        with pytest.raises(HTTPException) as error:
            await TaskService().decide_task(
                session,
                7,
                41,
                11,
                False,
                "later",
                "暂缓",
            )

    assert (error.value.status_code, error.value.detail) == (
        400,
        "Invalid decision. Must be approve or reject.",
    )
    assert task.status == "open"
    assert task.completed_at is not None
    assert task.decision_note == "暂缓"
    assert session.added == []


@pytest.mark.asyncio
async def test_conflict_edit_approval_keeps_handler_payload_and_notification():
    stale_result = {
        "original_object": {"id": 9, "name": "旧名称"},
        "diff": {"name": "新名称"},
    }
    task = _make_task(
        task_type="resolve_conflict",
        payload={
            "target_type": "edit_feature",
            "stale_ai_result": stale_result,
        },
    )
    session = _FakeSession(task)
    handler = MagicMock()
    handler._confirm_edit_draft = AsyncMock()
    audit = AsyncMock()

    with (
        patch(
            "backend.api.modules.ai_interaction.public.AIAddSessionService",
            return_value=MagicMock(),
        ),
        patch(
            "backend.api.modules.ai_interaction.public.AIAddDraftHandler",
            return_value=handler,
        ),
        patch.object(task_service.audit_service, "record", audit),
    ):
        result = await TaskService().decide_task(
            session,
            7,
            41,
            11,
            False,
            "approve",
            "同意合并",
        )

    assert result is task
    assert task.status == "done"
    handler._confirm_edit_draft.assert_awaited_once_with(
        {
            "project_id": 7,
            "original_object": stale_result["original_object"],
            "diff": stale_result["diff"],
            "target_type": "edit_feature",
        },
        session,
    )
    notification = session.added[0]
    assert isinstance(notification, NotificationModel)
    assert (
        notification.recipient_user_id,
        notification.event_type,
        notification.title,
        notification.body,
    ) == (
        12,
        "task_decided",
        "collaboration.notifications.conflictTaskApproved.title",
        "collaboration.notifications.conflictTaskApproved.body",
    )
    assert audit.await_args.kwargs["payload"] == {
        "acted_as_admin": False,
        "decision_note": "同意合并",
    }
