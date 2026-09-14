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
from backend.api.modules.requirements_core.flow.application.flow_generation_service import FlowGenerationService
from backend.api.modules.requirements_core.flow.application.flow_object_usage_service import FlowObjectUsageService
from backend.api.modules.requirements_core.flow.application.flow_service import FlowService
from backend.api.modules.requirements_core.flow.application.flow_transition_service import FlowTransitionService
from backend.api.modules.requirements_core.flow.application.path_projection_service import PathProjectionService
from backend.api.modules.requirements_core.flow.schemas import (
    FlowCreateRequest,
    FlowGenerationConfirmResponse,
    FlowGenerationDraftCreateRequest,
    FlowGenerationDraftDiscardResponse,
    FlowGenerationDraftResponse,
    FlowObjectUsageResponse,
    FlowResponse,
    FlowStepCreateRequest,
    FlowStepResponse,
    FlowStepsReorderRequest,
    FlowStepUpdateRequest,
    FlowTransitionCreateRequest,
    FlowTransitionResponse,
    FlowTransitionUpdateRequest,
    FlowUpdateRequest,
    PathProjectionResponse,
)
from backend.api.modules.version_control.dependencies import reject_commit_write
from backend.api.modules.version_control.public import map_branch_error, resolve_branch_context
from backend.database.database import get_session
from backend.database.model import GenerativeDraftModel, ProjectModel, UserModel

# CRUD Router
router = APIRouter(
    prefix="/api/projects/{project_id}/flows",
    tags=["flows"],
)

flow_service = FlowService()
flow_transition_service = FlowTransitionService()
path_projection_service = PathProjectionService()
flow_object_usage_service = FlowObjectUsageService()

@router.post("", response_model=FlowResponse)
async def create_flow(
    project_id: str,
    request: FlowCreateRequest,
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
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    try:
        ws_id = ws_obj.id
        return await flow_service.create_flow(
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
            detail=f"Failed to create flow: {error}",
        )


@router.put("/{flow_id}", response_model=FlowResponse)
async def update_flow(
    project_id: str,
    flow_id: int,
    request: FlowUpdateRequest,
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
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    try:
        ws_id = ws_obj.id
        return await flow_service.update_flow(
            project_id=owned_project.id,
            flow_id=flow_id,
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
            detail=f"Failed to update flow: {error}",
        )


@router.delete("/{flow_id}")
async def delete_flow(
    project_id: str,
    flow_id: int,
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
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    try:
        ws_id = ws_obj.id
        return await flow_service.delete_flow(
            project_id=owned_project.id,
            flow_id=flow_id,
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
            detail=f"Failed to delete flow: {error}",
        )


@router.get("/{flow_id}/paths", response_model=PathProjectionResponse)
async def get_flow_paths(
    project_id: str,
    flow_id: int,
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

    ws_id = ws_obj.id
    return await path_projection_service.get_path_projections(
        project_id=owned_project.id,
        flow_id=flow_id,
        session=session,
        workspace_id=ws_id,
    )


@router.get("/{flow_id}/object-usage", response_model=FlowObjectUsageResponse)
async def get_flow_object_usage(
    project_id: str,
    flow_id: int,
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

    ws_id = ws_obj.id
    return await flow_object_usage_service.get_flow_object_usage(
        project_id=owned_project.id,
        flow_id=flow_id,
        session=session,
        workspace_id=ws_id,
    )


@router.post("/{flow_id}/steps", response_model=FlowStepResponse)
async def create_flow_step(
    project_id: str,
    flow_id: int,
    request: FlowStepCreateRequest,
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
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    try:
        ws_id = ws_obj.id
        return await flow_service.create_flow_step(
            project_id=owned_project.id,
            flow_id=flow_id,
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
            detail=f"Failed to create flow step: {error}",
        )


@router.put("/{flow_id}/steps/reorder", response_model=FlowResponse)
async def reorder_flow_steps(
    project_id: str,
    flow_id: int,
    request: FlowStepsReorderRequest,
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
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    try:
        ws_id = ws_obj.id
        return await flow_service.reorder_flow_steps(
            project_id=owned_project.id,
            flow_id=flow_id,
            req=request,
            session=session,
            workspace_id=ws_id,
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
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    try:
        ws_id = ws_obj.id
        return await flow_service.update_flow_step(
            project_id=owned_project.id,
            flow_id=flow_id,
            step_id=step_id,
            req=request,
            session=session,
            workspace_id=ws_id,
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
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    try:
        ws_id = ws_obj.id
        return await flow_service.delete_flow_step(
            project_id=owned_project.id,
            flow_id=flow_id,
            step_id=step_id,
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
            detail=f"Failed to delete flow step: {error}",
        )


@router.post("/{flow_id}/transitions", response_model=FlowTransitionResponse)
async def create_flow_transition(
    project_id: str,
    flow_id: int,
    request: FlowTransitionCreateRequest,
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
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests",
        )

    ws_id = ws_obj.id
    return await flow_transition_service.create_transition(
        project_id=owned_project.id,
        flow_id=flow_id,
        request=request,
        session=session,
        workspace_id=ws_id,
    )


@router.get("/{flow_id}/transitions", response_model=list[FlowTransitionResponse])
async def list_flow_transitions(
    project_id: str,
    flow_id: int,
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

    ws_id = ws_obj.id
    return await flow_transition_service.list_transitions(
        project_id=owned_project.id,
        flow_id=flow_id,
        session=session,
        workspace_id=ws_id,
    )


@router.get("/{flow_id}/transitions/{transition_id}", response_model=FlowTransitionResponse)
async def get_flow_transition(
    project_id: str,
    flow_id: int,
    transition_id: int,
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

    ws_id = ws_obj.id
    return await flow_transition_service.get_transition(
        project_id=owned_project.id,
        flow_id=flow_id,
        transition_id=transition_id,
        session=session,
        workspace_id=ws_id,
    )


@router.put("/{flow_id}/transitions/{transition_id}", response_model=FlowTransitionResponse)
async def update_flow_transition(
    project_id: str,
    flow_id: int,
    transition_id: int,
    request: FlowTransitionUpdateRequest,
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
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests",
        )

    ws_id = ws_obj.id
    return await flow_transition_service.update_transition(
        project_id=owned_project.id,
        flow_id=flow_id,
        transition_id=transition_id,
        request=request,
        session=session,
        workspace_id=ws_id,
    )


@router.delete("/{flow_id}/transitions/{transition_id}")
async def delete_flow_transition(
    project_id: str,
    flow_id: int,
    transition_id: int,
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
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests",
        )

    ws_id = ws_obj.id
    await flow_transition_service.delete_transition(
        project_id=owned_project.id,
        flow_id=flow_id,
        transition_id=transition_id,
        session=session,
        workspace_id=ws_id,
    )
    return {"status": "ok"}


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
    "invalid_actor_reference",
    "invalid_step_type",
}


@generation_router.post(
    "",
    response_model=FlowGenerationDraftResponse,
)
async def create_flow_generation_draft(
    request: FlowGenerationDraftCreateRequest,
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
            return await flow_generation_service.create_draft(
                project_id=owned_project.id,
                owner_user_id=user.id,
                session=session,
                branch_name=branch_obj.name if branch_obj else None,
                head_commit_id=branch_obj.head_commit_id if branch_obj else None,
                workspace_id=ws_id,
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
    commit_guard: None = Depends(reject_commit_write),
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
        return await flow_generation_service.confirm_draft(
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
        if err_str in FLOW_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=err_str,
            )
        raise


@generation_router.delete(
    "/{draft_id}",
    response_model=FlowGenerationDraftDiscardResponse,
)
async def discard_flow_generation_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    commit_guard: None = Depends(reject_commit_write),
):
    return await flow_generation_service.discard_draft(
        draft_id=draft.draft_id,
        owner_user_id=draft.owner_user_id,
    )
