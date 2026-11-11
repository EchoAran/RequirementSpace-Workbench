"""Unit tests for the PathProjectionEngine domain logic."""

import pytest

from backend.core.path_projection import (
    PathProjectionEngine,
    PathStepNode,
    PathTransitionEdge,
)


def test_linear_flow_path_projection():
    """Verify standard single-chain linear flow computes single main path."""
    steps = [
        PathStepNode(id=1, logical_uuid="u-1", position=1, name="Step 1"),
        PathStepNode(id=2, logical_uuid="u-2", position=2, name="Step 2"),
        PathStepNode(id=3, logical_uuid="u-3", position=3, name="Step 3"),
    ]
    transitions = [
        PathTransitionEdge(
            id=101, logical_uuid="t-1", source_step_id=1, target_step_id=2,
            label="", condition_text="", is_default=False, position=0
        ),
        PathTransitionEdge(
            id=102, logical_uuid="t-2", source_step_id=2, target_step_id=3,
            label="", condition_text="", is_default=False, position=0
        ),
    ]
    engine = PathProjectionEngine(steps, transitions)
    paths = engine.compute_projections()

    assert len(paths) == 1
    assert paths[0].is_main is True
    assert paths[0].status == "complete"
    assert paths[0].step_ids == [1, 2, 3]
    assert paths[0].transition_ids == [101, 102]


def test_branching_flow_with_default():
    """Verify branching flow chooses default edge for main path and generates branch path."""
    steps = [
        PathStepNode(id=1, logical_uuid="u-1", position=1, name="Init"),
        PathStepNode(id=2, logical_uuid="u-2", position=2, name="Approve"),
        PathStepNode(id=3, logical_uuid="u-3", position=3, name="Reject"),
    ]
    transitions = [
        PathTransitionEdge(
            id=101, logical_uuid="t-1", source_step_id=1, target_step_id=2,
            label="Approved", condition_text="score >= 60", is_default=True, position=0
        ),
        PathTransitionEdge(
            id=102, logical_uuid="t-2", source_step_id=1, target_step_id=3,
            label="Rejected", condition_text="score < 60", is_default=False, position=1
        ),
    ]
    engine = PathProjectionEngine(steps, transitions)
    paths = engine.compute_projections()

    assert len(paths) == 2
    # Main path follows default edge to Step 2
    main = next(p for p in paths if p.is_main)
    assert main.step_ids == [1, 2]
    assert main.transition_ids == [101]
    assert main.status == "complete"

    # Branch path follows alternate edge to Step 3
    branch = next(p for p in paths if not p.is_main)
    assert branch.step_ids == [1, 3]
    assert branch.transition_ids == [102]
    assert branch.status == "complete"


def test_ambiguous_branching_without_default():
    """Verify multiple outgoing branches without a default are marked ambiguous."""
    steps = [
        PathStepNode(id=1, logical_uuid="u-1", position=1, name="Decision"),
        PathStepNode(id=2, logical_uuid="u-2", position=2, name="Choice A"),
        PathStepNode(id=3, logical_uuid="u-3", position=3, name="Choice B"),
    ]
    transitions = [
        PathTransitionEdge(
            id=101, logical_uuid="t-1", source_step_id=1, target_step_id=2,
            label="A", condition_text="", is_default=False, position=0
        ),
        PathTransitionEdge(
            id=102, logical_uuid="t-2", source_step_id=1, target_step_id=3,
            label="B", condition_text="", is_default=False, position=1
        ),
    ]
    engine = PathProjectionEngine(steps, transitions)
    paths = engine.compute_projections()

    main = next(p for p in paths if p.is_main)
    assert main.status == "ambiguous"
    assert main.step_ids == [1]


def test_multiple_entries_topology():
    """Verify multiple in-degree 0 steps produce ambiguous alternative paths."""
    steps = [
        PathStepNode(id=1, logical_uuid="u-1", position=1, name="Entry 1"),
        PathStepNode(id=2, logical_uuid="u-2", position=2, name="Entry 2"),
        PathStepNode(id=3, logical_uuid="u-3", position=3, name="Common End"),
    ]
    transitions = [
        PathTransitionEdge(
            id=101, logical_uuid="t-1", source_step_id=1, target_step_id=3,
            label="", condition_text="", is_default=False, position=0
        ),
        PathTransitionEdge(
            id=102, logical_uuid="t-2", source_step_id=2, target_step_id=3,
            label="", condition_text="", is_default=False, position=0
        ),
    ]
    engine = PathProjectionEngine(steps, transitions)
    paths = engine.compute_projections()

    assert len(paths) == 2
    assert all(p.status == "ambiguous" for p in paths)


def test_pure_cycle_topology():
    """Verify graph with no in-degree 0 steps detects cycle without infinite looping."""
    steps = [
        PathStepNode(id=1, logical_uuid="u-1", position=1, name="Node 1"),
        PathStepNode(id=2, logical_uuid="u-2", position=2, name="Node 2"),
    ]
    transitions = [
        PathTransitionEdge(
            id=101, logical_uuid="t-1", source_step_id=1, target_step_id=2,
            label="", condition_text="", is_default=True, position=0
        ),
        PathTransitionEdge(
            id=102, logical_uuid="t-2", source_step_id=2, target_step_id=1,
            label="", condition_text="", is_default=True, position=0
        ),
    ]
    engine = PathProjectionEngine(steps, transitions)
    paths = engine.compute_projections()

    assert len(paths) == 1
    assert paths[0].status == "cycle"


def test_empty_flow_projection():
    """Verify flow with zero steps produces zero projections."""
    engine = PathProjectionEngine([], [])
    assert engine.compute_projections() == []


def test_nested_branching_path_projection():
    """Verify nested branches inside a branch path are fully captured."""
    # Topology:
    # 1 -> 2 -> 3 (Main Path via 101, 102)
    # 2 -> 4 (Branch 1 via 103)
    # 4 -> 5 (Default on 4 via 104)
    # 4 -> 6 (Nested branch on 4 via 105)
    steps = [
        PathStepNode(id=1, logical_uuid="u-1", position=1, name="Step 1"),
        PathStepNode(id=2, logical_uuid="u-2", position=2, name="Step 2"),
        PathStepNode(id=3, logical_uuid="u-3", position=3, name="Step 3"),
        PathStepNode(id=4, logical_uuid="u-4", position=4, name="Step 4"),
        PathStepNode(id=5, logical_uuid="u-5", position=5, name="Step 5"),
        PathStepNode(id=6, logical_uuid="u-6", position=6, name="Step 6"),
    ]
    transitions = [
        PathTransitionEdge(id=101, logical_uuid="t-1", source_step_id=1, target_step_id=2, label="to-2", condition_text="", is_default=True, position=0),
        PathTransitionEdge(id=102, logical_uuid="t-2", source_step_id=2, target_step_id=3, label="to-3", condition_text="", is_default=True, position=0),
        PathTransitionEdge(id=103, logical_uuid="t-3", source_step_id=2, target_step_id=4, label="to-4", condition_text="", is_default=False, position=1),
        PathTransitionEdge(id=104, logical_uuid="t-4", source_step_id=4, target_step_id=5, label="to-5", condition_text="", is_default=True, position=0),
        PathTransitionEdge(id=105, logical_uuid="t-5", source_step_id=4, target_step_id=6, label="to-6", condition_text="", is_default=False, position=1),
    ]
    engine = PathProjectionEngine(steps, transitions)
    paths = engine.compute_projections()

    # Should have 3 paths: Main (1->2->3), Branch 1 (2->4->5), Nested Branch (4->6)
    assert len(paths) == 3
    all_transition_ids = {t for p in paths for t in p.transition_ids}
    assert all_transition_ids == {101, 102, 103, 104, 105}


def test_disconnected_cycle_component_path_projection():
    """Verify flow with normal entry path and disconnected cycle component captures both."""
    # Entry flow: 1 -> 2
    # Disconnected cycle: 3 -> 4 -> 3
    steps = [
        PathStepNode(id=1, logical_uuid="u-1", position=1, name="Step 1"),
        PathStepNode(id=2, logical_uuid="u-2", position=2, name="Step 2"),
        PathStepNode(id=3, logical_uuid="u-3", position=3, name="Step 3"),
        PathStepNode(id=4, logical_uuid="u-4", position=4, name="Step 4"),
    ]
    transitions = [
        PathTransitionEdge(id=101, logical_uuid="t-1", source_step_id=1, target_step_id=2, label="", condition_text="", is_default=True, position=0),
        PathTransitionEdge(id=102, logical_uuid="t-2", source_step_id=3, target_step_id=4, label="", condition_text="", is_default=True, position=0),
        PathTransitionEdge(id=103, logical_uuid="t-3", source_step_id=4, target_step_id=3, label="", condition_text="", is_default=True, position=0),
    ]
    engine = PathProjectionEngine(steps, transitions)
    paths = engine.compute_projections()

    assert len(paths) == 2
    main = next(p for p in paths if p.is_main)
    assert main.step_ids == [1, 2]
    assert main.transition_ids == [101]

    cycle_comp = next(p for p in paths if not p.is_main)
    assert cycle_comp.status == "cycle"
    assert set(cycle_comp.transition_ids).issubset({102, 103})
    all_transition_ids = {t for p in paths for t in p.transition_ids}
    assert {101, 102, 103}.issubset(all_transition_ids)


async def test_path_projection_service_workspace_scoping():
    """Verify PathProjectionService enforces workspace_id boundaries on flow and components."""
    from fastapi import HTTPException
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from backend.database.database import Base
    from backend.database.model import (
        BranchWorkspaceModel,
        FlowModel,
        FlowStepModel,
        FlowTransitionModel,
        ProjectModel,
        RequirementBranchModel,
    )
    from backend.schemas import FlowStepType
    from backend.api.modules.requirements_core.flow.application.path_projection_service import (
        PathProjectionService,
    )

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        project = ProjectModel(owner_user_id=1, name="P1", description="", user_requirements="")
        session.add(project)
        await session.flush()

        b1 = RequirementBranchModel(project_id=project.id, name="b1")
        b2 = RequirementBranchModel(project_id=project.id, name="b2")
        session.add_all([b1, b2])
        await session.flush()

        ws1 = BranchWorkspaceModel(project_id=project.id, branch_id=b1.id, user_requirements="")
        ws2 = BranchWorkspaceModel(project_id=project.id, branch_id=b2.id, user_requirements="")
        session.add_all([ws1, ws2])
        await session.flush()

        flow1 = FlowModel(project_id=project.id, workspace_id=ws1.id, name="Flow 1", description="")
        session.add(flow1)
        await session.flush()

        s1 = FlowStepModel(flow_id=flow1.id, workspace_id=ws1.id, name="S1", step_type=FlowStepType.ACTOR_ACTION, position=0)
        s2 = FlowStepModel(flow_id=flow1.id, workspace_id=ws1.id, name="S2", step_type=FlowStepType.SYSTEM_ACTION, position=1)
        session.add_all([s1, s2])
        await session.flush()

        t1 = FlowTransitionModel(
            project_id=project.id,
            workspace_id=ws1.id,
            flow_id=flow1.id,
            source_step_id=s1.id,
            target_step_id=s2.id,
            label="T1",
            position=0,
            is_default=True,
        )
        session.add(t1)
        await session.flush()

        service = PathProjectionService()

        # 1. Querying with matching workspace_id succeeds
        resp = await service.get_path_projections(
            project_id=project.id,
            flow_id=flow1.id,
            session=session,
            workspace_id=ws1.id,
        )
        assert resp.flow_id == flow1.id
        assert len(resp.paths) == 1
        assert resp.paths[0].step_ids == [s1.id, s2.id]

        # 2. Querying with mismatching workspace_id raises 404
        with pytest.raises(HTTPException) as exc_info:
            await service.get_path_projections(
                project_id=project.id,
                flow_id=flow1.id,
                session=session,
                workspace_id=ws2.id,
            )
        assert exc_info.value.status_code == 404

    await engine.dispose()
