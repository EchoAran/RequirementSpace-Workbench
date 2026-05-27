from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas import DraftRegenerateRequest
from backend.api.schemas.project_creation_schema import (
    ProjectCreationConfirmResponse,
    ProjectCreationDraftCreateRequest,
    ProjectCreationDraftDiscardResponse,
    ProjectCreationDraftResponse,
)
from backend.api.services.service_registry import (
    project_creation_service,
)
from backend.database.database import get_session


FEATURE_GENERATION_ERRORS = {
    "empty_features",
    "duplicate_feature_number",
    "invalid_feature_number_format",
    "missing_parent_feature",
    "invalid_root_feature_count",
    "invalid_project_payload",
    "invalid_actor_reference",
    "invalid_feature_payload",
    "invalid_skill_payload",
}

router = APIRouter(
    prefix="/api/project_creation_drafts",
    tags=["project_creation"],
)

@router.post(
    "",
    response_model=ProjectCreationDraftResponse,
)
async def create_project_creation_draft(
    request: ProjectCreationDraftCreateRequest,
):
    try:
        return await project_creation_service.create_draft(
            user_requirements=request.user_requirements,
            project_name=request.project_name,
            project_description=request.project_description,
        )
    except ValueError as error:
        if str(error) in FEATURE_GENERATION_ERRORS:
            raise HTTPException(
                status_code=502,
                detail=str(error),
            )
        raise


@router.post(
    "/{draft_id}/regenerate",
    response_model=ProjectCreationDraftResponse,
)
async def regenerate_project_creation_draft(
    draft_id: str,
    request: DraftRegenerateRequest | None = None,
):
    user_feedback = request.user_feedback if request else None
    try:
        return await project_creation_service.regenerate_draft(
            draft_id=draft_id,
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
                status_code=502,
                detail=str(error),
            )

        raise


@router.post(
    "/{draft_id}/confirm",
    response_model=ProjectCreationConfirmResponse,
)
async def confirm_project_creation_draft(
    draft_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await project_creation_service.confirm_draft(
            draft_id=draft_id,
            session=session,
        )
    except ValueError as error:
        if str(error) == "draft_not_found":
            raise HTTPException(
                status_code=404,
                detail="draft_not_found",
            )

        raise


@router.delete(
    "/{draft_id}",
    response_model=ProjectCreationDraftDiscardResponse,
)
async def discard_project_creation_draft(
    draft_id: str,
):
    return await project_creation_service.discard_draft(
        draft_id=draft_id,
    )
