from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.services.scope_service import ScopeService
from backend.database.database import get_session

router = APIRouter(
    prefix="/api/projects/{project_id}/scope",
    tags=["project_scope"],
)

scope_service = ScopeService()


@router.post("/skip_kano")
async def skip_kano(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await scope_service.set_kano_status(
            project_id=project_id,
            status="skipped",
            session=session,
        )
    except ValueError as error:
        status = 404 if "not_found" in str(error) else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to skip Kano analysis: {error}",
        )


@router.post("/reset_kano")
async def reset_kano(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await scope_service.set_kano_status(
            project_id=project_id,
            status="missing",
            session=session,
        )
    except ValueError as error:
        status = 404 if "not_found" in str(error) else 400
        raise HTTPException(
            status_code=status,
            detail=str(error),
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset Kano analysis: {error}",
        )
