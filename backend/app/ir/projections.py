from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def build_projection(ir: dict[str, Any], kind: str) -> dict[str, Any]:
    if kind not in {"goal", "role", "system", "data", "ui"}:
        raise HTTPException(status_code=400, detail=f"projection_kind 不支持：{kind}")

    nodes: dict[str, dict[str, Any]] = ir.get("nodes") or {}
    links: list[dict[str, Any]] = ir.get("links") or []
    slots: dict[str, dict[str, Any]] = ir.get("slots") or {}
    issues: dict[str, dict[str, Any]] = ir.get("issues") or {}
    choice_groups: dict[str, dict[str, Any]] = ir.get("choiceGroups") or {}

    def by_kind(k: str) -> list[dict[str, Any]]:
        return [n for n in nodes.values() if n.get("kind") == k]

    def links_by_type(*types: str) -> list[dict[str, Any]]:
        allowed = set(types)
        return [l for l in links if l.get("type") in allowed]

    def open_issues_for_projection(projection: str) -> list[dict[str, Any]]:
        return [i for i in issues.values() if i.get("status") == "open" and i.get("suggestedProjection") == projection]

    def slots_for_projection(projection: str) -> list[dict[str, Any]]:
        return [s for s in slots.values() if s.get("ownerProjection") == projection]

    def candidate_slots_for_projection(projection: str) -> list[dict[str, Any]]:
        return [s for s in slots_for_projection(projection) if s.get("status") in {"empty", "candidate_ready"}]

    def choice_groups_for_projection(projection: str) -> list[dict[str, Any]]:
        projection_slot_ids = {slot["id"] for slot in slots_for_projection(projection)}
        return [group for group in choice_groups.values() if group.get("slotId") in projection_slot_ids]

    if kind == "goal":
        return {
            "goals": by_kind("goal"),
            "capabilities": by_kind("capability"),
            "tasks": by_kind("task"),
            "actors": by_kind("actor"),
            "links": {
                "realizes": links_by_type("realizes"),
                "supports": links_by_type("supports"),
                "performed_by": links_by_type("performed_by"),
            },
            "openIssues": open_issues_for_projection("goal"),
            "candidateSlots": candidate_slots_for_projection("goal"),
            "choiceGroups": choice_groups_for_projection("goal"),
        }

    if kind == "role":
        return {
            "actors": by_kind("actor"),
            "tasks": by_kind("task"),
            "flowSteps": by_kind("flow_step"),
            "screens": by_kind("screen"),
            "links": {
                "performed_by": links_by_type("performed_by"),
                "accessible_by": links_by_type("accessible_by"),
            },
            "openIssues": open_issues_for_projection("role"),
            "candidateSlots": candidate_slots_for_projection("role"),
        }

    if kind == "system":
        return {
            "flows": by_kind("flow"),
            "steps": by_kind("flow_step"),
            "rules": by_kind("rule"),
            "stateTransitions": by_kind("state_transition"),
            "links": {
                "precedes": links_by_type("precedes"),
                "branches_to": links_by_type("branches_to"),
                "performed_by": links_by_type("performed_by"),
                "guards": links_by_type("guards"),
                "changes_state": links_by_type("changes_state"),
            },
            "openIssues": open_issues_for_projection("system"),
            "candidateSlots": candidate_slots_for_projection("system"),
            "choiceGroups": choice_groups_for_projection("system"),
        }

    if kind == "data":
        return {
            "objects": by_kind("business_object"),
            "fields": by_kind("field"),
            "stateMachines": by_kind("state_machine"),
            "objectStates": by_kind("object_state"),
            "stateTransitions": by_kind("state_transition"),
            "links": {
                "contains": links_by_type("contains"),
                "reads": links_by_type("reads"),
                "writes": links_by_type("writes"),
                "changes_state": links_by_type("changes_state"),
            },
            "openIssues": open_issues_for_projection("data"),
            "candidateSlots": candidate_slots_for_projection("data"),
        }

    return {
        "screens": by_kind("screen"),
        "components": by_kind("ui_component"),
        "fields": by_kind("field"),
        "steps": by_kind("flow_step"),
        "actors": by_kind("actor"),
        "links": {
            "contains": links_by_type("contains"),
            "binds_field": links_by_type("binds_field"),
            "invokes_step": links_by_type("invokes_step"),
            "accessible_by": links_by_type("accessible_by"),
        },
        "openIssues": open_issues_for_projection("ui"),
        "candidateSlots": candidate_slots_for_projection("ui"),
        "choiceGroups": choice_groups_for_projection("ui"),
    }
