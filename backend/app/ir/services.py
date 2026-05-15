from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from .. import crud
from .llm import LLMProvider, load_llm_config
from .prompts import (
    ExpandSlotInput,
    ExpandSlotOutput,
    InitializeWorkspaceInput,
    InitializeWorkspaceOutput,
    build_expand_slot_messages,
    build_initialize_messages,
)
from .schema import AuditInfo, GraphPatch, Meta, ProjectionKind, ProjectionState, RequirementSpaceIR
from .validators import validate_choice_group, validate_ir


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _canonicalize_assumptions(meta: dict[str, Any]) -> dict[str, Any]:
    assumptions = meta.get("assumptions")
    if not isinstance(assumptions, list):
        return meta

    normalized_items: list[dict[str, str]] = []
    for index, item in enumerate(assumptions, start=1):
        if isinstance(item, dict):
            item_id = str(item.get("id") or f"assumption_{index}")
            description = str(item.get("description") or "")
            normalized_items.append({"id": item_id, "description": description})
        elif isinstance(item, str):
            text = item.strip()
            if text:
                normalized_items.append({"id": f"assumption_{index}", "description": text})
    meta["assumptions"] = normalized_items
    return meta


def _canonicalize_initialize_links(payload: dict[str, Any]) -> dict[str, Any]:
    nodes = payload.get("nodes")
    links = payload.get("links")
    if not isinstance(nodes, dict) or not isinstance(links, list):
        return payload

    for link in links:
        if not isinstance(link, dict):
            continue
        source_id = link.get("sourceId")
        target_id = link.get("targetId")
        if not isinstance(source_id, str) or not isinstance(target_id, str):
            continue
        source_node = nodes.get(source_id)
        target_node = nodes.get(target_id)
        if not isinstance(source_node, dict) or not isinstance(target_node, dict):
            continue

        source_kind = source_node.get("kind")
        target_kind = target_node.get("kind")
        link_type = link.get("type")

        # Canonicalize the most common LLM slips to the latest link semantics.
        if link_type == "supports" and source_kind == "flow_step" and target_kind == "flow_step":
            link["type"] = "precedes"
        elif link_type == "realizes" and source_kind == "task" and target_kind == "capability":
            link["type"] = "supports"

    return payload


def _canonicalize_initialize_issues(payload: dict[str, Any]) -> dict[str, Any]:
    nodes = payload.get("nodes")
    slots = payload.get("slots")
    issues = payload.get("issues")
    if not isinstance(nodes, dict) or not isinstance(slots, dict) or not isinstance(issues, dict):
        return payload

    node_ids = set(nodes.keys())
    slot_owner_map = {
        slot_id: slot.get("ownerNodeId")
        for slot_id, slot in slots.items()
        if isinstance(slot, dict) and isinstance(slot.get("ownerNodeId"), str)
    }

    for issue in issues.values():
        if not isinstance(issue, dict):
            continue
        related_ids = issue.get("relatedNodeIds")
        if not isinstance(related_ids, list):
            continue
        normalized_ids: list[str] = []
        for item in related_ids:
            if not isinstance(item, str):
                continue
            mapped = item if item in node_ids else slot_owner_map.get(item)
            if isinstance(mapped, str) and mapped in node_ids and mapped not in normalized_ids:
                normalized_ids.append(mapped)
        issue["relatedNodeIds"] = normalized_ids

    return payload


def _normalize_initialize_ir(raw_ir: dict[str, Any], *, idea: str) -> dict[str, Any]:
    payload = dict(raw_ir)
    payload.setdefault("id", "rs_bootstrap_seed")
    payload.setdefault("name", "新建需求探索项目")
    payload.setdefault("idea", idea)
    payload.setdefault("meta", Meta(inputPrompt=idea).model_dump(mode="json"))
    if isinstance(payload.get("meta"), dict):
        payload["meta"] = _canonicalize_assumptions(dict(payload["meta"]))
        payload["meta"].setdefault("inputPrompt", idea)
    payload.setdefault("nodes", {})
    payload.setdefault("links", [])
    payload.setdefault("slots", {})
    payload.setdefault("choiceGroups", {})
    payload.setdefault("proposals", {})
    payload.setdefault("issues", {})
    payload.setdefault("projections", ProjectionState().model_dump(mode="json"))
    payload.setdefault(
        "audit",
        AuditInfo(sourceSummary=[{"type": "user", "text": idea}]).model_dump(mode="json"),
    )
    payload = _canonicalize_initialize_links(payload)
    return _canonicalize_initialize_issues(payload)


def _validate_initialize_output(raw: dict[str, Any], *, idea: str) -> RequirementSpaceIR:
    if not isinstance(raw, dict) or not isinstance(raw.get("ir"), dict):
        raise HTTPException(status_code=502, detail="InitializeWorkspaceOutput schema 校验失败：顶层必须是 {'ir': {...}}")

    normalized = {"ir": _normalize_initialize_ir(raw["ir"], idea=idea)}
    try:
        output = InitializeWorkspaceOutput.model_validate(normalized)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"InitializeWorkspaceOutput schema 校验失败：{exc}") from exc
    return validate_ir(output.ir, status_code=502)


def _validate_expand_slot_output(raw: dict[str, Any], *, slot_id: str) -> ExpandSlotOutput:
    try:
        output = ExpandSlotOutput.model_validate(raw)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ExpandSlotOutput schema 校验失败：{exc}") from exc
    output.choiceGroup = validate_choice_group(output.choiceGroup, status_code=502, expected_slot_id=slot_id)
    return output


def initialize_workspace_from_idea(idea: str) -> dict[str, Any]:
    idea = (idea or "").strip()
    if not idea:
        raise HTTPException(status_code=400, detail="prompt 不能为空")

    try:
        provider = LLMProvider(load_llm_config())
        system, user = build_initialize_messages(InitializeWorkspaceInput(idea=idea))
        raw = provider.complete_json(system=system, user=user)
        ir = _validate_initialize_output(raw, idea=idea)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"InitializeWorkspacePrompt 失败：{exc}") from exc

    payload = ir.model_dump(mode="json")
    payload["id"] = _new_id("rs")
    payload["name"] = payload.get("name") or "新建需求探索项目"
    payload["idea"] = idea

    meta = dict(payload.get("meta") or {})
    meta.setdefault("assumptions", [])
    meta.setdefault("inputPrompt", idea)
    payload["meta"] = meta

    audit = dict(payload.get("audit") or {})
    audit.setdefault("createdAt", _now_iso())
    audit["updatedAt"] = _now_iso()
    audit.setdefault("sourceSummary", [{"type": "user", "text": idea}])
    audit.setdefault("operationLog", [])
    payload["audit"] = audit

    return validate_ir(payload, status_code=400).model_dump(mode="json")


def expand_slot(db, ws, slot_id: str) -> str:
    ir = validate_ir(crud.serialize_workspace(ws), status_code=500)
    slot = ir.slots.get(slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail=f"Slot `{slot_id}` 不存在")
    existing_group = next((group for group in ir.choiceGroups.values() if group.slotId == slot.id), None)
    if existing_group:
        return existing_group.id

    owner = ir.nodes.get(slot.ownerNodeId)
    if not owner:
        raise HTTPException(status_code=400, detail="Slot ownerNode 不存在")

    related_node_ids = set(slot.context.relatedNodeIds)
    related_node_ids.add(slot.ownerNodeId)
    related_nodes = [node for node in ir.nodes.values() if node.id in related_node_ids and node.id != owner.id]
    related_links = [
        link for link in ir.links if link.sourceId in related_node_ids or link.targetId in related_node_ids
    ]

    try:
        provider = LLMProvider(load_llm_config())
        system, user = build_expand_slot_messages(
            ExpandSlotInput(
                slot=slot,
                ownerNode=owner,
                relatedNodes=related_nodes,
                relatedLinks=related_links,
                projectionContext=slot.ownerProjection.value,
            )
        )
        raw = provider.complete_json(system=system, user=user)
        generated_group = _validate_expand_slot_output(raw, slot_id=slot.id).choiceGroup
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ExpandSlotPrompt 失败：{exc}") from exc

    if not generated_group.choices:
        raise HTTPException(status_code=500, detail="ExpandSlotPrompt 没有返回 choices")

    raw_group_id = _new_id("cg")
    group_payload = generated_group.model_dump(mode="json")
    group_payload["id"] = raw_group_id
    group_payload["slotId"] = slot.id
    group_payload["selectedChoiceIds"] = []
    group_payload["status"] = "open"
    group_payload["choices"] = [
        {**choice, "choiceGroupId": raw_group_id}
        for choice in group_payload["choices"][:3]
    ]

    result = crud.apply_graph_patch(
        db,
        ws,
        {
            "addChoiceGroups": [group_payload],
            "updateSlots": [{"id": slot.id, "status": "candidate_ready"}],
        },
    )
    return result["idMap"].get(raw_group_id, raw_group_id)


def apply_choice_patch(db, ws, choice_id: str) -> dict[str, Any]:
    return crud.accept_choice(db, ws, choice_id)
