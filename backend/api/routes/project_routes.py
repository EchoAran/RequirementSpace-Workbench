from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.project_schema import (
    ProjectListItemResponse,
    ProjectDetailResponse,
    ProjectDeleteResponse,
    ProjectUpdateRequest,
    ProjectUpdateResponse,
    ScopeImpactPreviewRequest,
    ScopeImpactPreviewResponse,
)
from backend.api.services.service_registry import project_service
from backend.database.database import get_session

router = APIRouter(
    prefix="/api/projects",
    tags=["projects"],
)


@router.get(
    "",
    response_model=list[ProjectListItemResponse],
)
async def list_projects(
    session: AsyncSession = Depends(get_session),
):
    return await project_service.list_projects(session=session)


@router.get(
    "/{project_id}",
    response_model=ProjectDetailResponse,
)
async def get_project_detail(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.get_project_detail(
            project_id=project_id,
            session=session,
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        raise


@router.delete(
    "/{project_id}",
    response_model=ProjectDeleteResponse,
)
async def delete_project(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.delete_project(
            project_id=project_id,
            session=session,
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        raise

@router.put(
    "/{project_id}",
    response_model=ProjectUpdateResponse,
)
async def update_project(
    project_id: int,
    request: ProjectUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.update_project(
            project_id=project_id,
            name=request.name,
            description=request.description,
            session=session,
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        raise

@router.get(
    "/{project_id}/export/json",
    response_model=ProjectDetailResponse,
)
async def export_project_json(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.get_project_detail(
            project_id=project_id,
            session=session,
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        raise

@router.get(
    "/{project_id}/export/markdown",
    response_class=PlainTextResponse,
)
async def export_project_markdown(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.export_project_markdown(
            project_id=project_id,
            session=session,
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        raise

@router.post(
    "/{project_id}/impact-preview",
    response_model=ScopeImpactPreviewResponse,
)
async def preview_scope_impact(
    project_id: int,
    request: ScopeImpactPreviewRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.preview_scope_impact(
            project_id=project_id,
            feature_id=request.feature_id,
            next_status=request.next_status,
            session=session,
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        if str(error) == "feature_not_found":
            raise HTTPException(
                status_code=404,
                detail="feature_not_found",
            )
        raise
