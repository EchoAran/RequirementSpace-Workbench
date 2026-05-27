from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.prototype_generation_schema import (
    PrototypePreviewGenerateRequest,
    PrototypePreviewNotFoundResponse,
    PrototypePreviewResponse,
)
from backend.api.services.service_registry import prototype_generation_service
from backend.database.database import get_session


router = APIRouter(
    prefix="/api/projects",
    tags=["prototype_generation"],
)

PROTOTYPE_GENERATION_ERRORS = {
    "invalid_skill_payload",
}


@router.post(
    "/{project_id}/prototype-preview",
    response_model=PrototypePreviewResponse,
)
async def generate_prototype_preview(
    project_id: int,
    request: PrototypePreviewGenerateRequest | None = Body(default=None),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await prototype_generation_service.generate_preview(
            project_id=project_id,
            session=session,
            force_regenerate=(
                request.force_regenerate
                if request is not None
                else True
            ),
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        if str(error) in PROTOTYPE_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.get(
    "/{project_id}/prototype-preview/latest",
    response_model=PrototypePreviewResponse | PrototypePreviewNotFoundResponse,
)
async def get_latest_prototype_preview(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        latest = await prototype_generation_service.get_latest_preview(
            project_id=project_id,
            session=session,
            raise_if_missing=False,
        )
        if latest is None:
            return PrototypePreviewNotFoundResponse(project_id=project_id)
        return latest
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        raise
