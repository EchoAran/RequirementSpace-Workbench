import json
from datetime import datetime

from backend.api.modules.preview_convergence.application.shadow_project_creator import (
    remap_snapshot_to_pydantic,
)
from backend.api.modules.project_lifecycle.schemas.project import ProjectDetailResponse


def test_shadow_snapshot_remap_supplies_required_updated_at_fields():
    existing_updated_at = "2026-07-19T12:00:00+08:00"
    snapshot = {
        "project_id": "project-1",
        "name": "Shadow project",
        "description": "Preview",
        "user_requirements": "Build a preview",
        "actors": [{"id": 1, "name": "User", "description": "Uses it", "updatedAt": existing_updated_at}],
        "features": [{
            "id": 2,
            "name": "Feature",
            "description": "Does work",
            "actor_ids": [1],
            "scenarios": [{
                "id": 3,
                "name": "Scenario",
                "content": "Given, when, then",
                "feature_id": 2,
                "actor_id": 1,
                "acceptance_criteria": [{"id": 4, "content": "It works"}],
            }],
            "scope": {"id": 5, "status": "CURRENT", "reason": "Required"},
        }],
        "business_objects": [{
            "id": 6,
            "name": "Record",
            "description": "Stored data",
            "business_object_attributes": [{
                "id": 7,
                "name": "value",
                "description": "A value",
                "data_type": "string",
                "example": "sample",
            }],
        }],
        "flows": [{
            "id": 8,
            "name": "Flow",
            "description": "Main flow",
            "feature_ids": [2],
            "flow_steps": [{
                "id": 9,
                "name": "Start",
                "description": "Starts",
                "step_type": "USER_ACTION",
                "position": 1,
            }],
        }],
    }

    remapped = remap_snapshot_to_pydantic(snapshot)
    detail = ProjectDetailResponse.model_validate(remapped)

    json.dumps(remapped)
    assert detail.actors[0].updated_at == datetime.fromisoformat(existing_updated_at)
    assert detail.features[0].updated_at is not None
    assert detail.features[0].scenarios[0].updated_at is not None
    assert detail.features[0].scenarios[0].acceptance_criteria[0].updated_at is not None
    assert detail.features[0].scope.updated_at is not None
    assert detail.business_objects[0].updated_at is not None
    assert detail.business_objects[0].business_object_attributes[0].updated_at is not None
    assert detail.flows[0].updated_at is not None
    assert detail.flows[0].flow_steps[0].updated_at is not None
    assert "updated_at" not in snapshot["features"][0]
