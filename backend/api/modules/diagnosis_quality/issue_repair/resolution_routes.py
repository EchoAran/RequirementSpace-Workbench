from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.llm import get_llm_context
from backend.api.dependencies.ownership import (
    require_owned_project as require_owned_project,
)
from backend.api.modules.diagnosis_quality.issue_repair.application.issue_repair_service import (
    IssueRepairService,
)
from backend.api.modules.diagnosis_quality.issue_repair.schemas import (
    IssueResolutionResponse,
    IssueResolveRequest,
)
from backend.api.modules.version_control.dependencies import reject_commit_write
from backend.database.database import get_session
from backend.database.model import UserModel

router = APIRouter(
    prefix="/api/projects/{project_id}/issue_repairs",
    tags=["issue_repairs"],
)

issue_repair_service = IssueRepairService()

ISSUE_ERRORS = {
    "project_not_found",
    "invalid_stage",
    "unsupported_issue_code",
    "invalid_resolution_payload",
    "unsupported_resolution_draft",
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
    "scenario_not_found",
    "duplicate_scenario_id",
    "invalid_scenario_reference",
    "invalid_scenario_actor_reference",
    "invalid_scenario_feature_reference",
    "empty_acceptance_criteria",
    "invalid_acceptance_criteria_payload",
    "acceptance_criteria_already_exist",
    "empty_scopes",
    "duplicate_scope_feature",
    "scope_feature_mismatch",
    "invalid_feature_reference",
    "invalid_scope_status",
    "invalid_scope_payload",
    "invalid_picture_base64",
    "stage_not_unlocked",
    "invalid_issue_status",
}


@router.post(
    "/resolve",
    response_model=IssueResolutionResponse,
)
async def resolve_project_issue(
    project_id: str,
    request: IssueResolveRequest,
    branch: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
    user: UserModel = Depends(get_current_user),
    commit_guard: None = Depends(reject_commit_write),
):
    from backend.api.dependencies.ownership import require_project_member
    from backend.api.modules.version_control.public import (
        map_branch_error,
        resolve_branch_context,
    )
    project = await require_project_member(project_id, user, session)
    try:
        branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    if not perms["can_write"]:
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    ws_id = ws_obj.id
    branch_name = branch_obj.name
    head_commit_id = branch_obj.head_commit.public_id if branch_obj.head_commit else "head"

    try:
        res = await issue_repair_service.resolve(
            project_id=project.id,
            issue_code=request.issue_code,
            stage=request.stage,
            target=(
                request.target.model_dump()
                if request.target is not None
                else None
            ),
            metadata={**request.metadata, **({"issue_id": request.issue_id} if request.issue_id else {})},
            session=session,
            workspace_id=ws_id,
            branch_name=branch_name,
            head_commit_id=head_commit_id,
        )
        res["project_id"] = project.public_id
        if "action" in res and isinstance(res["action"], dict):
            act = res["action"]
            if "route" in act and isinstance(act["route"], str):
                act["route"] = act["route"].replace(f"/projects/{project.id}", f"/projects/{project.public_id}")
            if "payload" in act and isinstance(act["payload"], dict):
                if act["payload"].get("project_id") == project.id:
                    act["payload"]["project_id"] = project.public_id
                if "draft" in act["payload"] and isinstance(act["payload"]["draft"], dict):
                    if act["payload"]["draft"].get("project_id") == project.id:
                        act["payload"]["draft"]["project_id"] = project.public_id
        if "draft" in res and isinstance(res["draft"], dict):
            if res["draft"].get("project_id") == project.id:
                res["draft"]["project_id"] = project.public_id
        return res
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        if str(error) in ISSUE_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise
