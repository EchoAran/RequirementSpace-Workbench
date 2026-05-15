from __future__ import annotations

from .schema import GraphPatch, NodeKind, RequirementSpaceIR


def compute_impact_preview(ir: RequirementSpaceIR, patch: GraphPatch) -> dict[str, object]:
    touched: set[str] = set()
    kind_by_id = {node.id: node.kind for node in ir.nodes.values()}

    for node in patch.addNodes:
        touched.add(node.id)
        kind_by_id[node.id] = node.kind
    for node in patch.updateNodes:
        touched.add(node.id)
    for node_id in patch.removeNodeIds:
        touched.add(node_id)
    for link in patch.addLinks:
        touched.add(link.sourceId)
        touched.add(link.targetId)
    for link in patch.updateLinks:
        if "sourceId" in link.model_fields_set and link.sourceId:
            touched.add(link.sourceId)
        if "targetId" in link.model_fields_set and link.targetId:
            touched.add(link.targetId)
    for slot in patch.addSlots:
        touched.add(slot.ownerNodeId)
    for slot in patch.updateSlots:
        touched.add(slot.id)
        if "ownerNodeId" in slot.model_fields_set and slot.ownerNodeId:
            touched.add(slot.ownerNodeId)
    for group in patch.addChoiceGroups:
        touched.add(group.slotId)
    for issue in patch.addIssues:
        touched.update(issue.relatedNodeIds)
    for issue in patch.updateIssues:
        if "relatedNodeIds" in issue.model_fields_set and issue.relatedNodeIds:
            touched.update(issue.relatedNodeIds)

    return {
        "affectedGoals": sorted(node_id for node_id in touched if kind_by_id.get(node_id) == NodeKind.GOAL),
        "affectedActors": sorted(node_id for node_id in touched if kind_by_id.get(node_id) == NodeKind.ACTOR),
        "affectedFlows": sorted(
            node_id for node_id in touched if kind_by_id.get(node_id) in {NodeKind.FLOW, NodeKind.FLOW_STEP}
        ),
        "affectedObjects": sorted(node_id for node_id in touched if kind_by_id.get(node_id) == NodeKind.BUSINESS_OBJECT),
        "affectedScreens": sorted(node_id for node_id in touched if kind_by_id.get(node_id) == NodeKind.SCREEN),
        "newIssues": sorted(issue.id for issue in patch.addIssues) or None,
        "resolvedIssues": sorted(patch.resolveIssueIds) or None,
    }
