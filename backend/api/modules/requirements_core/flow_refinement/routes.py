"""FastAPI HTTP routes for triggering bounded flow path refinement."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_project_member
from backend.api.modules.decision_workflow.public import (
    GenerationChoiceService,
)
from backend.api.modules.requirements_core.flow_refinement.schemas import (
    FlowRefinementRequest,
)
from backend.api.modules.version_control.dependencies import reject_commit_write
from backend.api.modules.version_control.public import (
    map_branch_error,
    resolve_branch_context,
)
from backend.database.database import get_session
from backend.database.model import ProjectModel, UserModel

router = APIRouter(tags=["flow_refinement"])


@router.post("/api/projects/{project_id}/flows/refine")
async def trigger_flow_refinement(
    project_id: str,
    request: FlowRefinementRequest,
    branch: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    owned_project: ProjectModel = Depends(require_project_member),
    commit_guard: None = Depends(reject_commit_write),
):
    """Trigger bounded flow path refinement and create candidate choice group."""
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

    service = GenerationChoiceService()
    try:
        result = await service.create_choice_group(
            project_id=owned_project.id,
            generation_type="flow_refinement",
            candidate_count=request.candidate_count,
            session=session,
            target={
                "target_kind": request.target_kind,
                "target_id": request.target_id,
                "source_finding_id": request.source_finding_id,
            },
            user_feedback=request.focus_text,
            workspace_id=ws_id,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create flow refinement choice group: {exc}",
        )
