from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models
from .audit import append_operation
from .link_rules import LINK_RULES, is_link_allowed


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _normalize_scope_status(value: Any) -> Any:
    if value == "dependency":
        return "external_dependency"
    if value == "excluded":
        return None
    return value


def _as_list(value: Any, field_name: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise HTTPException(status_code=400, detail=f"GraphPatch.{field_name} 必须是数组")
    return value


def _as_str_set(value: Any, field_name: str) -> set[str]:
    items = _as_list(value, field_name)
    out: set[str] = set()
    for i in items:
        if not isinstance(i, str) or not i:
            raise HTTPException(status_code=400, detail=f"GraphPatch.{field_name} 必须是 string[]")
        out.add(i)
    return out


def _namespace_id(namespace: str, raw_id: str) -> str:
    if raw_id.startswith(f"{namespace}__"):
        return raw_id
    return f"{namespace}__{raw_id}"


def _remap_node_ids(values: Any, node_id_map: dict[str, str]) -> Any:
    if not isinstance(values, list):
        return values
    return [node_id_map.get(v, v) if isinstance(v, str) else v for v in values]


def namespace_graph_patch_ids(workspace_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(patch, dict):
        return patch

    normalized = copy.deepcopy(patch)
    add_nodes = _as_list(normalized.get("addNodes"), "addNodes")
    add_links = _as_list(normalized.get("addLinks"), "addLinks")
    add_slots = _as_list(normalized.get("addSlots"), "addSlots")
    add_issues = _as_list(normalized.get("addIssues") or normalized.get("createIssues"), "addIssues")

    node_id_map = {
        item["id"]: _namespace_id(workspace_id, item["id"])
        for item in add_nodes
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id")
    }
    link_id_map = {
        item["id"]: _namespace_id(workspace_id, item["id"])
        for item in add_links
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id")
    }
    slot_id_map = {
        item["id"]: _namespace_id(workspace_id, item["id"])
        for item in add_slots
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id")
    }
    issue_id_map = {
        item["id"]: _namespace_id(workspace_id, item["id"])
        for item in add_issues
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id")
    }

    for node in add_nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        if isinstance(node_id, str):
            node["id"] = node_id_map.get(node_id, node_id)
        if "slots" in node:
            node["slots"] = [
                slot_id_map.get(slot_id, slot_id) if isinstance(slot_id, str) else slot_id
                for slot_id in (node.get("slots") or [])
            ]

    for link in add_links:
        if not isinstance(link, dict):
            continue
        link_id = link.get("id")
        source_id = link.get("sourceId")
        target_id = link.get("targetId")
        if isinstance(link_id, str):
            link["id"] = link_id_map.get(link_id, link_id)
        if isinstance(source_id, str):
            link["sourceId"] = node_id_map.get(source_id, source_id)
        if isinstance(target_id, str):
            link["targetId"] = node_id_map.get(target_id, target_id)

    for slot in add_slots:
        if not isinstance(slot, dict):
            continue
        slot_id = slot.get("id")
        owner_node_id = slot.get("ownerNodeId")
        choice_group_id = slot.get("choiceGroupId")
        if isinstance(slot_id, str):
            slot["id"] = slot_id_map.get(slot_id, slot_id)
        if isinstance(owner_node_id, str):
            slot["ownerNodeId"] = node_id_map.get(owner_node_id, owner_node_id)
        if isinstance(choice_group_id, str):
            slot["choiceGroupId"] = _namespace_id(workspace_id, choice_group_id)
        context = slot.get("context")
        if isinstance(context, dict) and isinstance(context.get("relatedNodeIds"), list):
            context = dict(context)
            context["relatedNodeIds"] = _remap_node_ids(context["relatedNodeIds"], node_id_map)
            slot["context"] = context

    for update_slot in _as_list(normalized.get("updateSlots"), "updateSlots"):
        if not isinstance(update_slot, dict):
            continue
        owner_node_id = update_slot.get("ownerNodeId")
        if isinstance(owner_node_id, str):
            update_slot["ownerNodeId"] = node_id_map.get(owner_node_id, owner_node_id)
        context = update_slot.get("context")
        if isinstance(context, dict) and isinstance(context.get("relatedNodeIds"), list):
            context = dict(context)
            context["relatedNodeIds"] = _remap_node_ids(context["relatedNodeIds"], node_id_map)
            update_slot["context"] = context

    for issue in add_issues:
        if not isinstance(issue, dict):
            continue
        issue_id = issue.get("id")
        if isinstance(issue_id, str):
            issue["id"] = issue_id_map.get(issue_id, issue_id)
        if isinstance(issue.get("relatedNodeIds"), list):
            issue["relatedNodeIds"] = _remap_node_ids(issue["relatedNodeIds"], node_id_map)

    for update_issue in _as_list(normalized.get("updateIssues"), "updateIssues"):
        if not isinstance(update_issue, dict):
            continue
        if isinstance(update_issue.get("relatedNodeIds"), list):
            update_issue["relatedNodeIds"] = _remap_node_ids(update_issue["relatedNodeIds"], node_id_map)

    if isinstance(normalized.get("resolveIssueIds"), list):
        normalized["resolveIssueIds"] = [
            issue_id_map.get(issue_id, issue_id) if isinstance(issue_id, str) else issue_id
            for issue_id in normalized["resolveIssueIds"]
        ]

    return normalized


def _validate_workspace_consistency(db: Session, workspace_id: str) -> None:
    node_ids = {
        r[0]
        for r in db.query(models.Node.id).filter(models.Node.workspace_id == workspace_id).all()
    }

    broken: list[str] = []
    for link in db.query(models.Link).filter(models.Link.workspace_id == workspace_id).all():
        if link.source_id not in node_ids:
            broken.append(f"Link `{link.id}` source `{link.source_id}` 不存在")
        if link.target_id not in node_ids:
            broken.append(f"Link `{link.id}` target `{link.target_id}` 不存在")

    for slot in db.query(models.Slot).filter(models.Slot.workspace_id == workspace_id).all():
        if slot.owner_node_id not in node_ids:
            broken.append(f"Slot `{slot.id}` ownerNodeId `{slot.owner_node_id}` 不存在")

    if broken:
        raise HTTPException(status_code=500, detail="IR 校验失败：" + "；".join(broken[:8]))


class GraphPatchService:
    @staticmethod
    def validate(db: Session, ws: models.Workspace, patch: dict[str, Any]) -> None:
        if not isinstance(patch, dict):
            raise HTTPException(status_code=400, detail="GraphPatch 必须是对象")

        patch = namespace_graph_patch_ids(ws.id, patch)

        add_nodes = _as_list(patch.get("addNodes"), "addNodes")
        update_nodes = _as_list(patch.get("updateNodes"), "updateNodes")
        add_links = _as_list(patch.get("addLinks"), "addLinks")
        add_slots = _as_list(patch.get("addSlots"), "addSlots")

        remove_node_ids = _as_str_set(patch.get("removeNodeIds"), "removeNodeIds")
        remove_link_ids = _as_str_set(patch.get("removeLinkIds"), "removeLinkIds")
        _ = _as_str_set(patch.get("removeSlotIds"), "removeSlotIds")
        _ = _as_str_set(patch.get("resolveIssueIds"), "resolveIssueIds")

        add_node_ids: set[str] = set()
        for node in add_nodes:
            if not isinstance(node, dict):
                raise HTTPException(status_code=400, detail="addNodes 中每项必须是对象")
            node_id = node.get("id")
            if not isinstance(node_id, str) or not node_id:
                raise HTTPException(status_code=400, detail="addNodes 中的节点必须包含 id")
            add_node_ids.add(node_id)

        if add_node_ids & remove_node_ids:
            raise HTTPException(status_code=400, detail="GraphPatch 同时 add 与 remove 同一节点")

        existing_nodes = (
            db.query(models.Node.id, models.Node.kind)
            .filter(models.Node.workspace_id == ws.id)
            .all()
        )
        existing_node_ids = {r[0] for r in existing_nodes}
        kind_by_id: dict[str, str] = {r[0]: r[1] for r in existing_nodes}
        for node in add_nodes:
            if isinstance(node, dict) and isinstance(node.get("id"), str) and isinstance(node.get("kind"), str):
                kind_by_id[node["id"]] = node["kind"]

        allowed_node_ids = existing_node_ids | add_node_ids

        for update in update_nodes:
            if not isinstance(update, dict):
                raise HTTPException(status_code=400, detail="updateNodes 中每项必须是对象")
            node_id = update.get("id")
            if not isinstance(node_id, str) or not node_id:
                raise HTTPException(status_code=400, detail="updateNodes 中的节点必须包含 id")
            if node_id not in existing_node_ids:
                raise HTTPException(status_code=404, detail=f"Node `{node_id}` 不存在")

        for link in add_links:
            if not isinstance(link, dict):
                raise HTTPException(status_code=400, detail="addLinks 中每项必须是对象")
            link_id = link.get("id")
            if not isinstance(link_id, str) or not link_id:
                raise HTTPException(status_code=400, detail="addLinks 中的链接必须包含 id")
            if db.get(models.Link, link_id):
                raise HTTPException(status_code=409, detail=f"Link `{link_id}` 已存在")

            source_id = link.get("sourceId")
            target_id = link.get("targetId")
            if not isinstance(source_id, str) or not source_id:
                raise HTTPException(status_code=400, detail=f"Link `{link_id}` sourceId 缺失")
            if not isinstance(target_id, str) or not target_id:
                raise HTTPException(status_code=400, detail=f"Link `{link_id}` targetId 缺失")
            if source_id not in allowed_node_ids:
                raise HTTPException(status_code=400, detail=f"Link `{link_id}` sourceId `{source_id}` 不存在")
            if target_id not in allowed_node_ids:
                raise HTTPException(status_code=400, detail=f"Link `{link_id}` targetId `{target_id}` 不存在")

            link_type = link.get("type")
            if not isinstance(link_type, str) or not link_type:
                raise HTTPException(status_code=400, detail=f"Link `{link_id}` type 缺失")
            if link_type not in LINK_RULES:
                raise HTTPException(status_code=400, detail=f"Link `{link_id}` type `{link_type}` 不在允许集合")

            source_kind = kind_by_id.get(source_id)
            target_kind = kind_by_id.get(target_id)
            if not source_kind or not target_kind:
                raise HTTPException(status_code=400, detail=f"Link `{link_id}` 无法推断节点类型")
            if not is_link_allowed(link_type, source_kind, target_kind):
                raise HTTPException(
                    status_code=400,
                    detail=f"Link `{link_id}` 不合法：{link_type} 不允许 {source_kind} -> {target_kind}",
                )

        for raw_slot in add_slots:
            if not isinstance(raw_slot, dict):
                raise HTTPException(status_code=400, detail="addSlots 中每项必须是对象")
            slot_id = raw_slot.get("id")
            if not isinstance(slot_id, str) or not slot_id:
                raise HTTPException(status_code=400, detail="addSlots 中的 slot 必须包含 id")
            if db.get(models.Slot, slot_id):
                raise HTTPException(status_code=409, detail=f"Slot `{slot_id}` 已存在")
            owner_node_id = raw_slot.get("ownerNodeId")
            if not isinstance(owner_node_id, str) or not owner_node_id:
                raise HTTPException(status_code=400, detail=f"Slot `{slot_id}` ownerNodeId 缺失")
            if owner_node_id not in allowed_node_ids:
                raise HTTPException(status_code=400, detail=f"Slot `{slot_id}` ownerNodeId `{owner_node_id}` 不存在")

        if remove_link_ids:
            existing_links = {
                r[0]
                for r in db.query(models.Link.id)
                .filter(models.Link.workspace_id == ws.id, models.Link.id.in_(list(remove_link_ids)))
                .all()
            }
            missing = sorted(remove_link_ids - existing_links)
            if missing:
                raise HTTPException(status_code=404, detail=f"removeLinkIds 中存在不存在的链接：{missing[:5]}")

    @staticmethod
    def apply(db: Session, ws: models.Workspace, patch: dict[str, Any]) -> None:
        if not isinstance(patch, dict):
            raise HTTPException(status_code=400, detail="GraphPatch 必须是对象")

        patch = namespace_graph_patch_ids(ws.id, patch)

        add_nodes = _as_list(patch.get("addNodes"), "addNodes")
        update_nodes = _as_list(patch.get("updateNodes"), "updateNodes")
        add_links = _as_list(patch.get("addLinks"), "addLinks")
        add_slots = _as_list(patch.get("addSlots"), "addSlots")
        update_slots = _as_list(patch.get("updateSlots"), "updateSlots")
        add_issues = _as_list(patch.get("addIssues") or patch.get("createIssues"), "addIssues")
        update_issues = _as_list(patch.get("updateIssues"), "updateIssues")

        remove_node_ids = _as_str_set(patch.get("removeNodeIds"), "removeNodeIds")
        remove_link_ids = _as_str_set(patch.get("removeLinkIds"), "removeLinkIds")
        remove_slot_ids = _as_str_set(patch.get("removeSlotIds"), "removeSlotIds")
        resolve_issue_ids = _as_str_set(patch.get("resolveIssueIds"), "resolveIssueIds")

        add_node_ids: set[str] = set()
        for node in add_nodes:
            if not isinstance(node, dict):
                raise HTTPException(status_code=400, detail="addNodes 中每项必须是对象")
            node_id = node.get("id")
            if not isinstance(node_id, str) or not node_id:
                raise HTTPException(status_code=400, detail="addNodes 中的节点必须包含 id")
            add_node_ids.add(node_id)

        if add_node_ids & remove_node_ids:
            raise HTTPException(status_code=400, detail="GraphPatch 同时 add 与 remove 同一节点")

        if remove_link_ids:
            db.query(models.Link).filter(
                models.Link.workspace_id == ws.id, models.Link.id.in_(list(remove_link_ids))
            ).delete(synchronize_session=False)

        removed_slot_ids: set[str] = set()
        removed_choice_group_ids: set[str] = set()

        if remove_slot_ids:
            groups_to_remove = (
                db.query(models.ChoiceGroup.id)
                .filter(models.ChoiceGroup.workspace_id == ws.id, models.ChoiceGroup.slot_id.in_(list(remove_slot_ids)))
                .all()
            )
            removed_choice_group_ids |= {r[0] for r in groups_to_remove}
            if removed_choice_group_ids:
                db.query(models.ChoiceGroup).filter(
                    models.ChoiceGroup.workspace_id == ws.id, models.ChoiceGroup.id.in_(list(removed_choice_group_ids))
                ).delete(synchronize_session=False)

            db.query(models.Slot).filter(
                models.Slot.workspace_id == ws.id, models.Slot.id.in_(list(remove_slot_ids))
            ).delete(synchronize_session=False)
            removed_slot_ids |= set(remove_slot_ids)

        if remove_node_ids:
            db.query(models.Link).filter(
                models.Link.workspace_id == ws.id,
                (models.Link.source_id.in_(list(remove_node_ids)) | models.Link.target_id.in_(list(remove_node_ids))),
            ).delete(synchronize_session=False)

            slots_to_remove = (
                db.query(models.Slot.id)
                .filter(models.Slot.workspace_id == ws.id, models.Slot.owner_node_id.in_(list(remove_node_ids)))
                .all()
            )
            removed_slot_ids = {r[0] for r in slots_to_remove}
            if removed_slot_ids:
                groups_to_remove = (
                    db.query(models.ChoiceGroup.id)
                    .filter(models.ChoiceGroup.workspace_id == ws.id, models.ChoiceGroup.slot_id.in_(list(removed_slot_ids)))
                    .all()
                )
                removed_choice_group_ids = {r[0] for r in groups_to_remove}

                db.query(models.ChoiceGroup).filter(
                    models.ChoiceGroup.workspace_id == ws.id, models.ChoiceGroup.id.in_(list(removed_choice_group_ids))
                ).delete(synchronize_session=False)

                db.query(models.Slot).filter(
                    models.Slot.workspace_id == ws.id, models.Slot.id.in_(list(removed_slot_ids))
                ).delete(synchronize_session=False)

            nodes = (
                db.query(models.Node)
                .filter(models.Node.workspace_id == ws.id, models.Node.id.in_(list(remove_node_ids)))
                .all()
            )
            for n in nodes:
                db.delete(n)

            issues = db.query(models.Issue).filter(models.Issue.workspace_id == ws.id).all()
            for issue in issues:
                if not issue.related_node_ids:
                    continue
                new_related = [rid for rid in issue.related_node_ids if rid not in remove_node_ids]
                if new_related != issue.related_node_ids:
                    issue.related_node_ids = new_related

        for node in add_nodes:
            node_id = node.get("id")
            exists = db.get(models.Node, node_id)
            if exists:
                raise HTTPException(status_code=409, detail=f"Node `{node_id}` 已存在")

            base_keys = {"id", "kind", "title", "description", "status", "confidence", "scopeStatus", "source", "slots"}
            extra = {k: v for k, v in node.items() if k not in base_keys}
            scope_status = _normalize_scope_status(node.get("scopeStatus"))
            status = node.get("status") or "needs_confirmation"
            if node.get("scopeStatus") == "excluded":
                status = "excluded"
                scope_status = None
            db.add(
                models.Node(
                    id=node_id,
                    workspace_id=ws.id,
                    kind=node.get("kind", "capability"),
                    title=node.get("title") or node_id,
                    description=node.get("description"),
                    status=status,
                    confidence=node.get("confidence"),
                    scope_status=scope_status,
                    source=node.get("source") or {"type": "user"},
                    slots=node.get("slots"),
                    extra=extra,
                )
            )

        for update in update_nodes:
            if not isinstance(update, dict):
                raise HTTPException(status_code=400, detail="updateNodes 中每项必须是对象")
            node_id = update.get("id")
            if not isinstance(node_id, str) or not node_id:
                raise HTTPException(status_code=400, detail="updateNodes 中的节点必须包含 id")

            node = db.get(models.Node, node_id)
            if not node or node.workspace_id != ws.id:
                raise HTTPException(status_code=404, detail=f"Node `{node_id}` 不存在")

            if "title" in update and update["title"] is not None:
                node.title = update["title"]
            if "description" in update:
                node.description = update["description"]
            if "status" in update and update["status"] is not None:
                node.status = update["status"]
            if "scopeStatus" in update and update["scopeStatus"] is not None:
                if update["scopeStatus"] == "excluded":
                    node.status = "excluded"
                    node.scope_status = None
                else:
                    node.scope_status = _normalize_scope_status(update["scopeStatus"])
            if "confidence" in update:
                node.confidence = update["confidence"]
            if "source" in update and update["source"] is not None:
                node.source = update["source"]

            extra_update = {k: v for k, v in update.items() if k not in {"id", "kind", "title", "description", "status", "scopeStatus", "confidence", "source"}}
            if extra_update:
                merged = dict(node.extra or {})
                merged.update(extra_update)
                node.extra = merged

            node.updated_at = datetime.utcnow()

        existing_nodes = (
            db.query(models.Node.id, models.Node.kind)
            .filter(models.Node.workspace_id == ws.id)
            .all()
        )
        existing_node_ids = {r[0] for r in existing_nodes}
        kind_by_id: dict[str, str] = {r[0]: r[1] for r in existing_nodes}
        for node in add_nodes:
            if isinstance(node, dict) and isinstance(node.get("id"), str) and isinstance(node.get("kind"), str):
                kind_by_id[node["id"]] = node["kind"]

        allowed_link_node_ids = existing_node_ids | add_node_ids

        for link in add_links:
            if not isinstance(link, dict):
                raise HTTPException(status_code=400, detail="addLinks 中每项必须是对象")
            link_id = link.get("id")
            if not isinstance(link_id, str) or not link_id:
                raise HTTPException(status_code=400, detail="addLinks 中的链接必须包含 id")
            exists = db.get(models.Link, link_id)
            if exists:
                raise HTTPException(status_code=409, detail=f"Link `{link_id}` 已存在")

            source_id = link.get("sourceId")
            target_id = link.get("targetId")
            if not isinstance(source_id, str) or not source_id:
                raise HTTPException(status_code=400, detail=f"Link `{link_id}` sourceId 缺失")
            if not isinstance(target_id, str) or not target_id:
                raise HTTPException(status_code=400, detail=f"Link `{link_id}` targetId 缺失")
            if source_id not in allowed_link_node_ids:
                raise HTTPException(status_code=400, detail=f"Link `{link_id}` sourceId `{source_id}` 不存在")
            if target_id not in allowed_link_node_ids:
                raise HTTPException(status_code=400, detail=f"Link `{link_id}` targetId `{target_id}` 不存在")

            link_type = link.get("type")
            if not isinstance(link_type, str) or not link_type:
                raise HTTPException(status_code=400, detail=f"Link `{link_id}` type 缺失")
            if link_type not in LINK_RULES:
                raise HTTPException(status_code=400, detail=f"Link `{link_id}` type `{link_type}` 不在允许集合")

            source_kind = kind_by_id.get(source_id)
            target_kind = kind_by_id.get(target_id)
            if not source_kind or not target_kind:
                raise HTTPException(status_code=400, detail=f"Link `{link_id}` 无法推断节点类型")
            if not is_link_allowed(link_type, source_kind, target_kind):
                raise HTTPException(
                    status_code=400,
                    detail=f"Link `{link_id}` 不合法：{link_type} 不允许 {source_kind} -> {target_kind}",
                )

            db.add(
                models.Link(
                    id=link_id,
                    workspace_id=ws.id,
                    source_id=source_id,
                    target_id=target_id,
                    type=link_type,
                    label=link.get("label"),
                    status=link.get("status", "active"),
                    source=link.get("source", {"type": "ai"}),
                )
            )

        for slot_update in update_slots:
            if not isinstance(slot_update, dict):
                raise HTTPException(status_code=400, detail="updateSlots 中每项必须是对象")
            slot_id = slot_update.get("id")
            if not isinstance(slot_id, str) or not slot_id:
                raise HTTPException(status_code=400, detail="updateSlots 中的 slot 必须包含 id")
            slot = db.get(models.Slot, slot_id)
            if not slot or slot.workspace_id != ws.id:
                raise HTTPException(status_code=404, detail=f"Slot `{slot_id}` 不存在")

            if "ownerProjection" in slot_update and slot_update["ownerProjection"] is not None:
                slot.owner_projection = slot_update["ownerProjection"]
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

        existing_node_ids = {
            r[0] for r in db.query(models.Node.id).filter(models.Node.workspace_id == ws.id).all()
        }
        allowed_slot_owner_ids = existing_node_ids | add_node_ids

        for raw_slot in add_slots:
            if not isinstance(raw_slot, dict):
                raise HTTPException(status_code=400, detail="addSlots 中每项必须是对象")
            slot_id = raw_slot.get("id")
            if not isinstance(slot_id, str) or not slot_id:
                raise HTTPException(status_code=400, detail="addSlots 中的 slot 必须包含 id")
            exists = db.get(models.Slot, slot_id)
            if exists:
                raise HTTPException(status_code=409, detail=f"Slot `{slot_id}` 已存在")

            owner_node_id = raw_slot.get("ownerNodeId")
            if not isinstance(owner_node_id, str) or not owner_node_id:
                raise HTTPException(status_code=400, detail=f"Slot `{slot_id}` ownerNodeId 缺失")
            if owner_node_id not in allowed_slot_owner_ids:
                raise HTTPException(status_code=400, detail=f"Slot `{slot_id}` ownerNodeId `{owner_node_id}` 不存在")

            owner_projection = raw_slot.get("ownerProjection")
            if not owner_projection:
                hints = (raw_slot.get("context") or {}).get("projectionHints") or []
                owner_projection = hints[0] if hints else "goal"

            db.add(
                models.Slot(
                    id=slot_id,
                    workspace_id=ws.id,
                    owner_node_id=owner_node_id,
                    owner_projection=owner_projection,
                    name=raw_slot.get("name") or slot_id,
                    description=raw_slot.get("description"),
                    expected_kinds=raw_slot.get("expectedKinds") or [],
                    arity=raw_slot.get("arity") or "many",
                    status=raw_slot.get("status") or "empty",
                    choice_group_id=raw_slot.get("choiceGroupId"),
                    context=raw_slot.get("context") or {},
                )
            )

        if resolve_issue_ids:
            issues = (
                db.query(models.Issue)
                .filter(models.Issue.workspace_id == ws.id, models.Issue.id.in_(list(resolve_issue_ids)))
                .all()
            )
            for issue in issues:
                issue.status = "resolved"

        for raw in add_issues:
            if not isinstance(raw, dict):
                raise HTTPException(status_code=400, detail="addIssues 中每项必须是对象")
            issue_id = raw.get("id") or _new_id("issue")
            exists = db.get(models.Issue, issue_id)
            if exists:
                raise HTTPException(status_code=409, detail=f"Issue `{issue_id}` 已存在")
            db.add(
                models.Issue(
                    id=issue_id,
                    workspace_id=ws.id,
                    title=raw.get("title") or issue_id,
                    description=raw.get("description") or "",
                    severity=raw.get("severity") or "medium",
                    category=raw.get("category") or "missing",
                    related_node_ids=raw.get("relatedNodeIds") or [],
                    suggested_projection=raw.get("suggestedProjection") or "goal",
                    suggested_action=raw.get("suggestedAction") or "",
                    status=raw.get("status") or "open",
                    source=raw.get("source") or {"type": "system"},
                )
            )

        for raw in update_issues:
            if not isinstance(raw, dict):
                raise HTTPException(status_code=400, detail="updateIssues 中每项必须是对象")
            issue_id = raw.get("id")
            if not isinstance(issue_id, str) or not issue_id:
                raise HTTPException(status_code=400, detail="updateIssues 中的 issue 必须包含 id")
            issue = db.get(models.Issue, issue_id)
            if not issue or issue.workspace_id != ws.id:
                raise HTTPException(status_code=404, detail=f"Issue `{issue_id}` 不存在")

            if "title" in raw and raw["title"] is not None:
                issue.title = raw["title"]
            if "description" in raw:
                issue.description = raw["description"] or ""
            if "severity" in raw and raw["severity"] is not None:
                issue.severity = raw["severity"]
            if "category" in raw and raw["category"] is not None:
                issue.category = raw["category"]
            if "relatedNodeIds" in raw and raw["relatedNodeIds"] is not None:
                issue.related_node_ids = raw["relatedNodeIds"]
            if "suggestedProjection" in raw and raw["suggestedProjection"] is not None:
                issue.suggested_projection = raw["suggestedProjection"]
            if "suggestedAction" in raw and raw["suggestedAction"] is not None:
                issue.suggested_action = raw["suggestedAction"]
            if "status" in raw and raw["status"] is not None:
                issue.status = raw["status"]
            if "source" in raw and raw["source"] is not None:
                issue.source = raw["source"]

        db.flush()
        _validate_workspace_consistency(db, ws.id)
        append_operation(
            ws,
            actionType="apply_patch",
            targetIds=sorted(add_node_ids | remove_node_ids | remove_link_ids),
            actor={"type": "system"},
            summary="应用 GraphPatch",
            details={
                "addNodeIds": sorted(add_node_ids),
                "updateNodeCount": len(update_nodes),
                "removeNodeIds": sorted(remove_node_ids),
                "addLinkCount": len(add_links),
                "removeLinkIds": sorted(remove_link_ids),
                "addSlotCount": len(add_slots),
                "removeSlotIds": sorted(remove_slot_ids),
                "updateSlotCount": len(update_slots),
                "resolveIssueIds": sorted(resolve_issue_ids),
                "addIssueCount": len(add_issues),
                "updateIssueCount": len(update_issues),
                "cascadeRemovedSlotIds": sorted(removed_slot_ids),
                "cascadeRemovedChoiceGroupIds": sorted(removed_choice_group_ids),
            },
        )

