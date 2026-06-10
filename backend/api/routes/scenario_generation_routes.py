from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_owned_project, require_owned_generative_draft
from backend.api.dependencies.llm import get_llm_context
from backend.database.model import UserModel, GenerativeDraftModel
from backend.api.schemas import DraftRegenerateRequest
from backend.api.schemas.scenario_generation_schema import (
    ScenarioGenerationConfirmRequest,
    ScenarioGenerationConfirmResponse,
    ScenarioGenerationDraftDiscardResponse,
    ScenarioGenerationDraftResponse,
    ScenarioGenerationFullDraftCreateRequest,
    ScenarioGenerationSingleDraftCreateRequest,
)
from backend.api.services.service_registry import (
    scenario_generation_service,
)
from backend.database.database import get_session


router = APIRouter(
    prefix="/api/scenario_generation_drafts",
    tags=["scenario_generation"],
)

SCENARIO_GENERATION_ERRORS = {
    "project_not_found",
    "empty_actors",
    "empty_features",
    "empty_leaf_features",
    "feature_id_required",
    "feature_not_found",
    "feature_is_not_leaf",
    "actor_id_required",
    "actor_not_found",
    "leaf_feature_without_actor",
    "invalid_feature_actor_reference",
    "empty_generation_targets",
    "empty_scenarios",
    "invalid_scenario_payload",
    "invalid_skill_payload",
    "invalid_scenario_reference",
    "duplicate_scenario_id",
    "invalid_scenario_actor_reference",
    "invalid_scenario_feature_reference",
    "empty_acceptance_criteria",
    "invalid_acceptance_criteria_payload",
    "acceptance_criteria_already_exist",
}

@router.post(
    "/full",
    response_model=ScenarioGenerationDraftResponse,
)
async def create_full_scenario_generation_draft(
    request: ScenarioGenerationFullDraftCreateRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    owned_project = await require_owned_project(request.project_id, user, session)
    try:
        return await scenario_generation_service.create_full_draft(
            project_id=owned_project.id,
            owner_user_id=user.id,
            session=session,
        )
    except ValueError as error:
        if str(error) in SCENARIO_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.post(
    "/single",
    response_model=ScenarioGenerationDraftResponse,
)
async def create_single_scenario_generation_draft(
    request: ScenarioGenerationSingleDraftCreateRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    owned_project = await require_owned_project(request.project_id, user, session)
    try:
        return await scenario_generation_service.create_single_draft(
            project_id=owned_project.id,
            feature_id=request.feature_id,
            owner_user_id=user.id,
            session=session,
        )
    except ValueError as error:
        if str(error) in SCENARIO_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@router.post(
    "/{draft_id}/regenerate",
    response_model=ScenarioGenerationDraftResponse,
)
async def regenerate_scenario_generation_draft(
    request: DraftRegenerateRequest | None = None,
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    user_feedback = request.user_feedback if request else None
    try:
        return await scenario_generation_service.regenerate_draft(
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
        if str(error) in SCENARIO_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise

@router.post(
    "/{draft_id}/confirm",
    response_model=ScenarioGenerationConfirmResponse,
)
async def confirm_scenario_generation_draft(
    request: ScenarioGenerationConfirmRequest | None = Body(default=None),
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    try:
        generate_acceptance_criteria = (
            request.generate_acceptance_criteria
            if request is not None
            else False
        )

        return await scenario_generation_service.confirm_draft(
            draft_id=draft.draft_id,
            owner_user_id=draft.owner_user_id,
            session=session,
            generate_acceptance_criteria=generate_acceptance_criteria,
        )
    except ValueError as error:
        if str(error) == "draft_not_found":
            raise HTTPException(
                status_code=404,
                detail="draft_not_found",
            )
        if str(error) in SCENARIO_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise

@router.delete(
    "/{draft_id}",
    response_model=ScenarioGenerationDraftDiscardResponse,
)
async def discard_scenario_generation_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
):
    return await scenario_generation_service.discard_draft(
        draft_id=draft.draft_id,
        owner_user_id=draft.owner_user_id,
    )
