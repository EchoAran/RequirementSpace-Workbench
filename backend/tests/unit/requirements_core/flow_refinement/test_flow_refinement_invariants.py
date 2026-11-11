import pytest

from backend.api.modules.requirements_core.flow_refinement.domain.invariants import (
    MAX_ADDED_RULES,
    MAX_ADDED_STEPS,
    MAX_ADDED_TRANSITIONS,
    validate_no_confirmed_rule_modifications,
    validate_refinement_bounds,
    validate_refinement_references,
    validate_refinement_temp_ids,
)


def test_refinement_bounds_success():
    steps = [{"temp_id": f"temp_step_{i}"} for i in range(MAX_ADDED_STEPS)]
    transitions = [{"temp_id": f"temp_trans_{i}"} for i in range(MAX_ADDED_TRANSITIONS)]
    rules = [{"temp_id": f"temp_rule_{i}"} for i in range(MAX_ADDED_RULES)]

    validate_refinement_bounds(steps, transitions, rules)


def test_refinement_bounds_exceeded_steps():
    steps = [{"temp_id": f"temp_step_{i}"} for i in range(MAX_ADDED_STEPS + 1)]
    transitions = []
    rules = []

    with pytest.raises(ValueError) as excinfo:
        validate_refinement_bounds(steps, transitions, rules)
    assert "refinement_step_limit_exceeded" in str(excinfo.value)


def test_refinement_bounds_exceeded_transitions():
    steps = []
    transitions = [{"temp_id": f"temp_trans_{i}"} for i in range(MAX_ADDED_TRANSITIONS + 1)]
    rules = []

    with pytest.raises(ValueError) as excinfo:
        validate_refinement_bounds(steps, transitions, rules)
    assert "refinement_transition_limit_exceeded" in str(excinfo.value)


def test_refinement_bounds_exceeded_rules():
    steps = []
    transitions = []
    rules = [{"temp_id": f"temp_rule_{i}"} for i in range(MAX_ADDED_RULES + 1)]

    with pytest.raises(ValueError) as excinfo:
        validate_refinement_bounds(steps, transitions, rules)
    assert "refinement_rule_limit_exceeded" in str(excinfo.value)


def test_refinement_temp_ids_valid():
    steps = [{"temp_id": "temp_step_1"}, {"temp_id": "temp_step_2"}]
    transitions = [{"temp_id": "temp_trans_1"}]
    rules = [{"temp_id": "temp_rule_1"}]

    validate_refinement_temp_ids(steps, transitions, rules)


def test_refinement_temp_ids_duplicate():
    steps = [{"temp_id": "temp_step_1"}, {"temp_id": "temp_step_1"}]
    with pytest.raises(ValueError) as excinfo:
        validate_refinement_temp_ids(steps, [], [])
    assert "duplicate_step_temp_id: temp_step_1" in str(excinfo.value)


def test_refinement_temp_ids_missing():
    steps = [{}]
    with pytest.raises(ValueError) as excinfo:
        validate_refinement_temp_ids(steps, [], [])
    assert "missing_step_temp_id" in str(excinfo.value)


def test_refinement_references_valid():
    steps = [{"temp_id": "temp_step_1"}]
    transitions_added = [
        {"source_step_ref": 1, "target_step_ref": "temp_step_1"}
    ]
    transitions_updated = [
        {"logical_uuid": "trans-uuid-1"}
    ]
    rules = [
        {
            "temp_id": "temp_rule_1",
            "parent_rule_ref": "rule-uuid-1",
            "source_links": [
                {"target_kind": "feature", "target_ref": "feat-uuid-1"}
            ],
        }
    ]
    rule_links = [
        {"rule_ref": "temp_rule_1", "target_kind": "flow_step", "target_ref": "temp_step_1"}
    ]

    validate_refinement_references(
        steps_added=steps,
        transitions_added=transitions_added,
        transitions_updated=transitions_updated,
        rules_added=rules,
        rule_links_added=rule_links,
        existing_step_positions={1, 2},
        existing_step_uuids={"step-uuid-1", "step-uuid-2"},
        existing_transition_uuids={"trans-uuid-1"},
        existing_rule_uuids={"rule-uuid-1"},
        context_feature_uuids={"feat-uuid-1"},
    )


def test_refinement_references_invalid_step_ref():
    transitions_added = [
        {"source_step_ref": 999, "target_step_ref": "temp_step_1"}
    ]
    with pytest.raises(ValueError) as excinfo:
        validate_refinement_references(
            steps_added=[{"temp_id": "temp_step_1"}],
            transitions_added=transitions_added,
            transitions_updated=[],
            rules_added=[],
            rule_links_added=[],
            existing_step_positions={1},
            existing_step_uuids=set(),
            existing_transition_uuids=set(),
            existing_rule_uuids=set(),
        )
    assert "invalid_transition_source_reference: 999" in str(excinfo.value)


def test_refinement_references_invalid_transition_update():
    transitions_updated = [
        {"logical_uuid": "unknown-trans-uuid"}
    ]
    with pytest.raises(ValueError) as excinfo:
        validate_refinement_references(
            steps_added=[],
            transitions_added=[],
            transitions_updated=transitions_updated,
            rules_added=[],
            rule_links_added=[],
            existing_step_positions=set(),
            existing_step_uuids=set(),
            existing_transition_uuids={"known-trans-uuid"},
            existing_rule_uuids=set(),
        )
    assert "invalid_updated_transition_reference: unknown-trans-uuid" in str(excinfo.value)


def test_refinement_references_invalid_rule_link_target():
    rule_links = [
        {"rule_ref": "temp_rule_1", "target_kind": "flow_step", "target_ref": "unknown_step"}
    ]
    with pytest.raises(ValueError) as excinfo:
        validate_refinement_references(
            steps_added=[{"temp_id": "temp_step_1"}],
            transitions_added=[],
            transitions_updated=[],
            rules_added=[{"temp_id": "temp_rule_1", "parent_rule_ref": "rule-1"}],
            rule_links_added=rule_links,
            existing_step_positions=set(),
            existing_step_uuids={"step-1"},
            existing_transition_uuids=set(),
            existing_rule_uuids={"rule-1"},
        )
    assert "invalid_rule_link_step_target: unknown_step" in str(excinfo.value)


def test_refinement_references_rule_missing_evidence():
    with pytest.raises(ValueError) as excinfo:
        validate_refinement_references(
            steps_added=[],
            transitions_added=[],
            transitions_updated=[],
            rules_added=[{"temp_id": "temp_rule_1"}],
            rule_links_added=[],
            existing_step_positions=set(),
            existing_step_uuids=set(),
            existing_transition_uuids=set(),
            existing_rule_uuids=set(),
        )
    assert "rule_lacks_parent_or_source_evidence: temp_rule_1" in str(excinfo.value)


def test_refinement_references_local_radius_violation():
    # flow_step refinement target with transitions outside allowed 1-layer radius
    transitions_added = [
        {"source_step_ref": 10, "target_step_ref": 11}
    ]
    with pytest.raises(ValueError) as excinfo:
        validate_refinement_references(
            steps_added=[],
            transitions_added=transitions_added,
            transitions_updated=[],
            rules_added=[],
            rule_links_added=[],
            existing_step_positions={1, 2, 10, 11},
            existing_step_uuids={"s1", "s2", "s10", "s11"},
            existing_transition_uuids=set(),
            existing_rule_uuids=set(),
            target_kind="flow_step",
            allowed_step_positions={1, 2},
            allowed_step_uuids={"s1", "s2"},
        )
    assert "transition_outside_local_refinement_radius" in str(excinfo.value)


def test_flow_step_radius_rejects_boundary_crossing_edges():
    # Boundary crossing: source inside radius (1), target outside radius (10)
    transitions_added_1 = [
        {"source_step_ref": 1, "target_step_ref": 10}
    ]
    with pytest.raises(ValueError) as excinfo1:
        validate_refinement_references(
            steps_added=[],
            transitions_added=transitions_added_1,
            transitions_updated=[],
            rules_added=[],
            rule_links_added=[],
            existing_step_positions={1, 2, 10},
            existing_step_uuids={"s1", "s2", "s10"},
            existing_transition_uuids=set(),
            existing_rule_uuids=set(),
            target_kind="flow_step",
            allowed_step_positions={1, 2},
            allowed_step_uuids={"s1", "s2"},
        )
    assert "transition_outside_local_refinement_radius" in str(excinfo1.value)

    # Boundary crossing: source outside radius (10), target inside radius (2)
    transitions_added_2 = [
        {"source_step_ref": 10, "target_step_ref": 2}
    ]
    with pytest.raises(ValueError) as excinfo2:
        validate_refinement_references(
            steps_added=[],
            transitions_added=transitions_added_2,
            transitions_updated=[],
            rules_added=[],
            rule_links_added=[],
            existing_step_positions={1, 2, 10},
            existing_step_uuids={"s1", "s2", "s10"},
            existing_transition_uuids=set(),
            existing_rule_uuids=set(),
            target_kind="flow_step",
            allowed_step_positions={1, 2},
            allowed_step_uuids={"s1", "s2"},
        )
    assert "transition_outside_local_refinement_radius" in str(excinfo2.value)


def test_refinement_references_source_link_whitelist_violation():
    rules = [
        {
            "temp_id": "temp_rule_1",
            "source_links": [
                {"target_kind": "feature", "target_ref": "unauthorized-feature-uuid"}
            ],
        }
    ]
    with pytest.raises(ValueError) as excinfo:
        validate_refinement_references(
            steps_added=[],
            transitions_added=[],
            transitions_updated=[],
            rules_added=rules,
            rule_links_added=[],
            existing_step_positions=set(),
            existing_step_uuids=set(),
            existing_transition_uuids=set(),
            existing_rule_uuids=set(),
            context_feature_uuids={"authorized-feature-uuid"},
        )
    assert "rule_source_link_not_in_context: feature unauthorized-feature-uuid" in str(excinfo.value)


def test_no_confirmed_rule_modifications():
    confirmed_statements = {"Order total must exceed zero.", "User must be authenticated."}
    rules = [{"statement": "Discount cannot exceed 50%"}]
    validate_no_confirmed_rule_modifications(rules, confirmed_statements)

    violating_rules = [{"statement": "Order total must exceed zero."}]
    with pytest.raises(ValueError) as excinfo:
        validate_no_confirmed_rule_modifications(violating_rules, confirmed_statements)
    assert "confirmed_rule_modification_forbidden" in str(excinfo.value)

    # Rejection of confirmation_status != "ai_assumption"
    confirmed_status_rules = [{"statement": "New Rule", "confirmation_status": "confirmed"}]
    with pytest.raises(ValueError) as excinfo:
        validate_no_confirmed_rule_modifications(confirmed_status_rules, confirmed_statements)
    assert "confirmed_rule_generation_forbidden" in str(excinfo.value)


def test_flow_step_radius_rejects_out_of_radius_rule_link_step():
    rule_links = [
        {"rule_ref": "r1", "target_kind": "flow_step", "target_ref": "s10"}
    ]
    with pytest.raises(ValueError) as excinfo:
        validate_refinement_references(
            steps_added=[],
            transitions_added=[],
            transitions_updated=[],
            rules_added=[{"temp_id": "r1", "parent_rule_ref": "r0"}],
            rule_links_added=rule_links,
            existing_step_positions={1, 2, 10},
            existing_step_uuids={"s1", "s2", "s10"},
            existing_transition_uuids=set(),
            existing_rule_uuids={"r0"},
            target_kind="flow_step",
            allowed_step_positions={1, 2},
            allowed_step_uuids={"s1", "s2"},
        )
    assert "invalid_rule_link_step_target: s10" in str(excinfo.value)


def test_flow_step_radius_rejects_out_of_radius_rule_link_transition():
    rule_links = [
        {"rule_ref": "r1", "target_kind": "flow_transition", "target_ref": "t10"}
    ]
    with pytest.raises(ValueError) as excinfo:
        validate_refinement_references(
            steps_added=[],
            transitions_added=[],
            transitions_updated=[],
            rules_added=[{"temp_id": "r1", "parent_rule_ref": "r0"}],
            rule_links_added=rule_links,
            existing_step_positions={1, 2},
            existing_step_uuids={"s1", "s2"},
            existing_transition_uuids={"t1", "t10"},
            existing_rule_uuids={"r0"},
            target_kind="flow_step",
            allowed_step_positions={1, 2},
            allowed_step_uuids={"s1", "s2"},
            allowed_transition_uuids={"t1"},
        )
    assert "invalid_rule_link_transition_target: t10" in str(excinfo.value)


def test_flow_step_radius_rejects_out_of_radius_rule_source_link_step():
    rules = [
        {
            "temp_id": "r1",
            "source_links": [{"target_kind": "flow_step", "target_ref": "s10"}],
        }
    ]
    with pytest.raises(ValueError) as excinfo:
        validate_refinement_references(
            steps_added=[],
            transitions_added=[],
            transitions_updated=[],
            rules_added=rules,
            rule_links_added=[],
            existing_step_positions={1, 2, 10},
            existing_step_uuids={"s1", "s2", "s10"},
            existing_transition_uuids=set(),
            existing_rule_uuids=set(),
            target_kind="flow_step",
            allowed_step_positions={1, 2},
            allowed_step_uuids={"s1", "s2"},
        )
    assert "rule_source_link_not_in_context: flow_step s10" in str(excinfo.value)


def test_flow_step_radius_rejects_out_of_radius_step_actor():
    steps = [
        {
            "temp_id": "step-new-1",
            "name": "New Step",
            "actor_ids": [99],
        }
    ]
    with pytest.raises(ValueError) as excinfo:
        validate_refinement_references(
            steps_added=steps,
            transitions_added=[],
            transitions_updated=[],
            rules_added=[],
            rule_links_added=[],
            existing_step_positions={1, 2},
            existing_step_uuids={"s1", "s2"},
            existing_transition_uuids=set(),
            existing_rule_uuids=set(),
            target_kind="flow_step",
            allowed_step_positions={1, 2},
            allowed_step_uuids={"s1", "s2"},
            allowed_actor_ids={1, 2},
        )
    assert "step_actor_outside_local_refinement_radius: actor 99" in str(excinfo.value)


def test_flow_step_radius_rejects_out_of_radius_step_business_object():
    steps = [
        {
            "temp_id": "step-new-1",
            "name": "New Step",
            "input_business_object_numbers": ["BO-99"],
        }
    ]
    with pytest.raises(ValueError) as excinfo:
        validate_refinement_references(
            steps_added=steps,
            transitions_added=[],
            transitions_updated=[],
            rules_added=[],
            rule_links_added=[],
            existing_step_positions={1, 2},
            existing_step_uuids={"s1", "s2"},
            existing_transition_uuids=set(),
            existing_rule_uuids=set(),
            target_kind="flow_step",
            allowed_step_positions={1, 2},
            allowed_step_uuids={"s1", "s2"},
            allowed_bo_numbers={"BO-1"},
        )
    assert "step_business_object_outside_local_refinement_radius: business_object BO-99" in str(excinfo.value)


def test_flow_step_radius_accepts_new_business_object_and_in_radius_actor():
    steps = [
        {
            "temp_id": "step-new-1",
            "name": "New Step",
            "actor_ids": [1],
            "input_business_object_numbers": ["BO-1"],
            "output_business_object_numbers": ["BO-NEW-1"],
        }
    ]
    bos = [
        {
            "business_object_number": "BO-NEW-1",
            "business_object_name": "New Order",
            "business_object_description": "New Order description",
            "business_object_attributes": [{"name": "total", "data_type": "float"}],
        }
    ]
    # Should not raise any exception
    validate_refinement_references(
        steps_added=steps,
        transitions_added=[],
        transitions_updated=[],
        rules_added=[],
        rule_links_added=[],
        business_objects_added=bos,
        existing_step_positions={1, 2},
        existing_step_uuids={"s1", "s2"},
        existing_transition_uuids=set(),
        existing_rule_uuids=set(),
        target_kind="flow_step",
        allowed_step_positions={1, 2},
        allowed_step_uuids={"s1", "s2"},
        allowed_actor_ids={1, 2},
        allowed_bo_numbers={"BO-1"},
    )
