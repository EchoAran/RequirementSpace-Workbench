"""Tests for FlowTransition position collision handling and reordering."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.modules.requirements_core.flow.application.flow_transition_service import (
    FlowTransitionService,
)
from backend.api.modules.requirements_core.flow.schemas import (
    FlowTransitionCreateRequest,
    FlowTransitionUpdateRequest,
)
from backend.database.database import Base
from backend.database.model import (
    BranchWorkspaceModel,
    FlowModel,
    FlowStepModel,
    ProjectModel,
    RequirementBranchModel,
)
from backend.schemas import FlowStepType


@pytest.fixture
async def async_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _setup_fixture(session: AsyncSession):
    project = ProjectModel(owner_user_id=1, name="Test Project", description="Desc", user_requirements="Reqs")
    session.add(project)
    await session.flush()

    branch = RequirementBranchModel(project_id=project.id, name="main")
    session.add(branch)
    await session.flush()

    workspace = BranchWorkspaceModel(project_id=project.id, branch_id=branch.id, user_requirements="Reqs")
    session.add(workspace)
    await session.flush()

    flow = FlowModel(
        project_id=project.id,
        workspace_id=workspace.id,
        name="Collision Test Flow",
        description="Flow for collision tests",
    )
    session.add(flow)
    await session.flush()

    steps = []
    for i in range(1, 5):
        s = FlowStepModel(
            flow_id=flow.id,
            workspace_id=workspace.id,
            name=f"Step {i}",
            step_type=FlowStepType.SYSTEM_ACTION,
            position=i - 1,
        )
        session.add(s)
        steps.append(s)
    await session.flush()

    return project, workspace, flow, steps


@pytest.mark.asyncio
async def test_update_transition_position_to_existing_sibling_avoids_collision(async_session: AsyncSession):
    """Updating position to an existing sibling's position should shift siblings and not fail UniqueConstraint."""
    project, workspace, flow, steps = await _setup_fixture(async_session)
    service = FlowTransitionService()

    # Step 1 -> Step 2 (pos=0)
    t1 = await service.create_transition(
        project_id=project.id,
        flow_id=flow.id,
        request=FlowTransitionCreateRequest(source_step_id=steps[0].id, target_step_id=steps[1].id),
        session=async_session,
        workspace_id=workspace.id,
    )
    assert t1.position == 0

    # Step 1 -> Step 3 (pos=1)
    t2 = await service.create_transition(
        project_id=project.id,
        flow_id=flow.id,
        request=FlowTransitionCreateRequest(source_step_id=steps[0].id, target_step_id=steps[2].id),
        session=async_session,
        workspace_id=workspace.id,
    )
    assert t2.position == 1

    # Step 1 -> Step 4 (pos=2)
    t3 = await service.create_transition(
        project_id=project.id,
        flow_id=flow.id,
        request=FlowTransitionCreateRequest(source_step_id=steps[0].id, target_step_id=steps[3].id),
        session=async_session,
        workspace_id=workspace.id,
    )
    assert t3.position == 2

    # Now update t3 position to 0 (which is currently held by t1)
    # This must NOT throw IntegrityError / uq_flow_transition_source_position
    updated_t3 = await service.update_transition(
        project_id=project.id,
        flow_id=flow.id,
        transition_id=t3.id,
        request=FlowTransitionUpdateRequest(position=0),
        session=async_session,
        workspace_id=workspace.id,
    )
    assert updated_t3.position == 0

    # Verify all siblings have normalized, unique sequential positions
    fetched_t1 = await service.get_transition(project.id, flow.id, t1.id, async_session, workspace_id=workspace.id)
    fetched_t2 = await service.get_transition(project.id, flow.id, t2.id, async_session, workspace_id=workspace.id)
    fetched_t3 = await service.get_transition(project.id, flow.id, t3.id, async_session, workspace_id=workspace.id)

    assert fetched_t3.position == 0
    assert fetched_t1.position == 1
    assert fetched_t2.position == 2


@pytest.mark.asyncio
async def test_create_transition_with_colliding_position_shifts_siblings(async_session: AsyncSession):
    """Creating transition with an explicit position that collides should shift existing siblings."""
    project, workspace, flow, steps = await _setup_fixture(async_session)
    service = FlowTransitionService()

    # Step 1 -> Step 2 (pos=0)
    t1 = await service.create_transition(
        project_id=project.id,
        flow_id=flow.id,
        request=FlowTransitionCreateRequest(source_step_id=steps[0].id, target_step_id=steps[1].id, position=0),
        session=async_session,
        workspace_id=workspace.id,
    )
    assert t1.position == 0

    # Step 1 -> Step 3 (explicit pos=0, collides with t1)
    t2 = await service.create_transition(
        project_id=project.id,
        flow_id=flow.id,
        request=FlowTransitionCreateRequest(source_step_id=steps[0].id, target_step_id=steps[2].id, position=0),
        session=async_session,
        workspace_id=workspace.id,
    )
    assert t2.position == 0

    fetched_t1 = await service.get_transition(project.id, flow.id, t1.id, async_session, workspace_id=workspace.id)
    assert fetched_t1.position == 1


@pytest.mark.asyncio
async def test_delete_transition_normalizes_positions(async_session: AsyncSession):
    """Deleting a transition should re-normalize remaining sibling positions to 0, 1, ..."""
    project, workspace, flow, steps = await _setup_fixture(async_session)
    service = FlowTransitionService()

    t1 = await service.create_transition(
        project_id=project.id,
        flow_id=flow.id,
        request=FlowTransitionCreateRequest(source_step_id=steps[0].id, target_step_id=steps[1].id),
        session=async_session,
        workspace_id=workspace.id,
    )
    t2 = await service.create_transition(
        project_id=project.id,
        flow_id=flow.id,
        request=FlowTransitionCreateRequest(source_step_id=steps[0].id, target_step_id=steps[2].id),
        session=async_session,
        workspace_id=workspace.id,
    )
    t3 = await service.create_transition(
        project_id=project.id,
        flow_id=flow.id,
        request=FlowTransitionCreateRequest(source_step_id=steps[0].id, target_step_id=steps[3].id),
        session=async_session,
        workspace_id=workspace.id,
    )

    # Delete t2 (pos=1)
    await service.delete_transition(project.id, flow.id, t2.id, async_session, workspace_id=workspace.id)

    fetched_t1 = await service.get_transition(project.id, flow.id, t1.id, async_session, workspace_id=workspace.id)
    fetched_t3 = await service.get_transition(project.id, flow.id, t3.id, async_session, workspace_id=workspace.id)

    assert fetched_t1.position == 0
    assert fetched_t3.position == 1
