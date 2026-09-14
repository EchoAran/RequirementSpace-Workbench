import sqlalchemy as sa
from fastapi import HTTPException

from backend.database.model import (
    BusinessObjectModel,
    ChoiceModel,
    CollaborationTaskModel,
    ConfirmationStatus,
    FeatureModel,
    FlowModel,
    NotificationModel,
    ScenarioModel,
)


def validate_task_creator(member, detail: str) -> None:
    if not member or member.role not in {
        "owner",
        "admin",
        "editor",
    }:
        raise HTTPException(status_code=403, detail=detail)


def validate_task_assignee(member) -> None:
    if not member:
        raise HTTPException(
            status_code=400,
            detail="Assignee must be an active project member.",
        )
    if member.role == "viewer":
        raise HTTPException(
            status_code=400,
            detail="Cannot assign tasks to a viewer.",
        )


async def _related_project_id(
    session,
    model,
    related_id: int,
) -> int | None:
    result = await session.execute(
        sa.select(model).where(model.id == related_id)
    )
    related = result.scalar_one_or_none()
    return related.project_id if related else None


async def get_node_project_id(
    session,
    node_kind: str,
    node,
) -> int | None:
    if isinstance(node, ChoiceModel):
        group = node.choice_group
        if group is None or group.generation_type != "flow_refinement":
            return None
        return group.project_id
    if hasattr(node, "project_id"):
        return node.project_id
    relation_specs = {
        "scope": (FeatureModel, "feature_id"),
        "acceptance_criterion": (
            ScenarioModel,
            "scenario_id",
        ),
        "business_object_attribute": (
            BusinessObjectModel,
            "business_object_id",
        ),
        "flow_step": (FlowModel, "flow_id"),
    }
    spec = relation_specs.get(node_kind)
    if spec is None:
        return None
    model, id_attribute = spec
    return await _related_project_id(
        session,
        model,
        getattr(node, id_attribute),
    )


async def load_validated_target(
    session,
    snapshot_service,
    project_id: int,
    node_kind: str,
    node_id: int,
):
    snapshot_result = await snapshot_service.get_snapshot_and_hash(
        session,
        node_kind,
        node_id,
    )
    node = snapshot_result["node"]
    node_project_id = await get_node_project_id(
        session,
        node_kind,
        node,
    )
    if node_project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Target node {node_kind}:{node_id} "
                "not found in this project."
            ),
        )
    return snapshot_result, node


def mark_needs_confirmation(node) -> str:
    if isinstance(node, ChoiceModel):
        return node.status
    old_status = node.confirmation_status
    if old_status != ConfirmationStatus.NEEDS_CONFIRMATION.value:
        node.confirmation_status = (
            ConfirmationStatus.NEEDS_CONFIRMATION.value
        )
    return old_status


def add_assignment_notification(
    session,
    *,
    assigned_to_user_id: int,
    project_id: int,
    task_id: int,
    is_batch: bool,
) -> None:
    task_kind = "batch" if is_batch else "single"
    session.add(
        NotificationModel(
            recipient_user_id=assigned_to_user_id,
            project_id=project_id,
            task_id=task_id,
            event_type="task_assigned",
            title=(
                "collaboration.notifications."
                f"{task_kind}TaskAssigned.title"
            ),
            body=(
                "collaboration.notifications."
                f"{task_kind}TaskAssigned.body"
            ),
        )
    )


async def supersede_open_node_tasks(
    session,
    audit_service,
    *,
    project_id: int,
    node_kind: str,
    node_id: int,
    utc_now,
) -> None:
    result = await session.execute(
        sa.select(CollaborationTaskModel).where(
            sa.and_(
                CollaborationTaskModel.project_id == project_id,
                CollaborationTaskModel.target_type == node_kind,
                CollaborationTaskModel.target_id == str(node_id),
                CollaborationTaskModel.status == "open",
            )
        )
    )
    for old_task in result.scalars().all():
        old_task.status = "superseded"
        old_task.completed_at = utc_now()
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="task_superseded",
            summary="task_superseded",
            target_type="task",
            target_id=old_task.id,
            task_id=old_task.id,
            payload={"superseded_by_task_id": "new_task"},
        )


def build_single_confirmation_task(
    *,
    project_id: int,
    creator_id: int,
    assigned_to_user_id: int,
    node_kind: str,
    node_id: int,
    title: str,
    description: str | None,
    priority: str,
    due_at,
    snapshot_result: dict,
) -> CollaborationTaskModel:
    return CollaborationTaskModel(
        project_id=project_id,
        task_type="confirm_node",
        title=title,
        description=description,
        target_type=node_kind,
        target_id=str(node_id),
        status="open",
        priority=priority,
        created_by_user_id=creator_id,
        assigned_to_user_id=assigned_to_user_id,
        content_snapshot=snapshot_result["snapshot"],
        content_hash=snapshot_result["hash"],
        due_at=due_at,
    )


async def record_single_task_audits(
    session,
    audit_service,
    *,
    task,
    project_id: int,
    assigned_to_user_id: int,
    node_kind: str,
    node_id: int,
    old_status: str,
) -> None:
    await audit_service.record(
        session=session,
        project_id=project_id,
        action_type="task_created",
        summary="task_created",
        target_type="task",
        target_id=task.id,
        task_id=task.id,
        payload={
            "assigned_to_user_id": assigned_to_user_id,
            "node_kind": node_kind,
            "node_id": node_id,
        },
    )
    if old_status == ConfirmationStatus.NEEDS_CONFIRMATION.value:
        return
    await audit_service.record(
        session=session,
        project_id=project_id,
        action_type="update_confirmation_status",
        summary=(
            f"更新 {node_kind} 状态: {old_status} "
            "-> needs_confirmation (发起确认任务)"
        ),
        target_type=node_kind,
        target_id=node_id,
        task_id=task.id,
        diff={
            "confirmation_status": {
                "before": old_status,
                "after": (
                    ConfirmationStatus.NEEDS_CONFIRMATION.value
                ),
            }
        },
    )


async def process_batch_targets(
    session,
    snapshot_service,
    project_id: int,
    targets: list[dict],
) -> list[dict]:
    processed_targets = []
    for target in targets:
        node_kind = target["node_kind"]
        node_id = target["node_id"]
        snapshot_result, node = await load_validated_target(
            session,
            snapshot_service,
            project_id,
            node_kind,
            node_id,
        )
        processed_targets.append(
            {
                "node_kind": node_kind,
                "node_id": node_id,
                "node_name": (
                    getattr(node, "name", None)
                    or snapshot_result["snapshot"].get("name")
                ),
                "snapshot": snapshot_result["snapshot"],
                "hash": snapshot_result["hash"],
                "old_status": mark_needs_confirmation(node),
            }
        )
    return processed_targets


def build_batch_confirmation_task(
    *,
    project_id: int,
    creator_id: int,
    assigned_to_user_id: int,
    title: str,
    description: str | None,
    priority: str,
    due_at,
    processed_targets: list[dict],
) -> CollaborationTaskModel:
    return CollaborationTaskModel(
        project_id=project_id,
        task_type="confirm_nodes",
        title=title,
        description=description,
        target_type=None,
        target_id=None,
        targets=processed_targets,
        status="open",
        priority=priority,
        created_by_user_id=creator_id,
        assigned_to_user_id=assigned_to_user_id,
        due_at=due_at,
    )


async def record_batch_task_audits(
    session,
    audit_service,
    *,
    task,
    project_id: int,
    processed_targets: list[dict],
) -> None:
    await audit_service.record(
        session=session,
        project_id=project_id,
        action_type="task_created",
        summary="task_created",
        target_type="task",
        target_id=task.id,
        task_id=task.id,
    )
    for target in processed_targets:
        if (
            target["old_status"]
            == ConfirmationStatus.NEEDS_CONFIRMATION.value
        ):
            continue
        await audit_service.record(
            session=session,
            project_id=project_id,
            action_type="update_confirmation_status",
            summary=(
                f"更新 {target['node_kind']} 状态: "
                f"{target['old_status']} -> needs_confirmation "
                "(确认任务指派)"
            ),
            target_type=target["node_kind"],
            target_id=target["node_id"],
            task_id=task.id,
            diff={
                "confirmation_status": {
                    "before": target["old_status"],
                    "after": (
                        ConfirmationStatus.NEEDS_CONFIRMATION.value
                    ),
                }
            },
        )
