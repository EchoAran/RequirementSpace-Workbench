from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.audit_schema import (
    AuditLogResponse,
    UserRequirementsUpdateRequest,
    UserRequirementsRefineRequest,
    UserRequirementsResponse,
)
from backend.api.services.project_requirements_service import (
    ProjectRequirementsService,
)
from backend.database.database import get_session


router = APIRouter(
    prefix="/api/projects",
    tags=["project_requirements"],
)

_service = ProjectRequirementsService()

PROJECT_REQUIREMENTS_ERRORS = {
    "project_not_found",
    "llm_refinement_failed",
}


@router.get(
    "/{project_id}/audit-logs",
    response_model=list[AuditLogResponse],
)
async def list_audit_logs(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    return await _service.list_audit_logs(
        project_id=project_id,
        session=session,
    )


@router.put(
    "/{project_id}/user-requirements",
    response_model=UserRequirementsResponse,
)
async def update_user_requirements(
    project_id: int,
    request: UserRequirementsUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await _service.update_user_requirements(
            project_id=project_id,
            user_requirements=request.user_requirements,
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
    "/{project_id}/user-requirements/refine",
    response_model=UserRequirementsResponse,
)
async def refine_user_requirements(
    project_id: int,
    request: UserRequirementsRefineRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await _service.refine_user_requirements(
            project_id=project_id,
            user_feedback=request.user_feedback,
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
