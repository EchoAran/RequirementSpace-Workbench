import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.modules.requirements_core.scenario.application.scenario_generation_service import (
    ScenarioGenerationService,
)
from backend.database.database import Base
from backend.database.model import (
    ActorModel,
    BranchWorkspaceModel,
    FeatureModel,
    FeatureRelationModel,
    ProjectModel,
    RequirementBranchModel,
    feature_actor_table,
)


@pytest.mark.asyncio
async def test_load_scenario_generation_context_preserves_target_modes():
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
                description="",
                workspace_id=workspace.id,
            )
            for name in ("Customer", "Operator")
        ]
        features = [
            FeatureModel(
                project_id=project.id,
                name=name,
                description="",
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
                    "feature_id": features[1].id,
                    "actor_id": actors[1].id,
                },
                {
                    "feature_id": features[2].id,
                    "actor_id": actors[1].id,
                },
            ],
        )
        await session.flush()

        full_context = await ScenarioGenerationService._load_generation_context(
            project.id,
            None,
            None,
            "full",
            session,
                                 workspace_id=workspace.id,
        )
        single_context = (
            await ScenarioGenerationService._load_generation_context(
                project.id,
                features[1].id,
                None,
                "single",
                session,
                      workspace_id=workspace.id,
            )
        )
        pair_context = await ScenarioGenerationService._load_generation_context(
            project.id,
            features[1].id,
            actors[1].id,
            "pair",
            session,
                                 workspace_id=workspace.id,
        )
        with pytest.raises(ValueError, match="^feature_is_not_leaf$"):
            await ScenarioGenerationService._load_generation_context(
                project.id,
                features[0].id,
                None,
                "single",
                session,
                      workspace_id=workspace.id,
            )

        session.add(FeatureModel(
            project_id=project.id,
            workspace_id=workspace.id,
            name="Unselected feature without actor",
            description="",
        ))
        other_branch = RequirementBranchModel(project_id=project.id, name="other-workspace")
        session.add(other_branch)
        await session.flush()
        other_workspace = BranchWorkspaceModel(project_id=project.id, branch_id=other_branch.id)
        session.add(other_workspace)
        await session.flush()
        other_feature = FeatureModel(
            project_id=project.id, workspace_id=other_workspace.id, name="Other workspace", description="",
        )
        session.add(other_feature)
        await session.flush()
        batch_context = await ScenarioGenerationService._load_generation_context(
            project.id, None, None, "batch", session,
            workspace_id=workspace.id,
            feature_ids=[features[1].id, features[2].id],
        )
        for invalid_ids, error in [
            ([], "empty_generation_targets"),
            ([features[1].id, 999], "feature_not_found"),
            ([features[1].id, other_feature.id], "feature_not_found"),
            ([features[0].id], "feature_is_not_leaf"),
        ]:
            with pytest.raises(ValueError, match=f"^{error}$"):
                await ScenarioGenerationService._load_generation_context(
                    project.id, None, None, "batch", session,
                    workspace_id=workspace.id, feature_ids=invalid_ids,
                )
        with pytest.raises(ValueError, match="^leaf_feature_without_actor$"):
            await ScenarioGenerationService._load_generation_context(
                project.id, None, None, "full", session,
                workspace_id=workspace.id,
            )

    await engine.dispose()

    assert full_context[0] == "Build checkout"
    assert list(full_context[1]) == [actor.id for actor in actors]
    assert list(full_context[2]) == [feature.id for feature in features]
    assert full_context[3] == [
        (features[1].id, actors[0].id),
        (features[1].id, actors[1].id),
        (features[2].id, actors[1].id),
    ]
    assert single_context[3] == [
        (features[1].id, actors[0].id),
        (features[1].id, actors[1].id),
    ]
    assert pair_context[3] == [(features[1].id, actors[1].id)]
    assert batch_context[3] == full_context[3]
