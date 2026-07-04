from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies.auth import get_current_user
from backend.database.database import get_session
from backend.database.model import (
    UserModel,
    ProjectModel,
    KnowledgeWorkspaceModel,
    KnowledgeDocumentModel,
)
from backend.api.dependencies.project_access import (
    require_project_member,
    require_project_role,
)

async def require_owned_knowledge_workspace(
    workspace_id: str,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> KnowledgeWorkspaceModel:
    """Verifies that the knowledge workspace exists and is owned by the current user."""
    query = select(KnowledgeWorkspaceModel).where(KnowledgeWorkspaceModel.public_id == workspace_id)
    res = await session.execute(query)
    workspace = res.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="workspace_not_found")
    
    if workspace.project_id is not None:
        proj_query = select(ProjectModel.public_id).where(ProjectModel.id == workspace.project_id)
        proj_res = await session.execute(proj_query)
        proj_public_id = proj_res.scalar_one_or_none()
        if not proj_public_id:
            raise HTTPException(status_code=404, detail="project_not_found")
        await require_project_member(proj_public_id, user, session)
    else:
        if workspace.owner_user_id != user.id:
            raise HTTPException(status_code=404, detail="workspace_not_found")
            
    return workspace

async def require_owned_knowledge_document(
    document_id: str,
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
) -> KnowledgeDocumentModel:
    """Verifies that the knowledge document exists and can be accessed by the current user."""
    query = select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.public_id == document_id)
    res = await session.execute(query)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="document_not_found")
    if doc.status == "deleted":
        raise HTTPException(status_code=404, detail="document_not_found")
        
    if doc.project_id is not None:
        proj_query = select(ProjectModel.public_id).where(ProjectModel.id == doc.project_id)
        proj_res = await session.execute(proj_query)
        proj_public_id = proj_res.scalar_one_or_none()
        if not proj_public_id:
            raise HTTPException(status_code=404, detail="project_not_found")
            
        if request is not None and request.method == "GET":
            await require_project_member(proj_public_id, user, session, request)
        else:
            await require_project_member(proj_public_id, user, session, request)
            cache_key = f"project_member:{proj_public_id}:{user.id}"
            cached = getattr(request.state, cache_key, None)
            if cached and cached is not False:
                member = cached[1]
                if request is not None and request.method == "DELETE":
                    if doc.owner_user_id == user.id or member.role in ("owner", "admin"):
                        pass
                    else:
                        raise HTTPException(status_code=403, detail="insufficient_project_role")
                else:
                    if doc.owner_user_id == user.id or member.role in ("owner", "admin", "editor"):
                        pass
                    else:
                        raise HTTPException(status_code=403, detail="insufficient_project_role")
            else:
                raise HTTPException(status_code=403, detail="insufficient_project_role")
    else:
        if not doc.workspace_id:
            if doc.owner_user_id != user.id:
                raise HTTPException(status_code=404, detail="document_not_found")
        else:
            ws_query = select(KnowledgeWorkspaceModel).where(KnowledgeWorkspaceModel.id == doc.workspace_id)
            ws_res = await session.execute(ws_query)
            ws = ws_res.scalar_one_or_none()
            if not ws or ws.owner_user_id != user.id:
                raise HTTPException(status_code=404, detail="document_not_found")
                
    return doc
