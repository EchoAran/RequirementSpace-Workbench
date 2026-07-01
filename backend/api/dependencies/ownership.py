from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.database.database import get_session
from backend.database.model import (
    UserModel,
    ProjectModel,
    GenerativeDraftModel,
    ChoiceGroupModel,
    ChoiceModel,
    AIAddSessionModel,
)
from backend.api.dependencies.project_access import (
    require_project_member,
    require_project_role,
)


async def require_owned_project(
    project_id: str,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
) -> ProjectModel:
    """Old owner check rewritten to support project membership and roles.

    If the request method is GET, it only checks project membership.
    Otherwise (POST, PUT, DELETE, etc.), it checks editor role.
    """
    if request is not None and request.method == "GET":
        return await require_project_member(project_id, user, session, request)
    dep = require_project_role("editor")
    return await dep(project_id, user, session, request)


async def require_owned_generative_draft(
    draft_id: str,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
) -> GenerativeDraftModel:
    """Checks draft ownership based on the draft's project membership/role context."""
    query = select(GenerativeDraftModel).where(GenerativeDraftModel.draft_id == draft_id)
    res = await session.execute(query)
    draft = res.scalar()
    if not draft:
        raise HTTPException(status_code=404, detail="draft_not_found")

    if draft.project_id is not None:
        proj_query = select(ProjectModel.public_id).where(ProjectModel.id == draft.project_id)
        proj_res = await session.execute(proj_query)
        proj_public_id = proj_res.scalar()
        if not proj_public_id:
            raise HTTPException(status_code=404, detail="draft_not_found")

        # Confirming a draft requires editor role
        dep = require_project_role("editor")
        await dep(proj_public_id, user, session, request)
    else:
        # Onboarding drafts have no project; fallback to check creator
        if draft.owner_user_id != user.id:
            raise HTTPException(status_code=404, detail="draft_not_found")

    return draft


async def require_owned_choice_group(
    choice_group_id: int,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
) -> ChoiceGroupModel:
    """Verifies that the user is an active member of the parent project of this choice group."""
    query = (
        select(ChoiceGroupModel, ProjectModel)
        .join(ProjectModel, ChoiceGroupModel.project_id == ProjectModel.id)
        .where(ChoiceGroupModel.id == choice_group_id)
    )
    res = await session.execute(query)
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="choice_group_not_found")
    group, project = row

    await require_project_member(project.public_id, user, session, request)
    return group


async def require_owned_choice(
    choice_id: int,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
) -> ChoiceModel:
    """Verifies that the user is an active member of the parent project of this choice."""
    query = (
        select(ChoiceModel, ProjectModel)
        .join(ChoiceGroupModel, ChoiceModel.choice_group_id == ChoiceGroupModel.id)
        .join(ProjectModel, ChoiceGroupModel.project_id == ProjectModel.id)
        .where(ChoiceModel.id == choice_id)
    )
    res = await session.execute(query)
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="choice_not_found")
    choice, project = row

    await require_project_member(project.public_id, user, session, request)
    return choice


async def require_owned_ai_add_session(
    session_id: int,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
) -> AIAddSessionModel:
    """Verifies project access for the parent project of this AI Add session.

    If request method is GET, checks membership. Otherwise, checks editor role.
    """
    query = (
        select(AIAddSessionModel, ProjectModel)
        .join(ProjectModel, AIAddSessionModel.project_id == ProjectModel.id)
        .where(AIAddSessionModel.id == session_id)
    )
    res = await session.execute(query)
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="session_not_found")
    ai_session, project = row

    if request is not None and request.method == "GET":
        await require_project_member(project.public_id, user, session, request)
    else:
        dep = require_project_role("editor")
        await dep(project.public_id, user, session, request)
    return ai_session


async def require_owned_choice_group_draft(
    group_id: str,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
) -> GenerativeDraftModel:
    return await require_owned_generative_draft(group_id, user, session, request)
