from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.llm import get_llm_context
from backend.api.dependencies.ownership import require_project_member
from backend.api.modules.diagnosis_quality.issue_repair.application.issue_repair_draft_service import (
    IssueRepairDraftService,
)
from backend.api.modules.diagnosis_quality.issue_repair.schemas import (
    IssueRepairDraftActionResponse,
    IssueRepairDraftResponse,
)
from backend.api.modules.version_control.dependencies import reject_commit_write
from backend.database.database import get_session
from backend.database.model import ProjectModel, UserModel

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
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    from backend.api.modules.version_control.public import (
        map_branch_error,
        resolve_branch_context,
    )
    try:
        branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    if not perms.get("can_write", True):
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    ws_id = ws_obj.id if ws_obj else None
    try:
        return await draft_service.confirm_draft(
            project_id=project.id,
            draft_id=draft_id,
            session=session,
            workspace_id=ws_id,
            branch_name=branch_obj.name if branch_obj else None,
            head_commit_id=branch_obj.head_commit.public_id if branch_obj.head_commit else "head",
        )
    except ValueError as e:
        error_msg = str(e)
        if error_msg in ("draft_not_found", "draft_project_mismatch"):
            raise HTTPException(status_code=404, detail=error_msg)
        if error_msg in ("draft_branch_mismatch", "branch_drift_detected"):
            raise HTTPException(status_code=409, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)


@router.post(
    "/{draft_id}/discard",
    response_model=IssueRepairDraftActionResponse,
)
async def discard_repair_draft(
    project_id: str,
    draft_id: str,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    from backend.api.modules.version_control.public import (
        map_branch_error,
        resolve_branch_context,
    )
    try:
        _branch_obj, _ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    if not perms.get("can_write", True):
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    try:
        return await draft_service.discard_draft(
            project_id=project.id,
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
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
    project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    """Re-run AI solver for the old draft's issue and create a new draft."""
    from backend.api.modules.version_control.public import (
        map_branch_error,
        resolve_branch_context,
    )
    try:
        branch_obj, ws_obj, perms = await session.run_sync(
            lambda s: resolve_branch_context(s, project.id, branch, user.id)
        )
    except (ValueError, PermissionError) as error:
        raise map_branch_error(error)

    if not perms.get("can_write", True):
        raise HTTPException(
            status_code=403,
            detail="Branch is read-only or protected; main branch can only be evolved via Merge Requests"
        )

    ws_id = ws_obj.id if ws_obj else None
    try:
        return await draft_service.regenerate_draft(
            project_id=project.id,
            draft_id=draft_id,
            session=session,
            workspace_id=ws_id,
            branch_name=branch_obj.name if branch_obj else None,
            head_commit_id=branch_obj.head_commit.public_id if branch_obj.head_commit else "head",
        )
    except ValueError as e:
        error_msg = str(e)
        if error_msg in ("draft_not_found", "draft_project_mismatch"):
            raise HTTPException(status_code=404, detail=error_msg)
        if error_msg in ("draft_branch_mismatch", "branch_drift_detected"):
            raise HTTPException(status_code=409, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
