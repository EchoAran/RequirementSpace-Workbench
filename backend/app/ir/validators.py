from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .schema import RequirementSpaceIR


def _require_keys(kind: str, item_id: str, payload: dict[str, Any], required_keys: list[str]) -> None:
    missing = [key for key in required_keys if payload.get(key) in (None, "")]
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"IR 校验失败：{kind} `{item_id}` 缺少必要字段 {', '.join(missing)}",
        )


def validate_ir(payload: dict[str, Any]) -> RequirementSpaceIR:
    ir = RequirementSpaceIR.model_validate(payload)

    node_ids = set(ir.nodes.keys())

    for node_id, node in ir.nodes.items():
        _require_keys("Node", node_id, node, ["id", "kind", "title", "status"])
        if node.get("id") != node_id:
            raise HTTPException(status_code=500, detail=f"IR 校验失败：Node key `{node_id}` 与 node.id 不一致")

    for link in ir.links:
        src = link.get("sourceId")
        tgt = link.get("targetId")
        if src and src not in node_ids:
            raise HTTPException(status_code=500, detail=f"IR 校验失败：Link.sourceId `{src}` 不存在")
        if tgt and tgt not in node_ids:
            raise HTTPException(status_code=500, detail=f"IR 校验失败：Link.targetId `{tgt}` 不存在")

    for slot_id, slot in ir.slots.items():
        _require_keys("Slot", slot_id, slot, ["id", "ownerNodeId", "ownerProjection", "name", "arity", "status"])
        if slot.get("id") != slot_id:
            raise HTTPException(status_code=500, detail=f"IR 校验失败：Slot key `{slot_id}` 与 slot.id 不一致")
        owner = slot.get("ownerNodeId")
        if owner and owner not in node_ids:
            raise HTTPException(
                status_code=500, detail=f"IR 校验失败：Slot `{slot_id}` ownerNodeId `{owner}` 不存在"
            )

    for choice_group_id, choice_group in ir.choiceGroups.items():
        _require_keys("ChoiceGroup", choice_group_id, choice_group, ["id", "slotId", "selectionMode", "status"])
        if choice_group.get("id") != choice_group_id:
            raise HTTPException(
                status_code=500,
                detail=f"IR 校验失败：ChoiceGroup key `{choice_group_id}` 与 choiceGroup.id 不一致",
            )
        slot_id = choice_group.get("slotId")
        if slot_id and slot_id not in ir.slots:
            raise HTTPException(
                status_code=500,
                detail=f"IR 校验失败：ChoiceGroup `{choice_group_id}` slotId `{slot_id}` 不存在",
            )

    for issue_id, issue in ir.issues.items():
        _require_keys("Issue", issue_id, issue, ["id", "title", "severity", "status", "suggestedProjection"])
        if issue.get("id") != issue_id:
            raise HTTPException(status_code=500, detail=f"IR 校验失败：Issue key `{issue_id}` 与 issue.id 不一致")

    return ir
