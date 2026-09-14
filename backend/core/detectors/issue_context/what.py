from sqlalchemy import select

from backend.database.model import (
    ActorModel,
    FeatureModel,
    FeatureRelationModel,
    ProjectModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    feature_actor_table,
)

from .types import (
    AcceptanceCriterionIssueItem,
    ActorIssueItem,
    FeatureIssueItem,
    ScenarioIssueItem,
)


async def load_issue_project(project_id: int, session) -> ProjectModel:
    result = await session.execute(
        select(ProjectModel).where(ProjectModel.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise ValueError("project_not_found")
    return project


async def load_issue_actors(
    project_id: int,
    session,
    workspace_id: int,
) -> list[ActorIssueItem]:
    stmt = select(ActorModel).where(
        ActorModel.project_id == project_id,
        ActorModel.workspace_id == workspace_id,
    )
    result = await session.execute(stmt)
    return [
        ActorIssueItem(
            actor_id=actor.id,
            name=actor.name,
            description=actor.description,
        )
        for actor in result.scalars().all()
    ]


async def _load_feature_maps(
    feature_ids: list[int],
    session,
) -> tuple[dict[int, list[int]], dict[int, int], dict[int, list[int]]]:
    children_map: dict[int, list[int]] = {}
    parent_map: dict[int, int] = {}
    actor_ids_map: dict[int, list[int]] = {}
    if not feature_ids:
        return children_map, parent_map, actor_ids_map

    relation_result = await session.execute(
        select(FeatureRelationModel).where(
            FeatureRelationModel.parent_feature_id.in_(feature_ids)
        )
    )
    for relation in relation_result.scalars().all():
        children_map.setdefault(
            relation.parent_feature_id,
            [],
        ).append(relation.child_feature_id)
        parent_map[relation.child_feature_id] = relation.parent_feature_id

    feature_actor_result = await session.execute(
        select(
            feature_actor_table.c.feature_id,
            feature_actor_table.c.actor_id,
        ).where(feature_actor_table.c.feature_id.in_(feature_ids))
    )
    for feature_id, actor_id in feature_actor_result.all():
        actor_ids_map.setdefault(feature_id, []).append(actor_id)
    return children_map, parent_map, actor_ids_map


async def load_issue_features(
    project_id: int,
    session,
    workspace_id: int,
) -> tuple[list[FeatureIssueItem], list[int]]:
    stmt = select(FeatureModel).where(
        FeatureModel.project_id == project_id,
        FeatureModel.workspace_id == workspace_id,
    )
    result = await session.execute(stmt)
    feature_models = result.scalars().all()
    feature_ids = [feature.id for feature in feature_models]
    children_map, parent_map, actor_ids_map = await _load_feature_maps(
        feature_ids,
        session,
    )
    return (
        [
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
        feature_ids,
    )


async def _load_acceptance_criteria(
    scenario_ids: list[int],
    session,
) -> dict[int, list[AcceptanceCriterionIssueItem]]:
    criteria_map: dict[int, list[AcceptanceCriterionIssueItem]] = {}
    if not scenario_ids:
        return criteria_map
    result = await session.execute(
        select(ScenarioAcceptanceCriterionModel).where(
            ScenarioAcceptanceCriterionModel.scenario_id.in_(
                scenario_ids
            )
        )
    )
    for criterion in result.scalars().all():
        criteria_map.setdefault(criterion.scenario_id, []).append(
            AcceptanceCriterionIssueItem(
                criterion_id=criterion.id,
                content=criterion.content,
                position=criterion.position,
            )
        )
    return criteria_map


async def load_issue_scenarios(
    project_id: int,
    session,
    workspace_id: int,
) -> list[ScenarioIssueItem]:
    stmt = select(ScenarioModel).where(
        ScenarioModel.project_id == project_id,
        ScenarioModel.workspace_id == workspace_id,
    )
    result = await session.execute(stmt)
    scenario_models = result.scalars().all()
    criteria_map = await _load_acceptance_criteria(
        [scenario.id for scenario in scenario_models],
        session,
    )
    return [
        ScenarioIssueItem(
            scenario_id=scenario.id,
            feature_id=scenario.feature_id,
            actor_id=scenario.actor_id,
            name=scenario.name,
            content=scenario.content,
            acceptance_criteria=sorted(
                criteria_map.get(scenario.id, []),
                key=lambda item: item.position,
            ),
            acceptance_criteria_count=len(
                criteria_map.get(scenario.id, [])
            ),
        )
        for scenario in scenario_models
    ]
