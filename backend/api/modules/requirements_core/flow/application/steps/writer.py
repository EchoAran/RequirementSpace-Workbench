from sqlalchemy import func, insert, select
from sqlalchemy.orm import selectinload

from backend.database.model import (
    ActorModel,
    BusinessObjectModel,
    FlowModel,
    FlowStepModel,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    flow_step_next_table,
    flow_step_output_business_object_table,
)


async def ensure_flow_exists(
    session,
    project_id: int,
    flow_id: int,
) -> None:
    result = await session.execute(
        select(FlowModel).where(
            FlowModel.project_id == project_id,
            FlowModel.id == flow_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise ValueError("flow_not_found")


async def get_next_step_position(session, flow_id: int) -> int:
    result = await session.execute(
        select(func.max(FlowStepModel.position)).where(
            FlowStepModel.flow_id == flow_id
        )
    )
    maximum = result.scalar()
    return 1 if maximum is None else maximum + 1


async def _validated_ids(
    session,
    statement,
    requested_ids: list[int],
    error_code: str,
) -> list[int]:
    result = await session.execute(statement)
    valid_ids = result.scalars().all()
    if len(valid_ids) != len(requested_ids):
        raise ValueError(error_code)
    return valid_ids


async def _write_actor_links(
    session,
    project_id: int,
    step_id: int,
    actor_ids: list[int],
) -> None:
    if not actor_ids:
        return
    valid_ids = await _validated_ids(
        session,
        select(ActorModel.id).where(
            ActorModel.project_id == project_id,
            ActorModel.id.in_(actor_ids),
        ),
        actor_ids,
        "invalid_actor_ids",
    )
    await session.execute(
        insert(flow_step_actor_table),
        [
            {"flow_step_id": step_id, "actor_id": actor_id}
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
) -> None:
    if not business_object_ids:
        return
    valid_ids = await _validated_ids(
        session,
        select(BusinessObjectModel.id).where(
            BusinessObjectModel.project_id == project_id,
            BusinessObjectModel.id.in_(business_object_ids),
        ),
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


async def _write_next_step_links(
    session,
    flow_id: int,
    step_id: int,
    next_step_ids: list[int],
) -> None:
    if not next_step_ids:
        return
    valid_ids = await _validated_ids(
        session,
        select(FlowStepModel.id).where(
            FlowStepModel.flow_id == flow_id,
            FlowStepModel.id.in_(next_step_ids),
        ),
        next_step_ids,
        "invalid_next_step_ids",
    )
    await session.execute(
        insert(flow_step_next_table),
        [
            {
                "source_step_id": step_id,
                "target_step_id": target_step_id,
            }
            for target_step_id in valid_ids
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
    next_step_ids: list[int],
) -> None:
    await _write_actor_links(
        session,
        project_id,
        step_id,
        actor_ids,
    )
    await _write_business_object_links(
        session,
        project_id=project_id,
        step_id=step_id,
        business_object_ids=input_business_object_ids,
        table=flow_step_input_business_object_table,
        error_code="invalid_input_business_object_ids",
    )
    await _write_business_object_links(
        session,
        project_id=project_id,
        step_id=step_id,
        business_object_ids=output_business_object_ids,
        table=flow_step_output_business_object_table,
        error_code="invalid_output_business_object_ids",
    )
    await _write_next_step_links(
        session,
        flow_id,
        step_id,
        next_step_ids,
    )


async def load_flow_step(session, step_id: int):
    result = await session.execute(
        select(FlowStepModel)
        .where(FlowStepModel.id == step_id)
        .options(
            selectinload(FlowStepModel.actors),
            selectinload(FlowStepModel.input_business_objects),
            selectinload(FlowStepModel.output_business_objects),
            selectinload(FlowStepModel.next_steps),
        )
    )
    return result.scalar_one()


async def load_flow_step_for_update(session, flow_id: int, step_id: int):
    result = await session.execute(
        select(FlowStepModel)
        .where(
            FlowStepModel.flow_id == flow_id,
            FlowStepModel.id == step_id,
        )
        .options(
            selectinload(FlowStepModel.actors),
            selectinload(FlowStepModel.input_business_objects),
            selectinload(FlowStepModel.output_business_objects),
            selectinload(FlowStepModel.next_steps),
        )
    )
    step = result.scalar_one_or_none()
    if step is None:
        raise ValueError("flow_step_not_found")
    return step


def capture_flow_step_state(step) -> dict:
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
        "next_step_ids": [next_step.id for next_step in step.next_steps],
    }


def apply_flow_step_scalar_updates(step, request) -> None:
    new_step_type = (
        request.step_type
        if request.step_type is not None
        else step.step_type
    )
    new_actor_ids = (
        request.actor_ids
        if request.actor_ids is not None
        else [actor.id for actor in step.actors]
    )
    if new_step_type == "actorAction" and not new_actor_ids:
        raise ValueError("actor_ids_cannot_be_empty_for_actor_action")

    if request.name is not None:
        step.name = request.name
    if request.description is not None:
        step.description = request.description
    if request.step_type is not None:
        step.step_type = request.step_type


async def _validated_models(
    session,
    statement,
    requested_ids: list[int],
    error_code: str,
) -> list:
    result = await session.execute(statement)
    models = result.scalars().all()
    if len(models) != len(requested_ids):
        raise ValueError(error_code)
    return models


async def _replace_relationship(
    session,
    *,
    step,
    attribute: str,
    requested_ids: list[int] | None,
    statement,
    error_code: str,
) -> None:
    if requested_ids is None:
        return
    if not requested_ids:
        setattr(step, attribute, [])
        return
    models = await _validated_models(
        session,
        statement,
        requested_ids,
        error_code,
    )
    setattr(step, attribute, models)


async def apply_flow_step_relationship_updates(
    session,
    *,
    project_id: int,
    flow_id: int,
    step,
    request,
) -> None:
    await _replace_relationship(
        session,
        step=step,
        attribute="actors",
        requested_ids=request.actor_ids,
        statement=select(ActorModel).where(
            ActorModel.project_id == project_id,
            ActorModel.id.in_(request.actor_ids or []),
        ),
        error_code="invalid_actor_ids",
    )
    await _replace_relationship(
        session,
        step=step,
        attribute="input_business_objects",
        requested_ids=request.input_business_object_ids,
        statement=select(BusinessObjectModel).where(
            BusinessObjectModel.project_id == project_id,
            BusinessObjectModel.id.in_(
                request.input_business_object_ids or []
            ),
        ),
        error_code="invalid_input_business_object_ids",
    )
    await _replace_relationship(
        session,
        step=step,
        attribute="output_business_objects",
        requested_ids=request.output_business_object_ids,
        statement=select(BusinessObjectModel).where(
            BusinessObjectModel.project_id == project_id,
            BusinessObjectModel.id.in_(
                request.output_business_object_ids or []
            ),
        ),
        error_code="invalid_output_business_object_ids",
    )
    await _replace_relationship(
        session,
        step=step,
        attribute="next_steps",
        requested_ids=request.next_step_ids,
        statement=select(FlowStepModel).where(
            FlowStepModel.flow_id == flow_id,
            FlowStepModel.id.in_(request.next_step_ids or []),
        ),
        error_code="invalid_next_step_ids",
    )


def build_flow_step_update_diff(before: dict, step) -> dict:
    after = capture_flow_step_state(step)
    return {
        field: {"before": before[field], "after": value}
        for field, value in after.items()
        if before[field] != value
    }
