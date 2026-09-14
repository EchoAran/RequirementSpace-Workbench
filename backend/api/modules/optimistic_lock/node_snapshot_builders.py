import sqlalchemy as sa
from sqlalchemy import inspect

from backend.database.model import (
    BusinessObjectAttributeModel,
    DomainRuleModel,
    FeatureRelationModel,
    FlowStepModel,
    FlowTransitionModel,
    RuleLinkModel,
)


async def _build_actor(_session, node, _unloaded) -> dict:
    return {
        "name": node.name or "",
        "description": node.description or "",
    }


async def _build_feature(session, node, unloaded) -> dict:
    if "parent_relation" in unloaded:
        parent_id = (
            await session.execute(
                sa.select(
                    FeatureRelationModel.parent_feature_id
                ).where(
                    FeatureRelationModel.child_feature_id == node.id
                )
            )
        ).scalar_one_or_none()
    else:
        parent_id = (
            node.parent_relation.parent_feature_id
            if node.parent_relation
            else None
        )

    if "actors" in unloaded:
        from backend.database.model import features_actors

        actor_rows = (
            await session.execute(
                sa.select(features_actors.c.actor_id).where(
                    features_actors.c.feature_id == node.id
                )
            )
        ).all()
        actor_ids = [row[0] for row in actor_rows]
    else:
        actor_ids = [
            actor.id
            for actor in node.actors
        ] if node.actors else []

    return {
        "name": node.name or "",
        "description": node.description or "",
        "parent_id": parent_id,
        "actor_ids": sorted(actor_ids),
    }


async def _build_scenario(_session, node, _unloaded) -> dict:
    return {
        "name": node.name or "",
        "content": node.content or "",
        "feature_id": node.feature_id,
        "actor_id": node.actor_id,
    }


async def _build_acceptance_criterion(
    _session,
    node,
    _unloaded,
) -> dict:
    return {
        "content": node.content or "",
        "position": node.position,
        "scenario_id": node.scenario_id,
    }


def _attribute_snapshot(attribute) -> dict:
    return {
        "name": attribute.name or "",
        "description": attribute.description or "",
        "data_type": attribute.data_type or "",
        "example": attribute.example or "",
    }


async def _build_business_object(
    session,
    node,
    unloaded,
) -> dict:
    if "attributes" in unloaded:
        attributes = (
            await session.execute(
                sa.select(BusinessObjectAttributeModel).where(
                    BusinessObjectAttributeModel.business_object_id
                    == node.id
                )
            )
        ).scalars().all()
    else:
        attributes = node.attributes or []
    attributes_data = sorted(
        (
            _attribute_snapshot(attribute)
            for attribute in attributes
        ),
        key=lambda item: item["name"],
    )
    return {
        "name": node.name or "",
        "description": node.description or "",
        "attributes": attributes_data,
    }


def _flow_step_summary(step) -> dict:
    return {
        "position": step.position,
        "name": step.name or "",
        "description": step.description or "",
        "step_type": step.step_type or "",
    }


async def _build_flow(session, node, unloaded) -> dict:
    if "steps" in unloaded:
        steps = (
            await session.execute(
                sa.select(FlowStepModel).where(
                    FlowStepModel.flow_id == node.id
                )
            )
        ).scalars().all()
    else:
        steps = node.steps or []
    steps_data = sorted(
        (_flow_step_summary(step) for step in steps),
        key=lambda item: item["position"],
    )
    if "transitions" in unloaded:
        transitions = (
            await session.execute(
                sa.select(FlowTransitionModel).where(
                    FlowTransitionModel.flow_id == node.id,
                    FlowTransitionModel.workspace_id == node.workspace_id,
                )
            )
        ).scalars().all()
    else:
        transitions = node.transitions or []
    return {
        "name": node.name or "",
        "description": node.description or "",
        "steps": steps_data,
        "transitions": sorted(
            (
                {
                    "logical_uuid": transition.logical_uuid,
                    "source_step_id": transition.source_step_id,
                    "target_step_id": transition.target_step_id,
                    "label": transition.label or "",
                    "condition_text": transition.condition_text or "",
                    "is_default": transition.is_default,
                    "position": transition.position,
                    "semantic_tags": sorted(set(transition.semantic_tags or [])),
                }
                for transition in transitions
            ),
            key=lambda item: (
                item["source_step_id"],
                item["position"],
                item["logical_uuid"],
            ),
        ),
    }


async def _load_related_ids(
    session,
    table,
    owner_column,
    related_column,
    node_id: int,
) -> list[int]:
    rows = (
        await session.execute(
            sa.select(related_column).where(
                owner_column == node_id
            )
        )
    ).all()
    return [row[0] for row in rows]


async def _flow_step_relation_ids(
    session,
    node,
    unloaded,
) -> tuple[list[int], list[int], list[int]]:
    if "actors" in unloaded:
        from backend.database.model import flow_steps_actors

        actor_ids = await _load_related_ids(
            session,
            flow_steps_actors,
            flow_steps_actors.c.flow_step_id,
            flow_steps_actors.c.actor_id,
            node.id,
        )
    else:
        actor_ids = [
            actor.id
            for actor in node.actors
        ] if node.actors else []

    relation_specs = (
        (
            "input_business_objects",
            "input",
        ),
        (
            "output_business_objects",
            "output",
        ),
    )
    business_object_ids = []
    for relationship, direction in relation_specs:
        if relationship in unloaded:
            if direction == "input":
                from backend.database.model import (
                    flow_steps_input_business_objects as table,
                )
            else:
                from backend.database.model import (
                    flow_steps_output_business_objects as table,
                )
            ids = await _load_related_ids(
                session,
                table,
                table.c.flow_step_id,
                table.c.business_object_id,
                node.id,
            )
        else:
            entities = getattr(node, relationship)
            ids = [
                entity.id
                for entity in entities
            ] if entities else []
        business_object_ids.append(ids)
    return actor_ids, business_object_ids[0], business_object_ids[1]


async def _build_flow_step(session, node, unloaded) -> dict:
    (
        actor_ids,
        input_business_object_ids,
        output_business_object_ids,
    ) = await _flow_step_relation_ids(session, node, unloaded)
    return {
        "name": node.name or "",
        "description": node.description or "",
        "position": node.position,
        "step_type": node.step_type or "",
        "flow_id": node.flow_id,
        "actor_ids": sorted(actor_ids),
        "input_business_object_ids": sorted(
            input_business_object_ids
        ),
        "output_business_object_ids": sorted(
            output_business_object_ids
        ),
        "incoming_transition_logical_uuids": sorted(
            (
                await session.execute(
                    sa.select(FlowTransitionModel.logical_uuid).where(
                        FlowTransitionModel.target_step_id == node.id,
                        FlowTransitionModel.workspace_id == node.workspace_id,
                    )
                )
            ).scalars().all()
        ),
        "outgoing_transition_logical_uuids": sorted(
            (
                await session.execute(
                    sa.select(FlowTransitionModel.logical_uuid).where(
                        FlowTransitionModel.source_step_id == node.id,
                        FlowTransitionModel.workspace_id == node.workspace_id,
                    )
                )
            ).scalars().all()
        ),
    }


async def _build_scope(_session, node, _unloaded) -> dict:
    return {
        "feature_id": node.feature_id,
        "status": node.status or "",
        "positive_summary": node.positive_summary or "",
        "negative_summary": node.negative_summary or "",
        "reason": node.reason or "",
        "kano_category": node.kano_category or "",
    }


async def _build_business_object_attribute(
    _session,
    node,
    _unloaded,
) -> dict:
    return _attribute_snapshot(node)


async def _build_domain_rule(session, node, _unloaded) -> dict:
    parent_uuid = None
    if node.parent_rule_id is not None:
        parent_uuid = await session.scalar(
            sa.select(DomainRuleModel.logical_uuid).where(
                DomainRuleModel.id == node.parent_rule_id,
                DomainRuleModel.workspace_id == node.workspace_id,
            )
        )
    links = (
        await session.execute(
            sa.select(RuleLinkModel).where(
                RuleLinkModel.rule_id == node.id,
                RuleLinkModel.workspace_id == node.workspace_id,
            )
        )
    ).scalars().all()
    return {
        "logical_uuid": node.logical_uuid,
        "workspace_id": node.workspace_id,
        "title": node.title or "",
        "statement": node.statement or "",
        "origin": node.origin or "",
        "confirmation_status": node.confirmation_status or "",
        "parent_rule_logical_uuid": parent_uuid,
        "links": sorted(
            (
                {
                    "logical_uuid": link.logical_uuid,
                    "target_kind": link.target_kind,
                    "target_logical_uuid": link.target_logical_uuid,
                    "link_purpose": link.link_purpose,
                    "context_text": link.context_text or "",
                }
                for link in links
            ),
            key=lambda item: (
                item["link_purpose"],
                item["target_kind"],
                item["target_logical_uuid"],
                item["logical_uuid"],
            ),
        ),
    }


async def _build_rule_link(session, node, _unloaded) -> dict:
    rule_uuid = await session.scalar(
        sa.select(DomainRuleModel.logical_uuid).where(
            DomainRuleModel.id == node.rule_id,
            DomainRuleModel.workspace_id == node.workspace_id,
        )
    )
    if rule_uuid is None:
        raise ValueError("Rule link refers to a rule outside the workspace")
    return {
        "logical_uuid": node.logical_uuid,
        "workspace_id": node.workspace_id,
        "rule_logical_uuid": rule_uuid,
        "target_kind": node.target_kind or "",
        "target_logical_uuid": node.target_logical_uuid or "",
        "link_purpose": node.link_purpose or "",
        "context_text": node.context_text or "",
    }


async def _build_flow_transition(session, node, _unloaded) -> dict:
    step_rows = (
        await session.execute(
            sa.select(FlowStepModel.id, FlowStepModel.logical_uuid).where(
                FlowStepModel.id.in_([node.source_step_id, node.target_step_id]),
                FlowStepModel.workspace_id == node.workspace_id,
            )
        )
    ).all()
    step_uuids = dict(step_rows)
    if len(step_uuids) != 2:
        raise ValueError("Flow transition endpoints are outside the workspace")
    links = (
        await session.execute(
            sa.select(RuleLinkModel).where(
                RuleLinkModel.workspace_id == node.workspace_id,
                RuleLinkModel.target_kind == "flow_transition",
                RuleLinkModel.target_logical_uuid == node.logical_uuid,
                RuleLinkModel.link_purpose == "applies_to",
            )
        )
    ).scalars().all()
    rule_ids = sorted({link.rule_id for link in links})
    rule_rows = (
        await session.execute(
            sa.select(DomainRuleModel.id, DomainRuleModel.logical_uuid).where(
                DomainRuleModel.id.in_(rule_ids),
                DomainRuleModel.workspace_id == node.workspace_id,
            )
        )
    ).all() if rule_ids else []
    return {
        "logical_uuid": node.logical_uuid,
        "workspace_id": node.workspace_id,
        "source_step_logical_uuid": step_uuids[node.source_step_id],
        "target_step_logical_uuid": step_uuids[node.target_step_id],
        "label": node.label or "",
        "condition_text": node.condition_text or "",
        "is_default": node.is_default,
        "position": node.position,
        "semantic_tags": sorted(set(node.semantic_tags or [])),
        "origin": node.origin,
        "confirmation_status": node.confirmation_status,
        "rule_logical_uuids": sorted(row[1] for row in rule_rows),
    }


async def _build_flow_refinement_choice(_session, node, _unloaded) -> dict:
    group = node.choice_group
    if group is None or group.generation_type != "flow_refinement":
        raise ValueError("Choice is not a flow refinement candidate")
    if group.workspace_id != node.workspace_id:
        raise ValueError("Choice and choice group belong to different workspaces")
    return {
        "logical_uuid": node.logical_uuid,
        "workspace_id": node.workspace_id,
        "choice_group_logical_uuid": group.logical_uuid,
        "generation_type": group.generation_type,
        "status": node.status,
        "title": node.title,
        "rationale": node.rationale,
        "payload": node.payload,
        "preview": node.preview,
    }


_BUILDERS = {
    "actor": _build_actor,
    "feature": _build_feature,
    "scenario": _build_scenario,
    "acceptance_criterion": _build_acceptance_criterion,
    "business_object": _build_business_object,
    "flow": _build_flow,
    "flow_step": _build_flow_step,
    "scope": _build_scope,
    "business_object_attribute": _build_business_object_attribute,
    "domain_rule": _build_domain_rule,
    "rule_link": _build_rule_link,
    "flow_transition": _build_flow_transition,
    "flow_refinement_choice": _build_flow_refinement_choice,
}


async def build_node_snapshot(
    session,
    node_kind: str,
    node,
) -> dict:
    kind = node_kind.lower()
    builder = _BUILDERS.get(kind)
    if builder is None:
        raise ValueError(f"Unsupported node kind: {node_kind}")
    return await builder(session, node, inspect(node).unloaded)
