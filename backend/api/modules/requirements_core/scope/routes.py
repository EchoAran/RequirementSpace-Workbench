from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_owned_project, require_owned_generative_draft
from backend.api.dependencies.llm import get_llm_context, llm_context_manager
from backend.database.model import UserModel, GenerativeDraftModel, ProjectModel
from backend.database.database import get_session

from backend.api.modules.project_lifecycle.public import DraftRegenerateRequest
from backend.api.modules.requirements_core.scope.schemas import (
    ScopeUpdateRequest,
    ScopeResponse,
    ScopeGenerationConfirmResponse,
    ScopeGenerationDraftCreateRequest,
    ScopeGenerationDraftDiscardResponse,
    ScopeGenerationDraftResponse,
)
from backend.api.modules.requirements_core.scope.application.scope_service import ScopeService
from backend.api.modules.requirements_core.scope.application.scope_generation_service import ScopeGenerationService

# 1. Feature-level Scope CRUD Router
router = APIRouter(
    prefix="/api/projects/{project_id}/features/{feature_id}/scope",
    tags=["scope"],
)

scope_service = ScopeService()

@router.put("", response_model=ScopeResponse)
async def update_feature_scope(
    project_id: str,
    feature_id: int,
    request: ScopeUpdateRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        return await scope_service.update_scope(
            project_id=owned_project.id,
            feature_id=feature_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        status = 404 if "not_found" in str(error) else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update feature scope: {error}",
        )


# 2. Project-level Scope/Kano Router
project_scope_router = APIRouter(
    prefix="/api/projects/{project_id}/scope",
    tags=["project_scope"],
)

@project_scope_router.post("/skip_kano")
async def skip_kano(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        return await scope_service.set_kano_status(
            project_id=owned_project.id,
            status="skipped",
            session=session,
        )
    except ValueError as error:
        status = 404 if "not_found" in str(error) else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to skip Kano analysis: {error}",
        )


@project_scope_router.post("/reset_kano")
async def reset_kano(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        return await scope_service.set_kano_status(
            project_id=owned_project.id,
            status="missing",
            session=session,
        )
    except ValueError as error:
        status = 404 if "not_found" in str(error) else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset Kano analysis: {error}",
        )


# 3. Scope Generation Router
generation_router = APIRouter(
    prefix="/api/scope_generation_drafts",
    tags=["scope_generation"],
)

scope_generation_service = ScopeGenerationService()

SCOPES_GENERATION_ERRORS = {
    "project_not_found",
    "empty_features",
    "empty_leaf_features",
    "empty_scopes",
    "duplicate_scope_feature",
    "scope_feature_mismatch",
    "invalid_feature_reference",
    "invalid_scope_status",
    "invalid_scope_payload",
    "invalid_skill_payload",
    "invalid_picture_base64",
}


@generation_router.post(
    "",
    response_model=ScopeGenerationDraftResponse,
)
async def create_scope_generation_draft(
    request: ScopeGenerationDraftCreateRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    owned_project = await require_owned_project(request.project_id, user, session)
    async with llm_context_manager(user, session, project_id=owned_project.id):
        try:
            return await scope_generation_service.create_draft(
                project_id=owned_project.id,
                owner_user_id=user.id,
                session=session,
            )
        except ValueError as error:
            if str(error) in SCOPES_GENERATION_ERRORS:
                raise HTTPException(
                    status_code=400,
                    detail=str(error),
                )
            raise


@generation_router.post(
    "/{draft_id}/regenerate",
    response_model=ScopeGenerationDraftResponse,
)
async def regenerate_scope_generation_draft(
    request: DraftRegenerateRequest | None = None,
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    user_feedback = request.user_feedback if request else None
    try:
        return await scope_generation_service.regenerate_draft(
            draft_id=draft.draft_id,
            owner_user_id=draft.owner_user_id,
            session=session,
            user_feedback=user_feedback,
        )
    except ValueError as error:
        if str(error) == "draft_not_found":
            raise HTTPException(
                status_code=404,
                detail="draft_not_found",
            )
        if str(error) in SCOPES_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@generation_router.post(
    "/{draft_id}/confirm",
    response_model=ScopeGenerationConfirmResponse,
)
async def confirm_scope_generation_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await scope_generation_service.confirm_draft(
            draft_id=draft.draft_id,
            owner_user_id=draft.owner_user_id,
            session=session,
        )
    except ValueError as error:
        if str(error) == "draft_not_found":
            raise HTTPException(
                status_code=404,
                detail="draft_not_found",
            )
        if str(error) in SCOPES_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@generation_router.delete(
    "/{draft_id}",
    response_model=ScopeGenerationDraftDiscardResponse,
)
async def discard_scope_generation_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
):
    return await scope_generation_service.discard_draft(
        draft_id=draft.draft_id,
        owner_user_id=draft.owner_user_id,
        session=session,
    )
