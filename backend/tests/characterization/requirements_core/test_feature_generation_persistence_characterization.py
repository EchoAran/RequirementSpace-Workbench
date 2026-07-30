import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.modules.requirements_core.feature.application.feature_generation_service import (
    FeatureGenerationService,
)
from backend.database.database import Base
from backend.database.model import (
    ActorModel,
    FeatureModel,
    FeatureRelationModel,
    ProjectModel,
    feature_actor_table,
)


@pytest.mark.asyncio
async def test_persist_feature_generation_draft_preserves_tree_and_project():
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
            name=" ",
            description="",
            user_requirements="Build checkout",
        )
        session.add(project)
        await session.flush()
        actor = ActorModel(
            project_id=project.id,
            name="Customer",
            description="",
        )
        session.add(actor)
        await session.flush()

        result = await FeatureGenerationService()._persist_feature_generation_draft(
            {
                "project_id": project.id,
                "features": [
                    {
                        "feature_number": "F001",
                        "feature_name": "Checkout",
                        "feature_description": "Checkout root",
                        "actor_ids": [],
                    },
                    {
                        "feature_number": "F001-001",
                        "feature_name": "Review",
                        "feature_description": "Review cart",
                        "actor_ids": [actor.id],
                    },
                    {
                        "feature_number": "F001-002",
                        "feature_name": "Submit",
                        "feature_description": "Submit order",
                        "actor_ids": [actor.id],
                    },
                ],
            },
            session,
        )

        features = (
            await session.execute(
                select(FeatureModel).order_by(FeatureModel.id)
            )
        ).scalars().all()
        relations = (
            await session.execute(
                select(FeatureRelationModel).order_by(
                    FeatureRelationModel.position
                )
            )
        ).scalars().all()
        actor_rows = (
            await session.execute(
                select(
                    feature_actor_table.c.feature_id,
                    feature_actor_table.c.actor_id,
                ).order_by(feature_actor_table.c.feature_id)
            )
        ).all()

    await engine.dispose()

    assert result == {
        "project_id": project.id,
        "feature_count": 3,
        "message": "features_created",
    }
    assert project.name == "Checkout"
    assert project.description == "Checkout root"
    assert [
        (feature.name, feature.confirmation_status)
        for feature in features
    ] == [
        ("Checkout", "ai_assumption"),
        ("Review", "ai_assumption"),
        ("Submit", "ai_assumption"),
    ]
    assert [
        (
            relation.parent_feature_id,
            relation.child_feature_id,
            relation.position,
        )
        for relation in relations
    ] == [
        (features[0].id, features[1].id, 1),
        (features[0].id, features[2].id, 2),
    ]
    assert actor_rows == [
        (features[1].id, actor.id),
        (features[2].id, actor.id),
    ]
