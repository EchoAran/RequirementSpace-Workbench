from fastapi import HTTPException

from .common import (
    _add_decision_notification,
    _record_task_decision,
)


async def _persist_approved_conflict_payload(
    session,
    task,
    project_id: int,
) -> None:
    payload = task.payload
    target_type = payload.get("target_type")
    stale_result = payload.get("stale_ai_result")
    workspace_id = payload["workspace_id"]
    from backend.api.modules.ai_interaction.public import (
        AIAddDraftHandler,
        AIAddSessionService,
    )

    handler = AIAddDraftHandler(AIAddSessionService())
    if target_type.startswith("edit_"):
        draft = {
            "project_id": project_id,
            "original_object": (
                payload.get("stale_ai_result", {}).get("original_object")
                or payload.get("original_object")
            ),
            "diff": (
                payload.get("stale_ai_result", {}).get("diff")
                or stale_result
            ),
            "target_type": target_type,
        }
        await handler._confirm_edit_draft(draft, session, workspace_id=workspace_id)
        return
    await handler._pre_confirm_validation(
        target_type,
        stale_result,
        project_id,
        session,
    )
    await handler._persist_generated_object(
        target_type,
        stale_result,
        project_id,
        session,
        workspace_id=workspace_id,
    )


async def decide_conflict_task(
    session,
    task,
    project_id: int,
    is_assignee: bool,
    is_admin_or_owner: bool,
    decision: str,
    note: str | None,
    audit_service,
    now,
):
    task.completed_at = now()
    task.decision_note = note
    acted_as_admin = not is_assignee and is_admin_or_owner
    if decision == "approve":
        task.status = "done"
        await _persist_approved_conflict_payload(
            session,
            task,
            project_id,
        )
        action_type = "task_approved"
    elif decision == "reject":
        task.status = "rejected"
        action_type = "task_rejected"
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid decision. Must be approve or reject.",
        )

    await _record_task_decision(
        audit_service,
        session,
        project_id,
        task,
        action_type,
        acted_as_admin,
        note,
    )
    _add_decision_notification(
        session,
        task,
        project_id,
        "conflictTask",
        decision,
    )
    return task
