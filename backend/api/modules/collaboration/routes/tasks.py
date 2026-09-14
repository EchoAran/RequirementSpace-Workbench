import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.project_access import require_project_editor, require_project_member
from backend.api.modules.collaboration.application.confirmation_summary_query import (
    load_confirmation_summary,
)
from backend.api.modules.collaboration.application.task_service import TaskService
from backend.api.modules.collaboration.schemas.tasks import (
    BatchTaskCreateRequest,
    ConfirmationSummaryResponse,
    TaskCreateRequest,
    TaskDecisionRequest,
    TaskResponse,
    UserTaskResponse,
)
from backend.api.modules.optimistic_lock.public import NodeSnapshotService
from backend.api.modules.optimistic_lock.snapshot_service import KIND_TO_MODEL
from backend.database.database import get_session
from backend.database.model import (
    CollaborationTaskModel,
    ProjectMemberModel,
    ProjectModel,
    UserModel,
)

# 1. Project-scoped Tasks Router
router = APIRouter(
    prefix="/api/projects/{project_id}/tasks",
    tags=["project_tasks"],
)
snapshot_service = NodeSnapshotService()

# Project-scoped Summary Router
summary_router = APIRouter(
    prefix="/api/projects/{project_id}",
    tags=["project_confirmation"],
)

# 2. Me Tasks Router (global/user-scoped)
me_router = APIRouter(
    prefix="/api/me/tasks",
    tags=["user_tasks"],
)

task_service = TaskService()

async def _map_task(session, task: CollaborationTaskModel) -> TaskResponse:
    creator_email = task.creator.email if task.creator else None
    assignee_email = task.assignee.email if task.assignee else None

    node_name = None
    content_changed = False

    if task.target_type and task.target_id:
        try:
            model_cls = KIND_TO_MODEL.get(task.target_type.lower())
            if model_cls:
                node_id = int(task.target_id)
                res = await session.execute(sa.select(model_cls).where(model_cls.id == node_id))
                node = res.scalar_one_or_none()
                if node:
                    node_name = getattr(node, "name", None)
                    if task.status == "open":
                        snap_res = await snapshot_service.get_snapshot_and_hash(session, task.target_type, node_id)
                        if snap_res["hash"] != task.content_hash:
                            content_changed = True
                elif task.status == "open":
                    content_changed = True
        except (TypeError, ValueError):
            content_changed = task.status == "open"
    elif task.task_type == "confirm_nodes" and task.targets:
        try:
            if task.status == "open":
                for pt in task.targets:
                    node_kind = pt["node_kind"]
                    node_id = pt["node_id"]
                    stored_hash = pt["hash"]
                    snap_res = await snapshot_service.get_snapshot_and_hash(session, node_kind, node_id)
                    if snap_res["hash"] != stored_hash:
                        content_changed = True
                        break

            node_names = []
            for pt in task.targets[:3]:
                model_cls = KIND_TO_MODEL.get(pt["node_kind"].lower())
                if model_cls:
                    res = await session.execute(sa.select(model_cls).where(model_cls.id == int(pt["node_id"])))
                    node = res.scalar_one_or_none()
                    if node and getattr(node, "name", None):
                        node_names.append(node.name)
            if node_names:
                node_name = ", ".join(node_names)
                if len(task.targets) > 3:
                    node_name += f" +{len(task.targets) - 3}"
        except (TypeError, ValueError):
            content_changed = task.status == "open"

    return TaskResponse(
        id=task.id,
        project_id=task.project_id,
        task_type=task.task_type,
        title=task.title,
        description=task.description,
        target_type=task.target_type,
        target_id=task.target_id,
        targets=task.targets,
        status=task.status,
        priority=task.priority,
        created_by_user_id=task.created_by_user_id,
        assigned_to_user_id=task.assigned_to_user_id,
        content_snapshot=task.content_snapshot,
        content_hash=task.content_hash,
        decision_note=task.decision_note,
        due_at=task.due_at,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
        creator_email=creator_email,
        assignee_email=assignee_email,
        node_name=node_name,
        content_changed=content_changed
    )


@router.post("/confirm-node", response_model=TaskResponse)
async def create_confirm_node_task(
    project_id: str,
    req: TaskCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_editor),
):
    task = await task_service.create_confirm_task(
        session=session,
        project_id=owned_project.id,
        creator_id=current_user.id,
        node_kind=req.node_kind,
        node_id=req.node_id,
        assigned_to_user_id=req.assigned_to_user_id,
        title=req.title,
        description=req.description,
        priority=req.priority,
        due_at=req.due_at
    )
    await session.commit()

    # Reload with relationships
    query = sa.select(CollaborationTaskModel).where(CollaborationTaskModel.id == task.id).options(
        selectinload(CollaborationTaskModel.creator),
        selectinload(CollaborationTaskModel.assignee)
    )
    res = await session.execute(query)
    task_loaded = res.scalar_one()
    return await _map_task(session, task_loaded)


@router.get("", response_model=list[TaskResponse])
async def list_project_tasks(
    project_id: str,
    status: str | None = Query(None),
    task_type: str | None = Query(None),
    assigned_to_user_id: int | None = Query(None),
    created_by_user_id: int | None = Query(None),
    target_type: str | None = Query(None),
    target_id: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_editor),
):
    conditions = [CollaborationTaskModel.project_id == owned_project.id]
    if status:
        conditions.append(CollaborationTaskModel.status == status)
    if task_type:
        conditions.append(CollaborationTaskModel.task_type == task_type)
    if assigned_to_user_id:
        conditions.append(CollaborationTaskModel.assigned_to_user_id == assigned_to_user_id)
    if created_by_user_id:
        conditions.append(CollaborationTaskModel.created_by_user_id == created_by_user_id)
    if target_type:
        conditions.append(CollaborationTaskModel.target_type == target_type)
    if target_id:
        conditions.append(CollaborationTaskModel.target_id == target_id)

    query = sa.select(CollaborationTaskModel).where(sa.and_(*conditions)).options(
        selectinload(CollaborationTaskModel.creator),
        selectinload(CollaborationTaskModel.assignee)
    ).order_by(CollaborationTaskModel.created_at.desc())

    res = await session.execute(query)
    tasks = res.scalars().all()

    mapped_tasks = []
    for t in tasks:
        mapped_tasks.append(await _map_task(session, t))
    return mapped_tasks


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_details(
    project_id: str,
    task_id: int,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_editor),
):
    query = sa.select(CollaborationTaskModel).where(
        sa.and_(
            CollaborationTaskModel.id == task_id,
            CollaborationTaskModel.project_id == owned_project.id
        )
    ).options(
        selectinload(CollaborationTaskModel.creator),
        selectinload(CollaborationTaskModel.assignee)
    )
    res = await session.execute(query)
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return await _map_task(session, task)


@router.patch("/{task_id}/decision", response_model=TaskResponse)
async def decide_task_endpoint(
    project_id: str,
    task_id: int,
    req: TaskDecisionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
):
    # Check if current user is admin or owner of the project
    query = sa.select(ProjectMemberModel).where(
        sa.and_(
            ProjectMemberModel.project_id == owned_project.id,
            ProjectMemberModel.user_id == current_user.id,
            ProjectMemberModel.status == "active"
        )
    )
    res = await session.execute(query)
    mem = res.scalar_one_or_none()
    is_admin_or_owner = mem is not None and mem.role in {"owner", "admin"}

    task = await task_service.decide_task(
        session=session,
        project_id=owned_project.id,
        task_id=task_id,
        user_id=current_user.id,
        is_admin_or_owner=is_admin_or_owner,
        decision=req.decision,
        note=req.decision_note
    )
    await session.commit()

    # Reload task with loaded relations
    query_reload = sa.select(CollaborationTaskModel).where(CollaborationTaskModel.id == task.id).options(
        selectinload(CollaborationTaskModel.creator),
        selectinload(CollaborationTaskModel.assignee)
    )
    res_reload = await session.execute(query_reload)
    task_loaded = res_reload.scalar_one()
    return await _map_task(session, task_loaded)


@router.patch("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task_endpoint(
    project_id: str,
    task_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
):
    query = sa.select(ProjectMemberModel).where(
        sa.and_(
            ProjectMemberModel.project_id == owned_project.id,
            ProjectMemberModel.user_id == current_user.id,
            ProjectMemberModel.status == "active"
        )
    )
    res = await session.execute(query)
    mem = res.scalar_one_or_none()
    is_admin_or_owner = mem is not None and mem.role in {"owner", "admin"}

    task = await task_service.cancel_task(
        session=session,
        project_id=owned_project.id,
        task_id=task_id,
        user_id=current_user.id,
        is_admin_or_owner=is_admin_or_owner
    )
    await session.commit()

    # Reload
    query_reload = sa.select(CollaborationTaskModel).where(CollaborationTaskModel.id == task.id).options(
        selectinload(CollaborationTaskModel.creator),
        selectinload(CollaborationTaskModel.assignee)
    )
    res_reload = await session.execute(query_reload)
    task_loaded = res_reload.scalar_one()
    return await _map_task(session, task_loaded)


@summary_router.get("/confirmation-summary", response_model=ConfirmationSummaryResponse)
async def get_confirmation_summary(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
):
    summary = await load_confirmation_summary(
        session,
        project_id=owned_project.id,
        user_id=current_user.id,
    )
    return ConfirmationSummaryResponse(**summary)


@router.post("/confirm-nodes", response_model=TaskResponse)
async def create_confirm_nodes_task(
    project_id: str,
    req: BatchTaskCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
):
    task = await task_service.create_batch_confirm_task(
        session=session,
        project_id=owned_project.id,
        creator_id=current_user.id,
        targets=[t.model_dump() for t in req.targets],
        assigned_to_user_id=req.assigned_to_user_id,
        title=req.title,
        description=req.description,
        priority=req.priority,
        due_at=req.due_at
    )
    await session.commit()

    query = sa.select(CollaborationTaskModel).where(CollaborationTaskModel.id == task.id).options(
        selectinload(CollaborationTaskModel.creator),
        selectinload(CollaborationTaskModel.assignee)
    )
    res = await session.execute(query)
    task_loaded = res.scalar_one()
    return await _map_task(session, task_loaded)


def _build_my_task_conditions(
    *,
    user_id: int,
    role: str | None,
    status: str | None,
    task_type: str | None,
) -> list:
    if role == "creator":
        conditions = [
            CollaborationTaskModel.created_by_user_id == user_id
        ]
    elif role == "both":
        conditions = [
            sa.or_(
                CollaborationTaskModel.assigned_to_user_id == user_id,
                CollaborationTaskModel.created_by_user_id == user_id,
            )
        ]
    else:
        conditions = [
            CollaborationTaskModel.assigned_to_user_id == user_id
        ]
    if status:
        conditions.append(CollaborationTaskModel.status.in_(status.split(",")))
    if task_type:
        conditions.append(CollaborationTaskModel.task_type == task_type)
    return conditions


async def _resolve_task_project_id(session, project_public_id: str) -> int | None:
    statement = sa.select(ProjectModel).where(
        ProjectModel.public_id == project_public_id
    )
    result = await session.execute(statement)
    project = result.scalar_one_or_none()
    return project.id if project else None


def _build_my_tasks_query(
    conditions: list,
    *,
    offset: int | None,
    limit: int | None,
):
    query = (
        sa.select(CollaborationTaskModel)
        .where(sa.and_(*conditions))
        .options(
            selectinload(CollaborationTaskModel.creator),
            selectinload(CollaborationTaskModel.assignee),
        )
        .order_by(CollaborationTaskModel.created_at.desc())
    )
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return query


async def _load_task_projects(session, tasks: list) -> dict:
    project_ids = list({task.project_id for task in tasks})
    if not project_ids:
        return {}
    statement = sa.select(ProjectModel).where(ProjectModel.id.in_(project_ids))
    result = await session.execute(statement)
    return {project.id: project for project in result.scalars().all()}


async def _build_user_task_response(
    session,
    task,
    projects_map: dict,
) -> dict:
    mapped_task = await _map_task(session, task)
    project = projects_map.get(task.project_id)
    node_kind = None
    node_id = None
    if task.target_type and task.target_id:
        node_kind = task.target_type
        try:
            node_id = int(task.target_id)
        except ValueError:
            pass
    elif task.task_type == "confirm_nodes":
        node_kind = "batch"

    return {
        "task": mapped_task,
        "project_summary": {
            "project_id": project.public_id if project else "",
            "project_name": project.name if project else "",
        },
        "target_summary": {
            "node_kind": node_kind,
            "node_id": node_id,
            "node_name": mapped_task.node_name,
        },
        "creator_summary": {
            "user_id": task.created_by_user_id,
            "email": task.creator.email if task.creator else "",
        },
        "assignee_summary": {
            "user_id": task.assigned_to_user_id,
            "email": task.assignee.email if task.assignee else "",
        },
        "content_changed": mapped_task.content_changed,
    }


@me_router.get("", response_model=list[UserTaskResponse])
async def list_my_tasks(
    role: str | None = Query(None, description="Filter by role: assignee, creator, or both. Default is assignee."),
    status: str | None = Query(None, description="Comma-separated statuses"),
    task_type: str | None = Query(None),
    project_id: str | None = Query(None),
    limit: int | None = Query(None),
    offset: int | None = Query(None),
    session: AsyncSession = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
):
    conditions = _build_my_task_conditions(
        user_id=current_user.id,
        role=role,
        status=status,
        task_type=task_type,
    )
    if project_id:
        project_id_internal = await _resolve_task_project_id(session, project_id)
        if project_id_internal is None:
            return []
        conditions.append(
            CollaborationTaskModel.project_id == project_id_internal
        )
    query = _build_my_tasks_query(
        conditions,
        offset=offset,
        limit=limit,
    )
    res = await session.execute(query)
    tasks = res.scalars().all()
    projects_map = await _load_task_projects(session, tasks)
    return [
        await _build_user_task_response(session, task, projects_map)
        for task in tasks
    ]
