"""Unit tests for flow transition domain model invariants."""

import pytest

from backend.api.modules.requirements_core.flow.domain.model_invariants import (
    normalize_semantic_tags,
    validate_default_transition_exclusivity,
    validate_no_self_loop,
    validate_transition_flow_boundary,
    validate_transition_labels,
    validate_transition_position,
)


def test_normalize_semantic_tags_deduplicates_and_sorts():
    """Verify semantic tags are trimmed, deduplicated, and sorted alphabetically."""
    raw = ["  happy_path ", "exception", "happy_path", "", "  ", "audit_log"]
    result = normalize_semantic_tags(raw)
    assert result == ["audit_log", "exception", "happy_path"]


def test_normalize_semantic_tags_handles_empty():
    """Verify empty or None tags produce an empty list."""
    assert normalize_semantic_tags(None) == []
    assert normalize_semantic_tags([]) == []


def test_validate_transition_flow_boundary_success():
    """Verify valid matching flow boundaries pass without exception."""
    validate_transition_flow_boundary(
        source_flow_id=10,
        target_flow_id=10,
        expected_flow_id=10,
        source_project_id=1,
        target_project_id=1,
        expected_project_id=1,
        source_workspace_id=5,
        target_workspace_id=5,
        expected_workspace_id=5,
    )


def test_validate_transition_flow_boundary_mismatch_raises():
    """Verify mismatched flow or project boundaries raise ValueError."""
    with pytest.raises(ValueError, match="Source step flow"):
        validate_transition_flow_boundary(
            source_flow_id=11,
            target_flow_id=10,
            expected_flow_id=10,
        )

    with pytest.raises(ValueError, match="Target step flow"):
        validate_transition_flow_boundary(
            source_flow_id=10,
            target_flow_id=12,
            expected_flow_id=10,
        )

    with pytest.raises(ValueError, match="Source step project"):
        validate_transition_flow_boundary(
            source_flow_id=10,
            target_flow_id=10,
            expected_flow_id=10,
            source_project_id=2,
            expected_project_id=1,
        )

    with pytest.raises(ValueError, match="Target step project"):
        validate_transition_flow_boundary(
            source_flow_id=10,
            target_flow_id=10,
            expected_flow_id=10,
            source_project_id=1,
            target_project_id=2,
            expected_project_id=1,
        )

    with pytest.raises(ValueError, match="Source step workspace"):
        validate_transition_flow_boundary(
            source_flow_id=10,
            target_flow_id=10,
            expected_flow_id=10,
            source_project_id=1,
            target_project_id=1,
            expected_project_id=1,
            source_workspace_id=9,
            target_workspace_id=5,
            expected_workspace_id=5,
        )

    with pytest.raises(ValueError, match="Target step workspace"):
        validate_transition_flow_boundary(
            source_flow_id=10,
            target_flow_id=10,
            expected_flow_id=10,
            source_project_id=1,
            target_project_id=1,
            expected_project_id=1,
            source_workspace_id=5,
            target_workspace_id=9,
            expected_workspace_id=5,
        )


def test_validate_no_self_loop():
    """Verify self-loops raise ValueError, while distinct steps pass."""
    validate_no_self_loop(source_step_id=1, target_step_id=2)
    with pytest.raises(ValueError, match="Self-loop"):
        validate_no_self_loop(source_step_id=5, target_step_id=5)


def test_validate_transition_position():
    """Verify negative positions raise ValueError, while non-negative pass."""
    validate_transition_position(0)
    validate_transition_position(5)
    with pytest.raises(ValueError, match="non-negative"):
        validate_transition_position(-1)


def test_validate_transition_labels():
    """Verify whitespace is trimmed from label and condition text."""
    lbl, cond = validate_transition_labels("  Approve  ", "  amount > 100 \n")
    assert lbl == "Approve"
    assert cond == "amount > 100"


def test_validate_default_transition_exclusivity():
    """Verify at most one default transition per step is enforced."""
    # When is_default is False, always passes
    validate_default_transition_exclusivity(False, existing_default_transition_id=10)
    # When is_default is True and no existing default, passes
    validate_default_transition_exclusivity(True, existing_default_transition_id=None)
    # When is_default is True and same transition being updated, passes
    validate_default_transition_exclusivity(True, existing_default_transition_id=10, current_transition_id=10)
    # When is_default is True and different transition is already default, raises
    with pytest.raises(ValueError, match="already has default transition"):
        validate_default_transition_exclusivity(True, existing_default_transition_id=10, current_transition_id=20)
