import copy

import pytest

from backend.api.modules.preview_convergence.application.shadow_patch_applier import (
    PreviewShadowPatchApplier,
)


def _base_snapshot() -> dict:
    return {
        "project_id": 7,
        "name": "原项目",
        "description": "原描述",
        "user_requirements": "原需求",
        "kano_status": "pending",
        "actors": [
            {
                "id": 1,
                "name": "已有角色",
                "description": "已有",
            }
        ],
        "features": [
            {
                "id": 10,
                "name": "已有功能",
                "description": "已有",
                "actor_ids": [],
                "parent_id": None,
                "children_ids": [],
                "scenarios": [
                    {
                        "id": 20,
                        "name": "已有场景",
                        "acceptance_criteria": [],
                    }
                ],
                "scope": None,
            }
        ],
        "business_objects": [
            {
                "id": 30,
                "name": "已有对象",
                "business_object_attributes": [],
            }
        ],
        "flows": [
            {
                "id": 40,
                "name": "已有流程",
                "feature_ids": [10],
                "flow_steps": [],
            "transitions": [],
            }
        ],
    }


def test_apply_patch_to_snapshot_preserves_full_mapping_and_input():
    base_snapshot = _base_snapshot()
    original = copy.deepcopy(base_snapshot)
    patch = {
        "actors_added": [
            {
                "temp_id": "tmp_actor",
                "name": "新角色",
                "description": "新增",
            }
        ],
        "features_added": [
            {
                "temp_id": "tmp_feature",
                "name": "新功能",
                "description": "新增",
                "parent_ref": "feature:10",
            }
        ],
        "feature_actor_links_added": [
            {
                "feature_ref": "tmp_feature",
                "actor_ref": "tmp_actor",
            }
        ],
        "scenarios_added": [
            {
                "temp_id": "tmp_scenario",
                "name": "新场景",
                "content": "新内容",
                "feature_ref": "tmp_feature",
                "actor_ref": "tmp_actor",
            }
        ],
        "acceptance_criteria_added": [
            {
                "scenario_ref": "scenario:20",
                "content": "既有场景准则",
                "position": 1,
            },
            {
                "scenario_ref": "tmp_scenario",
                "content": "新场景准则",
                "position": 1,
            },
        ],
        "business_objects_added": [
            {
                "temp_id": "tmp_bo",
                "name": "新对象",
                "description": "新增",
            }
        ],
        "business_object_attributes_added": [
            {
                "business_object_ref": "business_object:30",
                "name": "已有对象属性",
                "description": "新增属性",
                "data_type": "string",
                "example": "A",
            },
            {
                "business_object_ref": "tmp_bo",
                "name": "新对象属性",
                "description": "新增属性",
                "data_type": "integer",
                "example": "1",
            },
        ],
        "flows_added": [
            {
                "temp_id": "tmp_flow",
                "name": "新流程",
                "description": "新增",
                "feature_refs": ["tmp_feature"],
            }
        ],
        "flow_steps_added": [
                {
                    "temp_id": "tmp_existing_flow_step",
                    "flow_ref": "tmp_flow",
                "name": "已有流程新增步骤",
                "description": "步骤",
                "step_type": "actorAction",
                "position": 1,
                "actor_refs": ["tmp_actor"],
                "input_bo_refs": ["business_object:30"],
                "output_bo_refs": ["tmp_bo"],
            },
            {
                "temp_id": "tmp_new_flow_step",
                "flow_ref": "tmp_flow",
                "name": "新流程步骤",
                "description": "步骤",
                "step_type": "systemAction",
                "position": 1,
                "actor_refs": [],
                "input_bo_refs": ["tmp_bo"],
                "output_bo_refs": [],
            },
        ],
            "flow_transitions_added": [
                {
                        "temp_id": "tmp_transition",
                        "flow_ref": "tmp_flow",
                    "source_step_ref": "tmp_existing_flow_step",
                    "target_step_ref": "tmp_new_flow_step",
                    "condition_text": "",
                    "label": "continue",
                    "is_default": False,
                    "position": 0,
                    "semantic_tags": [],
                    "origin": "manual",
                    "confirmation_status": "ai_assumption",
                }
            ],
        "scopes_added": [
            {
                "feature_ref": "tmp_feature",
                "status": "CURRENT",
                "reason": "本期实现",
                "kano_category": "M",
                "kano_category_name": "Must-be",
            }
        ],
    }

    snapshot, temp_ids = PreviewShadowPatchApplier.apply_patch_to_snapshot(
        base_snapshot,
        patch,
    )

    assert base_snapshot == original
    assert temp_ids == {
        "tmp_actor": -1001,
        "tmp_feature": -1002,
        "tmp_scenario": -1003,
        "tmp_bo": -1004,
        "tmp_flow": -1005,
        "tmp_existing_flow_step": -1006,
        "tmp_new_flow_step": -1007,
        "tmp_transition": -1008,
    }
    assert snapshot["features"][0]["children_ids"] == [-1002]
    assert snapshot["features"][0]["scenarios"][0][
        "acceptance_criteria"
    ] == [
        {
            "criterion_id": -1009,
            "logical_uuid": None,
            "criterion_content": "既有场景准则",
            "position": 1,
        }
    ]
    new_feature = snapshot["features"][1]
    assert new_feature["actor_ids"] == [-1001]
    assert new_feature["parent_id"] == 10
    assert new_feature["scenarios"][0]["scenario_id"] == -1003
    assert new_feature["scenarios"][0]["acceptance_criteria"][0] == {
        "criterion_id": -1010,
        "logical_uuid": None,
        "criterion_content": "新场景准则",
        "position": 1,
    }
    assert snapshot["business_objects"][0][
        "business_object_attributes"
    ][0]["business_object_attribute_id"] == -1011
    assert snapshot["business_objects"][1][
        "business_object_attributes"
    ][0]["business_object_attribute_id"] == -1012
    assert snapshot["flows"][1]["flow_id"] == -1005
    assert snapshot["flows"][1]["flow_steps"][0]["step_id"] == -1006
    assert snapshot["flows"][1]["flow_steps"][1]["step_id"] == -1007
    assert snapshot["flows"][1]["transitions"][0]["transition_id"] == -1008
    assert snapshot["flows"][1]["transitions"][0]["source_step_id"] == -1006
    assert snapshot["flows"][1]["transitions"][0]["target_step_id"] == -1007
    assert new_feature["scope"]["scope_id"] == -1013
    assert snapshot["kano_status"] == "generated"


def test_apply_patch_to_snapshot_rejects_leaf_without_scope():
    base_snapshot = _base_snapshot()
    base_snapshot["features"][0]["scenarios"] = []

    with pytest.raises(ValueError, match="shadow_scope_missing"):
        PreviewShadowPatchApplier.apply_patch_to_snapshot(
            base_snapshot,
            {},
        )


def _how_lifecycle_snapshot() -> dict:
    snapshot = _base_snapshot()
    snapshot["features"][0]["logical_uuid"] = "feature-10"
    snapshot["features"][0]["scope"] = {
        "scope_id": 60,
        "scope_status": "CURRENT",
        "reason": "Included",
    }
    snapshot["flows"][0]["logical_uuid"] = "flow-40"
    snapshot["flows"][0]["flow_steps"] = [
        {"id": 41, "logical_uuid": "step-41"},
        {"id": 42, "logical_uuid": "step-42"},
    ]
    snapshot["flows"][0]["transitions"] = [
        {
            "id": 43,
            "logical_uuid": "transition-43",
            "source_step_id": 41,
            "target_step_id": 42,
            "label": "Continue",
            "condition_text": "Ready",
            "is_default": True,
            "position": 0,
            "semantic_tags": [],
            "origin": "manual",
            "confirmation_status": "confirmed",
        }
    ]
    snapshot["domain_rules"] = [
        {
            "id": 51,
            "logical_uuid": "rule-51",
            "parent_rule_logical_uuid": None,
            "title": "Eligibility",
            "statement": "The request must be eligible.",
            "origin": "manual",
            "confirmation_status": "confirmed",
            "links": [
                {
                    "id": 52,
                    "logical_uuid": "link-52",
                    "target_kind": "flow_transition",
                    "target_logical_uuid": "transition-43",
                    "link_purpose": "applies_to",
                    "context_text": "Controls the branch.",
                }
            ],
        }
    ]
    return snapshot


def test_apply_patch_to_snapshot_updates_how_lifecycle_entities():
    snapshot, _ = PreviewShadowPatchApplier.apply_patch_to_snapshot(
        _how_lifecycle_snapshot(),
        {
            "domain_rules_updated": [
                {
                    "rule_ref": "domain_rule:51",
                    "statement": "The approved request must be eligible.",
                }
            ],
            "rule_links_updated": [
                {
                    "rule_link_ref": "rule_link:52",
                    "context_text": "Explains the approved branch.",
                }
            ],
            "flow_transitions_updated": [
                {
                    "transition_ref": "flow_transition:43",
                    "condition_text": "Approved and eligible",
                    "semantic_tags": ["approval", "approval"],
                }
            ],
        },
    )

    assert snapshot["domain_rules"][0]["statement"].startswith("The approved")
    assert snapshot["domain_rules"][0]["links"][0]["context_text"].startswith(
        "Explains"
    )
    transition = snapshot["flows"][0]["transitions"][0]
    assert transition["condition_text"] == "Approved and eligible"
    assert transition["semantic_tags"] == ["approval"]


def test_apply_patch_to_snapshot_removes_how_entities_in_dependency_order():
    snapshot, _ = PreviewShadowPatchApplier.apply_patch_to_snapshot(
        _how_lifecycle_snapshot(),
        {
            "rule_links_removed": ["rule_link:52"],
            "flow_transitions_removed": ["flow_transition:43"],
            "domain_rules_removed": ["domain_rule:51"],
        },
    )

    assert snapshot["domain_rules"] == []
    assert snapshot["flows"][0]["transitions"] == []
