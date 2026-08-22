from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.actor_context import get_actor_context
from backend.api.dependencies.llm import get_llm_context
from backend.api.dependencies.ownership import require_owned_project
from backend.api.modules.project_lifecycle.application.requirements_service import (
    ProjectRequirementsService,
)
from backend.api.modules.project_lifecycle.schemas.audit import (
    AuditLogResponse,
    UserRequirementsRefineRequest,
    UserRequirementsResponse,
    UserRequirementsUpdateRequest,
)
from backend.core.actor_context import ActorContext
from backend.database.database import get_session
from backend.database.model import ProjectModel

router = APIRouter(
    prefix="/api/projects/{project_id}",
    tags=["project_requirements"],
)

_service = ProjectRequirementsService()

PROJECT_REQUIREMENTS_ERRORS = {
    "project_not_found",
    "llm_refinement_failed",
}


from fastapi import Query


@router.get(
    "/audit-logs",
    response_model=list[AuditLogResponse],
)
async def list_audit_logs(
    project_id: str,
    actor_user_id: int | None = Query(None),
    actor_type: str | None = Query(None),
    action_type: str | None = Query(None),
    target_type: str | None = Query(None),
    task_id: int | None = Query(None),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    return await _service.list_audit_logs(
        project_id=owned_project.id,
        session=session,
        actor_user_id=actor_user_id,
        actor_type=actor_type,
        action_type=action_type,
        target_type=target_type,
        task_id=task_id,
    )


@router.put(
    "/user-requirements",
    response_model=UserRequirementsResponse,
)
async def update_user_requirements(
    project_id: str,
    request: UserRequirementsUpdateRequest,
    branch: str | None = Query(None),
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    from backend.api.modules.version_control.public import map_branch_error, resolve_branch_context
    try:
        _branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, actor.user_id)
        )
    except (ValueError, PermissionError) as err:
        raise map_branch_error(err)

    if perms and not perms.get("can_write", True):
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    try:
        return await _service.update_user_requirements(
            project_id=owned_project.id,
            user_requirements=request.user_requirements,
            actor=actor,
            session=session,
            workspace_id=ws_obj.id if ws_obj else None,
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        if str(error) in PROJECT_REQUIREMENTS_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.post(
    "/user-requirements/refine",
    response_model=UserRequirementsResponse,
)
async def refine_user_requirements(
    project_id: str,
    request: UserRequirementsRefineRequest,
    branch: str | None = Query(None),
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    from backend.api.modules.version_control.public import map_branch_error, resolve_branch_context
    try:
        _branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, actor.user_id)
        )
    except (ValueError, PermissionError) as err:
        raise map_branch_error(err)

    if perms and not perms.get("can_write", True):
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    try:
        # Convert user actor context to AI actor type for logging AI refinements
        ai_actor = ActorContext.ai(user_id=actor.user_id, request_id=actor.request_id)
        return await _service.refine_user_requirements(
            project_id=owned_project.id,
            user_feedback=request.user_feedback,
            actor=ai_actor,
            session=session,
            workspace_id=ws_obj.id if ws_obj else None,
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        if str(error) in PROJECT_REQUIREMENTS_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise
