from backend.api.modules.diagnosis_quality.perception.application.job_invalidator import PerceptionJobInvalidator


async def mark_perception_jobs_stale(
    project_id: int,
    stages: set[str],
    session,
    perception_kinds: set[str] | None = None,
    clear_active_slot: bool = True,
) -> None:
    await PerceptionJobInvalidator.mark_perception_jobs_stale(
        project_id=project_id,
        stages=stages,
        session=session,
        perception_kinds=perception_kinds,
        clear_active_slot=clear_active_slot,
    )


async def _clear_active_slot_if_affected(
    project_id: int,
    stages: set[str],
    perception_kinds: set[str] | None,
    session,
) -> None:
    await PerceptionJobInvalidator._clear_active_slot_if_affected(
        project_id=project_id,
        stages=stages,
        perception_kinds=perception_kinds,
        session=session,
    )
