from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.model import (
    ActorModel,
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    DomainRuleModel,
    FeatureModel,
    FeatureRelationModel,
    FlowModel,
    FlowStepModel,
    FlowTransitionModel,
    RuleLinkModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    feature_actor_table,
    flow_feature_table,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    flow_step_output_business_object_table,
)

from .common import _CommitIdMaps
from .lifecycle_writer import apply_how_removals, apply_how_updates


async def _insert_actors(
    project_id: int,
    workspace_id: int,
    patch: dict,
    id_maps: _CommitIdMaps,
    session: AsyncSession,
) -> None:
    for actor_data in patch.get("actors_added", []):
        actor = ActorModel(
            project_id=project_id,
            workspace_id=workspace_id,
            name=actor_data["name"],
            description=actor_data["description"],
        )
        session.add(actor)
        await session.flush()
        id_maps.actors[actor_data["temp_id"]] = actor.id

def _resolve_feature_parent(
    parent_ref: Any,
    feature_ids: dict[str, int],
) -> tuple[bool, int | None]:
    if parent_ref is None:
        return True, None
    parent_ref_text = str(parent_ref)
    if parent_ref_text.startswith("feature:"):
        return True, int(parent_ref_text.split(":")[1])
    if parent_ref_text.startswith("tmp_"):
        if parent_ref_text in feature_ids:
            return True, feature_ids[parent_ref_text]
        return False, None
    try:
        return True, int(parent_ref_text)
    except ValueError:
        return False, None

async def _next_feature_position(
    parent_id: int,
    next_position_by_parent: dict[int, int],
    session: AsyncSession,
) -> int:
    if parent_id not in next_position_by_parent:
        result = await session.execute(
            select(func.max(FeatureRelationModel.position)).where(
                FeatureRelationModel.parent_feature_id == parent_id
            )
        )
        max_position = result.scalar()
        next_position_by_parent[parent_id] = (
            0 if max_position is None else max_position + 1
        )
    position = next_position_by_parent[parent_id]
    next_position_by_parent[parent_id] = position + 1
    return position

async def _insert_feature(
    project_id: int,
    workspace_id: int,
    feature_data: dict,
    parent_id: int | None,
    id_maps: _CommitIdMaps,
    next_position_by_parent: dict[int, int],
    session: AsyncSession,
) -> None:
    feature = FeatureModel(
        project_id=project_id,
        workspace_id=workspace_id,
        name=feature_data["name"],
        description=feature_data["description"],
    )
    session.add(feature)
    await session.flush()
    id_maps.features[feature_data["temp_id"]] = feature.id
    if parent_id is None:
        return
    position = await _next_feature_position(
        parent_id,
        next_position_by_parent,
        session,
    )
    session.add(
        FeatureRelationModel(
            parent_feature_id=parent_id,
            child_feature_id=feature.id,
            position=position,
        )
    )
    await session.flush()

async def _insert_features(
    project_id: int,
    workspace_id: int,
    patch: dict,
    id_maps: _CommitIdMaps,
    session: AsyncSession,
) -> None:
    features_to_insert = list(patch.get("features_added", []))
    next_position_by_parent: dict[int, int] = {}
    while features_to_insert:
        inserted_count = 0
        remaining = []
        for feature_data in features_to_insert:
            can_insert, parent_id = _resolve_feature_parent(
                feature_data.get("parent_ref"),
                id_maps.features,
            )
            if not can_insert:
                remaining.append(feature_data)
                continue
            await _insert_feature(
                project_id,
                workspace_id,
                feature_data,
                parent_id,
                id_maps,
                next_position_by_parent,
                session,
            )
            inserted_count += 1
        if inserted_count == 0:
            raise ValueError("Cyclic dependency detected in features_added!")
        features_to_insert = remaining

async def _insert_feature_actor_links(
    patch: dict,
    id_maps: _CommitIdMaps,
    session: AsyncSession,
) -> None:
    for link in patch.get("feature_actor_links_added", []):
        await session.execute(
            feature_actor_table.insert().values(
                feature_id=id_maps.resolve_feature(link["feature_ref"]),
                actor_id=id_maps.resolve_actor(link["actor_ref"]),
            )
        )

async def _insert_scenarios(
    project_id: int,
    workspace_id: int,
    patch: dict,
    id_maps: _CommitIdMaps,
    session: AsyncSession,
) -> None:
    for scenario_data in patch.get("scenarios_added", []):
        scenario = ScenarioModel(
            project_id=project_id,
            workspace_id=workspace_id,
            feature_id=id_maps.resolve_feature(
                scenario_data["feature_ref"]
            ),
            actor_id=id_maps.resolve_actor(scenario_data["actor_ref"]),
            name=scenario_data["name"],
            content=scenario_data["content"],
        )
        session.add(scenario)
        await session.flush()
        id_maps.scenarios[scenario_data["temp_id"]] = scenario.id

async def _insert_acceptance_criteria(
    patch: dict,
    id_maps: _CommitIdMaps,
    session: AsyncSession,
) -> None:
    for criterion_data in patch.get("acceptance_criteria_added", []):
        session.add(
            ScenarioAcceptanceCriterionModel(
                scenario_id=id_maps.resolve_scenario(
                    criterion_data["scenario_ref"]
                ),
                content=criterion_data["content"],
                position=criterion_data["position"],
            )
        )
        await session.flush()

async def _insert_business_objects(
    project_id: int,
    workspace_id: int,
    patch: dict,
    id_maps: _CommitIdMaps,
    session: AsyncSession,
) -> None:
    for object_data in patch.get("business_objects_added", []):
        business_object = BusinessObjectModel(
            project_id=project_id,
            workspace_id=workspace_id,
            name=object_data["name"],
            description=object_data["description"],
        )
        session.add(business_object)
        await session.flush()
        id_maps.business_objects[object_data["temp_id"]] = business_object.id

async def _insert_business_object_attributes(
    patch: dict,
    id_maps: _CommitIdMaps,
    session: AsyncSession,
) -> None:
    for attribute_data in patch.get(
        "business_object_attributes_added",
        [],
    ):
        session.add(
            BusinessObjectAttributeModel(
                business_object_id=id_maps.resolve_business_object(
                    attribute_data["business_object_ref"]
                ),
                name=attribute_data["name"],
                description=attribute_data["description"],
                data_type=attribute_data["data_type"],
                example=attribute_data["example"],
            )
        )
        await session.flush()

async def _insert_flows(
    project_id: int,
    workspace_id: int,
    patch: dict,
    id_maps: _CommitIdMaps,
    session: AsyncSession,
) -> None:
    for flow_data in patch.get("flows_added", []):
        flow = FlowModel(
            project_id=project_id,
            workspace_id=workspace_id,
            name=flow_data["name"],
            description=flow_data["description"],
        )
        session.add(flow)
        await session.flush()
        id_maps.flows[flow_data["temp_id"]] = flow.id
        for feature_ref in flow_data.get("feature_refs", []):
            await session.execute(
                flow_feature_table.insert().values(
                    flow_id=flow.id,
                    feature_id=id_maps.resolve_feature(feature_ref),
                )
            )

async def _insert_flow_steps(
    patch: dict,
    id_maps: _CommitIdMaps,
    session: AsyncSession,
) -> None:
    for step_data in patch.get("flow_steps_added", []):
        step = FlowStepModel(
            flow_id=id_maps.resolve_flow(step_data["flow_ref"]),
            name=step_data["name"],
            description=step_data["description"],
            step_type=step_data["step_type"],
            position=step_data["position"],
        )
        session.add(step)
        await session.flush()
        id_maps.steps[step_data["temp_id"]] = step.id

async def _insert_flow_step_associations(
    patch: dict,
    id_maps: _CommitIdMaps,
    session: AsyncSession,
) -> None:
    for step_data in patch.get("flow_steps_added", []):
        step_id = id_maps.steps[step_data["temp_id"]]
        for actor_ref in step_data.get("actor_refs", []):
            await session.execute(
                flow_step_actor_table.insert().values(
                    flow_step_id=step_id,
                    actor_id=id_maps.resolve_actor(actor_ref),
                )
            )
        for object_ref in step_data.get("input_bo_refs", []):
            await session.execute(
                flow_step_input_business_object_table.insert().values(
                    flow_step_id=step_id,
                    business_object_id=id_maps.resolve_business_object(
                        object_ref
                    ),
                )
            )
        for object_ref in step_data.get("output_bo_refs", []):
            await session.execute(
                flow_step_output_business_object_table.insert().values(
                    flow_step_id=step_id,
                    business_object_id=id_maps.resolve_business_object(
                        object_ref
                    ),
                )
            )

async def _insert_flow_transitions(
    project_id: int,
    workspace_id: int,
    patch: dict,
    id_maps: _CommitIdMaps,
    session: AsyncSession,
) -> None:
    for trans_data in patch.get("flow_transitions_added", []):
        flow_id = id_maps.resolve_flow(trans_data["flow_ref"])
        source_step_id = id_maps.resolve_step(trans_data["source_step_ref"])
        target_step_id = id_maps.resolve_step(trans_data["target_step_ref"])
        transition = FlowTransitionModel(
            project_id=project_id,
            workspace_id=workspace_id,
            flow_id=flow_id,
            source_step_id=source_step_id,
            target_step_id=target_step_id,
            condition_text=trans_data.get("condition_text", ""),
            label=trans_data.get("label") or "",
            is_default=bool(trans_data.get("is_default", False)),
            position=int(trans_data.get("position", 0)),
            semantic_tags=sorted(set(trans_data.get("semantic_tags", []))),
            origin=trans_data.get("origin", "manual"),
            confirmation_status=trans_data.get(
                "confirmation_status", "ai_assumption"
            ),
        )
        session.add(transition)
        await session.flush()
        id_maps.transitions[trans_data["temp_id"]] = transition.id


async def _insert_domain_rules(
    project_id: int,
    workspace_id: int,
    patch: dict,
    id_maps: _CommitIdMaps,
    session: AsyncSession,
) -> None:
    for item in patch.get("domain_rules_added", []):
        rule_values = dict(
            project_id=project_id,
            workspace_id=workspace_id,
            title=item["title"],
            statement=item["statement"],
            origin=item["origin"],
            confirmation_status=item["confirmation_status"],
        )
        if item.get("logical_uuid"):
            rule_values["logical_uuid"] = item["logical_uuid"]
        rule = DomainRuleModel(**rule_values)
        session.add(rule)
        await session.flush()
        id_maps.domain_rules[item["temp_id"]] = rule.id
    for item in patch.get("domain_rules_added", []):
        parent_ref = item.get("parent_ref")
        if parent_ref:
            rule = await session.get(
                DomainRuleModel,
                id_maps.resolve_domain_rule(item["temp_id"]),
            )
            rule.parent_rule_id = id_maps.resolve_domain_rule(parent_ref)
    await session.flush()


_RULE_LINK_TARGET_MODELS = {
    "feature": FeatureModel,
    "scenario": ScenarioModel,
    "acceptance_criterion": ScenarioAcceptanceCriterionModel,
    "flow": FlowModel,
    "flow_step": FlowStepModel,
    "flow_transition": FlowTransitionModel,
}


async def _resolve_target_logical_uuid(
    target_kind: str,
    target_ref: str,
    id_maps: _CommitIdMaps,
    session: AsyncSession,
) -> str:
    if target_kind == "knowledge":
        return target_ref
    resolvers = {
        "feature": id_maps.resolve_feature,
        "scenario": id_maps.resolve_scenario,
        "acceptance_criterion": lambda reference: int(
            str(reference).split(":")[-1]
        ),
        "flow": id_maps.resolve_flow,
        "flow_step": id_maps.resolve_step,
        "flow_transition": id_maps.resolve_transition,
    }
    model = _RULE_LINK_TARGET_MODELS.get(target_kind)
    resolver = resolvers.get(target_kind)
    if model is None or resolver is None:
        raise ValueError(f"Unsupported shadow rule link target '{target_kind}'")
    target = await session.get(model, resolver(target_ref))
    if target is None:
        raise ValueError(f"Unresolved shadow rule link target '{target_ref}'")
    return target.logical_uuid


async def _insert_rule_links(
    project_id: int,
    workspace_id: int,
    patch: dict,
    id_maps: _CommitIdMaps,
    session: AsyncSession,
) -> None:
    for item in patch.get("rule_links_added", []):
        target_uuid = await _resolve_target_logical_uuid(
            item["target_kind"],
            item["target_ref"],
            id_maps,
            session,
        )
        link_values = dict(
            project_id=project_id,
            workspace_id=workspace_id,
            rule_id=id_maps.resolve_domain_rule(item["rule_ref"]),
            target_kind=item["target_kind"],
            target_logical_uuid=target_uuid,
            link_purpose=item["link_purpose"],
            context_text=item.get("context_text", ""),
        )
        if item.get("logical_uuid"):
            link_values["logical_uuid"] = item["logical_uuid"]
        session.add(RuleLinkModel(**link_values))
    await session.flush()

async def _write_patch_entities(
    project_id: int,
    workspace_id: int,
    patch: dict,
    id_maps: _CommitIdMaps,
    session: AsyncSession,
) -> None:
    await apply_how_removals(project_id, workspace_id, patch, session)
    await _insert_actors(project_id, workspace_id, patch, id_maps, session)
    await _insert_features(project_id, workspace_id, patch, id_maps, session)
    await _insert_feature_actor_links(patch, id_maps, session)
    await _insert_scenarios(project_id, workspace_id, patch, id_maps, session)
    await _insert_acceptance_criteria(patch, id_maps, session)
    await _insert_business_objects(project_id, workspace_id, patch, id_maps, session)
    await _insert_business_object_attributes(patch, id_maps, session)
    await _insert_domain_rules(project_id, workspace_id, patch, id_maps, session)
    await _insert_flows(project_id, workspace_id, patch, id_maps, session)
    await _insert_flow_steps(patch, id_maps, session)
    await _insert_flow_transitions(project_id, workspace_id, patch, id_maps, session)
    await _insert_rule_links(project_id, workspace_id, patch, id_maps, session)
    await apply_how_updates(
        project_id,
        workspace_id,
        patch,
        id_maps,
        _resolve_target_logical_uuid,
        session,
    )
    await _insert_flow_step_associations(patch, id_maps, session)
