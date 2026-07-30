import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.modules.requirements_core.scenario.application.acceptance_criteria_generation_service import (
    AcceptanceCriteriaGenerationService,
)
from backend.database.database import Base
from backend.database.model import (
    ActorModel,
    FeatureModel,
    ProjectModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
)


@pytest.mark.asyncio
async def test_load_acceptance_criteria_context_preserves_selection_and_errors():
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
                description="",
            )
            for name in ("Customer", "Operator")
        ]
        features = [
            FeatureModel(
                project_id=project.id,
                name=name,
                description="",
            )
            for name in ("Review", "Submit")
        ]
        session.add_all([*actors, *features])
        await session.flush()
        scenarios = [
            ScenarioModel(
                project_id=project.id,
                feature_id=features[index].id,
                actor_id=actors[index].id,
                name=name,
                content=f"{name} content",
            )
            for index, name in enumerate(("Review cart", "Submit order"))
        ]
        session.add_all(scenarios)
        await session.flush()

        result = (
            await AcceptanceCriteriaGenerationService._load_generation_context(
                project.id,
                [scenarios[1].id, scenarios[0].id],
                session,
            )
        )
        with pytest.raises(ValueError, match="^duplicate_scenario_id$"):
            await AcceptanceCriteriaGenerationService._load_generation_context(
                project.id,
                [scenarios[0].id, scenarios[0].id],
                session,
            )

        session.add(
            ScenarioAcceptanceCriterionModel(
                scenario_id=scenarios[0].id,
                position=1,
                content="Cart is reviewed",
            )
        )
        await session.flush()
        with pytest.raises(
            ValueError,
            match="^acceptance_criteria_already_exist$",
        ):
            await AcceptanceCriteriaGenerationService._load_generation_context(
                project.id,
                [scenarios[0].id],
                session,
            )

    await engine.dispose()

    requirements, actor_nodes, feature_nodes, scenario_nodes = result
    assert requirements == "Build checkout"
    assert list(actor_nodes) == [actor.id for actor in actors]
    assert list(feature_nodes) == [feature.id for feature in features]
    assert [
        (
            node.scenarioId,
            node.scenarioName,
            node.featureId,
            node.actorId,
            node.acceptanceCriteria,
        )
        for node in scenario_nodes
    ] == [
        (
            scenarios[0].id,
            "Review cart",
            features[0].id,
            actors[0].id,
            [],
        ),
        (
            scenarios[1].id,
            "Submit order",
            features[1].id,
            actors[1].id,
            [],
        ),
    ]
