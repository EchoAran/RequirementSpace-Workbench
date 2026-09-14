from sqlalchemy import select

from backend.api.modules.requirements_core.generation_context import (
    build_feature_graph_maps,
    load_feature_graph_rows,
    load_generation_features,
    load_generation_project,
)
from backend.database.model import ScopeModel
from backend.schemas import FeatureNode, ScopeNode, ScopeStatus
from backend.services.binary_conversion_service import BinaryConversionService


def parse_scope_status(value: str) -> ScopeStatus | None:
    upper_value = value.upper()
    if upper_value in ScopeStatus.__members__:
        return ScopeStatus[upper_value]
    try:
        return ScopeStatus(value.lower())
    except ValueError:
        return None


def build_scope_node(model) -> ScopeNode | None:
    status = parse_scope_status(model.status)
    if status is None:
        return None
    return ScopeNode(
        scopeId=model.id,
        scopeStatus=status,
        reason=model.reason,
        positiveSummary=model.positive_summary or None,
        negativeSummary=model.negative_summary or None,
        positivePictureBase64=(
            BinaryConversionService.bytes_to_base64(model.positive_picture)
            if model.positive_picture is not None
            else None
        ),
        negativePictureBase64=(
            BinaryConversionService.bytes_to_base64(model.negative_picture)
            if model.negative_picture is not None
            else None
        ),
        kanoCategory=model.kano_category,
        kanoCategoryName=model.kano_category_name,
    )


async def load_scope_nodes_by_feature(
    session,
    feature_ids: set[int],
) -> dict[int, ScopeNode]:
    result = await session.execute(
        select(ScopeModel).where(ScopeModel.feature_id.in_(feature_ids))
    )
    nodes = {}
    for model in result.scalars().all():
        node = build_scope_node(model)
        if node is not None:
            nodes[model.feature_id] = node
    return nodes


def build_scoped_feature_nodes(
    feature_models: list,
    children_by_feature: dict[int, list[int]],
    parent_by_feature: dict[int, int],
    actors_by_feature: dict[int, list[int]],
    scopes_by_feature: dict[int, ScopeNode],
) -> list[FeatureNode]:
    return [
        FeatureNode(
            featureId=feature.id,
            featureName=feature.name,
            featureDescription=feature.description,
            actorIds=actors_by_feature.get(feature.id, []),
            parentId=parent_by_feature.get(feature.id),
            childrenIds=children_by_feature.get(feature.id, []),
            scope=scopes_by_feature.get(feature.id),
        )
        for feature in feature_models
    ]


async def load_scope_generation_context(project_id: int, session, workspace_id: int):
    from backend.database.model import BranchWorkspaceModel

    workspace = await session.get(BranchWorkspaceModel, workspace_id)
    if workspace is None or workspace.project_id != project_id:
        raise ValueError("project_not_found")
    user_reqs = workspace.user_requirements

    feature_models = await load_generation_features(session, project_id, workspace_id=workspace_id)
    feature_ids = {feature.id for feature in feature_models}
    relations, feature_actor_rows = await load_feature_graph_rows(
        session,
        feature_ids,
    )
    graph_maps = build_feature_graph_maps(
        relations,
        feature_actor_rows,
    )
    scopes_by_feature = await load_scope_nodes_by_feature(
        session,
        feature_ids,
    )
    feature_nodes = build_scoped_feature_nodes(
        feature_models,
        *graph_maps,
        scopes_by_feature,
    )
    leaf_features = [
        feature
        for feature in feature_nodes
        if not feature.childrenIds
    ]
    if not leaf_features:
        raise ValueError("empty_leaf_features")
    return user_reqs, feature_nodes, leaf_features
