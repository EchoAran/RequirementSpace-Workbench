from backend.api.dependencies.ownership import require_owned_project
from backend.database.model import ProjectModel, UserModel
from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.llm import llm_context_manager
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.modules.diagnosis_quality.next_suggestion.schemas import (
    NextSuggestionRediagnoseRequest,
    NextSuggestionResponse,
)
from backend.api.modules.diagnosis_quality.next_suggestion.application.next_suggestion_service import (
    NextSuggestionService,
)
from backend.database.database import get_session


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
    stage: str = Query(pattern="^(what|how|scope|preview)$"),
    session: AsyncSession = Depends(get_session),
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_owned_project)):
    try:
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
    session: AsyncSession = Depends(get_session),
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_owned_project)):
    try:
        async with llm_context_manager(user, session, project_id=owned_project.id):
            return await next_suggestion_service.rediagnose_next_suggestion(
                project_id=owned_project.id,
                stage=request.stage,
                session=session,
                background_tasks=background_tasks,
                public_project_id=owned_project.public_id,
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
    stage: str = Query(pattern="^(what|how|scope|preview)$"),
    session: AsyncSession = Depends(get_session),
    user: UserModel = Depends(get_current_user),
    owned_project: ProjectModel = Depends(require_owned_project)):
    try:
        async with llm_context_manager(user, session, project_id=owned_project.id):
            return await next_suggestion_service.get_next_suggestion(
                project_id=owned_project.id,
                stage=stage,
                session=session,
                background_tasks=background_tasks,
                public_project_id=owned_project.public_id,
                include_perception=True,
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
