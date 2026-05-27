from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas import DraftRegenerateRequest
from backend.api.schemas.feature_generation_schema import (
    FeatureGenerationConfirmResponse,
    FeatureGenerationDraftCreateRequest,
    FeatureGenerationDraftDiscardResponse,
    FeatureGenerationDraftResponse,
)
from backend.api.services.service_registry import (
    feature_generation_service,
)
from backend.database.database import get_session


router = APIRouter(
    prefix="/api/feature_generation_drafts",
    tags=["feature_generation"],
)

FEATURE_GENERATION_ERRORS = {
    "project_not_found",
    "empty_features",
    "duplicate_feature_number",
    "invalid_feature_number_format",
    "missing_parent_feature",
    "invalid_root_feature_count",
    "invalid_actor_reference",
    "invalid_feature_payload",
    "invalid_skill_payload",
    "features_already_exist",
}


@router.post(
    "",
    response_model=FeatureGenerationDraftResponse,
)
async def create_feature_generation_draft(
    request: FeatureGenerationDraftCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await feature_generation_service.create_draft(
            project_id=request.project_id,
            session=session,
        )
    except ValueError as error:
        if str(error) in FEATURE_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.post(
    "/{draft_id}/regenerate",
    response_model=FeatureGenerationDraftResponse,
)
async def regenerate_feature_generation_draft(
    draft_id: str,
    request: DraftRegenerateRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    user_feedback = request.user_feedback if request else None
    try:
        return await feature_generation_service.regenerate_draft(
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
        if str(error) in FEATURE_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.post(
    "/{draft_id}/confirm",
    response_model=FeatureGenerationConfirmResponse,
)
async def confirm_feature_generation_draft(
    draft_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await feature_generation_service.confirm_draft(
            draft_id=draft_id,
            session=session,
        )
    except ValueError as error:
        if str(error) == "draft_not_found":
            raise HTTPException(
                status_code=404,
                detail="draft_not_found",
            )
        if str(error) in FEATURE_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.delete(
    "/{draft_id}",
    response_model=FeatureGenerationDraftDiscardResponse,
)
async def discard_feature_generation_draft(
    draft_id: str,
):
    return await feature_generation_service.discard_draft(
        draft_id=draft_id,
    )
