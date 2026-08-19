"""
Tests for the Three-Way Semantic Merge Engine (Phase 6).
覆盖阶段 06 验收：不相交字段自动合并、同字段冲突与解决、删除 vs 修改、关系相反操作、
排序竞争、feature 树合并、项目元数据冲突、conflict_id 稳定性。
"""
from backend.api.modules.version_control.domain.semantic_merge import compute_three_way_merge


def _make_state(**kwargs):
    """构造一份规范化状态字典；未给出的集合默认为空。"""
    state = {
        "schema_version": "1.0",
        "project_metadata": {
            "user_requirements": "",
            "kano_status": "missing",
            "unlocked_stages": "",
        },
        "actors": [],
        "features": [],
        "feature_relations": [],
        "scenarios": [],
        "business_objects": [],
        "flows": [],
        "scopes": [],
    }
    state.update(kwargs)
    return state


def _feature(uuid, name="功能", description="", actor_uuids=None):
    return {
        "logical_uuid": uuid,
        "name": name,
        "description": description,
        "confirmation_status": "ai_assumption",
        "actor_logical_uuids": actor_uuids or [],
    }


def _actor(uuid, name="参与者"):
    return {
        "logical_uuid": uuid,
        "name": name,
        "description": "",
        "confirmation_status": "ai_assumption",
    }


def _feature_relation(uuid, parent, child, position=0):
    return {
        "logical_uuid": uuid,
        "parent_feature_logical_uuid": parent,
        "child_feature_logical_uuid": child,
        "position": position,
    }


def _scenario(uuid, feature, actor, name="场景", content="", acs=None):
    return {
        "logical_uuid": uuid,
        "feature_logical_uuid": feature,
        "actor_logical_uuid": actor,
        "name": name,
        "content": content,
        "confirmation_status": "ai_assumption",
        "acceptance_criteria": acs or [],
    }


def _ac(uuid, position, content):
    return {
        "logical_uuid": uuid,
        "position": position,
        "content": content,
        "confirmation_status": "ai_assumption",
    }


def _step(uuid, position, name="步骤"):
    return {
        "logical_uuid": uuid,
        "position": position,
        "name": name,
        "description": "",
        "step_type": "task",
        "confirmation_status": "ai_assumption",
        "actor_logical_uuids": [],
        "input_business_object_logical_uuids": [],
        "output_business_object_logical_uuids": [],
        "next_step_logical_uuids": [],
    }


def _flow(uuid, name, steps):
    return {
        "logical_uuid": uuid,
        "name": name,
        "description": "",
        "confirmation_status": "ai_assumption",
        "feature_logical_uuids": [],
        "steps": steps,
    }


def test_disjoint_fields_auto_merge():
    """target 改 name、source 改 description → 合并同时保留两侧改动。"""
    base = _make_state(features=[_feature("F1", "F1", "base-desc")])
    target = _make_state(features=[_feature("F1", "F1-target", "base-desc")])
    source = _make_state(features=[_feature("F1", "F1", "source-desc")])
    result = compute_three_way_merge(base, target, source)
    assert result["conflicts"] == []
    merged = result["merged_state"]["features"][0]
    assert merged["name"] == "F1-target"
    assert merged["description"] == "source-desc"


def test_same_field_different_value_conflict_and_resolution():
    """两侧修改同一字段为不同值 → 冲突；resolution target/source 分别取对应值。"""
    base = _make_state(features=[_feature("F1", "F1", "base")])
    target = _make_state(features=[_feature("F1", "F1-t", "base")])
    source = _make_state(features=[_feature("F1", "F1-s", "base")])

    result = compute_three_way_merge(base, target, source)
    assert len(result["conflicts"]) == 1
    conflict = result["conflicts"][0]
    assert conflict["conflict_type"] == "same_field_different_value"
    assert conflict["entity_uuid"] == "F1"
    assert conflict["path"] == "name"
    assert conflict["base_value"] == "F1"
    assert conflict["target_value"] == "F1-t"
    assert conflict["source_value"] == "F1-s"

    cid = conflict["conflict_id"]
    r_target = compute_three_way_merge(
        base, target, source, resolutions={cid: {"choice": "target"}}
    )
    assert r_target["conflicts"] == []
    assert r_target["merged_state"]["features"][0]["name"] == "F1-t"

    r_source = compute_three_way_merge(
        base, target, source, resolutions={cid: {"choice": "source"}}
    )
    assert r_source["conflicts"] == []
    assert r_source["merged_state"]["features"][0]["name"] == "F1-s"


def test_one_sided_add_and_remove_auto_applied():
    """单侧新增对象、单侧删除对象 → 自动应用。"""
    base = _make_state(features=[_feature("F1")])
    target = _make_state(features=[_feature("F1"), _feature("F2", "target-added")])
    source = _make_state(features=[])
    result = compute_three_way_merge(base, target, source)
    # F2 新增自动应用；F1 被 source 删除且 target 未改 → 删除生效。
    assert result["conflicts"] == []
    uuids = {e["logical_uuid"] for e in result["merged_state"]["features"]}
    assert uuids == {"F2"}


def test_both_sides_remove_and_both_add_distinct():
    """两侧都删除 → 保持删除；两侧新增不同对象 → 都保留。"""
    base = _make_state(features=[_feature("F1")])
    target = _make_state(features=[_feature("F2", "t-add")])
    source = _make_state(features=[_feature("F3", "s-add")])
    result = compute_three_way_merge(base, target, source)
    assert result["conflicts"] == []
    uuids = {e["logical_uuid"] for e in result["merged_state"]["features"]}
    assert uuids == {"F2", "F3"}


def test_delete_vs_modify_conflict():
    """一侧删除、另一侧修改 → 冲突；未解决时合并状态排除被删实体。"""
    base = _make_state(features=[_feature("F1", "F1", "base")])
    target = _make_state(features=[_feature("F1", "F1-kept", "changed")])
    source = _make_state(features=[])
    result = compute_three_way_merge(base, target, source)
    assert len(result["conflicts"]) == 1
    assert result["conflicts"][0]["conflict_type"] == "delete_vs_modify"
    assert result["merged_state"]["features"] == []

    cid = result["conflicts"][0]["conflict_id"]
    r_target = compute_three_way_merge(
        base, target, source, resolutions={cid: {"choice": "target"}}
    )
    assert r_target["conflicts"] == []
    assert len(r_target["merged_state"]["features"]) == 1
    assert r_target["merged_state"]["features"][0]["name"] == "F1-kept"


def test_feature_relation_delete_vs_modify_conflict():
    """功能树边：一侧删除、另一侧修改同一条边 → delete_vs_modify 冲突。"""
    base = _make_state(
        features=[_feature("P", "父"), _feature("C", "子")],
        feature_relations=[_feature_relation("R1", "P", "C", 0)],
    )
    target = _make_state(
        features=[_feature("P", "父"), _feature("C", "子")],
        feature_relations=[_feature_relation("R1", "P", "C", 3)],
    )
    source = _make_state(
        features=[_feature("P", "父"), _feature("C", "子")],
        feature_relations=[],
    )
    result = compute_three_way_merge(base, target, source)
    assert len(result["conflicts"]) == 1
    assert result["conflicts"][0]["conflict_type"] == "delete_vs_modify"


def test_disjoint_relation_ops_auto_merge():
    """关系集合字段：一侧移除 A1、另一侧新增 A2（不同元素）→ 自动合并。"""
    base = _make_state(
        features=[_feature("F1", actor_uuids=["A1"])],
        actors=[_actor("A1")],
    )
    target = _make_state(
        features=[_feature("F1", actor_uuids=["A1", "A2"])],
        actors=[_actor("A1"), _actor("A2")],
    )
    source = _make_state(
        features=[_feature("F1", actor_uuids=[])],
        actors=[_actor("A1")],
    )
    result = compute_three_way_merge(base, target, source)
    assert result["conflicts"] == []
    assert set(result["merged_state"]["features"][0]["actor_logical_uuids"]) == {"A2"}


def test_same_position_order_conflict():
    """两侧对同一流程步骤给出不同重排 → 排序冲突；选中侧序列获胜。"""
    base = _make_state(flows=[_flow("FL1", "流程", [_step("S1", 0), _step("S2", 1), _step("S3", 2)])])
    target = _make_state(flows=[_flow("FL1", "流程", [_step("S2", 0), _step("S1", 1), _step("S3", 2)])])
    source = _make_state(flows=[_flow("FL1", "流程", [_step("S1", 0), _step("S3", 1), _step("S2", 2)])])

    result = compute_three_way_merge(base, target, source)
    assert len(result["conflicts"]) == 1
    assert result["conflicts"][0]["conflict_type"] == "same_position_order"

    cid = result["conflicts"][0]["conflict_id"]
    r_target = compute_three_way_merge(
        base, target, source, resolutions={cid: {"choice": "target"}}
    )
    assert r_target["conflicts"] == []
    steps = r_target["merged_state"]["flows"][0]["steps"]
    assert [s["logical_uuid"] for s in steps] == ["S2", "S1", "S3"]
    assert [s["position"] for s in steps] == [0, 1, 2]


def test_single_side_order_change_auto_applied():
    """仅一侧重排顺序 → 自动采用该侧顺序，不产生冲突。"""
    base = _make_state(flows=[_flow("FL1", "流程", [_step("S1", 0), _step("S2", 1)])])
    target = _make_state(flows=[_flow("FL1", "流程", [_step("S2", 0), _step("S1", 1)])])
    source = _make_state(flows=[_flow("FL1", "流程", [_step("S1", 0), _step("S2", 1)])])
    result = compute_three_way_merge(base, target, source)
    assert result["conflicts"] == []
    steps = result["merged_state"]["flows"][0]["steps"]
    assert [s["logical_uuid"] for s in steps] == ["S2", "S1"]


def test_feature_tree_same_position_concurrent_add_conflict():
    """两侧在 base 的同一相对插入点新增不同子边 → 产生 same_position_order 冲突。"""
    base = _make_state(
        features=[_feature("P", "父"), _feature("C1", "子1"), _feature("C2", "子2")],
        feature_relations=[
            _feature_relation("R1", "P", "C1", 0),
            _feature_relation("R2", "P", "C2", 1),
        ],
    )
    target = _make_state(
        features=[_feature("P", "父"), _feature("C1", "子1"), _feature("C2", "子2"), _feature("C3", "子3")],
        feature_relations=[
            _feature_relation("R1", "P", "C1", 0),
            _feature_relation("R2", "P", "C2", 1),
            _feature_relation("R3", "P", "C3", 2),
        ],
    )
    source = _make_state(
        features=[_feature("P", "父"), _feature("C1", "子1"), _feature("C2", "子2"), _feature("C4", "子4")],
        feature_relations=[
            _feature_relation("R1", "P", "C1", 0),
            _feature_relation("R2", "P", "C2", 1),
            _feature_relation("R4", "P", "C4", 2),
        ],
    )
    result = compute_three_way_merge(base, target, source)
    assert len(result["conflicts"]) == 1
    conflict = result["conflicts"][0]
    assert conflict["conflict_type"] == "same_position_order"
    assert conflict["competing_uuid"] == "R4"

    def _child_order(state):
        return [r["child_feature_logical_uuid"] for r in state["merged_state"]["feature_relations"]]

    # 选择 target：竞争位置由 target 新增项 R3 占据，source 新增项 R4 排在后面。
    r_target = compute_three_way_merge(
        base, target, source,
        resolutions={conflict["conflict_id"]: {"choice": "target"}},
    )
    assert r_target["conflicts"] == []
    order_target = _child_order(r_target)
    assert order_target.index("C3") < order_target.index("C4")
    positions = [r["position"] for r in r_target["merged_state"]["feature_relations"]]
    assert sorted(positions) == list(range(len(positions)))
    assert {r["child_feature_logical_uuid"] for r in r_target["merged_state"]["feature_relations"]} == {"C1", "C2", "C3", "C4"}

    # 选择 source：竞争位置由 source 新增项 R4 占据，target 新增项 R3 排在后面。
    r_source = compute_three_way_merge(
        base, target, source,
        resolutions={conflict["conflict_id"]: {"choice": "source"}},
    )
    assert r_source["conflicts"] == []
    order_source = _child_order(r_source)
    assert order_source.index("C4") < order_source.index("C3")
    # target/source 两种选择必须产生不同的相对顺序。
    assert order_target != order_source


def test_feature_tree_disjoint_position_add_auto_merge():
    """两侧在不同相对位置新增子边 → 自动合并，无冲突，重编号后位置唯一。"""
    base = _make_state(
        features=[_feature("P", "父"), _feature("C1", "子1"), _feature("C2", "子2")],
        feature_relations=[
            _feature_relation("R1", "P", "C1", 0),
            _feature_relation("R2", "P", "C2", 1),
        ],
    )
    # target 在开头新增（插入点 0），source 在末尾新增（插入点 2）。
    target = _make_state(
        features=[_feature("P", "父"), _feature("C1", "子1"), _feature("C2", "子2"), _feature("C3", "子3")],
        feature_relations=[
            _feature_relation("R3", "P", "C3", 0),
            _feature_relation("R1", "P", "C1", 1),
            _feature_relation("R2", "P", "C2", 2),
        ],
    )
    source = _make_state(
        features=[_feature("P", "父"), _feature("C1", "子1"), _feature("C2", "子2"), _feature("C4", "子4")],
        feature_relations=[
            _feature_relation("R1", "P", "C1", 0),
            _feature_relation("R2", "P", "C2", 1),
            _feature_relation("R4", "P", "C4", 2),
        ],
    )
    result = compute_three_way_merge(base, target, source)
    assert result["conflicts"] == []
    rels = result["merged_state"]["feature_relations"]
    positions = [r["position"] for r in rels]
    assert sorted(positions) == list(range(len(rels)))
    child_uuids = {r["child_feature_logical_uuid"] for r in rels}
    assert child_uuids == {"C1", "C2", "C3", "C4"}


def test_project_metadata_conflict_and_disjoint_auto():
    """user_requirements 同字段冲突 + kano_status 单侧改动自动合并。"""
    base = _make_state()
    base["project_metadata"] = {"user_requirements": "base", "kano_status": "missing", "unlocked_stages": ""}
    target = _make_state()
    target["project_metadata"] = {"user_requirements": "target-req", "kano_status": "missing", "unlocked_stages": ""}
    source = _make_state()
    source["project_metadata"] = {"user_requirements": "source-req", "kano_status": "pending", "unlocked_stages": ""}

    result = compute_three_way_merge(base, target, source)
    conflicts = [c for c in result["conflicts"] if c["entity_type"] == "project_metadata"]
    assert len(conflicts) == 1
    assert conflicts[0]["path"] == "user_requirements"
    # kano_status 仅 source 改动 → 自动采用 source。
    assert result["merged_state"]["project_metadata"]["kano_status"] == "pending"
    assert result["merged_state"]["project_metadata"]["unlocked_stages"] == ""

    cid = conflicts[0]["conflict_id"]
    r_target = compute_three_way_merge(
        base, target, source, resolutions={cid: {"choice": "target"}}
    )
    assert r_target["conflicts"] == []
    assert r_target["merged_state"]["project_metadata"]["user_requirements"] == "target-req"


def test_conflict_id_stable_across_recompute():
    """同一冲突在不同重算中产生相同 conflict_id。"""
    base = _make_state(features=[_feature("F1", "F1", "base")])
    target = _make_state(features=[_feature("F1", "F1-t", "base")])
    source = _make_state(features=[_feature("F1", "F1-s", "base")])
    r1 = compute_three_way_merge(base, target, source)
    r2 = compute_three_way_merge(base, target, source)
    assert r1["conflicts"][0]["conflict_id"] == r2["conflicts"][0]["conflict_id"]


def test_manual_resolution_value():
    """受限手工编辑：choice=manual 用 manual_value 覆盖字段值。"""
    base = _make_state(features=[_feature("F1", "F1", "base")])
    target = _make_state(features=[_feature("F1", "F1-t", "base")])
    source = _make_state(features=[_feature("F1", "F1-s", "base")])
    result = compute_three_way_merge(base, target, source)
    cid = result["conflicts"][0]["conflict_id"]
    r_manual = compute_three_way_merge(
        base, target, source,
        resolutions={cid: {"choice": "manual", "manual_value": "F1-custom"}},
    )
    assert r_manual["conflicts"] == []
    assert r_manual["merged_state"]["features"][0]["name"] == "F1-custom"
