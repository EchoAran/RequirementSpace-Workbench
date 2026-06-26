from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_owned_project, require_owned_generative_draft
from backend.api.dependencies.llm import get_llm_context
from backend.database.model import UserModel, GenerativeDraftModel, ProjectModel
from backend.database.database import get_session

from backend.api.modules.project_lifecycle.public import DraftRegenerateRequest
from backend.api.modules.requirements_core.flow.schemas import (
    FlowCreateRequest,
    FlowUpdateRequest,
    FlowResponse,
    FlowStepCreateRequest,
    FlowStepUpdateRequest,
    FlowStepResponse,
    FlowStepsReorderRequest,
    FlowGenerationConfirmResponse,
    FlowGenerationDraftCreateRequest,
    FlowGenerationDraftDiscardResponse,
    FlowGenerationDraftResponse,
)
from backend.api.modules.requirements_core.flow.application.flow_service import FlowService
from backend.api.modules.requirements_core.flow.application.flow_generation_service import FlowGenerationService

# CRUD Router
router = APIRouter(
    prefix="/api/projects/{project_id}/flows",
    tags=["flows"],
)

flow_service = FlowService()

@router.post("", response_model=FlowResponse)
async def create_flow(
    project_id: str,
    request: FlowCreateRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        return await flow_service.create_flow(
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
            detail=f"Failed to create flow: {error}",
        )


@router.put("/{flow_id}", response_model=FlowResponse)
async def update_flow(
    project_id: str,
    flow_id: int,
    request: FlowUpdateRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        return await flow_service.update_flow(
            project_id=owned_project.id,
            flow_id=flow_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        status = 404 if str(error) == "flow_not_found" else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update flow: {error}",
        )


@router.delete("/{flow_id}")
async def delete_flow(
    project_id: str,
    flow_id: int,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        return await flow_service.delete_flow(
            project_id=owned_project.id,
            flow_id=flow_id,
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
            detail=f"Failed to delete flow: {error}",
        )


@router.post("/{flow_id}/steps", response_model=FlowStepResponse)
async def create_flow_step(
    project_id: str,
    flow_id: int,
    request: FlowStepCreateRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        return await flow_service.create_flow_step(
            project_id=owned_project.id,
            flow_id=flow_id,
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
            detail=f"Failed to create flow step: {error}",
        )


@router.put("/{flow_id}/steps/reorder", response_model=FlowResponse)
async def reorder_flow_steps(
    project_id: str,
    flow_id: int,
    request: FlowStepsReorderRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        return await flow_service.reorder_flow_steps(
            project_id=owned_project.id,
            flow_id=flow_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        status = 404 if str(error) == "flow_not_found" else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reorder steps: {error}",
        )


@router.put("/{flow_id}/steps/{step_id}", response_model=FlowStepResponse)
async def update_flow_step(
    project_id: str,
    flow_id: int,
    step_id: int,
    request: FlowStepUpdateRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        return await flow_service.update_flow_step(
            project_id=owned_project.id,
            flow_id=flow_id,
            step_id=step_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        status = 404 if "not_found" in str(error) else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update flow step: {error}",
        )


@router.delete("/{flow_id}/steps/{step_id}")
async def delete_flow_step(
    project_id: str,
    flow_id: int,
    step_id: int,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        return await flow_service.delete_flow_step(
            project_id=owned_project.id,
            flow_id=flow_id,
            step_id=step_id,
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
            detail=f"Failed to delete flow step: {error}",
        )


# Generation Router
generation_router = APIRouter(
    prefix="/api/flow_generation_drafts",
    tags=["flow_generation"],
)

flow_generation_service = FlowGenerationService()

FLOW_GENERATION_ERRORS = {
    "project_not_found",
    "empty_actors",
    "empty_features",
    "empty_leaf_features",
    "empty_llm_response",
    "invalid_llm_response",
    "empty_business_objects",
    "empty_flows",
    "empty_flow_steps",
    "duplicate_business_object_number",
    "invalid_business_object_number_format",
    "invalid_business_object_reference",
    "invalid_feature_reference",
    "duplicate_step_number",
    "invalid_step_number_format",
    "invalid_next_step_reference",
    "invalid_actor_reference",
    "invalid_step_type",
}


@generation_router.post(
    "",
    response_model=FlowGenerationDraftResponse,
)
async def create_flow_generation_draft(
    request: FlowGenerationDraftCreateRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    owned_project = await require_owned_project(request.project_id, user, session)
    try:
        return await flow_generation_service.create_draft(
            project_id=owned_project.id,
            owner_user_id=user.id,
            session=session,
        )
    except ValueError as error:
        if str(error) in FLOW_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@generation_router.post(
    "/{draft_id}/regenerate",
    response_model=FlowGenerationDraftResponse,
)
async def regenerate_flow_generation_draft(
    request: DraftRegenerateRequest | None = None,
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    user_feedback = request.user_feedback if request else None
    try:
        return await flow_generation_service.regenerate_draft(
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
        if str(error) in FLOW_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@generation_router.post(
    "/{draft_id}/confirm",
    response_model=FlowGenerationConfirmResponse,
)
async def confirm_flow_generation_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await flow_generation_service.confirm_draft(
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
        if str(error) in FLOW_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise


@generation_router.delete(
    "/{draft_id}",
    response_model=FlowGenerationDraftDiscardResponse,
)
async def discard_flow_generation_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
):
    return await flow_generation_service.discard_draft(
        draft_id=draft.draft_id,
        owner_user_id=draft.owner_user_id,
    )
