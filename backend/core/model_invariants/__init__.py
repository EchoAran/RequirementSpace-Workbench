"""Domain model invariants shared across persistence services and shadow validation."""

from .flow_invariants import (
    normalize_semantic_tags,
    validate_default_transition_exclusivity,
    validate_no_duplicate_transition,
    validate_no_self_loop,
    validate_transition_flow_boundary,
    validate_transition_labels,
    validate_transition_position,
)
from .rule_invariants import (
    ALLOWED_RULE_LINK_TARGET_KINDS,
    CONFIRMATION_STATUS_VALUES,
    RULE_LINK_PURPOSE_VALUES,
    RULE_ORIGIN_VALUES,
    validate_parent_hierarchy,
    validate_rule_confirmation_status,
    validate_rule_link_purpose,
    validate_rule_link_target,
    validate_rule_origin,
    validate_rule_text,
)

__all__ = [
    "ALLOWED_RULE_LINK_TARGET_KINDS",
    "CONFIRMATION_STATUS_VALUES",
    "RULE_LINK_PURPOSE_VALUES",
    "RULE_ORIGIN_VALUES",
    "normalize_semantic_tags",
    "validate_default_transition_exclusivity",
    "validate_no_duplicate_transition",
    "validate_no_self_loop",
    "validate_parent_hierarchy",
    "validate_rule_confirmation_status",
    "validate_rule_link_purpose",
    "validate_rule_link_target",
    "validate_rule_origin",
    "validate_rule_text",
    "validate_transition_flow_boundary",
    "validate_transition_labels",
    "validate_transition_position",
]
