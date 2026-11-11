import uuid

from backend.tests.fixtures.flow_graph_fixtures import (
    make_branch_and_join_fixture,
    make_branch_without_join_fixture,
    make_cycle_retry_fixture,
    make_linear_flow_fixture,
    make_multi_exit_non_judgment_fixture,
    make_multi_flow_shared_object_fixture,
    make_pure_cycle_fixture,
    make_unreachable_step_fixture,
)


def _assert_valid_uuid(uuid_str: str) -> None:
    """Verify that a given string is a valid RFC-4122 UUID."""
    val = uuid.UUID(uuid_str)
    assert str(val) == uuid_str


def test_linear_flow_fixture():
    """Verify linear fixture has strictly increasing sequence without branches."""
    fixture = make_linear_flow_fixture()
    assert fixture.id == 101
    _assert_valid_uuid(fixture.logical_uuid)
    assert len(fixture.steps) == 3
    assert len(fixture.transitions) == 2
    for step in fixture.steps:
        assert step.id > 0
        _assert_valid_uuid(step.logical_uuid)
    for trans in fixture.transitions:
        assert trans.id > 0
        _assert_valid_uuid(trans.logical_uuid)


def test_branch_and_join_fixture():
    """Verify branch and join fixture contains judgment and convergence."""
    fixture = make_branch_and_join_fixture()
    _assert_valid_uuid(fixture.logical_uuid)
    assert len(fixture.steps) == 5
    assert len(fixture.transitions) == 5
    judgment_steps = [s for s in fixture.steps if s.step_type == "judgment"]
    assert len(judgment_steps) == 1
    # Check join step 1015 has multiple incoming transitions
    incoming_to_5 = [t for t in fixture.transitions if t.target_step_id == 1015]
    assert len(incoming_to_5) == 2
    for step in fixture.steps:
        _assert_valid_uuid(step.logical_uuid)


def test_multi_exit_non_judgment_fixture():
    """Verify non-judgment step can branch out."""
    fixture = make_multi_exit_non_judgment_fixture()
    _assert_valid_uuid(fixture.logical_uuid)
    step_review = next(s for s in fixture.steps if s.id == 1022)
    assert step_review.step_type == "actorAction"
    exits = [t for t in fixture.transitions if t.source_step_id == 1022]
    assert len(exits) == 2


def test_branch_without_join_fixture():
    """Verify branches terminate separately."""
    fixture = make_branch_without_join_fixture()
    _assert_valid_uuid(fixture.logical_uuid)
    assert len(fixture.steps) == 3
    assert len(fixture.transitions) == 2
    target_ids = {t.target_step_id for t in fixture.transitions}
    assert len(target_ids) == 2  # Two distinct targets


def test_cycle_retry_fixture():
    """Verify backward edge forming retry cycle."""
    fixture = make_cycle_retry_fixture()
    _assert_valid_uuid(fixture.logical_uuid)
    backward_transitions = [
        t for t in fixture.transitions if t.target_step_id < t.source_step_id
    ]
    assert len(backward_transitions) == 1
    assert backward_transitions[0].source_step_id == 1043
    assert backward_transitions[0].target_step_id == 1042


def test_pure_cycle_fixture():
    """Verify ring cycle where every step has incoming edges."""
    fixture = make_pure_cycle_fixture()
    _assert_valid_uuid(fixture.logical_uuid)
    step_ids = {s.id for s in fixture.steps}
    target_ids = {t.target_step_id for t in fixture.transitions}
    assert step_ids == target_ids  # Every node has at least one in-edge


def test_unreachable_step_fixture():
    """Verify orphaned step with in-degree 0."""
    fixture = make_unreachable_step_fixture()
    _assert_valid_uuid(fixture.logical_uuid)
    step_ids = {s.id for s in fixture.steps}
    target_ids = {t.target_step_id for t in fixture.transitions}
    unreachable = step_ids - target_ids - {1061}  # Not target and not initial
    assert 1063 in unreachable


def test_multi_flow_shared_object_fixture():
    """Verify two flows share the same business object ID and UUID."""
    flow_a, flow_b, shared_obj = make_multi_flow_shared_object_fixture()
    assert shared_obj.id == 5001
    _assert_valid_uuid(shared_obj.logical_uuid)
    assert flow_a.business_objects[0].id == shared_obj.id
    assert flow_b.business_objects[0].id == shared_obj.id
