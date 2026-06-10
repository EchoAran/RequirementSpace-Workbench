from backend.api.dependencies.ownership import require_owned_project
from backend.database.model import ProjectModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.crud_schema import (
    ScopeUpdateRequest,
    ScopeResponse,
)
from backend.api.services.scope_service import ScopeService
from backend.database.database import get_session

router = APIRouter(
    prefix="/api/projects/{project_id}/features/{feature_id}/scope",
    tags=["scope"],
)

scope_service = ScopeService()


@router.put("", response_model=ScopeResponse)
async def update_feature_scope(
    project_id: str,
    feature_id: int,
    request: ScopeUpdateRequest,
    session: AsyncSession = Depends(get_session),
 owned_project: ProjectModel = Depends(require_owned_project)):
    try:
        return await scope_service.update_scope(
            project_id=owned_project.id,
            feature_id=feature_id,
            req=request,
            session=session,
        )
    except ValueError as error:
        status = 404 if "not_found" in str(error) else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update feature scope: {error}",
        )
