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
from backend.database.model import ProjectModel, ActorModel, FeatureModel, feature_actor_table

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
        "email": "test_owner@suggestion.test",
        "password": "securepassword123"
    }
    response = client.post("/api/auth/register", json=reg_payload)
    assert response.status_code == 200
    user_id = int(response.json()["id"])
    cookie = client.cookies.get("auth_session")
    assert cookie
    
    client.cookies.set("auth_session", cookie)
    
    # Seed a project owned by this user
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
            name="Suggestion Route Test Project",
            description="Testing next suggestions routes",
            owner_user_id=user_id,
            user_requirements="Testing requirements",
            unlocked_stages="what,how",
        )
        session.add(project)
        await session.commit()
        project_id = project.public_id
        db_project_id = project.id

        # Setup actors and features to trigger BIND_ACTORS_TO_FEATURE or GENERATE_SCENARIOS
        actor1 = ActorModel(project_id=db_project_id, name="管理员", description="系统管理员")
        f1 = FeatureModel(project_id=db_project_id, name="用户设置", description="管理用户设置")
        session.add_all([actor1, f1])
        await session.commit()

    yield client, project_id, db_project_id


def test_get_next_suggestion_contract(client_with_auth):
    client, project_id, db_project_id = client_with_auth

    # GET request to next-suggestion
    resp = client.get(f"/api/projects/{project_id}/next-suggestion?stage=what")
    assert resp.status_code == 200
    res_data = resp.json()
    
    # Ensure project_id returned is the public UUID string, not the integer db id
    assert res_data["projectId"] == project_id
    assert res_data["projectId"] != str(db_project_id)
    assert res_data["stage"] == "what"
    
    suggestion = res_data["suggestion"]
    if suggestion:
        assert "code" in suggestion
        assert "title" in suggestion
        action = suggestion.get("action")
        if action:
            # If there's an action, verify its route/payload doesn't leak the integer database id
            if "route" in action and action["route"]:
                assert f"/projects/{db_project_id}/" not in action["route"]
                assert project_id in action["route"]
            if "payload" in action and action["payload"]:
                if "project_id" in action["payload"]:
                    assert action["payload"].get("project_id") == project_id




def test_rediagnose_next_suggestion_contract(client_with_auth):
    client, project_id, db_project_id = client_with_auth

    # POST request to rediagnose next-suggestion
    resp = client.post(
        f"/api/projects/{project_id}/next-suggestion/rediagnose",
        json={"stage": "what"}
    )
    assert resp.status_code == 200
    res_data = resp.json()
    
    # Ensure project_id returned is public UUID string
    assert res_data["projectId"] == project_id
    assert res_data["projectId"] != str(db_project_id)
    assert res_data["stage"] == "what"


def test_start_next_suggestion_endpoint_removed(client_with_auth):
    client, project_id, _ = client_with_auth

    resp = client.post(
        f"/api/projects/{project_id}/next-suggestion/start",
        json={
            "stage": "what",
            "suggestionCode": "GENERATE_SCENARIOS",
            "target": None,
        },
    )
    assert resp.status_code == 404


    # Start COMPLETE_FLOW_STEPS suggestion — should return open_panel/flow_editor
def test_get_next_suggestion_locked_stage(client_with_auth):
    client, project_id, db_project_id = client_with_auth

    resp = client.get(f"/api/projects/{project_id}/next-suggestion?stage=preview")
    assert resp.status_code == 200
    res_data = resp.json()

    assert res_data["projectId"] == project_id
    assert res_data["projectId"] != str(db_project_id)
    assert res_data["stage"] == "preview"

    suggestion = res_data["suggestion"]
    assert suggestion is not None
    assert suggestion["code"] == "PREVIEW_READY"

    action = suggestion["action"]
    assert action["kind"] == "navigate"
    assert action["route"] == f"/projects/{project_id}/preview"
    assert f"/projects/{db_project_id}/" not in action["route"]

    resp_rediag = client.post(
        f"/api/projects/{project_id}/next-suggestion/rediagnose",
        json={"stage": "preview"}
    )
    assert resp_rediag.status_code == 200
    res_data_rediag = resp_rediag.json()
    assert res_data_rediag["projectId"] == project_id
    assert res_data_rediag["suggestion"]["code"] == "PREVIEW_READY"
    assert res_data_rediag["suggestion"]["action"]["route"] == f"/projects/{project_id}/preview"
    assert f"/projects/{db_project_id}/" not in res_data_rediag["suggestion"]["action"]["route"]
