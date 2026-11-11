from backend.database.model import BranchWorkspaceModel, RequirementBranchModel
import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
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
    FlowStepModel, FlowTransitionModel,
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
                        },
                        {
                            "step_number": "S-002",
                            "step_name": "Submit",
                            "step_description": "Submit order",
                            "step_type": "systemAction",
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
                "rule_refs": [],
                "feature_names": ["Checkout"],
                "flow_steps": [
                    {
                        "step_name": "Review",
                        "step_description": "Review cart",
                        "step_type": "actorAction",
                        "rule_refs": [],
                        "actor_names": ["Customer"],
                        "input_business_object_names": ["Cart"],
                        "output_business_object_names": ["Order"],
                    },
                    {
                        "step_name": "Submit",
                        "step_description": "Submit order",
                        "step_type": "systemAction",
                        "rule_refs": [],
                        "actor_names": [],
                        "input_business_object_names": [],
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
                        "rule_refs": [],
                    }
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
            owner_user_id=1,
            name="Project",
            description="Description",
            user_requirements="Requirements",
        )
        session.add(project)
        await session.flush()
        branch = RequirementBranchModel(project_id=project.id, name="test-characterization")
        session.add(branch)
        await session.flush()
        workspace = BranchWorkspaceModel(project_id=project.id, branch_id=branch.id,
                                         user_requirements=project.user_requirements)
        session.add(workspace)
        await session.flush()
        actor = ActorModel(
            project_id=project.id,
            name="Customer",
            description="",
                    workspace_id=workspace.id,
        )
        feature = FeatureModel(
            project_id=project.id,
            name="Checkout",
            description="",
                      workspace_id=workspace.id,
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
                            },
                            {
                                "step_number": 2,
                                "step_name": "Submit",
                                "step_description": "",
                                "step_type": "systemAction",
                                "actor_ids": [],
                                "input_business_object_numbers": [2],
                                "output_business_object_numbers": [],
                            },
                        ],
                        "transitions": [
                            {
                                "source_step_number": 1,
                                "target_step_number": 2,
                            }
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
                            }
                        ],
                    },
                ],
            },
            session,
                           workspace_id=workspace.id,
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
                    selectinload(FlowModel.transitions),
                )
                .order_by(FlowModel.id)
            )
        ).scalars().all()
        flow = flows[0]
        transitions = (await session.execute(select(FlowTransitionModel).where(FlowTransitionModel.flow_id == flow.id))).scalars().all()

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
    assert len(transitions) == 1
    assert transitions[0].source_step_id == flow.steps[0].id
    assert transitions[0].target_step_id == flow.steps[1].id
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
        )
        for step in flow.steps
    ] == [
        (1, "Review", [actor.id], ["Cart"], ["Order"]),
        (2, "Submit", [], ["Order"], []),
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
            owner_user_id=1,
            name="Project",
            description="Description",
            user_requirements="Build checkout",
        )
        session.add(project)
        await session.flush()
        branch = RequirementBranchModel(project_id=project.id, name="test-characterization")
        session.add(branch)
        await session.flush()
        workspace = BranchWorkspaceModel(project_id=project.id, branch_id=branch.id,
                                         user_requirements=project.user_requirements)
        session.add(workspace)
        await session.flush()
        actors = [
            ActorModel(
                project_id=project.id,
                name=name,
                description=f"{name} description",
                workspace_id=workspace.id,
            )
            for name in ("Customer", "Operator")
        ]
        features = [
            FeatureModel(
                project_id=project.id,
                name=name,
                description=f"{name} description",
                workspace_id=workspace.id,
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
        from backend.database.model import DomainRuleModel
        session.add(
            DomainRuleModel(
                project_id=project.id,
                title="Checkout rule",
                statement="Checkout flow generation requires a domain rule.",
                workspace_id=workspace.id,
            )
        )
        await session.flush()

        result = await FlowGenerationService._load_project_context(
            project.id,
            session,
                           workspace_id=workspace.id,
        )

    await engine.dispose()

    requirements = result.user_requirements
    actor_nodes = result.actors
    feature_nodes = result.features
    leaf_count = result.leaf_feature_count
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


def test_validate_duplicate_default_transition_raises():
    """Verify validation immediately fails if a flow contains multiple default transitions from the same source."""
    raw = _valid_generated_flow()
    # Add two transitions from S-001 both marked is_default=True
    raw["flows"][0]["flow_steps"].append({
        "step_number": "S-002",
        "step_type": "systemAction",
    })
    raw["flows"][0]["flow_steps"].append({
        "step_number": "S-003",
        "step_type": "systemAction",
    })
    raw["flows"][0]["transitions"] = [
        {
            "source_step_number": "S-001",
            "target_step_number": "S-002",
            "is_default": True,
        },
        {
            "source_step_number": "S-001",
            "target_step_number": "S-003",
            "is_default": True,
        },
    ]

    actor_nodes = [ActorNode(actorId=10, actorName="Customer", actorDescription="")]
    feature_nodes = [FeatureNode(featureId=20, featureName="Checkout", featureDescription="", actorIds=[10], parentId=None, childrenIds=[])]

    service = FlowGenerationService()
    with pytest.raises(ValueError, match="duplicate_default_transition"):
        service._validate_generated_flows(raw, actor_nodes, feature_nodes)


async def test_persist_duplicate_default_transition_raises():
    """Verify persistence explicitly raises ValueError on duplicate default transitions from same source."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        project = ProjectModel(owner_user_id=1, name="Project", description="", user_requirements="")
        session.add(project)
        await session.flush()
        branch = RequirementBranchModel(project_id=project.id, name="test-characterization")
        session.add(branch)
        await session.flush()
        workspace = BranchWorkspaceModel(project_id=project.id, branch_id=branch.id,
                                         user_requirements=project.user_requirements)
        session.add(workspace)
        await session.flush()

        draft = {
            "project_id": project.id,
            "business_objects": [],
            "flows": [
                {
                    "flow_name": "Test Flow",
                    "flow_description": "",
                    "feature_ids": [],
                    "flow_steps": [
                        {"step_number": "S-001", "step_name": "S1", "step_description": "", "step_type": "actorAction"},
                        {"step_number": "S-002", "step_name": "S2", "step_description": "", "step_type": "systemAction"},
                        {"step_number": "S-003", "step_name": "S3", "step_description": "", "step_type": "systemAction"},
                    ],
                    "transitions": [
                        {"source_step_number": "S-001", "target_step_number": "S-002", "is_default": True},
                        {"source_step_number": "S-001", "target_step_number": "S-003", "is_default": True},
                    ],
                }
            ],
        }

        with pytest.raises(ValueError, match="duplicate_default_transition"):
            await FlowGenerationService._persist_flow_generation_draft(draft, session, workspace_id=workspace.id)

    await engine.dispose()
