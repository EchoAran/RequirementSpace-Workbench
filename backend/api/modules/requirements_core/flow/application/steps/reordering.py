from sqlalchemy import insert, select

from backend.database.model import FlowModel, FlowStepModel, flow_step_next_table


async def load_flow_for_reorder(session, project_id: int, flow_id: int):
    result = await session.execute(
        select(FlowModel).where(
            FlowModel.project_id == project_id,
            FlowModel.id == flow_id,
        )
    )
    flow = result.scalar_one_or_none()
    if flow is None:
        raise ValueError("flow_not_found")
    return flow


async def validate_reordered_steps(
    session,
    flow_id: int,
    step_ids: list[int],
) -> dict[int, FlowStepModel]:
    if not step_ids:
        raise ValueError("step_ids_cannot_be_empty")
    if len(step_ids) != len(set(step_ids)):
        raise ValueError("duplicate_step_ids")

    result = await session.execute(
        select(FlowStepModel).where(FlowStepModel.flow_id == flow_id)
    )
    steps_by_id = {
        step.id: step
        for step in result.scalars().all()
    }
    if set(step_ids) != set(steps_by_id):
        raise ValueError("invalid_step_ids_match")
    return steps_by_id


async def apply_reordered_positions(
    session,
    step_ids: list[int],
    steps_by_id: dict[int, FlowStepModel],
) -> None:
    for index, step_id in enumerate(step_ids):
        steps_by_id[step_id].position = -(index + 1)
    await session.flush()

    for index, step_id in enumerate(step_ids):
        steps_by_id[step_id].position = index + 1
    await session.flush()


async def replace_with_linear_topology(
    session,
    step_ids: list[int],
) -> None:
    await session.execute(
        flow_step_next_table.delete().where(
            flow_step_next_table.c.source_step_id.in_(step_ids)
        )
    )
    await session.flush()

    edges = [
        {
            "source_step_id": source_id,
            "target_step_id": target_id,
        }
        for source_id, target_id in zip(step_ids, step_ids[1:])
    ]
    if edges:
        await session.execute(insert(flow_step_next_table), edges)
    await session.flush()
