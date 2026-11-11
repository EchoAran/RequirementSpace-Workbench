from backend.database.model import BranchWorkspaceModel, RequirementBranchModel
import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.modules.requirements_core.scope.application.scope_generation_service import (
    ScopeGenerationService,
)
from backend.database.database import Base
from backend.database.model import (
    ActorModel,
    FeatureModel,
    FeatureRelationModel,
    ProjectModel,
    ScopeModel,
    feature_actor_table,
)
from backend.schemas import ScopeStatus


@pytest.mark.asyncio
async def test_load_scope_generation_context_preserves_scope_and_tree():
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
        actor = ActorModel(
            project_id=project.id,
            name="Customer",
            description="",
                    workspace_id=workspace.id,
        )
        parent = FeatureModel(
            project_id=project.id,
            name="Checkout",
            description="Parent",
                     workspace_id=workspace.id,
        )
        leaf = FeatureModel(
            project_id=project.id,
            name="Review",
            description="Leaf",
                   workspace_id=workspace.id,
        )
        session.add_all([actor, parent, leaf])
        await session.flush()
        session.add(
            FeatureRelationModel(
                parent_feature_id=parent.id,
                child_feature_id=leaf.id,
                position=1,
            )
        )
        session.add(
            ScopeModel(
                feature_id=leaf.id,
                status="current",
                reason="Needed now",
                positive_summary="Value",
                negative_summary="Cost",
                positive_picture=b"positive",
                negative_picture=b"negative",
                kano_category="M",
                kano_category_name="Must-be",
                workspace_id=workspace.id,
            )
        )
        await session.execute(
            insert(feature_actor_table),
            [{"feature_id": leaf.id, "actor_id": actor.id}],
        )
        await session.flush()

        result = await ScopeGenerationService._load_project_context(
            project.id,
            session,
                           workspace_id=workspace.id,
        )

    await engine.dispose()

    requirements, feature_nodes, leaf_nodes = result
    assert requirements == "Build checkout"
    assert [
        (
            node.featureId,
            node.actorIds,
            node.parentId,
            node.childrenIds,
        )
        for node in feature_nodes
    ] == [
        (parent.id, [], None, [leaf.id]),
        (leaf.id, [actor.id], parent.id, []),
    ]
    assert [node.featureId for node in leaf_nodes] == [leaf.id]
    scope = leaf_nodes[0].scope
    assert scope.scopeStatus is ScopeStatus.CURRENT
    assert scope.reason == "Needed now"
    assert scope.positiveSummary == "Value"
    assert scope.negativeSummary == "Cost"
    assert scope.positivePictureBase64 == "cG9zaXRpdmU="
    assert scope.negativePictureBase64 == "bmVnYXRpdmU="
    assert scope.kanoCategory == "M"
    assert scope.kanoCategoryName == "Must-be"
