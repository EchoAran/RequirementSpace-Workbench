import copy

import pytest

from backend.core.shadow_preview.shadow_patch_validator import (
    ShadowPatchValidator,
)


@pytest.fixture
def base_snapshot():
    return {
        "project_id": "project-1",
        "actors": [{"id": 1}],
        "features": [
            {
                "id": 2,
                "scenarios": [{"id": 3}],
            }
        ],
        "business_objects": [{"id": 4}],
        "flows": [
            {
                "id": 5,
                "flow_steps": [{"id": 6}],
            }
        ],
    }


@pytest.fixture
def complete_patch():
    return {
        "actors_added": [{"temp_id": "tmp_actor"}],
        "features_added": [
            {
                "temp_id": "tmp_feature",
                "parent_ref": "feature:2",
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
                "feature_ref": "tmp_feature",
                "actor_ref": "actor:1",
            }
        ],
        "acceptance_criteria_added": [
            {
                "scenario_ref": "tmp_scenario",
                "content": "订单已创建",
            }
        ],
        "business_objects_added": [{"temp_id": "tmp_order"}],
        "business_object_attributes_added": [
            {
                "business_object_ref": "tmp_order",
                "name": "订单号",
                "data_type": "string",
            }
        ],
        "flows_added": [
            {
                "temp_id": "tmp_flow",
                "name": "下单",
                "feature_refs": ["feature:2"],
            }
        ],
        "flow_steps_added": [
            {
                "temp_id": "tmp_step_2",
                "flow_ref": "tmp_flow",
                "name": "保存订单",
                "step_type": "systemAction",
                "position": 2,
                "output_bo_refs": ["business_object:4"],
            },
            {
                "temp_id": "tmp_step_1",
                "flow_ref": "tmp_flow",
                "name": "提交订单",
                "step_type": "actorAction",
                "position": 1,
                "actor_refs": ["actor:1"],
                "input_bo_refs": ["tmp_order"],
                "next_step_refs": ["tmp_step_2"],
            },
        ],
        "scopes_added": [
            {
                "feature_ref": "tmp_feature",
                "status": "CURRENT",
                "reason": "核心能力",
            }
        ],
    }


def test_validate_patch_accepts_complete_cross_referenced_patch(
    base_snapshot,
    complete_patch,
):
    assert (
        ShadowPatchValidator.validate_patch(
            complete_patch,
            base_snapshot,
            "project-1",
        )
        is True
    )


def test_validate_patch_preserves_duplicate_temp_id_error(
    base_snapshot,
    complete_patch,
):
    patch = copy.deepcopy(complete_patch)
    patch["business_objects_added"][0]["temp_id"] = "tmp_actor"

    with pytest.raises(
        ValueError,
        match="^Duplicate temp_id 'tmp_actor' across patch elements\\.$",
    ):
        ShadowPatchValidator.validate_patch(
            patch,
            base_snapshot,
            "project-1",
        )


def test_validate_patch_preserves_membership_error(
    base_snapshot,
    complete_patch,
):
    patch = copy.deepcopy(complete_patch)
    patch["feature_actor_links_added"][0]["actor_ref"] = "actor:999"

    with pytest.raises(
        ValueError,
        match=(
            "^Actor ID 999 in reference 'actor:999' does not exist "
            "or belong to project project-1\\.$"
        ),
    ):
        ShadowPatchValidator.validate_patch(
            patch,
            base_snapshot,
            "project-1",
        )


def test_validate_patch_preserves_step_position_error(
    base_snapshot,
    complete_patch,
):
    patch = copy.deepcopy(complete_patch)
    patch["flow_steps_added"][0]["position"] = 3

    with pytest.raises(
        ValueError,
        match=(
            "^Flow steps positions for flow 'tmp_flow' are not "
            "consecutive and sequential starting from 1\\. Got: \\[1, 3\\]$"
        ),
    ):
        ShadowPatchValidator.validate_patch(
            patch,
            base_snapshot,
            "project-1",
        )


def test_validate_patch_preserves_optional_missing_project_id(
    base_snapshot,
    complete_patch,
):
    base_without_project_id = copy.deepcopy(base_snapshot)
    base_without_project_id.pop("project_id")

    with pytest.raises(
        ValueError,
        match=(
            "^Project ID mismatch: base_snapshot is for project None, "
            "but active project is project-1\\.$"
        ),
    ):
        ShadowPatchValidator.validate_patch(
            complete_patch,
            base_without_project_id,
            "project-1",
        )

    assert (
        ShadowPatchValidator.validate_patch(
            complete_patch,
            base_without_project_id,
            "project-1",
            allow_missing_project_id=True,
        )
        is True
    )
