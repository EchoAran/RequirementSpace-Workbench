from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.model import (
    ActorModel,
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    FeatureModel,
    FeatureRelationModel,
    FlowModel,
    FlowStepModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    ScopeModel,
    feature_actor_table,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    flow_step_output_business_object_table,
)


@dataclass(frozen=True)
class WhatGateContext:
    actor_ids: set[int]
    leaf_feature_ids: list[int]
    feature_actor_map: dict[int, list[int]]
    feature_scenario_map: dict[int, list[int]]
    scenario_ids: list[int]
    ac_scenario_ids: set[int]


@dataclass(frozen=True)
class HowGateContext:
    flow_ids: list[int]
    steps: list[FlowStepModel]
    flows_with_steps: set[int]
    step_actor_map: dict[int, list[int]]
    step_input_bo_map: dict[int, list[int]]
    step_output_bo_map: dict[int, list[int]]
    business_object_ids: set[int]
    object_attribute_count: int


def _rows_to_map(rows) -> dict[int, list[int]]:
    result: dict[int, list[int]] = {}
    for owner_id, related_id in rows:
        result.setdefault(owner_id, []).append(related_id)
    return result


async def _load_leaf_feature_ids(
    project_id: int,
    session: AsyncSession,
) -> list[int]:
    features = (
        await session.execute(
            select(FeatureModel).where(
                FeatureModel.project_id == project_id
            )
        )
    ).scalars().all()
    feature_ids = [feature.id for feature in features]
    parent_ids: set[int] = set()
    if feature_ids:
        parent_ids = set(
            (
                await session.execute(
                    select(
                        FeatureRelationModel.parent_feature_id
                    ).where(
                        FeatureRelationModel.parent_feature_id.in_(
                            feature_ids
                        ),
                        FeatureRelationModel.child_feature_id.in_(
                            feature_ids
                        ),
                    )
                )
            ).scalars().all()
        )
    return [
        feature.id
        for feature in features
        if feature.id not in parent_ids
    ]


async def _load_scenario_data(
    project_id: int,
    session: AsyncSession,
) -> tuple[dict[int, list[int]], list[int], set[int]]:
    scenarios = (
        await session.execute(
            select(ScenarioModel)
            .join(
                FeatureModel,
                FeatureModel.id == ScenarioModel.feature_id,
            )
            .where(FeatureModel.project_id == project_id)
        )
    ).scalars().all()
    scenario_ids = [scenario.id for scenario in scenarios]
    feature_scenario_map: dict[int, list[int]] = {}
    for scenario in scenarios:
        feature_scenario_map.setdefault(
            scenario.feature_id,
            [],
        ).append(scenario.id)

    ac_scenario_ids: set[int] = set()
    if scenario_ids:
        ac_scenario_ids = set(
            (
                await session.execute(
                    select(
                        ScenarioAcceptanceCriterionModel.scenario_id
                    ).where(
                        ScenarioAcceptanceCriterionModel.scenario_id.in_(
                            scenario_ids
                        )
                    )
                )
            ).scalars().all()
        )
    return feature_scenario_map, scenario_ids, ac_scenario_ids


async def load_what_gate_context(
    project_id: int,
    session: AsyncSession,
) -> WhatGateContext:
    actor_ids = set(
        (
            await session.execute(
                select(ActorModel.id).where(
                    ActorModel.project_id == project_id
                )
            )
        ).scalars().all()
    )
    leaf_feature_ids = await _load_leaf_feature_ids(
        project_id,
        session,
    )
    feature_actor_rows = (
        await session.execute(
            select(
                feature_actor_table.c.feature_id,
                feature_actor_table.c.actor_id,
            )
            .join(
                FeatureModel,
                FeatureModel.id == feature_actor_table.c.feature_id,
            )
            .where(FeatureModel.project_id == project_id)
        )
    ).all()
    (
        feature_scenario_map,
        scenario_ids,
        ac_scenario_ids,
    ) = await _load_scenario_data(project_id, session)
    return WhatGateContext(
        actor_ids=actor_ids,
        leaf_feature_ids=leaf_feature_ids,
        feature_actor_map=_rows_to_map(feature_actor_rows),
        feature_scenario_map=feature_scenario_map,
        scenario_ids=scenario_ids,
        ac_scenario_ids=ac_scenario_ids,
    )


async def _load_step_link_map(
    table,
    related_id_column,
    step_ids: list[int],
    session: AsyncSession,
) -> dict[int, list[int]]:
    rows = (
        await session.execute(
            select(
                table.c.flow_step_id,
                related_id_column,
            ).where(table.c.flow_step_id.in_(step_ids))
        )
    ).all()
    return _rows_to_map(rows)


async def _load_steps_and_links(
    flow_ids: list[int],
    session: AsyncSession,
):
    if not flow_ids:
        return [], set(), {}, {}, {}

    steps = (
        await session.execute(
            select(FlowStepModel).where(
                FlowStepModel.flow_id.in_(flow_ids)
            )
        )
    ).scalars().all()
    flows_with_steps = {step.flow_id for step in steps}
    step_ids = [step.id for step in steps]
    if not step_ids:
        return steps, flows_with_steps, {}, {}, {}

    step_actor_map = await _load_step_link_map(
        flow_step_actor_table,
        flow_step_actor_table.c.actor_id,
        step_ids,
        session,
    )
    step_input_bo_map = await _load_step_link_map(
        flow_step_input_business_object_table,
        flow_step_input_business_object_table.c.business_object_id,
        step_ids,
        session,
    )
    step_output_bo_map = await _load_step_link_map(
        flow_step_output_business_object_table,
        flow_step_output_business_object_table.c.business_object_id,
        step_ids,
        session,
    )
    return (
        steps,
        flows_with_steps,
        step_actor_map,
        step_input_bo_map,
        step_output_bo_map,
    )


async def _load_business_object_data(
    project_id: int,
    session: AsyncSession,
) -> tuple[set[int], int]:
    business_object_ids = (
        await session.execute(
            select(BusinessObjectModel.id).where(
                BusinessObjectModel.project_id == project_id
            )
        )
    ).scalars().all()
    object_attribute_count = 0
    if business_object_ids:
        object_attribute_count = len(
            (
                await session.execute(
                    select(
                        BusinessObjectAttributeModel.id
                    ).where(
                        BusinessObjectAttributeModel.business_object_id.in_(
                            business_object_ids
                        )
                    )
                )
            ).scalars().all()
        )
    return set(business_object_ids), object_attribute_count


async def load_how_gate_context(
    project_id: int,
    session: AsyncSession,
) -> HowGateContext:
    flows = (
        await session.execute(
            select(FlowModel).where(
                FlowModel.project_id == project_id
            )
        )
    ).scalars().all()
    flow_ids = [flow.id for flow in flows]
    (
        steps,
        flows_with_steps,
        step_actor_map,
        step_input_bo_map,
        step_output_bo_map,
    ) = await _load_steps_and_links(flow_ids, session)
    (
        business_object_ids,
        object_attribute_count,
    ) = await _load_business_object_data(project_id, session)
    return HowGateContext(
        flow_ids=flow_ids,
        steps=steps,
        flows_with_steps=flows_with_steps,
        step_actor_map=step_actor_map,
        step_input_bo_map=step_input_bo_map,
        step_output_bo_map=step_output_bo_map,
        business_object_ids=business_object_ids,
        object_attribute_count=object_attribute_count,
    )


async def load_scoped_feature_ids(
    project_id: int,
    session: AsyncSession,
) -> set[int]:
    scopes = (
        await session.execute(
            select(ScopeModel)
            .join(FeatureModel)
            .where(FeatureModel.project_id == project_id)
        )
    ).scalars().all()
    return {
        scope.feature_id
        for scope in scopes
        if scope.status
    }
