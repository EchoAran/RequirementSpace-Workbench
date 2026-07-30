import sqlalchemy as sa

from backend.core.actor_context import get_current_actor
from backend.database.model import (
    AuditLogModel,
    CollaborationTaskModel,
    NotificationModel,
)


def _actor_audit_fields() -> tuple[int | None, str, str | None]:
    actor_context = get_current_actor()
    if actor_context is None:
        return None, "system", None
    return (
        actor_context.user_id,
        actor_context.actor_type,
        actor_context.request_id,
    )


def _add_superseded_records(
    session,
    task,
    node_kind: str,
    node_id: int,
    *,
    current_hash: str | None = None,
    is_batch: bool = False,
) -> None:
    actor_user_id, actor_type, request_id = _actor_audit_fields()
    if is_batch:
        summary = f"Batch task {task.id} superseded by node update"
        payload = {
            "task_id": task.id,
            "node_kind": node_kind,
            "node_id": node_id,
            "batch": True,
        }
        title = (
            "collaboration.notifications."
            "batchTaskSuperseded.title"
        )
        body = (
            "collaboration.notifications."
            "batchTaskSuperseded.body"
        )
    else:
        summary = f"Task {task.id} superseded by node update"
        payload = {
            "task_id": task.id,
            "node_kind": node_kind,
            "node_id": node_id,
            "old_hash": task.content_hash,
            "new_hash": current_hash,
        }
        title = (
            "collaboration.notifications."
            "singleTaskSuperseded.title"
        )
        body = (
            "collaboration.notifications."
            "singleTaskSuperseded.body"
        )

    task.status = "superseded"
    session.add(
        AuditLogModel(
            project_id=task.project_id,
            action_type="task_superseded_by_node_update",
            summary=summary,
            target_type="task",
            target_id=str(task.id),
            payload=payload,
            actor_user_id=actor_user_id,
            actor_type=actor_type,
            request_id=request_id,
            task_id=task.id,
        )
    )
    session.add(
        NotificationModel(
            recipient_user_id=task.assigned_to_user_id,
            project_id=task.project_id,
            task_id=task.id,
            event_type="task_superseded",
            title=title,
            body=body,
        )
    )


async def _load_open_node_tasks(
    session,
    node_kind: str,
    node_id: int,
):
    result = await session.execute(
        sa.select(CollaborationTaskModel).where(
            sa.and_(
                CollaborationTaskModel.target_type
                == node_kind.lower(),
                CollaborationTaskModel.target_id == str(node_id),
                CollaborationTaskModel.status == "open",
            )
        )
    )
    return result.scalars().all()


async def _load_open_batch_tasks(session):
    result = await session.execute(
        sa.select(CollaborationTaskModel).where(
            sa.and_(
                CollaborationTaskModel.task_type == "confirm_nodes",
                CollaborationTaskModel.status == "open",
            )
        )
    )
    return result.scalars().all()


def _batch_task_has_stale_target(
    task,
    node_kind: str,
    node_id: int,
    current_hash: str,
) -> bool:
    mismatch_found = False
    if task.targets:
        for target in task.targets:
            if (
                target.get("node_kind") == node_kind.lower()
                and str(target.get("node_id")) == str(node_id)
                and target.get("hash") != current_hash
            ):
                mismatch_found = True
    return mismatch_found


async def supersede_tasks_for_node_update(
    session,
    node_kind: str,
    node,
    get_snapshot_and_hash,
) -> None:
    open_tasks = await _load_open_node_tasks(
        session,
        node_kind,
        node.id,
    )
    snapshot_result = await get_snapshot_and_hash(
        session,
        node_kind,
        node.id,
    )
    current_hash = snapshot_result["hash"]
    for task in open_tasks:
        if task.content_hash != current_hash:
            _add_superseded_records(
                session,
                task,
                node_kind,
                node.id,
                current_hash=current_hash,
            )

    open_batch_tasks = await _load_open_batch_tasks(session)
    for task in open_batch_tasks:
        if _batch_task_has_stale_target(
            task,
            node_kind,
            node.id,
            current_hash,
        ):
            _add_superseded_records(
                session,
                task,
                node_kind,
                node.id,
                is_batch=True,
            )
