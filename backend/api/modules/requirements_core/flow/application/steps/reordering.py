"""Step reordering application helpers.

This module handles step loading, validation, and safe position re-indexing
during flow step reorder operations, keeping topology and transitions intact.
"""

from __future__ import annotations

from sqlalchemy import select

from backend.database.model import FlowModel, FlowStepModel


async def load_flow_for_reorder(session, project_id: int, flow_id: int) -> FlowModel:
    """Load flow model verifying ownership and project boundary."""
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
    """Validate that reordered step IDs match existing steps in the flow."""
    if not step_ids:
        raise ValueError("step_ids_cannot_be_empty")
    if len(step_ids) != len(set(step_ids)):
        raise ValueError("duplicate_step_ids")

    result = await session.execute(
        select(FlowStepModel).where(FlowStepModel.flow_id == flow_id)
    )
    steps_by_id = {step.id: step for step in result.scalars().all()}
    if set(step_ids) != set(steps_by_id):
        raise ValueError("invalid_step_ids_match")
    return steps_by_id


async def apply_reordered_positions(
    session,
    step_ids: list[int],
    steps_by_id: dict[int, FlowStepModel],
) -> None:
    """Apply updated 1-based position ordering using temporary negative indexing."""
    for index, step_id in enumerate(step_ids):
        steps_by_id[step_id].position = -(index + 1)
    await session.flush()

    for index, step_id in enumerate(step_ids):
        steps_by_id[step_id].position = index + 1
    await session.flush()
