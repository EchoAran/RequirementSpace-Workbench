from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models


def compute_impact_preview(db: Session, ws: models.Workspace, patch: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(patch, dict):
        raise HTTPException(status_code=400, detail="patch 必须是对象")

    touched: set[str] = set()
    for n in (patch.get("addNodes") or []):
        if isinstance(n, dict) and isinstance(n.get("id"), str):
            touched.add(n["id"])
    for n in (patch.get("updateNodes") or []):
        if isinstance(n, dict) and isinstance(n.get("id"), str):
            touched.add(n["id"])
    for nid in (patch.get("removeNodeIds") or []):
        if isinstance(nid, str):
            touched.add(nid)
    for l in (patch.get("addLinks") or []):
        if isinstance(l, dict):
            if isinstance(l.get("sourceId"), str):
                touched.add(l["sourceId"])
            if isinstance(l.get("targetId"), str):
                touched.add(l["targetId"])

    node_rows = (
        db.query(models.Node.id, models.Node.kind)
        .filter(models.Node.workspace_id == ws.id)
        .all()
    )
    kind_by_id = {r[0]: r[1] for r in node_rows}
    for n in (patch.get("addNodes") or []):
        if isinstance(n, dict) and isinstance(n.get("id"), str) and isinstance(n.get("kind"), str):
            kind_by_id[n["id"]] = n["kind"]

    affected_goals = sorted([nid for nid in touched if kind_by_id.get(nid) == "goal"])
    affected_actors = sorted([nid for nid in touched if kind_by_id.get(nid) == "actor"])
    affected_flows = sorted([nid for nid in touched if kind_by_id.get(nid) in {"flow", "flow_step"}])
    affected_objects = sorted([nid for nid in touched if kind_by_id.get(nid) == "business_object"])
    affected_screens = sorted([nid for nid in touched if kind_by_id.get(nid) == "screen"])

    new_issues = []
    for i in (patch.get("addIssues") or patch.get("createIssues") or []):
        if isinstance(i, dict) and isinstance(i.get("id"), str):
            new_issues.append(i["id"])

    resolved_issues = patch.get("resolveIssueIds") or []

    return {
        "affectedGoals": affected_goals,
        "affectedActors": affected_actors,
        "affectedFlows": affected_flows,
        "affectedObjects": affected_objects,
        "affectedScreens": affected_screens,
        "newIssues": new_issues or None,
        "resolvedIssues": resolved_issues or None,
    }

