from dataclasses import dataclass

from sqlalchemy import or_, select

from backend.database.model import (
    ActorModel,
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    FeatureModel,
    FeatureRelationModel,
    FlowModel,
    FlowStepModel,
    ProjectModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    ScopeModel,
    feature_actor_table,
    flow_feature_table,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    flow_step_next_table,
    flow_step_output_business_object_table,
)


@dataclass
class SnapshotData:
    project: ProjectModel
    actors: list
    features: list
    scenarios: list
    flows: list
    business_objects: list
    scopes_by_feature: dict
    actors_by_feature: dict[int, list[int]]
    parent_by_child: dict[int, int]
    children_by_parent: dict[int, list[int]]
    criteria_by_scenario: dict[int, list]
    features_by_flow: dict[int, list[int]]
    steps_by_flow: dict[int, list]
    actors_by_step: dict[int, list[int]]
    inputs_by_step: dict[int, list[int]]
    outputs_by_step: dict[int, list[int]]
    next_by_step: dict[int, list[int]]
    attributes_by_object: dict[int, list]


def _pairs_to_map(rows) -> dict[int, list[int]]:
    mapping: dict[int, list[int]] = {}
    for key, value in rows:
        mapping.setdefault(key, []).append(value)
    return mapping


async def _load_primary_models(project_id: int, session):
    project = await session.get(ProjectModel, project_id)
    if not project:
        raise ValueError("project_not_found")
    model_queries = (
        select(ActorModel)
        .where(ActorModel.project_id == project_id)
        .order_by(ActorModel.id.asc()),
        select(FeatureModel)
        .where(FeatureModel.project_id == project_id)
        .order_by(FeatureModel.id.asc()),
        select(ScenarioModel)
        .where(ScenarioModel.project_id == project_id)
        .order_by(ScenarioModel.id.asc()),
        select(FlowModel)
        .where(FlowModel.project_id == project_id)
        .order_by(FlowModel.id.asc()),
        select(BusinessObjectModel)
        .where(BusinessObjectModel.project_id == project_id)
        .order_by(BusinessObjectModel.id.asc()),
    )
    loaded = []
    for query in model_queries:
        result = await session.execute(query)
        loaded.append(result.scalars().all())
    return project, *loaded


async def _load_feature_maps(
    project_id: int,
    feature_ids: list[int],
    session,
):
    scopes = (
        await session.execute(
            select(ScopeModel)
            .join(FeatureModel)
            .where(FeatureModel.project_id == project_id)
            .order_by(ScopeModel.id.asc())
        )
    ).scalars().all()
    actor_rows = (
        await session.execute(
            select(
                feature_actor_table.c.feature_id,
                feature_actor_table.c.actor_id,
            ).where(feature_actor_table.c.feature_id.in_(feature_ids))
        )
    ).all()
    relation_rows = (
        await session.execute(
            select(
                FeatureRelationModel.parent_feature_id,
                FeatureRelationModel.child_feature_id,
            ).where(
                or_(
                    FeatureRelationModel.parent_feature_id.in_(
                        feature_ids
                    ),
                    FeatureRelationModel.child_feature_id.in_(feature_ids),
                )
            )
        )
    ).all()
    return (
        {scope.feature_id: scope for scope in scopes},
        _pairs_to_map(actor_rows),
        {
            child_id: parent_id
            for parent_id, child_id in relation_rows
        },
        _pairs_to_map(relation_rows),
    )


async def _load_scenario_criteria(
    scenario_ids: list[int],
    session,
) -> dict[int, list]:
    criteria = (
        await session.execute(
            select(ScenarioAcceptanceCriterionModel)
            .where(
                ScenarioAcceptanceCriterionModel.scenario_id.in_(
                    scenario_ids
                )
            )
            .order_by(ScenarioAcceptanceCriterionModel.position.asc())
        )
    ).scalars().all()
    mapping = {}
    for criterion in criteria:
        mapping.setdefault(criterion.scenario_id, []).append(criterion)
    return mapping


async def _load_flow_maps(flow_ids: list[int], session):
    feature_rows = (
        await session.execute(
            select(
                flow_feature_table.c.flow_id,
                flow_feature_table.c.feature_id,
            ).where(flow_feature_table.c.flow_id.in_(flow_ids))
        )
    ).all()
    steps = (
        await session.execute(
            select(FlowStepModel)
            .where(FlowStepModel.flow_id.in_(flow_ids))
            .order_by(FlowStepModel.position.asc())
        )
    ).scalars().all()
    steps_by_flow = {}
    for step in steps:
        steps_by_flow.setdefault(step.flow_id, []).append(step)
    return _pairs_to_map(feature_rows), steps, steps_by_flow


async def _load_step_maps(step_ids: list[int], session):
    tables = (
        (
            flow_step_actor_table,
            flow_step_actor_table.c.actor_id,
        ),
        (
            flow_step_input_business_object_table,
            flow_step_input_business_object_table.c.business_object_id,
        ),
        (
            flow_step_output_business_object_table,
            flow_step_output_business_object_table.c.business_object_id,
        ),
        (
            flow_step_next_table,
            flow_step_next_table.c.target_step_id,
        ),
    )
    maps = []
    for table, value_column in tables:
        key_column = (
            table.c.source_step_id
            if table is flow_step_next_table
            else table.c.flow_step_id
        )
        rows = (
            await session.execute(
                select(key_column, value_column).where(
                    key_column.in_(step_ids)
                )
            )
        ).all()
        maps.append(_pairs_to_map(rows))
    return tuple(maps)


async def _load_attributes(
    object_ids: list[int],
    session,
) -> dict[int, list]:
    attributes = (
        await session.execute(
            select(BusinessObjectAttributeModel)
            .where(
                BusinessObjectAttributeModel.business_object_id.in_(
                    object_ids
                )
            )
            .order_by(BusinessObjectAttributeModel.id.asc())
        )
    ).scalars().all()
    mapping = {}
    for attribute in attributes:
        mapping.setdefault(
            attribute.business_object_id,
            [],
        ).append(attribute)
    return mapping


async def load_snapshot_data(
    project_id: int,
    session,
) -> SnapshotData:
    (
        project,
        actors,
        features,
        scenarios,
        flows,
        business_objects,
    ) = await _load_primary_models(project_id, session)
    feature_ids = [feature.id for feature in features]
    (
        scopes_by_feature,
        actors_by_feature,
        parent_by_child,
        children_by_parent,
    ) = await _load_feature_maps(project_id, feature_ids, session)
    criteria_by_scenario = await _load_scenario_criteria(
        [scenario.id for scenario in scenarios],
        session,
    )
    features_by_flow, steps, steps_by_flow = await _load_flow_maps(
        [flow.id for flow in flows],
        session,
    )
    (
        actors_by_step,
        inputs_by_step,
        outputs_by_step,
        next_by_step,
    ) = await _load_step_maps([step.id for step in steps], session)
    attributes_by_object = await _load_attributes(
        [item.id for item in business_objects],
        session,
    )
    return SnapshotData(
        project=project,
        actors=actors,
        features=features,
        scenarios=scenarios,
        flows=flows,
        business_objects=business_objects,
        scopes_by_feature=scopes_by_feature,
        actors_by_feature=actors_by_feature,
        parent_by_child=parent_by_child,
        children_by_parent=children_by_parent,
        criteria_by_scenario=criteria_by_scenario,
        features_by_flow=features_by_flow,
        steps_by_flow=steps_by_flow,
        actors_by_step=actors_by_step,
        inputs_by_step=inputs_by_step,
        outputs_by_step=outputs_by_step,
        next_by_step=next_by_step,
        attributes_by_object=attributes_by_object,
    )
