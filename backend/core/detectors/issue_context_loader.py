from dataclasses import dataclass, field

from sqlalchemy import select


@dataclass
class ActorIssueItem:
    actor_id: int
    name: str
    description: str


@dataclass
class FeatureIssueItem:
    feature_id: int
    name: str
    description: str
    actor_ids: list[int] = field(default_factory=list)
    parent_id: int | None = None
    child_ids: list[int] = field(default_factory=list)


@dataclass
class AcceptanceCriterionIssueItem:
    criterion_id: int
    content: str
    position: int


@dataclass
class ScenarioIssueItem:
    scenario_id: int
    feature_id: int
    actor_id: int
    name: str
    content: str
    acceptance_criteria_count: int = 0
    acceptance_criteria: list[AcceptanceCriterionIssueItem] = field(
        default_factory=list
    )


@dataclass
class FlowStepIssueItem:
    step_id: int
    flow_id: int
    position: int
    name: str
    description: str
    step_type: str
    actor_ids: list[int] = field(default_factory=list)
    next_step_ids: list[int] = field(default_factory=list)


@dataclass
class FlowIssueItem:
    flow_id: int
    name: str
    description: str
    feature_ids: list[int] = field(default_factory=list)
    steps: list[FlowStepIssueItem] = field(default_factory=list)


@dataclass
class BusinessObjectIssueItem:
    business_object_id: int
    name: str
    description: str
    attribute_count: int = 0
    usage_count: int = 0


@dataclass
class ScopeIssueItem:
    scope_id: int
    feature_id: int
    status: str
    reason: str


@dataclass
class IssueProjectContext:
    project_id: int
    user_requirements: str
    actors: list[ActorIssueItem]
    features: list[FeatureIssueItem]
    scenarios: list[ScenarioIssueItem]
    flows: list[FlowIssueItem]
    business_objects: list[BusinessObjectIssueItem]
    scopes: list[ScopeIssueItem]

    @property
    def leaf_features(self) -> list[FeatureIssueItem]:
        return [
            feature
            for feature in self.features
            if len(feature.child_ids) == 0
        ]


async def load_issue_project_context(project_id: int, session) -> IssueProjectContext:
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

    project_result = await session.execute(
        select(ProjectModel).where(ProjectModel.id == project_id)
    )
    project = project_result.scalar_one_or_none()

    if project is None:
        raise ValueError("project_not_found")

    actor_result = await session.execute(
        select(ActorModel).where(ActorModel.project_id == project_id)
    )
    actor_models = actor_result.scalars().all()

    feature_result = await session.execute(
        select(FeatureModel).where(FeatureModel.project_id == project_id)
    )
    feature_models = feature_result.scalars().all()

    feature_ids = [
        feature.id
        for feature in feature_models
    ]

    children_map: dict[int, list[int]] = {}
    parent_map: dict[int, int] = {}
    actor_ids_map: dict[int, list[int]] = {}

    if feature_ids:
        relation_result = await session.execute(
            select(FeatureRelationModel).where(
                FeatureRelationModel.parent_feature_id.in_(feature_ids)
            )
        )
        relation_models = relation_result.scalars().all()

        for relation in relation_models:
            children_map.setdefault(
                relation.parent_feature_id,
                [],
            ).append(relation.child_feature_id)
            parent_map[relation.child_feature_id] = (
                relation.parent_feature_id
            )

        feature_actor_result = await session.execute(
            select(
                feature_actor_table.c.feature_id,
                feature_actor_table.c.actor_id,
            ).where(feature_actor_table.c.feature_id.in_(feature_ids))
        )

        for feature_id, actor_id in feature_actor_result.all():
            actor_ids_map.setdefault(feature_id, []).append(actor_id)

    scenario_result = await session.execute(
        select(ScenarioModel).where(ScenarioModel.project_id == project_id)
    )
    scenario_models = scenario_result.scalars().all()

    scenario_ids = [
        scenario.id
        for scenario in scenario_models
    ]

    acceptance_criteria_map: dict[int, list[AcceptanceCriterionIssueItem]] = {}

    if scenario_ids:
        acceptance_result = await session.execute(
            select(ScenarioAcceptanceCriterionModel).where(
                ScenarioAcceptanceCriterionModel.scenario_id.in_(
                    scenario_ids
                )
            )
        )

        for criterion in acceptance_result.scalars().all():
            acceptance_criteria_map.setdefault(
                criterion.scenario_id,
                [],
            ).append(
                AcceptanceCriterionIssueItem(
                    criterion_id=criterion.id,
                    content=criterion.content,
                    position=criterion.position,
                )
            )

    flow_result = await session.execute(
        select(FlowModel).where(FlowModel.project_id == project_id)
    )
    flow_models = flow_result.scalars().all()

    flow_ids = [
        flow.id
        for flow in flow_models
    ]

    flow_feature_ids_map: dict[int, list[int]] = {}
    flow_steps_map: dict[int, list[FlowStepIssueItem]] = {}
    step_actor_ids_map: dict[int, list[int]] = {}
    step_next_ids_map: dict[int, list[int]] = {}

    if flow_ids:
        flow_feature_result = await session.execute(
            select(
                flow_feature_table.c.flow_id,
                flow_feature_table.c.feature_id,
            ).where(flow_feature_table.c.flow_id.in_(flow_ids))
        )

        for flow_id, feature_id in flow_feature_result.all():
            flow_feature_ids_map.setdefault(flow_id, []).append(feature_id)

        step_result = await session.execute(
            select(FlowStepModel).where(FlowStepModel.flow_id.in_(flow_ids))
        )
        step_models = step_result.scalars().all()

        step_ids = [
            step.id
            for step in step_models
        ]

        if step_ids:
            step_actor_result = await session.execute(
                select(
                    flow_step_actor_table.c.flow_step_id,
                    flow_step_actor_table.c.actor_id,
                ).where(flow_step_actor_table.c.flow_step_id.in_(step_ids))
            )

            for step_id, actor_id in step_actor_result.all():
                step_actor_ids_map.setdefault(step_id, []).append(actor_id)

            step_next_result = await session.execute(
                select(
                    flow_step_next_table.c.source_step_id,
                    flow_step_next_table.c.target_step_id,
                ).where(flow_step_next_table.c.source_step_id.in_(step_ids))
            )

            for source_step_id, target_step_id in step_next_result.all():
                step_next_ids_map.setdefault(
                    source_step_id,
                    [],
                ).append(target_step_id)

        for step in step_models:
            flow_steps_map.setdefault(step.flow_id, []).append(
                FlowStepIssueItem(
                    step_id=step.id,
                    flow_id=step.flow_id,
                    position=step.position,
                    name=step.name,
                    description=step.description,
                    step_type=step.step_type,
                    actor_ids=step_actor_ids_map.get(step.id, []),
                    next_step_ids=step_next_ids_map.get(step.id, []),
                )
            )

    business_object_result = await session.execute(
        select(BusinessObjectModel).where(
            BusinessObjectModel.project_id == project_id
        )
    )
    business_object_models = business_object_result.scalars().all()

    business_object_ids = [
        item.id
        for item in business_object_models
    ]

    attribute_count_map: dict[int, int] = {}
    usage_count_map: dict[int, int] = {}

    if business_object_ids:
        attribute_result = await session.execute(
            select(
                BusinessObjectAttributeModel.business_object_id,
                BusinessObjectAttributeModel.id,
            ).where(
                BusinessObjectAttributeModel.business_object_id.in_(
                    business_object_ids
                )
            )
        )

        for business_object_id, _attribute_id in attribute_result.all():
            attribute_count_map[business_object_id] = (
                attribute_count_map.get(business_object_id, 0) + 1
            )

        input_usage_result = await session.execute(
            select(
                flow_step_input_business_object_table.c.business_object_id
            ).where(
                flow_step_input_business_object_table.c.business_object_id.in_(
                    business_object_ids
                )
            )
        )

        for business_object_id in input_usage_result.scalars().all():
            usage_count_map[business_object_id] = (
                usage_count_map.get(business_object_id, 0) + 1
            )

        output_usage_result = await session.execute(
            select(
                flow_step_output_business_object_table.c.business_object_id
            ).where(
                flow_step_output_business_object_table.c.business_object_id.in_(
                    business_object_ids
                )
            )
        )

        for business_object_id in output_usage_result.scalars().all():
            usage_count_map[business_object_id] = (
                usage_count_map.get(business_object_id, 0) + 1
            )

    scope_result = await session.execute(
        select(ScopeModel).where(ScopeModel.feature_id.in_(feature_ids))
        if feature_ids
        else select(ScopeModel).where(False)
    )
    scope_models = scope_result.scalars().all()

    return IssueProjectContext(
        project_id=project.id,
        user_requirements=project.user_requirements,
        actors=[
            ActorIssueItem(
                actor_id=actor.id,
                name=actor.name,
                description=actor.description,
            )
            for actor in actor_models
        ],
        features=[
            FeatureIssueItem(
                feature_id=feature.id,
                name=feature.name,
                description=feature.description,
                actor_ids=actor_ids_map.get(feature.id, []),
                parent_id=parent_map.get(feature.id),
                child_ids=children_map.get(feature.id, []),
            )
            for feature in feature_models
        ],
        scenarios=[
            ScenarioIssueItem(
                scenario_id=scenario.id,
                feature_id=scenario.feature_id,
                actor_id=scenario.actor_id,
                name=scenario.name,
                content=scenario.content,
                acceptance_criteria=sorted(
                    acceptance_criteria_map.get(scenario.id, []),
                    key=lambda item: item.position,
                ),
                acceptance_criteria_count=len(
                    acceptance_criteria_map.get(scenario.id, [])
                ),
            )
            for scenario in scenario_models
        ],
        flows=[
            FlowIssueItem(
                flow_id=flow.id,
                name=flow.name,
                description=flow.description,
                feature_ids=flow_feature_ids_map.get(flow.id, []),
                steps=sorted(
                    flow_steps_map.get(flow.id, []),
                    key=lambda item: item.position,
                ),
            )
            for flow in flow_models
        ],
        business_objects=[
            BusinessObjectIssueItem(
                business_object_id=item.id,
                name=item.name,
                description=item.description,
                attribute_count=attribute_count_map.get(item.id, 0),
                usage_count=usage_count_map.get(item.id, 0),
            )
            for item in business_object_models
        ],
        scopes=[
            ScopeIssueItem(
                scope_id=scope.id,
                feature_id=scope.feature_id,
                status=scope.status,
                reason=scope.reason,
            )
            for scope in scope_models
        ],
    )
