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


async def load_generation_actors(session, project_id: int, workspace_id: int) -> list:

    stmt = select(ActorModel).where(ActorModel.project_id == project_id)
    stmt = stmt.where(ActorModel.workspace_id == workspace_id)
    result = await session.execute(stmt)
    actors = result.scalars().all()
    if not actors:
        raise ValueError("empty_actors")
    return actors


async def load_generation_features(session, project_id: int, workspace_id: int) -> list:

    stmt = select(FeatureModel).where(FeatureModel.project_id == project_id)
    stmt = stmt.where(FeatureModel.workspace_id == workspace_id)
    result = await session.execute(stmt)
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


import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlowGenerationContext:
    user_requirements: str
    actors: list[ActorNode]
    features: list[FeatureNode]
    leaf_feature_count: int
    scenarios: list[dict[str, Any]] = field(default_factory=list)
    acceptance_criteria: list[dict[str, Any]] = field(default_factory=list)
    rules: list[dict[str, Any]] = field(default_factory=list)
    context_hash: str = ""


def compute_flow_context_hash(
    user_requirements: str,
    actors: list[ActorNode],
    features: list[FeatureNode],
    scenarios: list[dict[str, Any]],
    acceptance_criteria: list[dict[str, Any]],
    rules: list[dict[str, Any]],
) -> str:
    """Compute deterministic SHA-256 hash representing upstream input and rule state."""
    data = {
        "reqs": (user_requirements or "").strip(),
        "actors": sorted(
            [{"id": a.actorId, "name": a.actorName} for a in actors],
            key=lambda x: x["id"],
        ),
        "features": sorted(
            [{"id": f.featureId, "name": f.featureName} for f in features],
            key=lambda x: x["id"],
        ),
        "scenarios": sorted(
            [
                {
                    "uuid": s.get("logical_uuid"),
                    "name": s.get("name"),
                    "content": s.get("content"),
                }
                for s in scenarios
            ],
            key=lambda x: str(x["uuid"]),
        ),
        "ac": sorted(
            [
                {
                    "uuid": ac.get("logical_uuid"),
                    "content": ac.get("content"),
                }
                for ac in acceptance_criteria
            ],
            key=lambda x: str(x["uuid"]),
        ),
        "rules": sorted(
            [
                {
                    "uuid": r.get("logical_uuid"),
                    "statement": r.get("statement"),
                    "status": r.get("confirmation_status"),
                    "parent_uuid": r.get("parent_rule_uuid"),
                    "links": sorted(
                        [
                            f"{lnk.get('target_kind')}:{lnk.get('target_logical_uuid')}"
                            for lnk in r.get("links", [])
                        ]
                    ),
                }
                for r in rules
            ],
            key=lambda x: str(x["uuid"]),
        ),
    }
    raw_json = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()


async def load_flow_generation_context(
    project_id: int,
    session,
    workspace_id: int,
    injected_rules: list[dict] | None = None,
) -> FlowGenerationContext:
    from sqlalchemy.orm import selectinload

    from backend.database.model import (
        BranchWorkspaceModel,
        DomainRuleModel,
        ScenarioAcceptanceCriterionModel,
        ScenarioModel,
    )


    # Load requirements and specs
    await load_generation_project(session, project_id)
    workspace = await session.get(BranchWorkspaceModel, workspace_id)
    if workspace is None or workspace.project_id != project_id:
        raise ValueError("workspace_not_found")
    user_reqs = workspace.user_requirements

    actors = await load_generation_actors(session, project_id, workspace_id=workspace_id)
    features = await load_generation_features(session, project_id, workspace_id=workspace_id)
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

    # Load Scenarios and Acceptance Criteria
    scenario_stmt = select(ScenarioModel).where(ScenarioModel.project_id == project_id)
    scenario_stmt = scenario_stmt.where(ScenarioModel.workspace_id == workspace_id)
    scenario_rows = (await session.execute(scenario_stmt)).scalars().all()

    scenarios = [
        {
            "id": s.id,
            "logical_uuid": s.logical_uuid,
            "name": s.name,
            "content": s.content,
            "feature_id": s.feature_id,
            "actor_id": s.actor_id,
        }
        for s in scenario_rows
    ]

    scenario_ids = [s.id for s in scenario_rows]
    acceptance_criteria = []
    if scenario_ids:
        ac_stmt = select(ScenarioAcceptanceCriterionModel).where(
            ScenarioAcceptanceCriterionModel.scenario_id.in_(scenario_ids)
        )
        ac_stmt = ac_stmt.where(
            ScenarioAcceptanceCriterionModel.workspace_id == workspace_id
        )
        ac_stmt = ac_stmt.order_by(ScenarioAcceptanceCriterionModel.position.asc())
        ac_rows = (await session.execute(ac_stmt)).scalars().all()
        acceptance_criteria = [
            {
                "id": ac.id,
                "logical_uuid": ac.logical_uuid,
                "scenario_id": ac.scenario_id,
                "content": ac.content,
            }
            for ac in ac_rows
        ]

    # Load Domain Rules and links
    if injected_rules is not None:
        if not injected_rules:
            raise ValueError("domain_rule_required")
        rules = injected_rules
    else:
        rule_stmt = (
            select(DomainRuleModel)
            .where(DomainRuleModel.project_id == project_id)
            .options(selectinload(DomainRuleModel.links))
        )
        rule_stmt = rule_stmt.where(DomainRuleModel.workspace_id == workspace_id)
        rule_rows = (await session.execute(rule_stmt)).scalars().all()
        if not rule_rows:
            raise ValueError("domain_rule_required")

        id_to_uuid = {r.id: r.logical_uuid for r in rule_rows if r.logical_uuid}
        rules = [
            {
                "id": r.id,
                "logical_uuid": r.logical_uuid,
                "title": r.title,
                "statement": r.statement,
                "confirmation_status": r.confirmation_status,
                "parent_rule_id": r.parent_rule_id,
                "parent_rule_uuid": id_to_uuid.get(r.parent_rule_id)
                if r.parent_rule_id
                else None,
                "links": [
                    {
                        "target_kind": lnk.target_kind,
                        "target_logical_uuid": lnk.target_logical_uuid,
                        "link_purpose": lnk.link_purpose,
                    }
                    for lnk in r.links
                ],
            }
            for r in rule_rows
        ]

    context_hash = compute_flow_context_hash(
        user_requirements=user_reqs,
        actors=actor_nodes,
        features=feature_nodes,
        scenarios=scenarios,
        acceptance_criteria=acceptance_criteria,
        rules=rules,
    )

    return FlowGenerationContext(
        user_requirements=user_reqs,
        actors=actor_nodes,
        features=feature_nodes,
        leaf_feature_count=count_leaf_features(feature_nodes),
        scenarios=scenarios,
        acceptance_criteria=acceptance_criteria,
        rules=rules,
        context_hash=context_hash,
    )
