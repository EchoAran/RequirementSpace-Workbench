from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _PatchSections:
    actors: list
    features: list
    feature_actor_links: list
    scenarios: list
    acceptance_criteria: list
    business_objects: list
    business_object_attributes: list
    flows: list
    flow_steps: list
    scopes: list

    @classmethod
    def from_patch(cls, patch: dict) -> _PatchSections:
        return cls(
            actors=patch.get("actors_added", []),
            features=patch.get("features_added", []),
            feature_actor_links=patch.get(
                "feature_actor_links_added",
                [],
            ),
            scenarios=patch.get("scenarios_added", []),
            acceptance_criteria=patch.get(
                "acceptance_criteria_added",
                [],
            ),
            business_objects=patch.get(
                "business_objects_added",
                [],
            ),
            business_object_attributes=patch.get(
                "business_object_attributes_added",
                [],
            ),
            flows=patch.get("flows_added", []),
            flow_steps=patch.get("flow_steps_added", []),
            scopes=patch.get("scopes_added", []),
        )


@dataclass(frozen=True)
class _TempIds:
    actors: set[str]
    features: set[str]
    scenarios: set[str]
    flows: set[str]
    business_objects: set[str]
    flow_steps: set[str]


def _validate_project_id(
    base_snapshot: dict,
    project_id: str,
    allow_missing_project_id: bool,
) -> None:
    base_project_id = base_snapshot.get("project_id")
    project_mismatch = (
        base_project_id is not None
        and str(base_project_id) != str(project_id)
        if allow_missing_project_id
        else base_project_id != project_id
    )
    if project_mismatch:
        raise ValueError(
            "Project ID mismatch: base_snapshot is for project "
            f"{base_project_id}, but active project is {project_id}."
        )


def _collect_real_ids(base_snapshot: dict) -> dict[str, set]:
    features = base_snapshot.get("features", [])
    flows = base_snapshot.get("flows", [])
    return {
        "actor": {
            item["id"]
            for item in base_snapshot.get("actors", [])
        },
        "feature": {item["id"] for item in features},
        "scenario": {
            scenario["id"]
            for feature in features
            for scenario in feature.get("scenarios", [])
        },
        "flow": {item["id"] for item in flows},
        "business_object": {
            item["id"]
            for item in base_snapshot.get("business_objects", [])
        },
        "flow_step": {
            step["id"]
            for flow in flows
            for step in flow.get("flow_steps", [])
        },
    }


def _verify_ref(
    ref: str,
    expected_type: str,
    allowed_temp_ids: set[str],
    real_ids: dict[str, set],
    project_id: str,
) -> bool:
    if not ref:
        return False
    if ref.startswith("tmp_"):
        if ref not in allowed_temp_ids:
            raise ValueError(
                f"Invalid temporary reference '{ref}': "
                "not defined in patch."
            )
        return True

    parts = ref.split(":")
    if len(parts) != 2:
        raise ValueError(
            f"Invalid reference format '{ref}'. Must be type:id."
        )

    ref_type, ref_id_str = parts[0], parts[1]
    if ref_type != expected_type:
        raise ValueError(
            f"Reference type mismatch for '{ref}': expected "
            f"'{expected_type}', got '{ref_type}'."
        )

    try:
        ref_id = int(ref_id_str)
    except ValueError:
        raise ValueError(
            f"Invalid non-integer ID in reference '{ref}'."
        )

    if ref_id in real_ids[ref_type]:
        return True

    labels = {
        "actor": "Actor",
        "feature": "Feature",
        "scenario": "Scenario",
        "flow": "Flow",
        "business_object": "Business Object",
        "flow_step": "Flow Step",
    }
    raise ValueError(
        f"{labels[ref_type]} ID {ref_id} in reference '{ref}' "
        f"does not exist or belong to project {project_id}."
    )


def _add_temp_id(
    temp_id: str,
    category_ids: set[str],
    all_temp_ids: set[str],
    field_name: str,
) -> None:
    if not temp_id:
        raise ValueError(f"Empty temp_id in {field_name}.")
    if not temp_id.startswith("tmp_"):
        raise ValueError(
            f"Temporary ID '{temp_id}' in {field_name} "
            "must start with 'tmp_'."
        )
    if temp_id in all_temp_ids:
        raise ValueError(
            f"Duplicate temp_id '{temp_id}' across patch elements."
        )
    all_temp_ids.add(temp_id)
    category_ids.add(temp_id)


def _collect_temp_ids(sections: _PatchSections) -> _TempIds:
    all_temp_ids: set[str] = set()
    category_specs = (
        (sections.actors, set(), "actors_added"),
        (sections.features, set(), "features_added"),
        (sections.scenarios, set(), "scenarios_added"),
        (
            sections.business_objects,
            set(),
            "business_objects_added",
        ),
        (sections.flows, set(), "flows_added"),
        (sections.flow_steps, set(), "flow_steps_added"),
    )
    for items, category_ids, field_name in category_specs:
        for item in items:
            _add_temp_id(
                item.get("temp_id"),
                category_ids,
                all_temp_ids,
                field_name,
            )

    return _TempIds(
        actors=category_specs[0][1],
        features=category_specs[1][1],
        scenarios=category_specs[2][1],
        business_objects=category_specs[3][1],
        flows=category_specs[4][1],
        flow_steps=category_specs[5][1],
    )


def _validate_what_references(
    sections: _PatchSections,
    temp_ids: _TempIds,
    real_ids: dict[str, set],
    project_id: str,
) -> None:
    for feature in sections.features:
        parent_ref = feature.get("parent_ref")
        if parent_ref:
            _verify_ref(
                parent_ref,
                "feature",
                temp_ids.features,
                real_ids,
                project_id,
            )

    for link in sections.feature_actor_links:
        _verify_ref(
            link.get("feature_ref"),
            "feature",
            temp_ids.features,
            real_ids,
            project_id,
        )
        _verify_ref(
            link.get("actor_ref"),
            "actor",
            temp_ids.actors,
            real_ids,
            project_id,
        )

    for scenario in sections.scenarios:
        _verify_ref(
            scenario.get("feature_ref"),
            "feature",
            temp_ids.features,
            real_ids,
            project_id,
        )
        _verify_ref(
            scenario.get("actor_ref"),
            "actor",
            temp_ids.actors,
            real_ids,
            project_id,
        )


def _validate_acceptance_criteria(
    sections: _PatchSections,
    temp_ids: _TempIds,
    real_ids: dict[str, set],
    project_id: str,
) -> None:
    for criterion in sections.acceptance_criteria:
        _verify_ref(
            criterion.get("scenario_ref"),
            "scenario",
            temp_ids.scenarios,
            real_ids,
            project_id,
        )
        if not criterion.get("content", "").strip():
            raise ValueError(
                "Acceptance Criterion content cannot be empty."
            )


def _validate_business_object_attributes(
    sections: _PatchSections,
    temp_ids: _TempIds,
    real_ids: dict[str, set],
    project_id: str,
) -> None:
    for attribute in sections.business_object_attributes:
        _verify_ref(
            attribute.get("business_object_ref"),
            "business_object",
            temp_ids.business_objects,
            real_ids,
            project_id,
        )
        if not attribute.get("name", "").strip():
            raise ValueError(
                "Business Object Attribute name cannot be empty."
            )
        if not attribute.get("data_type", "").strip():
            raise ValueError(
                "Business Object Attribute data_type cannot be empty."
            )


def _validate_flows(
    sections: _PatchSections,
    temp_ids: _TempIds,
    real_ids: dict[str, set],
    project_id: str,
) -> None:
    for flow in sections.flows:
        feature_refs = flow.get("feature_refs", [])
        if not feature_refs:
            raise ValueError(
                f"Flow '{flow.get('name')}' must reference at least "
                "one feature."
            )
        for feature_ref in feature_refs:
            _verify_ref(
                feature_ref,
                "feature",
                temp_ids.features,
                real_ids,
                project_id,
            )


def _validate_step_references(
    step: dict,
    temp_ids: _TempIds,
    real_ids: dict[str, set],
    project_id: str,
) -> None:
    actor_refs = step.get("actor_refs", [])
    input_bo_refs = step.get("input_bo_refs", [])
    output_bo_refs = step.get("output_bo_refs", [])
    next_step_refs = step.get("next_step_refs", [])
    if step.get("step_type") == "actorAction" and not actor_refs:
        raise ValueError(
            f"Flow step '{step.get('name')}' of type 'actorAction' "
            "must reference at least one actor."
        )

    reference_specs = (
        (actor_refs, "actor", temp_ids.actors),
        (
            input_bo_refs,
            "business_object",
            temp_ids.business_objects,
        ),
        (
            output_bo_refs,
            "business_object",
            temp_ids.business_objects,
        ),
        (next_step_refs, "flow_step", temp_ids.flow_steps),
    )
    for references, expected_type, allowed_temp_ids in reference_specs:
        for reference in references:
            _verify_ref(
                reference,
                expected_type,
                allowed_temp_ids,
                real_ids,
                project_id,
            )


def _validate_flow_steps(
    sections: _PatchSections,
    temp_ids: _TempIds,
    real_ids: dict[str, set],
    project_id: str,
) -> None:
    steps_by_flow: dict[str, list[dict]] = {}
    for step in sections.flow_steps:
        flow_ref = step.get("flow_ref")
        _verify_ref(
            flow_ref,
            "flow",
            temp_ids.flows,
            real_ids,
            project_id,
        )
        steps_by_flow.setdefault(flow_ref, []).append(step)
        _validate_step_references(
            step,
            temp_ids,
            real_ids,
            project_id,
        )

    for flow_ref, steps in steps_by_flow.items():
        positions = []
        for step in steps:
            position = step.get("position")
            if position is None:
                raise ValueError(
                    f"Step '{step.get('name')}' is missing a "
                    "position index."
                )
            positions.append(position)

        sorted_positions = sorted(positions)
        if sorted_positions != list(range(1, len(steps) + 1)):
            raise ValueError(
                f"Flow steps positions for flow '{flow_ref}' are not "
                "consecutive and sequential starting from 1. "
                f"Got: {sorted_positions}"
            )


def _validate_scopes(
    sections: _PatchSections,
    temp_ids: _TempIds,
    real_ids: dict[str, set],
    project_id: str,
) -> None:
    for scope in sections.scopes:
        feature_ref = scope.get("feature_ref")
        _verify_ref(
            feature_ref,
            "feature",
            temp_ids.features,
            real_ids,
            project_id,
        )
        status = scope.get("status")
        if status not in {"CURRENT", "POSTPONED", "EXCLUDE"}:
            raise ValueError(
                f"Invalid scope status '{status}' for feature "
                f"reference '{feature_ref}'. Must be one of "
                "'CURRENT', 'POSTPONED', 'EXCLUDE'."
            )
        if not scope.get("reason", "").strip():
            raise ValueError(
                f"Scope for feature '{feature_ref}' is missing a "
                "rationale reason."
            )


class ShadowPatchValidator:
    @staticmethod
    def validate_patch(
        patch: dict,
        base_snapshot: dict,
        project_id: str,
        *,
        allow_missing_project_id: bool = False,
    ) -> bool:
        _validate_project_id(
            base_snapshot,
            project_id,
            allow_missing_project_id,
        )
        real_ids = _collect_real_ids(base_snapshot)
        sections = _PatchSections.from_patch(patch)
        temp_ids = _collect_temp_ids(sections)
        validators = (
            _validate_what_references,
            _validate_acceptance_criteria,
            _validate_business_object_attributes,
            _validate_flows,
            _validate_flow_steps,
            _validate_scopes,
        )
        for validator in validators:
            validator(sections, temp_ids, real_ids, project_id)
        return True
