from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_owned_project, require_owned_generative_draft
from backend.api.dependencies.llm import get_llm_context, llm_context_manager
from backend.database.model import UserModel, GenerativeDraftModel
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
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    owned_project = await require_owned_project(request.project_id, user, session)
    async with llm_context_manager(user, session):
        try:
            return await actor_generation_service.create_draft(
                project_id=owned_project.id,
                owner_user_id=user.id,
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
    request: DraftRegenerateRequest | None = None,
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    user_feedback = request.user_feedback if request else None
    try:
        return await actor_generation_service.regenerate_draft(
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
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await actor_generation_service.confirm_draft(
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
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
):
    return await actor_generation_service.discard_draft(
        draft_id=draft.draft_id,
        owner_user_id=draft.owner_user_id,
    )
