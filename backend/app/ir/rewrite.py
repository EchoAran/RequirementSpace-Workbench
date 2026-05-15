from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import crud, models
from .graph_patch import GraphPatchService
from .llm import LLMProvider, load_llm_config
from .prompts import RewriteInput, RewriteOutput, build_rewrite_messages
from .validators import validate_proposal


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _validate_rewrite_output(raw: dict[str, Any], *, workspace_id: str):
    try:
        output = RewriteOutput.model_validate(raw)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"RewriteOutput schema 校验失败：{exc}") from exc
    proposal = validate_proposal(output.proposal, status_code=502, expected_workspace_id=workspace_id)
    return output, proposal


def _build_ir_slice(ir: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
    kind = scope.get("kind")
    if kind == "node":
        target_id = scope.get("nodeId")
    elif kind == "issue":
        target_id = scope.get("issueId")
    elif kind == "slot":
        target_id = scope.get("slotId")
    elif kind == "choiceGroup":
        target_id = scope.get("choiceGroupId")
    elif kind == "choice":
        target_id = scope.get("choiceId")
    else:
        target_id = scope.get("targetId")

    if not isinstance(target_id, str) or not target_id:
        return {"nodes": {}, "links": [], "slots": {}, "issues": {}}

    nodes: dict[str, Any] = ir.get("nodes") or {}
    links: list[dict[str, Any]] = ir.get("links") or []
    slots: dict[str, Any] = ir.get("slots") or {}
    issues: dict[str, Any] = ir.get("issues") or {}

    related_node_ids: set[str] = set()
    if kind == "issue":
        issue = issues.get(target_id) or {}
        for nid in (issue.get("relatedNodeIds") or []):
            if isinstance(nid, str):
                related_node_ids.add(nid)
    elif kind == "slot":
        slot = slots.get(target_id) or {}
        owner = slot.get("ownerNodeId")
        if isinstance(owner, str):
            related_node_ids.add(owner)
        for nid in ((slot.get("context") or {}).get("relatedNodeIds") or []):
            if isinstance(nid, str):
                related_node_ids.add(nid)
    elif kind == "choiceGroup":
        group = (ir.get("choiceGroups") or {}).get(target_id) or {}
        slot_id = group.get("slotId")
        slot = slots.get(slot_id) or {}
        owner = slot.get("ownerNodeId")
        if isinstance(owner, str):
            related_node_ids.add(owner)
        for nid in ((slot.get("context") or {}).get("relatedNodeIds") or []):
            if isinstance(nid, str):
                related_node_ids.add(nid)
    elif kind == "choice":
        group = next(
            (
                cg
                for cg in (ir.get("choiceGroups") or {}).values()
                if any(isinstance(choice, dict) and choice.get("id") == target_id for choice in (cg.get("choices") or []))
            ),
            {},
        )
        slot_id = group.get("slotId")
        slot = slots.get(slot_id) or {}
        owner = slot.get("ownerNodeId")
        if isinstance(owner, str):
            related_node_ids.add(owner)
        for nid in ((slot.get("context") or {}).get("relatedNodeIds") or []):
            if isinstance(nid, str):
                related_node_ids.add(nid)
    else:
        related_node_ids.add(target_id)

    neighbor_ids: set[str] = set(related_node_ids)
    for l in links:
        if not isinstance(l, dict):
            continue
        s = l.get("sourceId")
        t = l.get("targetId")
        if s in related_node_ids or t in related_node_ids:
            if isinstance(s, str):
                neighbor_ids.add(s)
            if isinstance(t, str):
                neighbor_ids.add(t)

    slice_nodes = {nid: nodes[nid] for nid in neighbor_ids if nid in nodes}
    slice_links = [l for l in links if (l.get("sourceId") in neighbor_ids or l.get("targetId") in neighbor_ids)]
    slice_slots = {sid: s for sid, s in slots.items() if s.get("ownerNodeId") in neighbor_ids}
    slice_issues = {iid: i for iid, i in issues.items() if any(nid in neighbor_ids for nid in (i.get("relatedNodeIds") or []))}

    return {"nodes": slice_nodes, "links": slice_links, "slots": slice_slots, "issues": slice_issues}


def rewrite_workspace(db: Session, ws: models.Workspace, scope: dict[str, Any], instruction: str) -> dict[str, Any]:
    instruction = (instruction or "").strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="instruction 不能为空")

    ir = crud.serialize_workspace(ws)
    ir_slice = _build_ir_slice(ir, scope)

    try:
        provider = LLMProvider(load_llm_config())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    inp = RewriteInput(workspaceId=ws.id, scope=scope, instruction=instruction, irSlice=ir_slice)
    system, user = build_rewrite_messages(inp)

    try:
        raw = provider.complete_json(system=system, user=user)
        _out, proposal = _validate_rewrite_output(raw, workspace_id=ws.id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"RewritePrompt 失败：{e}") from e

    proposal_payload = proposal.model_dump(mode="json")
    patch = proposal_payload.get("patch")
    if not isinstance(patch, dict):
        raise HTTPException(status_code=502, detail="proposal.patch 输出不合法")

    try:
        validation = GraphPatchService.validate(db, ws, patch)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"proposal.patch 校验失败：{e}") from e

    proposal_payload["patch"] = validation.materialized_patch.model_dump(mode="json")
    proposal_payload.setdefault("impactPreview", validation.impact_preview)

    proposal_id = str(proposal_payload.get("id") or _new_id("prop"))
    proposal_payload["id"] = proposal_id
    proposal_payload["workspaceId"] = ws.id
    proposal_payload.setdefault("createdAt", _now_iso())
    proposal_payload.setdefault("scope", scope)
    proposal_payload["status"] = "candidate"
    proposal_payload.setdefault("source", {"type": "ai", "text": instruction})

    proposal_row = (
        db.query(models.Proposal)
        .filter(models.Proposal.workspace_id == ws.id, models.Proposal.id == proposal_id)
        .first()
    )
    if proposal_row is None:
        proposal_row = models.Proposal(workspace_id=ws.id, id=proposal_id)
        db.add(proposal_row)
    proposal_row.title = proposal_payload["title"]
    proposal_row.summary = proposal_payload.get("summary") or ""
    proposal_row.scope = proposal_payload.get("scope") or {}
    proposal_row.patch = proposal_payload["patch"]
    proposal_row.impact_preview = proposal_payload.get("impactPreview") or {}
    proposal_row.status = proposal_payload["status"]
    proposal_row.created_at = datetime.fromisoformat(proposal_payload["createdAt"].replace("Z", "+00:00"))
    proposal_row.source = proposal_payload["source"]
    ws.updated_at = datetime.utcnow()
    db.flush()

    return {"proposalId": proposal_id, "proposal": proposal_payload}
