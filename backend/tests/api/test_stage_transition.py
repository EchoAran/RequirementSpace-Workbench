import os
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

if "LLM_CONFIG_ENCRYPTION_KEY" not in os.environ:
    os.environ["LLM_CONFIG_ENCRYPTION_KEY"] = "rK9PjN_wO2v5gVjHqX8zL1_pT5yW3xM8mU7bC4tN2zI="

from backend.main import app
from backend.database.database import get_session, Base
from backend.database.model import (
    ActorModel,
    AuditLogModel,
    FeatureModel,
    FlowModel,
    FlowStepModel,
    ProjectModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    feature_actor_table,
    flow_step_actor_table,
)
from backend.schemas import Finding, FindingType, BlockingScope, IssueStage, IssueSeverity
from backend.api.modules.diagnosis_quality.finding.application.finding_service import FindingService

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def transition_test_db():
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session
    yield session_factory
    app.dependency_overrides.pop(get_session, None)
    await engine.dispose()


def _register_and_login(client):
    reg_payload = {"email": "test_user@example.com", "password": "password123"}
    res = client.post("/api/auth/register", json=reg_payload)
    user_id = int(res.json()["id"])
    login_payload = {"email": "test_user@example.com", "password": "password123"}
    client.post("/api/auth/login", json=login_payload)
    return user_id


async def _complete_what_stage(session_factory, public_project_id):
    async with session_factory() as session:
        project = (await session.execute(
            sa.select(ProjectModel).where(ProjectModel.public_id == public_project_id)
        )).scalar_one()
        actor = ActorModel(project_id=project.id, name="Warehouse Clerk", description="Handles inbound stock")
        feature = FeatureModel(project_id=project.id, name="Register inbound stock", description="Create an inbound record")
        session.add_all([actor, feature])
        await session.flush()
        await session.execute(feature_actor_table.insert().values(feature_id=feature.id, actor_id=actor.id))
        scenario = ScenarioModel(
            project_id=project.id,
            feature_id=feature.id,
            actor_id=actor.id,
            name="Warehouse clerk registers inbound stock",
            content="Given stock arrives, when the clerk records it, then the inventory is updated",
        )
        session.add(scenario)
        await session.flush()
        session.add(ScenarioAcceptanceCriterionModel(
            scenario_id=scenario.id,
            position=1,
            content="Inventory quantity is updated after inbound registration",
        ))
        await session.commit()


async def _complete_how_stage(session_factory, public_project_id):
    async with session_factory() as session:
        project = (await session.execute(
            sa.select(ProjectModel).where(ProjectModel.public_id == public_project_id)
        )).scalar_one()
        actor = (await session.execute(
            sa.select(ActorModel).where(ActorModel.project_id == project.id)
        )).scalars().first()
        flow = FlowModel(project_id=project.id, name="Inbound registration flow", description="Register inbound stock")
        session.add(flow)
        await session.flush()
        step = FlowStepModel(
            flow_id=flow.id,
            position=1,
            name="Record inbound stock",
            description="Clerk records the arrived stock",
            step_type="task",
        )
        session.add(step)
        await session.flush()
        await session.execute(flow_step_actor_table.insert().values(flow_step_id=step.id, actor_id=actor.id))
        await session.commit()


@pytest.mark.asyncio
async def test_stage_transition_endpoints(transition_test_db):
    client = TestClient(app)
    user_id = _register_and_login(client)

    # 1. Create a blank project
    create_payload = {
        "user_requirements": "Test PRD requirements",
        "project_name": "Test Project",
        "project_description": "Test Description"
    }
    response = client.post("/api/blank_projects", json=create_payload)
    assert response.status_code == 200
    project_id = response.json()["project_id"]

    # 2. A blank project must not be unlocked just because there are no blocking findings.
    with patch.object(FindingService, "list_findings", return_value=[]):
        response = client.post(
            f"/api/projects/{project_id}/stage-transition",
            json={"action": "enter_how", "force": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "blocked"
        assert data["unlockedStage"] is None
        assert "what" not in data["unlockedStages"]

    await _complete_what_stage(transition_test_db, project_id)

    # 3. Test transition enter_how when mandatory checks pass and there are no blocking findings.
    with patch.object(FindingService, "list_findings", return_value=[]):
        response = client.post(
            f"/api/projects/{project_id}/stage-transition",
            json={"action": "enter_how", "force": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unlocked"
        assert data["action"] == "enter_how"
        assert data["unlockedStage"] == "what"
        assert "what" in data["unlockedStages"]
        assert len(data["blockingFindings"]) == 0

    await _complete_how_stage(transition_test_db, project_id)

    # 4. Test transition enter_scope when there ARE blocking findings and force=False
    mock_finding = Finding(
        findingId="how:FLOW_ERROR:flow:1",
        type=FindingType.GATE_CONDITION,
        stage=IssueStage.HOW,
        code="FLOW_ERROR",
        severity=IssueSeverity.BLOCKING,
        title="泳道流程错误",
        description="描述测试泳道流程错误",
        blockingScope=BlockingScope.STAGE_TRANSITION,
        metadata={}
    )
    with patch.object(FindingService, "list_findings", return_value=[mock_finding]):
        response = client.post(
            f"/api/projects/{project_id}/stage-transition",
            json={"action": "enter_scope", "force": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "blocked"
        assert len(data["blockingFindings"]) == 1
        assert data["blockingFindings"][0]["code"] == "FLOW_ERROR"

    # 5. Test transition enter_scope when there ARE blocking findings and force=True
    with patch.object(FindingService, "list_findings", return_value=[mock_finding]):
        response = client.post(
            f"/api/projects/{project_id}/stage-transition",
            json={"action": "enter_scope", "force": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unlocked"
        assert data["unlockedStage"] == "how"
        assert data["unlockedStages"] == ["what", "how"] # Stable ordered: what, then how
        assert len(data["blockingFindings"]) == 0

        # Verify audit logs for forced transition
        async with transition_test_db() as session:
            res_db = await session.execute(
                sa.select(AuditLogModel).where(
                    AuditLogModel.action_type == "stage_transition_forced"
                )
            )
            log = res_db.scalar_one_or_none()
            assert log is not None
            assert log.actor_user_id == user_id
            assert log.payload["is_forced_transition"] is True
            assert log.payload["from_stage"] == "how"
            assert log.payload["target_stage"] == "scope"
            assert log.payload["blocking_finding_ids"] == ["how:FLOW_ERROR:flow:1"]
            assert log.payload["operator_id"] == user_id

    # 6. Test unlock-stage route with invalid stage (should return 400)
    response = client.post(
        f"/api/projects/{project_id}/unlock-stage",
        json={"stage": "invalid-stage-name"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_stage"

    # 7. Test unlock-stage route stable ordering and deduplication
    # Initial stages in db are "what,how" (unlocked in step 4).
    # We call unlock-stage with "what" again, should be idempotent and return stable sorted ["what", "how"]
    response = client.post(
        f"/api/projects/{project_id}/unlock-stage",
        json={"stage": "what"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["unlocked_stages"] == ["what", "how"]

    # Now we call unlock-stage with "scope", should return ["what", "how", "scope"]
    response = client.post(
        f"/api/projects/{project_id}/unlock-stage",
        json={"stage": "scope"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["unlocked_stages"] == ["what", "how", "scope"]
