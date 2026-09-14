from dataclasses import dataclass, field

from sqlalchemy import select

from backend.database.model import (
    FlowModel,
    FlowStepModel,
    FlowTransitionModel,
    flow_feature_table,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    flow_step_output_business_object_table,
)

from .types import FlowIssueItem, FlowStepIssueItem, FlowTransitionIssueItem


def _append_value(mapping: dict[int, list[int]], key: int, value: int) -> None:
    mapping.setdefault(key, []).append(value)


async def _load_flow_feature_map(
    flow_ids: list[int],
    session,
) -> dict[int, list[int]]:
    result = await session.execute(
        select(
            flow_feature_table.c.flow_id,
            flow_feature_table.c.feature_id,
        ).where(flow_feature_table.c.flow_id.in_(flow_ids))
    )
    feature_ids_map: dict[int, list[int]] = {}
    for flow_id, feature_id in result.all():
        _append_value(feature_ids_map, flow_id, feature_id)
    return feature_ids_map


@dataclass
class _StepAssociations:
    actor_ids: dict[int, list[int]] = field(default_factory=dict)
    input_object_ids: dict[int, list[int]] = field(default_factory=dict)
    output_object_ids: dict[int, list[int]] = field(default_factory=dict)


async def _load_step_associations(
    step_ids: list[int],
    session,
) -> _StepAssociations:
    associations = _StepAssociations()
    if not step_ids:
        return associations
    actor_result = await session.execute(
        select(
            flow_step_actor_table.c.flow_step_id,
            flow_step_actor_table.c.actor_id,
        ).where(flow_step_actor_table.c.flow_step_id.in_(step_ids))
    )
    for step_id, actor_id in actor_result.all():
        _append_value(associations.actor_ids, step_id, actor_id)

    input_result = await session.execute(
        select(
            flow_step_input_business_object_table.c.flow_step_id,
            flow_step_input_business_object_table.c.business_object_id,
        ).where(
            flow_step_input_business_object_table.c.flow_step_id.in_(
                step_ids
            )
        )
    )
    for step_id, object_id in input_result.all():
        _append_value(associations.input_object_ids, step_id, object_id)

    output_result = await session.execute(
        select(
            flow_step_output_business_object_table.c.flow_step_id,
            flow_step_output_business_object_table.c.business_object_id,
        ).where(
            flow_step_output_business_object_table.c.flow_step_id.in_(
                step_ids
            )
        )
    )
    for step_id, object_id in output_result.all():
        _append_value(associations.output_object_ids, step_id, object_id)

    return associations


async def _load_flow_steps(
    flow_ids: list[int],
    session,
) -> dict[int, list[FlowStepIssueItem]]:
    result = await session.execute(
        select(FlowStepModel).where(FlowStepModel.flow_id.in_(flow_ids))
    )
    step_models = result.scalars().all()
    associations = await _load_step_associations(
        [step.id for step in step_models],
        session,
    )
    steps_map: dict[int, list[FlowStepIssueItem]] = {}
    for step in step_models:
        steps_map.setdefault(step.flow_id, []).append(
            FlowStepIssueItem(
                step_id=step.id,
                flow_id=step.flow_id,
                position=step.position,
                name=step.name,
                description=step.description,
                step_type=step.step_type,
                actor_ids=associations.actor_ids.get(step.id, []),
                input_business_object_ids=(
                    associations.input_object_ids.get(step.id, [])
                ),
                output_business_object_ids=(
                    associations.output_object_ids.get(step.id, [])
                ),
                logical_uuid=step.logical_uuid,
            )
        )
    return steps_map


async def load_issue_flows(
    project_id: int,
    session,
    workspace_id: int,
) -> list[FlowIssueItem]:
    stmt = select(FlowModel).where(
        FlowModel.project_id == project_id,
        FlowModel.workspace_id == workspace_id,
    )
    result = await session.execute(stmt)
    flow_models = result.scalars().all()
    flow_ids = [flow.id for flow in flow_models]
    if not flow_ids:
        return []
    feature_ids_map = await _load_flow_feature_map(flow_ids, session)
    steps_map = await _load_flow_steps(flow_ids, session)
    transitions_map = await _load_flow_transitions(flow_ids, session)
    return [
        FlowIssueItem(
            flow_id=flow.id,
            name=flow.name,
            description=flow.description,
            confirmation_status=flow.confirmation_status,
            feature_ids=feature_ids_map.get(flow.id, []),
            steps=sorted(
                steps_map.get(flow.id, []),
                key=lambda item: item.position,
            ),
            transitions=sorted(
                transitions_map.get(flow.id, []),
                key=lambda item: item.position,
            ),
            logical_uuid=flow.logical_uuid,
        )
        for flow in flow_models
    ]


async def _load_flow_transitions(
    flow_ids: list[int],
    session,
) -> dict[int, list[FlowTransitionIssueItem]]:
    result = await session.execute(
        select(FlowTransitionModel).where(FlowTransitionModel.flow_id.in_(flow_ids))
    )
    transitions = result.scalars().all()
    trans_map: dict[int, list[FlowTransitionIssueItem]] = {}
    for trans in transitions:
        trans_map.setdefault(trans.flow_id, []).append(
            FlowTransitionIssueItem(
                transition_id=trans.id,
                flow_id=trans.flow_id,
                source_step_id=trans.source_step_id,
                target_step_id=trans.target_step_id,
                condition_text=trans.condition_text or "",
                label=trans.label or "",
                is_default=trans.is_default,
                position=trans.position,
                semantic_tags=trans.semantic_tags or [],
                logical_uuid=trans.logical_uuid,
            )
        )
    return trans_map
