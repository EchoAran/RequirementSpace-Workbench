"""Domain model invariants and validation rules for flow transitions.

This module provides pure domain logic for validating transition structure,
boundary constraints, tags normalization, and semantic integrity without
direct database or framework dependencies.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def normalize_semantic_tags(tags: Sequence[str] | None) -> list[str]:
    """Normalize, deduplicate, and sort semantic tags for a flow transition.

    Args:
        tags: Raw sequence of tag strings.

    Returns:
        Deduplicated, stripped, and alphabetically sorted list of non-empty tags.
    """
    if not tags:
        return []
    cleaned_tags = {tag.strip() for tag in tags if tag and tag.strip()}
    return sorted(cleaned_tags)


def validate_transition_flow_boundary(
    source_flow_id: int,
    target_flow_id: int,
    expected_flow_id: int,
    source_project_id: int | None = None,
    target_project_id: int | None = None,
    expected_project_id: int | None = None,
    source_workspace_id: int | None = None,
    target_workspace_id: int | None = None,
    expected_workspace_id: int | None = None,
) -> None:
    """Ensure source and target steps belong to the target flow, project, and workspace boundaries.

    Args:
        source_flow_id: Flow ID containing the source step.
        target_flow_id: Flow ID containing the target step.
        expected_flow_id: Required flow ID for the transition.
        source_project_id: Project ID of the source step (optional).
        target_project_id: Project ID of the target step (optional).
        expected_project_id: Required project ID for the transition (optional).
        source_workspace_id: Workspace ID of the source step (optional).
        target_workspace_id: Workspace ID of the target step (optional).
        expected_workspace_id: Required workspace ID for the transition (optional).

    Raises:
        ValueError: If any step belongs to a different flow, project, or workspace.
    """
    if source_flow_id != expected_flow_id:
        raise ValueError(
            f"Source step flow ({source_flow_id}) does not match transition flow ({expected_flow_id})"
        )
    if target_flow_id != expected_flow_id:
        raise ValueError(
            f"Target step flow ({target_flow_id}) does not match transition flow ({expected_flow_id})"
        )
    if (
        expected_project_id is not None
        and source_project_id is not None
        and source_project_id != expected_project_id
    ):
        raise ValueError(
            f"Source step project ({source_project_id}) does not match transition project ({expected_project_id})"
        )
    if (
        expected_project_id is not None
        and target_project_id is not None
        and target_project_id != expected_project_id
    ):
        raise ValueError(
            f"Target step project ({target_project_id}) does not match transition project ({expected_project_id})"
        )
    if (
        expected_workspace_id is not None
        and source_workspace_id != expected_workspace_id
    ):
        raise ValueError(
            f"Source step workspace ({source_workspace_id}) does not match transition workspace ({expected_workspace_id})"
        )
    if (
        expected_workspace_id is not None
        and target_workspace_id != expected_workspace_id
    ):
        raise ValueError(
            f"Target step workspace ({target_workspace_id}) does not match transition workspace ({expected_workspace_id})"
        )


def validate_no_self_loop(source_step_id: int | str, target_step_id: int | str) -> None:
    """Validate that transition does not form a direct self-loop on the same step.

    Args:
        source_step_id: ID or reference of the source step.
        target_step_id: ID or reference of the target step.

    Raises:
        ValueError: If source_step_id equals target_step_id.
    """
    if str(source_step_id) == str(target_step_id):
        raise ValueError(f"Self-loop transitions connecting a step to itself are not permitted: '{source_step_id}'")


def validate_no_duplicate_transition(
    existing_transitions: Sequence[Any],
    source_step_id: int | str,
    target_step_id: int | str,
    current_transition_id: int | None = None,
) -> None:
    """Validate that no duplicate directed transition exists between source and target steps.

    Args:
        existing_transitions: Sequence of existing transition objects or dicts.
        source_step_id: Source step identifier.
        target_step_id: Target step identifier.
        current_transition_id: Optional ID of current transition being edited.

    Raises:
        ValueError: If a duplicate transition with identical source and target exists.
    """
    for trans in existing_transitions:
        tid = getattr(trans, "id", None) if not isinstance(trans, dict) else trans.get("id")
        if current_transition_id is not None and tid == current_transition_id:
            continue
        s_id = getattr(trans, "source_step_id", None) if not isinstance(trans, dict) else trans.get("source_step_id", trans.get("source_step_ref"))
        t_id = getattr(trans, "target_step_id", None) if not isinstance(trans, dict) else trans.get("target_step_id", trans.get("target_step_ref"))
        if str(s_id) == str(source_step_id) and str(t_id) == str(target_step_id):
            raise ValueError(
                f"Duplicate transition from step {source_step_id} to step {target_step_id} already exists."
            )


def validate_transition_position(position: int) -> None:
    """Validate transition position ordering attribute.

    Args:
        position: Non-negative integer index for outgoing ordering.

    Raises:
        ValueError: If position is negative.
    """
    if position < 0:
        raise ValueError("Transition position must be a non-negative integer")


def validate_transition_labels(label: str | None, condition_text: str | None) -> tuple[str, str]:
    """Clean and validate label and condition text values.

    Args:
        label: Raw transition label.
        condition_text: Raw transition condition text.

    Returns:
        Tuple of stripped (label, condition_text).
    """
    cleaned_label = (label or "").strip()
    cleaned_condition = (condition_text or "").strip()
    return cleaned_label, cleaned_condition


def validate_default_transition_exclusivity(
    is_default: bool,
    existing_default_transition_id: int | str | None,
    current_transition_id: int | str | None = None,
) -> None:
    """Validate that at most one default transition exists per source step.

    Args:
        is_default: Whether the transition is marked as default.
        existing_default_transition_id: Identifier of existing default transition for the source step, if any.
        current_transition_id: Identifier of the transition being updated, if applicable.

    Raises:
        ValueError: If another transition is already set as default.
    """
    if is_default and existing_default_transition_id is not None:
        if current_transition_id is None or str(existing_default_transition_id) != str(current_transition_id):
            raise ValueError(
                f"Source step already has default transition ({existing_default_transition_id})"
            )
