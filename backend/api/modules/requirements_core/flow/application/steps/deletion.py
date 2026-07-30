from sqlalchemy import insert, select

from backend.database.model import FlowStepModel, flow_step_next_table


async def load_flow_step_to_delete(session, flow_id: int, step_id: int):
    result = await session.execute(
        select(FlowStepModel).where(
            FlowStepModel.flow_id == flow_id,
            FlowStepModel.id == step_id,
        )
    )
    step = result.scalar_one_or_none()
    if step is None:
        raise ValueError("flow_step_not_found")
    return step


async def load_step_neighbors(
    session,
    step_id: int,
) -> tuple[list[int], list[int]]:
    predecessor_result = await session.execute(
        select(flow_step_next_table.c.source_step_id).where(
            flow_step_next_table.c.target_step_id == step_id
        )
    )
    successor_result = await session.execute(
        select(flow_step_next_table.c.target_step_id).where(
            flow_step_next_table.c.source_step_id == step_id
        )
    )
    return (
        predecessor_result.scalars().all(),
        successor_result.scalars().all(),
    )


async def bridge_step_neighbors(
    session,
    predecessors: list[int],
    successors: list[int],
) -> None:
    if not predecessors or not successors:
        return
    result = await session.execute(
        select(
            flow_step_next_table.c.source_step_id,
            flow_step_next_table.c.target_step_id,
        ).where(
            flow_step_next_table.c.source_step_id.in_(predecessors),
            flow_step_next_table.c.target_step_id.in_(successors),
        )
    )
    existing_edges = set(result.all())
    missing_edges = [
        {
            "source_step_id": predecessor_id,
            "target_step_id": successor_id,
        }
        for predecessor_id in predecessors
        for successor_id in successors
        if (predecessor_id, successor_id) not in existing_edges
    ]
    if missing_edges:
        await session.execute(insert(flow_step_next_table), missing_edges)


async def normalize_flow_step_positions(session, flow_id: int) -> None:
    result = await session.execute(
        select(FlowStepModel)
        .where(FlowStepModel.flow_id == flow_id)
        .order_by(FlowStepModel.position.asc())
    )
    steps = result.scalars().all()
    for index, step in enumerate(steps):
        step.position = -(index + 1)
    await session.flush()

    for index, step in enumerate(steps):
        step.position = index + 1
    await session.flush()
