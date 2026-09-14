"""
Three-Way Semantic Requirement-Space Merge Engine.
在 base/target/source 三份规范化状态字典之间计算三方语义合并，而不是通用 JSON 合并。

对齐规则与 semantic_diff 一致：对象一律按 logical_uuid 匹配（跨分支复制后物理 ID 不同）。
合并规则（阶段 6）：
  - 仅一侧相对 base 改动的字段/关系自动采用；两侧修改不同字段自动合并；
  - 两侧对同一字段给出不同结果、删除与修改相撞、同一关系作相反操作、同一排序位竞争、
    对象身份/父层级冲突时生成冲突，绝不静默覆盖；
  - 冲突由调用方传入 resolutions（conflict_id → {"choice": "target"|"source"}）显式解决；
    未解决的冲突保留在返回值 conflicts 中，由合并执行层阻止提交。

本模块是纯函数，不依赖 FastAPI / SQLAlchemy，可独立测试。
"""
import hashlib
from typing import Any

from backend.api.modules.version_control.domain.semantic_diff import (
    COLLECTION_KEYS,
    ENTITY_TYPE_BY_COLLECTION,
    METADATA_FIELDS,
    ORDERED_CHILD_PARENTS,
    RELATION_FIELDS,
    SCALAR_FIELDS,
    _display_name,
    _index_entity,
)
from backend.api.modules.version_control.domain.serializer import (
    serialize_requirement_space,
)

# 冲突类型的稳定错误码
CONFLICT_TYPES = frozenset({
    "same_field_different_value",
    "delete_vs_modify",
    "opposite_relation_ops",
    "same_position_order",
    "object_identity_parent",
    "competing_default_transition",
    "rule_parent_cycle",
})
CHOICES = ("target", "source")


def _conflict_id(entity_uuid: str, path: str, conflict_type: str) -> str:
    """为冲突生成确定性 ID；heads 不变时跨重算稳定，便于客户端选择稳定映射。"""
    raw = f"{entity_uuid}::{path}::{conflict_type}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _make_conflict(
    conflict_type: str,
    entity_type: str,
    entity_uuid: str,
    entity_name: str,
    path: str,
    base_value: Any,
    target_value: Any,
    source_value: Any,
    parent_uuid: str | None = None,
    parent_type: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """构造一条冲突项，携带 base/target/source 三侧值供解决界面展示。"""
    item: dict[str, Any] = {
        "conflict_id": _conflict_id(entity_uuid, path, conflict_type),
        "conflict_type": conflict_type,
        "entity_type": entity_type,
        "entity_uuid": entity_uuid,
        "entity_name": entity_name,
        "path": path,
        "parent_uuid": parent_uuid,
        "parent_type": parent_type,
        "base_value": base_value,
        "target_value": target_value,
        "source_value": source_value,
        "choices": list(CHOICES),
        "resolved": False,
    }
    item.update(extra)
    return item


def _resolve_value(
    conflict: dict[str, Any],
    resolutions: dict[str, dict[str, Any]] | None,
) -> tuple[bool, Any]:
    """在 resolutions 中查找冲突的解决结果，返回 (是否已解决, 所选值)。"""
    if not resolutions:
        return False, None
    resolution = resolutions.get(conflict["conflict_id"])
    if not resolution:
        return False, None
    choice = resolution.get("choice")
    if choice == "target":
        return True, conflict["target_value"]
    if choice == "source":
        return True, conflict["source_value"]
    if choice == "manual":
        return True, resolution.get("manual_value")
    return False, None


def _build_name_index(
    base_state: dict[str, Any],
    target_state: dict[str, Any],
    source_state: dict[str, Any],
) -> dict[str, dict[str, str]]:
    """构建 uuid → (对象类型, 展示名) 的全局索引，覆盖三侧状态（含嵌套子对象）。"""
    index: dict[str, dict[str, str]] = {}
    for state in (base_state, target_state, source_state):
        for key, entity_type in ENTITY_TYPE_BY_COLLECTION.items():
            for entity in state.get(key, []):
                _index_entity(index, entity, entity_type)
        for scenario in state.get("scenarios", []):
            for ac in scenario.get("acceptance_criteria", []):
                _index_entity(index, ac, "acceptance_criterion")
        for bo in state.get("business_objects", []):
            for attr in bo.get("attributes", []):
                _index_entity(index, attr, "business_object_attribute")
        for flow in state.get("flows", []):
            for step in flow.get("steps", []):
                _index_entity(index, step, "flow_step")
            for transition in flow.get("transitions", []):
                _index_entity(index, transition, "flow_transition")
    index["project"] = {"entity_type": "project_metadata", "name": ""}
    return index


def _merge_field(
    field: str,
    base_value: Any,
    target_value: Any,
    source_value: Any,
    conflict_type: str,
    entity_type: str,
    entity_uuid: str,
    entity_name: str,
    path: str,
    parent_uuid: str | None,
    parent_type: str | None,
    resolutions: dict[str, dict[str, Any]] | None,
    conflicts: list[dict[str, Any]],
    name_index: dict[str, dict[str, str]] | None = None,
    **extra: Any,
) -> Any:
    """合并单个标量/单值字段：单侧改动自动采用，两侧不同则冲突。"""
    if target_value == source_value:
        return target_value
    if base_value == target_value:
        return source_value
    if base_value == source_value:
        return target_value
    conflict = _make_conflict(
        conflict_type, entity_type, entity_uuid, entity_name, path,
        base_value, target_value, source_value,
        parent_uuid, parent_type, **extra,
    )
    resolved, chosen = _resolve_value(conflict, resolutions)
    if resolved:
        return chosen
    conflicts.append(conflict)
    # 未解决时暂取 target 侧作为占位；合并执行层会因 conflicts 非空而阻止提交。
    return target_value


def _merge_relation_set(
    field: str,
    base_value: Any,
    target_value: Any,
    source_value: Any,
    entity_type: str,
    entity_uuid: str,
    entity_name: str,
    parent_uuid: str | None,
    parent_type: str | None,
    name_index: dict[str, dict[str, str]],
    resolutions: dict[str, dict[str, Any]] | None,
    conflicts: list[dict[str, Any]],
) -> list[str]:
    """合并关系集合字段：两侧新增取并集，同一元素一侧增另一侧删产生相反操作冲突。"""
    base_set = set(base_value or [])
    target_set = set(target_value or [])
    source_set = set(source_value or [])

    target_added = target_set - base_set
    target_removed = base_set - target_set
    source_added = source_set - base_set
    source_removed = base_set - source_set

    merged_set = (base_set | target_added | source_added) - target_removed - source_removed

    # 同一关系元素：一侧新增、另一侧移除，逐元素显式解决，避免静默丢增删。
    opposite = sorted((target_added & source_removed) | (source_added & target_removed))
    related_type = RELATION_FIELDS.get(entity_type, {}).get(field)
    for related_uuid in opposite:
        target_has = related_uuid in target_set
        source_has = related_uuid in source_set
        conflict = _make_conflict(
            "opposite_relation_ops", entity_type, entity_uuid, entity_name, field,
            related_uuid,
            related_uuid if target_has else None,
            related_uuid if source_has else None,
            parent_uuid, parent_type,
            related_entity_type=related_type,
            related_entity_uuid=related_uuid,
            related_entity_name=name_index.get(related_uuid, {}).get("name", ""),
        )
        resolved, chosen = _resolve_value(conflict, resolutions)
        if resolved:
            if chosen == related_uuid:
                merged_set.add(related_uuid)
            else:
                merged_set.discard(related_uuid)
        else:
            conflicts.append(conflict)
            merged_set.add(related_uuid)

    return sorted(merged_set)


def _merge_entity(
    entity_type: str,
    base: dict[str, Any],
    target: dict[str, Any],
    source: dict[str, Any],
    resolutions: dict[str, dict[str, Any]] | None,
    conflicts: list[dict[str, Any]],
    name_index: dict[str, dict[str, str]],
    parent_uuid: str | None = None,
    parent_type: str | None = None,
) -> dict[str, Any]:
    """合并单个实体（三者都存在）：标量字段、关系集合、单值关系逐项应用三方规则。"""
    entity_uuid = target.get("logical_uuid") or base.get("logical_uuid")
    entity_name = _display_name(target) or _display_name(base)
    merged: dict[str, Any] = {"logical_uuid": entity_uuid}

    for field in SCALAR_FIELDS.get(entity_type, []):
        merged[field] = _merge_field(
            field,
            base.get(field),
            target.get(field),
            source.get(field),
            "same_field_different_value",
            entity_type, entity_uuid, entity_name, field,
            parent_uuid, parent_type, resolutions, conflicts,
        )

    for field, related_type in RELATION_FIELDS.get(entity_type, {}).items():
        base_val = base.get(field)
        target_val = target.get(field)
        source_val = source.get(field)
        if isinstance(target_val, list):
            merged[field] = _merge_relation_set(
                field, base_val, target_val, source_val,
                entity_type, entity_uuid, entity_name,
                parent_uuid, parent_type, name_index,
                resolutions, conflicts,
            )
        else:
            # 单值关系（父/拥有者引用）走同一字段规则，冲突类型为身份/父层级。
            merged[field] = _merge_field(
                field,
                base_val,
                target_val,
                source_val,
                "object_identity_parent",
                entity_type, entity_uuid, entity_name, field,
                parent_uuid, parent_type, resolutions, conflicts,
                name_index=name_index,
                related_entity_type=related_type,
            )

    return merged


def _merge_ordered_items(
    child_type: str,
    list_key: str,
    base_list: list[dict[str, Any]],
    target_list: list[dict[str, Any]],
    source_list: list[dict[str, Any]],
    parent_uuid: str | None,
    parent_type: str | None,
    resolutions: dict[str, dict[str, Any]] | None,
    conflicts: list[dict[str, Any]],
    name_index: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """合并有序子对象集合，并对齐最终位置。

    位置规则（阶段 6）：
      1. base 已有且未删除的项按 base 顺序保留；仅单侧改动的项保持原位；
      2. 两侧对同一项给出不同重排时才产生 same_position_order 冲突；
      3. 新增项确定性追加到末尾；
      4. 最终按 (position, logical_uuid) 重编号为 0..n-1，消除 (parent, position) 唯一约束冲突。
    """
    base_map = {e["logical_uuid"]: e for e in base_list}
    target_map = {e["logical_uuid"]: e for e in target_list}
    source_map = {e["logical_uuid"]: e for e in source_list}

    kept: dict[str, dict[str, Any]] = {}
    for entity_uuid in sorted(set(base_map) | set(target_map) | set(source_map)):
        b = base_map.get(entity_uuid)
        t = target_map.get(entity_uuid)
        s = source_map.get(entity_uuid)

        if b is None and t is None and s is None:
            continue
        if b is not None and t is None and s is None:
            continue  # 两侧都删除

        # 单侧新增（另一侧不存在）→ 自动保留新增对象。
        if b is None and t is not None and s is None:
            kept[entity_uuid] = t
            continue
        if b is None and t is None and s is not None:
            kept[entity_uuid] = s
            continue

        if t is None and s is not None:
            # target 删除，source 保留/改动
            if s == b:
                continue  # source 未改，删除生效
            conflict = _make_conflict(
                "delete_vs_modify", child_type, entity_uuid,
                _display_name(s), list_key, b, None, s,
                parent_uuid, parent_type,
            )
            resolved, chosen = _resolve_value(conflict, resolutions)
            if resolved:
                if chosen is not None:
                    kept[entity_uuid] = chosen
            else:
                conflicts.append(conflict)
            continue

        if s is None and t is not None:
            if t == b:
                continue
            conflict = _make_conflict(
                "delete_vs_modify", child_type, entity_uuid,
                _display_name(t), list_key, b, t, None,
                parent_uuid, parent_type,
            )
            resolved, chosen = _resolve_value(conflict, resolutions)
            if resolved:
                if chosen is not None:
                    kept[entity_uuid] = chosen
            else:
                conflicts.append(conflict)
            continue

        # t 与 s 都存在：合并字段（b 可能缺失 = 两侧各自新增）。
        kept[entity_uuid] = _merge_entity(
            child_type,
            b or {},
            t or {},
            s or {},
            resolutions, conflicts, name_index,
            parent_uuid, parent_type,
        )

    # 在 base 中存在的幸存项的相对顺序（只比较两侧都保留的项），用 uuid 字符串表示。
    base_uuids = [e["logical_uuid"] for e in base_list]
    common = [u for u in kept if u in set(base_uuids)]
    target_rel = [u["logical_uuid"] for u in target_list if u["logical_uuid"] in set(common)]
    source_rel = [u["logical_uuid"] for u in source_list if u["logical_uuid"] in set(common)]
    base_rel = [u["logical_uuid"] for u in base_list if u["logical_uuid"] in set(common)]

    if target_rel == source_rel:
        order_seq = target_rel
    elif target_rel == base_rel:
        order_seq = source_rel
    elif source_rel == base_rel:
        order_seq = target_rel
    else:
        # 两侧以不同方式重排同一项：产生排序冲突，未解决时取 target 顺序。
        moved = [u for u in common if target_rel.index(u) != source_rel.index(u)]
        conflict = _make_conflict(
            "same_position_order", child_type,
            moved[0] if moved else common[0],
            kept.get(moved[0] if moved else common[0], {}).get("name", ""),
            "position", base_rel, target_rel, source_rel,
            parent_uuid, parent_type,
        )
        resolved, chosen = _resolve_value(conflict, resolutions)
        if resolved:
            order_seq = chosen
        else:
            conflicts.append(conflict)
            order_seq = target_rel

    final_uuids = [u for u in order_seq if u in kept]
    target_new_order = [
        e["logical_uuid"]
        for e in sorted(
            target_list,
            key=lambda e: (e.get("position", 0), e.get("logical_uuid", "")),
        )
        if e["logical_uuid"] not in base_map and e["logical_uuid"] in kept
    ]
    source_new_order = [
        e["logical_uuid"]
        for e in sorted(
            source_list,
            key=lambda e: (e.get("position", 0), e.get("logical_uuid", "")),
        )
        if e["logical_uuid"] not in base_map and e["logical_uuid"] in kept
    ]
    new_uuids = target_new_order + [
        u for u in source_new_order if u not in target_new_order
    ]

    # 同位置并发新增检测：两侧各自新增了项，且 target/source 在 base 的同一相对插入点新增。
    # 阶段文档要求“同位置排序竞争”产生冲突，而非静默按 UUID 排序丢弃两侧声明的位置。
    target_new = [u for u in new_uuids if u in target_map and u not in base_map]
    source_new = [u for u in new_uuids if u in source_map and u not in base_map]
    if target_new and source_new:
        # 以两侧新增项在各自按 position 排序后的列表中的索引作为插入点比较（相对 base 顺序）。
        target_full = [e["logical_uuid"] for e in sorted(target_list, key=lambda e: (e.get("position", 0), e.get("logical_uuid", "")))]
        source_full = [e["logical_uuid"] for e in sorted(source_list, key=lambda e: (e.get("position", 0), e.get("logical_uuid", "")))]
        target_positions = {u: target_full.index(u) for u in target_new}
        source_positions = {u: source_full.index(u) for u in source_new}
        competing = [
            (tu, su)
            for tu in target_new
            for su in source_new
            if target_positions[tu] == source_positions[su]
        ]
        if competing:
            tu, su = competing[0]
            conflict = _make_conflict(
                "same_position_order", child_type, tu,
                kept[tu].get("name", ""), "position",
                None, tu, su, parent_uuid, parent_type,
                competing_uuid=su,
            )
            resolved, chosen = _resolve_value(conflict, resolutions)
            if resolved:
                # 竞争位置排序：选择 target 则 tu 在前、su 在后；选择 source 反之。
                # 两者均不在 base 相对顺序中，按选择把竞争项排入 new_uuids 头部即可改变最终顺序。
                if chosen == su:
                    new_uuids = [su] + [u for u in new_uuids if u != su]
                else:
                    new_uuids = [tu] + [u for u in new_uuids if u != tu]
            else:
                conflicts.append(conflict)
                # 未解决时占位保留 target 新增项在前。

    final_uuids.extend(new_uuids)
    # 去重：确保 final_uuids 无重复（同位置冲突解决可能移动项）。
    seen: set[str] = set()
    deduped: list[str] = []
    for u in final_uuids:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    final_uuids = deduped

    # 位置重编号，保证每父位置唯一且确定。
    return [
        dict(kept[u], position=idx)
        for idx, u in enumerate(final_uuids)
    ]


def _merge_metadata(
    base: dict[str, Any],
    target: dict[str, Any],
    source: dict[str, Any],
    resolutions: dict[str, dict[str, Any]] | None,
    conflicts: list[dict[str, Any]],
) -> dict[str, Any]:
    """合并项目级元数据（用户需求、Kano 状态、阶段解锁）。"""
    merged: dict[str, Any] = {}
    for field, _kind in METADATA_FIELDS.items():
        merged[field] = _merge_field(
            field,
            base.get(field),
            target.get(field),
            source.get(field),
            "same_field_different_value",
            "project_metadata", "project", "", field,
            None, None, resolutions, conflicts,
        )
    return merged


def _merge_feature_relations(
    base_list: list[dict[str, Any]],
    target_list: list[dict[str, Any]],
    source_list: list[dict[str, Any]],
    resolutions: dict[str, dict[str, Any]] | None,
    conflicts: list[dict[str, Any]],
    name_index: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """合并功能树边集合：边以 logical_uuid 合并，位置按父功能分组重排。"""
    base_map = {e["logical_uuid"]: e for e in base_list}
    target_map = {e["logical_uuid"]: e for e in target_list}
    source_map = {e["logical_uuid"]: e for e in source_list}

    def _key(rel: dict[str, Any]) -> tuple[str, str]:
        return (rel.get("parent_feature_logical_uuid", ""), rel.get("child_feature_logical_uuid", ""))

    # 同一 (parent, child) 边被两侧以不同 logical_uuid 新增 → 冲突，避免合并后重复边。
    target_key_map: dict[tuple[str, str], str] = {}
    source_key_map: dict[tuple[str, str], str] = {}
    for rel in target_list:
        target_key_map.setdefault(_key(rel), rel["logical_uuid"])
    for rel in source_list:
        source_key_map.setdefault(_key(rel), rel["logical_uuid"])
    for edge_key in sorted(set(target_key_map) & set(source_key_map)):
        t_uuid = target_key_map[edge_key]
        s_uuid = source_key_map[edge_key]
        if t_uuid == s_uuid:
            continue
        conflict = _make_conflict(
            "object_identity_parent", "feature_relation", t_uuid,
            _display_name(target_map.get(t_uuid, {})), "feature_relations",
            None, t_uuid, s_uuid,
        )
        resolved, chosen = _resolve_value(conflict, resolutions)
        if resolved:
            if chosen == s_uuid:
                target_map.pop(t_uuid, None)
            else:
                source_map.pop(s_uuid, None)
        else:
            conflicts.append(conflict)
            source_map.pop(s_uuid, None)  # 占位保留 target 边

    all_uuids = sorted(set(base_map) | set(target_map) | set(source_map))
    kept: dict[str, dict[str, Any]] = {}
    for entity_uuid in all_uuids:
        b = base_map.get(entity_uuid)
        t = target_map.get(entity_uuid)
        s = source_map.get(entity_uuid)

        if b is None and t is None and s is None:
            continue
        if b is not None and t is None and s is None:
            continue
        # 单侧新增（另一侧不存在）→ 自动保留新增边。
        if b is None and t is not None and s is None:
            kept[entity_uuid] = t
            continue
        if b is None and t is None and s is not None:
            kept[entity_uuid] = s
            continue
        if t is None and s is not None:
            if s == b:
                continue
            conflict = _make_conflict(
                "delete_vs_modify", "feature_relation", entity_uuid,
                _display_name(s), "feature_relations", b, None, s,
            )
            resolved, chosen = _resolve_value(conflict, resolutions)
            if resolved and chosen is not None:
                kept[entity_uuid] = chosen
            elif not resolved:
                conflicts.append(conflict)
            continue
        if s is None and t is not None:
            if t == b:
                continue
            conflict = _make_conflict(
                "delete_vs_modify", "feature_relation", entity_uuid,
                _display_name(t), "feature_relations", b, t, None,
            )
            resolved, chosen = _resolve_value(conflict, resolutions)
            if resolved and chosen is not None:
                kept[entity_uuid] = chosen
            elif not resolved:
                conflicts.append(conflict)
            continue
        kept[entity_uuid] = _merge_entity(
            "feature_relation", b or {}, t or {}, s or {},
            resolutions, conflicts, name_index,
        )

    # 按父功能分组，组内按 position 重排并重编号。
    by_parent: dict[str, list[str]] = {}
    for entity_uuid, rel in kept.items():
        by_parent.setdefault(rel.get("parent_feature_logical_uuid", ""), []).append(entity_uuid)

    merged: list[dict[str, Any]] = []
    for parent_uuid in sorted(by_parent):
        uuids = by_parent[parent_uuid]
        # 各组须按 position 排序，位置比较才有意义（避免按 uuid 字典序误判插入点）。
        base_group = sorted(
            [base_map[u] for u in uuids if u in base_map],
            key=lambda r: (r.get("position", 0), r["logical_uuid"]),
        )
        target_group = sorted(
            [target_map[u] for u in uuids if u in target_map],
            key=lambda r: (r.get("position", 0), r["logical_uuid"]),
        )
        source_group = sorted(
            [source_map[u] for u in uuids if u in source_map],
            key=lambda r: (r.get("position", 0), r["logical_uuid"]),
        )
        merged.extend(
            _merge_ordered_items(
                "feature_relation", "feature_relations",
                base_group, target_group, source_group,
                parent_uuid, "feature",
                resolutions, conflicts, name_index,
            )
        )
    return merged


def _merge_collection(
    key: str,
    base_list: list[dict[str, Any]],
    target_list: list[dict[str, Any]],
    source_list: list[dict[str, Any]],
    entity_type: str,
    resolutions: dict[str, dict[str, Any]] | None,
    conflicts: list[dict[str, Any]],
    name_index: dict[str, dict[str, str]],
    parent_uuid: str | None = None,
    parent_type: str | None = None,
) -> list[dict[str, Any]]:
    """合并顶层集合（参与者、功能、场景、业务对象、流程、范围）。"""
    base_map = {e["logical_uuid"]: e for e in base_list}
    target_map = {e["logical_uuid"]: e for e in target_list}
    source_map = {e["logical_uuid"]: e for e in source_list}

    kept: list[dict[str, Any]] = []
    for entity_uuid in sorted(set(base_map) | set(target_map) | set(source_map)):
        b = base_map.get(entity_uuid)
        t = target_map.get(entity_uuid)
        s = source_map.get(entity_uuid)

        if b is None and t is None and s is None:
            continue
        if b is not None and t is None and s is None:
            continue  # 两侧都删除

        # 单侧新增（另一侧不存在）→ 自动保留新增对象。
        if b is None and t is not None and s is None:
            kept.append(t)
            continue
        if b is None and t is None and s is not None:
            kept.append(s)
            continue

        if t is None and s is not None:
            # target 删除，source 保留/改动
            if s == b:
                continue
            conflict = _make_conflict(
                "delete_vs_modify", entity_type, entity_uuid,
                _display_name(s), key, b, None, s,
                parent_uuid, parent_type,
            )
            resolved, chosen = _resolve_value(conflict, resolutions)
            if resolved:
                if chosen is not None:
                    kept.append(chosen)
            else:
                conflicts.append(conflict)
            continue

        if s is None and t is not None:
            if t == b:
                continue
            conflict = _make_conflict(
                "delete_vs_modify", entity_type, entity_uuid,
                _display_name(t), key, b, t, None,
                parent_uuid, parent_type,
            )
            resolved, chosen = _resolve_value(conflict, resolutions)
            if resolved:
                if chosen is not None:
                    kept.append(chosen)
            else:
                conflicts.append(conflict)
            continue

        merged_entity = _merge_entity(
            entity_type, b or {}, t or {}, s or {},
            resolutions, conflicts, name_index, parent_uuid, parent_type,
        )
        if entity_type == "business_object":
            merged_entity["attributes"] = _merge_collection(
                "attributes",
                (b or {}).get("attributes", []),
                t.get("attributes", []),
                s.get("attributes", []),
                "business_object_attribute",
                resolutions, conflicts, name_index,
                entity_uuid, entity_type,
            )
        kept.append(merged_entity)

    return kept


def _merge_ordered_parent_children(
    merged_raw: dict[str, Any],
    base_state: dict[str, Any],
    target_state: dict[str, Any],
    source_state: dict[str, Any],
    resolutions: dict[str, dict[str, Any]] | None,
    conflicts: list[dict[str, Any]],
    name_index: dict[str, dict[str, str]],
) -> None:
    """为含有序子对象的父对象（scenario.acceptance_criteria、flow.steps）合并子集合。"""
    for child_type, (parent_type, list_key) in ORDERED_CHILD_PARENTS.items():
        parent_key = _parent_collection_key(parent_type)
        base_by_parent = {e["logical_uuid"]: e for e in base_state.get(parent_key, [])}
        target_by_parent = {e["logical_uuid"]: e for e in target_state.get(parent_key, [])}
        source_by_parent = {e["logical_uuid"]: e for e in source_state.get(parent_key, [])}
        for parent_uuid in sorted(set(base_by_parent) | set(target_by_parent) | set(source_by_parent)):
            merged_parent = next(
                (e for e in merged_raw[parent_key] if e.get("logical_uuid") == parent_uuid),
                None,
            )
            if merged_parent is None:
                continue
            b_parent = base_by_parent.get(parent_uuid, {})
            t_parent = target_by_parent.get(parent_uuid, {})
            s_parent = source_by_parent.get(parent_uuid, {})
            merged_parent[list_key] = _merge_ordered_items(
                child_type, list_key,
                b_parent.get(list_key, []),
                t_parent.get(list_key, []),
                s_parent.get(list_key, []),
                parent_uuid, parent_type,
                resolutions, conflicts, name_index,
            )


def _default_transition_by_source(flow: dict[str, Any]) -> dict[str, str]:
    return {
        transition["source_step_logical_uuid"]: transition["logical_uuid"]
        for transition in flow.get("transitions", [])
        if transition.get("is_default")
    }


def _resolve_competing_default_transitions(
    merged_raw: dict[str, Any],
    base_state: dict[str, Any],
    target_state: dict[str, Any],
    source_state: dict[str, Any],
    resolutions: dict[str, dict[str, Any]] | None,
    conflicts: list[dict[str, Any]],
) -> None:
    """Detect branch-wide default choices that entity-local merging cannot see."""
    merged_flows = {flow["logical_uuid"]: flow for flow in merged_raw.get("flows", [])}
    base_flows = {flow["logical_uuid"]: flow for flow in base_state.get("flows", [])}
    target_flows = {flow["logical_uuid"]: flow for flow in target_state.get("flows", [])}
    source_flows = {flow["logical_uuid"]: flow for flow in source_state.get("flows", [])}

    for flow_uuid in sorted(set(base_flows) & set(target_flows) & set(source_flows)):
        merged_flow = merged_flows.get(flow_uuid)
        if merged_flow is None:
            continue
        base_defaults = _default_transition_by_source(base_flows[flow_uuid])
        target_defaults = _default_transition_by_source(target_flows[flow_uuid])
        source_defaults = _default_transition_by_source(source_flows[flow_uuid])
        for step_uuid in sorted(set(target_defaults) | set(source_defaults)):
            base_choice = base_defaults.get(step_uuid)
            target_choice = target_defaults.get(step_uuid)
            source_choice = source_defaults.get(step_uuid)
            if (
                target_choice in (source_choice, base_choice)
                or source_choice == base_choice
            ):
                continue
            conflict = _make_conflict(
                "competing_default_transition",
                "flow_step",
                step_uuid,
                "",
                "default_transition",
                base_choice,
                target_choice,
                source_choice,
                flow_uuid,
                "flow",
            )
            resolved, chosen = _resolve_value(conflict, resolutions)
            if not resolved:
                conflicts.append(conflict)
                chosen = target_choice
            for transition in merged_flow.get("transitions", []):
                if transition.get("source_step_logical_uuid") == step_uuid:
                    transition["is_default"] = transition.get("logical_uuid") == chosen


def _find_rule_parent_cycles(parent_by_rule: dict[str, str | None]) -> list[list[str]]:
    cycles: list[list[str]] = []
    completed: set[str] = set()
    for start in sorted(parent_by_rule):
        if start in completed:
            continue
        path: list[str] = []
        positions: dict[str, int] = {}
        current: str | None = start
        while current is not None and current in parent_by_rule and current not in completed:
            if current in positions:
                cycles.append(path[positions[current]:])
                break
            positions[current] = len(path)
            path.append(current)
            current = parent_by_rule[current]
        completed.update(path)
    return cycles


def _resolve_rule_parent_cycles(
    merged_raw: dict[str, Any],
    base_state: dict[str, Any],
    target_state: dict[str, Any],
    source_state: dict[str, Any],
    resolutions: dict[str, dict[str, Any]] | None,
    conflicts: list[dict[str, Any]],
) -> None:
    """Expose parent cycles created by combining otherwise independent rule edits."""
    merged_rules = {
        rule["logical_uuid"]: rule for rule in merged_raw.get("domain_rules", [])
    }
    parent_maps = []
    for state in (base_state, target_state, source_state):
        parent_maps.append({
            rule["logical_uuid"]: rule.get("parent_rule_logical_uuid")
            for rule in state.get("domain_rules", [])
        })
    merged_parents = {
        rule_uuid: rule.get("parent_rule_logical_uuid")
        for rule_uuid, rule in merged_rules.items()
    }
    for cycle in _find_rule_parent_cycles(merged_parents):
        cycle_key = sorted(cycle)[0]
        values = [
            {rule_uuid: parent_map.get(rule_uuid) for rule_uuid in sorted(cycle)}
            for parent_map in parent_maps
        ]
        conflict = _make_conflict(
            "rule_parent_cycle",
            "domain_rule",
            cycle_key,
            merged_rules[cycle_key].get("title", ""),
            "parent_rule_logical_uuid",
            values[0],
            values[1],
            values[2],
            cycle_members=sorted(cycle),
        )
        resolved, chosen = _resolve_value(conflict, resolutions)
        if not resolved:
            conflicts.append(conflict)
            chosen = values[1]
        if isinstance(chosen, dict):
            for rule_uuid, parent_uuid in chosen.items():
                if rule_uuid in merged_rules:
                    merged_rules[rule_uuid]["parent_rule_logical_uuid"] = parent_uuid


def _parent_collection_key(parent_type: str) -> str:
    """父对象类型 → 顶层集合键（ENTITY_TYPE_BY_COLLECTION 的反向映射）。"""
    for key, etype in ENTITY_TYPE_BY_COLLECTION.items():
        if etype == parent_type:
            return key
    raise ValueError(f"Unknown parent type '{parent_type}'")


def _canonicalize(merged_raw: dict[str, Any]) -> dict[str, Any]:
    """把合并结果经确定性序列化器归一化，保证与 Commit state_json 同构可哈希。"""
    return serialize_requirement_space(merged_raw)


def _build_auto_summary(
    base_state: dict[str, Any],
    target_state: dict[str, Any],
    source_state: dict[str, Any],
    conflict_count: int,
) -> dict[str, int]:
    """汇总合并统计：触及对象数、自动合并数、冲突数。"""
    changed = 0
    auto = 0
    for key in COLLECTION_KEYS:
        base_map = {e["logical_uuid"]: e for e in base_state.get(key, [])}
        target_map = {e["logical_uuid"]: e for e in target_state.get(key, [])}
        source_map = {e["logical_uuid"]: e for e in source_state.get(key, [])}
        for uuid in set(base_map) | set(target_map) | set(source_map):
            b = base_map.get(uuid)
            t = target_map.get(uuid)
            s = source_map.get(uuid)
            if (t is not None and t != b) or (s is not None and s != b):
                changed += 1
                if t in (s, b) or s == b:
                    auto += 1
    for field in METADATA_FIELDS:
        b = base_state.get("project_metadata", {}).get(field)
        t = target_state.get("project_metadata", {}).get(field)
        s = source_state.get("project_metadata", {}).get(field)
        if (t != b) or (s != b):
            changed += 1
            if t in (s, b) or s == b:
                auto += 1
    return {
        "total_changed": changed,
        "total_auto_merged": auto,
        "total_conflicts": conflict_count,
    }


def compute_three_way_merge(
    base_state: dict[str, Any],
    target_state: dict[str, Any],
    source_state: dict[str, Any],
    resolutions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    计算 base/target/source 三方语义合并。

    :param base_state: 共同祖先的规范化状态（通常来自 merge base Commit）
    :param target_state: 目标分支 head 的规范化状态
    :param source_state: 来源分支 head 的规范化状态
    :param resolutions: conflict_id → {"choice": "target"|"source"|"manual", "manual_value"?}
    :return: {"merged_state": 规范化状态, "conflicts": 未解决冲突列表, "auto_merged": 统计}
    """
    name_index = _build_name_index(base_state, target_state, source_state)
    conflicts: list[dict[str, Any]] = []

    merged_raw: dict[str, Any] = {
        "project_metadata": _merge_metadata(
            base_state.get("project_metadata", {}),
            target_state.get("project_metadata", {}),
            source_state.get("project_metadata", {}),
            resolutions,
            conflicts,
        ),
    }

    for key in COLLECTION_KEYS:
        entity_type = ENTITY_TYPE_BY_COLLECTION[key]
        if key == "feature_relations":
            merged_raw[key] = _merge_feature_relations(
                base_state.get(key, []),
                target_state.get(key, []),
                source_state.get(key, []),
                resolutions, conflicts, name_index,
            )
        else:
            merged_raw[key] = _merge_collection(
                key,
                base_state.get(key, []),
                target_state.get(key, []),
                source_state.get(key, []),
                entity_type,
                resolutions, conflicts, name_index,
            )

    _merge_ordered_parent_children(
        merged_raw, base_state, target_state, source_state,
        resolutions, conflicts, name_index,
    )
    _resolve_competing_default_transitions(
        merged_raw,
        base_state,
        target_state,
        source_state,
        resolutions,
        conflicts,
    )
    _resolve_rule_parent_cycles(
        merged_raw,
        base_state,
        target_state,
        source_state,
        resolutions,
        conflicts,
    )

    merged_state = _canonicalize(merged_raw)
    auto_merged = _build_auto_summary(base_state, target_state, source_state, len(conflicts))
    return {
        "merged_state": merged_state,
        "conflicts": conflicts,
        "auto_merged": auto_merged,
    }
