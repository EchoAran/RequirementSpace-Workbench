"""
Tests for Deterministic Requirement Space Serializer and SHA-256 Hasher.
验证相同模型状态反复序列化时的 JSON 与哈希绝对一致性、字段确定性排序和空值规范化。
"""
from backend.api.modules.version_control.domain.serializer import (
    serialize_requirement_space,
    to_deterministic_json,
    compute_state_hash,
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

    assert norm["schema_version"] == "1.0"
    assert norm["actors"] == []
    assert norm["features"] == []
    assert isinstance(json_str, str)
    assert len(h) == 64
