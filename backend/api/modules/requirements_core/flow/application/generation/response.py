def build_business_object_previews(items: list[dict]) -> list[dict]:
    return [
        {
            "business_object_name": item["business_object_name"],
            "business_object_description": item[
                "business_object_description"
            ],
            "business_object_attributes": item.get(
                "business_object_attributes",
                [],
            ),
        }
        for item in items
    ]


def build_flow_step_preview(
    step: dict,
    *,
    actor_names: dict[int, str],
    business_object_names: dict[str, str],
    step_names: dict[str, str],
) -> dict:
    return {
        "step_name": step["step_name"],
        "step_description": step["step_description"],
        "step_type": step["step_type"],
        "rule_refs": step.get("rule_refs", []),
        "actor_names": [
            actor_names[actor_id]
            for actor_id in step.get("actor_ids", [])
        ],
        "input_business_object_names": [
            business_object_names[number]
            for number in step.get(
                "input_business_object_numbers",
                [],
            )
        ],
        "output_business_object_names": [
            business_object_names[number]
            for number in step.get(
                "output_business_object_numbers",
                [],
            )
        ],
    }


def build_flow_transition_preview(
    transition: dict,
    *,
    step_names: dict[str, str],
) -> dict:
    source_num = transition.get("source_step_number")
    target_num = transition.get("target_step_number")
    return {
        "source_step_name": step_names.get(source_num, source_num),
        "target_step_name": step_names.get(target_num, target_num),
        "label": transition.get("label", ""),
        "condition_text": transition.get("condition_text", ""),
        "is_default": transition.get("is_default", False),
        "position": transition.get("position", 0),
        "semantic_tags": transition.get("semantic_tags", []),
        "rule_refs": transition.get("rule_refs", []),
    }


def build_flow_preview(
    flow: dict,
    *,
    actor_names: dict[int, str],
    feature_names: dict[int, str],
    business_object_names: dict[str, str],
) -> dict:
    steps = flow.get("flow_steps", [])
    step_names = {
        step["step_number"]: step["step_name"]
        for step in steps
    }
    return {
        "flow_name": flow["flow_name"],
        "flow_description": flow["flow_description"],
        "rule_refs": flow.get("rule_refs", []),
        "feature_names": [
            feature_names[feature_id]
            for feature_id in flow.get("feature_ids", [])
        ],
        "flow_steps": [
            build_flow_step_preview(
                step,
                actor_names=actor_names,
                business_object_names=business_object_names,
                step_names=step_names,
            )
            for step in steps
        ],
        "transitions": [
            build_flow_transition_preview(
                transition,
                step_names=step_names,
            )
            for transition in flow.get("transitions", [])
        ],
    }


def build_flow_generation_response(
    project_id: int,
    draft: dict,
    actor_nodes: list,
    feature_nodes: list,
) -> dict:
    actor_names = {
        actor.actorId: actor.actorName
        for actor in actor_nodes
    }
    feature_names = {
        feature.featureId: feature.featureName
        for feature in feature_nodes
    }
    business_object_names = {
        item["business_object_number"]: item["business_object_name"]
        for item in draft["business_objects"]
    }
    return {
        "project_id": project_id,
        "generation_mode": draft["generation_mode"],
        "leaf_feature_count": draft["leaf_feature_count"],
        "business_objects": build_business_object_previews(
            draft["business_objects"]
        ),
        "flows": [
            build_flow_preview(
                flow,
                actor_names=actor_names,
                feature_names=feature_names,
                business_object_names=business_object_names,
            )
            for flow in draft["flows"]
        ],
    }
