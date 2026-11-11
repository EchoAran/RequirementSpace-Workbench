"""
Tests for Deterministic Requirement Space Serializer and SHA-256 Hasher.
验证相同模型状态反复序列化时的 JSON 与哈希绝对一致性、字段确定性排序和空值规范化。
"""
from backend.api.modules.version_control.domain.serializer import (
    compute_state_hash,
    serialize_requirement_space,
    to_deterministic_json,
)


def test_deterministic_serialization_identity():
    """验证包含混乱顺序输入的数据经过规范化序列化后，产生的 JSON 与 Hash 绝对一致。"""
    raw_data_1 = {
        "project_metadata": {
            "kano_status": "configured",
            "user_requirements": "Building a version control module for requirement space",
            "unlocked_stages": "what,flow,scope",
        },
        "actors": [
            {"logical_uuid": "uuid-actor-2", "name": "Admin", "description": "System Admin", "confirmation_status": "confirmed"},
            {"logical_uuid": "uuid-actor-1", "name": "Member", "description": "Project Member", "confirmation_status": "ai_assumption"},
        ],
        "features": [
            {
                "logical_uuid": "uuid-feature-1",
                "name": "Branching",
                "description": "Create and switch branches",
                "confirmation_status": "confirmed",
                "actor_logical_uuids": ["uuid-actor-2", "uuid-actor-1"],
            }
        ],
    }

    # 数据 2 调整键顺序和列表顺序，但逻辑内容与 数据 1 完全相同
    raw_data_2 = {
        "features": [
            {
                "actor_logical_uuids": ["uuid-actor-1", "uuid-actor-2"],
                "confirmation_status": "confirmed",
                "description": "Create and switch branches",
                "logical_uuid": "uuid-feature-1",
                "name": "Branching",
            }
        ],
        "actors": [
            {"confirmation_status": "ai_assumption", "description": "Project Member", "logical_uuid": "uuid-actor-1", "name": "Member"},
            {"confirmation_status": "confirmed", "description": "System Admin", "logical_uuid": "uuid-actor-2", "name": "Admin"},
        ],
        "project_metadata": {
            "unlocked_stages": "what,flow,scope",
            "user_requirements": "Building a version control module for requirement space",
            "kano_status": "configured",
        },
    }

    norm_1 = serialize_requirement_space(raw_data_1)
    norm_2 = serialize_requirement_space(raw_data_2)

    json_1 = to_deterministic_json(norm_1)
    json_2 = to_deterministic_json(norm_2)

    hash_1 = compute_state_hash(json_1)
    hash_2 = compute_state_hash(json_2)

    assert json_1 == json_2
    assert hash_1 == hash_2
    assert len(hash_1) == 64


def test_empty_workspace_serialization():
    """验证空需求空间能够正常生成规范模型与 Hash。"""
    raw_empty = {}
    norm = serialize_requirement_space(raw_empty)
    json_str = to_deterministic_json(norm)
    h = compute_state_hash(json_str)

    assert norm["schema_version"] == "2.0"
    assert norm["actors"] == []
    assert norm["features"] == []
    assert isinstance(json_str, str)
    assert len(h) == 64


def test_rule_and_transition_state_is_canonical_and_semantic():
    raw = {
        "flows": [
            {
                "logical_uuid": "flow-1",
                "steps": [
                    {"logical_uuid": "step-2", "position": 2},
                    {"logical_uuid": "step-1", "position": 1},
                ],
                "transitions": [
                    {
                        "logical_uuid": "transition-2",
                        "source_step_logical_uuid": "step-1",
                        "target_step_logical_uuid": "step-2",
                        "label": "approved",
                        "condition_text": "approval succeeds",
                        "is_default": False,
                        "position": 1,
                        "semantic_tags": ["success", "success", "review"],
                        "origin": "manual",
                        "confirmation_status": "confirmed",
                    }
                ],
            }
        ],
        "domain_rules": [
            {
                "logical_uuid": "rule-2",
                "parent_rule_logical_uuid": "rule-1",
                "title": "Detailed approval",
                "statement": "Managers approve high-value requests.",
                "origin": "flow_refinement",
                "confirmation_status": "needs_confirmation",
            },
            {
                "logical_uuid": "rule-1",
                "title": "Approval",
                "statement": "Requests require approval.",
                "origin": "manual",
                "confirmation_status": "confirmed",
            },
        ],
        "rule_links": [
            {
                "logical_uuid": "link-1",
                "rule_logical_uuid": "rule-2",
                "target_kind": "flow_transition",
                "target_logical_uuid": "transition-2",
                "link_purpose": "applies_to",
                "context_text": "Approval branch",
            }
        ],
    }

    normalized = serialize_requirement_space(raw)

    assert [rule["logical_uuid"] for rule in normalized["domain_rules"]] == [
        "rule-1",
        "rule-2",
    ]
    assert normalized["flows"][0]["transitions"][0] == {
        "logical_uuid": "transition-2",
        "source_step_logical_uuid": "step-1",
        "target_step_logical_uuid": "step-2",
        "label": "approved",
        "condition_text": "approval succeeds",
        "is_default": False,
        "position": 1,
        "semantic_tags": ["review", "success"],
        "origin": "manual",
        "confirmation_status": "confirmed",
    }
    assert normalized["rule_links"][0]["target_logical_uuid"] == "transition-2"
