from backend.api.dependencies.ownership import require_owned_project
from backend.database.model import ProjectModel
from fastapi import APIRouter, Depends, HTTPException
from backend.api.dependencies.actor_context import get_actor_context
from backend.core.actor_context import ActorContext
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.modules.project_lifecycle.schemas.audit import (
    AuditLogResponse,
    UserRequirementsUpdateRequest,
    UserRequirementsRefineRequest,
    UserRequirementsResponse,
)
from backend.api.modules.project_lifecycle.application.requirements_service import (
    ProjectRequirementsService,
)
from backend.database.database import get_session
from backend.api.dependencies.llm import get_llm_context


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
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    try:
        return await _service.update_user_requirements(
            project_id=owned_project.id,
            user_requirements=request.user_requirements,
            actor=actor,
            session=session,
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
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    try:
        # Convert user actor context to AI actor type for logging AI refinements
        ai_actor = ActorContext.ai(user_id=actor.user_id, request_id=actor.request_id)
        return await _service.refine_user_requirements(
            project_id=owned_project.id,
            user_feedback=request.user_feedback,
            actor=ai_actor,
            session=session,
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
