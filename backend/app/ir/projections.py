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

    def by_kind(k: str) -> list[dict[str, Any]]:
        return [n for n in nodes.values() if n.get("kind") == k]

    if kind == "goal":
        goals = by_kind("goal")
        capabilities = by_kind("capability")
        tasks = by_kind("task")
        realizes = [l for l in links if l.get("type") == "realizes"]
        supports = [l for l in links if l.get("type") == "supports"]
        return {
            "goals": goals,
            "capabilities": capabilities,
            "tasks": tasks,
            "links": {"realizes": realizes, "supports": supports},
            "openIssues": [i for i in issues.values() if i.get("status") == "open" and i.get("suggestedProjection") == "goal"],
            "candidateSlots": [s for s in slots.values() if s.get("ownerProjection") == "goal" and s.get("status") in {"empty", "candidate_ready"}],
        }

    if kind == "role":
        actors = by_kind("actor")
        performed = [l for l in links if l.get("type") == "performed_by"]
        access = [l for l in links if l.get("type") in {"accessible_by", "reads"}]
        return {
            "actors": actors,
            "links": {"performed_by": performed, "accessible_by": access},
            "openIssues": [i for i in issues.values() if i.get("status") == "open" and i.get("suggestedProjection") == "role"],
        }

    if kind == "system":
        flows = by_kind("flow")
        steps = by_kind("flow_step")
        precedes = [l for l in links if l.get("type") == "precedes"]
        branches = [l for l in links if l.get("type") == "branches_to"]
        performed = [l for l in links if l.get("type") == "performed_by"]
        return {
            "flows": flows,
            "steps": steps,
            "links": {"precedes": precedes, "branches_to": branches, "performed_by": performed},
            "openIssues": [i for i in issues.values() if i.get("status") == "open" and i.get("suggestedProjection") == "system"],
            "candidateSlots": [s for s in slots.values() if s.get("ownerProjection") == "system" and s.get("status") in {"empty", "candidate_ready"}],
        }

    if kind == "data":
        objects = by_kind("business_object")
        fields = by_kind("field")
        contains = [l for l in links if l.get("type") == "contains"]
        owns = [l for l in links if l.get("type") == "owns"]
        return {
            "objects": objects,
            "fields": fields,
            "links": {"contains": contains, "owns": owns},
            "openIssues": [i for i in issues.values() if i.get("status") == "open" and i.get("suggestedProjection") == "data"],
        }

    screens = by_kind("screen")
    components = by_kind("ui_component")
    contains = [l for l in links if l.get("type") in {"contains", "displayed_on"}]
    invokes = [l for l in links if l.get("type") in {"invokes_step", "triggered_by"}]
    access = [l for l in links if l.get("type") in {"accessible_by", "reads"}]
    return {
        "screens": screens,
        "components": components,
        "links": {"contains": contains, "invokes_step": invokes, "accessible_by": access},
        "openIssues": [i for i in issues.values() if i.get("status") == "open" and i.get("suggestedProjection") == "ui"],
    }

