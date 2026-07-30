from .apply_state import NegativeIdAllocator


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
        "next_step_ids": [
            allocator.resolve(reference)
            for reference in step.get("next_step_refs", [])
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


def apply_how_nodes(
    snapshot: dict,
    patch: dict,
    allocator: NegativeIdAllocator,
) -> None:
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
    _apply_flows(snapshot, patch, allocator)
    _apply_flow_steps(snapshot, patch, allocator)
