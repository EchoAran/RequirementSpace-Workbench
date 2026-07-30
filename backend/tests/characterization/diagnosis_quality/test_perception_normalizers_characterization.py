import pytest
from types import SimpleNamespace

from backend.api.modules.diagnosis_quality.perception.application.normalizers import (
    PerceptionDraftNormalizer,
)
from backend.schemas import BusinessObjectNode


def test_normalize_filled_business_objects_preserves_ids_and_aliases():
    business_objects, reference_map = (
        PerceptionDraftNormalizer.normalize_filled_business_objects(
            [
                {
                    "business_object_id": "5",
                    "business_object_name": "Cart",
                    "business_object_description": "Existing cart",
                    "business_object_attributes": None,
                },
                {
                    "business_object_number": "B-001",
                    "business_object_name": "Order",
                    "business_object_description": "New order",
                    "business_object_attributes": [
                        {
                            "business_object_attribute_name": "total",
                            "business_object_attribute_description": "Total",
                            "business_object_attribute_type": "decimal",
                            "business_object_attribute_example": None,
                        }
                    ],
                },
                {
                    "business_object_number": "B-002",
                    "business_object_name": "Receipt",
                    "business_object_description": "New receipt",
                },
            ],
            [
                BusinessObjectNode(
                    businessObjectId=5,
                    businessObjectName="Cart",
                    businessObjectDescription="Existing cart",
                )
            ],
        )
    )

    assert business_objects == [
        {
            "business_object_id": 5,
            "business_object_name": "Cart",
            "business_object_description": "Existing cart",
            "is_existing": True,
            "business_object_attributes": [],
        },
        {
            "business_object_id": -1,
            "business_object_name": "Order",
            "business_object_description": "New order",
            "is_existing": False,
            "business_object_attributes": [
                {
                    "business_object_attribute_name": "total",
                    "business_object_attribute_description": "Total",
                    "business_object_attribute_type": "decimal",
                    "business_object_attribute_example": "",
                }
            ],
        },
        {
            "business_object_id": -2,
            "business_object_name": "Receipt",
            "business_object_description": "New receipt",
            "is_existing": False,
            "business_object_attributes": [],
        },
    ]
    assert reference_map[5] == 5
    assert reference_map["5"] == 5
    assert reference_map["B-001"] == -1
    assert reference_map["B-002"] == -2


def test_normalize_filled_business_objects_preserves_duplicate_error_order():
    with pytest.raises(ValueError, match="^duplicate_business_object_id$"):
        PerceptionDraftNormalizer.normalize_filled_business_objects(
            [
                {
                    "business_object_id": 1,
                    "business_object_name": "First",
                    "business_object_description": "Valid",
                },
                {
                    "business_object_id": 1,
                    "business_object_name": "",
                    "business_object_description": "",
                },
            ],
            [],
        )


def test_normalize_and_validate_filled_flows_preserves_references():
    flows = PerceptionDraftNormalizer.normalize_filled_flows(
        [
            {
                "flow_name": "Purchase",
                "flow_description": "Checkout flow",
                "feature_ids": ["8", "8"],
                "flow_steps": [
                    {
                        "step_number": "s1",
                        "step_name": "Review",
                        "step_description": "Review order",
                        "step_type": "actor_action",
                        "actor_ids": ["7", "7", "invalid"],
                        "input_business_object_ids": ["5"],
                        "input_business_object_numbers": ["B-001"],
                        "output_business_object_numbers": ["B-002"],
                        "next_steps": ["2", "missing"],
                    },
                    {
                        "step_number": 2,
                        "step_name": "Submit",
                        "step_description": "Submit order",
                        "step_type": "system",
                    },
                ],
            }
        ],
        {
            5: 5,
            "5": 5,
            "B-001": -1,
            "B-002": -2,
        },
    )

    assert flows == [
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
                    "input_business_object_ids": [5, -1],
                    "input_business_object_numbers": ["B-001"],
                    "output_business_object_numbers": ["B-002"],
                    "output_business_object_ids": [-2],
                    "next_steps": ["S-002"],
                },
                {
                    "step_number": "S-002",
                    "step_name": "Submit",
                    "step_description": "Submit order",
                    "step_type": "systemAction",
                    "actor_ids": [],
                    "input_business_object_ids": [],
                    "output_business_object_ids": [],
                    "next_steps": [],
                },
            ],
        }
    ]
    PerceptionDraftNormalizer.validate_filled_flows(
        flows,
        [
            {"business_object_id": -1},
            {"business_object_id": -2},
        ],
        SimpleNamespace(
            actors=[SimpleNamespace(actor_id=7)],
            features=[SimpleNamespace(feature_id=8)],
        ),
        [
            BusinessObjectNode(
                businessObjectId=5,
                businessObjectName="Cart",
                businessObjectDescription="",
            )
        ],
    )


def test_validate_filled_flows_preserves_feature_error_order():
    with pytest.raises(ValueError, match="^invalid_feature_reference$"):
        PerceptionDraftNormalizer.validate_filled_flows(
            [
                {
                    "flow_name": "Purchase",
                    "flow_description": "Checkout flow",
                    "feature_ids": [999],
                    "flow_steps": [],
                }
            ],
            [],
            SimpleNamespace(
                actors=[],
                features=[SimpleNamespace(feature_id=8)],
            ),
            [],
        )
