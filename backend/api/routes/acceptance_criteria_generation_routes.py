from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_owned_project, require_owned_generative_draft
from backend.api.dependencies.llm import get_llm_context
from backend.database.model import UserModel, GenerativeDraftModel
from backend.api.schemas import DraftRegenerateRequest
from backend.api.schemas.acceptance_criteria_generation_schema import (
    AcceptanceCriteriaGenerationBatchDraftCreateRequest,
    AcceptanceCriteriaGenerationConfirmResponse,
    AcceptanceCriteriaGenerationDraftDiscardResponse,
    AcceptanceCriteriaGenerationDraftResponse,
    AcceptanceCriteriaGenerationFullDraftCreateRequest,
    AcceptanceCriteriaGenerationSingleDraftCreateRequest,
)
from backend.api.services.service_registry import (
    acceptance_criteria_generation_service,
)
from backend.database.database import get_session


router = APIRouter(
    prefix="/api/acceptance_criteria_generation_drafts",
    tags=["acceptance_criteria_generation"],
)

ACCEPTANCE_CRITERIA_GENERATION_ERRORS = {
    "project_not_found",
    "no_scenarios_found",
    "empty_scenarios",
    "scenario_not_found",
    "duplicate_scenario_id",
    "invalid_scenario_reference",
    "invalid_scenario_actor_reference",
    "invalid_scenario_feature_reference",
    "empty_acceptance_criteria",
    "invalid_acceptance_criteria_payload",
    "invalid_skill_payload",
    "acceptance_criteria_already_exist",
}


@router.post(
    "/full",
    response_model=AcceptanceCriteriaGenerationDraftResponse,
)
async def create_full_acceptance_criteria_generation_draft(
    request: AcceptanceCriteriaGenerationFullDraftCreateRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    owned_project = await require_owned_project(request.project_id, user, session)
    try:
        return await acceptance_criteria_generation_service.create_full_draft(
            project_id=owned_project.id,
            owner_user_id=user.id,
            session=session,
        )
    except ValueError as error:
        if str(error) in ACCEPTANCE_CRITERIA_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.post(
    "/single",
    response_model=AcceptanceCriteriaGenerationDraftResponse,
)
async def create_single_acceptance_criteria_generation_draft(
    request: AcceptanceCriteriaGenerationSingleDraftCreateRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    owned_project = await require_owned_project(request.project_id, user, session)
    try:
        return await acceptance_criteria_generation_service.create_single_draft(
            project_id=owned_project.id,
            scenario_id=request.scenario_id,
            owner_user_id=user.id,
            session=session,
        )
    except ValueError as error:
        if str(error) in ACCEPTANCE_CRITERIA_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.post(
    "/batch",
    response_model=AcceptanceCriteriaGenerationDraftResponse,
)
async def create_batch_acceptance_criteria_generation_draft(
    request: AcceptanceCriteriaGenerationBatchDraftCreateRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    owned_project = await require_owned_project(request.project_id, user, session)
    try:
        return await acceptance_criteria_generation_service.create_batch_draft(
            project_id=owned_project.id,
            scenario_ids=request.scenario_ids,
            owner_user_id=user.id,
            session=session,
        )
    except ValueError as error:
        if str(error) in ACCEPTANCE_CRITERIA_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.post(
    "/{draft_id}/regenerate",
    response_model=AcceptanceCriteriaGenerationDraftResponse,
)
async def regenerate_acceptance_criteria_generation_draft(
    request: DraftRegenerateRequest | None = None,
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    user_feedback = request.user_feedback if request else None
    try:
        return await acceptance_criteria_generation_service.regenerate_draft(
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
        if str(error) in ACCEPTANCE_CRITERIA_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.post(
    "/{draft_id}/confirm",
    response_model=AcceptanceCriteriaGenerationConfirmResponse,
)
async def confirm_acceptance_criteria_generation_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await acceptance_criteria_generation_service.confirm_draft(
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
        if str(error) in ACCEPTANCE_CRITERIA_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.delete(
    "/{draft_id}",
    response_model=AcceptanceCriteriaGenerationDraftDiscardResponse,
)
async def discard_acceptance_criteria_generation_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
):
    return await acceptance_criteria_generation_service.discard_draft(
        draft_id=draft.draft_id,
        owner_user_id=draft.owner_user_id,
    )
