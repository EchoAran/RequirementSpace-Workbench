"""Domain model invariants and validation rules for flow transitions.

Delegates to core domain invariants in backend.core.model_invariants.flow_invariants.
"""

from __future__ import annotations

from backend.core.model_invariants.flow_invariants import (
    normalize_semantic_tags,
    validate_default_transition_exclusivity,
    validate_no_duplicate_transition,
    validate_no_self_loop,
    validate_transition_flow_boundary,
    validate_transition_labels,
    validate_transition_position,
)

__all__ = [
    "normalize_semantic_tags",
    "validate_default_transition_exclusivity",
    "validate_no_duplicate_transition",
    "validate_no_self_loop",
    "validate_transition_flow_boundary",
    "validate_transition_labels",
    "validate_transition_position",
]
