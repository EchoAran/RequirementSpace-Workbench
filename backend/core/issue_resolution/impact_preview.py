"""Impact Preview — structured summary of a repair patch.

Used by:
- IssueRepairDraftService.create_draft() — stored in draft.validation_report
- ChoiceService.create_choice_group() — stored in ChoiceModel.impact_preview

Static analysis (no dry-run). Entity names queried via session for readability.
"""

from sqlalchemy import select
from backend.database.model import (
    ActorModel,
    BusinessObjectModel,
    FeatureModel,
    FlowModel,
    FlowStepModel,
    ScenarioModel,
    ScopeModel,
)


# Risk level mapping by operation pattern
_RISK_MAP: dict[str, str] = {
    "updateNodes:scope:reason": "low",
    "addNodes:business_object_attribute": "low",
    "addLinks:feature_actor_relation": "medium",
    "addLinks:flow_feature_relation": "medium",
    "updateNodes:scenario:feature_id": "medium",
    "addLinks:flow_step_actor": "medium",
    "addLinks:flow_step_next": "high",
    "addLinks:flow_step_input_business_object": "medium",
    "addLinks:flow_step_output_business_object": "medium",
}


def _determine_risk_level(patch: dict) -> str:
    """Return the highest risk level across all operations in the patch."""
    levels = {"low": 0, "medium": 1, "high": 2}
    highest = "low"
    for op, items in patch.items():
        for item in items if isinstance(items, list) else []:
            kind = item.get("kind", "")
            key = f"{op}:{kind}"
            # Match with field specificity
            for pattern, level in _RISK_MAP.items():
                if key.startswith(pattern.rstrip("*")):
                    if levels.get(level, 0) > levels.get(highest, 0):
                        highest = level
    return highest


def _make_summary(affected_nodes: list, affected_relations: list) -> str:
    """Build a one-line human-readable summary."""
    parts = []
    node_changes = {}
    for n in affected_nodes:
        c = n.get("change", "")
        name = n.get("name", "")
        node_changes[c] = node_changes.get(c, 0) + 1
    for change, count in node_changes.items():
        parts.append(f"{change}: {count} 项")
    for r in affected_relations:
        parts.append(f"{r.get('change', '')}: {r.get('source', '')} → {r.get('target', '')}")
    return "；".join(parts) if parts else "无影响"


async def _resolve_node_name(project_id: int, kind: str, entity_id: int, session) -> str:
    """Query the entity name for a given kind and id."""
    try:
        if kind == "feature":
            res = await session.execute(
                select(FeatureModel.name).where(FeatureModel.id == entity_id, FeatureModel.project_id == project_id)
            )
        elif kind == "actor":
            res = await session.execute(
                select(ActorModel.name).where(ActorModel.id == entity_id, ActorModel.project_id == project_id)
            )
        elif kind == "flow":
            res = await session.execute(
                select(FlowModel.name).where(FlowModel.id == entity_id, FlowModel.project_id == project_id)
            )
        elif kind == "flow_step":
            res = await session.execute(
                select(FlowStepModel.name).where(FlowStepModel.id == entity_id)
            )
        elif kind == "scenario":
            res = await session.execute(
                select(ScenarioModel.name).where(ScenarioModel.id == entity_id, ScenarioModel.project_id == project_id)
            )
        elif kind == "scope":
            res = await session.execute(
                select(ScopeModel.reason).where(ScopeModel.id == entity_id)
            )
            row = res.scalar_one_or_none()
            return f"scope (id={entity_id})"
        elif kind == "business_object":
            res = await session.execute(
                select(BusinessObjectModel.name).where(BusinessObjectModel.id == entity_id, BusinessObjectModel.project_id == project_id)
            )
        else:
            return f"{kind} (id={entity_id})"
        row = res.scalar_one_or_none()
        return row if row else f"{kind} (id={entity_id})"
    except Exception:
        return f"{kind} (id={entity_id})"


async def build_impact_preview(
    patch: dict,
    project_id: int,
    issue_code: str,
    session,
) -> dict:
    """Analyze a patch dict and produce a structured impact summary.

    Queries entity names via session for human-readable affected_nodes.
    """
    affected_nodes = []
    affected_relations = []

    # Analyze updateNodes
    for node in patch.get("updateNodes", []):
        kind = node.get("kind", "")
        node_id = int(node.get("id") or 0)
        name = await _resolve_node_name(project_id, kind, node_id, session)
        if kind == "scope":
            affected_nodes.append({"kind": "scope", "id": node_id, "name": name, "change": "更新范围决策理由"})
        elif kind == "scenario" and ("feature_id" in node or "featureId" in node):
            affected_nodes.append({"kind": "scenario", "id": node_id, "name": name, "change": "修改场景功能归属"})

    # Analyze addLinks
    for link in patch.get("addLinks", []):
        link_type = link.get("type") or link.get("relationType") or link.get("relation_type") or ""
        source_id = int(link.get("sourceId") or link.get("source_id") or link.get("source") or 0)
        target_id = int(link.get("targetId") or link.get("target_id") or link.get("target") or 0)

        if link_type in ("feature_actor_relation", "feature_actor"):
            f_name = await _resolve_node_name(project_id, "feature", source_id, session)
            a_name = await _resolve_node_name(project_id, "actor", target_id, session)
            affected_relations.append({"type": link_type, "source": f_name, "target": a_name, "change": "新增执行角色关系"})
        elif link_type in ("flow_feature_relation", "flow_feature"):
            fl_name = await _resolve_node_name(project_id, "flow", source_id, session)
            fe_name = await _resolve_node_name(project_id, "feature", target_id, session)
            affected_relations.append({"type": link_type, "source": fl_name, "target": fe_name, "change": "新增流程-功能关联"})
        elif link_type == "flow_step_actor":
            s_name = await _resolve_node_name(project_id, "flow_step", source_id, session)
            a_name = await _resolve_node_name(project_id, "actor", target_id, session)
            affected_relations.append({"type": link_type, "source": s_name, "target": a_name, "change": "新增步骤执行角色"})
        elif link_type == "flow_step_next":
            src_name = await _resolve_node_name(project_id, "flow_step", source_id, session)
            tgt_name = await _resolve_node_name(project_id, "flow_step", target_id, session)
            affected_relations.append({"type": link_type, "source": src_name, "target": tgt_name, "change": "修改流程步骤连接"})

    # Analyze addNodes
    for node in patch.get("addNodes", []):
        kind = node.get("kind", "")
        if kind == "business_object_attribute":
            bo_id = int(node.get("business_object_id") or node.get("businessObjectId") or 0)
            bo_name = await _resolve_node_name(project_id, "business_object", bo_id, session)
            affected_nodes.append({
                "kind": "business_object_attribute",
                "id": bo_id,
                "name": f"{bo_name}.{node.get('name', '')}",
                "change": "新增属性",
            })

    summary = _make_summary(affected_nodes, affected_relations)
    risk_level = _determine_risk_level(patch)

    return {
        "summary": summary,
        "affected_nodes": affected_nodes,
        "affected_relations": affected_relations,
        "risk_level": risk_level,
    }
