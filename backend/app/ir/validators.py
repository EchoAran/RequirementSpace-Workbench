from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError

from .link_rules import is_link_allowed
from .schema import ChoiceGroup, GraphPatch, ProjectionKind, Proposal, RequirementSpaceIR


def _raise_ir_error(message: str, status_code: int) -> None:
    raise HTTPException(status_code=status_code, detail=f"IR 校验失败：{message}")


def _raise_patch_error(message: str, status_code: int) -> None:
    raise HTTPException(status_code=status_code, detail=f"GraphPatch 校验失败：{message}")


def _raise_choice_group_error(message: str, status_code: int) -> None:
    raise HTTPException(status_code=status_code, detail=f"ChoiceGroup 校验失败：{message}")


def _raise_proposal_error(message: str, status_code: int) -> None:
    raise HTTPException(status_code=status_code, detail=f"Proposal 校验失败：{message}")


def validate_graph_patch(payload: dict[str, Any] | GraphPatch, *, status_code: int = 400) -> GraphPatch:
    try:
        patch = payload if isinstance(payload, GraphPatch) else GraphPatch.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=status_code, detail=f"GraphPatch 校验失败：{exc}") from exc

    _ensure_unique_ids([node.id for node in patch.addNodes], "addNodes", status_code, _raise_patch_error)
    _ensure_unique_ids([link.id for link in patch.addLinks], "addLinks", status_code, _raise_patch_error)
    _ensure_unique_ids([slot.id for slot in patch.addSlots], "addSlots", status_code, _raise_patch_error)
    _ensure_unique_ids([group.id for group in patch.addChoiceGroups], "addChoiceGroups", status_code, _raise_patch_error)
    _ensure_unique_ids([issue.id for issue in patch.addIssues], "addIssues", status_code, _raise_patch_error)

    for group in patch.addChoiceGroups:
        _ensure_unique_ids([choice.id for choice in group.choices], f"ChoiceGroup `{group.id}`.choices", status_code, _raise_patch_error)
    for group in patch.updateChoiceGroups:
        if group.choices:
            _ensure_unique_ids(
                [choice.id for choice in group.choices],
                f"ChoiceGroupUpdate `{group.id}`.choices",
                status_code,
                _raise_patch_error,
            )

    return patch


def validate_choice_group(
    payload: dict[str, Any] | ChoiceGroup,
    *,
    status_code: int = 400,
    expected_slot_id: str | None = None,
) -> ChoiceGroup:
    try:
        group = payload if isinstance(payload, ChoiceGroup) else ChoiceGroup.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=status_code, detail=f"ChoiceGroup 校验失败：{exc}") from exc

    if expected_slot_id and group.slotId != expected_slot_id:
        _raise_choice_group_error(
            f"slotId `{group.slotId}` 与预期槽位 `{expected_slot_id}` 不一致",
            status_code,
        )
    if not group.choices:
        _raise_choice_group_error("choices 不能为空", status_code)
    choice_ids = [choice.id for choice in group.choices]
    _ensure_unique_ids(choice_ids, f"ChoiceGroup `{group.id}`.choices", status_code, _raise_choice_group_error)
    for choice in group.choices:
        if choice.choiceGroupId != group.id:
            _raise_choice_group_error(
                f"Choice `{choice.id}` choiceGroupId `{choice.choiceGroupId}` 与 ChoiceGroup `{group.id}` 不一致",
                status_code,
            )
    for selected_choice_id in group.selectedChoiceIds:
        if selected_choice_id not in choice_ids:
            _raise_choice_group_error(
                f"selectedChoiceIds 包含不存在的 choice `{selected_choice_id}`",
                status_code,
            )
    return group


def validate_proposal(
    payload: dict[str, Any] | Proposal,
    *,
    status_code: int = 400,
    expected_workspace_id: str | None = None,
) -> Proposal:
    try:
        proposal = payload if isinstance(payload, Proposal) else Proposal.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=status_code, detail=f"Proposal 校验失败：{exc}") from exc

    if expected_workspace_id and proposal.workspaceId != expected_workspace_id:
        _raise_proposal_error(
            f"workspaceId `{proposal.workspaceId}` 与预期 workspace `{expected_workspace_id}` 不一致",
            status_code,
        )
    return proposal


def validate_ir(payload: dict[str, Any] | RequirementSpaceIR, *, status_code: int = 400) -> RequirementSpaceIR:
    try:
        ir = payload if isinstance(payload, RequirementSpaceIR) else RequirementSpaceIR.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=status_code, detail=f"IR 校验失败：{exc}") from exc

    node_ids = set(ir.nodes.keys())
    slot_ids = set(ir.slots.keys())
    issue_ids = set(ir.issues.keys())

    for node_id, node in ir.nodes.items():
        if node.id != node_id:
            _raise_ir_error(f"Node key `{node_id}` 与 node.id 不一致", status_code)

    link_ids: set[str] = set()
    for link in ir.links:
        if link.id in link_ids:
            _raise_ir_error(f"Link `{link.id}` 重复", status_code)
        link_ids.add(link.id)
        if link.sourceId not in node_ids:
            _raise_ir_error(f"Link `{link.id}` sourceId `{link.sourceId}` 不存在", status_code)
        if link.targetId not in node_ids:
            _raise_ir_error(f"Link `{link.id}` targetId `{link.targetId}` 不存在", status_code)
        source_kind = ir.nodes[link.sourceId].kind
        target_kind = ir.nodes[link.targetId].kind
        if not is_link_allowed(link.type, source_kind, target_kind):
            _raise_ir_error(
                f"Link `{link.id}` 类型 `{link.type.value}` 不允许连接 `{source_kind.value}` -> `{target_kind.value}`",
                status_code,
            )

    for slot_id, slot in ir.slots.items():
        if slot.id != slot_id:
            _raise_ir_error(f"Slot key `{slot_id}` 与 slot.id 不一致", status_code)
        if slot.ownerNodeId not in node_ids:
            _raise_ir_error(f"Slot `{slot_id}` ownerNodeId `{slot.ownerNodeId}` 不存在", status_code)
        for related_node_id in slot.context.relatedNodeIds:
            if related_node_id not in node_ids:
                _raise_ir_error(f"Slot `{slot_id}` context.relatedNodeIds 包含不存在节点 `{related_node_id}`", status_code)

    for group_id, group in ir.choiceGroups.items():
        if group.id != group_id:
            _raise_ir_error(f"ChoiceGroup key `{group_id}` 与 choiceGroup.id 不一致", status_code)
        if group.slotId not in slot_ids:
            _raise_ir_error(f"ChoiceGroup `{group_id}` slotId `{group.slotId}` 不存在", status_code)
        choice_ids = {choice.id for choice in group.choices}
        if len(choice_ids) != len(group.choices):
            _raise_ir_error(f"ChoiceGroup `{group_id}` 内 choice.id 重复", status_code)
        for choice in group.choices:
            if choice.choiceGroupId != group_id:
                _raise_ir_error(f"Choice `{choice.id}` choiceGroupId 与 ChoiceGroup `{group_id}` 不一致", status_code)
            _validate_patch_against_ir(
                ir,
                choice.patch,
                label=f"ChoiceGroup `{group_id}`.choices[`{choice.id}`].patch",
                status_code=status_code,
            )
        invalid_selected_ids = [choice_id for choice_id in group.selectedChoiceIds if choice_id not in choice_ids]
        if invalid_selected_ids:
            _raise_ir_error(
                f"ChoiceGroup `{group_id}` selectedChoiceIds 包含不存在的 choice `{invalid_selected_ids[0]}`",
                status_code,
            )

    for proposal_id, proposal in ir.proposals.items():
        if proposal.id != proposal_id:
            _raise_ir_error(f"Proposal key `{proposal_id}` 与 proposal.id 不一致", status_code)
        if proposal.workspaceId != ir.id:
            _raise_ir_error(f"Proposal `{proposal_id}` workspaceId `{proposal.workspaceId}` 与 IR 不一致", status_code)
        _validate_patch_against_ir(
            ir,
            proposal.patch,
            label=f"Proposal `{proposal_id}`.patch",
            status_code=status_code,
        )

    for issue_id, issue in ir.issues.items():
        if issue.id != issue_id:
            _raise_ir_error(f"Issue key `{issue_id}` 与 issue.id 不一致", status_code)
        for related_node_id in issue.relatedNodeIds:
            if related_node_id not in node_ids:
                _raise_ir_error(f"Issue `{issue_id}` relatedNodeIds 包含不存在节点 `{related_node_id}`", status_code)

    for expanded_id in ir.projections.goal.expandedNodeIds:
        if expanded_id not in node_ids:
            _raise_ir_error(f"projections.goal.expandedNodeIds 包含不存在节点 `{expanded_id}`", status_code)
    if ir.projections.role.activeActorId and ir.projections.role.activeActorId not in node_ids:
        _raise_ir_error(f"projections.role.activeActorId `{ir.projections.role.activeActorId}` 不存在", status_code)
    for highlighted_id in ir.projections.system.highlightedNodeIds:
        if highlighted_id not in node_ids:
            _raise_ir_error(f"projections.system.highlightedNodeIds 包含不存在节点 `{highlighted_id}`", status_code)
    if ir.projections.ui.activeActorId and ir.projections.ui.activeActorId not in node_ids:
        _raise_ir_error(f"projections.ui.activeActorId `{ir.projections.ui.activeActorId}` 不存在", status_code)
    if ir.projections.ui.activeScreenId and ir.projections.ui.activeScreenId not in node_ids:
        _raise_ir_error(f"projections.ui.activeScreenId `{ir.projections.ui.activeScreenId}` 不存在", status_code)

    projection_values = {item.value for item in ProjectionKind}
    for issue in ir.issues.values():
        if issue.suggestedProjection.value not in projection_values:
            _raise_ir_error(f"Issue `{issue.id}` suggestedProjection 非法", status_code)

    valid_target_ids = (
        node_ids
        | link_ids
        | slot_ids
        | set(ir.choiceGroups.keys())
        | {choice.id for group in ir.choiceGroups.values() for choice in group.choices}
        | issue_ids
        | set(ir.proposals.keys())
    )
    for operation in ir.audit.operationLog:
        historical_target_ids = {
            item
            for item in (operation.details.get("historicalTargetIds") if isinstance(operation.details, dict) else []) or []
            if isinstance(item, str)
        }
        historical_all = isinstance(operation.details, dict) and operation.details.get("historical") is True
        for target_id in operation.targetIds:
            if target_id in valid_target_ids or historical_all or target_id in historical_target_ids:
                continue
            _raise_ir_error(
                f"audit.operationLog `{operation.id}` targetIds 包含不存在对象 `{target_id}`，且未标记 historical",
                status_code,
            )

    return ir


def _ensure_unique_ids(
    ids: list[str],
    label: str,
    status_code: int,
    error_builder,
) -> None:
    seen: set[str] = set()
    for item_id in ids:
        if item_id in seen:
            error_builder(f"{label} 中存在重复 id `{item_id}`", status_code)
        seen.add(item_id)


def _validate_patch_against_ir(
    ir: RequirementSpaceIR,
    payload: dict[str, Any] | GraphPatch,
    *,
    label: str,
    status_code: int,
) -> None:
    try:
        patch = validate_graph_patch(payload, status_code=status_code)
    except HTTPException as exc:
        raise HTTPException(status_code=exc.status_code, detail=f"{label} 非法：{exc.detail}") from exc

    current_node_kinds = {node_id: node.kind for node_id, node in ir.nodes.items()}
    patch_node_kinds = {node.id: node.kind for node in patch.addNodes}
    available_node_kinds = {**current_node_kinds, **patch_node_kinds}
    current_node_ids = set(current_node_kinds.keys())
    available_node_ids = set(available_node_kinds.keys())
    current_link_ids = {link.id for link in ir.links}
    current_slot_ids = set(ir.slots.keys())
    available_slot_ids = current_slot_ids | {slot.id for slot in patch.addSlots}
    current_issue_ids = set(ir.issues.keys())
    available_issue_ids = current_issue_ids | {issue.id for issue in patch.addIssues}

    for node in patch.updateNodes:
        if node.id not in current_node_ids:
            _raise_ir_error(f"{label}.updateNodes[`{node.id}`] 指向不存在节点", status_code)
    for node_id in patch.removeNodeIds:
        if node_id not in current_node_ids:
            _raise_ir_error(f"{label}.removeNodeIds 包含不存在节点 `{node_id}`", status_code)

    for link in patch.addLinks:
        if link.sourceId not in available_node_ids:
            _raise_ir_error(f"{label}.addLinks[`{link.id}`].sourceId `{link.sourceId}` 不存在", status_code)
        if link.targetId not in available_node_ids:
            _raise_ir_error(f"{label}.addLinks[`{link.id}`].targetId `{link.targetId}` 不存在", status_code)
        source_kind = available_node_kinds[link.sourceId]
        target_kind = available_node_kinds[link.targetId]
        if not is_link_allowed(link.type, source_kind, target_kind):
            _raise_ir_error(
                f"{label}.addLinks[`{link.id}`] 类型 `{link.type.value}` 不允许连接 `{source_kind.value}` -> `{target_kind.value}`",
                status_code,
            )
    current_links = {link.id: link for link in ir.links}
    for link in patch.updateLinks:
        existing = current_links.get(link.id)
        if existing is None:
            _raise_ir_error(f"{label}.updateLinks[`{link.id}`] 指向不存在 link", status_code)
        source_id = link.sourceId if link.sourceId is not None else existing.sourceId
        target_id = link.targetId if link.targetId is not None else existing.targetId
        link_type = link.type if link.type is not None else existing.type
        if source_id not in current_node_ids:
            _raise_ir_error(f"{label}.updateLinks[`{link.id}`].sourceId `{source_id}` 不存在", status_code)
        if target_id not in current_node_ids:
            _raise_ir_error(f"{label}.updateLinks[`{link.id}`].targetId `{target_id}` 不存在", status_code)
        if not is_link_allowed(link_type, current_node_kinds[source_id], current_node_kinds[target_id]):
            _raise_ir_error(
                f"{label}.updateLinks[`{link.id}`] 类型 `{link_type.value}` 不允许连接 "
                f"`{current_node_kinds[source_id].value}` -> `{current_node_kinds[target_id].value}`",
                status_code,
            )
    for link_id in patch.removeLinkIds:
        if link_id not in current_link_ids:
            _raise_ir_error(f"{label}.removeLinkIds 包含不存在 link `{link_id}`", status_code)

    for slot in patch.addSlots:
        if slot.ownerNodeId not in available_node_ids:
            _raise_ir_error(f"{label}.addSlots[`{slot.id}`].ownerNodeId `{slot.ownerNodeId}` 不存在", status_code)
        for related_node_id in slot.context.relatedNodeIds:
            if related_node_id not in available_node_ids:
                _raise_ir_error(
                    f"{label}.addSlots[`{slot.id}`].context.relatedNodeIds 包含不存在节点 `{related_node_id}`",
                    status_code,
                )
    for slot in patch.updateSlots:
        if slot.id not in current_slot_ids:
            _raise_ir_error(f"{label}.updateSlots[`{slot.id}`] 指向不存在 slot", status_code)
        if slot.ownerNodeId is not None and slot.ownerNodeId not in current_node_ids:
            _raise_ir_error(f"{label}.updateSlots[`{slot.id}`].ownerNodeId `{slot.ownerNodeId}` 不存在", status_code)
        if slot.context is not None:
            for related_node_id in slot.context.relatedNodeIds:
                if related_node_id not in current_node_ids:
                    _raise_ir_error(
                        f"{label}.updateSlots[`{slot.id}`].context.relatedNodeIds 包含不存在节点 `{related_node_id}`",
                        status_code,
                    )
    for slot_id in patch.removeSlotIds:
        if slot_id not in current_slot_ids:
            _raise_ir_error(f"{label}.removeSlotIds 包含不存在 slot `{slot_id}`", status_code)

    current_choice_groups = ir.choiceGroups
    for group in patch.addChoiceGroups:
        if group.slotId not in available_slot_ids:
            _raise_ir_error(f"{label}.addChoiceGroups[`{group.id}`].slotId `{group.slotId}` 不存在", status_code)
    for group in patch.updateChoiceGroups:
        existing_group = current_choice_groups.get(group.id)
        if existing_group is None:
            _raise_ir_error(f"{label}.updateChoiceGroups[`{group.id}`] 指向不存在 choiceGroup", status_code)
        if group.slotId is not None and group.slotId not in current_slot_ids:
            _raise_ir_error(f"{label}.updateChoiceGroups[`{group.id}`].slotId `{group.slotId}` 不存在", status_code)
        if group.selectedChoiceIds is not None:
            choice_ids = {choice.id for choice in existing_group.choices}
            if group.choices:
                choice_ids |= {choice.id for choice in group.choices}
            for selected_choice_id in group.selectedChoiceIds:
                if selected_choice_id not in choice_ids:
                    _raise_ir_error(
                        f"{label}.updateChoiceGroups[`{group.id}`].selectedChoiceIds 包含不存在 choice `{selected_choice_id}`",
                        status_code,
                    )

    for issue in patch.addIssues:
        for related_node_id in issue.relatedNodeIds:
            if related_node_id not in available_node_ids:
                _raise_ir_error(
                    f"{label}.addIssues[`{issue.id}`].relatedNodeIds 包含不存在节点 `{related_node_id}`",
                    status_code,
                )
    for issue in patch.updateIssues:
        if issue.id not in current_issue_ids:
            _raise_ir_error(f"{label}.updateIssues[`{issue.id}`] 指向不存在 issue", status_code)
        if issue.relatedNodeIds is not None:
            for related_node_id in issue.relatedNodeIds:
                if related_node_id not in current_node_ids:
                    _raise_ir_error(
                        f"{label}.updateIssues[`{issue.id}`].relatedNodeIds 包含不存在节点 `{related_node_id}`",
                        status_code,
                    )
    for issue_id in patch.resolveIssueIds:
        if issue_id not in available_issue_ids:
            _raise_ir_error(f"{label}.resolveIssueIds 包含不存在 issue `{issue_id}`", status_code)
