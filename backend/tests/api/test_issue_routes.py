import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, AsyncMock
from sqlalchemy import select

if "LLM_CONFIG_ENCRYPTION_KEY" not in os.environ:
    os.environ["LLM_CONFIG_ENCRYPTION_KEY"] = "rK9PjN_wO2v5gVjHqX8zL1_pT5yW3xM8mU7bC4tN2zI="

from backend.main import app
from backend.database.database import get_session, Base
from backend.database.model import ProjectModel, UserModel, ActorModel, FeatureModel, ScenarioModel, feature_actor_table

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


@pytest.fixture
async def client_with_auth(test_db):
    client = TestClient(app)
    
    # Register user
    reg_payload = {
        "email": "test_owner@issue.test",
        "password": "securepassword123"
    }
    response = client.post("/api/auth/register", json=reg_payload)
    assert response.status_code == 200
    user_id = int(response.json()["id"])
    cookie = client.cookies.get("auth_session")
    assert cookie
    client.cookies.set("auth_session", cookie)

    # Seed UserLLMConfig to pass get_llm_context dependency
    async with test_db() as session:
        from backend.database.model import UserLLMConfigModel
        from backend.core.security.encryption import encrypt_llm_api_key
        llm_config = UserLLMConfigModel(
            user_id=user_id,
            api_url="http://localhost:8000",
            encrypted_api_key=encrypt_llm_api_key("sk-testkey1234567890"),
            api_key_last4="890",
            model_name="gpt-4o",
        )
        session.add(llm_config)
        
        project = ProjectModel(
            name="Issue Route Test Project",
            description="Testing issues resolve route",
            owner_user_id=user_id,
            unlocked_stages="what",
        )
        session.add(project)
        await session.commit()
        project_id = project.public_id
        db_project_id = project.id

    yield client, project_id, db_project_id


def test_resolve_issue_repair_draft(client_with_auth):
    client, project_id, db_project_id = client_with_auth

    mock_response = {
        "project_id": db_project_id,
        "issue_code": "SCOPE_WITHOUT_REASON",
        "resolution_type": "repair_draft",
        "title": "Add reason to scope",
        "description": "Rationale for adding reason",
        "action": {
            "kind": "show_repair_draft",
            "draft_id": "draft-123",
            "payload": {
                "project_id": db_project_id,
                "draft": {"project_id": db_project_id}
            }
        },
        "draft_id": "draft-123",
        "draft": {"project_id": db_project_id},
        "patch": {},
        "issue_fingerprint": "fp-123",
        "context_hash": "hash-123"
    }

    with patch("backend.api.modules.diagnosis_quality.issue_repair.application.issue_repair_service.IssueRepairService.resolve", return_value=mock_response):
        payload = {
            "issue_id": "what:SCOPE_WITHOUT_REASON:feature:1",
            "issue_code": "SCOPE_WITHOUT_REASON",
            "stage": "what",
            "target": {"target_type": "feature", "target_id": 1},
            "metadata": {}
        }
        resp = client.post(f"/api/projects/{project_id}/issues/resolve", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolutionType"] == "repair_draft"
        assert data["projectId"] == project_id
        assert data["action"]["payload"]["project_id"] == project_id
        assert data["draft"]["project_id"] == project_id


def test_resolve_issue_unsupported(client_with_auth):
    client, project_id, _ = client_with_auth

    payload = {
        "issue_id": "what:UNKNOWN_CODE:feature:1",
        "issue_code": "UNKNOWN_CODE",
        "stage": "what",
        "target": {"target_type": "feature", "target_id": 1},
        "metadata": {}
    }
    # Resolve against unknown code: IssueRepairService will find matched_issue is None
    # and return resolution_type: unsupported
    resp = client.post(f"/api/projects/{project_id}/issues/resolve", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolutionType"] == "unsupported"
    assert "暂不支持自动处理" in data["title"]



def test_resolve_issue_gate_feature_actor_pair_active(client_with_auth, test_db):
    """FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO gate must be resolvable with
    a composite feature_actor_pair target directly from the findings API.
    We create one pair with a scenario and another pair without a scenario
    to trigger the detector and pass the non-equilibrium rule. Then we fetch
    the aggregate gate condition finding and resolve it.
    """
    import asyncio
    import json
    client, pub_id, db_project_id = client_with_auth

    async def seed_pairs():
        async with test_db() as session:
            actor = ActorModel(project_id=db_project_id, name="测试角色", description="测试角色描述")
            f1 = FeatureModel(project_id=db_project_id, name="功能一", description="功能一描述")
            f2 = FeatureModel(project_id=db_project_id, name="功能二", description="功能二描述")
            session.add_all([actor, f1, f2])
            await session.commit()

            actor_id = actor.id
            f1_id = f1.id
            f2_id = f2.id

            # Associate both features with the actor
            await session.execute(
                feature_actor_table.insert().values(
                    [
                        {"feature_id": f1_id, "actor_id": actor_id},
                        {"feature_id": f2_id, "actor_id": actor_id},
                    ]
                )
            )

            # Create one scenario for (f1, actor)
            scenario = ScenarioModel(
                project_id=db_project_id,
                feature_id=f1_id,
                actor_id=actor_id,
                name="已有场景",
                content="场景内容描述",
            )
            session.add(scenario)
            await session.commit()
            return f2_id, actor_id

    loop = asyncio.get_event_loop()
    f2_id, actor_id = loop.run_until_complete(seed_pairs())

    # 1. Call GET findings?view=gate to get the aggregate Gate finding
    gates_resp = client.get(f"/api/projects/{pub_id}/findings?view=gate&stage=what")
    assert gates_resp.status_code == 200
    gates = gates_resp.json()["findings"]
    
    target_gate = None
    for gate in gates:
        if gate["code"] == "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO" and gate["findingId"] == "what:FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO:aggregate":
            target_gate = gate
            break
            
    assert target_gate is not None, "Expected aggregated gate condition for FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO"
    
    # 2. Extract targets from gate metadata to ensure it's correct
    missing_pairs = target_gate["metadata"]["missing_pairs"]
    assert len(missing_pairs) > 0
    assert missing_pairs[0]["feature_id"] == f2_id
    assert missing_pairs[0]["actor_id"] == actor_id

    # Mock the LLM call to return a valid repair candidate
    mock_llm_response = {
        "candidates": [
            {
                "repair_type": "reassign_scenario_feature",
                "title": "将已有场景重新分配给此功能与参与者对",
                "rationale": "该场景内容与当前功能更契合",
                "confidence": 0.85,
                "patch": {
                    "updateNodes": [
                        {
                            "kind": "scenario",
                            "id": 1,
                            "feature_id": f2_id
                        }
                    ]
                },
                "requires_user_decision": False
            }
        ]
    }

    # 3. Call issues/resolve and verify it actually succeeds with repair_draft and not already_resolved or unsupported
    with patch("backend.services.LLM_service.LLMHandler.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = json.dumps(mock_llm_response)
        
        payload = {
            "issue_id": target_gate["findingId"],
            "issue_code": "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO",
            "stage": "what",
            "target": {"target_type": "feature_actor_pair", "target_id": f"{f2_id}:{actor_id}"},
            "metadata": {},
        }
        resp = client.post(f"/api/projects/{pub_id}/issues/resolve", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["resolutionType"] == "repair_draft", f"Expected repair_draft, got: {data}"



def test_resolve_issue_already_resolved(client_with_auth):
    client, project_id, _ = client_with_auth

    payload = {
        "issue_id": "what:SCOPE_WITHOUT_REASON:feature:99",
        "issue_code": "SCOPE_WITHOUT_REASON",
        "stage": "what",
        "target": {"target_type": "feature", "target_id": 99},
        "metadata": {}
    }
    # For a target that does not exist in the database (like feature ID 99),
    # IssueRepairService will detect matched_issue is None but since code is known (SCOPE_WITHOUT_REASON),
    # it returns already_resolved.
    resp = client.post(f"/api/projects/{project_id}/issues/resolve", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolutionType"] == "already_resolved"
    assert data["title"] == "该问题已解决"
