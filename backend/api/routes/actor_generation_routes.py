from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas import DraftRegenerateRequest
from backend.api.schemas.actor_generation_schema import (
    ActorGenerationConfirmResponse,
    ActorGenerationDraftCreateRequest,
    ActorGenerationDraftDiscardResponse,
    ActorGenerationDraftResponse,
)
from backend.api.services.service_registry import (
    actor_generation_service,
)
from backend.database.database import get_session


router = APIRouter(
    prefix="/api/actor_generation_drafts",
    tags=["actor_generation"],
)

ACTOR_GENERATION_ERRORS = {
    "project_not_found",
    "empty_actors",
    "invalid_actor_payload",
}


@router.post(
    "",
    response_model=ActorGenerationDraftResponse,
)
async def create_actor_generation_draft(
    request: ActorGenerationDraftCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await actor_generation_service.create_draft(
            project_id=request.project_id,
            session=session,
        )
    except ValueError as error:
        if str(error) in ACTOR_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.post(
    "/{draft_id}/regenerate",
    response_model=ActorGenerationDraftResponse,
)
async def regenerate_actor_generation_draft(
    draft_id: str,
    request: DraftRegenerateRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    user_feedback = request.user_feedback if request else None
    try:
        return await actor_generation_service.regenerate_draft(
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
        if str(error) in ACTOR_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.post(
    "/{draft_id}/confirm",
    response_model=ActorGenerationConfirmResponse,
)
async def confirm_actor_generation_draft(
    draft_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await actor_generation_service.confirm_draft(
            draft_id=draft_id,
            session=session,
        )
    except ValueError as error:
        if str(error) == "draft_not_found":
            raise HTTPException(
                status_code=404,
                detail="draft_not_found",
            )
        if str(error) in ACTOR_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.delete(
    "/{draft_id}",
    response_model=ActorGenerationDraftDiscardResponse,
)
async def discard_actor_generation_draft(
    draft_id: str,
):
    return await actor_generation_service.discard_draft(
        draft_id=draft_id,
    )
