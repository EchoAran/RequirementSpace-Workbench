from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.next_suggestion_schema import (
    NextSuggestionRediagnoseRequest,
    NextSuggestionResponse,
    NextSuggestionStartRequest,
    NextSuggestionStartResponse,
)
from backend.api.services.next_suggestion_service import (
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
    "unsupported_suggestion_code",
    "stage_not_unlocked",
}


@router.get(
    "",
    response_model=NextSuggestionResponse,
)
async def get_next_suggestion(
    project_id: int,
    background_tasks: BackgroundTasks,
    stage: str = Query(pattern="^(what|how|scope|preview)$"),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await next_suggestion_service.get_next_suggestion(
            project_id=project_id,
            stage=stage,
            session=session,
            background_tasks=background_tasks,
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
    project_id: int,
    request: NextSuggestionRediagnoseRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await next_suggestion_service.rediagnose_next_suggestion(
            project_id=project_id,
            stage=request.stage,
            session=session,
            background_tasks=background_tasks,
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
    "/start",
    response_model=NextSuggestionStartResponse,
)
async def start_next_suggestion(
    project_id: int,
    request: NextSuggestionStartRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await next_suggestion_service.start_next_suggestion(
            project_id=project_id,
            stage=request.stage,
            suggestion_code=request.suggestion_code,
            target=request.target,
            query=request.query,
            session=session,
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
