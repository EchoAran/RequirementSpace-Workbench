from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas import DraftRegenerateRequest
from backend.api.schemas.scope_generation_schema import (
    ScopeGenerationConfirmResponse,
    ScopeGenerationDraftCreateRequest,
    ScopeGenerationDraftDiscardResponse,
    ScopeGenerationDraftResponse,
)
from backend.api.services.service_registry import (
    scope_generation_service,
)
from backend.database.database import get_session


router = APIRouter(
    prefix="/api/scope_generation_drafts",
    tags=["scope_generation"],
)

SCOPE_GENERATION_ERRORS = {
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


@router.post(
    "",
    response_model=ScopeGenerationDraftResponse,
)
async def create_scope_generation_draft(
    request: ScopeGenerationDraftCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await scope_generation_service.create_draft(
            project_id=request.project_id,
            session=session,
        )
    except ValueError as error:
        if str(error) in SCOPE_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.post(
    "/{draft_id}/regenerate",
    response_model=ScopeGenerationDraftResponse,
)
async def regenerate_scope_generation_draft(
    draft_id: str,
    request: DraftRegenerateRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    user_feedback = request.user_feedback if request else None
    try:
        return await scope_generation_service.regenerate_draft(
            draft_id=draft_id,
            session=session,
            user_feedback=user_feedback,
        )
    except ValueError as error:
        if str(error) == "draft_not_found":
            raise HTTPException(
                status_code=404,
                detail="draft_not_found",
            )
        if str(error) in SCOPE_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.post(
    "/{draft_id}/confirm",
    response_model=ScopeGenerationConfirmResponse,
)
async def confirm_scope_generation_draft(
    draft_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await scope_generation_service.confirm_draft(
            draft_id=draft_id,
            session=session,
        )
    except ValueError as error:
        if str(error) == "draft_not_found":
            raise HTTPException(
                status_code=404,
                detail="draft_not_found",
            )
        if str(error) in SCOPE_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.delete(
    "/{draft_id}",
    response_model=ScopeGenerationDraftDiscardResponse,
)
async def discard_scope_generation_draft(
    draft_id: str,
):
    return await scope_generation_service.discard_draft(
        draft_id=draft_id,
    )
