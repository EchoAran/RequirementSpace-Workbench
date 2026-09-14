from backend.services.binary_conversion_service import (
    BinaryConversionService,
)

from .loader import SnapshotData


def _serialize_scope(scope) -> dict | None:
    if not scope:
        return None
    return {
        "id": scope.id,
        "logical_uuid": scope.logical_uuid,
        "feature_id": scope.feature_id,
        "status": scope.status,
        "reason": scope.reason,
        "positive_summary": scope.positive_summary,
        "negative_summary": scope.negative_summary,
        "positive_picture_base64": (
            BinaryConversionService.bytes_to_base64(
                scope.positive_picture
            )
            if scope.positive_picture is not None
            else None
        ),
        "negative_picture_base64": (
            BinaryConversionService.bytes_to_base64(
                scope.negative_picture
            )
            if scope.negative_picture is not None
            else None
        ),
        "kano_category": scope.kano_category,
        "kano_category_name": scope.kano_category_name,
    }


def _serialize_scenario(scenario, criteria: list) -> dict:
    return {
        "id": scenario.id,
        "logical_uuid": scenario.logical_uuid,
        "name": scenario.name,
        "content": scenario.content,
        "feature_id": scenario.feature_id,
        "actor_id": scenario.actor_id,
        "acceptance_criteria": [
            {
                "id": criterion.id,
                "logical_uuid": criterion.logical_uuid,
                "content": criterion.content,
                "position": criterion.position,
            }
            for criterion in criteria
        ],
    }


def _serialize_features(data: SnapshotData) -> list[dict]:
    scenarios_by_feature = {}
    for scenario in data.scenarios:
        scenarios_by_feature.setdefault(
            scenario.feature_id,
            [],
        ).append(scenario)
    return [
        {
            "id": feature.id,
            "logical_uuid": feature.logical_uuid,
            "name": feature.name,
            "description": feature.description,
            "actor_ids": sorted(
                data.actors_by_feature.get(feature.id, [])
            ),
            "parent_id": data.parent_by_child.get(feature.id),
            "children_ids": sorted(
                data.children_by_parent.get(feature.id, [])
            ),
            "scenarios": [
                _serialize_scenario(
                    scenario,
                    data.criteria_by_scenario.get(scenario.id, []),
                )
                for scenario in scenarios_by_feature.get(feature.id, [])
            ],
            "scope": _serialize_scope(
                data.scopes_by_feature.get(feature.id)
            ),
        }
        for feature in data.features
    ]


def _serialize_business_objects(data: SnapshotData) -> list[dict]:
    return [
        {
            "id": item.id,
            "logical_uuid": item.logical_uuid,
            "name": item.name,
            "description": item.description,
            "business_object_attributes": [
                {
                    "id": attribute.id,
                    "logical_uuid": attribute.logical_uuid,
                    "name": attribute.name,
                    "description": attribute.description,
                    "data_type": attribute.data_type,
                    "example": attribute.example,
                }
                for attribute in data.attributes_by_object.get(
                    item.id,
                    [],
                )
            ],
        }
        for item in data.business_objects
    ]


def _serialize_flow_step(step, data: SnapshotData) -> dict:
    return {
        "id": step.id,
        "logical_uuid": step.logical_uuid,
        "name": step.name,
        "description": step.description,
        "step_type": step.step_type,
        "position": step.position,
        "actor_ids": sorted(data.actors_by_step.get(step.id, [])),
        "input_business_object_ids": sorted(
            data.inputs_by_step.get(step.id, [])
        ),
        "output_business_object_ids": sorted(
            data.outputs_by_step.get(step.id, [])
        ),
    }


def _serialize_flow_transition(transition) -> dict:
    return {
        "id": transition.id,
        "flow_id": transition.flow_id,
        "source_step_id": transition.source_step_id,
        "target_step_id": transition.target_step_id,
        "condition_text": transition.condition_text or "",
        "label": transition.label or "",
        "is_default": bool(transition.is_default),
        "position": transition.position or 0,
        "logical_uuid": transition.logical_uuid,
        "semantic_tags": sorted(set(transition.semantic_tags or [])),
        "origin": transition.origin,
        "confirmation_status": transition.confirmation_status,
    }


def _serialize_domain_rules(data: SnapshotData) -> list[dict]:
    rule_uuid_by_id = {
        rule.id: rule.logical_uuid
        for rule in data.domain_rules
    }
    return [
        {
            "id": rule.id,
            "logical_uuid": rule.logical_uuid,
            "parent_rule_logical_uuid": rule_uuid_by_id.get(rule.parent_rule_id),
            "title": rule.title,
            "statement": rule.statement,
            "origin": rule.origin,
            "confirmation_status": rule.confirmation_status,
            "links": [
                {
                    "id": link.id,
                    "logical_uuid": link.logical_uuid,
                    "target_kind": link.target_kind,
                    "target_logical_uuid": link.target_logical_uuid,
                    "link_purpose": link.link_purpose,
                    "context_text": link.context_text,
                }
                for link in data.rule_links_by_rule.get(rule.id, [])
            ],
        }
        for rule in data.domain_rules
    ]


def _serialize_flows(data: SnapshotData) -> list[dict]:
    return [
        {
            "id": flow.id,
            "logical_uuid": flow.logical_uuid,
            "name": flow.name,
            "description": flow.description,
            "feature_ids": sorted(
                data.features_by_flow.get(flow.id, [])
            ),
            "flow_steps": [
                _serialize_flow_step(step, data)
                for step in data.steps_by_flow.get(flow.id, [])
            ],
            "transitions": [
                _serialize_flow_transition(transition)
                for transition in data.transitions_by_flow.get(flow.id, [])
            ],
        }
        for flow in data.flows
    ]


def serialize_snapshot(data: SnapshotData) -> dict:
    return {
        "project_id": data.project.public_id,
        "name": data.project.name,
        "description": data.project.description,
        "user_requirements": data.project.user_requirements,
        "actors": [
            {
                "id": actor.id,
                "logical_uuid": actor.logical_uuid,
                "name": actor.name,
                "description": actor.description,
            }
            for actor in data.actors
        ],
        "features": _serialize_features(data),
        "business_objects": _serialize_business_objects(data),
        "flows": _serialize_flows(data),
        "domain_rules": _serialize_domain_rules(data),
    }
