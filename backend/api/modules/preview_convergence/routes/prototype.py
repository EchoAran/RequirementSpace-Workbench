from backend.api.dependencies.ownership import require_owned_project
from backend.database.model import ProjectModel
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.modules.preview_convergence.schemas.prototype import (
    PrototypePreviewGenerateRequest,
    PrototypePreviewNotFoundResponse,
    PrototypePreviewResponse,
)
from backend.api.modules.preview_convergence.ports import get_prototype_generation_service
from backend.database.database import get_session
from backend.api.dependencies.llm import get_llm_context


router = APIRouter(
    prefix="/api/projects/{project_id}",
    tags=["prototype_generation"],
)

PROTOTYPE_GENERATION_ERRORS = {
    "invalid_skill_payload",
}


@router.post(
    "/prototype-preview",
    response_model=PrototypePreviewResponse,
)
async def generate_prototype_preview(
    project_id: str,
    request: PrototypePreviewGenerateRequest | None = Body(default=None),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        # Commit request session early to release db connection before long-running LLM call
        await session.commit()
        return await get_prototype_generation_service().generate_preview(
            project_id=owned_project.id,
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
    "/prototype-preview/latest",
    response_model=PrototypePreviewResponse | PrototypePreviewNotFoundResponse,
)
async def get_latest_prototype_preview(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)):
    try:
        latest = await get_prototype_generation_service().get_latest_preview(
            project_id=owned_project.id,
            session=session,
            raise_if_missing=False,
        )
        if latest is None:
            return PrototypePreviewNotFoundResponse(project_id=owned_project.public_id)
        return latest
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        raise
