"""Derived path-projection comparison for version-control states."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from backend.core.path_projection import project_flow_paths


def _project_flow(flow: dict[str, Any]) -> list[dict[str, Any]]:
    ordered_steps = sorted(
        flow.get("steps", []),
        key=lambda step: (step.get("position", 0), step.get("logical_uuid", "")),
    )
    step_ids = {
        step["logical_uuid"]: index
        for index, step in enumerate(ordered_steps, start=1)
    }
    steps = [
        SimpleNamespace(
            id=step_ids[step["logical_uuid"]],
            logical_uuid=step["logical_uuid"],
            position=step.get("position", 0),
            name=step.get("name", ""),
        )
        for step in ordered_steps
    ]
    transitions = []
    for index, transition in enumerate(flow.get("transitions", []), start=1):
        source_uuid = transition.get("source_step_logical_uuid")
        target_uuid = transition.get("target_step_logical_uuid")
        if source_uuid not in step_ids or target_uuid not in step_ids:
            raise ValueError(
                f"path_projection_references_missing_step: {transition.get('logical_uuid', '')}"
            )
        transitions.append(
            SimpleNamespace(
                id=index,
                logical_uuid=transition["logical_uuid"],
                source_step_id=step_ids[source_uuid],
                target_step_id=step_ids[target_uuid],
                label=transition.get("label", ""),
                condition_text=transition.get("condition_text", ""),
                is_default=bool(transition.get("is_default", False)),
                position=transition.get("position", 0),
            )
        )
    summary = project_flow_paths(1, steps, transitions)
    return [
        {
            "is_main": path.is_main,
            "status": path.status,
            "step_logical_uuids": path.step_logical_uuids,
            "transition_logical_uuids": path.transition_logical_uuids,
        }
        for path in summary.paths
    ]


def diff_path_projections(
    base_state: dict[str, Any],
    target_state: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return derived path changes for flows present in both states."""
    base_flows = {flow["logical_uuid"]: flow for flow in base_state.get("flows", [])}
    target_flows = {flow["logical_uuid"]: flow for flow in target_state.get("flows", [])}
    entries: list[dict[str, Any]] = []
    for flow_uuid in sorted(set(base_flows) & set(target_flows)):
        before = _project_flow(base_flows[flow_uuid])
        after = _project_flow(target_flows[flow_uuid])
        if before == after:
            continue
        entries.append(
            {
                "change_type": "entity_updated",
                "entity_type": "path_projection",
                "entity_uuid": flow_uuid,
                "entity_name": target_flows[flow_uuid].get("name", ""),
                "parent_uuid": flow_uuid,
                "parent_type": "flow",
                "path": "path_projection",
                "field": "paths",
                "before": before,
                "after": after,
            }
        )
    return entries
