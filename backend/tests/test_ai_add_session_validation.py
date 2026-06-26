"""
Unit tests for AI add session validation logic (_validate_generated_object, _build_preview).

These tests do NOT require database access — they test the static/stateless
validation and preview-building methods of AIAddSessionService directly.
"""

import pytest
from backend.api.modules.ai_interaction.ai_add.application.session import AIAddSessionService


# ---------------------------------------------------------------------------
# Actor validation
# ---------------------------------------------------------------------------

def test_validate_actor_success():
    """A valid actor with name and description passes."""
    raw = {"actor": {"name": "测试用户", "description": "负责测试的用户角色"}}
    ctx = {"actors": []}
    result = AIAddSessionService._validate_generated_object("actor", raw, ctx)
    assert result["name"] == "测试用户"
    assert result["description"] == "负责测试的用户角色"


def test_validate_actor_empty_name():
    """Actor with blank name raises ValueError."""
    raw = {"actor": {"name": "  ", "description": "test"}}
    ctx = {"actors": []}
    with pytest.raises(ValueError, match="empty_actor_name"):
        AIAddSessionService._validate_generated_object("actor", raw, ctx)


def test_validate_actor_duplicate_name():
    """Actor whose name matches an existing actor raises ValueError."""
    raw = {"actor": {"name": "重复名称", "description": "test"}}
    ctx = {"actors": [{"id": 1, "name": "重复名称"}]}
    with pytest.raises(ValueError, match="duplicate_actor_name"):
        AIAddSessionService._validate_generated_object("actor", raw, ctx)


def test_validate_actor_missing_actor_key():
    """Missing actor key raises KeyError-or-null handling — name becomes empty."""
    raw = {}
    ctx = {"actors": []}
    with pytest.raises(ValueError, match="empty_actor_name"):
        AIAddSessionService._validate_generated_object("actor", raw, ctx)


# ---------------------------------------------------------------------------
# Feature validation (leaf & branch)
# ---------------------------------------------------------------------------

def test_validate_feature_leaf_success():
    """A valid leaf feature passes."""
    raw = {
        "feature": {
            "name": "批量导入",
            "description": "导入歌曲",
            "parent_id": 1,
            "actor_ids": [10, 20],
            "feature_kind": "leaf",
        }
    }
    ctx = {"features": [], "actors": [{"id": 10}, {"id": 20}]}
    result = AIAddSessionService._validate_generated_object("feature_leaf", raw, ctx)
    assert result["name"] == "批量导入"
    assert result["feature_kind"] == "leaf"
    assert result["actor_ids"] == [10, 20]
    assert result["parent_id"] == 1


def test_validate_feature_branch_success():
    """A valid branch feature passes."""
    raw = {
        "feature": {
            "name": "歌单管理",
            "description": "管理歌单",
            "actor_ids": [],
            "feature_kind": "branch",
        }
    }
    ctx = {"features": [], "actors": []}
    result = AIAddSessionService._validate_generated_object("feature_branch", raw, ctx)
    assert result["name"] == "歌单管理"
    assert result["feature_kind"] == "branch"


def test_validate_feature_empty_name():
    """Feature with blank name raises ValueError."""
    raw = {"feature": {"name": "", "feature_kind": "leaf"}}
    ctx = {"features": [], "actors": []}
    with pytest.raises(ValueError, match="empty_feature_name"):
        AIAddSessionService._validate_generated_object("feature_leaf", raw, ctx)


def test_validate_feature_invalid_kind():
    """Feature with invalid feature_kind raises ValueError."""
    raw = {"feature": {"name": "test", "feature_kind": "invalid_type"}}
    ctx = {"features": [], "actors": []}
    with pytest.raises(ValueError, match="invalid_feature_kind"):
        AIAddSessionService._validate_generated_object("feature_leaf", raw, ctx)


def test_validate_feature_invalid_actor_reference():
    """Feature referencing non-existent actor IDs raises ValueError."""
    raw = {
        "feature": {
            "name": "test",
            "actor_ids": [999],
            "feature_kind": "leaf",
        }
    }
    ctx = {"features": [], "actors": [{"id": 1}, {"id": 2}]}
    with pytest.raises(ValueError, match="invalid_actor_reference"):
        AIAddSessionService._validate_generated_object("feature_leaf", raw, ctx)


def test_validate_feature_kind_mismatch_accepts_both():
    """target_type 'feature_leaf' does not reject 'branch' kind — handled by generator."""
    raw = {"feature": {"name": "test", "feature_kind": "branch"}}
    ctx = {"features": [], "actors": []}
    result = AIAddSessionService._validate_generated_object("feature_leaf", raw, ctx)
    # Validation passes; kind mismatch is caught at the prompt level, not validation
    assert result["feature_kind"] == "branch"


# ---------------------------------------------------------------------------
# Flow validation
# ---------------------------------------------------------------------------

def test_validate_flow_success():
    """A valid flow with feature_ids passes."""
    raw = {
        "flow": {
            "name": "导入流程",
            "description": "导入歌曲流程",
            "feature_ids": [100, 200],
        }
    }
    ctx = {"features": [{"id": 100}, {"id": 200}], "flows": []}
    result = AIAddSessionService._validate_generated_object("flow", raw, ctx)
    assert result["name"] == "导入流程"
    assert result["feature_ids"] == [100, 200]


def test_validate_flow_empty_feature_ids():
    """Flow with empty feature_ids raises ValueError."""
    raw = {"flow": {"name": "test", "feature_ids": []}}
    ctx = {"features": [], "flows": []}
    with pytest.raises(ValueError, match="empty_flow_feature_ids"):
        AIAddSessionService._validate_generated_object("flow", raw, ctx)


def test_validate_flow_invalid_feature_reference():
    """Flow referencing non-existent feature IDs raises ValueError."""
    raw = {"flow": {"name": "test", "feature_ids": [999]}}
    ctx = {"features": [{"id": 1}], "flows": []}
    with pytest.raises(ValueError, match="invalid_feature_reference"):
        AIAddSessionService._validate_generated_object("flow", raw, ctx)


# ---------------------------------------------------------------------------
# Business object validation
# ---------------------------------------------------------------------------

def test_validate_business_object_success():
    """A valid business object with attributes passes."""
    raw = {
        "business_object": {
            "name": "歌曲文件",
            "description": "音乐文件",
            "attributes": [
                {"name": "路径", "description": "文件路径", "data_type": "string", "example": "/music/song.flac"},
                {"name": "大小", "description": "文件大小", "data_type": "int", "example": "10485760"},
            ],
        }
    }
    ctx = {"business_objects": [], "flows": []}
    result = AIAddSessionService._validate_generated_object("business_object", raw, ctx)
    assert result["name"] == "歌曲文件"
    assert len(result["attributes"]) == 2


def test_validate_business_object_duplicate_name():
    """Business object with duplicate name raises ValueError."""
    raw = {"business_object": {"name": "已存在", "description": ""}}
    ctx = {"business_objects": [{"id": 1, "name": "已存在"}], "flows": []}
    with pytest.raises(ValueError, match="duplicate_business_object_name"):
        AIAddSessionService._validate_generated_object("business_object", raw, ctx)


def test_validate_business_object_duplicate_attributes_deduplicated():
    """Business object with duplicate attribute names deduplicates them."""
    raw = {
        "business_object": {
            "name": "新对象",
            "attributes": [
                {"name": "重复名", "data_type": "string"},
                {"name": "重复名", "data_type": "int"},
                {"name": "唯一名", "data_type": "string"},
            ],
        }
    }
    ctx = {"business_objects": [], "flows": []}
    result = AIAddSessionService._validate_generated_object("business_object", raw, ctx)
    names = [a["name"] for a in result["attributes"]]
    assert names == ["重复名", "唯一名"]


def test_validate_business_object_skips_empty_attr_names():
    """Attributes with empty names are skipped."""
    raw = {
        "business_object": {
            "name": "新对象",
            "attributes": [
                {"name": "", "data_type": "string"},
                {"name": "有效名", "data_type": "string"},
            ],
        }
    }
    ctx = {"business_objects": [], "flows": []}
    result = AIAddSessionService._validate_generated_object("business_object", raw, ctx)
    assert len(result["attributes"]) == 1
    assert result["attributes"][0]["name"] == "有效名"


# ---------------------------------------------------------------------------
# Preview builder
# ---------------------------------------------------------------------------

def test_build_preview_actor():
    preview = AIAddSessionService._build_preview("actor", {"name": "A", "description": "B"})
    assert preview["name"] == "A"
    assert preview["description"] == "B"


def test_build_preview_feature():
    preview = AIAddSessionService._build_preview(
        "feature_leaf",
        {"name": "F", "description": "D", "parent_id": 1, "actor_ids": [10], "feature_kind": "leaf"},
    )
    assert preview["name"] == "F"
    assert preview["feature_kind"] == "leaf"
    assert preview["parent_id"] == 1


def test_build_preview_flow():
    preview = AIAddSessionService._build_preview(
        "flow",
        {"name": "Fl", "description": "D", "feature_ids": [1, 2]},
    )
    assert preview["name"] == "Fl"
    assert preview["feature_ids"] == [1, 2]


def test_build_preview_business_object():
    preview = AIAddSessionService._build_preview(
        "business_object",
        {"name": "BO", "description": "D", "attributes": [{"name": "a"}]},
    )
    assert preview["name"] == "BO"
    assert preview["attribute_count"] == 1


# ---------------------------------------------------------------------------
# Unsupported target_type
# ---------------------------------------------------------------------------

def test_validate_unsupported_target_type():
    with pytest.raises(ValueError, match="unsupported_target_type"):
        AIAddSessionService._validate_generated_object("unknown_type", {}, {})
