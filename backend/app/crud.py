from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models
from .ir.audit import append_operation
from .ir.validators import validate_ir
from .ir.graph_patch import GraphPatchService
from .ir.diagnostics import run_deterministic_diagnosis


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

def _normalize_scope_status(value: Any) -> Any:
    if value == "dependency":
        return "external_dependency"
    if value == "excluded":
        return None
    return value


def _require_field(payload: dict[str, Any], field: str, kind: str, item_id: str) -> Any:
    value = payload.get(field)
    if value in (None, ""):
        raise HTTPException(status_code=500, detail=f"{kind} `{item_id}` 缺少必要字段 `{field}`")
    return value


def _validate_related_node_ids(db: Session, workspace_id: str, related_node_ids: Any) -> list[str]:
    if related_node_ids is None:
        return []
    if not isinstance(related_node_ids, list):
        raise HTTPException(status_code=400, detail="relatedNodeIds 必须是 string[]")
    cleaned = [node_id for node_id in related_node_ids if isinstance(node_id, str) and node_id]
    if len(cleaned) != len(related_node_ids):
        raise HTTPException(status_code=400, detail="relatedNodeIds 必须是非空 string[]")
    if not cleaned:
        return []
    existing = {
        r[0]
        for r in db.query(models.Node.id)
        .filter(models.Node.workspace_id == workspace_id, models.Node.id.in_(cleaned))
        .all()
    }
    missing = sorted(set(cleaned) - existing)
    if missing:
        raise HTTPException(status_code=400, detail=f"relatedNodeIds 中存在无效节点：{missing[:5]}")
    return cleaned


def _page_projection_hints(page: str | None) -> set[str]:
    if page == "/what":
        return {"goal", "role"}
    if page == "/flow":
        return {"system"}
    if page == "/scope":
        return {"data", "system"}
    if page == "/preview":
        return {"ui", "system"}
    return set()


def _page_node_ids(ws: models.Workspace, page: str | None) -> set[str]:
    nodes = list(ws.nodes or [])
    if page == "/what":
        kinds = {"goal", "capability", "task", "actor"}
        return {n.id for n in nodes if n.kind in kinds}
    if page == "/flow":
        kinds = {"flow", "flow_step", "rule", "state_transition"}
        return {n.id for n in nodes if n.kind in kinds}
    if page == "/scope":
        return {n.id for n in nodes if n.scope_status or n.status == "excluded"}
    if page == "/preview":
        kinds = {"screen", "ui_component", "flow_step", "actor"}
        return {n.id for n in nodes if n.kind in kinds}
    return set()


def _diagnostic_matches_scope(
    ws: models.Workspace,
    diagnostic: Any,
    scope: dict[str, Any] | None,
) -> bool:
    scope = scope or {}
    target_id = scope.get("targetId") if isinstance(scope.get("targetId"), str) else None
    page = scope.get("page") if isinstance(scope.get("page"), str) else None
    trigger = scope.get("trigger") if isinstance(scope.get("trigger"), str) else None

    related_ids = set(diagnostic.related_node_ids or [])
    page_ids = _page_node_ids(ws, page)
    projection_hints = _page_projection_hints(page)

    if trigger == "scope_recommendation":
        scoped_ids = _page_node_ids(ws, "/scope")
        return diagnostic.category == "scope_risk" or bool(related_ids & scoped_ids)

    if target_id:
        if target_id in related_ids:
            return True
        return False

    if page:
        if not page_ids and not projection_hints:
            return True
        if related_ids and related_ids & page_ids:
            return True
        if projection_hints and diagnostic.suggested_projection in projection_hints:
            return True
        return False

    if trigger == "next_step":
        return diagnostic.severity == "high" or diagnostic.category in {"missing", "flow_gap", "scope_risk"}

    return True


def upsert_workspace_from_ir(db: Session, ir: dict[str, Any]) -> models.Workspace:
    workspace_id = ir["id"]
    existing = db.get(models.Workspace, workspace_id)
    if existing:
        db.delete(existing)
        db.flush()

    ws = models.Workspace(
        id=workspace_id,
        name=ir.get("name", "未命名项目"),
        idea=ir.get("idea", ""),
        domain=ir.get("meta", ir.get("domain", {})),
        projections=ir.get("projections", {}),
        proposals=ir.get("proposals", {}),
        audit=ir.get("audit", {}),
    )
    db.add(ws)

    for node_id, node in (ir.get("nodes") or {}).items():
        base_keys = {
            "id",
            "kind",
            "title",
            "description",
            "status",
            "confidence",
            "scopeStatus",
            "source",
            "slots",
        }
        extra = {k: v for k, v in node.items() if k not in base_keys}
        scope_status = _normalize_scope_status(node.get("scopeStatus"))
        status = node.get("status", "needs_confirmation")
        if node.get("scopeStatus") == "excluded":
            status = "excluded"
            scope_status = None
        db.add(
            models.Node(
                id=node_id,
                workspace_id=workspace_id,
                kind=node.get("kind", "capability"),
                title=node.get("title", node_id),
                description=node.get("description"),
                status=status,
                confidence=node.get("confidence"),
                scope_status=scope_status,
                source=node.get("source", {"type": "ai"}),
                slots=node.get("slots"),
                extra=extra,
            )
        )

    for link in ir.get("links") or []:
        db.add(
            models.Link(
                id=link["id"],
                workspace_id=workspace_id,
                source_id=link["sourceId"],
                target_id=link["targetId"],
                type=link["type"],
                label=link.get("label"),
                status=link.get("status", "active"),
                source=link.get("source", {"type": "ai"}),
            )
        )

    for slot_id, slot in (ir.get("slots") or {}).items():
        owner_projection = slot.get("ownerProjection")
        if not owner_projection:
            hints = (slot.get("context") or {}).get("projectionHints") or []
            owner_projection = hints[0] if hints else "goal"
        owner_node_id = _require_field(slot, "ownerNodeId", "Slot", slot_id)
        slot_name = _require_field(slot, "name", "Slot", slot_id)
        db.add(
            models.Slot(
                id=slot_id,
                workspace_id=workspace_id,
                owner_node_id=owner_node_id,
                owner_projection=owner_projection,
                name=slot_name,
                description=slot.get("description"),
                expected_kinds=slot.get("expectedKinds", []),
                arity=slot.get("arity", "many"),
                status=slot.get("status", "empty"),
                choice_group_id=slot.get("choiceGroupId"),
                context=slot.get("context", {}),
            )
        )

    for cg_id, cg in (ir.get("choiceGroups") or {}).items():
        group = models.ChoiceGroup(
            id=cg_id,
            workspace_id=workspace_id,
            slot_id=_require_field(cg, "slotId", "ChoiceGroup", cg_id),
            selected_choice_id=cg.get("selectedChoiceId"),
            selection_mode=cg.get("selectionMode", "single"),
            status=cg.get("status", "open"),
        )
        db.add(group)
        for choice in cg.get("choices", []):
            db.add(
                models.Choice(
                    id=_require_field(choice, "id", "Choice", cg_id),
                    workspace_id=workspace_id,
                    choice_group_id=cg_id,
                    title=_require_field(choice, "title", "Choice", choice.get("id", cg_id)),
                    rationale=choice.get("rationale", ""),
                    patch=choice.get("patch", {}) or {},
                    proposed_node_ids=choice.get("proposedNodeIds", []),
                    proposed_link_ids=choice.get("proposedLinkIds", []),
                    impact_preview=choice.get("impactPreview", {}),
                    status=choice.get("status", "candidate"),
                )
            )

    for issue_id, issue in (ir.get("issues") or {}).items():
        db.add(
            models.Issue(
                id=issue_id,
                workspace_id=workspace_id,
                title=_require_field(issue, "title", "Issue", issue_id),
                description=issue.get("description", ""),
                severity=issue.get("severity", "medium"),
                category=issue.get("category", "missing"),
                related_node_ids=issue.get("relatedNodeIds", []),
                suggested_projection=issue.get("suggestedProjection", "goal"),
                suggested_action=issue.get("suggestedAction", ""),
                status=issue.get("status", "open"),
                source=issue.get("source", {"type": "ai"}),
            )
        )

    db.flush()
    return ws


def get_workspace_or_404(db: Session, workspace_id: str) -> models.Workspace:
    ws = db.get(models.Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace `{workspace_id}` 不存在")
    return ws


def serialize_workspace(ws: models.Workspace) -> dict[str, Any]:
    nodes: dict[str, Any] = {}
    for n in ws.nodes:
        status = n.status
        scope_status = _normalize_scope_status(n.scope_status)
        if n.scope_status == "excluded":
            status = "excluded"
            scope_status = None
        payload = {
            "id": n.id,
            "kind": n.kind,
            "title": n.title,
            "description": n.description,
            "status": status,
            "confidence": n.confidence,
            "scopeStatus": scope_status,
            "source": n.source,
            "slots": n.slots,
        }
        payload.update(n.extra or {})
        nodes[n.id] = payload

    links = [
        {
            "id": l.id,
            "sourceId": l.source_id,
            "targetId": l.target_id,
            "type": l.type,
            "label": l.label,
            "status": l.status,
            "source": l.source,
        }
        for l in ws.links
    ]

    slots = {
        s.id: {
            "id": s.id,
            "ownerNodeId": s.owner_node_id,
            "ownerProjection": s.owner_projection
            or ((s.context or {}).get("projectionHints") or ["goal"])[0],
            "name": s.name,
            "description": s.description,
            "expectedKinds": s.expected_kinds,
            "arity": s.arity,
            "status": s.status,
            "choiceGroupId": s.choice_group_id,
            "context": s.context,
        }
        for s in ws.slots
    }

    choice_groups = {}
    for cg in ws.choice_groups:
        choice_groups[cg.id] = {
            "id": cg.id,
            "slotId": cg.slot_id,
            "selectedChoiceId": cg.selected_choice_id,
            "selectionMode": cg.selection_mode,
            "status": cg.status,
            "choices": [
                {
                    "id": c.id,
                    "title": c.title,
                    "rationale": c.rationale,
                    "patch": c.patch or {},
                    "proposedNodeIds": c.proposed_node_ids,
                    "proposedLinkIds": c.proposed_link_ids,
                    "impactPreview": {
                        "affectedGoals": (c.impact_preview or {}).get("affectedGoals") or [],
                        "affectedActors": (c.impact_preview or {}).get("affectedActors") or [],
                        "affectedFlows": (c.impact_preview or {}).get("affectedFlows") or [],
                        "affectedObjects": (c.impact_preview or {}).get("affectedObjects") or [],
                        "affectedScreens": (c.impact_preview or {}).get("affectedScreens") or [],
                        "newIssues": (c.impact_preview or {}).get("newIssues"),
                        "resolvedIssues": (c.impact_preview or {}).get("resolvedIssues"),
                    },
                    "status": c.status,
                }
                for c in cg.choices
            ],
        }

    issues = {
        i.id: {
            "id": i.id,
            "title": i.title,
            "description": i.description,
            "severity": i.severity,
            "category": i.category,
            "relatedNodeIds": i.related_node_ids,
            "suggestedProjection": i.suggested_projection,
            "suggestedAction": i.suggested_action,
            "status": i.status,
            "source": i.source,
        }
        for i in ws.issues
    }

    audit = dict(ws.audit or {})
    audit["updatedAt"] = now_iso()

    meta = dict(ws.domain or {})
    if "assumptions" not in meta:
        meta["assumptions"] = []
    if "inputPrompt" not in meta:
        meta["inputPrompt"] = ws.idea

    payload = {
        "id": ws.id,
        "name": ws.name,
        "idea": ws.idea,
        "meta": meta,
        "nodes": nodes,
        "links": links,
        "slots": slots,
        "choiceGroups": choice_groups,
        "proposals": ws.proposals or {},
        "issues": issues,
        "projections": ws.projections or {},
        "audit": audit,
    }
    validate_ir(payload)
    return payload


def update_node(db: Session, ws: models.Workspace, node_id: str, updates: dict[str, Any]) -> None:
    node = db.get(models.Node, node_id)
    if not node or node.workspace_id != ws.id:
        raise HTTPException(status_code=404, detail=f"Node `{node_id}` 不存在")

    if "title" in updates and updates["title"] is not None:
        node.title = updates["title"]
    if "description" in updates:
        node.description = updates["description"]
    if "status" in updates and updates["status"] is not None:
        node.status = updates["status"]
    if "scopeStatus" in updates and updates["scopeStatus"] is not None:
        if updates["scopeStatus"] == "excluded":
            node.status = "excluded"
            node.scope_status = None
        else:
            node.scope_status = _normalize_scope_status(updates["scopeStatus"])
    if "confidence" in updates:
        node.confidence = updates["confidence"]
    if "source" in updates and updates["source"] is not None:
        node.source = updates["source"]
    if "extra" in updates and updates["extra"] is not None:
        merged = dict(node.extra or {})
        merged.update(updates["extra"])
        node.extra = merged

    node.updated_at = datetime.utcnow()
    _touch_workspace(ws)


def move_scope(db: Session, ws: models.Workspace, node_id: str, scope_status: str) -> None:
    if scope_status == "excluded":
        raise HTTPException(status_code=400, detail="excluded 不属于 scopeStatus，请使用 status=excluded")
    update_node(db, ws, node_id, {"scopeStatus": scope_status})


def update_issue_status(db: Session, ws: models.Workspace, issue_id: str, status: str) -> None:
    issue = db.get(models.Issue, issue_id)
    if not issue or issue.workspace_id != ws.id:
        raise HTTPException(status_code=404, detail=f"Issue `{issue_id}` 不存在")
    issue.status = status
    _touch_workspace(ws)


def update_issue(db: Session, ws: models.Workspace, issue_id: str, updates: dict[str, Any]) -> None:
    issue = db.get(models.Issue, issue_id)
    if not issue or issue.workspace_id != ws.id:
        raise HTTPException(status_code=404, detail=f"Issue `{issue_id}` 不存在")

    if "title" in updates and updates["title"] is not None:
        issue.title = updates["title"]
    if "description" in updates:
        issue.description = updates["description"] or ""
    if "severity" in updates and updates["severity"] is not None:
        issue.severity = updates["severity"]
    if "category" in updates and updates["category"] is not None:
        issue.category = updates["category"]
    if "relatedNodeIds" in updates and updates["relatedNodeIds"] is not None:
        issue.related_node_ids = _validate_related_node_ids(db, ws.id, updates["relatedNodeIds"])
    if "suggestedProjection" in updates and updates["suggestedProjection"] is not None:
        issue.suggested_projection = updates["suggestedProjection"]
    if "suggestedAction" in updates and updates["suggestedAction"] is not None:
        issue.suggested_action = updates["suggestedAction"]
    if "status" in updates and updates["status"] is not None:
        issue.status = updates["status"]
    if "source" in updates and updates["source"] is not None:
        issue.source = updates["source"]

    _touch_workspace(ws)


def update_choice(db: Session, ws: models.Workspace, choice_id: str, updates: dict[str, Any]) -> None:
    choice = (
        db.query(models.Choice)
        .join(models.ChoiceGroup, models.Choice.choice_group_id == models.ChoiceGroup.id)
        .filter(models.Choice.id == choice_id, models.ChoiceGroup.workspace_id == ws.id)
        .one_or_none()
    )
    if not choice:
        raise HTTPException(status_code=404, detail=f"Choice `{choice_id}` 不存在")

    if "title" in updates and updates["title"] is not None:
        choice.title = updates["title"]
    if "rationale" in updates and updates["rationale"] is not None:
        choice.rationale = updates["rationale"]
    if "patch" in updates and updates["patch"] is not None:
        choice.patch = updates["patch"]
    if "status" in updates and updates["status"] is not None:
        choice.status = updates["status"]

    _touch_workspace(ws)


def generate_candidate_for_issue(db: Session, ws: models.Workspace, issue_id: str) -> dict[str, str]:
    issue = db.get(models.Issue, issue_id)
    if not issue or issue.workspace_id != ws.id:
        raise HTTPException(status_code=404, detail=f"Issue `{issue_id}` 不存在")

    owner_node_id = issue.related_node_ids[0] if issue.related_node_ids else next(iter({n.id for n in ws.nodes}), None)
    if not owner_node_id:
        raise HTTPException(status_code=400, detail="当前工作台没有可关联节点")

    slot_id = _new_id("slot")
    choice_group_id = _new_id("cg")
    choice_id = _new_id("cand")

    db.add(
        models.Slot(
            id=slot_id,
            workspace_id=ws.id,
            owner_node_id=owner_node_id,
            owner_projection="system",
            name=f"{issue.title} - 修复方案",
            description=issue.description,
            expected_kinds=["flow_step", "rule", "ui_component"],
            arity="many",
            status="candidate_ready",
            choice_group_id=choice_group_id,
            context={"projectionHints": ["system", "ui"], "relatedNodeIds": issue.related_node_ids},
        )
    )

    db.add(
        models.ChoiceGroup(
            id=choice_group_id,
            workspace_id=ws.id,
            slot_id=slot_id,
            selected_choice_id=None,
            selection_mode="single",
            status="open",
        )
    )

    db.add(
        models.Choice(
            id=choice_id,
            workspace_id=ws.id,
            choice_group_id=choice_group_id,
            title=f"修复 {issue.title} 的候选方案",
            rationale=f"为问题 `{issue.title}` 自动补充一条可执行路径。",
            patch={},
            proposed_node_ids=[],
            proposed_link_ids=[],
            impact_preview={
                "affectedGoals": [],
                "affectedActors": [],
                "affectedFlows": issue.related_node_ids,
                "affectedObjects": [],
                "affectedScreens": [],
                "resolvedIssues": [issue.id],
            },
            status="candidate",
        )
    )
    _touch_workspace(ws)
    return {"slotId": slot_id, "choiceGroupId": choice_group_id, "choiceId": choice_id}


def accept_choice(db: Session, ws: models.Workspace, choice_id: str) -> None:
    choice = db.get(models.Choice, choice_id)
    if not choice:
        raise HTTPException(status_code=404, detail=f"Choice `{choice_id}` 不存在")

    group = db.get(models.ChoiceGroup, choice.choice_group_id)
    if not group or group.workspace_id != ws.id:
        raise HTTPException(status_code=404, detail=f"ChoiceGroup `{choice.choice_group_id}` 不存在")

    patch = choice.patch or {}
    GraphPatchService.apply(db, ws, patch)

    group.selected_choice_id = choice.id
    group.status = "selected"
    choice.status = "selected"

    for c in group.choices:
        if c.id != choice.id and c.status == "candidate":
            c.status = "rejected"

    resolved = set((choice.impact_preview or {}).get("resolvedIssues") or [])
    resolved.update(patch.get("resolveIssueIds") or [])
    if resolved:
        issues = (
            db.query(models.Issue)
            .filter(models.Issue.workspace_id == ws.id, models.Issue.id.in_(list(resolved)))
            .all()
        )
        for issue in issues:
            issue.status = "resolved"

    slot = db.get(models.Slot, group.slot_id)
    if slot:
        slot.status = "filled"

    _append_operation(
        ws,
        kind="accept_choice",
        payload={
            "choiceId": choice.id,
            "choiceGroupId": group.id,
            "slotId": group.slot_id,
        },
    )
    _touch_workspace(ws)


def reject_choice(db: Session, ws: models.Workspace, choice_id: str) -> None:
    choice = db.get(models.Choice, choice_id)
    if not choice:
        raise HTTPException(status_code=404, detail=f"Choice `{choice_id}` 不存在")
    group = db.get(models.ChoiceGroup, choice.choice_group_id)
    if not group or group.workspace_id != ws.id:
        raise HTTPException(status_code=404, detail=f"ChoiceGroup `{choice.choice_group_id}` 不存在")
    choice.status = "rejected"
    _touch_workspace(ws)


def run_diagnosis(db: Session, ws: models.Workspace, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = (
        db.query(models.Issue)
        .filter(models.Issue.workspace_id == ws.id, models.Issue.status == "open")
        .all()
    )
    existing_keys = {
        (
            i.title.strip(),
            tuple(sorted(i.related_node_ids or [])),
            i.category,
            i.severity,
        )
        for i in existing
    }

    created: list[str] = []
    for di in run_deterministic_diagnosis(ws):
        if not _diagnostic_matches_scope(ws, di, scope):
            continue
        key = (di.title.strip(), tuple(sorted(di.related_node_ids or [])), di.category, di.severity)
        if key in existing_keys:
            continue
        issue_id = _new_id("gap")
        payload = di.as_payload()
        db.add(
            models.Issue(
                id=issue_id,
                workspace_id=ws.id,
                title=payload["title"],
                description=payload.get("description", ""),
                severity=payload.get("severity", "medium"),
                category=payload.get("category", "missing"),
                related_node_ids=payload.get("relatedNodeIds", []),
                suggested_projection=payload.get("suggestedProjection", "goal"),
                suggested_action=payload.get("suggestedAction", ""),
                status=payload.get("status", "open"),
                source=payload.get("source", {"type": "system"}),
            )
        )
        created.append(issue_id)
        existing_keys.add(key)

    if created:
        _append_operation(ws, kind="diagnose", payload={"createdIssueIds": created})
    _touch_workspace(ws)
    return {"createdIssueIds": created}


def apply_graph_patch(db: Session, ws: models.Workspace, patch: dict[str, Any]) -> None:
    GraphPatchService.apply(db, ws, patch)


def create_issue(db: Session, ws: models.Workspace, payload: dict[str, Any]) -> str:
    issue_id = payload.get("id") or _new_id("issue")
    exists = db.get(models.Issue, issue_id)
    if exists:
        raise HTTPException(status_code=409, detail=f"Issue `{issue_id}` 已存在")
    related_node_ids = _validate_related_node_ids(db, ws.id, payload.get("relatedNodeIds"))

    issue = models.Issue(
        id=issue_id,
        workspace_id=ws.id,
        title=payload["title"],
        description=payload.get("description", ""),
        severity=payload.get("severity", "medium"),
        category=payload.get("category", "missing"),
        related_node_ids=related_node_ids,
        suggested_projection=payload.get("suggestedProjection", "goal"),
        suggested_action=payload.get("suggestedAction", ""),
        status=payload.get("status", "open"),
        source=payload.get("source", {"type": "system"}),
    )
    db.add(issue)
    _touch_workspace(ws)
    return issue_id


def create_slot_for_issue(db: Session, ws: models.Workspace, issue_id: str) -> str:
    issue = db.get(models.Issue, issue_id)
    if not issue or issue.workspace_id != ws.id:
        raise HTTPException(status_code=404, detail=f"Issue `{issue_id}` 不存在")

    hint = f"issue:{issue.id}"
    existing = (
        db.query(models.Slot)
        .filter(models.Slot.workspace_id == ws.id)
        .all()
    )
    for s in existing:
        prompts = (s.context or {}).get("promptHints") or []
        if hint in prompts:
            return s.id

    owner_node_id = issue.related_node_ids[0] if issue.related_node_ids else next(iter({n.id for n in ws.nodes}), None)
    if not owner_node_id:
        raise HTTPException(status_code=400, detail="当前工作台没有可关联节点")

    owner_projection = issue.suggested_projection or "goal"

    expected: list[str]
    if issue.category in {"flow_gap", "rule_gap"}:
        expected = ["flow_step", "rule", "state_transition"]
    elif issue.category == "data_gap":
        expected = ["business_object", "field", "state_machine", "state_transition"]
    elif issue.category == "ui_gap":
        expected = ["screen", "ui_component"]
    else:
        expected = ["task", "flow_step", "rule", "ui_component"]

    slot_id = _new_id("slot")
    db.add(
        models.Slot(
            id=slot_id,
            workspace_id=ws.id,
            owner_node_id=owner_node_id,
            owner_projection=owner_projection,
            name=f"{issue.title} - 待补充",
            description=issue.description,
            expected_kinds=expected,
            arity="many",
            status="empty",
            choice_group_id=None,
            context={
                "projectionHints": [owner_projection],
                "relatedNodeIds": issue.related_node_ids,
                "promptHints": [hint],
            },
        )
    )
    _append_operation(ws, kind="create_slot_for_issue", payload={"issueId": issue.id, "slotId": slot_id})
    _touch_workspace(ws)
    return slot_id


def add_choice_to_group(db: Session, ws: models.Workspace, choice_group_id: str, payload: dict[str, Any]) -> str:
    group = db.get(models.ChoiceGroup, choice_group_id)
    if not group or group.workspace_id != ws.id:
        raise HTTPException(status_code=404, detail=f"ChoiceGroup `{choice_group_id}` 不存在")

    choice_id = payload.get("id") or _new_id("cand")
    exists = db.get(models.Choice, choice_id)
    if exists:
        raise HTTPException(status_code=409, detail=f"Choice `{choice_id}` 已存在")

    choice = models.Choice(
        id=choice_id,
        workspace_id=ws.id,
        choice_group_id=choice_group_id,
        title=payload["title"],
        rationale=payload.get("rationale", ""),
        patch=payload.get("patch") or {},
        proposed_node_ids=payload.get("proposedNodeIds", []),
        proposed_link_ids=payload.get("proposedLinkIds", []),
        impact_preview=payload.get("impactPreview", {}),
        status=payload.get("status", "candidate"),
    )
    db.add(choice)
    _touch_workspace(ws)
    return choice_id


def _touch_workspace(ws: models.Workspace) -> None:
    ws.updated_at = datetime.utcnow()
    audit = dict(ws.audit or {})
    audit["updatedAt"] = now_iso()
    ws.audit = audit


def _append_operation(ws: models.Workspace, kind: str, payload: dict[str, Any]) -> None:
    append_operation(
        ws,
        actionType=kind,
        targetIds=[],
        actor={"type": "system"},
        summary=kind,
        details=payload,
    )
