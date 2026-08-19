from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_owned_project, require_project_member, require_owned_generative_draft
from backend.api.dependencies.llm import get_llm_context, llm_context_manager
from backend.database.database import get_session
from backend.database.model import UserModel, ProjectModel, GenerativeDraftModel
from backend.api.modules.project_lifecycle.public import DraftRegenerateRequest
from backend.api.modules.requirements_core.scenario.schemas import (
    ScenarioCreateRequest,
    ScenarioUpdateRequest,
    ScenarioResponse,
    AcceptanceCriterionCreateRequest,
    AcceptanceCriterionUpdateRequest,
    AcceptanceCriterionResponse,
    ScenarioGenerationConfirmRequest,
    ScenarioGenerationConfirmResponse,
    ScenarioGenerationDraftDiscardResponse,
    ScenarioGenerationDraftResponse,
    ScenarioGenerationFullDraftCreateRequest,
    ScenarioGenerationSingleDraftCreateRequest,
    AcceptanceCriteriaGenerationBatchDraftCreateRequest,
    AcceptanceCriteriaGenerationConfirmResponse,
    AcceptanceCriteriaGenerationDraftDiscardResponse,
    AcceptanceCriteriaGenerationDraftResponse,
    AcceptanceCriteriaGenerationFullDraftCreateRequest,
    AcceptanceCriteriaGenerationSingleDraftCreateRequest,
)
from backend.api.modules.requirements_core.scenario.application.scenario_service import ScenarioService
from backend.api.modules.requirements_core.scenario.application.scenario_generation_service import ScenarioGenerationService
from backend.api.modules.requirements_core.scenario.application.acceptance_criteria_generation_service import AcceptanceCriteriaGenerationService
from backend.api.modules.version_control.public import resolve_branch_context
from backend.api.modules.version_control.dependencies import reject_commit_write


# 1. CRUD Router
crud_router = APIRouter(
    prefix="/api/projects/{project_id}/scenarios",
    tags=["scenarios"],
)

scenario_service = ScenarioService()


@crud_router.post("", response_model=ScenarioResponse)
async def create_scenario(
    project_id: str,
    request: ScenarioCreateRequest,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    try:
        branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
        if not perms.get("can_write", True):
            raise HTTPException(status_code=403, detail="Branch is read-only or protected for current user")

        ws_id = ws_obj.id if ws_obj else None
        return await scenario_service.create_scenario(
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
            detail=f"Failed to create scenario: {error}",
        )


@crud_router.put("/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    project_id: str,
    scenario_id: int,
    request: ScenarioUpdateRequest,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    try:
        branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
        if not perms.get("can_write", True):
            raise HTTPException(status_code=403, detail="Branch is read-only or protected for current user")

        ws_id = ws_obj.id if ws_obj else None
        return await scenario_service.update_scenario(
            project_id=owned_project.id,
            scenario_id=scenario_id,
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
            detail=f"Failed to update scenario: {error}",
        )


@crud_router.delete("/{scenario_id}")
async def delete_scenario(
    project_id: str,
    scenario_id: int,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    try:
        branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
        if not perms.get("can_write", True):
            raise HTTPException(status_code=403, detail="Branch is read-only or protected for current user")

        ws_id = ws_obj.id if ws_obj else None
        return await scenario_service.delete_scenario(
            project_id=owned_project.id,
            scenario_id=scenario_id,
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
            detail=f"Failed to delete scenario: {error}",
        )


@crud_router.post("/{scenario_id}/acceptance_criteria", response_model=AcceptanceCriterionResponse)
async def create_acceptance_criterion(
    project_id: str,
    scenario_id: int,
    request: AcceptanceCriterionCreateRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
    commit_guard: None = Depends(reject_commit_write),
):
    try:
        return await scenario_service.create_acceptance_criterion(
            project_id=owned_project.id,
            scenario_id=scenario_id,
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
            detail=f"Failed to create acceptance criterion: {error}",
        )


@crud_router.put("/{scenario_id}/acceptance_criteria/{ac_id}", response_model=AcceptanceCriterionResponse)
async def update_acceptance_criterion(
    project_id: str,
    scenario_id: int,
    ac_id: int,
    request: AcceptanceCriterionUpdateRequest,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
    commit_guard: None = Depends(reject_commit_write),
):
    try:
        return await scenario_service.update_acceptance_criterion(
            project_id=owned_project.id,
            scenario_id=scenario_id,
            ac_id=ac_id,
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
            detail=f"Failed to update acceptance criterion: {error}",
        )


@crud_router.delete("/{scenario_id}/acceptance_criteria/{ac_id}")
async def delete_acceptance_criterion(
    project_id: str,
    scenario_id: int,
    ac_id: int,
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
    commit_guard: None = Depends(reject_commit_write),
):
    try:
        return await scenario_service.delete_acceptance_criterion(
            project_id=owned_project.id,
            scenario_id=scenario_id,
            ac_id=ac_id,
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
            detail=f"Failed to delete acceptance criterion: {error}",
        )


# 2. Scenario Generation Router
scenario_generation_router = APIRouter(
    prefix="/api/scenario_generation_drafts",
    tags=["scenario_generation"],
)

scenario_generation_service = ScenarioGenerationService()

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


@scenario_generation_router.post(
    "/full",
    response_model=ScenarioGenerationDraftResponse,
)
async def create_full_scenario_generation_draft(
    request: ScenarioGenerationFullDraftCreateRequest,
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
    if not perms.get("can_write", True):
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    ws_id = ws_obj.id if ws_obj else None
    async with llm_context_manager(user, session, project_id=owned_project.id):
        try:
            return await scenario_generation_service.create_full_draft(
                project_id=owned_project.id,
                owner_user_id=user.id,
                session=session,
                branch_name=branch_obj.name if branch_obj else None,
                head_commit_id=branch_obj.head_commit_id if branch_obj else None,
                workspace_id=ws_id,
            )
        except ValueError as error:
            if str(error) in SCENARIO_GENERATION_ERRORS:
                raise HTTPException(
                    status_code=400,
                    detail=str(error),
                )
            raise


@scenario_generation_router.post(
    "/single",
    response_model=ScenarioGenerationDraftResponse,
)
async def create_single_scenario_generation_draft(
    request: ScenarioGenerationSingleDraftCreateRequest,
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
    if not perms.get("can_write", True):
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    ws_id = ws_obj.id if ws_obj else None
    async with llm_context_manager(user, session, project_id=owned_project.id):
        try:
            return await scenario_generation_service.create_single_draft(
                project_id=owned_project.id,
                feature_id=request.feature_id,
                owner_user_id=user.id,
                session=session,
                branch_name=branch_obj.name if branch_obj else None,
                head_commit_id=branch_obj.head_commit_id if branch_obj else None,
                workspace_id=ws_id,
            )
        except ValueError as error:
            if str(error) in SCENARIO_GENERATION_ERRORS:
                raise HTTPException(
                    status_code=400,
                    detail=str(error),
                )
            raise


@scenario_generation_router.post(
    "/{draft_id}/regenerate",
    response_model=ScenarioGenerationDraftResponse,
)
async def regenerate_scenario_generation_draft(
    request: DraftRegenerateRequest | None = None,
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
    commit_guard: None = Depends(reject_commit_write),
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


@scenario_generation_router.post(
    "/{draft_id}/confirm",
    response_model=ScenarioGenerationConfirmResponse,
)
async def confirm_scenario_generation_draft(
    request: ScenarioGenerationConfirmRequest | None = Body(default=None),
    branch: str | None = Query(None),
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
    commit_guard: None = Depends(reject_commit_write),
):
    from backend.api.modules.version_control.application.branch_service import resolve_branch_context
    branch_obj, ws_obj, perms = await session.run_sync(
        lambda s: resolve_branch_context(s, draft.project_id, branch, user.id)
    )
    if not perms.get("can_write", True):
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    ws_id = ws_obj.id if ws_obj else None
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
        if err_str in SCENARIO_GENERATION_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=err_str,
            )
        raise


@scenario_generation_router.delete(
    "/{draft_id}",
    response_model=ScenarioGenerationDraftDiscardResponse,
)
async def discard_scenario_generation_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    commit_guard: None = Depends(reject_commit_write),
):
    return await scenario_generation_service.discard_draft(
        draft_id=draft.draft_id,
        owner_user_id=draft.owner_user_id,
    )


# 3. Acceptance Criteria Generation Router
ac_generation_router = APIRouter(
    prefix="/api/acceptance_criteria_generation_drafts",
    tags=["acceptance_criteria_generation"],
)

acceptance_criteria_generation_service = AcceptanceCriteriaGenerationService()

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


@ac_generation_router.post(
    "/full",
    response_model=AcceptanceCriteriaGenerationDraftResponse,
)
async def create_full_acceptance_criteria_generation_draft(
    request: AcceptanceCriteriaGenerationFullDraftCreateRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    commit_guard: None = Depends(reject_commit_write),
):
    owned_project = await require_owned_project(request.project_id, user, session)
    async with llm_context_manager(user, session, project_id=owned_project.id):
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


@ac_generation_router.post(
    "/single",
    response_model=AcceptanceCriteriaGenerationDraftResponse,
)
async def create_single_acceptance_criteria_generation_draft(
    request: AcceptanceCriteriaGenerationSingleDraftCreateRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    commit_guard: None = Depends(reject_commit_write),
):
    owned_project = await require_owned_project(request.project_id, user, session)
    async with llm_context_manager(user, session, project_id=owned_project.id):
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


@ac_generation_router.post(
    "/batch",
    response_model=AcceptanceCriteriaGenerationDraftResponse,
)
async def create_batch_acceptance_criteria_generation_draft(
    request: AcceptanceCriteriaGenerationBatchDraftCreateRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    commit_guard: None = Depends(reject_commit_write),
):
    owned_project = await require_owned_project(request.project_id, user, session)
    async with llm_context_manager(user, session, project_id=owned_project.id):
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


@ac_generation_router.post(
    "/{draft_id}/regenerate",
    response_model=AcceptanceCriteriaGenerationDraftResponse,
)
async def regenerate_acceptance_criteria_generation_draft(
    request: DraftRegenerateRequest | None = None,
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
    commit_guard: None = Depends(reject_commit_write),
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


@ac_generation_router.post(
    "/{draft_id}/confirm",
    response_model=AcceptanceCriteriaGenerationConfirmResponse,
)
async def confirm_acceptance_criteria_generation_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    session: AsyncSession = Depends(get_session),
    commit_guard: None = Depends(reject_commit_write),
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


@ac_generation_router.delete(
    "/{draft_id}",
    response_model=AcceptanceCriteriaGenerationDraftDiscardResponse,
)
async def discard_acceptance_criteria_generation_draft(
    draft: GenerativeDraftModel = Depends(require_owned_generative_draft),
    commit_guard: None = Depends(reject_commit_write),
):
    return await acceptance_criteria_generation_service.discard_draft(
        draft_id=draft.draft_id,
        owner_user_id=draft.owner_user_id,
    )


router = crud_router
generation_router = scenario_generation_router
