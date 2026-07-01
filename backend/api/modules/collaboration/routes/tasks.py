import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from backend.database.database import get_session
from backend.database.model import (
    CollaborationTaskModel,
    ProjectMemberModel,
    UserModel,
    ProjectModel,
)
from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.project_access import require_project_member, require_project_role
from backend.api.modules.collaboration.application.task_service import TaskService, snapshot_service, KIND_TO_MODEL
from backend.api.modules.collaboration.schemas.tasks import (
    TaskCreateRequest,
    BatchTaskCreateRequest,
    TaskDecisionRequest,
    TaskResponse,
    ConfirmationSummaryResponse,
    UserTaskResponse,
)

# 1. Project-scoped Tasks Router
router = APIRouter(
    prefix="/api/projects/{project_id}/tasks",
    tags=["project_tasks"],
)

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
        except Exception:
            pass
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
                    node_name += " 等"
        except Exception:
            pass

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
    owned_project: ProjectModel = Depends(require_project_role("editor")),
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
    owned_project: ProjectModel = Depends(require_project_role("editor")),
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
    owned_project: ProjectModel = Depends(require_project_role("editor")),
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
    pid = owned_project.id
    
    from backend.database.model import (
        ActorModel, FeatureModel, ScenarioModel,
        ScenarioAcceptanceCriterionModel, BusinessObjectModel,
        BusinessObjectAttributeModel, FlowModel, FlowStepModel, ScopeModel,
        ConfirmationStatus
    )
    ai_assumption_count = 0
    
    async def count_ai_assumptions(model_cls, is_subnode=False, parent_relation=None):
        if not is_subnode:
            stmt = sa.select(sa.func.count(model_cls.id)).where(
                sa.and_(
                    model_cls.project_id == pid,
                    model_cls.confirmation_status == ConfirmationStatus.AI_ASSUMPTION.value
                )
            )
            res = await session.execute(stmt)
            return res.scalar() or 0
        else:
            stmt = sa.select(sa.func.count(model_cls.id)).join(parent_relation).where(
                sa.and_(
                    parent_relation.property.mapper.class_.project_id == pid,
                    model_cls.confirmation_status == ConfirmationStatus.AI_ASSUMPTION.value
                )
            )
            res = await session.execute(stmt)
            return res.scalar() or 0

    ai_assumption_count += await count_ai_assumptions(ActorModel)
    ai_assumption_count += await count_ai_assumptions(FeatureModel)
    ai_assumption_count += await count_ai_assumptions(ScenarioModel)
    ai_assumption_count += await count_ai_assumptions(ScenarioAcceptanceCriterionModel, is_subnode=True, parent_relation=ScenarioAcceptanceCriterionModel.scenario)
    ai_assumption_count += await count_ai_assumptions(BusinessObjectModel)
    ai_assumption_count += await count_ai_assumptions(BusinessObjectAttributeModel, is_subnode=True, parent_relation=BusinessObjectAttributeModel.business_object)
    ai_assumption_count += await count_ai_assumptions(FlowModel)
    ai_assumption_count += await count_ai_assumptions(FlowStepModel, is_subnode=True, parent_relation=FlowStepModel.flow)
    
    scope_stmt = sa.select(sa.func.count(ScopeModel.id)).join(ScopeModel.feature).where(
        sa.and_(
            FeatureModel.project_id == pid,
            ScopeModel.confirmation_status == ConfirmationStatus.AI_ASSUMPTION.value
        )
    )
    scope_res = await session.execute(scope_stmt)
    ai_assumption_count += scope_res.scalar() or 0

    stmt_open = sa.select(sa.func.count(CollaborationTaskModel.id)).where(
        sa.and_(
            CollaborationTaskModel.project_id == pid,
            CollaborationTaskModel.status == "open"
        )
    )
    res_open = await session.execute(stmt_open)
    open_task_count = res_open.scalar() or 0

    stmt_me = sa.select(sa.func.count(CollaborationTaskModel.id)).where(
        sa.and_(
            CollaborationTaskModel.project_id == pid,
            CollaborationTaskModel.status == "open",
            CollaborationTaskModel.assigned_to_user_id == current_user.id
        )
    )
    res_me = await session.execute(stmt_me)
    assigned_to_me_count = res_me.scalar() or 0

    stmt_creator = sa.select(sa.func.count(CollaborationTaskModel.id)).where(
        sa.and_(
            CollaborationTaskModel.project_id == pid,
            CollaborationTaskModel.status == "open",
            CollaborationTaskModel.created_by_user_id == current_user.id
        )
    )
    res_creator = await session.execute(stmt_creator)
    created_by_me_count = res_creator.scalar() or 0

    stmt_rej = sa.select(sa.func.count(CollaborationTaskModel.id)).where(
        sa.and_(
            CollaborationTaskModel.project_id == pid,
            CollaborationTaskModel.status == "rejected",
            CollaborationTaskModel.created_by_user_id == current_user.id
        )
    )
    res_rej = await session.execute(stmt_rej)
    rejected_count = res_rej.scalar() or 0

    stmt_kind = sa.select(
        CollaborationTaskModel.target_type, sa.func.count(CollaborationTaskModel.id)
    ).where(
        sa.and_(
            CollaborationTaskModel.project_id == pid,
            CollaborationTaskModel.status == "open"
        )
    ).group_by(CollaborationTaskModel.target_type)
    res_kind = await session.execute(stmt_kind)
    by_node_kind = {row[0]: row[1] for row in res_kind.all() if row[0] is not None}

    stmt_batch = sa.select(CollaborationTaskModel.targets).where(
        sa.and_(
            CollaborationTaskModel.project_id == pid,
            CollaborationTaskModel.status == "open",
            CollaborationTaskModel.task_type == "confirm_nodes"
        )
    )
    res_batch = await session.execute(stmt_batch)
    for row in res_batch.scalars().all():
        if row:
            for pt in row:
                kind = pt.get("node_kind")
                if kind:
                    by_node_kind[kind] = by_node_kind.get(kind, 0) + 1

    stmt_assignee = sa.select(
        UserModel.email, sa.func.count(CollaborationTaskModel.id)
    ).join(
        CollaborationTaskModel, CollaborationTaskModel.assigned_to_user_id == UserModel.id
    ).where(
        sa.and_(
            CollaborationTaskModel.project_id == pid,
            CollaborationTaskModel.status == "open"
        )
    ).group_by(UserModel.email)
    res_assignee = await session.execute(stmt_assignee)
    by_assignee = {row[0]: row[1] for row in res_assignee.all()}

    return ConfirmationSummaryResponse(
        ai_assumption_count=ai_assumption_count,
        open_task_count=open_task_count,
        assigned_to_me_count=assigned_to_me_count,
        created_by_me_count=created_by_me_count,
        rejected_count=rejected_count,
        by_node_kind=by_node_kind,
        by_assignee=by_assignee,
    )


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
    conditions = []
    if role == "creator":
        conditions.append(CollaborationTaskModel.created_by_user_id == current_user.id)
    elif role == "both":
        conditions.append(
            sa.or_(
                CollaborationTaskModel.assigned_to_user_id == current_user.id,
                CollaborationTaskModel.created_by_user_id == current_user.id
            )
        )
    else:
        conditions.append(CollaborationTaskModel.assigned_to_user_id == current_user.id)
        
    if status:
        statuses = status.split(",")
        conditions.append(CollaborationTaskModel.status.in_(statuses))
    if task_type:
        conditions.append(CollaborationTaskModel.task_type == task_type)
    
    if project_id:
        proj_query = sa.select(ProjectModel).where(ProjectModel.public_id == project_id)
        res_proj = await session.execute(proj_query)
        proj = res_proj.scalar_one_or_none()
        if proj:
            conditions.append(CollaborationTaskModel.project_id == proj.id)
        else:
            return []

    query = sa.select(CollaborationTaskModel).where(sa.and_(*conditions)).options(
        selectinload(CollaborationTaskModel.creator),
        selectinload(CollaborationTaskModel.assignee)
    ).order_by(CollaborationTaskModel.created_at.desc())

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    res = await session.execute(query)
    tasks = res.scalars().all()
    
    mapped_tasks = []
    project_ids = list(set([t.project_id for t in tasks]))
    projects_map = {}
    if project_ids:
        proj_stmt = sa.select(ProjectModel).where(ProjectModel.id.in_(project_ids))
        proj_res = await session.execute(proj_stmt)
        projects_map = {p.id: p for p in proj_res.scalars().all()}

    for t in tasks:
        mapped_t = await _map_task(session, t)
        proj = projects_map.get(t.project_id)
        
        proj_summary = {
            "project_id": proj.public_id if proj else "",
            "project_name": proj.name if proj else ""
        }
        
        node_kind = None
        node_id = None
        node_name = mapped_t.node_name
        
        if t.target_type and t.target_id:
            node_kind = t.target_type
            try:
                node_id = int(t.target_id)
            except ValueError:
                pass
        elif t.task_type == "confirm_nodes":
            node_kind = "batch"

        target_summary = {
            "node_kind": node_kind,
            "node_id": node_id,
            "node_name": node_name
        }
        
        creator_summary = {
            "user_id": t.created_by_user_id,
            "email": t.creator.email if t.creator else ""
        }
        assignee_summary = {
            "user_id": t.assigned_to_user_id,
            "email": t.assignee.email if t.assignee else ""
        }
        
        mapped_tasks.append({
            "task": mapped_t,
            "project_summary": proj_summary,
            "target_summary": target_summary,
            "creator_summary": creator_summary,
            "assignee_summary": assignee_summary,
            "content_changed": mapped_t.content_changed
        })
        
    return mapped_tasks
