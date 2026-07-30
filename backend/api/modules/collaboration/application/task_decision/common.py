from fastapi import HTTPException

from backend.database.model import CollaborationTaskModel, NotificationModel


async def _load_decidable_task(
    session,
    project_id: int,
    task_id: int,
    user_id: int,
    is_admin_or_owner: bool,
) -> tuple[CollaborationTaskModel, bool]:
    task = await session.get(CollaborationTaskModel, task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail="Task not found in this project.",
        )
    if task.status != "open":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot decide on a task in {task.status} status.",
        )
    is_assignee = task.assigned_to_user_id == user_id
    if not is_assignee and not is_admin_or_owner:
        raise HTTPException(
            status_code=403,
            detail=(
                "Only the assignee or a project admin/owner can decide "
                "on this task."
            ),
        )
    return task, is_assignee


async def _record_task_decision(
    audit_service,
    session,
    project_id: int,
    task,
    action_type: str,
    acted_as_admin: bool,
    note: str | None,
) -> None:
    await audit_service.record(
        session=session,
        project_id=project_id,
        action_type=action_type,
        summary=action_type,
        target_type="task",
        target_id=task.id,
        task_id=task.id,
        payload={
            "acted_as_admin": acted_as_admin,
            "decision_note": note,
        },
    )


def _add_decision_notification(
    session,
    task,
    project_id: int,
    notification_kind: str,
    decision: str,
) -> None:
    result_key = "Approved" if decision == "approve" else "Rejected"
    session.add(
        NotificationModel(
            recipient_user_id=task.created_by_user_id,
            project_id=project_id,
            task_id=task.id,
            event_type="task_decided",
            title=(
                f"collaboration.notifications."
                f"{notification_kind}{result_key}.title"
            ),
            body=(
                f"collaboration.notifications."
                f"{notification_kind}{result_key}.body"
            ),
        )
    )
