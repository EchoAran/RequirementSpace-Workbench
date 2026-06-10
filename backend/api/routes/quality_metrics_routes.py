from backend.api.dependencies.ownership import require_owned_project
from backend.database.model import ProjectModel
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
    project_id: str,
    session: AsyncSession = Depends(get_session),
 owned_project: ProjectModel = Depends(require_owned_project)):
    return await get_repair_metrics(project_id=owned_project.id, session=session)
