"""Characterization baseline test documenting that reorder_flow_steps currently destroys topology.

As specified in P0 baseline, this test records that reordering flow steps currently invokes
replace_with_linear_topology(), which strips branch/loop connections and forces linear chains.
In P2, this destructive behavior will be removed so position reordering only alters display order.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.modules.requirements_core.flow.application.flow_service import FlowService
from backend.api.modules.requirements_core.flow.application.flow_transition_service import FlowTransitionService
from backend.api.modules.requirements_core.flow.schemas import (
    FlowCreateRequest,
    FlowStepCreateRequest,
    FlowStepsReorderRequest,
    FlowTransitionCreateRequest,
)
from backend.database.database import Base
from backend.database.model import BranchWorkspaceModel, RequirementBranchModel, FlowTransitionModel, ProjectModel, UserModel, UserRole


@pytest.fixture
async def session_factory():
    """Create in-memory SQLite database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
async def test_project_id(session_factory) -> int:
    """Create project using pre-seeded user ID 1."""
    async with session_factory() as session:
        project = ProjectModel(
            name="Flow Reorder Baseline Project",
            owner_user_id=1,
        )
        session.add(project)
        await session.flush()
        branch = RequirementBranchModel(project_id=project.id, name="test-reorder")
        session.add(branch)
        await session.flush()
        workspace = BranchWorkspaceModel(project_id=project.id, branch_id=branch.id)
        session.add(workspace)
        await session.commit()
        return project.id, workspace.id


@pytest.mark.asyncio
async def test_reorder_flow_steps_preserves_branching_topology(
    session_factory, test_project_id
):
    """Target contract expectation: reordering steps must preserve existing non-linear transitions."""
    project_id, workspace_id = test_project_id
    flow_service = FlowService()
    transition_service = FlowTransitionService()
    async with session_factory() as session:
        flow = await flow_service.create_flow(
            project_id,
            FlowCreateRequest(name="Order Evaluation Flow", description="Flow with branching"),
            session,
                         workspace_id=workspace_id,
        )
        flow_id = flow.flow_id

        s1 = await flow_service.create_flow_step(
            project_id, flow_id,
            FlowStepCreateRequest(name="Step 1", description="Init", step_type="judgment"),
            session,
                       workspace_id=workspace_id,
        )
        s2 = await flow_service.create_flow_step(
            project_id, flow_id,
            FlowStepCreateRequest(name="Step 2", description="Branch A", step_type="systemAction"),
            session,
                       workspace_id=workspace_id,
        )
        s3 = await flow_service.create_flow_step(
            project_id, flow_id,
            FlowStepCreateRequest(name="Step 3", description="Branch B", step_type="systemAction"),
            session,
                       workspace_id=workspace_id,
        )
        await session.commit()

        # Wire step 1 to both step 2 and step 3 (branching)
        await transition_service.create_transition(
            project_id, flow_id,
            FlowTransitionCreateRequest(source_step_id=s1.step_id, target_step_id=s2.step_id, is_default=False, position=0),
            session,
                  workspace_id=workspace_id,
        )
        await transition_service.create_transition(
            project_id, flow_id,
            FlowTransitionCreateRequest(source_step_id=s1.step_id, target_step_id=s3.step_id, is_default=False, position=1),
            session,
                  workspace_id=workspace_id,
        )
        await session.commit()

        # Verify initial branch connections exist in FlowTransitionModel
        rows_before = (await session.execute(
            select(FlowTransitionModel).where(FlowTransitionModel.source_step_id == s1.step_id)
        )).scalars().all()
        assert len(rows_before) == 2, "Expected step 1 to have 2 branches initially"

        # Execute reorder: swap positions of s2 and s3: [s1, s3, s2]
        await flow_service.reorder_flow_steps(
            project_id, flow_id,
            FlowStepsReorderRequest(step_ids=[s1.step_id, s3.step_id, s2.step_id]),
            session,
                  workspace_id=workspace_id,
        )
        await session.commit()

        # Contract expectation: both branches (s1->s2 and s1->s3) MUST be preserved
        rows_after = (await session.execute(
            select(FlowTransitionModel).where(FlowTransitionModel.source_step_id == s1.step_id)
        )).scalars().all()
        assert len(rows_after) == 2, "Topology preservation failed: branch connections were lost"
        target_ids = {row.target_step_id for row in rows_after}
        assert target_ids == {s2.step_id, s3.step_id}
