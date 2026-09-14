"""Step deletion application helpers.

This module handles step loading, position normalization, and cascading rule link
cleanup when a flow step is deleted.
"""

from __future__ import annotations

from sqlalchemy import delete, select

from backend.database.model import FlowStepModel, FlowTransitionModel, RuleLinkModel


async def load_flow_step_to_delete(
    session,
    flow_id: int,
    step_id: int,
    workspace_id: int,
) -> FlowStepModel:
    """Load flow step model for deletion, verifying boundaries."""
    stmt = select(FlowStepModel).where(
        FlowStepModel.flow_id == flow_id,
        FlowStepModel.id == step_id,
    )
    stmt = stmt.where(FlowStepModel.workspace_id == workspace_id)
    result = await session.execute(stmt)
    step = result.scalar_one_or_none()
    if step is None:
        raise ValueError("flow_step_not_found")
    return step


async def cleanup_step_transition_rule_links(session, step_id: int) -> None:
    """Clean up rule links pointing to transitions connected to the deleted step."""
    trans_stmt = select(FlowTransitionModel.logical_uuid).where(
        (FlowTransitionModel.source_step_id == step_id)
        | (FlowTransitionModel.target_step_id == step_id)
    )
    res = await session.execute(trans_stmt)
    trans_uuids = res.scalars().all()
    if trans_uuids:
        await session.execute(
            delete(RuleLinkModel).where(
                RuleLinkModel.target_kind == "flow_transition",
                RuleLinkModel.target_logical_uuid.in_(trans_uuids),
            )
        )


async def normalize_flow_step_positions(session, flow_id: int) -> None:
    """Re-index step positions to maintain contiguous 1-based order."""
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
