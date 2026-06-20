from backend.api.dependencies.ownership import require_owned_project
from backend.database.model import ProjectModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.issue_schema import (
    IssueResolutionResponse,
    IssueResolveRequest,
)
from backend.api.services.issue_service import IssueService
from backend.database.database import get_session
from backend.api.dependencies.llm import get_llm_context


router = APIRouter(
    prefix="/api/projects/{project_id}/issues",
    tags=["issues"],
)

issue_service = IssueService()

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
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
 owned_project: ProjectModel = Depends(require_owned_project)):
    try:
        res = await issue_service.resolve_issue(
            project_id=owned_project.id,
            issue_id=request.issue_id,
            issue_code=request.issue_code,
            stage=request.stage,
            target=(
                request.target.model_dump()
                if request.target is not None
                else None
            ),
            metadata=request.metadata,
            session=session,
        )
        res["project_id"] = owned_project.public_id
        if "action" in res and isinstance(res["action"], dict):
            act = res["action"]
            if "route" in act and isinstance(act["route"], str):
                act["route"] = act["route"].replace(f"/projects/{owned_project.id}", f"/projects/{owned_project.public_id}")
            if "payload" in act and isinstance(act["payload"], dict):
                if act["payload"].get("project_id") == owned_project.id:
                    act["payload"]["project_id"] = owned_project.public_id
                if "draft" in act["payload"] and isinstance(act["payload"]["draft"], dict):
                    if act["payload"]["draft"].get("project_id") == owned_project.id:
                        act["payload"]["draft"]["project_id"] = owned_project.public_id
        if "draft" in res and isinstance(res["draft"], dict):
            if res["draft"].get("project_id") == owned_project.id:
                res["draft"]["project_id"] = owned_project.public_id
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
