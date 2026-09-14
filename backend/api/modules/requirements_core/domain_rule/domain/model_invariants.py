"""Pure domain invariants and validation rules for domain rules and links.

Delegates to core domain invariants in backend.core.model_invariants.rule_invariants.
"""

from backend.core.model_invariants.rule_invariants import (
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
    "validate_parent_hierarchy",
    "validate_rule_confirmation_status",
    "validate_rule_link_purpose",
    "validate_rule_link_target",
    "validate_rule_origin",
    "validate_rule_text",
]
