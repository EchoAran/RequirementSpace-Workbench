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
        "flow_transitions_added": [],
        "domain_rules_added": [],
        "rule_links_added": [],
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
            "name": business_object.get("business_object_name"),
            "description": business_object.get(
                "business_object_description", ""
            ),
        })
        if not patch["business_objects_added"][-1]["name"]:
            raise ValueError("generated_business_object_name_missing")

        attributes = business_object.get("business_object_attributes", [])
        for attribute in attributes:
            if not isinstance(attribute, dict):
                raise ValueError("generated_business_object_attribute_invalid")
            attribute_patch = {
                "business_object_ref": temporary_business_object_id,
                "name": attribute.get("business_object_attribute_name"),
                "description": attribute.get(
                    "business_object_attribute_description", ""
                ),
                "data_type": attribute.get("business_object_attribute_type"),
                "example": attribute.get(
                    "business_object_attribute_example", ""
                ),
            }
            if not attribute_patch["name"] or not attribute_patch["data_type"]:
                raise ValueError("generated_business_object_attribute_invalid")
            patch["business_object_attributes_added"].append(attribute_patch)


from dataclasses import dataclass


@dataclass
class EdgePatch:
    temp_id: str
    flow_ref: str
    source_step_ref: str
    target_step_ref: str
    condition_text: str = ""
    label: str = ""
    is_default: bool = False
    position: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "temp_id": self.temp_id,
            "flow_ref": self.flow_ref,
            "source_step_ref": self.source_step_ref,
            "target_step_ref": self.target_step_ref,
            "condition_text": self.condition_text,
            "label": self.label,
            "is_default": self.is_default,
            "position": self.position,
        }


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
        scope_patch = {
            "feature_ref": resolve_feature_ref(scope.get("feature_id")),
            "status": str(scope.get("scope_status", "")).upper(),
            "reason": scope.get("reason"),
            "kano_category": scope.get("kano_category"),
            "kano_category_name": scope.get("kano_category_name"),
            "positive_summary": scope.get("positive_summary"),
            "negative_summary": scope.get("negative_summary"),
            "positive_picture_base64": scope.get(
                "positive_picture_base64"
            ),
            "negative_picture_base64": scope.get(
                "negative_picture_base64"
            ),
        }
        if not scope_patch["feature_ref"] or not scope_patch["status"] or not scope_patch["reason"]:
            raise ValueError("generated_scope_fields_missing")
        patch["scopes_added"].append(scope_patch)


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
