from sqlalchemy import select

from backend.schemas import PerceptionJobStatus


async def _exec_stmt(session, stmt):
    res = session.execute(stmt)
    if hasattr(res, "__await__"):
        return await res
    return res


class PerceptionJobInvalidator:
    @staticmethod
    async def _mark_stale_jobs(
        project_id: int,
        stage: str,
        perception_kind: str,
        target_type: str,
        target_id: str,
        context_hash: str,
        session,
        workspace_id: int | None = None,
    ) -> None:
        from backend.database.model import PerceptionJobModel

        stmt = select(PerceptionJobModel).where(
            PerceptionJobModel.project_id == project_id,
            PerceptionJobModel.stage == stage,
            PerceptionJobModel.perception_kind == perception_kind,
            PerceptionJobModel.target_type == target_type,
            PerceptionJobModel.target_id == target_id,
            PerceptionJobModel.context_hash != context_hash,
            PerceptionJobModel.status.in_(
                [
                    PerceptionJobStatus.DONE_EMPTY.value,
                    PerceptionJobStatus.DONE_WITH_SLOT.value,
                    PerceptionJobStatus.FAILED.value,
                ]
            ),
        )
        if workspace_id is not None:
            stmt = stmt.where(PerceptionJobModel.workspace_id == workspace_id)
        else:
            stmt = stmt.where(PerceptionJobModel.workspace_id.is_(None))

        result = await _exec_stmt(session, stmt)

        for job in result.scalars().all():
            job.status = PerceptionJobStatus.STALE.value

    @staticmethod
    async def mark_perception_jobs_stale(
        project_id: int,
        stages: set[str],
        session,
        perception_kinds: set[str] | None = None,
        clear_active_slot: bool = True,
        workspace_id: int | None = None,
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
        if workspace_id is not None:
            stale_stmt = stale_stmt.where(PerceptionJobModel.workspace_id == workspace_id)
        else:
            stale_stmt = stale_stmt.where(PerceptionJobModel.workspace_id.is_(None))
        if normalized_kinds is not None:
            stale_stmt = stale_stmt.where(
                PerceptionJobModel.perception_kind.in_(normalized_kinds)
            )

        result = await _exec_stmt(session, stale_stmt)

        for job in result.scalars().all():
            job.status = PerceptionJobStatus.STALE.value

        if clear_active_slot:
            await PerceptionJobInvalidator._clear_active_slot_if_affected(
                project_id=project_id,
                stages=stages,
                perception_kinds=normalized_kinds,
                session=session,
                workspace_id=workspace_id,
            )

    @staticmethod
    async def _clear_active_slot_if_affected(
        project_id: int,
        stages: set[str],
        perception_kinds: set[str] | None,
        session,
        workspace_id: int | None = None,
    ) -> None:
        from backend.database.model import (
            ChoiceGroupModel,
            PerceptionJobModel,
            PerceptionSlotModel,
        )

        slot_stmt = select(PerceptionSlotModel).where(
            PerceptionSlotModel.project_id == project_id,
        )
        if workspace_id is not None:
            slot_stmt = slot_stmt.where(PerceptionSlotModel.workspace_id == workspace_id)
        else:
            slot_stmt = slot_stmt.where(PerceptionSlotModel.workspace_id.is_(None))

        slot_result = await _exec_stmt(session, slot_stmt)
        slots = slot_result.scalars().all()
        if not slots:
            return

        for slot in slots:
            job_stmt = select(PerceptionJobModel).where(
                PerceptionJobModel.id == slot.id,
                PerceptionJobModel.project_id == project_id,
                PerceptionJobModel.stage.in_(stages),
            )
            if workspace_id is not None:
                job_stmt = job_stmt.where(PerceptionJobModel.workspace_id == workspace_id)
            else:
                job_stmt = job_stmt.where(PerceptionJobModel.workspace_id.is_(None))

            job_result = await _exec_stmt(session, job_stmt)
            slot_job = job_result.scalar_one_or_none()
            if slot_job is None:
                continue

            if (
                perception_kinds is not None
                and slot_job.perception_kind not in perception_kinds
            ):
                continue

            group_result = await _exec_stmt(
                session,
                select(ChoiceGroupModel).where(
                    ChoiceGroupModel.project_id == project_id,
                    ChoiceGroupModel.slot_id == slot.id,
                ),
            )
            for group in group_result.scalars().all():
                if group.status == "open":
                    group.status = "resolved"
                group.slot_id = None

            await session.delete(slot)
