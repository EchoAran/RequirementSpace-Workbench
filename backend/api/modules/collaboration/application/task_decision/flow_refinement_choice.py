from fastapi import HTTPException

from backend.api.modules.decision_workflow.public import ChoiceService

from .common import _add_decision_notification, _record_task_decision
from .single import _supersede_changed_single_task


async def decide_flow_refinement_choice_task(
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
    if snapshot["hash"] != task.content_hash:
        await _supersede_changed_single_task(
            session,
            task,
            project_id,
            note,
            audit_service,
            now,
        )

    choice_service = ChoiceService()
    if decision == "approve":
        payload = snapshot["snapshot"].get("payload") or {}
        expected_version = (
            payload.get("expected_workspace_version")
            or payload.get("context_hash")
        )
        acceptance = await choice_service.accept_choice(
            project_id,
            int(task.target_id),
            session,
            workspace_id=snapshot["snapshot"]["workspace_id"],
            expected_workspace_version=expected_version,
        )
        if acceptance.is_stale:
            await _supersede_changed_single_task(
                session,
                task,
                project_id,
                note,
                audit_service,
                now,
            )
        task.status = "done"
        action_type = "task_approved"
    elif decision == "reject":
        await choice_service.reject_choice(
            project_id,
            int(task.target_id),
            session,
        )
        task.status = "rejected"
        action_type = "task_rejected"
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid decision. Must be approve or reject.",
        )

    task.completed_at = now()
    task.decision_note = note
    await _record_task_decision(
        audit_service,
        session,
        project_id,
        task,
        action_type,
        not is_assignee and is_admin_or_owner,
        note,
    )
    _add_decision_notification(
        session,
        task,
        project_id,
        "singleTask",
        decision,
    )
    return task
