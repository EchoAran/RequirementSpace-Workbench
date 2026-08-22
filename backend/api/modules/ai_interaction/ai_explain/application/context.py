"""
Context loaders for the AI Explain (Q&A) service.

Each loader receives (project_id, target_id, session) and returns a
formatted plain-text block describing the target object and its relations.

Loaders do NOT call LLMs. They only query the database and format text.
The output is designed for human (LLM) readability: structured text with
section headers, indented lists, and no JSON.
"""

from __future__ import annotations

from sqlalchemy import select


def _format_entity(label: str, items: list[dict], template: str = "{name}") -> str:
    """Format a list of objects into a readable text block.

    Returns empty string if items is empty (caller should skip empty blocks).
    """
    if not items:
        return ""
    lines = [f"=== {label}（{len(items)}个） ==="]
    for item in items:
        lines.append(template.format(**item))
    return "\n".join(lines)


def _append_named_entities(
    parts: list[str],
    loaded: list[str],
    label: str,
    entities: list,
    loaded_kind: str | None,
) -> None:
    text = _format_entity(
        label,
        [{"name": entity.name, "id": entity.id} for entity in entities],
        "- {name} (ID:{id})",
    )
    if text:
        parts.append(text)
    if loaded_kind:
        loaded.extend(f"{loaded_kind}:{entity.id}" for entity in entities)


# ---------------------------------------------------------------------------
# Node-level loaders
# ---------------------------------------------------------------------------

async def _load_actor_context(project_id: int, target_id: int, session) -> tuple[str, list[str]]:
    """Load context for a single actor: self + features + scenarios."""
    from backend.database.model import ActorModel, FeatureModel, ScenarioModel, feature_actor_table

    actor = await session.get(ActorModel, target_id)
    if actor is None:
        raise ValueError("target_not_found")

    loaded = [f"actor:{target_id}"]
    parts = [f"参与者「{actor.name}」(ID:{actor.id})"]
    parts.append(f"描述：{actor.description or '（无描述）'}")

    # Associated features (via feature_actor_table)
    stmt = (
        select(FeatureModel)
        .join(feature_actor_table, FeatureModel.id == feature_actor_table.c.feature_id)
        .where(feature_actor_table.c.actor_id == target_id)
    )
    features = (await session.execute(stmt)).scalars().all()
    feat_text = _format_entity(
        "关联功能",
        [{"id": f.id, "name": f.name} for f in features],
        "- {name} (ID:{id})",
    )
    if feat_text:
        parts.append(feat_text)
    for f in features:
        loaded.append(f"feature:{f.id}")

    # Associated scenarios
    stmt = select(ScenarioModel).where(ScenarioModel.actor_id == target_id)
    scenarios = (await session.execute(stmt)).scalars().all()
    sc_text = _format_entity(
        "关联场景",
        [{"id": s.id, "name": s.name} for s in scenarios],
        "- {name} (ID:{id})",
    )
    if sc_text:
        parts.append(sc_text)
    for s in scenarios:
        loaded.append(f"scenario:{s.id}")

    return "\n\n".join(parts), loaded


async def _load_feature_context(project_id: int, target_id: int, session) -> tuple[str, list[str]]:
    """Load context for a single feature: self + parent + children + actors."""
    from backend.database.model import (
        ActorModel,
        FeatureModel,
        FeatureRelationModel,
        FlowModel,
        feature_actor_table,
        flow_feature_table,
    )

    feature = await session.get(FeatureModel, target_id)
    if feature is None:
        raise ValueError("target_not_found")

    loaded = [f"feature:{target_id}"]
    # A feature is a "branch" (module) if it has children, otherwise "leaf" (point)
    child_rel = await session.execute(
        select(FeatureRelationModel)
        .where(FeatureRelationModel.parent_feature_id == target_id)
        .limit(1)
    )
    is_branch = child_rel.first() is not None
    kind_label = "功能模块" if is_branch else "功能点"
    parts = [f"{kind_label}「{feature.name}」(ID:{feature.id})"]
    parts.append(f"描述：{feature.description or '（无描述）'}")

    # Parent feature (via FeatureRelationModel)
    rel = (await session.execute(
        select(FeatureRelationModel).where(FeatureRelationModel.child_feature_id == target_id)
    )).scalar_one_or_none()
    if rel:
        parent = await session.get(FeatureModel, rel.parent_feature_id)
        if parent:
            parts.append(f"所属父功能：{parent.name} (ID:{parent.id})")

    # Children (if branch)
    children = (await session.execute(
        select(FeatureModel)
        .join(FeatureRelationModel, FeatureModel.id == FeatureRelationModel.child_feature_id)
        .where(FeatureRelationModel.parent_feature_id == target_id)
    )).scalars().all()
    _append_named_entities(parts, loaded, "子功能", children, "feature")

    # Associated actors
    stmt = (
        select(ActorModel)
        .join(feature_actor_table, ActorModel.id == feature_actor_table.c.actor_id)
        .where(feature_actor_table.c.feature_id == target_id)
    )
    actors = (await session.execute(stmt)).scalars().all()
    _append_named_entities(parts, loaded, "关联参与者", actors, "actor")

    # Associated flows
    stmt = (
        select(FlowModel)
        .join(flow_feature_table, FlowModel.id == flow_feature_table.c.flow_id)
        .where(flow_feature_table.c.feature_id == target_id)
    )
    flows = (await session.execute(stmt)).scalars().all()
    _append_named_entities(parts, loaded, "关联流程", flows, None)

    return "\n\n".join(parts), loaded


async def _load_flow_context(project_id: int, target_id: int, session) -> tuple[str, list[str]]:
    """Load context for a single flow: self + features + steps."""
    from backend.database.model import FeatureModel, FlowModel, FlowStepModel, flow_feature_table

    flow = await session.get(FlowModel, target_id)
    if flow is None:
        raise ValueError("target_not_found")

    loaded = [f"flow:{target_id}"]
    parts = [f"流程「{flow.name}」(ID:{flow.id})"]
    parts.append(f"描述：{flow.description or '（无描述）'}")

    # Associated features
    stmt = (
        select(FeatureModel)
        .join(flow_feature_table, FeatureModel.id == flow_feature_table.c.feature_id)
        .where(flow_feature_table.c.flow_id == target_id)
    )
    features = (await session.execute(stmt)).scalars().all()
    feat_text = _format_entity(
        "关联功能",
        [{"name": f.name, "id": f.id} for f in features],
        "- {name} (ID:{id})",
    )
    if feat_text:
        parts.append(feat_text)
    for f in features:
        loaded.append(f"feature:{f.id}")

    # Flow steps
    steps = (await session.execute(
        select(FlowStepModel)
        .where(FlowStepModel.flow_id == target_id)
        .order_by(FlowStepModel.position)
    )).scalars().all()
    step_text = _format_entity(
        "流程步骤",
        [{"pos": s.position, "name": s.name} for s in steps],
        "{pos}. {name}",
    )
    if step_text:
        parts.append(step_text)

    return "\n\n".join(parts), loaded


async def _load_business_object_context(project_id: int, target_id: int, session) -> tuple[str, list[str]]:
    """Load context for a single business object: self + attributes."""
    from backend.database.model import BusinessObjectAttributeModel, BusinessObjectModel

    bo = await session.get(BusinessObjectModel, target_id)
    if bo is None:
        raise ValueError("target_not_found")

    loaded = [f"business_object:{target_id}"]
    parts = [f"业务数据对象「{bo.name}」(ID:{bo.id})"]
    parts.append(f"描述：{bo.description or '（无描述）'}")

    # Attributes
    attrs = (await session.execute(
        select(BusinessObjectAttributeModel).where(
            BusinessObjectAttributeModel.business_object_id == target_id
        )
    )).scalars().all()
    attr_text = _format_entity(
        "属性",
        [{"name": a.name, "type": a.data_type or "string"} for a in attrs],
        "- {name} ({type})",
    )
    if attr_text:
        parts.append(attr_text)
    for a in attrs:
        loaded.append(f"bo_attribute:{a.id}")

    return "\n\n".join(parts), loaded


# ---------------------------------------------------------------------------
# Node loader registry
# ---------------------------------------------------------------------------

NODE_LOADERS: dict[str, callable] = {
    "actor": _load_actor_context,
    "feature": _load_feature_context,
    "flow": _load_flow_context,
    "business_object": _load_business_object_context,
}

# ---------------------------------------------------------------------------
# Projection and workspace loaders
# ---------------------------------------------------------------------------

async def _append_project_entities(
    project_id: int,
    session,
    *,
    model,
    label: str,
    loaded_kind: str,
    parts: list[str],
    loaded: list[str],
) -> list:
    result = await session.execute(
        select(model).where(model.project_id == project_id)
    )
    entities = result.scalars().all()
    _append_named_entities(
        parts,
        loaded,
        label,
        entities,
        loaded_kind,
    )
    return entities


async def _append_scope_projection_details(
    features: list,
    session,
    *,
    parts: list[str],
    loaded: list[str],
) -> None:
    from backend.database.model import ScopeModel

    scope_result = await session.execute(
        select(ScopeModel).where(
            ScopeModel.feature_id.in_([feature.id for feature in features])
        )
    )
    scopes = scope_result.scalars().all()
    if not scopes:
        return

    features_by_id = {feature.id: feature for feature in features}
    scope_lines = ["=== Kano 分析与范围决策（每个功能的分类与理由） ==="]
    for scope in scopes:
        feature = features_by_id.get(scope.feature_id)
        feature_name = feature.name if feature else f"ID:{scope.feature_id}"
        line = f"- {feature_name}: 状态={scope.status}"
        if scope.kano_category_name:
            line += f", Kano={scope.kano_category_name}"
        if scope.reason:
            line += f", 理由={scope.reason[:200]}"
        if scope.positive_summary:
            line += f"\n  正面论证: {scope.positive_summary[:200]}"
        if scope.negative_summary:
            line += f"\n  反面论证: {scope.negative_summary[:200]}"
        scope_lines.append(line)
    parts.append("\n".join(scope_lines))
    loaded.extend(f"scope:{scope.id}" for scope in scopes)


async def _load_projection_context(
    project_id: int, stage: str, session,
) -> tuple[str, list[str]]:
    """Load context for a whole stage/projection: actors/features for 'what', etc."""
    loaders_map = {
        "what": ["actors", "features"],
        "how": ["features", "flows", "business_objects"],
        "scope": ["features"],
        "preview": ["features", "flows", "business_objects"],
    }
    required = loaders_map.get(stage, ["features"])
    loaded = []

    from backend.database.model import (
        ActorModel,
        BusinessObjectModel,
        FeatureModel,
        FlowModel,
    )

    parts = []
    if "actors" in required:
        await _append_project_entities(
            project_id,
            session,
            model=ActorModel,
            label="参与者",
            loaded_kind="actor",
            parts=parts,
            loaded=loaded,
        )

    features = []
    if "features" in required:
        features = await _append_project_entities(
            project_id,
            session,
            model=FeatureModel,
            label="功能",
            loaded_kind="feature",
            parts=parts,
            loaded=loaded,
        )
        if stage == "scope":
            await _append_scope_projection_details(
                features,
                session,
                parts=parts,
                loaded=loaded,
            )

    if "flows" in required:
        await _append_project_entities(
            project_id,
            session,
            model=FlowModel,
            label="流程",
            loaded_kind="flow",
            parts=parts,
            loaded=loaded,
        )

    if "business_objects" in required:
        await _append_project_entities(
            project_id,
            session,
            model=BusinessObjectModel,
            label="业务数据对象",
            loaded_kind="business_object",
            parts=parts,
            loaded=loaded,
        )

    return "\n\n".join(parts), loaded


async def _load_workspace_context(project_id: int, session) -> tuple[str, list[str]]:
    """Load full workspace context with threshold-based summary for large projects."""
    from backend.database.model import (
        ActorModel,
        BusinessObjectModel,
        FeatureModel,
        FlowModel,
        ProjectModel,
    )

    project = await session.get(ProjectModel, project_id)
    project_name = project.name if project else "未知项目"

    # Count objects
    actor_count = (await session.execute(
        select(ActorModel).where(ActorModel.project_id == project_id)
    )).scalars().all()
    feature_count = (await session.execute(
        select(FeatureModel).where(FeatureModel.project_id == project_id)
    )).scalars().all()
    flow_count = (await session.execute(
        select(FlowModel).where(FlowModel.project_id == project_id)
    )).scalars().all()
    bo_count = (await session.execute(
        select(BusinessObjectModel).where(BusinessObjectModel.project_id == project_id)
    )).scalars().all()

    total = len(actor_count) + len(feature_count) + len(flow_count) + len(bo_count)
    loaded = []

    if total > 50:
        parts = _build_workspace_summary(
            project_name,
            actor_count,
            feature_count,
            flow_count,
            bo_count,
        )
    else:
        parts = [f"=== 项目：{project_name} ==="]
        _append_named_entities(parts, loaded, "参与者", actor_count, "actor")
        _append_named_entities(parts, loaded, "功能", feature_count, "feature")
        _append_named_entities(parts, loaded, "流程", flow_count, "flow")
        _append_named_entities(
            parts,
            loaded,
            "业务数据对象",
            bo_count,
            "business_object",
        )

    return "\n\n".join(parts), loaded


def _build_workspace_summary(
    project_name: str,
    actors: list,
    features: list,
    flows: list,
    business_objects: list,
) -> list[str]:
    actor_names = [actor.name for actor in actors]
    name_preview = ", ".join(actor_names[:5])
    if len(actor_names) > 5:
        name_preview += "..."
    return [
        f"=== 项目总览：{project_name} ===",
        f"参与者：{len(actors)}个（{name_preview}）",
        f"功能：{len(features)}个",
        f"流程：{len(flows)}个",
        f"业务数据对象：{len(business_objects)}个",
        "",
        "如需详细信息，请选择更具体的范围或在问题中指定对象名称。",
    ]
