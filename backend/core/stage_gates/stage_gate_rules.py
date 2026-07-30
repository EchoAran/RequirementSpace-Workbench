from backend.core.stage_gates.stage_gate_context import (
    HowGateContext,
    WhatGateContext,
)
from backend.schemas import IssueSeverity


def _has_blocking_issue(issues: list) -> bool:
    return any(
        issue.severity == IssueSeverity.BLOCKING
        for issue in issues
    )


def evaluate_what_gate(
    context: WhatGateContext,
    issues: list,
) -> bool:
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
    issues: list,
) -> bool:
    flows_have_steps = all(
        flow_id in how_context.flows_with_steps
        for flow_id in how_context.flow_ids
    )
    actor_refs_are_valid = all(
        actor_id in what_context.actor_ids
        for step in how_context.steps
        for actor_id in how_context.step_actor_map.get(step.id, [])
    )
    object_refs_are_valid = all(
        object_id in how_context.business_object_ids
        for step in how_context.steps
        for object_id in (
            how_context.step_input_bo_map.get(step.id, [])
            + how_context.step_output_bo_map.get(step.id, [])
        )
    )
    objects_have_attributes = (
        not how_context.business_object_ids
        or how_context.object_attribute_count > 0
    )
    return bool(
        what_passed
        and how_context.flow_ids
        and flows_have_steps
        and actor_refs_are_valid
        and object_refs_are_valid
        and objects_have_attributes
        and not _has_blocking_issue(issues)
    )


def evaluate_scope_gate(
    what_passed: bool,
    how_passed: bool,
    leaf_feature_ids: list[int],
    scoped_feature_ids: set[int],
    kano_status: str,
    issues: list,
) -> bool:
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
