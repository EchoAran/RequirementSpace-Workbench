from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas import DraftRegenerateRequest
from backend.api.schemas.flow_generation_schema import (
    FlowGenerationConfirmResponse,
    FlowGenerationDraftCreateRequest,
    FlowGenerationDraftDiscardResponse,
    FlowGenerationDraftResponse,
)
from backend.api.services.service_registry import (
    flow_generation_service,
)
from backend.database.database import get_session


router = APIRouter(
    prefix="/api/flow_generation_drafts",
    tags=["flow_generation"],
)

FLOW_GENERATION_ERRORS = {
    "project_not_found",
    "empty_actors",
    "empty_features",
    "empty_leaf_features",
    "empty_llm_response",
    "invalid_llm_response",
    "empty_business_objects",
    "empty_flows",
    "empty_flow_steps",
    "duplicate_business_object_number",
    "invalid_business_object_number_format",
    "invalid_business_object_reference",
    "invalid_feature_reference",
    "duplicate_step_number",
    "invalid_step_number_format",
    "invalid_next_step_reference",
    "invalid_actor_reference",
    "invalid_step_type",
}

@router.post(
    "",
    response_model=FlowGenerationDraftResponse,
)
async def create_flow_generation_draft(
    request: FlowGenerationDraftCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await flow_generation_service.create_draft(
            project_id=request.project_id,
            session=session,
        )
    except ValueError as error:
        if str(error) in FLOW_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.post(
    "/{draft_id}/regenerate",
    response_model=FlowGenerationDraftResponse,
)
async def regenerate_flow_generation_draft(
    draft_id: str,
    request: DraftRegenerateRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    user_feedback = request.user_feedback if request else None
    try:
        return await flow_generation_service.regenerate_draft(
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
        if str(error) in FLOW_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.post(
    "/{draft_id}/confirm",
    response_model=FlowGenerationConfirmResponse,
)
async def confirm_flow_generation_draft(
    draft_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await flow_generation_service.confirm_draft(
            draft_id=draft_id,
            session=session,
        )
    except ValueError as error:
        if str(error) == "draft_not_found":
            raise HTTPException(
                status_code=404,
                detail="draft_not_found",
            )
        if str(error) in FLOW_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.delete(
    "/{draft_id}",
    response_model=FlowGenerationDraftDiscardResponse,
)
async def discard_flow_generation_draft(
    draft_id: str,
):
    return await flow_generation_service.discard_draft(
        draft_id=draft_id,
    )
