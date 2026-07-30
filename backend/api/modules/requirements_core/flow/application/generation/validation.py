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
    for number in step.get("next_steps", []):
        if number not in valid_step_numbers:
            raise ValueError("invalid_next_step_reference")


def validate_flow(
    flow: dict,
    *,
    step_number_pattern,
    valid_step_types: set[str],
    valid_actor_ids: set[int],
    valid_feature_ids: set[int],
    valid_business_object_numbers: set[str],
) -> None:
    validate_feature_references(flow, valid_feature_ids)
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
        validate_step_references(
            step,
            valid_step_types=valid_step_types,
            valid_actor_ids=valid_actor_ids,
            valid_business_object_numbers=valid_business_object_numbers,
            valid_step_numbers=step_number_set,
        )


def validate_generated_flows(
    raw: dict,
    actor_nodes: list,
    feature_nodes: list,
    *,
    business_object_number_pattern,
    step_number_pattern,
    valid_step_types: set[str],
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
        )
