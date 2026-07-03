import os
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

if "LLM_CONFIG_ENCRYPTION_KEY" not in os.environ:
    os.environ["LLM_CONFIG_ENCRYPTION_KEY"] = "rK9PjN_wO2v5gVjHqX8zL1_pT5yW3xM8mU7bC4tN2zI="

from backend.core.stage_gates.stage_gate_evaluator import StageGateEvaluator
from backend.database.database import Base
from backend.database.model import (
    ActorModel,
    FeatureModel,
    FeatureRelationModel,
    FlowModel,
    FlowStepModel,
    ProjectModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    feature_actor_table,
)


@pytest.fixture
async def gate_test_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


def _evaluator_without_detector_findings() -> StageGateEvaluator:
    evaluator = StageGateEvaluator()
    evaluator.what_detector.detect = AsyncMock(return_value=[])
    evaluator.how_detector.detect = AsyncMock(return_value=[])
    evaluator.scope_detector.detect = AsyncMock(return_value=[])
    return evaluator


async def _create_project(session: AsyncSession, name: str) -> ProjectModel:
    project = ProjectModel(
        owner_user_id=1,
        name=name,
        description=f"{name} description",
        user_requirements=f"{name} requirements",
    )
    session.add(project)
    await session.flush()
    return project


async def _complete_what(session: AsyncSession, project_id: int) -> tuple[ActorModel, FeatureModel]:
    actor = ActorModel(project_id=project_id, name="Warehouse Clerk", description="Handles inbound stock")
    feature = FeatureModel(project_id=project_id, name="Register inbound stock", description="Create an inbound record")
    session.add_all([actor, feature])
    await session.flush()

    await session.execute(
        feature_actor_table.insert().values(feature_id=feature.id, actor_id=actor.id)
    )
    scenario = ScenarioModel(
        project_id=project_id,
        feature_id=feature.id,
        actor_id=actor.id,
        name="Warehouse clerk registers inbound stock",
        content="Given stock arrives, when the clerk records it, then inventory is updated",
    )
    session.add(scenario)
    await session.flush()

    session.add(ScenarioAcceptanceCriterionModel(
        scenario_id=scenario.id,
        position=1,
        content="Inventory quantity is updated after inbound registration",
    ))
    await session.flush()
    return actor, feature


@pytest.mark.asyncio
async def test_stage_gate_evaluator_requires_full_what_mandatory_rules(gate_test_session):
    project = await _create_project(gate_test_session, "What Gate")
    actor = ActorModel(project_id=project.id, name="Warehouse Clerk", description="Handles inbound stock")
    feature = FeatureModel(project_id=project.id, name="Register inbound stock", description="Create an inbound record")
    gate_test_session.add_all([actor, feature])
    await gate_test_session.flush()

    await gate_test_session.execute(
        feature_actor_table.insert().values(feature_id=feature.id, actor_id=actor.id)
    )
    evaluator = _evaluator_without_detector_findings()

    gates = await evaluator.evaluate_gates(project.id, gate_test_session)
    assert gates["what"] is False

    scenario = ScenarioModel(
        project_id=project.id,
        feature_id=feature.id,
        actor_id=actor.id,
        name="Warehouse clerk registers inbound stock",
        content="Given stock arrives, when the clerk records it, then inventory is updated",
    )
    gate_test_session.add(scenario)
    await gate_test_session.flush()

    gates = await evaluator.evaluate_gates(project.id, gate_test_session)
    assert gates["what"] is False

    gate_test_session.add(ScenarioAcceptanceCriterionModel(
        scenario_id=scenario.id,
        position=1,
        content="Inventory quantity is updated after inbound registration",
    ))
    await gate_test_session.flush()

    gates = await evaluator.evaluate_gates(project.id, gate_test_session)
    assert gates["what"] is True


@pytest.mark.asyncio
async def test_stage_gate_evaluator_leaf_features_are_project_scoped(gate_test_session):
    project_a = await _create_project(gate_test_session, "Project A")
    project_b = await _create_project(gate_test_session, "Project B")
    _, project_a_feature = await _complete_what(gate_test_session, project_a.id)
    foreign_child = FeatureModel(project_id=project_b.id, name="Foreign child", description="Desc")
    gate_test_session.add(foreign_child)
    await gate_test_session.flush()

    gate_test_session.add(FeatureRelationModel(
        parent_feature_id=project_a_feature.id,
        child_feature_id=foreign_child.id,
        position=1,
    ))
    await gate_test_session.flush()

    gates = await _evaluator_without_detector_findings().evaluate_gates(project_a.id, gate_test_session)
    assert gates["what"] is True


@pytest.mark.asyncio
async def test_stage_gate_evaluator_requires_flow_steps_for_how(gate_test_session):
    project = await _create_project(gate_test_session, "How Gate")
    await _complete_what(gate_test_session, project.id)
    flow = FlowModel(project_id=project.id, name="Inbound registration flow", description="Register inbound stock")
    gate_test_session.add(flow)
    await gate_test_session.flush()

    evaluator = _evaluator_without_detector_findings()
    gates = await evaluator.evaluate_gates(project.id, gate_test_session)
    assert gates["what"] is True
    assert gates["how"] is False

    gate_test_session.add(FlowStepModel(
        flow_id=flow.id,
        position=1,
        name="Record inbound stock",
        description="Clerk records the arrived stock",
        step_type="task",
    ))
    await gate_test_session.flush()

    gates = await evaluator.evaluate_gates(project.id, gate_test_session)
    assert gates["how"] is True
