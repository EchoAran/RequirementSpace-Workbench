from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.issue_schema import (
    IssueResolutionResponse,
    IssueResolveRequest,
    IssueStatusUpdateRequest,
    IssueStatusUpdateResponse,
    ProjectIssuesResponse,
)
from backend.api.services.issue_service import IssueService
from backend.database.database import get_session


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


@router.get(
    "",
    response_model=ProjectIssuesResponse,
)
async def list_project_issues(
    project_id: int,
    stage: str = Query(pattern="^(what|how|scope|preview)$"),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await issue_service.list_issues(
            project_id=project_id,
            stage=stage,
            session=session,
        )
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


@router.post(
    "/resolve",
    response_model=IssueResolutionResponse,
)
async def resolve_project_issue(
    project_id: int,
    request: IssueResolveRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await issue_service.resolve_issue(
            project_id=project_id,
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


@router.put(
    "/status",
    response_model=IssueStatusUpdateResponse,
)
async def update_project_issue_status(
    project_id: int,
    request: IssueStatusUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await issue_service.set_issue_status(
            project_id=project_id,
            issue_id=request.issue_id,
            status=request.status,
            session=session,
        )
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
