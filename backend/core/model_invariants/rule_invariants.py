"""Pure domain invariants and validation rules for domain rules and links.

This module provides pure domain logic for validating domain rule hierarchy,
origins, confirmation statuses, and link targets without direct database
or framework dependencies.
"""

from __future__ import annotations

CONFIRMATION_STATUS_VALUES = frozenset({
    "needs_confirmation",
    "confirmed",
    "ai_assumption",
})

RULE_ORIGIN_VALUES = frozenset({
    "manual",
    "ai_generated",
    "flow_refinement",
})

RULE_LINK_PURPOSE_VALUES = frozenset({
    "source",
    "applies_to",
})

ALLOWED_RULE_LINK_TARGET_KINDS = frozenset({
    "feature",
    "scenario",
    "acceptance_criterion",
    "flow",
    "flow_step",
    "flow_transition",
    "knowledge",
})


def validate_rule_text(title: str, statement: str) -> None:
    """Validate that title and statement are non-empty and within length limits."""
    stripped_title = title.strip() if title else ""
    stripped_statement = statement.strip() if statement else ""

    if not stripped_title:
        raise ValueError("Domain rule title cannot be empty.")
    if len(stripped_title) > 255:
        raise ValueError("Domain rule title cannot exceed 255 characters.")
    if not stripped_statement:
        raise ValueError("Domain rule statement cannot be empty.")


def validate_parent_hierarchy(
    rule_id: int | str | None,
    parent_rule_id: int | str | None,
    ancestor_ids: set[int | str],
) -> None:
    """Ensure parent assignment does not create self-reference or cycles."""
    if parent_rule_id is None:
        return
    if rule_id is not None and str(rule_id) == str(parent_rule_id):
        raise ValueError("Domain rule cannot be its own parent.")
    if rule_id is not None and (rule_id in ancestor_ids or str(rule_id) in {str(a) for a in ancestor_ids}):
        raise ValueError("Cyclic parent hierarchy detected for domain rule.")


def validate_rule_parent_graph(
    parent_by_rule: dict[str, str | None],
) -> None:
    """Ensure every parent exists and the complete rule hierarchy is acyclic."""
    for rule_uuid, parent_uuid in parent_by_rule.items():
        if parent_uuid is not None and parent_uuid not in parent_by_rule:
            raise ValueError(
                f"Domain rule '{rule_uuid}' refers to missing parent '{parent_uuid}'."
            )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(rule_uuid: str) -> None:
        if rule_uuid in visiting:
            raise ValueError("Cyclic parent hierarchy detected for domain rule.")
        if rule_uuid in visited:
            return
        visiting.add(rule_uuid)
        parent_uuid = parent_by_rule[rule_uuid]
        if parent_uuid is not None:
            visit(parent_uuid)
        visiting.remove(rule_uuid)
        visited.add(rule_uuid)

    for rule_uuid in parent_by_rule:
        visit(rule_uuid)


def validate_rule_origin(origin: str) -> None:
    """Validate that the rule origin belongs to supported values."""
    if origin not in RULE_ORIGIN_VALUES:
        raise ValueError(f"Invalid rule origin '{origin}'. Allowed: {sorted(RULE_ORIGIN_VALUES)}")


def validate_rule_confirmation_status(status: str) -> None:
    """Validate that the confirmation status is recognized."""
    if status not in CONFIRMATION_STATUS_VALUES:
        raise ValueError(
            f"Invalid confirmation status '{status}'. Allowed: {sorted(CONFIRMATION_STATUS_VALUES)}"
        )


def validate_rule_link_target(target_kind: str, target_logical_uuid: str) -> None:
    """Validate link target kind and logical UUID."""
    if target_kind not in ALLOWED_RULE_LINK_TARGET_KINDS:
        raise ValueError(
            f"Unsupported target kind '{target_kind}'. Allowed: {sorted(ALLOWED_RULE_LINK_TARGET_KINDS)}"
        )
    if not target_logical_uuid or not target_logical_uuid.strip():
        raise ValueError("Target logical UUID cannot be empty.")


def validate_rule_link_purpose(link_purpose: str) -> None:
    """Validate link purpose."""
    if link_purpose not in RULE_LINK_PURPOSE_VALUES:
        raise ValueError(
            f"Invalid link purpose '{link_purpose}'. Allowed: {sorted(RULE_LINK_PURPOSE_VALUES)}"
        )

