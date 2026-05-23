from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas import DraftRegenerateRequest
from backend.api.schemas.perception_slot_filling_schema import (
    PerceptionSlotFillingConfirmResponse,
    PerceptionSlotFillingDraftCreateRequest,
    PerceptionSlotFillingDraftDiscardResponse,
    PerceptionSlotFillingDraftResponse,
)
from backend.api.services.perception_slot_filling_service import (
    PerceptionSlotFillingService,
)
from backend.database.database import get_session


router = APIRouter(
    prefix="/api/perception_slot_filling_drafts",
    tags=["perception_slot_filling"],
)

perception_slot_filling_service = PerceptionSlotFillingService()

PERCEPTION_SLOT_FILLING_ERRORS = {
    "project_not_found",
    "draft_not_found",
    "perception_job_not_found",
    "perception_slot_not_ready",
    "invalid_perception_kind",
    "unsupported_filler_kind",
    "empty_filler_response",
    "empty_actors",
    "invalid_actor_payload",
    "empty_features",
    "invalid_feature_payload",
    "duplicate_feature_id",
    "missing_parent_feature",
    "empty_scenarios",
    "invalid_scenario_payload",
    "invalid_perception_target",
    "empty_acceptance_criteria",
    "invalid_acceptance_criteria_payload",
    "invalid_scenario_reference",
    "duplicate_scenario_id",
    "empty_flows",
    "empty_flow_steps",
    "invalid_flow_step_payload",
    "invalid_flow_payload",
    "invalid_step_type",
    "invalid_step_number_format",
    "duplicate_step_number",
    "invalid_actor_reference",
    "invalid_feature_reference",
    "invalid_business_object_payload",
    "invalid_business_object_reference",
    "duplicate_business_object_id",
}


@router.post(
    "/actor",
    response_model=PerceptionSlotFillingDraftResponse,
)
async def create_actor_slot_filling_draft(
    request: PerceptionSlotFillingDraftCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await perception_slot_filling_service.create_actor_draft(
            project_id=request.project_id,
            perception_job_id=request.perception_job_id,
            session=session,
        )
    except ValueError as error:
        raise _to_http_exception(error)


@router.post(
    "/feature",
    response_model=PerceptionSlotFillingDraftResponse,
)
async def create_feature_slot_filling_draft(
    request: PerceptionSlotFillingDraftCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await perception_slot_filling_service.create_feature_draft(
            project_id=request.project_id,
            perception_job_id=request.perception_job_id,
            session=session,
        )
    except ValueError as error:
        raise _to_http_exception(error)


@router.post(
    "/scenario",
    response_model=PerceptionSlotFillingDraftResponse,
)
async def create_scenario_slot_filling_draft(
    request: PerceptionSlotFillingDraftCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await perception_slot_filling_service.create_scenario_draft(
            project_id=request.project_id,
            perception_job_id=request.perception_job_id,
            session=session,
        )
    except ValueError as error:
        raise _to_http_exception(error)


@router.post(
    "/acceptance_criteria",
    response_model=PerceptionSlotFillingDraftResponse,
)
async def create_acceptance_criteria_slot_filling_draft(
    request: PerceptionSlotFillingDraftCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await (
            perception_slot_filling_service
        ).create_acceptance_criteria_draft(
            project_id=request.project_id,
            perception_job_id=request.perception_job_id,
            session=session,
        )
    except ValueError as error:
        raise _to_http_exception(error)


@router.post(
    "/flow",
    response_model=PerceptionSlotFillingDraftResponse,
)
async def create_flow_slot_filling_draft(
    request: PerceptionSlotFillingDraftCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await perception_slot_filling_service.create_flow_draft(
            project_id=request.project_id,
            perception_job_id=request.perception_job_id,
            session=session,
        )
    except ValueError as error:
        raise _to_http_exception(error)


@router.post(
    "/{draft_id}/regenerate",
    response_model=PerceptionSlotFillingDraftResponse,
)
async def regenerate_slot_filling_draft(
    draft_id: str,
    request: DraftRegenerateRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    user_feedback = request.user_feedback if request else None
    try:
        return await perception_slot_filling_service.regenerate_draft(
            draft_id=draft_id,
            session=session,
            user_feedback=user_feedback,
        )
    except ValueError as error:
        raise _to_http_exception(error)


@router.post(
    "/{draft_id}/confirm",
    response_model=PerceptionSlotFillingConfirmResponse,
)
async def confirm_slot_filling_draft(
    draft_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await perception_slot_filling_service.confirm_draft(
            draft_id=draft_id,
            session=session,
        )
    except ValueError as error:
        raise _to_http_exception(error)


@router.delete(
    "/{draft_id}",
    response_model=PerceptionSlotFillingDraftDiscardResponse,
)
async def discard_slot_filling_draft(
    draft_id: str,
):
    return await perception_slot_filling_service.discard_draft(
        draft_id=draft_id,
    )


def _to_http_exception(error: ValueError) -> HTTPException:
    detail = str(error)

    if detail == "draft_not_found" or detail == "perception_job_not_found":
        return HTTPException(status_code=404, detail=detail)

    if detail in PERCEPTION_SLOT_FILLING_ERRORS:
        return HTTPException(status_code=400, detail=detail)

    raise error
