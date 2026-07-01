from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.dependencies.auth import get_current_user
from backend.database.database import get_session
from backend.database.model import UserModel, ProjectModel
from backend.api.dependencies.project_access import (
    require_project_member,
    require_project_role,
)
from backend.api.dependencies.actor_context import get_actor_context
from backend.core.actor_context import ActorContext
from backend.api.modules.project_lifecycle.application.members_service import ProjectMemberService
from backend.api.modules.project_lifecycle.schemas.members import (
    ProjectMemberResponse,
    ProjectMemberAddRequest,
    ProjectMemberUpdateRequest,
)

router = APIRouter(
    prefix="/api/projects/{project_id}/members",
    tags=["project_members"],
)

_service = ProjectMemberService()


@router.get("", response_model=list[ProjectMemberResponse])
async def list_members(
    project_id: str,
    owned_project: ProjectModel = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
):
    """List all members of the project."""
    members = await _service.list_members(project_id=owned_project.id, session=session)
    return [
        ProjectMemberResponse(
            member_id=m.id,
            user_id=m.user_id,
            email=m.user.email,
            role=m.role,
            status=m.status,
            joined_at=m.joined_at,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in members
    ]


@router.post("", response_model=ProjectMemberResponse)
async def add_member(
    project_id: str,
    body: ProjectMemberAddRequest,
    actor: ActorContext = Depends(get_actor_context),
    owned_project: ProjectModel = Depends(require_project_role("admin")),
    session: AsyncSession = Depends(get_session),
):
    """Add a new member to the project."""
    try:
        m = await _service.add_member(
            project_id=owned_project.id,
            email=body.email,
            role=body.role,
            actor=actor,
            session=session,
        )
        # Fetch with user loaded
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        res = await session.execute(
            select(m.__class__)
            .options(selectinload(m.__class__.user))
            .where(m.__class__.id == m.id)
        )
        m_loaded = res.scalar_one()
        return ProjectMemberResponse(
            member_id=m_loaded.id,
            user_id=m_loaded.user_id,
            email=m_loaded.user.email,
            role=m_loaded.role,
            status=m_loaded.status,
            joined_at=m_loaded.joined_at,
            created_at=m_loaded.created_at,
            updated_at=m_loaded.updated_at,
        )
    except ValueError as e:
        err_msg = str(e)
        if err_msg == "user_not_found":
            raise HTTPException(status_code=404, detail="user_not_found")
        if err_msg == "member_already_exists":
            raise HTTPException(status_code=400, detail="member_already_exists")
        raise HTTPException(status_code=400, detail=err_msg)


@router.patch("/{member_id}", response_model=ProjectMemberResponse)
async def update_member(
    project_id: str,
    member_id: int,
    body: ProjectMemberUpdateRequest,
    actor: ActorContext = Depends(get_actor_context),
    owned_project: ProjectModel = Depends(require_project_role("admin")),
    session: AsyncSession = Depends(get_session),
):
    """Update a project member's role or status."""
    try:
        m = await _service.update_member(
            project_id=owned_project.id,
            member_id=member_id,
            role=body.role,
            status=body.status,
            actor=actor,
            session=session,
        )
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        res = await session.execute(
            select(m.__class__)
            .options(selectinload(m.__class__.user))
            .where(m.__class__.id == m.id)
        )
        m_loaded = res.scalar_one()
        return ProjectMemberResponse(
            member_id=m_loaded.id,
            user_id=m_loaded.user_id,
            email=m_loaded.user.email,
            role=m_loaded.role,
            status=m_loaded.status,
            joined_at=m_loaded.joined_at,
            created_at=m_loaded.created_at,
            updated_at=m_loaded.updated_at,
        )
    except ValueError as e:
        err_msg = str(e)
        if err_msg == "member_not_found":
            raise HTTPException(status_code=404, detail="member_not_found")
        if err_msg == "cannot_remove_last_owner":
            raise HTTPException(status_code=400, detail="cannot_remove_last_owner")
        raise HTTPException(status_code=400, detail=err_msg)


@router.delete("/{member_id}")
async def remove_member(
    project_id: str,
    member_id: int,
    actor: ActorContext = Depends(get_actor_context),
    owned_project: ProjectModel = Depends(require_project_role("admin")),
    session: AsyncSession = Depends(get_session),
):
    """Remove a project member (mark status as removed)."""
    try:
        await _service.remove_member(
            project_id=owned_project.id,
            member_id=member_id,
            actor=actor,
            session=session,
        )
        return {"message": "member_removed"}
    except ValueError as e:
        err_msg = str(e)
        if err_msg == "member_not_found":
            raise HTTPException(status_code=404, detail="member_not_found")
        if err_msg == "cannot_remove_last_owner":
            raise HTTPException(status_code=400, detail="cannot_remove_last_owner")
        raise HTTPException(status_code=400, detail=err_msg)
