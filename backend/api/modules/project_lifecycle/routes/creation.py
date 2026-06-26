from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_owned_generative_draft
from backend.api.dependencies.llm import get_llm_context
from backend.database.model import UserModel, GenerativeDraftModel
from backend.api.modules.project_lifecycle.schemas.audit import DraftRegenerateRequest
from backend.api.modules.project_lifecycle.schemas.creation import (
    ProjectCreationConfirmResponse,
    ProjectCreationDraftCreateRequest,
    ProjectCreationDraftDiscardResponse,
    ProjectCreationDraftResponse,
)
from backend.api.modules.project_lifecycle.ports import get_project_creation_service
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
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    try:
        return await get_project_creation_service().create_draft(
            user_requirements=request.user_requirements,
            owner_user_id=user.id,
            session=session,
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
    request: DraftRegenerateRequest | None = None,
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    user_feedback = request.user_feedback if request else None
    try:
        return await get_project_creation_service().regenerate_draft(
            draft_id=draft.draft_id,
            owner_user_id=draft.owner_user_id,
            user_feedback=user_feedback,
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
                status_code=502,
                detail=str(error),
            )

        raise


@router.post(
    "/{draft_id}/confirm",
    response_model=ProjectCreationConfirmResponse,
)
async def confirm_project_creation_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await get_project_creation_service().confirm_draft(
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

        raise


@router.delete(
    "/{draft_id}",
    response_model=ProjectCreationDraftDiscardResponse,
)
async def discard_project_creation_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
):
    return await get_project_creation_service().discard_draft(
        draft_id=draft.draft_id,
        owner_user_id=draft.owner_user_id,
    )
