from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.services.quality_metrics_service import get_repair_metrics
from backend.database.database import get_session


router = APIRouter(
    prefix="/api/projects/{project_id}",
    tags=["quality_metrics"],
)


@router.get("/quality-metrics")
async def list_quality_metrics(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    return await get_repair_metrics(project_id=project_id, session=session)
