import copy
from datetime import datetime

from backend.database.model import beijing_now


def _updated_at(node: dict, fallback):
    value = node.get("updated_at") or node.get("updatedAt") or fallback
    return value.isoformat() if isinstance(value, datetime) else value


def _remap_actor(actor: dict, fallback) -> dict:
    return {
        "actor_id": (
            actor.get("actor_id")
            if "actor_id" in actor
            else actor.get("id")
        ),
        "actor_name": (
            actor.get("actor_name")
            if "actor_name" in actor
            else actor.get("name")
        ),
        "actor_description": (
            actor.get("actor_description")
            if "actor_description" in actor
            else actor.get("description")
        ),
        "updated_at": _updated_at(actor, fallback),
        "kind": "actor",
    }


def _remap_acceptance_criterion(criterion: dict, fallback) -> dict:
    return {
        "criterion_id": (
            criterion.get("criterion_id")
            if "criterion_id" in criterion
            else criterion.get("id")
        ),
        "criterion_content": (
            criterion.get("criterion_content")
            if "criterion_content" in criterion
            else criterion.get("content")
        ),
        "updated_at": _updated_at(criterion, fallback),
        "kind": "acceptance_criterion",
    }


def _remap_scenario(scenario: dict, fallback) -> dict:
    return {
        "scenario_id": (
            scenario.get("scenario_id")
            if "scenario_id" in scenario
            else scenario.get("id")
        ),
        "scenario_name": (
            scenario.get("scenario_name")
            if "scenario_name" in scenario
            else scenario.get("name")
        ),
        "scenario_content": (
            scenario.get("scenario_content")
            if "scenario_content" in scenario
            else scenario.get("content")
        ),
        "feature_id": scenario.get("feature_id"),
        "actor_id": scenario.get("actor_id"),
        "acceptance_criteria": [
            _remap_acceptance_criterion(criterion, fallback)
            for criterion in scenario.get("acceptance_criteria", [])
        ],
        "updated_at": _updated_at(scenario, fallback),
        "kind": "scenario",
    }


def _remap_scope(scope: dict | None, fallback) -> dict | None:
    if not scope:
        return None
    return {
        "scope_id": (
            scope.get("scope_id")
            if "scope_id" in scope
            else scope.get("id")
        ),
        "scope_status": (
            scope.get("scope_status")
            if "scope_status" in scope
            else scope.get("status")
        ),
        "reason": scope.get("reason"),
        "positive_summary": scope.get("positive_summary"),
        "negative_summary": scope.get("negative_summary"),
        "positive_picture_base64": (
            scope.get("positive_picture_base64")
            or scope.get("positivePictureBase64")
        ),
        "negative_picture_base64": (
            scope.get("negative_picture_base64")
            or scope.get("negativePictureBase64")
        ),
        "kano_category": scope.get("kano_category"),
        "kano_category_name": scope.get("kano_category_name"),
        "updated_at": _updated_at(scope, fallback),
        "kind": "scope",
    }


def _remap_feature(feature: dict, fallback) -> dict:
    return {
        "feature_id": (
            feature.get("feature_id")
            if "feature_id" in feature
            else feature.get("id")
        ),
        "feature_name": (
            feature.get("feature_name")
            if "feature_name" in feature
            else feature.get("name")
        ),
        "feature_description": (
            feature.get("feature_description")
            if "feature_description" in feature
            else feature.get("description")
        ),
        "actor_ids": feature.get("actor_ids", []),
        "parent_id": feature.get("parent_id"),
        "children_ids": feature.get("children_ids", []),
        "scenarios": [
            _remap_scenario(scenario, fallback)
            for scenario in feature.get("scenarios", [])
        ],
        "scope": _remap_scope(feature.get("scope"), fallback),
        "updated_at": _updated_at(feature, fallback),
        "kind": "feature",
    }


def _remap_attribute(attribute: dict, fallback) -> dict:
    attribute_id = (
        attribute.get("business_object_attribute_id")
        if "business_object_attribute_id" in attribute
        else attribute.get("id")
    )
    name = (
        attribute.get("business_object_attribute_name")
        if "business_object_attribute_name" in attribute
        else attribute.get("name")
    )
    description = (
        attribute.get("business_object_attribute_description")
        if "business_object_attribute_description" in attribute
        else attribute.get("description")
    )
    data_type = (
        attribute.get("business_object_attribute_type")
        if "business_object_attribute_type" in attribute
        else (
            attribute.get("data_type")
            or attribute.get("business_object_attribute_type")
        )
    )
    example = (
        attribute.get("business_object_attribute_example")
        if "business_object_attribute_example" in attribute
        else attribute.get("example")
    )
    return {
        "business_object_attribute_id": attribute_id or 0,
        "business_object_attribute_name": name or "",
        "business_object_attribute_description": description or "",
        "business_object_attribute_type": data_type or "string",
        "business_object_attribute_example": example or "",
        "updated_at": _updated_at(attribute, fallback),
        "kind": "business_object_attribute",
    }


def _remap_business_object(item: dict, fallback) -> dict:
    object_id = (
        item.get("business_object_id")
        if "business_object_id" in item
        else item.get("id")
    )
    name = (
        item.get("business_object_name")
        if "business_object_name" in item
        else item.get("name")
    )
    description = (
        item.get("business_object_description")
        if "business_object_description" in item
        else item.get("description")
    )
    return {
        "business_object_id": object_id or 0,
        "business_object_name": name or "",
        "business_object_description": description or "",
        "business_object_attributes": [
            _remap_attribute(attribute, fallback)
            for attribute in item.get("business_object_attributes", [])
        ],
        "updated_at": _updated_at(item, fallback),
        "kind": "business_object",
    }


def _remap_flow_step(step: dict, fallback) -> dict:
    return {
        "step_id": (
            step.get("step_id")
            if "step_id" in step
            else step.get("id")
        ),
        "step_name": (
            step.get("step_name")
            if "step_name" in step
            else step.get("name")
        ),
        "step_description": (
            step.get("step_description")
            if "step_description" in step
            else step.get("description")
        ),
        "step_type": step.get("step_type"),
        "position": step.get("position"),
        "actor_ids": step.get("actor_ids", []),
        "input_business_object_ids": step.get(
            "input_business_object_ids",
            [],
        ),
        "output_business_object_ids": step.get(
            "output_business_object_ids",
            [],
        ),
        "next_step_ids": step.get("next_step_ids", []),
        "updated_at": _updated_at(step, fallback),
        "kind": "flow_step",
    }


def _remap_flow(flow: dict, fallback) -> dict:
    return {
        "flow_id": (
            flow.get("flow_id")
            if "flow_id" in flow
            else flow.get("id")
        ),
        "flow_name": (
            flow.get("flow_name")
            if "flow_name" in flow
            else flow.get("name")
        ),
        "flow_description": (
            flow.get("flow_description")
            if "flow_description" in flow
            else flow.get("description")
        ),
        "feature_ids": flow.get("feature_ids", []),
        "flow_steps": [
            _remap_flow_step(step, fallback)
            for step in flow.get("flow_steps", [])
        ],
        "updated_at": _updated_at(flow, fallback),
        "kind": "flow",
    }


def remap_snapshot_to_pydantic(snapshot: dict) -> dict:
    remapped = copy.deepcopy(snapshot)
    fallback = beijing_now()
    remapped["project_id"] = remapped.get(
        "project_id",
        remapped.get("id"),
    )
    remapped["project_name"] = remapped.get(
        "project_name",
        remapped.get("name"),
    )
    remapped["project_description"] = remapped.get(
        "project_description",
        remapped.get("description"),
    )
    remapped["actors"] = [
        _remap_actor(actor, fallback)
        for actor in remapped.get("actors", [])
    ]
    remapped["features"] = [
        _remap_feature(feature, fallback)
        for feature in remapped.get("features", [])
    ]
    remapped["business_objects"] = [
        _remap_business_object(item, fallback)
        for item in remapped.get("business_objects", [])
    ]
    remapped["flows"] = [
        _remap_flow(flow, fallback)
        for flow in remapped.get("flows", [])
    ]
    return remapped
