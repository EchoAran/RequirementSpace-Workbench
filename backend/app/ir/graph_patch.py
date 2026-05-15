from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from pydantic import TypeAdapter

from .impact import compute_impact_preview
from .schema import (
    Choice,
    ChoiceGroup,
    ChoicePatch,
    GraphPatch,
    Issue,
    IssueStatus,
    OperationRecord,
    RequirementLink,
    RequirementNode,
    RequirementSlot,
    RequirementSpaceIR,
)
from .validators import validate_graph_patch, validate_ir

NODE_ADAPTER = TypeAdapter(RequirementNode)


@dataclass
class GraphPatchApplyResult:
    patch: GraphPatch
    materialized_patch: GraphPatch
    workspace: RequirementSpaceIR
    id_map: dict[str, str]
    impact_preview: dict[str, object]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GraphPatchService:
    @classmethod
    def validate(cls, db, ws, patch_payload: dict[str, Any] | GraphPatch) -> GraphPatchApplyResult:
        return cls._prepare(db, ws, patch_payload, include_audit=False)

    @classmethod
    def apply(cls, db, ws, patch_payload: dict[str, Any] | GraphPatch) -> GraphPatchApplyResult:
        from .. import crud

        result = cls._prepare(db, ws, patch_payload, include_audit=True)
        crud.replace_workspace_from_ir(db, ws, result.workspace)
        return result

    @classmethod
    def _prepare(
        cls,
        db,
        ws,
        patch_payload: dict[str, Any] | GraphPatch,
        *,
        include_audit: bool,
    ) -> GraphPatchApplyResult:
        from .. import crud

        current_ir = validate_ir(crud.serialize_workspace(ws), status_code=500)
        patch = validate_graph_patch(patch_payload, status_code=400)
        materialized_patch, id_map = cls._materialize_ids(current_ir, patch)
        next_ir = cls._apply_patch(current_ir, materialized_patch)
        impact_preview = compute_impact_preview(current_ir, materialized_patch)
        if include_audit:
            next_ir = cls._append_audit(next_ir, materialized_patch, id_map, impact_preview)
        validated_next_ir = validate_ir(next_ir, status_code=400)
        return GraphPatchApplyResult(
            patch=patch,
            materialized_patch=materialized_patch,
            workspace=validated_next_ir,
            id_map=id_map,
            impact_preview=impact_preview,
        )

    @classmethod
    def _materialize_ids(cls, ir: RequirementSpaceIR, patch: GraphPatch) -> tuple[GraphPatch, dict[str, str]]:
        materialized = patch.model_copy(deep=True)
        id_map: dict[str, str] = {}

        node_ids = set(ir.nodes.keys())
        link_ids = {link.id for link in ir.links}
        slot_ids = set(ir.slots.keys())
        choice_group_ids = set(ir.choiceGroups.keys())
        choice_ids = {choice.id for group in ir.choiceGroups.values() for choice in group.choices}
        issue_ids = set(ir.issues.keys())

        for node in materialized.addNodes:
            actual = cls._allocate_id(node.id, node_ids)
            id_map[node.id] = actual
            node.id = actual
        for link in materialized.addLinks:
            actual = cls._allocate_id(link.id, link_ids)
            id_map[link.id] = actual
            link.id = actual
        for slot in materialized.addSlots:
            actual = cls._allocate_id(slot.id, slot_ids)
            id_map[slot.id] = actual
            slot.id = actual
        for group in materialized.addChoiceGroups:
            actual_group_id = cls._allocate_id(group.id, choice_group_ids)
            id_map[group.id] = actual_group_id
            group.id = actual_group_id
            for choice in group.choices:
                actual_choice_id = cls._allocate_id(choice.id, choice_ids)
                id_map[choice.id] = actual_choice_id
                choice.id = actual_choice_id
        for group in materialized.updateChoiceGroups:
            if not group.choices:
                continue
            for choice in group.choices:
                if choice.id in choice_ids:
                    continue
                actual_choice_id = cls._allocate_id(choice.id, choice_ids)
                id_map[choice.id] = actual_choice_id
                choice.id = actual_choice_id
        for issue in materialized.addIssues:
            actual = cls._allocate_id(issue.id, issue_ids)
            id_map[issue.id] = actual
            issue.id = actual

        cls._remap_patch_references(materialized, id_map)
        return materialized, id_map

    @classmethod
    def _allocate_id(cls, raw_id: str, existing_ids: set[str]) -> str:
        candidate = raw_id
        suffix = 2
        while candidate in existing_ids:
            candidate = f"{raw_id}_{suffix}"
            suffix += 1
        existing_ids.add(candidate)
        return candidate

    @classmethod
    def _remap_patch_references(cls, patch: GraphPatch, id_map: dict[str, str]) -> None:
        def remap(value: str | None) -> str | None:
            if value is None:
                return None
            return id_map.get(value, value)

        for link in patch.addLinks:
            link.sourceId = remap(link.sourceId) or link.sourceId
            link.targetId = remap(link.targetId) or link.targetId
        for link in patch.updateLinks:
            if "sourceId" in link.model_fields_set:
                link.sourceId = remap(link.sourceId)
            if "targetId" in link.model_fields_set:
                link.targetId = remap(link.targetId)

        for slot in patch.addSlots:
            slot.ownerNodeId = remap(slot.ownerNodeId) or slot.ownerNodeId
            slot.context.relatedNodeIds = [remap(node_id) or node_id for node_id in slot.context.relatedNodeIds]
        for slot in patch.updateSlots:
            if "ownerNodeId" in slot.model_fields_set:
                slot.ownerNodeId = remap(slot.ownerNodeId)
            if "context" in slot.model_fields_set and slot.context is not None:
                slot.context.relatedNodeIds = [remap(node_id) or node_id for node_id in slot.context.relatedNodeIds]

        for group in patch.addChoiceGroups:
            group.slotId = remap(group.slotId) or group.slotId
            group.selectedChoiceIds = [remap(choice_id) or choice_id for choice_id in group.selectedChoiceIds]
            for choice in group.choices:
                choice.choiceGroupId = group.id
        for group in patch.updateChoiceGroups:
            if "slotId" in group.model_fields_set:
                group.slotId = remap(group.slotId)
            if "selectedChoiceIds" in group.model_fields_set and group.selectedChoiceIds is not None:
                group.selectedChoiceIds = [remap(choice_id) or choice_id for choice_id in group.selectedChoiceIds]

        for issue in patch.addIssues:
            issue.relatedNodeIds = [remap(node_id) or node_id for node_id in issue.relatedNodeIds]
        for issue in patch.updateIssues:
            if "relatedNodeIds" in issue.model_fields_set and issue.relatedNodeIds is not None:
                issue.relatedNodeIds = [remap(node_id) or node_id for node_id in issue.relatedNodeIds]

        patch.removeNodeIds = [remap(node_id) or node_id for node_id in patch.removeNodeIds]
        patch.removeLinkIds = [remap(link_id) or link_id for link_id in patch.removeLinkIds]
        patch.removeSlotIds = [remap(slot_id) or slot_id for slot_id in patch.removeSlotIds]
        patch.resolveIssueIds = [remap(issue_id) or issue_id for issue_id in patch.resolveIssueIds]

    @classmethod
    def _apply_patch(cls, current_ir: RequirementSpaceIR, patch: GraphPatch) -> RequirementSpaceIR:
        next_ir = RequirementSpaceIR.model_validate(current_ir.model_dump(mode="json"))

        if set(patch.removeNodeIds) & {node.id for node in patch.addNodes}:
            raise HTTPException(status_code=400, detail="GraphPatch 不能同时 add 与 remove 同一节点")

        cls._remove_links(next_ir, set(patch.removeLinkIds))
        cls._remove_slots(next_ir, set(patch.removeSlotIds))
        cls._remove_nodes(next_ir, set(patch.removeNodeIds))

        for node in patch.addNodes:
            if node.id in next_ir.nodes:
                raise HTTPException(status_code=409, detail=f"Node `{node.id}` 已存在")
            next_ir.nodes[node.id] = node

        for update in patch.updateNodes:
            if update.id not in next_ir.nodes:
                raise HTTPException(status_code=404, detail=f"Node `{update.id}` 不存在")
            next_ir.nodes[update.id] = cls._merge_node(next_ir.nodes[update.id], update)

        link_index = {link.id: link for link in next_ir.links}
        for link in patch.addLinks:
            if link.id in link_index:
                raise HTTPException(status_code=409, detail=f"Link `{link.id}` 已存在")
            next_ir.links.append(link)
            link_index[link.id] = link
        for update in patch.updateLinks:
            existing = link_index.get(update.id)
            if not existing:
                raise HTTPException(status_code=404, detail=f"Link `{update.id}` 不存在")
            merged = cls._merge_link(existing, update)
            link_index[update.id] = merged
        next_ir.links = list(link_index.values())

        for slot in patch.addSlots:
            if slot.id in next_ir.slots:
                raise HTTPException(status_code=409, detail=f"Slot `{slot.id}` 已存在")
            next_ir.slots[slot.id] = slot
        for update in patch.updateSlots:
            if update.id not in next_ir.slots:
                raise HTTPException(status_code=404, detail=f"Slot `{update.id}` 不存在")
            next_ir.slots[update.id] = cls._merge_slot(next_ir.slots[update.id], update)

        for group in patch.addChoiceGroups:
            if group.id in next_ir.choiceGroups:
                raise HTTPException(status_code=409, detail=f"ChoiceGroup `{group.id}` 已存在")
            for choice in group.choices:
                choice.choiceGroupId = group.id
            next_ir.choiceGroups[group.id] = group

        for update in patch.updateChoiceGroups:
            existing = next_ir.choiceGroups.get(update.id)
            if not existing:
                raise HTTPException(status_code=404, detail=f"ChoiceGroup `{update.id}` 不存在")
            next_ir.choiceGroups[update.id] = cls._merge_choice_group(existing, update)

        for issue in patch.addIssues:
            if issue.id in next_ir.issues:
                raise HTTPException(status_code=409, detail=f"Issue `{issue.id}` 已存在")
            next_ir.issues[issue.id] = issue
        for update in patch.updateIssues:
            if update.id not in next_ir.issues:
                raise HTTPException(status_code=404, detail=f"Issue `{update.id}` 不存在")
            next_ir.issues[update.id] = cls._merge_issue(next_ir.issues[update.id], update)
        for issue_id in patch.resolveIssueIds:
            if issue_id not in next_ir.issues:
                raise HTTPException(status_code=404, detail=f"Issue `{issue_id}` 不存在")
            next_ir.issues[issue_id].status = IssueStatus.RESOLVED

        return next_ir

    @classmethod
    def _remove_nodes(cls, ir: RequirementSpaceIR, node_ids: set[str]) -> None:
        if not node_ids:
            return

        cls._remove_links(ir, {link.id for link in ir.links if link.sourceId in node_ids or link.targetId in node_ids})
        cls._remove_slots(ir, {slot.id for slot in ir.slots.values() if slot.ownerNodeId in node_ids})

        for node_id in node_ids:
            ir.nodes.pop(node_id, None)

        for slot in ir.slots.values():
            slot.context.relatedNodeIds = [item for item in slot.context.relatedNodeIds if item not in node_ids]
        for issue in ir.issues.values():
            issue.relatedNodeIds = [item for item in issue.relatedNodeIds if item not in node_ids]
        ir.projections.goal.expandedNodeIds = [item for item in ir.projections.goal.expandedNodeIds if item not in node_ids]
        if ir.projections.role.activeActorId in node_ids:
            ir.projections.role.activeActorId = None
        ir.projections.system.highlightedNodeIds = [item for item in ir.projections.system.highlightedNodeIds if item not in node_ids]
        if ir.projections.ui.activeActorId in node_ids:
            ir.projections.ui.activeActorId = None
        if ir.projections.ui.activeScreenId in node_ids:
            ir.projections.ui.activeScreenId = None

    @classmethod
    def _remove_links(cls, ir: RequirementSpaceIR, link_ids: set[str]) -> None:
        if not link_ids:
            return
        ir.links = [link for link in ir.links if link.id not in link_ids]

    @classmethod
    def _remove_slots(cls, ir: RequirementSpaceIR, slot_ids: set[str]) -> None:
        if not slot_ids:
            return

        group_ids = {group.id for group in ir.choiceGroups.values() if group.slotId in slot_ids}
        for group_id in group_ids:
            ir.choiceGroups.pop(group_id, None)

        for slot_id in slot_ids:
            ir.slots.pop(slot_id, None)

    @classmethod
    def _merge_node(cls, existing: RequirementNode, update) -> RequirementNode:
        payload = existing.model_dump(mode="json")
        for field_name in update.model_fields_set:
            if field_name == "id":
                continue
            payload[field_name] = getattr(update, field_name)
        return NODE_ADAPTER.validate_python(payload)

    @classmethod
    def _merge_link(cls, existing: RequirementLink, update) -> RequirementLink:
        payload = existing.model_dump(mode="json")
        for field_name in update.model_fields_set:
            if field_name == "id":
                continue
            payload[field_name] = getattr(update, field_name)
        return RequirementLink.model_validate(payload)

    @classmethod
    def _merge_slot(cls, existing: RequirementSlot, update) -> RequirementSlot:
        payload = existing.model_dump(mode="json")
        for field_name in update.model_fields_set:
            if field_name == "id":
                continue
            value = getattr(update, field_name)
            if field_name == "context" and value is not None:
                payload[field_name] = value.model_dump(mode="json")
            else:
                payload[field_name] = value
        return RequirementSlot.model_validate(payload)

    @classmethod
    def _merge_choice_group(cls, existing: ChoiceGroup, update) -> ChoiceGroup:
        payload = existing.model_dump(mode="json")
        for field_name in update.model_fields_set:
            if field_name in {"id", "choices"}:
                continue
            payload[field_name] = getattr(update, field_name)

        choice_map = {choice["id"]: choice for choice in payload["choices"]}
        if "choices" in update.model_fields_set and update.choices is not None:
            for choice_update in update.choices:
                if choice_update.id in choice_map:
                    choice_map[choice_update.id] = cls._merge_choice(choice_map[choice_update.id], choice_update)
                else:
                    choice_map[choice_update.id] = cls._new_choice(payload["id"], choice_update)
        payload["choices"] = list(choice_map.values())
        return ChoiceGroup.model_validate(payload)

    @classmethod
    def _merge_choice(cls, existing_payload: dict[str, Any], update: ChoicePatch) -> dict[str, Any]:
        payload = dict(existing_payload)
        for field_name in update.model_fields_set:
            if field_name == "id":
                continue
            value = getattr(update, field_name)
            if field_name == "patch":
                payload[field_name] = value.model_dump(mode="json") if value is not None else GraphPatch().model_dump(mode="json")
            elif field_name == "impactPreview":
                payload[field_name] = value.model_dump(mode="json") if value is not None else {
                    "affectedGoals": [],
                    "affectedActors": [],
                    "affectedFlows": [],
                    "affectedObjects": [],
                    "affectedScreens": [],
                }
            else:
                payload[field_name] = value
        return Choice.model_validate(payload).model_dump(mode="json")

    @classmethod
    def _new_choice(cls, choice_group_id: str, update: ChoicePatch) -> dict[str, Any]:
        if "title" not in update.model_fields_set or not update.title:
            raise HTTPException(status_code=400, detail=f"新增 Choice `{update.id}` 必须提供 title")
        return Choice.model_validate(
            {
                "id": update.id,
                "choiceGroupId": choice_group_id,
                "title": update.title,
                "rationale": update.rationale or "",
                "patch": update.patch.model_dump(mode="json") if update.patch else GraphPatch().model_dump(mode="json"),
                "impactPreview": (
                    update.impactPreview.model_dump(mode="json")
                    if update.impactPreview
                    else {
                        "affectedGoals": [],
                        "affectedActors": [],
                        "affectedFlows": [],
                        "affectedObjects": [],
                        "affectedScreens": [],
                    }
                ),
                "status": update.status.value if update.status else "candidate",
            }
        ).model_dump(mode="json")

    @classmethod
    def _merge_issue(cls, existing: Issue, update) -> Issue:
        payload = existing.model_dump(mode="json")
        for field_name in update.model_fields_set:
            if field_name == "id":
                continue
            value = getattr(update, field_name)
            if field_name == "source" and value is not None:
                payload[field_name] = value.model_dump(mode="json")
            else:
                payload[field_name] = value
        return Issue.model_validate(payload)

    @classmethod
    def _append_audit(
        cls,
        ir: RequirementSpaceIR,
        patch: GraphPatch,
        id_map: dict[str, str],
        impact_preview: dict[str, object],
    ) -> RequirementSpaceIR:
        next_ir = RequirementSpaceIR.model_validate(ir.model_dump(mode="json"))
        next_ir.audit.updatedAt = _now_iso()
        historical_target_ids = sorted(
            set(patch.removeNodeIds)
            | set(patch.removeLinkIds)
            | set(patch.removeSlotIds)
        )
        next_ir.audit.operationLog.append(
            OperationRecord.model_validate(
                {
                "id": f"op_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
                "timestamp": _now_iso(),
                "actionType": "apply_graph_patch",
                "targetIds": sorted(
                    {node.id for node in patch.addNodes}
                    | {node.id for node in patch.updateNodes}
                    | set(patch.removeNodeIds)
                    | {link.id for link in patch.addLinks}
                    | {link.id for link in patch.updateLinks}
                    | set(patch.removeLinkIds)
                    | {slot.id for slot in patch.addSlots}
                    | {slot.id for slot in patch.updateSlots}
                    | set(patch.removeSlotIds)
                    | {group.id for group in patch.addChoiceGroups}
                    | {group.id for group in patch.updateChoiceGroups}
                    | {issue.id for issue in patch.addIssues}
                    | {issue.id for issue in patch.updateIssues}
                    | set(patch.resolveIssueIds)
                ),
                "actor": {"type": "system"},
                "summary": "应用 GraphPatch",
                "details": {
                    "idMap": id_map,
                    "impactPreview": impact_preview,
                    "historicalTargetIds": historical_target_ids,
                },
                }
            )
        )
        return next_ir
