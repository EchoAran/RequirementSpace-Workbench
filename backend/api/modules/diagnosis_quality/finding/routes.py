from backend.api.dependencies.ownership import require_owned_project
from backend.database.model import ProjectModel
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.modules.diagnosis_quality.finding.schemas import (
    ProjectFindingsResponse,
    FindingStatusUpdateRequest,
    FindingStatusUpdateResponse,
)
from backend.api.modules.diagnosis_quality.finding.application.finding_service import FindingService
from backend.database.database import get_session

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
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        findings = await finding_service.list_findings(
            project_id=owned_project.id,
            stage=stage,
            view=view,
            action=action,
            session=session,
            background_tasks=background_tasks,
            public_project_id=owned_project.public_id,
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
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_owned_project),
):
    try:
        res = await finding_service.set_finding_status(
            project_id=owned_project.id,
            finding_id=request.finding_id,
            status=request.status,
            session=session,
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
