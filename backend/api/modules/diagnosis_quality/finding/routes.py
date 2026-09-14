from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import (
    require_owned_project as require_owned_project,
    require_project_member,
)
from backend.api.modules.diagnosis_quality.finding.application.finding_service import (
    FindingService,
)
from backend.api.modules.diagnosis_quality.finding.schemas import (
    FindingStatusUpdateRequest,
    FindingStatusUpdateResponse,
    ProjectFindingsResponse,
)
from backend.api.modules.version_control.dependencies import reject_commit_write
from backend.api.modules.version_control.public import (
    map_branch_error,
    resolve_branch_context,
)
from backend.database.database import get_session
from backend.database.model import ProjectModel, UserModel

router = APIRouter(
    prefix="/api/projects/{project_id}/findings",
    tags=["findings"],
)

finding_service = FindingService()

FINDING_ERRORS = {
    "project_not_found",
    "invalid_stage",
    "invalid_view",
    "invalid_finding_status",
}

@router.get(
    "",
    response_model=ProjectFindingsResponse,
)
async def list_project_findings(
    project_id: str,
    background_tasks: BackgroundTasks,
    stage: str = Query("all", pattern="^(what|how|scope|preview|all)$"),
    view: str = Query("issues", pattern="^(issues|next_action|gate|health)$"),
    action: str | None = Query(None, pattern="^(enter_how|enter_scope|generate_preview|export|save_checkpoint)$"),
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    try:
        _branch_obj, ws_obj, _perms = await session.run_sync(
            lambda s: resolve_branch_context(s, owned_project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    try:
        ws_id = ws_obj.id

        findings = await finding_service.list_findings(
            project_id=owned_project.id,
            stage=stage,
            view=view,
            action=action,
            session=session,
            background_tasks=background_tasks,
            public_project_id=owned_project.public_id,
            workspace_id=ws_id,
        )
        return ProjectFindingsResponse(
            project_id=owned_project.public_id,
            stage=stage,
            view=view,
            findings=[
                {
                    "finding_id": f.findingId,
                    "type": f.type.value,
                    "stage": f.stage.value,
                    "code": f.code,
                    "severity": f.severity.value,
                    "title": f.title,
                    "description": f.description,
                    "target": (
                        {
                            "target_type": f.target.targetType,
                            "target_id": f.target.targetId,
                            "parent_type": f.target.parentType,
                            "parent_id": f.target.parentId,
                        }
                        if f.target is not None
                        else None
                    ),
                    "blocking_scope": f.blockingScope.value,
                    "action_code": f.actionCode,
                    "metadata": f.metadata,
                    "capability": f.capability,
                }
                for f in findings
            ],
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        if str(error) in FINDING_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise

@router.put(
    "/status",
    response_model=FindingStatusUpdateResponse,
)
async def update_project_finding_status(
    project_id: str,
    request: FindingStatusUpdateRequest,
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
        res = await finding_service.set_finding_status(
            project_id=owned_project.id,
            finding_id=request.finding_id,
            status=request.status,
            session=session,
            workspace_id=ws_id,
        )
        return FindingStatusUpdateResponse(
            project_id=owned_project.public_id,
            finding_id=res["finding_id"],
            status=res["status"],
        )
    except ValueError as error:
        if str(error) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail="project_not_found",
            )
        if str(error) in FINDING_ERRORS:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )
        raise
