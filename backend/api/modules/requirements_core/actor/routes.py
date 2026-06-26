from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_owned_project, require_owned_generative_draft
from backend.api.dependencies.llm import get_llm_context, llm_context_manager
from backend.database.database import get_session
from backend.database.model import UserModel, ProjectModel, GenerativeDraftModel
from backend.api.modules.project_lifecycle.public import DraftRegenerateRequest
from backend.api.modules.requirements_core.actor.schemas import (
    ActorCreateRequest,
    ActorUpdateRequest,
    ActorResponse,
    ActorGenerationConfirmResponse,
    ActorGenerationDraftCreateRequest,
    ActorGenerationDraftDiscardResponse,
    ActorGenerationDraftResponse,
)
from backend.api.modules.requirements_core.actor.application.actor_service import ActorService
from backend.api.modules.requirements_core.actor.application.actor_generation_service import ActorGenerationService


# 1. CRUD Router
crud_router = APIRouter(
    prefix="/api/projects/{project_id}/actors",
    tags=["actors"],
)

actor_service = ActorService()


@crud_router.get("", response_model=list[ActorResponse])
async def list_actors(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    try:
        return await actor_service.list_actors(
            project_id=owned_project.id,
            session=session,
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch actors: {error}",
        )


@crud_router.post("", response_model=ActorResponse)
async def create_actor(
    project_id: str,
    request: ActorCreateRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    try:
        return await actor_service.create_actor(
            project_id=owned_project.id,
            req=request,
            session=session,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create actor: {error}",
        )


@crud_router.put("/{actor_id}", response_model=ActorResponse)
async def update_actor(
    project_id: str,
    actor_id: int,
    request: ActorUpdateRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    try:
        return await actor_service.update_actor(
            project_id=owned_project.id,
            actor_id=actor_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        status = 404 if str(error) == "actor_not_found" else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update actor: {error}",
        )


@crud_router.delete("/{actor_id}")
async def delete_actor(
    project_id: str,
    actor_id: int,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project)
):
    try:
        return await actor_service.delete_actor(
            project_id=owned_project.id,
            actor_id=actor_id,
            session=session,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete actor: {error}",
        )


# 2. Generation Router
generation_router = APIRouter(
    prefix="/api/actor_generation_drafts",
    tags=["actor_generation"],
)

actor_generation_service = ActorGenerationService()

ACTOR_GENERATION_ERRORS = {
    "project_not_found",
    "empty_actors",
    "invalid_actor_payload",
}


@generation_router.post(
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


@generation_router.post(
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


@generation_router.post(
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


@generation_router.delete(
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


router = crud_router
