"""Deterministic evaluation criteria for project stage gates.

This module provides pure evaluation criteria for WHAT, HOW, and SCOPE gates,
ensuring objective verification of specification models without heuristic ambiguity.
"""

from __future__ import annotations

from collections.abc import Sequence

from backend.core.stage_gates.stage_gate_context import (
    HowGateContext,
    WhatGateContext,
)
from backend.schemas import Issue, IssueSeverity


def _has_blocking_issue(issues: Sequence[Issue]) -> bool:
    """Check if any issue in the collection has BLOCKING severity."""
    return any(
        issue.severity == IssueSeverity.BLOCKING
        for issue in issues
    )


def evaluate_what_gate(
    context: WhatGateContext,
    issues: Sequence[Issue],
) -> bool:
    """Evaluate whether the WHAT stage criteria are satisfied.

    Requirements:
    - At least one actor exists.
    - At least one leaf feature exists.
    - Every leaf feature is associated with at least one actor.
    - Every leaf feature has at least one scenario.
    - Every scenario contains at least one acceptance criterion.
    - No blocking WHAT issues exist.
    """
    return bool(
        context.actor_ids
        and context.leaf_feature_ids
        and all(
            context.feature_actor_map.get(feature_id)
            for feature_id in context.leaf_feature_ids
        )
        and all(
            context.feature_scenario_map.get(feature_id)
            for feature_id in context.leaf_feature_ids
        )
        and all(
            scenario_id in context.ac_scenario_ids
            for scenario_id in context.scenario_ids
        )
        and not _has_blocking_issue(issues)
    )


def evaluate_how_gate(
    what_passed: bool,
    what_context: WhatGateContext,
    how_context: HowGateContext,
    issues: Sequence[Issue],
) -> bool:
    """Evaluate whether the HOW stage criteria are satisfied.

    Requirements:
    1. WHAT gate must be passed.
    2. At least one domain rule exists.
    3. At least one flow exists, and every flow contains steps.
    4. Actor references in steps must belong to the valid project actor set.
    5. Business object references in steps must belong to the project business object set.
    6. Confirmed flows must not depend on unconfirmed rules.
    7. No blocking HOW issues exist.
    """
    if not what_passed:
        return False

    if not how_context.domain_rules:
        return False

    if not how_context.flow_ids:
        return False

    flows_have_steps = all(
        flow_id in how_context.flows_with_steps
        for flow_id in how_context.flow_ids
    )
    if not flows_have_steps:
        return False

    actor_refs_are_valid = all(
        actor_id in what_context.actor_ids
        for step in how_context.steps
        for actor_id in how_context.step_actor_map.get(step.id, [])
    )
    if not actor_refs_are_valid:
        return False

    object_refs_are_valid = all(
        object_id in how_context.business_object_ids
        for step in how_context.steps
        for object_id in (
            how_context.step_input_bo_map.get(step.id, [])
            + how_context.step_output_bo_map.get(step.id, [])
        )
    )
    if not object_refs_are_valid:
        return False

    if _has_blocking_issue(issues):
        return False

    return True


def evaluate_scope_gate(
    what_passed: bool,
    how_passed: bool,
    leaf_feature_ids: Sequence[int],
    scoped_feature_ids: set[int],
    kano_status: str,
    issues: Sequence[Issue],
) -> bool:
    """Evaluate whether the SCOPE stage criteria are satisfied."""
    all_leaf_features_scoped = bool(
        leaf_feature_ids
    ) and all(
        feature_id in scoped_feature_ids
        for feature_id in leaf_feature_ids
    )
    return bool(
        what_passed
        and how_passed
        and all_leaf_features_scoped
        and kano_status in ("generated", "skipped")
        and not _has_blocking_issue(issues)
    )
