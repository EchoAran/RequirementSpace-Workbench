from typing import Any


def _create_empty_patch() -> dict[str, list]:
    return {
        "actors_added": [],
        "features_added": [],
        "feature_actor_links_added": [],
        "scenarios_added": [],
        "acceptance_criteria_added": [],
        "business_objects_added": [],
        "business_object_attributes_added": [],
        "flows_added": [],
        "flow_steps_added": [],
        "scopes_added": [],
    }


def _append_generated_business_objects(patch: dict, raw_flows: dict) -> None:
    for business_object_index, business_object in enumerate(
        raw_flows.get("business_objects", [])
    ):
        business_object_number = f"gen_{business_object_index + 1}"
        temporary_business_object_id = f"tmp_bo_{business_object_number}"
        patch["business_objects_added"].append({
            "temp_id": temporary_business_object_id,
            "name": (
                business_object.get("business_object_name")
                or business_object.get("name")
            ),
            "description": (
                business_object.get("business_object_description")
                or business_object.get("description")
            ),
        })

        attributes = business_object.get("business_object_attributes", [])
        if not attributes:
            attributes = [
                {
                    "name": "id",
                    "description": "唯一标识",
                    "data_type": "integer",
                    "example": "1",
                },
                {
                    "name": "name",
                    "description": "名称",
                    "data_type": "string",
                    "example": "示例名称",
                },
            ]
        for attribute in attributes:
            if not isinstance(attribute, dict):
                continue
            patch["business_object_attributes_added"].append({
                "business_object_ref": temporary_business_object_id,
                "name": (
                    attribute.get("business_object_attribute_name")
                    or attribute.get("name")
                    or "未命名属性"
                ),
                "description": (
                    attribute.get("business_object_attribute_description")
                    or attribute.get("description")
                    or ""
                ),
                "data_type": (
                    attribute.get("business_object_attribute_type")
                    or attribute.get("data_type")
                    or "string"
                ),
                "example": (
                    attribute.get("business_object_attribute_example")
                    or attribute.get("example")
                    or ""
                ),
            })


def _resolve_next_step_refs(
    flow_number: str,
    step_index_by_number: dict,
    next_step_numbers: list,
) -> list[str]:
    next_step_refs = []
    for next_step_number in next_step_numbers:
        if next_step_number in step_index_by_number:
            mapped_index = step_index_by_number[next_step_number]
            next_step_refs.append(
                f"tmp_step_{flow_number}_gen_{mapped_index + 1}"
            )
        else:
            next_step_refs.append(
                f"tmp_step_{flow_number}_{next_step_number}"
            )
    return next_step_refs


def _resolve_preserved_scope_feature_ref(feature_id: Any) -> str:
    if isinstance(feature_id, int):
        return f"feature:{feature_id}"
    if str(feature_id).startswith("tmp_"):
        return feature_id
    return f"tmp_feature_{feature_id}"


def _append_generated_scopes(
    patch: dict,
    scopes: list[dict],
    resolve_feature_ref,
) -> None:
    for scope in scopes:
        patch["scopes_added"].append({
            "feature_ref": resolve_feature_ref(scope.get("feature_id")),
            "status": (
                scope.get("scope_status")
                or scope.get("status")
                or "CURRENT"
            ).upper(),
            "reason": scope.get("reason") or "AI影子收敛补充",
            "kano_category": scope.get("kano_category") or "M",
            "kano_category_name": (
                scope.get("kano_category_name") or "Must-be"
            ),
            "positive_summary": (
                scope.get("positive_summary") or "已支持"
            ),
            "negative_summary": (
                scope.get("negative_summary") or "不满足"
            ),
            "positive_picture_base64": scope.get(
                "positive_picture_base64"
            ),
            "negative_picture_base64": scope.get(
                "negative_picture_base64"
            ),
        })


def _build_generated_reference_map(
    temporary_id_to_raw_id: dict[str, Any],
) -> dict:
    reference_by_id = {}
    for temporary_id, raw_id in temporary_id_to_raw_id.items():
        reference_by_id[raw_id] = temporary_id
        reference_by_id[str(raw_id)] = temporary_id
        reference_by_id[temporary_id] = temporary_id
    return reference_by_id


def _resolve_generated_reference(
    value: Any,
    reference_by_id: dict,
    entity_prefix: str,
    temporary_prefix: str,
) -> str:
    if not value:
        return ""
    value_text = str(value).strip()
    if value_text.startswith(temporary_prefix):
        return value_text

    raw_id = value
    full_prefix = f"{entity_prefix}:"
    if value_text.startswith(full_prefix):
        prefixed_value = value_text.split(":", 1)[1]
        try:
            raw_id = int(prefixed_value)
        except ValueError:
            raw_id = prefixed_value
    else:
        try:
            raw_id = int(value)
        except (ValueError, TypeError):
            raw_id = value

    if raw_id in reference_by_id:
        return reference_by_id[raw_id]
    if str(raw_id) in reference_by_id:
        return reference_by_id[str(raw_id)]
    if isinstance(raw_id, int):
        return f"{entity_prefix}:{raw_id}"
    if value_text.startswith(full_prefix):
        return value_text
    return f"{temporary_prefix}{value}"
