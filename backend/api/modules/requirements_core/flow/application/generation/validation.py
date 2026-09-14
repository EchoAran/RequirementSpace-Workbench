def validate_number_sequence(
    numbers: list[str],
    *,
    pattern,
    duplicate_error: str,
    format_error: str,
) -> set[str]:
    number_set = set(numbers)
    if len(number_set) != len(numbers):
        raise ValueError(duplicate_error)
    for number in numbers:
        if pattern.match(number) is None:
            raise ValueError(format_error)
    return number_set


def validate_feature_references(
    flow: dict,
    valid_feature_ids: set[int],
) -> None:
    feature_ids = flow.get("feature_ids", [])
    if not feature_ids:
        raise ValueError("invalid_feature_reference")
    for feature_id in feature_ids:
        if feature_id not in valid_feature_ids:
            raise ValueError("invalid_feature_reference")


def validate_step_references(
    step: dict,
    *,
    valid_step_types: set[str],
    valid_actor_ids: set[int],
    valid_business_object_numbers: set[str],
    valid_step_numbers: set[str],
) -> None:
    if step.get("step_type") not in valid_step_types:
        raise ValueError("invalid_step_type")
    for actor_id in step.get("actor_ids", []):
        if actor_id not in valid_actor_ids:
            raise ValueError("invalid_actor_reference")
    for number in step.get("input_business_object_numbers", []):
        if number not in valid_business_object_numbers:
            raise ValueError("invalid_business_object_reference")
    for number in step.get("output_business_object_numbers", []):
        if number not in valid_business_object_numbers:
            raise ValueError("invalid_business_object_reference")


def validate_rule_references(item: dict, target_kind: str, valid_rule_uuids: set[str] | None) -> None:
    rule_refs = item.get("rule_refs", [])
    if rule_refs is None:
        rule_refs = []
    if not isinstance(rule_refs, list):
        raise ValueError(f"invalid_{target_kind}_rule_refs: expected list")
    for ref in rule_refs:
        if not isinstance(ref, str) or (valid_rule_uuids is not None and ref not in valid_rule_uuids):
            raise ValueError(
                f"invalid_{target_kind}_rule_reference: rule '{ref}' not found in reviewed domain rules"
            )


def validate_transition_references(
    transition: dict,
    *,
    valid_step_numbers: set[str],
    valid_rule_uuids: set[str] | None = None,
) -> None:
    source_num = transition.get("source_step_number")
    target_num = transition.get("target_step_number")
    if not source_num or source_num not in valid_step_numbers:
        raise ValueError("invalid_transition_step_reference")
    if not target_num or target_num not in valid_step_numbers:
        raise ValueError("invalid_transition_step_reference")
    if source_num == target_num:
        raise ValueError("transition_self_loop_detected")

    validate_rule_references(transition, "transition", valid_rule_uuids)


def validate_flow(
    flow: dict,
    *,
    step_number_pattern,
    valid_step_types: set[str],
    valid_actor_ids: set[int],
    valid_feature_ids: set[int],
    valid_business_object_numbers: set[str],
    valid_rule_uuids: set[str] | None = None,
) -> None:
    validate_feature_references(flow, valid_feature_ids)
    validate_rule_references(flow, "flow", valid_rule_uuids)
    steps = flow.get("flow_steps", [])
    if not steps:
        raise ValueError("empty_flow_steps")
    step_numbers = [step["step_number"] for step in steps]
    step_number_set = validate_number_sequence(
        step_numbers,
        pattern=step_number_pattern,
        duplicate_error="duplicate_step_number",
        format_error="invalid_step_number_format",
    )
    for step in steps:
        validate_rule_references(step, "step", valid_rule_uuids)
        validate_step_references(
            step,
            valid_step_types=valid_step_types,
            valid_actor_ids=valid_actor_ids,
            valid_business_object_numbers=valid_business_object_numbers,
            valid_step_numbers=step_number_set,
        )
    seen_default_sources: set[str] = set()
    seen_edges: set[tuple[str, str]] = set()
    for transition in flow.get("transitions", []):
        validate_transition_references(
            transition,
            valid_step_numbers=step_number_set,
            valid_rule_uuids=valid_rule_uuids,
        )
        src_num = transition.get("source_step_number")
        tgt_num = transition.get("target_step_number")
        edge = (src_num, tgt_num)
        if edge in seen_edges:
            raise ValueError(
                f"duplicate_transition_edge: transition from {edge[0]} to {edge[1]} already exists"
            )
        seen_edges.add(edge)

        if transition.get("is_default"):
            if src_num in seen_default_sources:
                raise ValueError(
                    f"duplicate_default_transition: Step {src_num} has multiple default transitions"
                )
            seen_default_sources.add(src_num)


def validate_generated_flows(
    raw: dict,
    actor_nodes: list,
    feature_nodes: list,
    *,
    business_object_number_pattern,
    step_number_pattern,
    valid_step_types: set[str],
    valid_rule_uuids: set[str] | None = None,
) -> None:
    business_objects = raw.get("business_objects", [])
    flows = raw.get("flows", [])
    if not business_objects:
        raise ValueError("empty_business_objects")
    if not flows:
        raise ValueError("empty_flows")

    business_object_numbers = [
        item["business_object_number"]
        for item in business_objects
    ]
    business_object_number_set = validate_number_sequence(
        business_object_numbers,
        pattern=business_object_number_pattern,
        duplicate_error="duplicate_business_object_number",
        format_error="invalid_business_object_number_format",
    )
    actor_ids = {actor.actorId for actor in actor_nodes}
    feature_ids = {feature.featureId for feature in feature_nodes}
    for flow in flows:
        validate_flow(
            flow,
            step_number_pattern=step_number_pattern,
            valid_step_types=valid_step_types,
            valid_actor_ids=actor_ids,
            valid_feature_ids=feature_ids,
            valid_business_object_numbers=business_object_number_set,
            valid_rule_uuids=valid_rule_uuids,
        )
