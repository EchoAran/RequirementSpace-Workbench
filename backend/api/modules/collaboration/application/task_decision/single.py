from fastapi import HTTPException

from backend.database.model import ConfirmationStatus

from .common import (
    _add_decision_notification,
    _record_task_decision,
)


async def _supersede_changed_single_task(
    session,
    task,
    project_id: int,
    note: str | None,
    audit_service,
    now,
) -> None:
    task.status = "superseded"
    task.completed_at = now()
    task.decision_note = note or "内容已变更，自动失效"
    await audit_service.record(
        session=session,
        project_id=project_id,
        action_type="task_superseded",
        summary="task_superseded",
        target_type="task",
        target_id=task.id,
        task_id=task.id,
        payload={"reason": "content_hash_mismatch"},
    )
    await session.commit()
    raise HTTPException(
        status_code=409,
        detail="task_content_changed",
    )


async def _record_single_status_change(
    audit_service,
    session,
    project_id: int,
    task,
    old_status: str,
    new_status: str,
    reason: str,
) -> None:
    if old_status == new_status:
        return
    await audit_service.record(
        session=session,
        project_id=project_id,
        action_type="update_confirmation_status",
        summary=(
            f"更新 {task.target_type} 状态: {old_status} -> "
            f"{new_status} ({reason})"
        ),
        target_type=task.target_type,
        target_id=int(task.target_id),
        task_id=task.id,
        diff={
            "confirmation_status": {
                "before": old_status,
                "after": new_status,
            }
        },
    )


async def decide_single_task(
    session,
    task,
    project_id: int,
    is_assignee: bool,
    is_admin_or_owner: bool,
    decision: str,
    note: str | None,
    audit_service,
    snapshot_service,
    now,
):
    try:
        snapshot = await snapshot_service.get_snapshot_and_hash(
            session,
            task.target_type,
            int(task.target_id),
        )
    except ValueError:
        await _supersede_changed_single_task(
            session,
            task,
            project_id,
            note,
            audit_service,
            now,
        )
    node = snapshot["node"]
    if snapshot["hash"] != task.content_hash:
        await _supersede_changed_single_task(
            session,
            task,
            project_id,
            note,
            audit_service,
            now,
        )

    task.completed_at = now()
    task.decision_note = note
    acted_as_admin = not is_assignee and is_admin_or_owner
    if decision == "approve":
        task.status = "done"
        action_type = "task_approved"
        new_status = ConfirmationStatus.CONFIRMED.value
        reason = "确认任务通过"
    elif decision == "reject":
        task.status = "rejected"
        action_type = "task_rejected"
        new_status = ConfirmationStatus.NEEDS_CONFIRMATION.value
        reason = "确认任务驳回"
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid decision. Must be approve or reject.",
        )

    old_status = node.confirmation_status
    if decision == "approve" or old_status != new_status:
        node.confirmation_status = new_status
    await _record_task_decision(
        audit_service,
        session,
        project_id,
        task,
        action_type,
        acted_as_admin,
        note,
    )
    await _record_single_status_change(
        audit_service,
        session,
        project_id,
        task,
        old_status,
        new_status,
        reason,
    )

    _add_decision_notification(
        session,
        task,
        project_id,
        "singleTask",
        decision,
    )
    return task
