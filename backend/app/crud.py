from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from . import models
from .ir.diagnostics import run_deterministic_diagnosis
from .ir.schema import (
    AuditInfo,
    ChoiceGroup,
    ChoiceStatus,
    GraphPatch,
    Issue,
    IssueCategory,
    IssueStatus,
    Meta,
    ProjectionState,
    Proposal,
    ProposalStatus,
    RequirementLink,
    RequirementNode,
    RequirementSlot,
    RequirementSpaceIR,
    SelectionMode,
)
from .ir.validators import validate_graph_patch, validate_ir

NODE_ADAPTER = TypeAdapter(RequirementNode)
NODE_BASE_FIELDS = {"id", "kind", "title", "description", "status", "confidence", "scopeStatus", "source", "tags"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def get_workspace_or_404(db: Session, workspace_id: str) -> models.Workspace:
    ws = db.get(models.Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace `{workspace_id}` 不存在")
    return ws


def upsert_workspace_from_ir(db: Session, ir_payload: dict[str, Any] | RequirementSpaceIR) -> models.Workspace:
    ir = validate_ir(ir_payload, status_code=400)
    ws = db.get(models.Workspace, ir.id)
    if not ws:
        ws = models.Workspace(id=ir.id, name=ir.name, idea=ir.idea)
        db.add(ws)
        db.flush()
    replace_workspace_from_ir(db, ws, ir)
    return ws


def replace_workspace_from_ir(
    db: Session, ws: models.Workspace, ir_payload: dict[str, Any] | RequirementSpaceIR
) -> models.Workspace:
    ir = validate_ir(ir_payload, status_code=400)

    ws.name = ir.name
    ws.idea = ir.idea
    ws.meta = ir.meta.model_dump(mode="json")
    ws.projections = ir.projections.model_dump(mode="json")
    ws.audit = ir.audit.model_dump(mode="json")
    ws.updated_at = datetime.utcnow()

    db.query(models.Proposal).filter(models.Proposal.workspace_id == ws.id).delete(synchronize_session=False)
    db.query(models.Link).filter(models.Link.workspace_id == ws.id).delete(synchronize_session=False)
    db.query(models.Choice).filter(models.Choice.workspace_id == ws.id).delete(synchronize_session=False)
    db.query(models.ChoiceGroup).filter(models.ChoiceGroup.workspace_id == ws.id).delete(synchronize_session=False)
    db.query(models.Slot).filter(models.Slot.workspace_id == ws.id).delete(synchronize_session=False)
    db.query(models.Issue).filter(models.Issue.workspace_id == ws.id).delete(synchronize_session=False)
    db.query(models.Node).filter(models.Node.workspace_id == ws.id).delete(synchronize_session=False)

    db.add_all([_node_row_from_model(ws.id, node) for node in ir.nodes.values()])
    db.add_all([_link_row_from_model(ws.id, link) for link in ir.links])
    db.add_all([_slot_row_from_model(ws.id, slot) for slot in ir.slots.values()])

    group_rows: list[models.ChoiceGroup] = []
    choice_rows: list[models.Choice] = []
    for group in ir.choiceGroups.values():
        group_rows.append(_choice_group_row_from_model(ws.id, group))
        choice_rows.extend(_choice_rows_from_group(ws.id, group))
    db.add_all(group_rows)
    db.add_all(choice_rows)
    db.add_all([_issue_row_from_model(ws.id, issue) for issue in ir.issues.values()])
    db.add_all([_proposal_row_from_model(ws.id, proposal) for proposal in ir.proposals.values()])
    db.flush()
    return ws


def serialize_workspace(ws: models.Workspace) -> dict[str, Any]:
    payload = RequirementSpaceIR(
        id=ws.id,
        name=ws.name,
        idea=ws.idea,
        meta=Meta.model_validate(ws.meta or {}),
        nodes={node.id: _node_model_from_row(node) for node in sorted(ws.nodes, key=lambda item: item.row_id)},
        links=[_link_model_from_row(link) for link in sorted(ws.links, key=lambda item: item.row_id)],
        slots={slot.id: _slot_model_from_row(slot) for slot in sorted(ws.slots, key=lambda item: item.row_id)},
        choiceGroups={
            group.id: _choice_group_model_from_row(group)
            for group in sorted(ws.choice_groups, key=lambda item: item.row_id)
        },
        proposals={
            proposal.id: _proposal_model_from_row(proposal)
            for proposal in sorted(ws.proposals, key=lambda item: item.row_id)
        },
        issues={issue.id: _issue_model_from_row(issue) for issue in sorted(ws.issues, key=lambda item: item.row_id)},
        projections=ProjectionState.model_validate(ws.projections or {}),
        audit=AuditInfo.model_validate(ws.audit or {}),
    )
    return validate_ir(payload, status_code=500).model_dump(mode="json")


def update_node(db: Session, ws: models.Workspace, node_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    return apply_graph_patch(db, ws, {"updateNodes": [{"id": node_id, **updates}]})


def move_scope(db: Session, ws: models.Workspace, node_id: str, scope_status: str) -> dict[str, Any]:
    return update_node(db, ws, node_id, {"scopeStatus": scope_status})


def update_issue_status(db: Session, ws: models.Workspace, issue_id: str, status: str) -> dict[str, Any]:
    return apply_graph_patch(db, ws, {"updateIssues": [{"id": issue_id, "status": status}]})


def update_issue(db: Session, ws: models.Workspace, issue_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    return apply_graph_patch(db, ws, {"updateIssues": [{"id": issue_id, **updates}]})


def update_choice(db: Session, ws: models.Workspace, choice_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    ir = validate_ir(serialize_workspace(ws), status_code=500)
    group = _find_choice_group_by_choice_id(ir, choice_id)
    return apply_graph_patch(db, ws, {"updateChoiceGroups": [{"id": group.id, "choices": [{"id": choice_id, **updates}]}]})


def apply_graph_patch(db: Session, ws: models.Workspace, patch_payload: dict[str, Any] | GraphPatch) -> dict[str, Any]:
    from .ir.graph_patch import GraphPatchService

    result = GraphPatchService.apply(db, ws, patch_payload)
    return {
        "workspace": result.workspace.model_dump(mode="json"),
        "idMap": result.id_map,
        "impactPreview": result.impact_preview,
    }


def run_diagnosis(db: Session, ws: models.Workspace, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    ir = validate_ir(serialize_workspace(ws), status_code=500)
    existing_keys = {
        (
            issue.category.value,
            tuple(sorted(issue.relatedNodeIds)),
            issue.suggestedProjection.value,
            issue.title.strip(),
        )
        for issue in ir.issues.values()
        if issue.status == IssueStatus.OPEN
    }

    add_issues: list[dict[str, Any]] = []
    raw_issue_ids: list[str] = []
    for diagnostic in run_deterministic_diagnosis(ir):
        if not _diagnostic_matches_scope(ir, diagnostic.related_node_ids, scope):
            continue
        key = (
            diagnostic.category.value,
            tuple(sorted(diagnostic.related_node_ids)),
            diagnostic.suggested_projection.value,
            diagnostic.title.strip(),
        )
        if key in existing_keys:
            continue
        raw_issue_id = _new_id("gap")
        raw_issue_ids.append(raw_issue_id)
        add_issues.append({"id": raw_issue_id, **diagnostic.as_payload()})
        existing_keys.add(key)

    if not add_issues:
        return {"createdIssueIds": [], "workspace": ir.model_dump(mode="json"), "idMap": {}}

    result = apply_graph_patch(db, ws, {"addIssues": add_issues})
    return {
        "createdIssueIds": [result["idMap"].get(raw_id, raw_id) for raw_id in raw_issue_ids],
        "workspace": result["workspace"],
        "idMap": result["idMap"],
    }


def create_issue(db: Session, ws: models.Workspace, payload: dict[str, Any]) -> dict[str, Any]:
    raw_issue_id = str(payload.get("id") or _new_id("issue"))
    result = apply_graph_patch(db, ws, {"addIssues": [{"id": raw_issue_id, **payload}]})
    return {
        "issueId": result["idMap"].get(raw_issue_id, raw_issue_id),
        "workspace": result["workspace"],
        "idMap": result["idMap"],
    }


def create_slot_for_issue(db: Session, ws: models.Workspace, issue_id: str) -> dict[str, Any]:
    ir = validate_ir(serialize_workspace(ws), status_code=500)
    issue = ir.issues.get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail=f"Issue `{issue_id}` 不存在")

    hint = f"issue:{issue.id}"
    for slot in ir.slots.values():
        if hint in slot.context.promptHints:
            return {"slotId": slot.id, "workspace": ir.model_dump(mode="json"), "idMap": {}}

    owner_node_id = issue.relatedNodeIds[0] if issue.relatedNodeIds else next(iter(ir.nodes.keys()), None)
    if not owner_node_id:
        raise HTTPException(status_code=400, detail="当前工作台没有可关联节点")

    raw_slot_id = _new_id("slot")
    result = apply_graph_patch(
        db,
        ws,
        {
            "addSlots": [
                {
                    "id": raw_slot_id,
                    "ownerNodeId": owner_node_id,
                    "ownerProjection": issue.suggestedProjection,
                    "name": f"{issue.title} - 待补充",
                    "description": issue.description,
                    "expectedKinds": _expected_kinds_for_issue(issue.category),
                    "arity": "many",
                    "status": "empty",
                    "context": {
                        "projectionHints": [issue.suggestedProjection],
                        "relatedNodeIds": issue.relatedNodeIds,
                        "promptHints": [hint],
                    },
                }
            ]
        },
    )
    return {
        "slotId": result["idMap"].get(raw_slot_id, raw_slot_id),
        "workspace": result["workspace"],
        "idMap": result["idMap"],
    }


def add_choice_to_group(db: Session, ws: models.Workspace, choice_group_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    ir = validate_ir(serialize_workspace(ws), status_code=500)
    if choice_group_id not in ir.choiceGroups:
        raise HTTPException(status_code=404, detail=f"ChoiceGroup `{choice_group_id}` 不存在")

    raw_choice_id = str(payload.get("id") or _new_id("cand"))
    result = apply_graph_patch(
        db,
        ws,
        {
            "updateChoiceGroups": [
                {
                    "id": choice_group_id,
                    "choices": [
                        {
                            "id": raw_choice_id,
                            "title": payload["title"],
                            "rationale": payload.get("rationale"),
                            "patch": payload.get("patch"),
                            "impactPreview": payload.get("impactPreview"),
                            "status": payload.get("status"),
                        }
                    ],
                }
            ]
        },
    )
    return {
        "choiceId": result["idMap"].get(raw_choice_id, raw_choice_id),
        "workspace": result["workspace"],
        "idMap": result["idMap"],
    }


def accept_choice(db: Session, ws: models.Workspace, choice_id: str) -> dict[str, Any]:
    ir = validate_ir(serialize_workspace(ws), status_code=500)
    group = _find_choice_group_by_choice_id(ir, choice_id)
    choice = next(item for item in group.choices if item.id == choice_id)
    slot = ir.slots[group.slotId]

    group_choice_updates = []
    for item in group.choices:
        if item.id == choice_id:
            next_status = ChoiceStatus.SELECTED
        elif item.status == ChoiceStatus.CANDIDATE:
            next_status = ChoiceStatus.REJECTED
        else:
            next_status = item.status
        group_choice_updates.append({"id": item.id, "status": next_status.value})

    base_patch = choice.patch.model_dump(mode="json")
    meta_patch = {
        "updateChoiceGroups": [
            {
                "id": group.id,
                "selectedChoiceIds": [choice.id],
                "status": "selected",
                "choices": group_choice_updates,
            }
        ],
        "updateSlots": [{"id": slot.id, "status": "filled"}],
        "resolveIssueIds": sorted(set(base_patch.get("resolveIssueIds") or []) | set(choice.impactPreview.resolvedIssues or [])),
    }
    return apply_graph_patch(db, ws, merge_graph_patches(base_patch, meta_patch))


def reject_choice(db: Session, ws: models.Workspace, choice_id: str) -> dict[str, Any]:
    ir = validate_ir(serialize_workspace(ws), status_code=500)
    group = _find_choice_group_by_choice_id(ir, choice_id)
    remaining = [item for item in group.choices if item.id != choice_id and item.status == ChoiceStatus.CANDIDATE]
    update_group: dict[str, Any] = {
        "id": group.id,
        "choices": [{"id": choice_id, "status": ChoiceStatus.REJECTED.value}],
    }
    if not remaining:
        update_group["status"] = "dismissed"
    return apply_graph_patch(db, ws, {"updateChoiceGroups": [update_group]})


def list_proposals(db: Session, ws: models.Workspace) -> list[dict[str, Any]]:
    rows = (
        db.query(models.Proposal)
        .filter(models.Proposal.workspace_id == ws.id)
        .order_by(models.Proposal.created_at.desc())
        .all()
    )
    return [_proposal_model_from_row(row).model_dump(mode="json") for row in rows]


def get_proposal_or_404(db: Session, workspace_id: str, proposal_id: str) -> models.Proposal:
    proposal = (
        db.query(models.Proposal)
        .filter(models.Proposal.workspace_id == workspace_id, models.Proposal.id == proposal_id)
        .first()
    )
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal `{proposal_id}` 不存在")
    return proposal


def accept_proposal(db: Session, ws: models.Workspace, proposal_id: str) -> dict[str, Any]:
    proposal = get_proposal_or_404(db, ws.id, proposal_id)
    if proposal.status == ProposalStatus.REJECTED.value:
        raise HTTPException(status_code=400, detail="已拒绝的 Proposal 不能直接采纳")

    apply_graph_patch(db, ws, proposal.patch or {})
    proposal = get_proposal_or_404(db, ws.id, proposal_id)
    proposal.status = ProposalStatus.ACCEPTED.value
    ws.updated_at = datetime.utcnow()
    db.flush()
    db.refresh(ws)
    return {"proposalId": proposal_id, "workspace": serialize_workspace(ws)}


def reject_proposal(db: Session, ws: models.Workspace, proposal_id: str) -> dict[str, Any]:
    proposal = get_proposal_or_404(db, ws.id, proposal_id)
    proposal.status = ProposalStatus.REJECTED.value
    ws.updated_at = datetime.utcnow()
    db.flush()
    db.refresh(ws)
    return {"proposalId": proposal_id, "workspace": serialize_workspace(ws)}


def convert_proposal_to_choice(db: Session, ws: models.Workspace, proposal_id: str) -> dict[str, Any]:
    proposal_row = get_proposal_or_404(db, ws.id, proposal_id)
    proposal = _proposal_model_from_row(proposal_row)
    ir = validate_ir(serialize_workspace(ws), status_code=500)

    slot_id = _resolve_slot_id_for_proposal(ir, proposal)
    if not slot_id:
        raise HTTPException(status_code=400, detail="当前 Proposal 无法定位到目标 Slot，不能转换为 Choice")
    if slot_id not in ir.slots:
        raise HTTPException(status_code=404, detail=f"Proposal 目标 Slot `{slot_id}` 不存在")

    group = _find_choice_group_by_slot_id(ir, slot_id)
    patch_payload: dict[str, Any] = {"updateSlots": [{"id": slot_id, "status": "candidate_ready"}]}
    raw_choice_id = _new_id("choice")

    choice_payload = {
        "id": raw_choice_id,
        "title": proposal.title,
        "rationale": proposal.summary,
        "patch": proposal.patch.model_dump(mode="json"),
        "impactPreview": proposal.impactPreview.model_dump(mode="json"),
        "status": "candidate",
    }

    if group is None:
        raw_group_id = _new_id("cg")
        patch_payload["addChoiceGroups"] = [
            {
                "id": raw_group_id,
                "slotId": slot_id,
                "selectionMode": SelectionMode.SINGLE.value,
                "status": "open",
                "selectedChoiceIds": [],
                "choices": [choice_payload],
            }
        ]
    else:
        patch_payload["updateChoiceGroups"] = [{"id": group.id, "status": "open", "choices": [choice_payload]}]

    result = apply_graph_patch(db, ws, patch_payload)
    proposal_row = get_proposal_or_404(db, ws.id, proposal_id)
    proposal_row.status = ProposalStatus.ARCHIVED.value
    ws.updated_at = datetime.utcnow()
    db.flush()
    db.refresh(ws)
    payload = {"proposalId": proposal_id, "choiceId": result["idMap"].get(raw_choice_id, raw_choice_id), "workspace": serialize_workspace(ws)}
    if "addChoiceGroups" in patch_payload:
        raw_group_id = patch_payload["addChoiceGroups"][0]["id"]
        payload["choiceGroupId"] = result["idMap"].get(raw_group_id, raw_group_id)
    else:
        payload["choiceGroupId"] = group.id
    return payload


def merge_graph_patches(*patches: dict[str, Any]) -> dict[str, Any]:
    merged = GraphPatch().model_dump(mode="json")
    for patch_payload in patches:
        patch = validate_graph_patch(patch_payload, status_code=400).model_dump(mode="json")
        for key, value in patch.items():
            if isinstance(value, list):
                merged[key].extend(value)
    return merged


def _expected_kinds_for_issue(category: IssueCategory) -> list[str]:
    if category in {IssueCategory.FLOW_GAP, IssueCategory.RULE_GAP}:
        return ["flow_step", "rule", "state_transition"]
    if category == IssueCategory.DATA_GAP:
        return ["business_object", "field", "state_machine", "state_transition"]
    if category == IssueCategory.UI_GAP:
        return ["screen", "ui_component"]
    return ["task", "flow_step", "rule", "ui_component"]


def _find_choice_group_by_choice_id(ir: RequirementSpaceIR, choice_id: str) -> ChoiceGroup:
    for group in ir.choiceGroups.values():
        if any(choice.id == choice_id for choice in group.choices):
            return group
    raise HTTPException(status_code=404, detail=f"Choice `{choice_id}` 不存在")


def _find_choice_group_by_slot_id(ir: RequirementSpaceIR, slot_id: str) -> ChoiceGroup | None:
    for group in ir.choiceGroups.values():
        if group.slotId == slot_id:
            return group
    return None


def _resolve_slot_id_for_proposal(ir: RequirementSpaceIR, proposal: Proposal) -> str | None:
    scope = proposal.scope or {}
    slot_id = scope.get("slotId")
    if isinstance(slot_id, str) and slot_id:
        return slot_id
    choice_group_id = scope.get("choiceGroupId")
    if isinstance(choice_group_id, str) and choice_group_id and choice_group_id in ir.choiceGroups:
        return ir.choiceGroups[choice_group_id].slotId
    return None


def _diagnostic_matches_scope(ir: RequirementSpaceIR, related_node_ids: list[str], scope: dict[str, Any] | None) -> bool:
    if not scope:
        return True

    node_id = scope.get("nodeId")
    if node_id and node_id not in related_node_ids:
        return False

    projection = scope.get("projection")
    if not projection or not related_node_ids:
        return True

    allowed_kinds = {
        "goal": {"goal", "capability", "task"},
        "role": {"actor", "task"},
        "system": {"flow", "flow_step", "rule", "state_transition"},
        "data": {"business_object", "field", "state_machine", "object_state", "state_transition"},
        "ui": {"screen", "ui_component"},
    }.get(str(projection), set())
    return any(node_id in ir.nodes and ir.nodes[node_id].kind.value in allowed_kinds for node_id in related_node_ids)


def _node_row_from_model(workspace_id: str, node: RequirementNode) -> models.Node:
    dumped = node.model_dump(mode="json")
    return models.Node(
        workspace_id=workspace_id,
        id=node.id,
        kind=node.kind.value,
        title=node.title,
        description=node.description,
        status=node.status.value,
        confidence=node.confidence,
        scope_status=node.scopeStatus.value if node.scopeStatus else None,
        source=node.source.model_dump(mode="json"),
        attributes={key: value for key, value in dumped.items() if key not in NODE_BASE_FIELDS},
    )


def _link_row_from_model(workspace_id: str, link: RequirementLink) -> models.Link:
    return models.Link(
        workspace_id=workspace_id,
        id=link.id,
        source_id=link.sourceId,
        target_id=link.targetId,
        type=link.type.value,
        label=link.label,
        status=link.status.value,
        source=link.source.model_dump(mode="json"),
    )


def _slot_row_from_model(workspace_id: str, slot: RequirementSlot) -> models.Slot:
    return models.Slot(
        workspace_id=workspace_id,
        id=slot.id,
        owner_node_id=slot.ownerNodeId,
        owner_projection=slot.ownerProjection.value,
        name=slot.name,
        description=slot.description,
        expected_kinds=[kind.value for kind in slot.expectedKinds],
        arity=slot.arity.value,
        status=slot.status.value,
        context=slot.context.model_dump(mode="json"),
    )


def _choice_group_row_from_model(workspace_id: str, group: ChoiceGroup) -> models.ChoiceGroup:
    return models.ChoiceGroup(
        workspace_id=workspace_id,
        id=group.id,
        slot_id=group.slotId,
        selected_choice_ids=group.selectedChoiceIds,
        selection_mode=group.selectionMode.value,
        status=group.status.value,
    )


def _choice_rows_from_group(workspace_id: str, group: ChoiceGroup) -> list[models.Choice]:
    return [
        models.Choice(
            workspace_id=workspace_id,
            id=choice.id,
            choice_group_id=group.id,
            title=choice.title,
            rationale=choice.rationale,
            patch=choice.patch.model_dump(mode="json"),
            impact_preview=choice.impactPreview.model_dump(mode="json"),
            status=choice.status.value,
        )
        for choice in group.choices
    ]


def _issue_row_from_model(workspace_id: str, issue: Issue) -> models.Issue:
    return models.Issue(
        workspace_id=workspace_id,
        id=issue.id,
        title=issue.title,
        description=issue.description,
        severity=issue.severity.value,
        category=issue.category.value,
        related_node_ids=issue.relatedNodeIds,
        suggested_projection=issue.suggestedProjection.value,
        suggested_action=issue.suggestedAction,
        status=issue.status.value,
        source=issue.source.model_dump(mode="json"),
    )


def _proposal_row_from_model(workspace_id: str, proposal: Proposal) -> models.Proposal:
    created_at = datetime.fromisoformat(proposal.createdAt.replace("Z", "+00:00"))
    return models.Proposal(
        workspace_id=workspace_id,
        id=proposal.id,
        title=proposal.title,
        summary=proposal.summary,
        scope=proposal.scope,
        patch=proposal.patch.model_dump(mode="json"),
        impact_preview=proposal.impactPreview.model_dump(mode="json"),
        status=proposal.status.value,
        created_at=created_at,
        source=proposal.source.model_dump(mode="json"),
    )


def _node_model_from_row(row: models.Node) -> RequirementNode:
    return NODE_ADAPTER.validate_python(
        {
            "id": row.id,
            "kind": row.kind,
            "title": row.title,
            "description": row.description or "",
            "status": row.status,
            "confidence": row.confidence,
            "scopeStatus": row.scope_status,
            "source": row.source or {"type": "system"},
            **(row.attributes or {}),
        }
    )


def _link_model_from_row(row: models.Link) -> RequirementLink:
    return RequirementLink.model_validate(
        {
            "id": row.id,
            "sourceId": row.source_id,
            "targetId": row.target_id,
            "type": row.type,
            "label": row.label,
            "status": row.status,
            "source": row.source or {"type": "system"},
        }
    )


def _slot_model_from_row(row: models.Slot) -> RequirementSlot:
    return RequirementSlot.model_validate(
        {
            "id": row.id,
            "ownerNodeId": row.owner_node_id,
            "ownerProjection": row.owner_projection,
            "name": row.name,
            "description": row.description or "",
            "expectedKinds": row.expected_kinds or [],
            "arity": row.arity,
            "status": row.status,
            "context": row.context or {},
        }
    )


def _choice_group_model_from_row(row: models.ChoiceGroup) -> ChoiceGroup:
    return ChoiceGroup.model_validate(
        {
            "id": row.id,
            "slotId": row.slot_id,
            "choices": [
                {
                    "id": choice.id,
                    "choiceGroupId": row.id,
                    "title": choice.title,
                    "rationale": choice.rationale or "",
                    "patch": choice.patch or {},
                    "impactPreview": choice.impact_preview or {},
                    "status": choice.status,
                }
                for choice in sorted(row.choices, key=lambda item: item.row_id)
            ],
            "selectedChoiceIds": row.selected_choice_ids or [],
            "selectionMode": row.selection_mode,
            "status": row.status,
        }
    )


def _issue_model_from_row(row: models.Issue) -> Issue:
    return Issue.model_validate(
        {
            "id": row.id,
            "title": row.title,
            "description": row.description or "",
            "severity": row.severity,
            "category": row.category,
            "relatedNodeIds": row.related_node_ids or [],
            "suggestedProjection": row.suggested_projection,
            "suggestedAction": row.suggested_action or "",
            "status": row.status,
            "source": row.source or {"type": "system"},
        }
    )


def _proposal_model_from_row(row: models.Proposal) -> Proposal:
    return Proposal.model_validate(
        {
            "id": row.id,
            "workspaceId": row.workspace_id,
            "title": row.title,
            "summary": row.summary or "",
            "scope": row.scope or {},
            "patch": row.patch or {},
            "impactPreview": row.impact_preview or {},
            "status": row.status,
            "createdAt": row.created_at.isoformat(),
            "source": row.source or {"type": "system"},
        }
    )
