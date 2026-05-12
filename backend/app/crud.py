from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


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
        domain=ir.get("domain", {}),
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
        db.add(
            models.Node(
                id=node_id,
                workspace_id=workspace_id,
                kind=node.get("kind", "capability"),
                title=node.get("title", node_id),
                description=node.get("description"),
                status=node.get("status", "needs_confirmation"),
                confidence=node.get("confidence"),
                scope_status=node.get("scopeStatus"),
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
        db.add(
            models.Slot(
                id=slot_id,
                workspace_id=workspace_id,
                owner_node_id=slot["ownerNodeId"],
                name=slot["name"],
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
            slot_id=cg["slotId"],
            selected_choice_id=cg.get("selectedChoiceId"),
            selection_mode=cg.get("selectionMode", "single"),
            status=cg.get("status", "open"),
        )
        db.add(group)
        for choice in cg.get("choices", []):
            db.add(
                models.Choice(
                    id=choice["id"],
                    choice_group_id=cg_id,
                    title=choice["title"],
                    rationale=choice.get("rationale", ""),
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
                title=issue["title"],
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
        payload = {
            "id": n.id,
            "kind": n.kind,
            "title": n.title,
            "description": n.description,
            "status": n.status,
            "confidence": n.confidence,
            "scopeStatus": n.scope_status,
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
                    "proposedNodeIds": c.proposed_node_ids,
                    "proposedLinkIds": c.proposed_link_ids,
                    "impactPreview": c.impact_preview,
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

    return {
        "id": ws.id,
        "name": ws.name,
        "idea": ws.idea,
        "domain": ws.domain or {"assumptions": []},
        "nodes": nodes,
        "links": links,
        "slots": slots,
        "choiceGroups": choice_groups,
        "proposals": ws.proposals or {},
        "issues": issues,
        "projections": ws.projections or {},
        "audit": audit,
    }


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
        node.scope_status = updates["scopeStatus"]
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
    update_node(db, ws, node_id, {"scopeStatus": scope_status})


def update_issue_status(db: Session, ws: models.Workspace, issue_id: str, status: str) -> None:
    issue = db.get(models.Issue, issue_id)
    if not issue or issue.workspace_id != ws.id:
        raise HTTPException(status_code=404, detail=f"Issue `{issue_id}` 不存在")
    issue.status = status
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
            name=f"{issue.title} - 修复方案",
            description=issue.description,
            expected_kinds=["flow_step", "rule", "ui_component"],
            arity="many",
            status="expanding",
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
            choice_group_id=choice_group_id,
            title=f"修复 {issue.title} 的候选方案",
            rationale=f"为问题 `{issue.title}` 自动补充一条可执行路径。",
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

    group.selected_choice_id = choice.id
    group.status = "selected"
    choice.status = "selected"

    for c in group.choices:
        if c.id != choice.id and c.status == "candidate":
            c.status = "rejected"

    resolved = (choice.impact_preview or {}).get("resolvedIssues") or []
    if resolved:
        issues = db.query(models.Issue).filter(models.Issue.workspace_id == ws.id, models.Issue.id.in_(resolved)).all()
        for issue in issues:
            issue.status = "resolved"

    slot = db.get(models.Slot, group.slot_id)
    if slot:
        slot.status = "filled"

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


def run_diagnosis(db: Session, ws: models.Workspace) -> dict[str, Any]:
    node_kinds = {}
    for node in ws.nodes:
        node_kinds.setdefault(node.kind, []).append(node.id)

    created: list[str] = []
    if not node_kinds.get("actor"):
        issue_id = _new_id("gap")
        db.add(
            models.Issue(
                id=issue_id,
                workspace_id=ws.id,
                title="缺少参与角色",
                description="当前需求空间没有角色节点，无法形成责任闭环。",
                severity="high",
                category="missing",
                related_node_ids=[],
                suggested_projection="role",
                suggested_action="请补充至少一个业务角色。",
                status="open",
                source={"type": "system"},
            )
        )
        created.append(issue_id)

    if not node_kinds.get("flow_step"):
        issue_id = _new_id("gap")
        db.add(
            models.Issue(
                id=issue_id,
                workspace_id=ws.id,
                title="缺少流程步骤",
                description="当前需求空间没有流程步骤，无法执行预览验证。",
                severity="high",
                category="flow_gap",
                related_node_ids=[],
                suggested_projection="system",
                suggested_action="请补充主流程步骤。",
                status="open",
                source={"type": "system"},
            )
        )
        created.append(issue_id)

    _touch_workspace(ws)
    return {"createdIssueIds": created}


def apply_graph_patch(db: Session, ws: models.Workspace, patch: dict[str, Any]) -> None:
    remove_node_ids = set(patch.get("removeNodeIds") or [])
    remove_link_ids = set(patch.get("removeLinkIds") or [])
    resolve_issue_ids = set(patch.get("resolveIssueIds") or [])

    if remove_link_ids:
        db.query(models.Link).filter(
            models.Link.workspace_id == ws.id, models.Link.id.in_(list(remove_link_ids))
        ).delete(synchronize_session=False)

    if remove_node_ids:
        db.query(models.Link).filter(
            models.Link.workspace_id == ws.id,
            (models.Link.source_id.in_(list(remove_node_ids)) | models.Link.target_id.in_(list(remove_node_ids))),
        ).delete(synchronize_session=False)

        db.query(models.Slot).filter(
            models.Slot.workspace_id == ws.id, models.Slot.owner_node_id.in_(list(remove_node_ids))
        ).delete(synchronize_session=False)

        nodes = db.query(models.Node).filter(models.Node.workspace_id == ws.id, models.Node.id.in_(list(remove_node_ids))).all()
        for n in nodes:
            db.delete(n)

        issues = db.query(models.Issue).filter(models.Issue.workspace_id == ws.id).all()
        for issue in issues:
            if not issue.related_node_ids:
                continue
            new_related = [rid for rid in issue.related_node_ids if rid not in remove_node_ids]
            if new_related != issue.related_node_ids:
                issue.related_node_ids = new_related

    for node in patch.get("addNodes") or []:
        node_id = node.get("id")
        if not node_id:
            raise HTTPException(status_code=400, detail="addNodes 中的节点必须包含 id")
        exists = db.get(models.Node, node_id)
        if exists:
            raise HTTPException(status_code=409, detail=f"Node `{node_id}` 已存在")

        base_keys = {"id", "kind", "title", "description", "status", "confidence", "scopeStatus", "source", "slots"}
        extra = {k: v for k, v in node.items() if k not in base_keys}

        db.add(
            models.Node(
                id=node_id,
                workspace_id=ws.id,
                kind=node.get("kind", "capability"),
                title=node.get("title") or node_id,
                description=node.get("description"),
                status=node.get("status") or "needs_confirmation",
                confidence=node.get("confidence"),
                scope_status=node.get("scopeStatus"),
                source=node.get("source") or {"type": "user"},
                slots=node.get("slots"),
                extra=extra,
            )
        )

    for update in patch.get("updateNodes") or []:
        node_id = update.get("id")
        if not node_id:
            raise HTTPException(status_code=400, detail="updateNodes 中的节点必须包含 id")

        base_update: dict[str, Any] = {}
        extra: dict[str, Any] = {}
        for k, v in update.items():
            if k in {"title", "description", "status", "scopeStatus", "confidence", "source"}:
                base_update[k] = v
            elif k not in {"id", "kind"}:
                extra[k] = v
        if extra:
            base_update["extra"] = extra

        update_node(db, ws, node_id, base_update)

    for link in patch.get("addLinks") or []:
        link_id = link.get("id")
        if not link_id:
            raise HTTPException(status_code=400, detail="addLinks 中的链接必须包含 id")
        exists = db.get(models.Link, link_id)
        if exists:
            raise HTTPException(status_code=409, detail=f"Link `{link_id}` 已存在")
        db.add(
            models.Link(
                id=link_id,
                workspace_id=ws.id,
                source_id=link.get("sourceId"),
                target_id=link.get("targetId"),
                type=link.get("type"),
                label=link.get("label"),
                status=link.get("status", "active"),
                source=link.get("source", {"type": "ai"}),
            )
        )

    for slot_update in patch.get("updateSlots") or []:
        slot_id = slot_update.get("id")
        if not slot_id:
            raise HTTPException(status_code=400, detail="updateSlots 中的 slot 必须包含 id")
        slot = db.get(models.Slot, slot_id)
        if not slot or slot.workspace_id != ws.id:
            raise HTTPException(status_code=404, detail=f"Slot `{slot_id}` 不存在")

        if "name" in slot_update and slot_update["name"] is not None:
            slot.name = slot_update["name"]
        if "description" in slot_update:
            slot.description = slot_update["description"]
        if "expectedKinds" in slot_update and slot_update["expectedKinds"] is not None:
            slot.expected_kinds = slot_update["expectedKinds"]
        if "arity" in slot_update and slot_update["arity"] is not None:
            slot.arity = slot_update["arity"]
        if "status" in slot_update and slot_update["status"] is not None:
            slot.status = slot_update["status"]
        if "choiceGroupId" in slot_update:
            slot.choice_group_id = slot_update["choiceGroupId"]
        if "context" in slot_update and slot_update["context"] is not None:
            slot.context = slot_update["context"]

    if resolve_issue_ids:
        issues = (
            db.query(models.Issue)
            .filter(models.Issue.workspace_id == ws.id, models.Issue.id.in_(list(resolve_issue_ids)))
            .all()
        )
        for issue in issues:
            issue.status = "resolved"

    _touch_workspace(ws)


def create_issue(db: Session, ws: models.Workspace, payload: dict[str, Any]) -> str:
    issue_id = payload.get("id") or _new_id("issue")
    exists = db.get(models.Issue, issue_id)
    if exists:
        raise HTTPException(status_code=409, detail=f"Issue `{issue_id}` 已存在")

    issue = models.Issue(
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
    db.add(issue)
    _touch_workspace(ws)
    return issue_id


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
        choice_group_id=choice_group_id,
        title=payload["title"],
        rationale=payload.get("rationale", ""),
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
