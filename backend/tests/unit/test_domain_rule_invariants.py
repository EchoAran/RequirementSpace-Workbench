"""Unit tests for domain rule model invariants."""

import pytest

from backend.api.modules.requirements_core.domain_rule.domain.model_invariants import (
    ALLOWED_RULE_LINK_TARGET_KINDS,
    validate_parent_hierarchy,
    validate_rule_confirmation_status,
    validate_rule_link_purpose,
    validate_rule_link_target,
    validate_rule_origin,
    validate_rule_text,
)


def test_validate_rule_text_valid():
    """Ensure valid title and statement pass without error."""
    validate_rule_text("Payment Timeout Rule", "Orders must be cancelled after 15 minutes of inactivity.")


def test_validate_rule_text_empty_title():
    """Empty or whitespace-only title must raise ValueError."""
    with pytest.raises(ValueError, match="title cannot be empty"):
        validate_rule_text("", "Some statement")
    with pytest.raises(ValueError, match="title cannot be empty"):
        validate_rule_text("   ", "Some statement")


def test_validate_rule_text_title_too_long():
    """Title exceeding 255 chars must raise ValueError."""
    with pytest.raises(ValueError, match="exceed 255 characters"):
        validate_rule_text("A" * 256, "Some statement")


def test_validate_rule_text_empty_statement():
    """Empty or whitespace-only statement must raise ValueError."""
    with pytest.raises(ValueError, match="statement cannot be empty"):
        validate_rule_text("Valid Title", "")
    with pytest.raises(ValueError, match="statement cannot be empty"):
        validate_rule_text("Valid Title", "   \n\t  ")


def test_validate_parent_hierarchy_self_reference():
    """Rule cannot be assigned as its own parent."""
    with pytest.raises(ValueError, match="cannot be its own parent"):
        validate_parent_hierarchy(rule_id=1, parent_rule_id=1, ancestor_ids=set())


def test_validate_parent_hierarchy_cycle():
    """Assigning a descendant or ancestor containing rule_id must raise ValueError."""
    with pytest.raises(ValueError, match="Cyclic parent hierarchy"):
        validate_parent_hierarchy(rule_id=3, parent_rule_id=1, ancestor_ids={1, 2, 3})


def test_validate_parent_hierarchy_valid():
    """Valid parent without cycles passes."""
    validate_parent_hierarchy(rule_id=3, parent_rule_id=2, ancestor_ids={1})
    validate_parent_hierarchy(rule_id=None, parent_rule_id=2, ancestor_ids={1})
    validate_parent_hierarchy(rule_id=3, parent_rule_id=None, ancestor_ids=set())


def test_validate_rule_origin():
    """Check origin validations."""
    validate_rule_origin("manual")
    validate_rule_origin("ai_generated")
    validate_rule_origin("flow_refinement")

    with pytest.raises(ValueError, match="Invalid rule origin"):
        validate_rule_origin("unknown_origin")


def test_validate_rule_confirmation_status():
    """Check confirmation status validations."""
    validate_rule_confirmation_status("ai_assumption")
    validate_rule_confirmation_status("needs_confirmation")
    validate_rule_confirmation_status("confirmed")

    with pytest.raises(ValueError, match="Invalid confirmation status"):
        validate_rule_confirmation_status("invalid_status")


def test_validate_rule_link_target():
    """Check target kind and UUID validation."""
    for kind in ALLOWED_RULE_LINK_TARGET_KINDS:
        validate_rule_link_target(kind, "00000000-0000-0000-0000-000000000001")

    with pytest.raises(ValueError, match="Unsupported target kind"):
        validate_rule_link_target("unsupported_kind", "00000000-0000-0000-0000-000000000001")

    with pytest.raises(ValueError, match="cannot be empty"):
        validate_rule_link_target("feature", "   ")


def test_validate_rule_link_purpose():
    """Check link purpose validation."""
    validate_rule_link_purpose("source")
    validate_rule_link_purpose("applies_to")

    with pytest.raises(ValueError, match="Invalid link purpose"):
        validate_rule_link_purpose("unsupported_purpose")
