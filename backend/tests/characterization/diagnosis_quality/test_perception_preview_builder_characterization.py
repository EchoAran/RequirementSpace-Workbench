from types import SimpleNamespace

from backend.api.modules.diagnosis_quality.perception.application.preview_builders import (
    PerceptionPreviewBuilder,
)
from backend.schemas import BusinessObjectNode


def test_build_flow_response_payload_preserves_names_and_fields():
    draft = {
        "project_id": 1,
        "perception_job_id": 2,
        "filler_kind": "flow",
        "business_objects": [
            {
                "business_object_id": -1,
                "business_object_name": "Order",
            }
        ],
        "flows": [
            {
                "flow_name": "Purchase",
                "flow_description": "Checkout flow",
                "feature_ids": [8],
                "flow_steps": [
                    {
                        "step_number": "S-001",
                        "step_name": "Review",
                        "step_description": "Review order",
                        "step_type": "actorAction",
                        "actor_ids": [7],
                        "input_business_object_ids": [5],
                        "output_business_object_ids": [-1],
                    },
                    {
                        "step_number": "S-002",
                        "step_name": "Submit",
                        "step_description": "Submit order",
                        "step_type": "systemAction",
                        "actor_ids": [],
                        "input_business_object_ids": [-1],
                        "output_business_object_ids": [],
                    },
                ],
                "transitions": [
                    {
                        "source_step_number": "S-001",
                        "target_step_number": "S-002",
                    }
                ],
            }
        ],
    }

    response = PerceptionPreviewBuilder._build_flow_response_payload(
        draft,
        SimpleNamespace(
            actors=[SimpleNamespace(actor_id=7, name="Customer")],
            features=[SimpleNamespace(feature_id=8, name="Checkout")],
        ),
        [
            BusinessObjectNode(
                businessObjectId=5,
                businessObjectName="Cart",
                businessObjectDescription="",
            )
        ],
    )

    assert response["business_objects"] == draft["business_objects"]
    assert response["flows"] == [
        {
            "flow_name": "Purchase",
            "flow_description": "Checkout flow",
            "feature_ids": [8],
            "feature_names": ["Checkout"],
            "flow_steps": [
                {
                    "step_number": "S-001",
                    "step_name": "Review",
                    "step_description": "Review order",
                    "step_type": "actorAction",
                    "actor_names": ["Customer"],
                    "input_business_object_names": ["Cart"],
                    "output_business_object_names": ["Order"],
                },
                {
                    "step_number": "S-002",
                    "step_name": "Submit",
                    "step_description": "Submit order",
                    "step_type": "systemAction",
                    "actor_names": [],
                    "input_business_object_names": ["Order"],
                    "output_business_object_names": [],
                },
            ],
            "transitions": [
                {
                    "source_step_name": "Review",
                    "target_step_name": "Submit",
                    "label": "",
                    "condition_text": "",
                    "is_default": False,
                    "position": 0,
                    "semantic_tags": [],
                }
            ],
        }
    ]
