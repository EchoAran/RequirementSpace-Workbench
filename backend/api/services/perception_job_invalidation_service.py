from sqlalchemy import select

from backend.schemas import PerceptionJobStatus


async def mark_perception_jobs_stale(
    project_id: int,
    stages: set[str],
    session,
    perception_kinds: set[str] | None = None,
    clear_active_slot: bool = True,
) -> None:
    from backend.database.model import PerceptionJobModel

    if not stages:
        return

    normalized_kinds = (
        {kind.strip().upper() for kind in perception_kinds if kind.strip()}
        if perception_kinds is not None
        else None
    )

    stale_stmt = select(PerceptionJobModel).where(
        PerceptionJobModel.project_id == project_id,
        PerceptionJobModel.stage.in_(stages),
        PerceptionJobModel.status != PerceptionJobStatus.STALE.value,
    )
    if normalized_kinds is not None:
        stale_stmt = stale_stmt.where(
            PerceptionJobModel.perception_kind.in_(normalized_kinds)
        )

    result = await session.execute(stale_stmt)

    for job in result.scalars().all():
        job.status = PerceptionJobStatus.STALE.value

    if clear_active_slot:
        await _clear_active_slot_if_affected(
            project_id=project_id,
            stages=stages,
            perception_kinds=normalized_kinds,
            session=session,
        )


async def _clear_active_slot_if_affected(
    project_id: int,
    stages: set[str],
    perception_kinds: set[str] | None,
    session,
) -> None:
    from backend.database.model import (
        ChoiceGroupModel,
        PerceptionJobModel,
        PerceptionSlotModel,
    )

    slot_result = await session.execute(
        select(PerceptionSlotModel).where(
            PerceptionSlotModel.project_id == project_id,
        )
    )
    slot = slot_result.scalar_one_or_none()
    if slot is None:
        return

    job_result = await session.execute(
        select(PerceptionJobModel).where(
            PerceptionJobModel.id == slot.id,
            PerceptionJobModel.project_id == project_id,
            PerceptionJobModel.stage.in_(stages),
        )
    )
    slot_job = job_result.scalar_one_or_none()
    if slot_job is None:
        return

    if (
        perception_kinds is not None
        and slot_job.perception_kind not in perception_kinds
    ):
        return

    # Slot ids mirror perception job ids. Clear only the currently displayed
    # slot whose owning job belongs to the affected stage/kind.
    group_result = await session.execute(
        select(ChoiceGroupModel).where(
            ChoiceGroupModel.project_id == project_id,
            ChoiceGroupModel.slot_id == slot.id,
        )
    )
    for group in group_result.scalars().all():
        if group.status == "open":
            group.status = "resolved"
        group.slot_id = None

    await session.delete(slot)
