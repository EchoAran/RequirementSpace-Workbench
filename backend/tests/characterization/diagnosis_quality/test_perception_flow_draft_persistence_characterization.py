import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import selectinload, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.modules.diagnosis_quality.perception.application.draft_confirmer import (
    PerceptionDraftConfirmer,
)
from backend.database.database import Base
from backend.database.model import (
    ActorModel,
    BusinessObjectModel,
    FeatureModel,
    FlowModel,
    FlowStepModel,
    ProjectModel,
)


@pytest.mark.asyncio
async def test_persist_perception_flow_draft_preserves_mixed_graph():
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
        existing_bo = BusinessObjectModel(
            project_id=project.id,
            name="Cart",
            description="",
        )
        session.add_all([actor, feature, existing_bo])
        await session.flush()

        result = await PerceptionDraftConfirmer._persist_flow_draft(
            {
                "project_id": project.id,
                "business_objects": [
                    {
                        "is_existing": True,
                        "business_object_id": existing_bo.id,
                    },
                    {
                        "is_existing": False,
                        "business_object_id": -1,
                        "business_object_name": "Order",
                        "business_object_description": "Placed order",
                        "business_object_attributes": [
                            {
                                "business_object_attribute_name": "total",
                                "business_object_attribute_description": "Total",
                                "business_object_attribute_type": "decimal",
                                "business_object_attribute_example": "12.50",
                            }
                        ],
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
                                "input_business_object_ids": [existing_bo.id],
                                "output_business_object_ids": [-1],
                                "next_steps": [2],
                            },
                            {
                                "step_number": 2,
                                "step_name": "Submit",
                                "step_description": "",
                                "step_type": "systemAction",
                                "actor_ids": [],
                                "input_business_object_ids": [-1],
                                "output_business_object_ids": [],
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
                                "step_name": "Send",
                                "step_description": "",
                                "step_type": "systemAction",
                                "actor_ids": [],
                                "input_business_object_ids": [-1],
                                "output_business_object_ids": [],
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

    await engine.dispose()

    assert result == {
        "project_id": project.id,
        "filler_kind": "flow",
        "created_count": 3,
        "business_object_count": 1,
        "flow_count": 2,
        "flow_step_count": 3,
        "message": "perception_slot_filled",
    }
    assert [item.name for item in business_objects] == ["Cart", "Order"]
    assert business_objects[1].attributes[0].example == "12.50"
    assert [item.name for item in flows] == ["Purchase", "Receipt"]
    purchase_steps = flows[0].steps
    assert [item.id for item in flows[0].features] == [feature.id]
    assert [item.id for item in purchase_steps[0].actors] == [actor.id]
    assert [
        item.name for item in purchase_steps[0].input_business_objects
    ] == ["Cart"]
    assert [
        item.name for item in purchase_steps[0].output_business_objects
    ] == ["Order"]
    assert [item.position for item in purchase_steps[0].next_steps] == [2]
