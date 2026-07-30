from fastapi import HTTPException

from backend.database.model import ConfirmationStatus

from .common import (
    _add_decision_notification,
    _record_task_decision,
)


async def _collect_batch_targets(session, task, snapshot_service):
    mismatches = []
    targets_to_update = []
    for target in task.targets:
        node_kind = target["node_kind"]
        node_id = target["node_id"]
        try:
            snapshot = await snapshot_service.get_snapshot_and_hash(
                session,
                node_kind,
                node_id,
            )
        except Exception:
            mismatches.append(
                {
                    "node_kind": node_kind,
                    "node_id": node_id,
                    "reason": "deleted",
                }
            )
            continue
        if snapshot["hash"] != target["hash"]:
            mismatches.append(
                {
                    "node_kind": node_kind,
                    "node_id": node_id,
                    "reason": "content_changed",
                }
            )
        else:
            targets_to_update.append(
                (snapshot["node"], node_kind, node_id)
            )
    return mismatches, targets_to_update


async def _supersede_changed_batch(
    session,
    task,
    project_id: int,
    note: str | None,
    mismatches: list[dict],
    audit_service,
    now,
) -> None:
    task.status = "superseded"
    task.completed_at = now()
    task.decision_note = (
        note or "批量任务中部分节点内容已变更，自动失效"
    )
    await audit_service.record(
        session=session,
        project_id=project_id,
        action_type="task_superseded",
        summary="task_superseded",
        target_type="task",
        target_id=task.id,
        task_id=task.id,
        payload={"mismatches": mismatches},
    )
    await session.commit()
    raise HTTPException(
        status_code=409,
        detail={
            "message": "task_content_changed",
            "mismatches": mismatches,
        },
    )


async def _record_batch_status_change(
    audit_service,
    session,
    project_id: int,
    task,
    node,
    node_kind: str,
    node_id: int,
    new_status: str,
    reason: str,
    assign_even_if_same: bool,
) -> None:
    old_status = node.confirmation_status
    if assign_even_if_same:
        node.confirmation_status = new_status
    if old_status == new_status:
        return
    if not assign_even_if_same:
        node.confirmation_status = new_status
    await audit_service.record(
        session=session,
        project_id=project_id,
        action_type="update_confirmation_status",
        summary=(
            f"更新 {node_kind} 状态: {old_status} -> "
            f"{new_status} ({reason})"
        ),
        target_type=node_kind,
        target_id=node_id,
        task_id=task.id,
        diff={
            "confirmation_status": {
                "before": old_status,
                "after": new_status,
            }
        },
    )


async def _apply_batch_node_decision(
    audit_service,
    session,
    project_id: int,
    task,
    targets_to_update: list[tuple],
    decision: str,
) -> None:
    if decision == "approve":
        new_status = ConfirmationStatus.CONFIRMED.value
        reason = "批量确认任务通过"
    else:
        new_status = ConfirmationStatus.NEEDS_CONFIRMATION.value
        reason = "批量确认任务驳回"
    for node, node_kind, node_id in targets_to_update:
        await _record_batch_status_change(
            audit_service,
            session,
            project_id,
            task,
            node,
            node_kind,
            node_id,
            new_status,
            reason,
            decision == "approve",
        )


async def decide_batch_task(
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
    mismatches, targets_to_update = await _collect_batch_targets(
        session,
        task,
        snapshot_service,
    )
    if mismatches:
        await _supersede_changed_batch(
            session,
            task,
            project_id,
            note,
            mismatches,
            audit_service,
            now,
        )

    task.completed_at = now()
    task.decision_note = note
    acted_as_admin = not is_assignee and is_admin_or_owner
    if decision == "approve":
        task.status = "done"
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
    await _apply_batch_node_decision(
        audit_service,
        session,
        project_id,
        task,
        targets_to_update,
        decision,
    )
    _add_decision_notification(
        session,
        task,
        project_id,
        "batchTask",
        decision,
    )
    return task
