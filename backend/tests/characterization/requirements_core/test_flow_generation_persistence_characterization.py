import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import selectinload, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.modules.requirements_core.flow.application.flow_generation_service import (
    FlowGenerationService,
)
from backend.database.database import Base
from backend.database.model import (
    ActorModel,
    BusinessObjectModel,
    FeatureModel,
    FeatureRelationModel,
    FlowModel,
    FlowStepModel,
    ProjectModel,
    feature_actor_table,
)
from backend.schemas import ActorNode, FeatureNode


def _valid_generated_flow() -> dict:
    return {
        "business_objects": [
            {
                "business_object_number": "B-001",
                "business_object_name": "Cart",
            }
        ],
        "flows": [
            {
                "feature_ids": [20],
                "flow_steps": [
                    {
                        "step_number": "S-001",
                        "step_type": "actorAction",
                        "actor_ids": [10],
                        "input_business_object_numbers": ["B-001"],
                        "output_business_object_numbers": [],
                        "next_steps": [],
                    }
                ],
            }
        ],
    }


@pytest.mark.parametrize(
    ("raw", "error_code"),
    [
        ({"business_objects": [], "flows": []}, "empty_business_objects"),
        (
            {
                "business_objects": [
                    {"business_object_number": "invalid"},
                    {"business_object_number": "invalid"},
                ],
                "flows": [],
            },
            "empty_flows",
        ),
        (
            {
                "business_objects": [
                    {"business_object_number": "B-001"},
                    {"business_object_number": "B-001"},
                ],
                "flows": [{}],
            },
            "duplicate_business_object_number",
        ),
        (
            {
                "business_objects": [
                    {"business_object_number": "B-001"},
                ],
                "flows": [{"feature_ids": [], "flow_steps": []}],
            },
            "invalid_feature_reference",
        ),
        (
            {
                "business_objects": [
                    {"business_object_number": "B-001"},
                ],
                "flows": [
                    {
                        "feature_ids": [20],
                        "flow_steps": [
                            {
                                "step_number": "S-001",
                                "step_type": "invalid",
                                "actor_ids": [999],
                            }
                        ],
                    }
                ],
            },
            "invalid_step_type",
        ),
    ],
)
def test_validate_generated_flows_preserves_first_error(raw, error_code):
    service = FlowGenerationService()
    actors = [
        ActorNode(
            actorId=10,
            actorName="Customer",
            actorDescription="",
        )
    ]
    features = [
        FeatureNode(
            featureId=20,
            featureName="Checkout",
            featureDescription="",
            actorIds=[10],
            parentId=None,
            childrenIds=[],
        )
    ]

    with pytest.raises(ValueError, match=f"^{error_code}$"):
        service._validate_generated_flows(raw, actors, features)


def test_validate_generated_flows_accepts_valid_graph():
    service = FlowGenerationService()
    service._validate_generated_flows(
        _valid_generated_flow(),
        [
            ActorNode(
                actorId=10,
                actorName="Customer",
                actorDescription="",
            )
        ],
        [
            FeatureNode(
                featureId=20,
                featureName="Checkout",
                featureDescription="",
                actorIds=[10],
                parentId=None,
                childrenIds=[],
            )
        ],
    )


def test_build_flow_generation_response_preserves_mapping_and_order():
    response = FlowGenerationService._build_response_payload(
        99,
        {
            "generation_mode": "three_step",
            "leaf_feature_count": 2,
            "business_objects": [
                {
                    "business_object_number": "B-001",
                    "business_object_name": "Cart",
                    "business_object_description": "Current cart",
                    "business_object_attributes": [{"name": "total"}],
                    "internal_field": "hidden",
                },
                {
                    "business_object_number": "B-002",
                    "business_object_name": "Order",
                    "business_object_description": "Placed order",
                },
            ],
            "flows": [
                {
                    "flow_name": "Purchase",
                    "flow_description": "Checkout flow",
                    "feature_ids": [20],
                    "flow_steps": [
                        {
                            "step_number": "S-001",
                            "step_name": "Review",
                            "step_description": "Review cart",
                            "step_type": "actorAction",
                            "actor_ids": [10],
                            "input_business_object_numbers": ["B-001"],
                            "output_business_object_numbers": ["B-002"],
                            "next_steps": ["S-002"],
                        },
                        {
                            "step_number": "S-002",
                            "step_name": "Submit",
                            "step_description": "Submit order",
                            "step_type": "systemAction",
                        },
                    ],
                }
            ],
        },
        [
            ActorNode(
                actorId=10,
                actorName="Customer",
                actorDescription="",
            )
        ],
        [
            FeatureNode(
                featureId=20,
                featureName="Checkout",
                featureDescription="",
                actorIds=[10],
                parentId=None,
                childrenIds=[],
            )
        ],
    )

    assert response == {
        "project_id": 99,
        "generation_mode": "three_step",
        "leaf_feature_count": 2,
        "business_objects": [
            {
                "business_object_name": "Cart",
                "business_object_description": "Current cart",
                "business_object_attributes": [{"name": "total"}],
            },
            {
                "business_object_name": "Order",
                "business_object_description": "Placed order",
                "business_object_attributes": [],
            },
        ],
        "flows": [
            {
                "flow_name": "Purchase",
                "flow_description": "Checkout flow",
                "feature_names": ["Checkout"],
                "flow_steps": [
                    {
                        "step_name": "Review",
                        "step_description": "Review cart",
                        "step_type": "actorAction",
                        "actor_names": ["Customer"],
                        "input_business_object_names": ["Cart"],
                        "output_business_object_names": ["Order"],
                        "next_step_names": ["Submit"],
                    },
                    {
                        "step_name": "Submit",
                        "step_description": "Submit order",
                        "step_type": "systemAction",
                        "actor_names": [],
                        "input_business_object_names": [],
                        "output_business_object_names": [],
                        "next_step_names": [],
                    },
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_persist_flow_generation_draft_preserves_graph_shape():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        project = ProjectModel(
            name="Project",
            description="Description",
            user_requirements="Requirements",
        )
        session.add(project)
        await session.flush()
        actor = ActorModel(
            project_id=project.id,
            name="Customer",
            description="",
        )
        feature = FeatureModel(
            project_id=project.id,
            name="Checkout",
            description="",
        )
        session.add_all([actor, feature])
        await session.flush()

        result = await FlowGenerationService._persist_flow_generation_draft(
            {
                "project_id": project.id,
                "business_objects": [
                    {
                        "business_object_number": 1,
                        "business_object_name": "Cart",
                        "business_object_description": "Current cart",
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
                        "business_object_number": 2,
                        "business_object_name": "Order",
                        "business_object_description": "Placed order",
                        "business_object_attributes": [],
                    },
                ],
                "flows": [
                    {
                        "flow_name": "Purchase",
                        "flow_description": "Checkout flow",
                        "feature_ids": [feature.id],
                        "flow_steps": [
                            {
                                "step_number": 1,
                                "step_name": "Review",
                                "step_description": "",
                                "step_type": "actorAction",
                                "actor_ids": [actor.id],
                                "input_business_object_numbers": [1],
                                "output_business_object_numbers": [2],
                                "next_steps": [2],
                            },
                            {
                                "step_number": 2,
                                "step_name": "Submit",
                                "step_description": "",
                                "step_type": "systemAction",
                                "actor_ids": [],
                                "input_business_object_numbers": [2],
                                "output_business_object_numbers": [],
                                "next_steps": [],
                            },
                        ],
                    },
                    {
                        "flow_name": "Receipt",
                        "flow_description": "Receipt flow",
                        "feature_ids": [],
                        "flow_steps": [
                            {
                                "step_number": 1,
                                "step_name": "Send receipt",
                                "step_description": "",
                                "step_type": "systemAction",
                                "actor_ids": [],
                                "input_business_object_numbers": [2],
                                "output_business_object_numbers": [],
                                "next_steps": [],
                            }
                        ],
                    },
                ],
            },
            session,
        )

        business_objects = (
            await session.execute(
                select(BusinessObjectModel)
                .options(selectinload(BusinessObjectModel.attributes))
                .order_by(BusinessObjectModel.id)
            )
        ).scalars().all()
        flows = (
            await session.execute(
                select(FlowModel)
                .options(
                    selectinload(FlowModel.features),
                    selectinload(FlowModel.steps).selectinload(
                        FlowStepModel.actors
                    ),
                    selectinload(FlowModel.steps).selectinload(
                        FlowStepModel.input_business_objects
                    ),
                    selectinload(FlowModel.steps).selectinload(
                        FlowStepModel.output_business_objects
                    ),
                    selectinload(FlowModel.steps).selectinload(
                        FlowStepModel.next_steps
                    ),
                )
                .order_by(FlowModel.id)
            )
        ).scalars().all()
        flow = flows[0]

    await engine.dispose()

    assert result == {
        "project_id": project.id,
        "business_object_count": 2,
        "flow_count": 2,
        "flow_step_count": 3,
        "message": "flows_created",
    }
    assert [
        (item.name, item.confirmation_status)
        for item in business_objects
    ] == [("Cart", "ai_assumption"), ("Order", "ai_assumption")]
    assert business_objects[0].attributes[0].example == ""
    assert [item.id for item in flow.features] == [feature.id]
    assert flow.confirmation_status == "ai_assumption"
    assert [
        (item.name, item.confirmation_status)
        for item in flows
    ] == [
        ("Purchase", "ai_assumption"),
        ("Receipt", "ai_assumption"),
    ]
    assert [
        (
            step.position,
            step.name,
            [item.id for item in step.actors],
            [item.name for item in step.input_business_objects],
            [item.name for item in step.output_business_objects],
            [item.position for item in step.next_steps],
        )
        for step in flow.steps
    ] == [
        (1, "Review", [actor.id], ["Cart"], ["Order"], [2]),
        (2, "Submit", [], ["Order"], [], []),
    ]


@pytest.mark.asyncio
async def test_load_flow_generation_context_preserves_graph_shape():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        project = ProjectModel(
            name="Project",
            description="Description",
            user_requirements="Build checkout",
        )
        session.add(project)
        await session.flush()
        actors = [
            ActorModel(
                project_id=project.id,
                name=name,
                description=f"{name} description",
            )
            for name in ("Customer", "Operator")
        ]
        features = [
            FeatureModel(
                project_id=project.id,
                name=name,
                description=f"{name} description",
            )
            for name in ("Checkout", "Review", "Submit")
        ]
        session.add_all([*actors, *features])
        await session.flush()
        session.add_all(
            [
                FeatureRelationModel(
                    parent_feature_id=features[0].id,
                    child_feature_id=features[1].id,
                    position=1,
                ),
                FeatureRelationModel(
                    parent_feature_id=features[0].id,
                    child_feature_id=features[2].id,
                    position=2,
                ),
            ]
        )
        await session.execute(
            insert(feature_actor_table),
            [
                {
                    "feature_id": features[1].id,
                    "actor_id": actors[0].id,
                },
                {
                    "feature_id": features[2].id,
                    "actor_id": actors[1].id,
                },
            ],
        )
        await session.flush()

        result = await FlowGenerationService._load_project_context(
            project.id,
            session,
        )

    await engine.dispose()

    requirements, actor_nodes, feature_nodes, leaf_count = result
    assert requirements == "Build checkout"
    assert [
        (node.actorId, node.actorName, node.actorDescription)
        for node in actor_nodes
    ] == [
        (actors[0].id, "Customer", "Customer description"),
        (actors[1].id, "Operator", "Operator description"),
    ]
    assert [
        (
            node.featureId,
            node.actorIds,
            node.parentId,
            node.childrenIds,
        )
        for node in feature_nodes
    ] == [
        (
            features[0].id,
            [],
            None,
            [features[1].id, features[2].id],
        ),
        (features[1].id, [actors[0].id], features[0].id, []),
        (features[2].id, [actors[1].id], features[0].id, []),
    ]
    assert leaf_count == 2
