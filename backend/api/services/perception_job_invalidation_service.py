from sqlalchemy import select

from backend.schemas import PerceptionJobStatus


async def mark_perception_jobs_stale(
    project_id: int,
    stages: set[str],
    session,
) -> None:
    from backend.database.model import PerceptionJobModel

    if not stages:
        return

    result = await session.execute(
        select(PerceptionJobModel).where(
            PerceptionJobModel.project_id == project_id,
            PerceptionJobModel.stage.in_(stages),
            PerceptionJobModel.status != PerceptionJobStatus.STALE.value,
        )
    )

    for job in result.scalars().all():
        job.status = PerceptionJobStatus.STALE.value
