from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_owned_project
from backend.api.dependencies.project_access import require_project_member, require_project_role
from backend.database.model import UserModel, ProjectModel
from backend.api.modules.project_lifecycle.schemas.project import (
    ProjectListItemResponse,
    ProjectDetailResponse,
    ProjectDeleteResponse,
    PerceptionSlotDeleteResponse,
    ProjectUpdateRequest,
    ProjectUpdateResponse,
    ScopeImpactPreviewRequest,
    ScopeImpactPreviewResponse,
    UnlockStageRequest,
    StageTransitionRequest,
    StageTransitionResponse,
    StageProgressResponse,
)
from backend.api.modules.project_lifecycle.ports import get_project_service

class LazyProjectServiceProxy:
    def __getattr__(self, name):
        return getattr(get_project_service(), name)

project_service = LazyProjectServiceProxy()
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
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await project_service.list_projects(user_id=user.id, session=session)


@router.get(
    "/{project_id}",
    response_model=ProjectDetailResponse,
)
async def get_project_detail(
    project_id: str,
    request: Request,
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    try:
        detail = await project_service.get_project_detail(
            project_id=owned_project.id,
            session=session,
        )
        cache_key = f"project_member:{project_id}:{user.id}"
        cached = getattr(request.state, cache_key, None)
        if cached:
            detail.current_user_role = cached[1].role
        return detail
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        raise


@router.post(
    "/{project_id}/unlock-stage",
)
async def unlock_stage(
    project_id: str,
    request: UnlockStageRequest,
    owned_project: ProjectModel = Depends(require_owned_project),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.unlock_stage(
            project_id=owned_project.id,
            stage=request.stage,
            session=session,
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        if str(error) == "invalid_stage":
            raise HTTPException(
                status_code=400,
                detail="invalid_stage",
            )
        raise


@router.post(
    "/{project_id}/stage-transition",
    response_model=StageTransitionResponse,
)
async def stage_transition(
    project_id: str,
    request: StageTransitionRequest,
    owned_project: ProjectModel = Depends(require_owned_project),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.stage_transition(
            project_id=owned_project.id,
            action=request.action,
            force=request.force,
            operator_id=user.id,
            session=session,
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        if str(error) == "invalid_stage_transition":
            raise HTTPException(
                status_code=400,
                detail="invalid_stage_transition",
            )
        raise



@router.delete(
    "/{project_id}/perception-slot",
    response_model=PerceptionSlotDeleteResponse,
)
async def delete_perception_slot(
    project_id: str,
    owned_project: ProjectModel = Depends(require_owned_project),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.delete_perception_slot(
            project_id=owned_project.id,
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
    project_id: str,
    owned_project: ProjectModel = Depends(require_project_role("owner")),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.delete_project(
            project_id=owned_project.id,
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
    project_id: str,
    request: ProjectUpdateRequest,
    owned_project: ProjectModel = Depends(require_owned_project),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.update_project(
            project_id=owned_project.id,
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
    project_id: str,
    owned_project: ProjectModel = Depends(require_owned_project),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.get_project_detail(
            project_id=owned_project.id,
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
    project_id: str,
    owned_project: ProjectModel = Depends(require_owned_project),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.export_project_markdown(
            project_id=owned_project.id,
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
    project_id: str,
    request: ScopeImpactPreviewRequest,
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.preview_scope_impact(
            project_id=owned_project.id,
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


@router.get(
    "/{project_id}/stage-progress",
    response_model=StageProgressResponse,
)
async def get_stage_progress(
    project_id: str,
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_service.get_stage_progress(
            project_id=owned_project.id,
            public_project_id=project_id,
            session=session,
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        raise
