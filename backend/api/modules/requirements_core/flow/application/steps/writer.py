"""Step writing and persistence application helpers.

This module handles step existence validation, position assignment, relationship
updates (actors, business objects), and state diff tracking for flow step mutations.
"""

from __future__ import annotations

from sqlalchemy import func, insert, select
from sqlalchemy.orm import selectinload

from backend.database.model import (
    ActorModel,
    BusinessObjectModel,
    FlowModel,
    FlowStepModel,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    flow_step_output_business_object_table,
)


async def ensure_flow_exists(
    session,
    project_id: int,
    flow_id: int,
    workspace_id: int,
) -> None:
    """Ensure the target flow exists in the project and workspace."""
    stmt = select(FlowModel).where(
        FlowModel.project_id == project_id,
        FlowModel.id == flow_id,
    )
    stmt = stmt.where(FlowModel.workspace_id == workspace_id)
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise ValueError("flow_not_found")


async def get_next_position_index(session, flow_id: int) -> int:
    """Calculate the next 1-based sequential position index for a new step."""
    max_position = await session.scalar(
        select(func.coalesce(func.max(FlowStepModel.position), 0)).where(
            FlowStepModel.flow_id == flow_id
        )
    )
    return int(max_position or 0) + 1


async def _validated_ids(session, statement, requested_ids: list[int], error_code: str) -> list[int]:
    """Validate that all requested IDs exist in database, raising ValueError on mismatch."""
    valid_ids = (await session.scalars(statement)).all()
    if len(valid_ids) != len(set(requested_ids)):
        raise ValueError(error_code)
    return list(valid_ids)


async def _write_actor_links(
    session,
    project_id: int,
    step_id: int,
    actor_ids: list[int],
    workspace_id: int,
) -> None:
    """Insert associations between flow step and actors."""
    if not actor_ids:
        return
    stmt = select(ActorModel.id).where(
        ActorModel.project_id == project_id,
        ActorModel.id.in_(actor_ids),
    )
    stmt = stmt.where(ActorModel.workspace_id == workspace_id)
    valid_ids = await _validated_ids(
        session,
        stmt,
        actor_ids,
        "invalid_actor_ids",
    )
    await session.execute(
        insert(flow_step_actor_table),
        [
            {
                "flow_step_id": step_id,
                "actor_id": actor_id,
            }
            for actor_id in valid_ids
        ],
    )


async def _write_business_object_links(
    session,
    *,
    project_id: int,
    step_id: int,
    business_object_ids: list[int],
    table,
    error_code: str,
    workspace_id: int,
) -> None:
    """Insert associations between flow step and business objects."""
    if not business_object_ids:
        return
    stmt = select(BusinessObjectModel.id).where(
        BusinessObjectModel.project_id == project_id,
        BusinessObjectModel.id.in_(business_object_ids),
    )
    stmt = stmt.where(BusinessObjectModel.workspace_id == workspace_id)
    valid_ids = await _validated_ids(
        session,
        stmt,
        business_object_ids,
        error_code,
    )
    await session.execute(
        insert(table),
        [
            {
                "flow_step_id": step_id,
                "business_object_id": business_object_id,
            }
            for business_object_id in valid_ids
        ],
    )


async def write_flow_step_links(
    session,
    *,
    project_id: int,
    flow_id: int,
    step_id: int,
    actor_ids: list[int],
    input_business_object_ids: list[int],
    output_business_object_ids: list[int],
    workspace_id: int,
) -> None:
    """Write actor and business object associations for a newly created step."""
    await _write_actor_links(
        session,
        project_id,
        step_id,
        actor_ids,
        workspace_id=workspace_id,
    )
    await _write_business_object_links(
        session,
        project_id=project_id,
        step_id=step_id,
        business_object_ids=input_business_object_ids,
        table=flow_step_input_business_object_table,
        error_code="invalid_input_business_object_ids",
        workspace_id=workspace_id,
    )
    await _write_business_object_links(
        session,
        project_id=project_id,
        step_id=step_id,
        business_object_ids=output_business_object_ids,
        table=flow_step_output_business_object_table,
        error_code="invalid_output_business_object_ids",
        workspace_id=workspace_id,
    )


async def load_flow_step(
    session,
    step_id: int,
) -> FlowStepModel:
    """Load flow step entity with eager-loaded actors and business objects."""
    stmt = select(FlowStepModel).where(
        FlowStepModel.id == step_id,
    )
    result = await session.execute(
        stmt
        .options(
            selectinload(FlowStepModel.actors),
            selectinload(FlowStepModel.input_business_objects),
            selectinload(FlowStepModel.output_business_objects),
        )
    )
    return result.scalar_one()


async def load_flow_step_for_update(
    session,
    flow_id: int,
    step_id: int,
    workspace_id: int,
) -> FlowStepModel:
    """Load flow step entity for update mutation with eager loading."""
    stmt = (
        select(FlowStepModel)
        .where(
            FlowStepModel.flow_id == flow_id,
            FlowStepModel.id == step_id,
        )
        .options(
            selectinload(FlowStepModel.actors),
            selectinload(FlowStepModel.input_business_objects),
            selectinload(FlowStepModel.output_business_objects),
        )
    )
    stmt = stmt.where(FlowStepModel.workspace_id == workspace_id)
    result = await session.execute(stmt)
    step = result.scalar_one_or_none()
    if step is None:
        raise ValueError("flow_step_not_found")
    return step


def capture_flow_step_state(step: FlowStepModel) -> dict:
    """Capture snapshot of step attributes for auditing diff generation."""
    return {
        "name": step.name,
        "description": step.description,
        "step_type": step.step_type,
        "actor_ids": [actor.id for actor in step.actors],
        "input_business_object_ids": [
            business_object.id
            for business_object in step.input_business_objects
        ],
        "output_business_object_ids": [
            business_object.id
            for business_object in step.output_business_objects
        ],
    }


def apply_flow_step_scalar_updates(step: FlowStepModel, request) -> None:
    """Apply scalar field updates from request onto step model."""
    new_step_type = (
        request.step_type
        if request.step_type is not None
        else step.step_type
    )
    step.name = request.name if request.name is not None else step.name
    step.description = (
        request.description
        if request.description is not None
        else step.description
    )
    step.step_type = new_step_type


async def _replace_relationship(
    session,
    *,
    step: FlowStepModel,
    attribute: str,
    requested_ids: list[int] | None,
    statement,
    error_code: str,
) -> None:
    """Replace collection relationship if new IDs are provided in request."""
    if requested_ids is None:
        return
    if not requested_ids:
        setattr(step, attribute, [])
        return
    entities = (await session.scalars(statement)).all()
    if len(entities) != len(set(requested_ids)):
        raise ValueError(error_code)
    setattr(step, attribute, list(entities))


async def apply_flow_step_relationship_updates(
    session,
    *,
    project_id: int,
    flow_id: int,
    step: FlowStepModel,
    request,
    workspace_id: int,
) -> None:
    """Update actors and business objects relationships on the step."""
    actor_stmt = select(ActorModel).where(
        ActorModel.project_id == project_id,
        ActorModel.id.in_(request.actor_ids or []),
    )
    actor_stmt = actor_stmt.where(ActorModel.workspace_id == workspace_id)

    await _replace_relationship(
        session,
        step=step,
        attribute="actors",
        requested_ids=request.actor_ids,
        statement=actor_stmt,
        error_code="invalid_actor_ids",
    )

    in_bo_stmt = select(BusinessObjectModel).where(
        BusinessObjectModel.project_id == project_id,
        BusinessObjectModel.id.in_(
            request.input_business_object_ids or []
        ),
    )
    in_bo_stmt = in_bo_stmt.where(BusinessObjectModel.workspace_id == workspace_id)

    await _replace_relationship(
        session,
        step=step,
        attribute="input_business_objects",
        requested_ids=request.input_business_object_ids,
        statement=in_bo_stmt,
        error_code="invalid_input_business_object_ids",
    )

    out_bo_stmt = select(BusinessObjectModel).where(
        BusinessObjectModel.project_id == project_id,
        BusinessObjectModel.id.in_(
            request.output_business_object_ids or []
        ),
    )
    out_bo_stmt = out_bo_stmt.where(BusinessObjectModel.workspace_id == workspace_id)

    await _replace_relationship(
        session,
        step=step,
        attribute="output_business_objects",
        requested_ids=request.output_business_object_ids,
        statement=out_bo_stmt,
        error_code="invalid_output_business_object_ids",
    )


def build_flow_step_update_diff(before: dict, step: FlowStepModel) -> dict:
    """Compute dictionary diff between before snapshot and current step state."""
    after = capture_flow_step_state(step)
    return {
        field: {"before": before[field], "after": value}
        for field, value in after.items()
        if before[field] != value
    }
