from sqlalchemy import select

from backend.schemas import PerceptionJobStatus


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
        workspace_id: int,
    ) -> None:
        from backend.database.model import PerceptionJobModel

        stmt = select(PerceptionJobModel).where(
            PerceptionJobModel.project_id == project_id,
            PerceptionJobModel.stage == stage,
            PerceptionJobModel.perception_kind == perception_kind,
            PerceptionJobModel.target_type == target_type,
            PerceptionJobModel.target_id == target_id,
            PerceptionJobModel.context_hash != context_hash,
            PerceptionJobModel.workspace_id == workspace_id,
            PerceptionJobModel.status.in_(
                [
                    PerceptionJobStatus.DONE_EMPTY.value,
                    PerceptionJobStatus.DONE_WITH_SLOT.value,
                    PerceptionJobStatus.FAILED.value,
                ]
            ),
        )

        result = await session.execute(stmt)

        for job in result.scalars().all():
            job.status = PerceptionJobStatus.STALE.value

    @staticmethod
    async def mark_perception_jobs_stale(
        project_id: int,
        stages: set[str],
        session,
        workspace_id: int,
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
            PerceptionJobModel.workspace_id == workspace_id,
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
        workspace_id: int,
    ) -> None:
        from backend.database.model import (
            ChoiceGroupModel,
            PerceptionJobModel,
            PerceptionSlotModel,
        )

        slot_stmt = select(PerceptionSlotModel).where(
            PerceptionSlotModel.project_id == project_id,
            PerceptionSlotModel.workspace_id == workspace_id,
        )

        slot_result = await session.execute(slot_stmt)
        slots = slot_result.scalars().all()
        if not slots:
            return

        for slot in slots:
            job_stmt = select(PerceptionJobModel).where(
                PerceptionJobModel.id == slot.id,
                PerceptionJobModel.project_id == project_id,
                PerceptionJobModel.stage.in_(stages),
                PerceptionJobModel.workspace_id == workspace_id,
            )

            job_result = await session.execute(job_stmt)
            slot_job = job_result.scalar_one_or_none()
            if slot_job is None:
                continue

            if (
                perception_kinds is not None
                and slot_job.perception_kind not in perception_kinds
            ):
                continue

            group_result = await session.execute(select(ChoiceGroupModel).where(
                    ChoiceGroupModel.project_id == project_id,
                    ChoiceGroupModel.slot_id == slot.id,
                ),)
            for group in group_result.scalars().all():
                if group.status == "open":
                    group.status = "resolved"
                group.slot_id = None

            await session.delete(slot)
