from backend.api.dependencies.ownership import require_owned_project
from backend.database.model import ProjectModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.modules.diagnosis_quality.issue_repair.schemas import (
    IssueRepairDraftActionResponse,
    IssueRepairDraftResponse,
)
from backend.api.modules.diagnosis_quality.issue_repair.application.issue_repair_draft_service import (
    IssueRepairDraftService,
)
from backend.database.database import get_session
from backend.api.dependencies.llm import get_llm_context


router = APIRouter(
    prefix="/api/projects/{project_id}/issue_repair_drafts",
    tags=["issue_repair_drafts"],
)

draft_service = IssueRepairDraftService()


@router.post(
    "/{draft_id}/confirm",
    response_model=IssueRepairDraftActionResponse,
)
async def confirm_repair_draft(
    project_id: str,
    draft_id: str,
    session: AsyncSession = Depends(get_session),
 owned_project: ProjectModel = Depends(require_owned_project)):
    try:
        return await draft_service.confirm_draft(
            project_id=owned_project.id,
            draft_id=draft_id,
            session=session,
        )
    except ValueError as e:
        error_msg = str(e)
        if error_msg in ("draft_not_found", "draft_project_mismatch"):
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)


@router.post(
    "/{draft_id}/discard",
    response_model=IssueRepairDraftActionResponse,
)
async def discard_repair_draft(
    project_id: str,
    draft_id: str,
    session: AsyncSession = Depends(get_session),
 owned_project: ProjectModel = Depends(require_owned_project)):
    try:
        return await draft_service.discard_draft(
            project_id=owned_project.id,
            draft_id=draft_id,
            session=session,
        )
    except ValueError as e:
        error_msg = str(e)
        if error_msg in ("draft_not_found", "draft_project_mismatch"):
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)


@router.post(
    "/{draft_id}/regenerate",
    response_model=IssueRepairDraftResponse,
)
async def regenerate_repair_draft(
    project_id: str,
    draft_id: str,
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
 owned_project: ProjectModel = Depends(require_owned_project)):
    """Re-run AI solver for the old draft's issue and create a new draft."""
    try:
        return await draft_service.regenerate_draft(
            project_id=owned_project.id,
            draft_id=draft_id,
            session=session,
        )
    except ValueError as e:
        error_msg = str(e)
        if error_msg in ("draft_not_found", "draft_project_mismatch"):
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
