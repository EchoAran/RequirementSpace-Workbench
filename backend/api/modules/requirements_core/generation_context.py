from sqlalchemy import select

from backend.database.model import (
    ActorModel,
    FeatureModel,
    FeatureRelationModel,
    ProjectModel,
    feature_actor_table,
)
from backend.schemas import ActorNode, FeatureNode


async def load_generation_project(session, project_id: int):
    result = await session.execute(
        select(ProjectModel).where(ProjectModel.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise ValueError("project_not_found")
    return project


async def load_generation_actors(session, project_id: int) -> list:
    result = await session.execute(
        select(ActorModel).where(ActorModel.project_id == project_id)
    )
    actors = result.scalars().all()
    if not actors:
        raise ValueError("empty_actors")
    return actors


async def load_generation_features(session, project_id: int) -> list:
    result = await session.execute(
        select(FeatureModel).where(FeatureModel.project_id == project_id)
    )
    features = result.scalars().all()
    if not features:
        raise ValueError("empty_features")
    return features


async def load_feature_graph_rows(
    session,
    feature_ids: set[int],
) -> tuple[list, list]:
    relation_result = await session.execute(
        select(FeatureRelationModel).where(
            FeatureRelationModel.parent_feature_id.in_(feature_ids)
        )
    )
    feature_actor_result = await session.execute(
        select(
            feature_actor_table.c.feature_id,
            feature_actor_table.c.actor_id,
        ).where(feature_actor_table.c.feature_id.in_(feature_ids))
    )
    return (
        relation_result.scalars().all(),
        feature_actor_result.all(),
    )


def build_feature_graph_maps(
    relations: list,
    feature_actor_rows: list,
) -> tuple[dict[int, list[int]], dict[int, int], dict[int, list[int]]]:
    children_by_feature: dict[int, list[int]] = {}
    parent_by_feature: dict[int, int] = {}
    for relation in relations:
        children_by_feature.setdefault(
            relation.parent_feature_id,
            [],
        ).append(relation.child_feature_id)
        parent_by_feature[relation.child_feature_id] = (
            relation.parent_feature_id
        )

    actors_by_feature: dict[int, list[int]] = {}
    for feature_id, actor_id in feature_actor_rows:
        actors_by_feature.setdefault(feature_id, []).append(actor_id)
    return children_by_feature, parent_by_feature, actors_by_feature


def build_actor_nodes(actors: list) -> list[ActorNode]:
    return [
        ActorNode(
            actorId=actor.id,
            actorName=actor.name,
            actorDescription=actor.description,
        )
        for actor in actors
    ]


def build_feature_nodes(
    features: list,
    children_by_feature: dict[int, list[int]],
    parent_by_feature: dict[int, int],
    actors_by_feature: dict[int, list[int]],
) -> list[FeatureNode]:
    return [
        FeatureNode(
            featureId=feature.id,
            featureName=feature.name,
            featureDescription=feature.description,
            actorIds=actors_by_feature.get(feature.id, []),
            parentId=parent_by_feature.get(feature.id),
            childrenIds=children_by_feature.get(feature.id, []),
        )
        for feature in features
    ]


def count_leaf_features(features: list[FeatureNode]) -> int:
    count = sum(not feature.childrenIds for feature in features)
    if not count:
        raise ValueError("empty_leaf_features")
    return count


async def load_flow_generation_context(
    project_id: int,
    session,
) -> tuple[str, list[ActorNode], list[FeatureNode], int]:
    project = await load_generation_project(session, project_id)
    actors = await load_generation_actors(session, project_id)
    features = await load_generation_features(session, project_id)
    feature_ids = {feature.id for feature in features}
    relations, feature_actor_rows = await load_feature_graph_rows(
        session,
        feature_ids,
    )
    graph_maps = build_feature_graph_maps(
        relations,
        feature_actor_rows,
    )
    actor_nodes = build_actor_nodes(actors)
    feature_nodes = build_feature_nodes(features, *graph_maps)
    return (
        project.user_requirements,
        actor_nodes,
        feature_nodes,
        count_leaf_features(feature_nodes),
    )
