"""
Tests for edit field permissions — EDITABLE_FIELDS configuration and diff validation.

Pure logic tests that don't require database access.
"""

import pytest
from backend.api.modules.ai_interaction.public import EDITABLE_FIELDS
from backend.api.modules.ai_interaction.ai_add.application.session import AIAddSessionService


# ---------------------------------------------------------------------------
# EDITABLE_FIELDS structure
# ---------------------------------------------------------------------------

def test_editable_fields_actor():
    """Actor has expected editable fields."""
    assert "name" in EDITABLE_FIELDS["actor"]
    assert "description" in EDITABLE_FIELDS["actor"]


def test_editable_fields_feature():
    """Feature has expected editable fields."""
    assert "name" in EDITABLE_FIELDS["feature"]
    assert "description" in EDITABLE_FIELDS["feature"]
    assert "actor_ids" in EDITABLE_FIELDS["feature"]


def test_editable_fields_flow():
    """Flow has expected editable fields."""
    assert "name" in EDITABLE_FIELDS["flow"]
    assert "description" in EDITABLE_FIELDS["flow"]
    assert "feature_ids" in EDITABLE_FIELDS["flow"]


def test_editable_fields_business_object():
    """Business object has expected editable fields."""
    assert "name" in EDITABLE_FIELDS["business_object"]
    assert "description" in EDITABLE_FIELDS["business_object"]


# ---------------------------------------------------------------------------
# Non-editable fields
# ---------------------------------------------------------------------------

def test_actor_id_not_editable():
    """Actor 'id' is not in editable fields."""
    assert "id" not in EDITABLE_FIELDS["actor"]


def test_feature_parent_id_not_editable():
    """Feature 'parent_id' is not in editable fields (topology constraint)."""
    assert "parent_id" not in EDITABLE_FIELDS["feature"]


def test_feature_feature_kind_not_editable():
    """Feature 'feature_kind' is not in editable fields (tree structure)."""
    assert "feature_kind" not in EDITABLE_FIELDS["feature"]


def test_flow_id_not_editable():
    """Flow 'id' is not in editable fields."""
    assert "id" not in EDITABLE_FIELDS["flow"]


def test_business_object_id_not_editable():
    """Business object 'id' is not in editable fields."""
    assert "id" not in EDITABLE_FIELDS["business_object"]


# ---------------------------------------------------------------------------
# _validate_edit_diff logic
# ---------------------------------------------------------------------------

def test_validate_edit_diff_accepts_valid_diff():
    """Valid diff within editable fields passes validation."""
    diff = {"name": {"old": "A", "new": "B"}}
    # Should not raise
    AIAddSessionService._validate_edit_diff("actor", diff)


def test_validate_edit_diff_rejects_non_editable_field():
    """Diff with non-editable field raises ValueError."""
    diff = {"parent_id": {"old": 1, "new": 2}}
    with pytest.raises(ValueError, match="field_not_editable"):
        AIAddSessionService._validate_edit_diff("feature", diff)


def test_validate_edit_diff_rejects_empty_diff():
    """Empty diff raises ValueError."""
    with pytest.raises(ValueError, match="edit_diff_empty"):
        AIAddSessionService._validate_edit_diff("actor", {})


def test_validate_edit_diff_missing_old_value():
    """Diff entry missing 'old' key raises ValueError."""
    diff = {"name": {"new": "B"}}
    with pytest.raises(ValueError, match="edit_diff_validation_failed"):
        AIAddSessionService._validate_edit_diff("actor", diff)


def test_validate_edit_diff_missing_new_value():
    """Diff entry missing 'new' key raises ValueError."""
    diff = {"name": {"old": "A"}}
    with pytest.raises(ValueError, match="edit_diff_validation_failed"):
        AIAddSessionService._validate_edit_diff("actor", diff)


def test_validate_edit_diff_actor_editable_fields():
    """Actor can edit name and description."""
    diff = {"name": {"old": "旧名", "new": "新名"}, "description": {"old": "", "new": "新描述"}}
    AIAddSessionService._validate_edit_diff("actor", diff)  # should not raise


def test_validate_edit_diff_feature_actor_ids():
    """Feature actor_ids is editable."""
    diff = {"actor_ids": {"old": [1, 2], "new": [1]}}
    AIAddSessionService._validate_edit_diff("feature", diff)  # should not raise


def test_validate_edit_diff_feature_kind_rejected():
    """Feature feature_kind is rejected."""
    diff = {"feature_kind": {"old": "leaf", "new": "branch"}}
    with pytest.raises(ValueError, match="field_not_editable"):
        AIAddSessionService._validate_edit_diff("feature", diff)
