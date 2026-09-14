from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.llm import get_llm_context
from backend.api.dependencies.ownership import require_owned_project
from backend.api.modules.preview_convergence.ports import get_prototype_generation_service
from backend.api.modules.preview_convergence.schemas.prototype import (
    PrototypePreviewGenerateRequest,
    PrototypePreviewNotFoundResponse,
    PrototypePreviewResponse,
)
from backend.database.database import get_session
from backend.database.model import ProjectModel, UserModel

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
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    request: PrototypePreviewGenerateRequest | None = Body(default=None),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        from backend.api.modules.version_control.public import resolve_branch_context
        resolved_branch, _, _ = await session.run_sync(
            lambda db: resolve_branch_context(db, owned_project.id, branch, user.id)
        )
        branch_ref = resolved_branch.public_id if resolved_branch else None
        # Commit request session early to release db connection before long-running LLM call
        await session.commit()
        return await get_prototype_generation_service().start_generation(
            project_id=owned_project.id,
            branch_ref=branch_ref,
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
        from backend.api.modules.version_control.public import map_branch_error
        raise map_branch_error(error)


@router.get(
    "/prototype-preview/latest",
    response_model=PrototypePreviewResponse | PrototypePreviewNotFoundResponse,
)
async def get_latest_prototype_preview(
    project_id: str,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
    owned_project: ProjectModel = Depends(require_owned_project)):
    try:
        from backend.api.modules.version_control.public import resolve_branch_context
        resolved_branch, _, _ = await session.run_sync(
            lambda db: resolve_branch_context(db, owned_project.id, branch, user.id)
        )
        branch_ref = resolved_branch.public_id if resolved_branch else None
        latest = await get_prototype_generation_service().get_latest_preview(
            project_id=owned_project.id,
            branch_ref=branch_ref,
            session=session,
            raise_if_missing=False,
        )
        if latest is None:
            return PrototypePreviewNotFoundResponse(project_id=owned_project.public_id)
        if latest.status == "generating":
            get_prototype_generation_service().ensure_generation_running(
                latest.prototype_id,
                owned_project.id,
            )
        return latest
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        from backend.api.modules.version_control.public import map_branch_error
        raise map_branch_error(error)
