import logging

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.dependencies.auth import get_current_user
from backend.core.logging import get_logger, log_event
from backend.core.logging.events import AUTH_PERMISSION_DENIED
from backend.database.database import get_session
from backend.database.model import (
    UserModel,
    ProjectModel,
    ProjectMemberModel,
    ProjectMemberStatus,
    ProjectMemberRole,
)

logger = get_logger(__name__)

async def require_project_member(
    project_id: str,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
) -> ProjectModel:
    """Ensures that the current user is an active member of the project.

    Raises 404 (not 403) for non-members to prevent project existence leakage.
    Caches the project and member details in request.state for subsequent checks.
    """
    if request is not None:
        cache_key = f"project_member:{project_id}:{user.id}"
        cached = getattr(request.state, cache_key, None)
        if cached is not None:
            if cached is False:
                raise HTTPException(status_code=404, detail="project_not_found")
            return cached[0]

    # Query project and project member status
    query = (
        select(ProjectModel, ProjectMemberModel)
        .outerjoin(
            ProjectMemberModel,
            (ProjectMemberModel.project_id == ProjectModel.id)
            & (ProjectMemberModel.user_id == user.id),
        )
        .where(ProjectModel.public_id == project_id)
    )
    res = await session.execute(query)
    row = res.first()
    if not row:
        if request is not None:
            setattr(request.state, f"project_member:{project_id}:{user.id}", False)
        raise HTTPException(status_code=404, detail="project_not_found")

    project, member = row

    # User must be an active member
    if not member or member.status != ProjectMemberStatus.ACTIVE.value:
        if request is not None:
            setattr(request.state, f"project_member:{project_id}:{user.id}", False)
        raise HTTPException(status_code=404, detail="project_not_found")

    if request is not None:
        setattr(request.state, f"project_member:{project_id}:{user.id}", (project, member))

    return project


def require_project_role(allowed_roles: list[str] | str):
    """Factory dependency checking if the user is an active project member with sufficient role.

    Hierarchical role checking is enforced:
    - "owner" -> only Owner can access.
    - "admin" -> Owner and Admin can access.
    - "editor" -> Owner, Admin, and Editor can access.
    - "reviewer" -> Owner, Admin, Editor, and Reviewer can access.
    - "viewer" -> Anyone in the project (Owner, Admin, Editor, Reviewer, Viewer).
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    # Map roles hierarchically
    role_hierarchy = {
        "owner": {"owner"},
        "admin": {"owner", "admin"},
        "editor": {"owner", "admin", "editor"},
        "reviewer": {"owner", "admin", "editor", "reviewer"},
        "viewer": {"owner", "admin", "editor", "reviewer", "viewer"},
    }

    resolved_allowed = set()
    for role in allowed_roles:
        if role in role_hierarchy:
            resolved_allowed.update(role_hierarchy[role])
        else:
            resolved_allowed.add(role)

    async def dependency(
        project_id: str,
        user: UserModel = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
        request: Request = None,
    ) -> ProjectModel:
        # 1. Verify membership (returns 404 if not member)
        project = await require_project_member(project_id, user, session, request)

        # 2. Retrieve cached membership from request state or DB
        member = None
        if request is not None:
            cache_key = f"project_member:{project_id}:{user.id}"
            cached = getattr(request.state, cache_key, None)
            if cached:
                _, member = cached
        
        if not member:
            query = select(ProjectMemberModel).where(
                ProjectMemberModel.project_id == project.id,
                ProjectMemberModel.user_id == user.id,
                ProjectMemberModel.status == ProjectMemberStatus.ACTIVE.value
            )
            res = await session.execute(query)
            member = res.scalar_one_or_none()
            
        if not member:
            raise HTTPException(status_code=404, detail="project_not_found")

        # 3. Check role (returns 403 if role insufficient)
        if member.role not in resolved_allowed:
            log_event(
                logger,
                logging.WARNING,
                "auth",
                AUTH_PERMISSION_DENIED,
                "Auth permission denied",
                user_id=user.id,
                project_id=project.id,
                required_role=",".join(allowed_roles),
                actual_role=member.role,
            )
            raise HTTPException(status_code=403, detail="insufficient_project_role")

        return project

    return dependency
