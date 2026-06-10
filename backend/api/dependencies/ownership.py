from fastapi import Depends, HTTPException
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


async def require_owned_project(
    project_id: str,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProjectModel:
    query = select(ProjectModel).where(
        ProjectModel.public_id == project_id, ProjectModel.owner_user_id == user.id
    )
    res = await session.execute(query)
    project = res.scalar()
    if not project:
        raise HTTPException(status_code=404, detail="project_not_found")
    return project


async def require_owned_generative_draft(
    draft_id: str,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GenerativeDraftModel:
    query = select(GenerativeDraftModel).where(
        GenerativeDraftModel.draft_id == draft_id,
        GenerativeDraftModel.owner_user_id == user.id,
    )
    res = await session.execute(query)
    draft = res.scalar()
    if not draft:
        raise HTTPException(status_code=404, detail="draft_not_found")

    if draft.project_id is not None:
        proj_query = select(ProjectModel.owner_user_id).where(ProjectModel.id == draft.project_id)
        proj_res = await session.execute(proj_query)
        proj_owner_id = proj_res.scalar()
        if proj_owner_id != user.id:
            raise HTTPException(status_code=404, detail="draft_not_found")

    return draft


async def require_owned_choice_group(
    choice_group_id: int,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChoiceGroupModel:
    query = (
        select(ChoiceGroupModel)
        .join(ProjectModel)
        .where(
            ChoiceGroupModel.id == choice_group_id,
            ProjectModel.owner_user_id == user.id,
        )
    )
    res = await session.execute(query)
    group = res.scalar()
    if not group:
        raise HTTPException(status_code=404, detail="choice_group_not_found")
    return group


async def require_owned_choice(
    choice_id: int,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChoiceModel:
    query = (
        select(ChoiceModel)
        .join(ChoiceGroupModel)
        .join(ProjectModel)
        .where(
            ChoiceModel.id == choice_id,
            ProjectModel.owner_user_id == user.id,
        )
    )
    res = await session.execute(query)
    choice = res.scalar()
    if not choice:
        raise HTTPException(status_code=404, detail="choice_not_found")
    return choice


async def require_owned_ai_add_session(
    session_id: int,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AIAddSessionModel:
    query = (
        select(AIAddSessionModel)
        .join(ProjectModel)
        .where(
            AIAddSessionModel.id == session_id,
            ProjectModel.owner_user_id == user.id,
        )
    )
    res = await session.execute(query)
    ai_session = res.scalar()
    if not ai_session:
        raise HTTPException(status_code=404, detail="session_not_found")
    return ai_session


async def require_owned_choice_group_draft(
    group_id: str,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GenerativeDraftModel:
    return await require_owned_generative_draft(group_id, user, session)
