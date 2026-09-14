from .batch import decide_batch_task
from .common import _load_decidable_task
from .conflict import decide_conflict_task
from .flow_refinement_choice import decide_flow_refinement_choice_task
from .single import decide_single_task


async def decide_task(
    session,
    project_id: int,
    task_id: int,
    user_id: int,
    is_admin_or_owner: bool,
    decision: str,
    note: str | None,
    audit_service,
    snapshot_service,
    now,
):
    task, is_assignee = await _load_decidable_task(
        session,
        project_id,
        task_id,
        user_id,
        is_admin_or_owner,
    )
    common_arguments = (
        session,
        task,
        project_id,
        is_assignee,
        is_admin_or_owner,
        decision,
        note,
        audit_service,
    )
    if task.task_type == "confirm_nodes":
        return await decide_batch_task(
            *common_arguments,
            snapshot_service,
            now,
        )
    if task.target_type == "flow_refinement_choice":
        return await decide_flow_refinement_choice_task(
            *common_arguments,
            snapshot_service,
            now,
        )
    if task.task_type in ("resolve_conflict", "review_draft"):
        return await decide_conflict_task(
            *common_arguments,
            now,
        )
    return await decide_single_task(
        *common_arguments,
        snapshot_service,
        now,
    )
