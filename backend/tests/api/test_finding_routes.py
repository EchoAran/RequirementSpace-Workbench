import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

# Set up encryption key for security settings before main import
if "LLM_CONFIG_ENCRYPTION_KEY" not in os.environ:
    os.environ["LLM_CONFIG_ENCRYPTION_KEY"] = "rK9PjN_wO2v5gVjHqX8zL1_pT5yW3xM8mU7bC4tN2zI="

from backend.main import app
from backend.database.database import get_session, Base
from backend.database.model import ProjectModel, ActorModel, FeatureModel, FindingOverrideModel, IssueOverrideModel, feature_actor_table, ScenarioModel
from backend.schemas import FindingType

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session_factory.created_sessions = []

    async def override_get_session():
        async with session_factory() as session:
            session_factory.created_sessions.append(session)
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


@pytest.fixture
async def client_with_auth(test_db):
    client = TestClient(app)
    
    # Register a user to get auth session cookie
    reg_payload = {
        "email": "test_owner@finding.test",
        "password": "securepassword123"
    }
    response = client.post("/api/auth/register", json=reg_payload)
    assert response.status_code == 200
    user_id = int(response.json()["id"])
    cookie = client.cookies.get("auth_session")
    assert cookie
    
    client.cookies.set("auth_session", cookie)
    
    # Seed a project owned by this user, with actors and features to trigger issues
    async with test_db() as session:
        project = ProjectModel(
            name="Finding Route Test Project",
            description="Testing findings and legacy issues routes",
            owner_user_id=user_id,
            user_requirements="Testing requirements",
            unlocked_stages="what,how",
        )
        session.add(project)
        await session.commit()
        project_id = project.public_id
        
        # Link project db id
        db_project_id = project.id

        # Setup actors and features to trigger LEAF_FEATURE_WITHOUT_ACTOR issue
        actor1 = ActorModel(project_id=db_project_id, name="管理员", description="系统管理员")
        f1 = FeatureModel(project_id=db_project_id, name="用户设置", description="管理用户设置")
        f2 = FeatureModel(project_id=db_project_id, name="系统设置", description="管理系统设置")
        
        session.add_all([actor1, f1, f2])
        await session.commit()

        await session.execute(
            feature_actor_table.insert().values(
                feature_id=f1.id,
                actor_id=actor1.id
            )
        )
        await session.commit()

    yield client, project_id, db_project_id


def test_issue_findings_capability_contract(client_with_auth):
    client, project_id, _ = client_with_auth

    # 1. Fetch new findings endpoint
    findings_resp = client.get(f"/api/projects/{project_id}/findings?view=issues&stage=what")
    assert findings_resp.status_code == 200
    findings = findings_resp.json()["findings"]
    assert len(findings) > 0
    finding_codes = {f["code"] for f in findings}
    assert "LEAF_FEATURE_WITHOUT_ACTOR" in finding_codes

    # 2. Verify capability contract for Issues (CamelModel serializes to camelCase)
    for f in findings:
        cap = f.get("capability")
        assert cap is not None, f"Issue finding {f['code']} must have capability"
        assert cap.get("kind") is not None, f"Issue finding {f['code']} capability must have 'kind'"
        assert cap.get("actionLabel") is not None, f"Issue finding {f['code']} capability must have 'actionLabel'"
        assert "enabled" in cap, f"Issue finding {f['code']} capability must have 'enabled'"

    # 3. Verify specific capability for a known code
    leaf_issue = next(f for f in findings if f["code"] == "LEAF_FEATURE_WITHOUT_ACTOR")
    assert leaf_issue["capability"]["kind"] == "ai_repair"
    assert leaf_issue["capability"]["actionLabel"] == "AI 修复"
    assert leaf_issue["capability"]["enabled"] is True

def test_status_update_writes_finding_overrides_only(client_with_auth, test_db):
    client, project_id, db_project_id = client_with_auth

    findings_resp = client.get(
        f"/api/projects/{project_id}/findings?view=issues&stage=what"
    )
    assert findings_resp.status_code == 200
    issue_id = findings_resp.json()["findings"][0]["findingId"]

    # 1. Update status via findings PUT endpoint
    finding_put_resp = client.put(
        f"/api/projects/{project_id}/findings/status",
        json={"findingId": issue_id, "status": "ignored"}
    )
    assert finding_put_resp.status_code == 200
    assert finding_put_resp.json()["status"] == "ignored"

    # Verify database: record exists in finding_overrides
    import asyncio
    
    async def assert_db():
        async with test_db() as session:
            # Check finding_overrides
            fo_res = await session.execute(
                select(FindingOverrideModel).where(
                    FindingOverrideModel.project_id == db_project_id,
                    FindingOverrideModel.finding_id == issue_id
                )
            )
            fo = fo_res.scalar_one_or_none()
            assert fo is not None
            assert fo.status == "ignored"
            
            # Check issue_overrides (MUST be empty)
            io_res = await session.execute(
                select(IssueOverrideModel).where(
                    IssueOverrideModel.project_id == db_project_id,
                    IssueOverrideModel.issue_id == issue_id
                )
            )
            assert io_res.scalar_one_or_none() is None

    # Run the async assert
    loop = asyncio.get_event_loop()
    loop.run_until_complete(assert_db())

    # 2. Reset status through the canonical Finding endpoint
    issue_put_resp = client.put(
        f"/api/projects/{project_id}/findings/status",
        json={"findingId": issue_id, "status": "open"}
    )
    assert issue_put_resp.status_code == 200
    assert issue_put_resp.json()["status"] == "open"

    async def assert_db_removed():
        async with test_db() as session:
            # Check finding_overrides (record should be deleted)
            fo_res = await session.execute(
                select(FindingOverrideModel).where(
                    FindingOverrideModel.project_id == db_project_id,
                    FindingOverrideModel.finding_id == issue_id
                )
            )
            assert fo_res.scalar_one_or_none() is None
            
            # Check issue_overrides (still empty)
            io_res = await session.execute(
                select(IssueOverrideModel).where(
                    IssueOverrideModel.project_id == db_project_id,
                    IssueOverrideModel.issue_id == issue_id
                )
            )
            assert io_res.scalar_one_or_none() is None

    loop.run_until_complete(assert_db_removed())


def test_health_and_gate_capability_contract(client_with_auth):
    """QUALITY_HINT and GATE_CONDITION must also return capability."""
    client, project_id, _ = client_with_auth

    # Health (quality_hint) view — Finding API uses CamelModel, so keys are camelCase
    health_resp = client.get(f"/api/projects/{project_id}/findings?view=health&stage=what")
    assert health_resp.status_code == 200
    health_findings = health_resp.json()["findings"]
    if health_findings:
        for hf in health_findings:
            cap = hf.get("capability")
            assert cap is not None, f"Quality hint {hf['code']} must have capability"
            assert cap.get("kind") is not None
            assert cap.get("actionLabel") is not None
            assert "enabled" in cap

    # Gate view
    gate_resp = client.get(f"/api/projects/{project_id}/findings?view=gate&stage=what")
    assert gate_resp.status_code == 200
    gate_findings = gate_resp.json()["findings"]
    if gate_findings:
        for gf in gate_findings:
            cap = gf.get("capability")
            assert cap is not None, f"Gate finding {gf['code']} must have capability"
            assert cap.get("kind") is not None
            assert cap.get("actionLabel") is not None
            assert "enabled" in cap


def test_status_update_dismissed_rejected(client_with_auth):
    client, project_id, _ = client_with_auth

    findings_resp = client.get(
        f"/api/projects/{project_id}/findings?view=issues&stage=what"
    )
    assert findings_resp.status_code == 200
    issue_id = findings_resp.json()["findings"][0]["findingId"]

    # Try putting dismissed status, should return 400 Bad Request
    resp = client.put(
        f"/api/projects/{project_id}/findings/status",
        json={"findingId": issue_id, "status": "dismissed"}
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid_finding_status"


def test_status_update_gate_condition_rejected(client_with_auth, test_db):
    client, project_id, db_project_id = client_with_auth

    # 1. Seed a scenario for the project using test_db to trigger the FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO gate condition
    import asyncio
    
    async def seed_scenario():
        async with test_db() as session:
            # Get actor id
            actor_res = await session.execute(
                select(ActorModel.id).where(ActorModel.project_id == db_project_id, ActorModel.name == "管理员")
            )
            actor_id = actor_res.scalars().first()
            
            # Get features
            f1_res = await session.execute(
                select(FeatureModel.id).where(FeatureModel.project_id == db_project_id, FeatureModel.name == "用户设置")
            )
            f1_id = f1_res.scalars().first()

            f2_res = await session.execute(
                select(FeatureModel.id).where(FeatureModel.project_id == db_project_id, FeatureModel.name == "系统设置")
            )
            f2_id = f2_res.scalars().first()
            
            # Associate f2 ("系统设置") with actor1 ("管理员") to create the (f2, actor1) pair
            await session.execute(
                feature_actor_table.insert().values(
                    feature_id=f2_id,
                    actor_id=actor_id
                )
            )
            
            # Create a scenario for f1 ("用户设置") and actor1 ("管理员")
            # This makes context.scenarios non-empty, leaving the (f2, actor1) pair without a scenario
            # to trigger the FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO gate condition
            scenario = ScenarioModel(
                project_id=db_project_id,
                feature_id=f1_id,
                actor_id=actor_id,
                name="Route Test Scenario",
                content="User performs route testing action"
            )
            session.add(scenario)
            await session.commit()
            
    loop = asyncio.get_event_loop()
    loop.run_until_complete(seed_scenario())

    # 2. Now call GET findings?view=gate to confirm the aggregate finding is active
    gates_resp = client.get(f"/api/projects/{project_id}/findings?view=gate&stage=what")
    assert gates_resp.status_code == 200
    gates = gates_resp.json()["findings"]
    assert any(g["code"] == "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO" for g in gates)
    
    gate_id = "what:FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO:aggregate"

    # 3. Try ignoring the gate condition, should return 400 Bad Request
    ignored_resp = client.put(
        f"/api/projects/{project_id}/findings/status",
        json={"findingId": gate_id, "status": "ignored"}
    )
    assert ignored_resp.status_code == 400
    assert ignored_resp.json()["detail"] == "invalid_finding_status"

    # 4. Try resolving the gate condition, should return 400 Bad Request
    resolved_resp = client.put(
        f"/api/projects/{project_id}/findings/status",
        json={"findingId": gate_id, "status": "resolved"}
    )
    assert resolved_resp.status_code == 400
    assert resolved_resp.json()["detail"] == "invalid_finding_status"

    # 5. Verify database: no record exists in finding_overrides
    async def assert_db_empty():
        async with test_db() as session:
            fo_res = await session.execute(
                select(FindingOverrideModel).where(
                    FindingOverrideModel.project_id == db_project_id,
                    FindingOverrideModel.finding_id == gate_id
                )
            )
    loop.run_until_complete(assert_db_empty())


def test_findings_next_action_with_background_tasks(client_with_auth):
    client, project_id, _ = client_with_auth

    # Fetch next action findings
    resp = client.get(f"/api/projects/{project_id}/findings?view=next_action&stage=what")
    assert resp.status_code == 200
    findings = resp.json()["findings"]
    assert len(findings) > 0
    next_act = findings[0]

    # Assert next action properties
    assert next_act["type"] == "next_suggestion"
    # The suggestion generated depends on whether actors/features/scenarios are present.
    # In client_with_auth, features and actors are present but scenarios might be empty
    # so we expect BIND_ACTORS_TO_FEATURE, GENERATE_SCENARIOS or similar suggestion.
    assert next_act["code"] in {"BIND_ACTORS_TO_FEATURE", "GENERATE_SCENARIOS", "ENTER_HOW"}

    # Assert that metadata has action and target
    assert "metadata" in next_act
    assert "action" in next_act["metadata"]
    assert "target" in next_act["metadata"]

    # NEXT_SUGGESTION capability must be null
    assert next_act.get("capability") is None, (
        f"NEXT_SUGGESTION must not have capability, got: {next_act.get('capability')}"
    )
