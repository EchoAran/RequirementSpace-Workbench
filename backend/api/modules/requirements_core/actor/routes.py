from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.llm import get_llm_context, llm_context_manager
from backend.api.dependencies.ownership import (
    require_owned_generative_draft,
    require_owned_project as require_owned_project,
    require_project_member,
)
from backend.api.modules.project_lifecycle.public import DraftRegenerateRequest
from backend.api.modules.requirements_core.actor.application.actor_generation_service import ActorGenerationService
from backend.api.modules.requirements_core.actor.application.actor_service import ActorService
from backend.api.modules.requirements_core.actor.schemas import (
    ActorCreateRequest,
    ActorGenerationConfirmResponse,
    ActorGenerationDraftCreateRequest,
    ActorGenerationDraftDiscardResponse,
    ActorGenerationDraftResponse,
    ActorResponse,
    ActorUpdateRequest,
)
from backend.api.modules.version_control.dependencies import reject_commit_write
from backend.api.modules.version_control.public import map_branch_error, resolve_branch_context
from backend.database.database import get_session
from backend.database.model import GenerativeDraftModel, ProjectModel, UserModel

# 1. CRUD Router
crud_router = APIRouter(
    prefix="/api/projects/{project_id}/actors",
    tags=["actors"],
)

actor_service = ActorService()


@crud_router.get("", response_model=list[ActorResponse])
async def list_actors(
    project_id: str,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
):
    try:
        _branch_obj, ws_obj, _perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    try:
        ws_id = ws_obj.id
        return await actor_service.list_actors(
            project_id=owned_project.id,
            session=session,
            workspace_id=ws_id,
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
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    try:
        _branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    if not perms["can_write"]:
        raise HTTPException(status_code=403, detail="Branch is read-only or protected for current user")

    try:
        ws_id = ws_obj.id
        return await actor_service.create_actor(
            project_id=owned_project.id,
            req=request,
            session=session,
            workspace_id=ws_id,
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
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    try:
        _branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    if not perms["can_write"]:
        raise HTTPException(status_code=403, detail="Branch is read-only or protected for current user")

    try:
        ws_id = ws_obj.id
        return await actor_service.update_actor(
            project_id=owned_project.id,
            actor_id=actor_id,
            req=request,
            session=session,
            workspace_id=ws_id,
        )
    except ValueError as error:
        err_msg = str(error)
        if "optimistic_lock" in err_msg or "stale" in err_msg or "version_conflict" in err_msg:
            raise HTTPException(status_code=409, detail=err_msg)
        status = 404 if "not_found" in err_msg else 400
        raise HTTPException(
            status_code=status,
            detail=err_msg,
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
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    try:
        _branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    if not perms["can_write"]:
        raise HTTPException(status_code=403, detail="Branch is read-only or protected for current user")

    try:
        ws_id = ws_obj.id
        return await actor_service.delete_actor(
            project_id=owned_project.id,
            actor_id=actor_id,
            session=session,
            workspace_id=ws_id,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=404 if "not_found" in str(error) else 400,
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
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    commit_guard: None = Depends(reject_commit_write),
):
    owned_project = await require_project_member(request.project_id, user, session)
    from backend.api.modules.version_control.application.branch_service import resolve_branch_context
    branch_obj, ws_obj, perms = await session.run_sync(
        lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
    )
    if not perms["can_write"]:
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    ws_id = ws_obj.id
    async with llm_context_manager(user, session, project_id=owned_project.id):
        try:
            return await actor_generation_service.create_draft(
                project_id=owned_project.id,
                owner_user_id=user.id,
                session=session,
                branch_name=branch_obj.name,
                head_commit_id=branch_obj.head_commit_id,
                workspace_id=ws_id,
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
    commit_guard: None = Depends(reject_commit_write),
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
    branch: str | None = Query(None),
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    commit_guard: None = Depends(reject_commit_write),
):
    from backend.api.modules.version_control.application.branch_service import resolve_branch_context
    branch_obj, ws_obj, perms = await session.run_sync(
        lambda s: resolve_branch_context(s, draft.project_id, branch, user.id)
    )
    if not perms["can_write"]:
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    ws_id = ws_obj.id
    try:
        return await actor_generation_service.confirm_draft(
            draft_id=draft.draft_id,
            owner_user_id=draft.owner_user_id,
            session=session,
            branch_name=branch_obj.name if branch_obj else None,
            head_commit_id=branch_obj.head_commit_id if branch_obj else None,
            workspace_id=ws_id,
        )
    except ValueError as error:
        err_str = str(error)
        if err_str == "draft_not_found":
            raise HTTPException(
                status_code=404,
                detail="draft_not_found",
            )
        if "branch_drift_detected" in err_str or "draft_branch_mismatch" in err_str:
            raise HTTPException(
                status_code=409,
                detail=err_str,
            )
        if err_str in ACTOR_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=err_str,
            )
        raise


@generation_router.delete(
    "/{draft_id}",
    response_model=ActorGenerationDraftDiscardResponse,
)
async def discard_actor_generation_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    commit_guard: None = Depends(reject_commit_write),
):
    return await actor_generation_service.discard_draft(
        draft_id=draft.draft_id,
        owner_user_id=draft.owner_user_id,
    )


router = crud_router
