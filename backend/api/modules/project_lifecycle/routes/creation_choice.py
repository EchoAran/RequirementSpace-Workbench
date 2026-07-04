from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.api.dependencies.ownership import require_owned_choice_group_draft
from backend.api.dependencies.llm import get_llm_context
from backend.database.model import UserModel, GenerativeDraftModel
from backend.api.modules.project_lifecycle.schemas.creation_choice import (
    ProjectCreationChoiceGroupCreateRequest,
    ProjectCreationChoiceGroupResponse,
    ProjectCreationChoiceAcceptResponse,
    ProjectCreationChoiceGroupDiscardResponse,
    ProjectCreationChoiceGroupDeferResponse,
)
from backend.api.modules.project_lifecycle.application.creation_choice_service import (
    ProjectCreationChoiceGroupService,
)
from backend.database.database import get_session

router = APIRouter(
    prefix="/api/project_creation_choice_groups",
    tags=["project_creation"],
)

_service = ProjectCreationChoiceGroupService()


@router.post(
    "",
    response_model=ProjectCreationChoiceGroupResponse,
)
async def create_project_creation_choice_group(
    body: ProjectCreationChoiceGroupCreateRequest,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    """Create a project creation choice group with multiple candidates.

    The request triggers concurrent generation of N project drafts
    (default 2). The user can later accept, discard, or defer.
    No real ProjectModel is created until accept.
    """
    try:
        return await _service.create_choice_group(
            user_requirements=body.user_requirements,
            owner_user_id=user.id,
            candidate_count=body.candidate_count,
            user_feedback=body.user_feedback,
            session=session,
            knowledge_workspace_id=body.knowledge_workspace_id,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create project creation choice group: {e}",
        )


@router.get(
    "/{group_id}",
    response_model=ProjectCreationChoiceGroupResponse,
)
async def get_project_creation_choice_group(
    draft: GenerativeDraftModel = Depends(require_owned_choice_group_draft),
    session: AsyncSession = Depends(get_session),
):
    """Get a single onboarding choice group by id."""
    result = await _service.get_choice_group(draft.draft_id, draft.owner_user_id, session)
    if result is None:
        raise HTTPException(status_code=404, detail="choice_group_not_found")
    return result


@router.get(
    "",
    response_model=list[ProjectCreationChoiceGroupResponse],
)
async def list_open_project_creation_choice_groups(
    status: str | None = Query(None),
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List all open onboarding choice groups."""
    if status and status != "open":
        return []
    return await _service.list_open_choice_groups(user.id, session)


@router.post(
    "/{group_id}/choices/{choice_id}/accept",
    response_model=ProjectCreationChoiceAcceptResponse,
)
async def accept_project_creation_choice(
    choice_id: str,
    draft: GenerativeDraftModel = Depends(require_owned_choice_group_draft),
    session: AsyncSession = Depends(get_session),
):
    """Accept a choice from an onboarding choice group.

    Creates the real ProjectModel + ActorModel + FeatureModel.
    Marks the group as resolved and other choices as rejected.
    """
    try:
        return await _service.accept_choice(
            group_id=draft.draft_id,
            choice_id=choice_id,
            owner_user_id=draft.owner_user_id,
            session=session,
        )
    except ValueError as e:
        err_msg = str(e)
        status = 404 if err_msg in (
            "choice_not_found", "choice_group_not_found"
        ) else 403 if err_msg == "forbidden" else 400
        raise HTTPException(status_code=status, detail=err_msg)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to accept project creation choice: {e}",
        )


@router.post(
    "/{group_id}/discard",
    response_model=ProjectCreationChoiceGroupDiscardResponse,
)
async def discard_project_creation_choice_group(
    draft: GenerativeDraftModel = Depends(require_owned_choice_group_draft),
    session: AsyncSession = Depends(get_session),
):
    """Discard an onboarding choice group. No project is created."""
    try:
        return await _service.discard_choice_group(
            group_id=draft.draft_id,
            owner_user_id=draft.owner_user_id,
            session=session,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to discard project creation choice group: {e}",
        )


@router.post(
    "/{group_id}/defer",
    response_model=ProjectCreationChoiceGroupDeferResponse,
)
async def defer_project_creation_choice_group(
    draft: GenerativeDraftModel = Depends(require_owned_choice_group_draft),
    session: AsyncSession = Depends(get_session),
    llm_ctx=Depends(get_llm_context),
):
    """Create a blank project and migrate the onboarding choice group into it."""
    try:
        return await _service.defer_choice_group(
            group_id=draft.draft_id,
            owner_user_id=draft.owner_user_id,
            session=session,
        )
    except ValueError as e:
        err_msg = str(e)
        status = 404 if err_msg == "choice_group_not_found" else 400
        raise HTTPException(status_code=status, detail=err_msg)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to defer project creation choice group: {e}",
        )
