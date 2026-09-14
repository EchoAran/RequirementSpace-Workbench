from .apply_state import NegativeIdAllocator


def _apply_actors(
    snapshot: dict,
    patch: dict,
    allocator: NegativeIdAllocator,
) -> None:
    for actor in patch.get("actors_added", []):
        snapshot["actors"].append({
            "actor_id": allocator.temp_id_to_negative[actor["temp_id"]],
            "logical_uuid": actor.get("logical_uuid", actor["temp_id"]),
            "actor_name": actor["name"],
            "actor_description": actor["description"],
        })


def _apply_features(
    snapshot: dict,
    patch: dict,
    allocator: NegativeIdAllocator,
) -> tuple[dict, dict]:
    existing_features = {
        feature["id"]: feature
        for feature in snapshot["features"]
    }
    added_features = {}
    for feature in patch.get("features_added", []):
        negative_id = allocator.temp_id_to_negative[feature["temp_id"]]
        new_feature = {
            "feature_id": negative_id,
            "logical_uuid": feature.get("logical_uuid", feature["temp_id"]),
            "feature_name": feature["name"],
            "feature_description": feature["description"],
            "actor_ids": [],
            "parent_id": (
                allocator.resolve(feature["parent_ref"])
                if feature.get("parent_ref")
                else None
            ),
            "children_ids": [],
            "scenarios": [],
            "scope": None,
        }
        snapshot["features"].append(new_feature)
        added_features[negative_id] = new_feature
    return existing_features, added_features


def _find_feature(
    feature_id: int,
    existing_features: dict,
    added_features: dict,
):
    return (
        existing_features.get(feature_id)
        or added_features.get(feature_id)
    )


def _apply_feature_actor_links(
    patch: dict,
    allocator: NegativeIdAllocator,
    existing_features: dict,
    added_features: dict,
) -> None:
    for link in patch.get("feature_actor_links_added", []):
        feature = _find_feature(
            allocator.resolve(link["feature_ref"]),
            existing_features,
            added_features,
        )
        actor_id = allocator.resolve(link["actor_ref"])
        if feature and actor_id not in feature["actor_ids"]:
            feature["actor_ids"].append(actor_id)


def _apply_scenarios(
    patch: dict,
    allocator: NegativeIdAllocator,
    existing_features: dict,
    added_features: dict,
) -> None:
    for scenario in patch.get("scenarios_added", []):
        negative_id = allocator.temp_id_to_negative[
            scenario["temp_id"]
        ]
        feature_id = allocator.resolve(scenario["feature_ref"])
        new_scenario = {
            "scenario_id": negative_id,
            "logical_uuid": scenario.get("logical_uuid", scenario["temp_id"]),
            "scenario_name": scenario["name"],
            "scenario_content": scenario["content"],
            "feature_id": feature_id,
            "actor_id": allocator.resolve(scenario["actor_ref"]),
            "acceptance_criteria": [],
        }
        feature = _find_feature(
            feature_id,
            existing_features,
            added_features,
        )
        if feature:
            feature["scenarios"].append(new_scenario)


def _scenario_index(snapshot: dict) -> dict[int, dict]:
    scenarios_by_id = {}
    for feature in snapshot["features"]:
        for scenario in feature["scenarios"]:
            scenario_id = scenario.get("scenario_id") or scenario.get("id")
            scenarios_by_id.setdefault(scenario_id, scenario)
    return scenarios_by_id


def _apply_acceptance_criteria(
    snapshot: dict,
    patch: dict,
    allocator: NegativeIdAllocator,
) -> None:
    scenarios_by_id = _scenario_index(snapshot)
    for criterion in patch.get("acceptance_criteria_added", []):
        scenario = scenarios_by_id.get(
            allocator.resolve(criterion["scenario_ref"])
        )
        if scenario:
            scenario["acceptance_criteria"].append({
                "criterion_id": allocator.allocate(),
                "logical_uuid": criterion.get("logical_uuid"),
                "criterion_content": criterion["content"],
                "position": criterion["position"],
            })


def apply_what_nodes(
    snapshot: dict,
    patch: dict,
    allocator: NegativeIdAllocator,
) -> tuple[dict, dict]:
    _apply_actors(snapshot, patch, allocator)
    existing_features, added_features = _apply_features(
        snapshot,
        patch,
        allocator,
    )
    _apply_feature_actor_links(
        patch,
        allocator,
        existing_features,
        added_features,
    )
    _apply_scenarios(
        patch,
        allocator,
        existing_features,
        added_features,
    )
    _apply_acceptance_criteria(snapshot, patch, allocator)
    return existing_features, added_features


def _apply_scopes(
    patch: dict,
    allocator: NegativeIdAllocator,
    existing_features: dict,
    added_features: dict,
) -> None:
    for scope in patch.get("scopes_added", []):
        feature = _find_feature(
            allocator.resolve(scope["feature_ref"]),
            existing_features,
            added_features,
        )
        if feature:
            feature["scope"] = {
                "scope_id": allocator.allocate(),
                "logical_uuid": scope.get("logical_uuid"),
                "scope_status": scope["status"],
                "reason": scope["reason"],
                "positive_summary": scope.get("positive_summary"),
                "negative_summary": scope.get("negative_summary"),
                "positive_picture_base64": scope.get(
                    "positive_picture_base64"
                ),
                "negative_picture_base64": scope.get(
                    "negative_picture_base64"
                ),
                "kano_category": scope.get("kano_category"),
                "kano_category_name": scope.get("kano_category_name"),
            }


def _resolve_added_feature_children(
    existing_features: dict,
    added_features: dict,
) -> None:
    for negative_id, feature in added_features.items():
        parent_id = feature["parent_id"]
        if parent_id is None:
            continue
        parent = _find_feature(
            parent_id,
            existing_features,
            added_features,
        )
        if parent and negative_id not in parent["children_ids"]:
            parent["children_ids"].append(negative_id)


def _validate_leaf_scopes(snapshot: dict) -> None:
    for feature in snapshot["features"]:
        if not feature.get("children_ids") and not feature.get("scope"):
            raise ValueError(
                f"shadow_scope_missing:{feature.get('logical_uuid')}"
            )


def finalize_what_nodes(
    snapshot: dict,
    patch: dict,
    allocator: NegativeIdAllocator,
    existing_features: dict,
    added_features: dict,
) -> None:
    _apply_scopes(
        patch,
        allocator,
        existing_features,
        added_features,
    )
    _resolve_added_feature_children(
        existing_features,
        added_features,
    )
    _validate_leaf_scopes(snapshot)
