"""
Tests for the Semantic Requirement-Space Diff Engine.
覆盖阶段 03 验收：字段修改、关系增减、顺序调整、对象增删、logical_uuid 对齐、空 Diff。
"""
from backend.api.modules.version_control.domain.semantic_diff import compute_semantic_diff


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


def _entry(entries, change_type):
    return [e for e in entries if e["change_type"] == change_type]


def test_identical_states_produce_empty_diff():
    """相同状态与自身比较应为空 Diff（无任何条目，汇总为 0）。"""
    state = _make_state(features=[_feature("f1", "订单支付", "描述")])
    result = compute_semantic_diff(state, state)
    assert result["entries"] == []
    assert result["summary"]["total_added"] == 0
    assert result["summary"]["total_removed"] == 0
    assert result["summary"]["total_modified"] == 0


def test_field_change_is_classified_correctly():
    """只修改功能描述 → field_changed 携带 before/after，且对象标记为已修改。"""
    base = _make_state(features=[_feature("f1", "订单支付", "旧描述")])
    target = _make_state(features=[_feature("f1", "订单支付", "新描述")])
    result = compute_semantic_diff(base, target)

    field_entries = _entry(result["entries"], "field_changed")
    assert len(field_entries) == 1
    field = field_entries[0]
    assert field["entity_uuid"] == "f1"
    assert field["field"] == "description"
    assert field["before"] == "旧描述"
    assert field["after"] == "新描述"
    # 文本字段附带行级片段
    assert field["text_blocks"] and field["text_blocks"][0]["kind"] == "replace"
    assert len(_entry(result["entries"], "entity_updated")) == 1
    assert result["summary"]["by_type"]["feature"]["modified"] == 1
    # 不出现增删
    assert not _entry(result["entries"], "entity_added")
    assert not _entry(result["entries"], "entity_removed")


def test_logical_uuid_alignment_instead_of_physical_identity():
    """同一 logical_uuid 的对象应被识别为更新，而不是先删后增。"""
    base = _make_state(features=[_feature("same-uuid", "旧名", "描述")])
    target = _make_state(features=[_feature("same-uuid", "新名", "描述")])
    result = compute_semantic_diff(base, target)
    assert not _entry(result["entries"], "entity_added")
    assert not _entry(result["entries"], "entity_removed")
    assert len(_entry(result["entries"], "entity_updated")) == 1


def test_relation_added_and_removed():
    """功能参与者关系增减 → relation_added / relation_removed，并携带另一端 UUID 与名称。"""
    base = _make_state(
        actors=[
            {"logical_uuid": "a1", "name": "用户", "description": "", "confirmation_status": "ai_assumption"},
            {"logical_uuid": "a2", "name": "管理员", "description": "", "confirmation_status": "ai_assumption"},
        ],
        features=[_feature("f1", "订单支付", "", actor_uuids=["a1"])],
    )
    target = _make_state(
        actors=[
            {"logical_uuid": "a1", "name": "用户", "description": "", "confirmation_status": "ai_assumption"},
            {"logical_uuid": "a2", "name": "管理员", "description": "", "confirmation_status": "ai_assumption"},
        ],
        features=[_feature("f1", "订单支付", "", actor_uuids=["a1", "a2"])],
    )
    result = compute_semantic_diff(base, target)

    added = _entry(result["entries"], "relation_added")
    removed = _entry(result["entries"], "relation_removed")
    assert len(added) == 1
    assert added[0]["related_entity_uuid"] == "a2"
    assert added[0]["related_entity_name"] == "管理员"
    assert added[0]["relation_type"] == "actor_logical_uuids"
    assert not removed


def test_entity_added_and_removed():
    """新增与删除对象 → entity_added / entity_removed，携带完整对象值供阅读旧值。"""
    base = _make_state(actors=[{"logical_uuid": "a1", "name": "用户", "description": "", "confirmation_status": "ai_assumption"}])
    target = _make_state(
        actors=[
            {"logical_uuid": "a1", "name": "用户", "description": "", "confirmation_status": "ai_assumption"},
            {"logical_uuid": "a2", "name": "运营", "description": "", "confirmation_status": "ai_assumption"},
        ]
    )
    result = compute_semantic_diff(base, target)
    assert len(_entry(result["entries"], "entity_added")) == 1
    assert result["summary"]["by_type"]["actor"]["added"] == 1
    assert result["summary"]["total_added"] == 1

    result = compute_semantic_diff(target, base)
    removed = _entry(result["entries"], "entity_removed")
    assert len(removed) == 1
    assert removed[0]["entity_uuid"] == "a2"
    assert removed[0]["before"]["name"] == "运营"


def test_flow_step_reorder_is_moved():
    """只调整流程步骤顺序 → ordered_item_moved，而不是把位置当成普通字段变更。"""
    base_steps = [_step("s1", 0, "步骤一"), _step("s2", 1, "步骤二"), _step("s3", 2, "步骤三")]
    target_steps = [_step("s1", 0, "步骤一"), _step("s3", 1, "步骤三"), _step("s2", 2, "步骤二")]
    base = _make_state(flows=[_flow("flow1", "支付流程", base_steps)])
    target = _make_state(flows=[_flow("flow1", "支付流程", target_steps)])
    result = compute_semantic_diff(base, target)

    moves = _entry(result["entries"], "ordered_item_moved")
    assert len(moves) >= 1
    moved = moves[0]
    assert moved["entity_type"] == "flow_step"
    assert moved["parent_uuid"] == "flow1"
    assert moved["after_position"] < moved["before_position"] or moved["after_position"] > moved["before_position"]
    # 父流程因此标记为已修改
    assert len(_entry(result["entries"], "entity_updated")) >= 1


def test_inserting_step_does_not_flag_siblings_as_moved():
    """在流程中插入新步骤时，相邻步骤不应被误判为位置移动。"""
    base_steps = [_step("s1", 0, "A"), _step("s2", 1, "B")]
    target_steps = [_step("s1", 0, "A"), _step("s_new", 1, "NEW"), _step("s2", 2, "B")]
    base = _make_state(flows=[_flow("flow1", "支付流程", base_steps)])
    target = _make_state(flows=[_flow("flow1", "支付流程", target_steps)])
    result = compute_semantic_diff(base, target)

    assert len(_entry(result["entries"], "ordered_item_moved")) == 0
    assert len(_entry(result["entries"], "entity_added")) == 1  # 仅新增的步骤
    added = _entry(result["entries"], "entity_added")[0]
    assert added["entity_uuid"] == "s_new"
    assert added["parent_uuid"] == "flow1"


def test_feature_tree_reorder_is_moved():
    """功能树子节点顺序调整 → feature_relation 被标记为 ordered_item_moved。"""
    common_features = [
        _feature("root", "根"),
        _feature("childA", "子 A"),
        _feature("childB", "子 B"),
    ]
    base_rels = [
        {"logical_uuid": "r1", "parent_feature_logical_uuid": "root", "child_feature_logical_uuid": "childA", "position": 0},
        {"logical_uuid": "r2", "parent_feature_logical_uuid": "root", "child_feature_logical_uuid": "childB", "position": 1},
    ]
    target_rels = [
        {"logical_uuid": "r2", "parent_feature_logical_uuid": "root", "child_feature_logical_uuid": "childB", "position": 0},
        {"logical_uuid": "r1", "parent_feature_logical_uuid": "root", "child_feature_logical_uuid": "childA", "position": 1},
    ]
    base = _make_state(features=common_features, feature_relations=base_rels)
    target = _make_state(features=common_features, feature_relations=target_rels)
    result = compute_semantic_diff(base, target)

    moves = _entry(result["entries"], "ordered_item_moved")
    assert len(moves) >= 1
    assert moves[0]["entity_type"] == "feature_relation"
    assert moves[0]["parent_type"] == "feature"


def test_project_metadata_change():
    """项目元数据（用户需求）变更 → field_changed 且归入 project_metadata 类型。"""
    base = _make_state()
    target = _make_state(
        project_metadata={
            "user_requirements": "新的需求说明",
            "kano_status": "missing",
            "unlocked_stages": "",
        }
    )
    result = compute_semantic_diff(base, target)
    fields = _entry(result["entries"], "field_changed")
    assert any(f["entity_type"] == "project_metadata" and f["field"] == "user_requirements" for f in fields)
    assert result["summary"]["by_type"]["project_metadata"]["modified"] == 1


def test_nested_acceptance_criterion_added():
    """场景内新增验收标准 → entity_added 挂在场景父上下文下。"""
    base_scenario = {
        "logical_uuid": "sc1",
        "feature_logical_uuid": "f1",
        "actor_logical_uuid": "a1",
        "name": "支付场景",
        "content": "",
        "confirmation_status": "ai_assumption",
        "acceptance_criteria": [
            {"logical_uuid": "ac1", "position": 0, "content": "支付成功", "confirmation_status": "ai_assumption"}
        ],
    }
    target_scenario = dict(base_scenario)
    target_scenario["acceptance_criteria"] = base_scenario["acceptance_criteria"] + [
        {"logical_uuid": "ac2", "position": 1, "content": "退款完成", "confirmation_status": "ai_assumption"}
    ]
    base = _make_state(
        actors=[{"logical_uuid": "a1", "name": "用户", "description": "", "confirmation_status": "ai_assumption"}],
        features=[_feature("f1", "订单支付")],
        scenarios=[base_scenario],
    )
    target = _make_state(
        actors=[{"logical_uuid": "a1", "name": "用户", "description": "", "confirmation_status": "ai_assumption"}],
        features=[_feature("f1", "订单支付")],
        scenarios=[target_scenario],
    )
    result = compute_semantic_diff(base, target)

    added = _entry(result["entries"], "entity_added")
    assert len(added) == 1
    assert added[0]["entity_type"] == "acceptance_criterion"
    assert added[0]["entity_uuid"] == "ac2"
    assert added[0]["parent_uuid"] == "sc1"
    assert result["summary"]["by_type"]["acceptance_criterion"]["added"] == 1
