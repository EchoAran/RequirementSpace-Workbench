from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.llm import llm_context_manager
from backend.api.dependencies.ownership import require_owned_project
from backend.api.modules.diagnosis_quality.next_suggestion.application.next_suggestion_service import (
    NextSuggestionService,
)
from backend.api.modules.diagnosis_quality.next_suggestion.schemas import (
    NextSuggestionRediagnoseRequest,
    NextSuggestionResponse,
)
from backend.api.modules.version_control.dependencies import reject_commit_write
from backend.api.modules.version_control.public import (
    map_branch_error,
    resolve_branch_context,
)
from backend.database.database import get_session
from backend.database.model import ProjectModel, UserModel

router = APIRouter(
    prefix="/api/projects/{project_id}/next-suggestion",
    tags=["next_suggestion"],
)

next_suggestion_service = NextSuggestionService()

NEXT_SUGGESTION_ERRORS = {
    "project_not_found",
    "invalid_stage",
    "stage_not_unlocked",
}


@router.get(
    "",
    response_model=NextSuggestionResponse,
)
async def get_next_suggestion(
    project_id: str,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[UserModel, Depends(get_current_user)],
    owned_project: Annotated[ProjectModel, Depends(require_owned_project)],
    stage: str = Query(pattern="^(what|how|scope|preview)$"),
    branch: str | None = Query(None),
):
    try:
        _branch_obj, ws_obj, _perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    try:
        ws_id = ws_obj.id
        async with llm_context_manager(
            user,
            session,
            project_id=owned_project.id,
            require_config=False,
        ):
            return await next_suggestion_service.get_next_suggestion(
                project_id=owned_project.id,
                stage=stage,
                session=session,
                background_tasks=background_tasks,
                public_project_id=owned_project.public_id,
                workspace_id=ws_id,
            )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        if str(error) in NEXT_SUGGESTION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.post(
    "/rediagnose",
    response_model=NextSuggestionResponse,
)
async def rediagnose_next_suggestion(
    project_id: str,
    request: NextSuggestionRediagnoseRequest,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[UserModel, Depends(get_current_user)],
    owned_project: Annotated[ProjectModel, Depends(require_owned_project)],
    commit_guard: Annotated[None, Depends(reject_commit_write)] = None,
    branch: str | None = Query(None),
):
    try:
        _branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    if not perms["can_write"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="branch_readonly_or_protected",
        )

    try:
        ws_id = ws_obj.id
        async with llm_context_manager(user, session, project_id=owned_project.id):
            return await next_suggestion_service.rediagnose_next_suggestion(
                project_id=owned_project.id,
                stage=request.stage,
                session=session,
                background_tasks=background_tasks,
                public_project_id=owned_project.public_id,
                workspace_id=ws_id,
            )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        if str(error) in NEXT_SUGGESTION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.get(
    "/rediagnose/status",
    response_model=NextSuggestionResponse,
)
async def get_rediagnose_status(
    project_id: str,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[UserModel, Depends(get_current_user)],
    owned_project: Annotated[ProjectModel, Depends(require_owned_project)],
    stage: str = Query(pattern="^(what|how|scope|preview)$"),
    branch: str | None = Query(None),
):
    try:
        _branch_obj, ws_obj, _perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    try:
        ws_id = ws_obj.id
        async with llm_context_manager(user, session, project_id=owned_project.id):
            return await next_suggestion_service.get_next_suggestion(
                project_id=owned_project.id,
                stage=stage,
                session=session,
                background_tasks=background_tasks,
                public_project_id=owned_project.public_id,
                include_perception=True,
                workspace_id=ws_id,
            )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        if str(error) in NEXT_SUGGESTION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise
