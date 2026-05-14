from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import crud, models
from .graph_patch import GraphPatchService
from .graph_patch import namespace_graph_patch_ids
from .llm import LLMProvider, load_llm_config
from .prompts import (
    ExpandSlotInput,
    ExpandSlotOutput,
    InitializeWorkspaceInput,
    InitializeWorkspaceOutput,
    build_expand_slot_messages,
    build_initialize_messages,
)
from .validators import validate_ir


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _coerce_impact_preview(raw: Any) -> dict[str, Any]:
    safe = raw if isinstance(raw, dict) else {}
    return {
        "affectedGoals": safe.get("affectedGoals") or [],
        "affectedActors": safe.get("affectedActors") or [],
        "affectedFlows": safe.get("affectedFlows") or [],
        "affectedObjects": safe.get("affectedObjects") or [],
        "affectedScreens": safe.get("affectedScreens") or [],
        "newIssues": safe.get("newIssues"),
        "resolvedIssues": safe.get("resolvedIssues"),
    }


def _recursive_replace_ids(value: Any, id_map: dict[str, str]) -> Any:
    if isinstance(value, str):
        return id_map.get(value, value)
    if isinstance(value, list):
        return [_recursive_replace_ids(item, id_map) for item in value]
    if isinstance(value, dict):
        return {key: _recursive_replace_ids(item, id_map) for key, item in value.items()}
    return value


def _namespace_id(namespace: str, raw_id: str) -> str:
    if raw_id.startswith(f"{namespace}__"):
        return raw_id
    return f"{namespace}__{raw_id}"


def _namespace_ir_ids(ir: dict[str, Any], namespace: str) -> dict[str, Any]:
    nodes = ir.get("nodes") or {}
    slots = ir.get("slots") or {}
    choice_groups = ir.get("choiceGroups") or {}
    issues = ir.get("issues") or {}

    node_id_map = {node_id: _namespace_id(namespace, node_id) for node_id in nodes.keys()}
    slot_id_map = {slot_id: _namespace_id(namespace, slot_id) for slot_id in slots.keys()}
    choice_group_id_map = {
        choice_group_id: _namespace_id(namespace, choice_group_id) for choice_group_id in choice_groups.keys()
    }
    issue_id_map = {issue_id: _namespace_id(namespace, issue_id) for issue_id in issues.keys()}

    choice_id_map: dict[str, str] = {}
    link_id_map: dict[str, str] = {}
    for link in ir.get("links") or []:
        link_id = link.get("id")
        if isinstance(link_id, str) and link_id:
            link_id_map[link_id] = _namespace_id(namespace, link_id)
    for choice_group in choice_groups.values():
        if not isinstance(choice_group, dict):
            continue
        for choice in choice_group.get("choices") or []:
            if isinstance(choice, dict):
                choice_id = choice.get("id")
                if isinstance(choice_id, str) and choice_id:
                    choice_id_map[choice_id] = _namespace_id(namespace, choice_id)

    id_map: dict[str, str] = {}
    id_map.update(node_id_map)
    id_map.update(slot_id_map)
    id_map.update(choice_group_id_map)
    id_map.update(choice_id_map)
    id_map.update(issue_id_map)
    id_map.update(link_id_map)

    remapped_nodes: dict[str, Any] = {}
    for old_node_id, node in nodes.items():
        if not isinstance(node, dict):
            continue
        new_node_id = node_id_map[old_node_id]
        remapped_node = dict(node)
        remapped_node["id"] = new_node_id
        if isinstance(remapped_node.get("slots"), list):
            remapped_node["slots"] = [slot_id_map.get(slot_id, slot_id) for slot_id in remapped_node["slots"]]
        remapped_nodes[new_node_id] = _recursive_replace_ids(remapped_node, {})

    remapped_links: list[dict[str, Any]] = []
    for link in ir.get("links") or []:
        if not isinstance(link, dict):
            continue
        remapped_link = dict(link)
        link_id = remapped_link.get("id")
        source_id = remapped_link.get("sourceId")
        target_id = remapped_link.get("targetId")
        if isinstance(link_id, str):
            remapped_link["id"] = link_id_map.get(link_id, link_id)
        if isinstance(source_id, str):
            remapped_link["sourceId"] = node_id_map.get(source_id, source_id)
        if isinstance(target_id, str):
            remapped_link["targetId"] = node_id_map.get(target_id, target_id)
        remapped_links.append(remapped_link)

    remapped_slots: dict[str, Any] = {}
    for old_slot_id, slot in slots.items():
        if not isinstance(slot, dict):
            continue
        new_slot_id = slot_id_map[old_slot_id]
        remapped_slot = dict(slot)
        remapped_slot["id"] = new_slot_id
        owner_node_id = remapped_slot.get("ownerNodeId")
        choice_group_id = remapped_slot.get("choiceGroupId")
        if isinstance(owner_node_id, str):
            remapped_slot["ownerNodeId"] = node_id_map.get(owner_node_id, owner_node_id)
        if isinstance(choice_group_id, str):
            remapped_slot["choiceGroupId"] = choice_group_id_map.get(choice_group_id, choice_group_id)
        if isinstance(remapped_slot.get("context"), dict):
            context = dict(remapped_slot["context"])
            if isinstance(context.get("relatedNodeIds"), list):
                context["relatedNodeIds"] = [node_id_map.get(node_id, node_id) for node_id in context["relatedNodeIds"]]
            remapped_slot["context"] = context
        remapped_slots[new_slot_id] = remapped_slot

    remapped_choice_groups: dict[str, Any] = {}
    for old_choice_group_id, choice_group in choice_groups.items():
        if not isinstance(choice_group, dict):
            continue
        new_choice_group_id = choice_group_id_map[old_choice_group_id]
        remapped_group = dict(choice_group)
        remapped_group["id"] = new_choice_group_id
        slot_id = remapped_group.get("slotId")
        selected_choice_id = remapped_group.get("selectedChoiceId")
        if isinstance(slot_id, str):
            remapped_group["slotId"] = slot_id_map.get(slot_id, slot_id)
        if isinstance(selected_choice_id, str):
            remapped_group["selectedChoiceId"] = choice_id_map.get(selected_choice_id, selected_choice_id)

        remapped_choices: list[dict[str, Any]] = []
        for choice in remapped_group.get("choices") or []:
            if not isinstance(choice, dict):
                continue
            remapped_choice = dict(choice)
            choice_id = remapped_choice.get("id")
            if isinstance(choice_id, str):
                remapped_choice["id"] = choice_id_map.get(choice_id, choice_id)
            if isinstance(remapped_choice.get("proposedNodeIds"), list):
                remapped_choice["proposedNodeIds"] = [
                    node_id_map.get(node_id, node_id) for node_id in remapped_choice["proposedNodeIds"]
                ]
            if isinstance(remapped_choice.get("proposedLinkIds"), list):
                remapped_choice["proposedLinkIds"] = [
                    link_id_map.get(link_id, link_id) for link_id in remapped_choice["proposedLinkIds"]
                ]
            if isinstance(remapped_choice.get("impactPreview"), dict):
                remapped_choice["impactPreview"] = _recursive_replace_ids(remapped_choice["impactPreview"], id_map)
            if isinstance(remapped_choice.get("patch"), dict):
                remapped_choice["patch"] = _recursive_replace_ids(remapped_choice["patch"], id_map)
            remapped_choices.append(remapped_choice)
        remapped_group["choices"] = remapped_choices
        remapped_choice_groups[new_choice_group_id] = remapped_group

    remapped_issues: dict[str, Any] = {}
    for old_issue_id, issue in issues.items():
        if not isinstance(issue, dict):
            continue
        new_issue_id = issue_id_map[old_issue_id]
        remapped_issue = dict(issue)
        remapped_issue["id"] = new_issue_id
        if isinstance(remapped_issue.get("relatedNodeIds"), list):
            remapped_issue["relatedNodeIds"] = [
                node_id_map.get(node_id, node_id) for node_id in remapped_issue["relatedNodeIds"]
            ]
        remapped_issues[new_issue_id] = remapped_issue

    ir["nodes"] = remapped_nodes
    ir["links"] = remapped_links
    ir["slots"] = remapped_slots
    ir["choiceGroups"] = remapped_choice_groups
    ir["issues"] = remapped_issues
    ir["projections"] = _recursive_replace_ids(ir.get("projections") or {}, id_map)
    ir["proposals"] = _recursive_replace_ids(ir.get("proposals") or {}, id_map)
    ir["audit"] = _recursive_replace_ids(ir.get("audit") or {}, id_map)
    return ir


def initialize_workspace_from_idea(idea: str) -> dict[str, Any]:
    idea = (idea or "").strip()
    if not idea:
        raise HTTPException(status_code=400, detail="prompt 不能为空")

    try:
        cfg = load_llm_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    provider = LLMProvider(cfg)
    inp = InitializeWorkspaceInput(idea=idea)
    system, user = build_initialize_messages(inp)
    try:
        raw = provider.complete_json(system=system, user=user)
        out = InitializeWorkspaceOutput.model_validate(raw)
        ir = out.ir
        if not isinstance(ir, dict):
            raise ValueError("ir 必须是对象")

        ir["id"] = _new_id("rs")
        ir = _namespace_ir_ids(ir, ir["id"])
        ir["name"] = ir.get("name") or "新建需求探索项目"
        ir["idea"] = idea

        meta = ir.get("meta")
        if not isinstance(meta, dict):
            meta = {}
        if "assumptions" not in meta:
            meta["assumptions"] = []
        if "inputPrompt" not in meta:
            meta["inputPrompt"] = idea
        ir["meta"] = meta

        audit = ir.get("audit")
        if not isinstance(audit, dict):
            audit = {}
        audit.setdefault("createdAt", _now_iso())
        audit["updatedAt"] = _now_iso()
        audit.setdefault("sourceSummary", [{"type": "user", "text": idea}])
        ir["audit"] = audit

        validate_ir(ir)
        return ir
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"InitializeWorkspacePrompt 失败：{e}") from e


def expand_slot(db: Session, ws: models.Workspace, slot_id: str) -> str:
    slot = db.get(models.Slot, slot_id)
    if not slot or slot.workspace_id != ws.id:
        raise HTTPException(status_code=404, detail=f"Slot `{slot_id}` 不存在")

    if slot.choice_group_id:
        return slot.choice_group_id

    owner = db.get(models.Node, slot.owner_node_id)
    if not owner or owner.workspace_id != ws.id:
        raise HTTPException(status_code=400, detail="Slot ownerNode 不存在")

    related_node_ids = set((slot.context or {}).get("relatedNodeIds") or [])
    related_node_ids.add(slot.owner_node_id)

    related_nodes = (
        db.query(models.Node)
        .filter(models.Node.workspace_id == ws.id, models.Node.id.in_(list(related_node_ids)))
        .all()
    )
    related_links = (
        db.query(models.Link)
        .filter(
            models.Link.workspace_id == ws.id,
            (models.Link.source_id.in_(list(related_node_ids)) | models.Link.target_id.in_(list(related_node_ids))),
        )
        .all()
    )

    slot_payload = {
        "id": slot.id,
        "ownerNodeId": slot.owner_node_id,
        "ownerProjection": slot.owner_projection
        or ((slot.context or {}).get("projectionHints") or ["goal"])[0],
        "name": slot.name,
        "description": slot.description,
        "expectedKinds": slot.expected_kinds,
        "arity": slot.arity,
        "status": slot.status,
        "choiceGroupId": slot.choice_group_id,
        "context": slot.context or {},
    }
    owner_payload = {
        "id": owner.id,
        "kind": owner.kind,
        "title": owner.title,
        "description": owner.description,
        "status": owner.status,
        "confidence": owner.confidence,
        "scopeStatus": owner.scope_status,
        "source": owner.source,
        **(owner.extra or {}),
    }
    related_node_payloads = [
        {
            "id": n.id,
            "kind": n.kind,
            "title": n.title,
            "description": n.description,
            "status": n.status,
            "confidence": n.confidence,
            "scopeStatus": n.scope_status,
            "source": n.source,
            **(n.extra or {}),
        }
        for n in related_nodes
        if n.id != owner.id
    ]
    related_link_payloads = [
        {
            "id": l.id,
            "sourceId": l.source_id,
            "targetId": l.target_id,
            "type": l.type,
            "label": l.label,
            "status": l.status,
            "source": l.source,
        }
        for l in related_links
    ]

    try:
        cfg = load_llm_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    projection = slot_payload["ownerProjection"]
    provider = LLMProvider(cfg)
    inp = ExpandSlotInput(
        slot=slot_payload,
        ownerNode=owner_payload,
        relatedNodes=related_node_payloads,
        relatedLinks=related_link_payloads,
        projectionContext=str(projection),
    )
    system, user = build_expand_slot_messages(inp)
    try:
        raw = provider.complete_json(system=system, user=user)
        out = ExpandSlotOutput.model_validate(raw)
        choice_group = out.choiceGroup
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ExpandSlotPrompt 失败：{e}") from e

    if not isinstance(choice_group, dict):
        raise HTTPException(status_code=500, detail="ExpandSlotPrompt 输出不合法")

    choices = choice_group.get("choices") or []
    if not isinstance(choices, list) or len(choices) == 0:
        raise HTTPException(status_code=500, detail="ExpandSlotPrompt 没有返回 choices")

    group_id = _new_id("cg")
    group = models.ChoiceGroup(
        id=group_id,
        workspace_id=ws.id,
        slot_id=slot.id,
        selected_choice_id=None,
        selection_mode=str(choice_group.get("selectionMode") or "single"),
        status="open",
    )
    db.add(group)

    for c in choices[:3]:
        if not isinstance(c, dict):
            continue
        choice = models.Choice(
            id=_new_id("cand"),
            workspace_id=ws.id,
            choice_group_id=group_id,
            title=str(c.get("title") or "候选方案"),
            rationale=str(c.get("rationale") or ""),
            patch=namespace_graph_patch_ids(ws.id, c.get("patch")) if isinstance(c.get("patch"), dict) else {},
            proposed_node_ids=c.get("proposedNodeIds") if isinstance(c.get("proposedNodeIds"), list) else [],
            proposed_link_ids=c.get("proposedLinkIds") if isinstance(c.get("proposedLinkIds"), list) else [],
            impact_preview=_coerce_impact_preview(c.get("impactPreview")),
            status="candidate",
        )
        db.add(choice)

    slot.choice_group_id = group_id
    slot.status = "candidate_ready"
    slot.owner_projection = slot.owner_projection or str(projection)

    return group_id


def apply_choice_patch(db: Session, ws: models.Workspace, choice_id: str) -> None:
    choice = db.get(models.Choice, choice_id)
    if not choice:
        raise HTTPException(status_code=404, detail=f"Choice `{choice_id}` 不存在")
    group = db.get(models.ChoiceGroup, choice.choice_group_id)
    if not group or group.workspace_id != ws.id:
        raise HTTPException(status_code=404, detail="ChoiceGroup 不存在")
    GraphPatchService.apply(db, ws, choice.patch or {})
