from backend.api.modules.requirements_core.generation_context import (
    build_actor_nodes,
    build_feature_graph_maps,
    build_feature_nodes,
    load_feature_graph_rows,
    load_generation_actors,
    load_generation_features,
)


def select_target_features(
    generation_mode: str,
    feature_id: int | None,
    feature_nodes_by_id: dict,
    leaf_features: list,
    feature_ids: list[int] | None = None,
) -> list:
    if generation_mode == "batch":
        if not feature_ids:
            raise ValueError("empty_generation_targets")
        target_ids = feature_ids
    elif generation_mode in {"single", "pair"}:
        if feature_id is None:
            raise ValueError("feature_id_required")
        target_ids = [feature_id]
    else:
        return leaf_features
    targets = []
    for target_id in target_ids:
        target = feature_nodes_by_id.get(target_id)
        if target is None:
            raise ValueError("feature_not_found")
        if target.childrenIds:
            raise ValueError("feature_is_not_leaf")
        targets.append(target)
    return targets


def build_target_pairs(
    target_features: list,
    actor_nodes_by_id: dict,
) -> list[tuple[int, int]]:
    pairs = []
    for feature in target_features:
        if not feature.actorIds:
            raise ValueError("leaf_feature_without_actor")
        for actor_id in feature.actorIds:
            if actor_id not in actor_nodes_by_id:
                raise ValueError("invalid_feature_actor_reference")
            pairs.append((feature.featureId, actor_id))
    return pairs


def select_pair_target(
    generation_mode: str,
    feature_id: int | None,
    actor_id: int | None,
    actor_nodes_by_id: dict,
    target_pairs: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    if generation_mode != "pair":
        return target_pairs
    if actor_id is None:
        raise ValueError("actor_id_required")
    if actor_id not in actor_nodes_by_id:
        raise ValueError("actor_not_found")
    pair = (feature_id, actor_id)
    if pair not in target_pairs:
        raise ValueError("invalid_feature_actor_reference")
    return [pair]


async def load_scenario_generation_context(
    project_id: int,
    feature_id: int | None,
    actor_id: int | None,
    generation_mode: str,
    session,
    workspace_id: int,
    feature_ids: list[int] | None = None,
):
    from backend.database.model import BranchWorkspaceModel

    workspace = await session.get(BranchWorkspaceModel, workspace_id)
    if workspace is None or workspace.project_id != project_id:
        raise ValueError("project_not_found")
    user_reqs = workspace.user_requirements

    actor_models = await load_generation_actors(session, project_id, workspace_id=workspace_id)
    feature_models = await load_generation_features(session, project_id, workspace_id=workspace_id)
    relations, feature_actor_rows = await load_feature_graph_rows(
        session,
        {feature.id for feature in feature_models},
    )
    graph_maps = build_feature_graph_maps(
        relations,
        feature_actor_rows,
    )
    actor_nodes_by_id = {
        node.actorId: node
        for node in build_actor_nodes(actor_models)
    }
    feature_nodes_by_id = {
        node.featureId: node
        for node in build_feature_nodes(feature_models, *graph_maps)
    }
    leaf_features = [
        feature
        for feature in feature_nodes_by_id.values()
        if not feature.childrenIds
    ]
    if not leaf_features:
        raise ValueError("empty_leaf_features")
    target_features = select_target_features(
        generation_mode,
        feature_id,
        feature_nodes_by_id,
        leaf_features,
        feature_ids,
    )
    target_pairs = build_target_pairs(
        target_features,
        actor_nodes_by_id,
    )
    target_pairs = select_pair_target(
        generation_mode,
        feature_id,
        actor_id,
        actor_nodes_by_id,
        target_pairs,
    )
    if not target_pairs:
        raise ValueError("empty_generation_targets")
    return (
        user_reqs,
        actor_nodes_by_id,
        feature_nodes_by_id,
        target_pairs,
    )
