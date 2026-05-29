from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.issue_repair_draft_schema import (
    IssueRepairDraftActionResponse,
    IssueRepairDraftResponse,
)
from backend.api.services.issue_repair_draft_service import (
    IssueRepairDraftService,
)
from backend.database.database import get_session


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
    project_id: int,
    draft_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await draft_service.confirm_draft(
            project_id=project_id,
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
    project_id: int,
    draft_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await draft_service.discard_draft(
            project_id=project_id,
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
    project_id: int,
    draft_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Re-run AI solver for the old draft's issue and create a new draft."""
    try:
        return await draft_service.regenerate_draft(
            project_id=project_id,
            draft_id=draft_id,
            session=session,
        )
    except ValueError as e:
        error_msg = str(e)
        if error_msg in ("draft_not_found", "draft_project_mismatch"):
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
