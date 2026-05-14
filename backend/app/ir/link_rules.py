from __future__ import annotations

from typing import Final


LINK_RULES: Final[dict[str, list[tuple[str, str]]]] = {
    "realizes": [
        ("capability", "goal"),
        ("task", "capability"),
        ("flow", "task"),
    ],
    "supports": [
        ("task", "capability"),
        ("flow_step", "task"),
    ],
    "performed_by": [
        ("task", "actor"),
        ("flow_step", "actor"),
    ],
    "owns": [
        ("actor", "business_object"),
    ],
    "precedes": [
        ("flow_step", "flow_step"),
    ],
    "branches_to": [
        ("flow_step", "flow_step"),
    ],
    "guards": [
        ("rule", "flow_step"),
        ("rule", "state_transition"),
    ],
    "reads": [
        ("flow_step", "business_object"),
        ("screen", "business_object"),
        ("screen", "actor"),
    ],
    "writes": [
        ("flow_step", "business_object"),
        ("screen", "business_object"),
    ],
    "changes_state": [
        ("flow_step", "business_object"),
        ("state_transition", "object_state"),
    ],
    "depends_on": [
        ("capability", "capability"),
        ("task", "task"),
        ("task", "capability"),
        ("flow_step", "flow_step"),
        ("ui_component", "flow_step"),
    ],
    "contains": [
        ("goal", "capability"),
        ("capability", "capability"),
        ("business_object", "field"),
        ("business_object", "state_machine"),
        ("state_machine", "object_state"),
        ("state_machine", "state_transition"),
        ("screen", "ui_component"),
        ("ui_component", "ui_component"),
    ],
    "accessible_by": [
        ("screen", "actor"),
    ],
    "binds_field": [
        ("ui_component", "field"),
    ],
    "invokes_step": [
        ("ui_component", "flow_step"),
    ],
    "displayed_on": [
        ("ui_component", "screen"),
    ],
    "triggered_by": [
        ("ui_component", "flow_step"),
    ],
}


def is_link_allowed(link_type: str, source_kind: str, target_kind: str) -> bool:
    allowed = LINK_RULES.get(link_type) or []
    return (source_kind, target_kind) in allowed
