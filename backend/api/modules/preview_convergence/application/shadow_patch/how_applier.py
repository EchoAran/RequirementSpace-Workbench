from .apply_state import NegativeIdAllocator
from .lifecycle_mutations import (
    apply_how_removals,
    apply_how_updates,
    validate_how_snapshot,
)


def _apply_business_objects(
    snapshot: dict,
    patch: dict,
    allocator: NegativeIdAllocator,
) -> tuple[dict, dict]:
    existing_objects = {
        item["id"]: item
        for item in snapshot["business_objects"]
    }
    added_objects = {}
    for item in patch.get("business_objects_added", []):
        negative_id = allocator.temp_id_to_negative[item["temp_id"]]
        new_object = {
            "business_object_id": negative_id,
            "logical_uuid": item.get("logical_uuid", item["temp_id"]),
            "business_object_name": item["name"],
            "business_object_description": item["description"],
            "business_object_attributes": [],
        }
        snapshot["business_objects"].append(new_object)
        added_objects[negative_id] = new_object
    return existing_objects, added_objects


def _apply_business_object_attributes(
    patch: dict,
    allocator: NegativeIdAllocator,
    existing_objects: dict,
    added_objects: dict,
) -> None:
    for attribute in patch.get(
        "business_object_attributes_added",
        [],
    ):
        object_id = allocator.resolve(attribute["business_object_ref"])
        target = (
            existing_objects.get(object_id)
            or added_objects.get(object_id)
        )
        if target:
            target["business_object_attributes"].append({
                "business_object_attribute_id": allocator.allocate(),
                "business_object_attribute_name": attribute["name"],
                "business_object_attribute_description": (
                    attribute["description"]
                ),
                "business_object_attribute_type": attribute["data_type"],
                "business_object_attribute_example": attribute["example"],
            })


def _apply_flows(
    snapshot: dict,
    patch: dict,
    allocator: NegativeIdAllocator,
) -> None:
    for flow in patch.get("flows_added", []):
        snapshot["flows"].append({
            "flow_id": allocator.temp_id_to_negative[flow["temp_id"]],
            "logical_uuid": flow.get("logical_uuid", flow["temp_id"]),
            "flow_name": flow["name"],
            "flow_description": flow["description"],
            "feature_ids": [
                allocator.resolve(reference)
                for reference in flow["feature_refs"]
            ],
            "flow_steps": [],
        })


def _flow_index(snapshot: dict) -> dict[int, dict]:
    flows_by_id = {}
    for flow in snapshot["flows"]:
        flow_id = flow.get("flow_id") or flow.get("id")
        flows_by_id.setdefault(flow_id, flow)
    return flows_by_id


def _build_flow_step(
    step: dict,
    allocator: NegativeIdAllocator,
) -> dict:
    return {
        "step_id": allocator.temp_id_to_negative[step["temp_id"]],
        "logical_uuid": step.get("logical_uuid", step["temp_id"]),
        "step_name": step["name"],
        "step_description": step["description"],
        "step_type": step["step_type"],
        "position": step["position"],
        "actor_ids": [
            allocator.resolve(reference)
            for reference in step.get("actor_refs", [])
        ],
        "input_business_object_ids": [
            allocator.resolve(reference)
            for reference in step.get("input_bo_refs", [])
        ],
        "output_business_object_ids": [
            allocator.resolve(reference)
            for reference in step.get("output_bo_refs", [])
        ],
    }


def _apply_flow_steps(
    snapshot: dict,
    patch: dict,
    allocator: NegativeIdAllocator,
) -> None:
    flows_by_id = _flow_index(snapshot)
    for step in patch.get("flow_steps_added", []):
        new_step = _build_flow_step(step, allocator)
        target_flow = flows_by_id.get(
            allocator.resolve(step["flow_ref"])
        )
        if target_flow:
            target_flow["flow_steps"].append(new_step)


def _apply_flow_transitions(
    snapshot: dict,
    patch: dict,
    allocator: NegativeIdAllocator,
) -> None:
    flows_by_id = _flow_index(snapshot)
    for trans in patch.get("flow_transitions_added", []):
        target_flow = flows_by_id.get(
            allocator.resolve(trans["flow_ref"])
        )
        if target_flow:
            target_flow.setdefault("transitions", []).append({
                "transition_id": allocator.temp_id_to_negative[trans["temp_id"]],
                "logical_uuid": trans.get("logical_uuid", trans["temp_id"]),
                "flow_id": target_flow.get("flow_id") or target_flow.get("id"),
                "source_step_id": allocator.resolve(trans["source_step_ref"]),
                "target_step_id": allocator.resolve(trans["target_step_ref"]),
                "condition_text": trans.get("condition_text", ""),
                "label": trans.get("label", ""),
                "is_default": bool(trans.get("is_default", False)),
                "position": int(trans.get("position", 0)),
                "semantic_tags": sorted(set(trans.get("semantic_tags", []))),
                "origin": trans.get("origin", "manual"),
                "confirmation_status": trans.get(
                    "confirmation_status", "ai_assumption"
                ),
            })


def _apply_domain_rules(
    snapshot: dict,
    patch: dict,
    allocator: NegativeIdAllocator,
) -> None:
    rules_by_id = {
        rule["id"]: rule
        for rule in snapshot.get("domain_rules", [])
    }
    for rule in patch.get("domain_rules_added", []):
        added_rule = {
            "id": allocator.temp_id_to_negative[rule["temp_id"]],
            "logical_uuid": rule.get("logical_uuid", rule["temp_id"]),
            "parent_rule_logical_uuid": None,
            "title": rule["title"],
            "statement": rule["statement"],
            "origin": rule["origin"],
            "confirmation_status": rule["confirmation_status"],
            "links": [],
        }
        snapshot.setdefault("domain_rules", []).append(added_rule)
        rules_by_id[added_rule["id"]] = added_rule
    for rule in patch.get("domain_rules_added", []):
        parent_ref = rule.get("parent_ref")
        if parent_ref is None:
            continue
        parent = rules_by_id.get(allocator.resolve(parent_ref))
        if parent is None:
            raise ValueError(f"Unresolved rule reference '{parent_ref}'")
        rules_by_id[allocator.resolve(rule["temp_id"])][
            "parent_rule_logical_uuid"
        ] = parent["logical_uuid"]


def _apply_rule_links(
    snapshot: dict,
    patch: dict,
    allocator: NegativeIdAllocator,
) -> None:
    rules_by_id = {
        rule["id"]: rule
        for rule in snapshot.get("domain_rules", [])
    }
    for link in patch.get("rule_links_added", []):
        rule_id = allocator.resolve(link["rule_ref"])
        rule = rules_by_id.get(rule_id)
        if rule is None:
            raise ValueError(f"Unresolved rule reference '{link['rule_ref']}'")
        target_uuid = _resolve_target_logical_uuid(
            snapshot,
            link["target_kind"],
            link["target_ref"],
            allocator,
        )
        rule.setdefault("links", []).append({
            "id": allocator.allocate(),
            "logical_uuid": link.get("logical_uuid", link.get("temp_id", "")),
            "target_kind": link["target_kind"],
            "target_logical_uuid": target_uuid,
            "link_purpose": link["link_purpose"],
            "context_text": link.get("context_text", ""),
        })


def _resolve_target_logical_uuid(
    snapshot: dict,
    target_kind: str,
    target_ref: str,
    allocator: NegativeIdAllocator,
) -> str:
    if target_kind == "knowledge":
        return target_ref
    target_id = allocator.resolve(target_ref)
    candidates: list[dict] = []
    if target_kind == "feature":
        candidates = snapshot.get("features", [])
    elif target_kind == "scenario":
        candidates = [
            scenario
            for feature in snapshot.get("features", [])
            for scenario in feature.get("scenarios", [])
        ]
    elif target_kind == "acceptance_criterion":
        candidates = [
            criterion
            for feature in snapshot.get("features", [])
            for scenario in feature.get("scenarios", [])
            for criterion in scenario.get("acceptance_criteria", [])
        ]
    elif target_kind == "flow":
        candidates = snapshot.get("flows", [])
    elif target_kind == "flow_step":
        candidates = [
            step
            for flow in snapshot.get("flows", [])
            for step in flow.get("flow_steps", [])
        ]
    elif target_kind == "flow_transition":
        candidates = [
            transition
            for flow in snapshot.get("flows", [])
            for transition in flow.get("transitions", [])
        ]
    else:
        raise ValueError(f"Unsupported rule link target '{target_kind}'")
    target = next(
        (
            candidate
            for candidate in candidates
            if target_id in {
                candidate.get("id"),
                candidate.get("feature_id"),
                candidate.get("scenario_id"),
                candidate.get("criterion_id"),
                candidate.get("flow_id"),
                candidate.get("step_id"),
                candidate.get("transition_id"),
            }
        ),
        None,
    )
    if target is None or not target.get("logical_uuid"):
        raise ValueError(f"Unresolved rule link target '{target_ref}'")
    return target["logical_uuid"]


def apply_how_nodes(
    snapshot: dict,
    patch: dict,
    allocator: NegativeIdAllocator,
) -> None:
    apply_how_removals(snapshot, patch, allocator)
    existing_objects, added_objects = _apply_business_objects(
        snapshot,
        patch,
        allocator,
    )
    _apply_business_object_attributes(
        patch,
        allocator,
        existing_objects,
        added_objects,
    )
    _apply_domain_rules(snapshot, patch, allocator)
    _apply_flows(snapshot, patch, allocator)
    _apply_flow_steps(snapshot, patch, allocator)
    _apply_flow_transitions(snapshot, patch, allocator)
    _apply_rule_links(snapshot, patch, allocator)
    apply_how_updates(
        snapshot,
        patch,
        allocator,
        _resolve_target_logical_uuid,
    )
    validate_how_snapshot(snapshot)
