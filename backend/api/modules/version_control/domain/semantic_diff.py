"""
Semantic Requirement-Space Diff Engine.
在两份规范化状态字典（同构于 Commit state_json）之间计算需求空间语义差异，而不是通用 JSON 差异。

对齐规则：对象一律按 logical_uuid 匹配（跨分支复制后物理 ID 不同，不可用于对齐）。
变更分类：
  - entity_added / entity_removed / entity_updated：对象级别的树节点；
  - field_changed：标量字段前后值，文本字段附带行级片段；
  - relation_added / relation_removed：关系增减，携带另一端 UUID 与类型；
  - ordered_item_moved：有序集合（功能树位置、验收标准、流程步骤）的相对顺序变化。
"""
import difflib
from collections import defaultdict
from typing import Any

# 规范化状态顶层集合 → 对象类型
COLLECTION_KEYS: list[str] = [
    "actors",
    "features",
    "feature_relations",
    "scenarios",
    "business_objects",
    "flows",
    "scopes",
]

ENTITY_TYPE_BY_COLLECTION: dict[str, str] = {
    "actors": "actor",
    "features": "feature",
    "feature_relations": "feature_relation",
    "scenarios": "scenario",
    "business_objects": "business_object",
    "flows": "flow",
    "scopes": "scope",
}

# 各对象类型的标量字段（不含 position：有序集合的位置差异由 ordered_item_moved 表达）
SCALAR_FIELDS: dict[str, list[str]] = {
    "actor": ["name", "description", "confirmation_status"],
    "feature": ["name", "description", "confirmation_status"],
    "feature_relation": [],
    "scenario": ["name", "content", "confirmation_status"],
    "acceptance_criterion": ["content", "confirmation_status"],
    "business_object": ["name", "description", "confirmation_status"],
    "business_object_attribute": [
        "name",
        "description",
        "data_type",
        "example",
        "confirmation_status",
    ],
    "flow": ["name", "description", "confirmation_status"],
    "flow_step": ["name", "description", "step_type", "confirmation_status"],
    "scope": [
        "status",
        "positive_summary",
        "negative_summary",
        "reason",
        "kano_category",
        "kano_category_name",
        "confirmation_status",
    ],
}

# 需要行级文本片段的文本字段
TEXT_FIELDS: dict[str, set[str]] = {
    "actor": {"description"},
    "feature": {"description"},
    "scenario": {"name", "content"},
    "acceptance_criterion": {"content"},
    "business_object": {"description"},
    "business_object_attribute": {"description", "example"},
    "flow": {"description"},
    "flow_step": {"name", "description"},
    "scope": {"positive_summary", "negative_summary", "reason"},
}

# 关系字段：字段名 → 另一端对象类型。值为 list 时按集合比较，单值时按前后值比较。
RELATION_FIELDS: dict[str, dict[str, str]] = {
    "feature": {"actor_logical_uuids": "actor"},
    "scenario": {
        "feature_logical_uuid": "feature",
        "actor_logical_uuid": "actor",
    },
    "flow": {"feature_logical_uuids": "feature"},
    "flow_step": {
        "actor_logical_uuids": "actor",
        "input_business_object_logical_uuids": "business_object",
        "output_business_object_logical_uuids": "business_object",
        "next_step_logical_uuids": "flow_step",
    },
    "scope": {"feature_logical_uuid": "feature"},
    "feature_relation": {
        "parent_feature_logical_uuid": "feature",
        "child_feature_logical_uuid": "feature",
    },
}

# 项目元数据字段及是否文本
METADATA_FIELDS: dict[str, str] = {
    "user_requirements": "text",
    "kano_status": "enum",
    "unlocked_stages": "enum",
}

# 有序集合子对象类型 → (父对象类型, 父状态内列表键)
ORDERED_CHILD_PARENTS: dict[str, tuple[str, str]] = {
    "acceptance_criterion": ("scenario", "acceptance_criteria"),
    "flow_step": ("flow", "steps"),
}

_CHANGE_RANK: dict[str, int] = {
    "entity_updated": 0,
    "field_changed": 1,
    "relation_removed": 2,
    "relation_added": 3,
    "ordered_item_moved": 4,
    "entity_removed": 5,
    "entity_added": 6,
}


def _display_name(entity: dict[str, Any]) -> str:
    """从对象字典中取一个适合树节点展示的名字。"""
    for key in ("name", "content", "title"):
        value = entity.get(key)
        if value:
            return value
    return entity.get("logical_uuid", "")


def _index_entity(
    index: dict[str, dict[str, str]],
    entity: dict[str, Any],
    entity_type: str,
) -> None:
    """把对象及其展示名登记进名称索引（首次命中保留，便于 base/target 都可用）。"""
    entity_uuid = entity.get("logical_uuid")
    if entity_uuid and entity_uuid not in index:
        index[entity_uuid] = {
            "entity_type": entity_type,
            "name": _display_name(entity),
        }


def _build_name_index(
    base_state: dict[str, Any],
    target_state: dict[str, Any],
) -> dict[str, dict[str, str]]:
    """构建 uuid → (对象类型, 展示名) 的全局索引，供关系另一端命名与缺失节点补全使用。"""
    index: dict[str, dict[str, str]] = {}
    for state in (base_state, target_state):
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
    index["project"] = {"entity_type": "project_metadata", "name": ""}
    return index


def _text_diff(before: Any, after: Any) -> list[dict[str, Any]]:
    """对文本字段做行级差异，输出红删绿增的统一视图片段。"""
    before_text = "" if before is None else str(before)
    after_text = "" if after is None else str(after)
    if before_text == after_text:
        return []
    before_lines = before_text.splitlines()
    after_lines = after_text.splitlines()
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)
    blocks: list[dict[str, Any]] = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            continue
        kind = {"replace": "replace", "delete": "remove", "insert": "add"}.get(op, "replace")
        blocks.append(
            {
                "kind": kind,
                "before_lines": before_lines[i1:i2],
                "after_lines": after_lines[j1:j2],
            }
        )
    return blocks


def _longest_common_subsequence(a: list[str], b: list[str]) -> list[str]:
    """返回 a、b 的最长公共子序列（回溯采用确定性的偏上选择，保证结果稳定）。"""
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    result: list[str] = []
    i, j = n, m
    while i > 0 and j > 0:
        if a[i - 1] == b[j - 1]:
            result.append(a[i - 1])
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    result.reverse()
    return result


def _order_moves(
    entity_type: str,
    base_list: list[dict[str, Any]],
    target_list: list[dict[str, Any]],
    parent_uuid: str,
    parent_type: str,
) -> list[dict[str, Any]]:
    """检测有序集合内的相对顺序变化，仅把真正调整位置的项标为 ordered_item_moved。

    插入/删除导致的整体位移不会误报：只对两侧都存在的项比较相对顺序。
    """
    base_ordered = sorted(base_list, key=lambda e: (e.get("position", 0), e.get("logical_uuid", "")))
    target_ordered = sorted(target_list, key=lambda e: (e.get("position", 0), e.get("logical_uuid", "")))
    base_seq = [e["logical_uuid"] for e in base_ordered]
    target_seq = [e["logical_uuid"] for e in target_ordered]
    common = set(base_seq) & set(target_seq)
    if len(common) < 2:
        return []

    kept = _longest_common_subsequence(
        [u for u in base_seq if u in common],
        [u for u in target_seq if u in common],
    )
    moved_uuids = sorted(u for u in common if u not in set(kept))
    if not moved_uuids:
        return []

    base_map = {e["logical_uuid"]: e for e in base_list}
    target_map = {e["logical_uuid"]: e for e in target_list}
    moves: list[dict[str, Any]] = []
    for entity_uuid in moved_uuids:
        before = base_map[entity_uuid]
        after = target_map[entity_uuid]
        moves.append(
            {
                "change_type": "ordered_item_moved",
                "entity_type": entity_type,
                "entity_uuid": entity_uuid,
                "entity_name": _display_name(after),
                "parent_uuid": parent_uuid,
                "parent_type": parent_type,
                "path": "position",
                "before_position": before.get("position", 0),
                "after_position": after.get("position", 0),
            }
        )
    return moves


def _relation_entry(
    change_type: str,
    entity_type: str,
    entity_uuid: str,
    entity_name: str,
    field: str,
    related_type: str,
    related_uuid: str,
    parent_uuid: str | None,
    parent_type: str | None,
    side: str,
    name_index: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """构造一条关系增减条目，携带另一端对象类型、UUID 与展示名。"""
    return {
        "change_type": change_type,
        "entity_type": entity_type,
        "entity_uuid": entity_uuid,
        "entity_name": entity_name,
        "parent_uuid": parent_uuid,
        "parent_type": parent_type,
        "path": field,
        "relation_type": field,
        "related_entity_type": related_type,
        "related_entity_uuid": related_uuid,
        "related_entity_name": name_index.get(related_uuid, {}).get("name", ""),
        "before": related_uuid if side == "before" else None,
        "after": related_uuid if side == "after" else None,
    }


def _diff_children(
    entity_type: str,
    base_list: list[dict[str, Any]],
    target_list: list[dict[str, Any]],
    parent_uuid: str,
    parent_type: str,
    out: list[dict[str, Any]],
    name_index: dict[str, dict[str, str]],
) -> None:
    """差异嵌套子对象（验收标准、步骤、属性），以父对象为上下文输出增删改分组。"""
    base_map = {e["logical_uuid"]: e for e in base_list}
    target_map = {e["logical_uuid"]: e for e in target_list}
    for entity_uuid in sorted(set(base_map) - set(target_map)):
        out.append(
            {
                "change_type": "entity_removed",
                "entity_type": entity_type,
                "entity_uuid": entity_uuid,
                "entity_name": _display_name(base_map[entity_uuid]),
                "parent_uuid": parent_uuid,
                "parent_type": parent_type,
                "path": entity_type,
                "before": base_map[entity_uuid],
            }
        )
    for entity_uuid in sorted(set(target_map) - set(base_map)):
        out.append(
            {
                "change_type": "entity_added",
                "entity_type": entity_type,
                "entity_uuid": entity_uuid,
                "entity_name": _display_name(target_map[entity_uuid]),
                "parent_uuid": parent_uuid,
                "parent_type": parent_type,
                "path": entity_type,
                "after": target_map[entity_uuid],
            }
        )
    for entity_uuid in sorted(set(base_map) & set(target_map)):
        _diff_entity(entity_type, base_map[entity_uuid], target_map[entity_uuid], out, parent_uuid, parent_type, name_index)


def _diff_entity(
    entity_type: str,
    base: dict[str, Any],
    target: dict[str, Any],
    out: list[dict[str, Any]],
    parent_uuid: str | None,
    parent_type: str | None,
    name_index: dict[str, dict[str, str]],
) -> None:
    """差异单个对象：标量字段、关系增减，以及嵌套子对象与其顺序。"""
    if base == target:
        return
    entity_uuid = target["logical_uuid"]
    entity_name = _display_name(target)
    detail: list[dict[str, Any]] = []

    for field in SCALAR_FIELDS.get(entity_type, []):
        before = base.get(field)
        after = target.get(field)
        if before != after:
            detail.append(
                {
                    "change_type": "field_changed",
                    "entity_type": entity_type,
                    "entity_uuid": entity_uuid,
                    "entity_name": entity_name,
                    "parent_uuid": parent_uuid,
                    "parent_type": parent_type,
                    "path": field,
                    "field": field,
                    "before": before,
                    "after": after,
                    "text_blocks": _text_diff(before, after)
                    if field in TEXT_FIELDS.get(entity_type, set())
                    else [],
                }
            )

    for field, related_type in RELATION_FIELDS.get(entity_type, {}).items():
        before = base.get(field)
        after = target.get(field)
        if isinstance(before, list):
            before_set = set(before or [])
            after_set = set(after or [])
            for related_uuid in sorted(before_set - after_set):
                detail.append(
                    _relation_entry(
                        "relation_removed", entity_type, entity_uuid, entity_name, field,
                        related_type, related_uuid, parent_uuid, parent_type, "before", name_index,
                    )
                )
            for related_uuid in sorted(after_set - before_set):
                detail.append(
                    _relation_entry(
                        "relation_added", entity_type, entity_uuid, entity_name, field,
                        related_type, related_uuid, parent_uuid, parent_type, "after", name_index,
                    )
                )
        elif before != after:
            if before:
                detail.append(
                    _relation_entry(
                        "relation_removed", entity_type, entity_uuid, entity_name, field,
                        related_type, before, parent_uuid, parent_type, "before", name_index,
                    )
                )
            if after:
                detail.append(
                    _relation_entry(
                        "relation_added", entity_type, entity_uuid, entity_name, field,
                        related_type, after, parent_uuid, parent_type, "after", name_index,
                    )
                )

    if entity_type == "scenario":
        _diff_children(
            "acceptance_criterion",
            base.get("acceptance_criteria", []),
            target.get("acceptance_criteria", []),
            entity_uuid,
            "scenario",
            detail,
            name_index,
        )
        detail.extend(
            _order_moves(
                "acceptance_criterion",
                base.get("acceptance_criteria", []),
                target.get("acceptance_criteria", []),
                entity_uuid,
                "scenario",
            )
        )
    elif entity_type == "business_object":
        _diff_children(
            "business_object_attribute",
            base.get("attributes", []),
            target.get("attributes", []),
            entity_uuid,
            "business_object",
            detail,
            name_index,
        )
    elif entity_type == "flow":
        _diff_children(
            "flow_step",
            base.get("steps", []),
            target.get("steps", []),
            entity_uuid,
            "flow",
            detail,
            name_index,
        )
        detail.extend(
            _order_moves(
                "flow_step",
                base.get("steps", []),
                target.get("steps", []),
                entity_uuid,
                "flow",
            )
        )

    if detail:
        out.append(
            {
                "change_type": "entity_updated",
                "entity_type": entity_type,
                "entity_uuid": entity_uuid,
                "entity_name": entity_name,
                "parent_uuid": parent_uuid,
                "parent_type": parent_type,
                "path": entity_type,
            }
        )
        out.extend(detail)


def _diff_metadata(
    base_meta: dict[str, Any],
    target_meta: dict[str, Any],
    out: list[dict[str, Any]],
) -> None:
    """差异项目级元数据（用户需求、Kano 状态、阶段解锁）。"""
    base_meta = base_meta or {}
    target_meta = target_meta or {}
    for field, kind in METADATA_FIELDS.items():
        before = base_meta.get(field)
        after = target_meta.get(field)
        if before == after:
            continue
        out.append(
            {
                "change_type": "field_changed",
                "entity_type": "project_metadata",
                "entity_uuid": "project",
                "entity_name": "",
                "parent_uuid": None,
                "parent_type": None,
                "path": field,
                "field": field,
                "before": before,
                "after": after,
                "text_blocks": _text_diff(before, after) if kind == "text" else [],
            }
        )


def _diff_feature_relation_ordering(
    base_state: dict[str, Any],
    target_state: dict[str, Any],
) -> list[dict[str, Any]]:
    """按父功能分组检测功能树子节点顺序变化（功能树位置调整）。"""
    base_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    target_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rel in base_state.get("feature_relations", []):
        base_by_parent[rel.get("parent_feature_logical_uuid")].append(rel)
    for rel in target_state.get("feature_relations", []):
        target_by_parent[rel.get("parent_feature_logical_uuid")].append(rel)
    moves: list[dict[str, Any]] = []
    for parent_uuid in sorted(set(base_by_parent) & set(target_by_parent)):
        moves.extend(
            _order_moves(
                "feature_relation",
                base_by_parent[parent_uuid],
                target_by_parent[parent_uuid],
                parent_uuid,
                "feature",
            )
        )
    return moves


def _ensure_updated_nodes(
    entries: list[dict[str, Any]],
    name_index: dict[str, dict[str, str]],
) -> None:
    """为只有细节条目但缺失 entity_updated 节点的对象补节点（例如仅顺序变化、仅子对象变化的父对象）。"""
    changed_uuids: set[str] = set()
    entity_parent: dict[str, tuple[str | None, str | None]] = {}
    for entry in entries:
        if entry["change_type"] in ("entity_updated", "entity_added", "entity_removed"):
            continue
        changed_uuids.add(entry["entity_uuid"])
        if entry.get("parent_uuid"):
            entity_parent.setdefault(entry["entity_uuid"], (entry["parent_uuid"], entry["parent_type"]))
    existing = {entry["entity_uuid"] for entry in entries if entry["change_type"] == "entity_updated"}
    for entity_uuid in sorted(changed_uuids - existing):
        meta = name_index.get(entity_uuid, {"entity_type": "", "name": entity_uuid})
        parent_uuid, parent_type = entity_parent.get(entity_uuid, (None, None))
        entries.append(
            {
                "change_type": "entity_updated",
                "entity_type": meta.get("entity_type", ""),
                "entity_uuid": entity_uuid,
                "entity_name": meta.get("name", entity_uuid),
                "parent_uuid": parent_uuid,
                "parent_type": parent_type,
                "path": meta.get("entity_type", ""),
            }
        )


def _build_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """按对象类型与变更种类聚合汇总计数。"""
    by_type: dict[str, dict[str, int]] = {}
    for entry in entries:
        if entry["change_type"] not in ("entity_added", "entity_removed", "entity_updated"):
            continue
        type_summary = by_type.setdefault(
            entry["entity_type"], {"added": 0, "removed": 0, "modified": 0}
        )
        if entry["change_type"] == "entity_added":
            type_summary["added"] += 1
        elif entry["change_type"] == "entity_removed":
            type_summary["removed"] += 1
        else:
            type_summary["modified"] += 1
    total_added = sum(ts["added"] for ts in by_type.values())
    total_removed = sum(ts["removed"] for ts in by_type.values())
    total_modified = sum(ts["modified"] for ts in by_type.values())
    return {
        "by_type": by_type,
        "total_added": total_added,
        "total_removed": total_removed,
        "total_modified": total_modified,
    }


def find_entity_meta(
    base_state: dict[str, Any],
    target_state: dict[str, Any],
    entity_uuid: str,
) -> dict[str, str]:
    """在 base/target 状态中查找对象类型与展示名，供实体详情接口使用。"""
    return _build_name_index(base_state, target_state).get(entity_uuid, {})


def compute_semantic_diff(
    base_state: dict[str, Any],
    target_state: dict[str, Any],
) -> dict[str, Any]:
    """
    计算两份规范化状态之间的语义差异。

    :param base_state: 基线规范化状态（通常来自历史 Commit）
    :param target_state: 目标规范化状态（来自其他 Commit 或当前工作区）
    :return: {"summary": {...}, "entries": [...]}，entries 为确定的、可被 DiffEntry 契约校验的字典列表
    """
    name_index = _build_name_index(base_state, target_state)
    entries: list[dict[str, Any]] = []

    _diff_metadata(base_state.get("project_metadata", {}), target_state.get("project_metadata", {}), entries)

    for key in COLLECTION_KEYS:
        entity_type = ENTITY_TYPE_BY_COLLECTION[key]
        base_list = base_state.get(key, [])
        target_list = target_state.get(key, [])
        base_map = {e["logical_uuid"]: e for e in base_list}
        target_map = {e["logical_uuid"]: e for e in target_list}
        for entity_uuid in sorted(set(base_map) - set(target_map)):
            entries.append(
                {
                    "change_type": "entity_removed",
                    "entity_type": entity_type,
                    "entity_uuid": entity_uuid,
                    "entity_name": _display_name(base_map[entity_uuid]),
                    "parent_uuid": None,
                    "parent_type": None,
                    "path": entity_type,
                    "before": base_map[entity_uuid],
                }
            )
        for entity_uuid in sorted(set(target_map) - set(base_map)):
            entries.append(
                {
                    "change_type": "entity_added",
                    "entity_type": entity_type,
                    "entity_uuid": entity_uuid,
                    "entity_name": _display_name(target_map[entity_uuid]),
                    "parent_uuid": None,
                    "parent_type": None,
                    "path": entity_type,
                    "after": target_map[entity_uuid],
                }
            )
        for entity_uuid in sorted(set(base_map) & set(target_map)):
            _diff_entity(entity_type, base_map[entity_uuid], target_map[entity_uuid], entries, None, None, name_index)

    entries.extend(_diff_feature_relation_ordering(base_state, target_state))
    _ensure_updated_nodes(entries, name_index)

    # 稳定的全局排序：同一对象的节点在前，细节随后；对象间按类型与 UUID 排序。
    entries.sort(
        key=lambda e: (
            e["entity_type"],
            e["entity_uuid"],
            _CHANGE_RANK.get(e["change_type"], 99),
            e.get("path") or "",
        )
    )

    return {"summary": _build_summary(entries), "entries": entries}
