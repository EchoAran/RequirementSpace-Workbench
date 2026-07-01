import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

from backend.main import app
from backend.database.model import Base, ProjectModel, ProjectMemberModel, ProjectLLMConfigModel
from backend.database.database import get_session
from backend.core.security.encryption import decrypt_llm_api_key

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

def register_user(client, email, password):
    res = client.post(
        "/api/auth/register",
        json={"email": email, "password": password}
    )
    assert res.status_code == 200
    res_login = client.post(
        "/api/auth/login",
        json={"email": email, "password": password}
    )
    assert res_login.status_code == 200
    return res_login.json()["id"], res_login.cookies.get("auth_session")

@pytest.mark.asyncio
async def test_project_llm_config_workflow(test_db):
    client = TestClient(app)

    owner_id, owner_cookie = register_user(client, "owner@projllm.com", "password123")

    async with test_db() as session:
        project = ProjectModel(
            name="Project LLM Config Test",
            owner_user_id=owner_id,
            user_requirements="Project requirements text."
        )
        session.add(project)
        await session.commit()
        project_public_id = project.public_id
        project_id = project.id

    client.cookies.set("auth_session", owner_cookie)

    # 1. Get config - should return configured=False
    res_get_init = client.get(f"/api/projects/{project_public_id}/llm-config")
    assert res_get_init.status_code == 200
    assert res_get_init.json()["configured"] is False

    # 2. Put config - should succeed (200)
    res_put = client.put(
        f"/api/projects/{project_public_id}/llm-config",
        json={
            "apiUrl": "http://mock-llm.api",
            "apiKey": "sk-mock-key-12345",
            "modelName": "gpt-4o"
        }
    )
    assert res_put.status_code == 200
    assert res_put.json()["configured"] is True
    assert res_put.json()["apiUrl"] == "http://mock-llm.api"
    assert res_put.json()["apiKeyLast4"] == "2345"

    # Verify db entry is encrypted
    async with test_db() as session:
        stmt = select(ProjectLLMConfigModel).where(ProjectLLMConfigModel.project_id == project_id)
        config_db = (await session.execute(stmt)).scalar_one()
        assert config_db.api_url == "http://mock-llm.api"
        assert config_db.model_name == "gpt-4o"
        assert decrypt_llm_api_key(config_db.encrypted_api_key) == "sk-mock-key-12345"

    # 3. Get config again - should return configured=True
    res_get_updated = client.get(f"/api/projects/{project_public_id}/llm-config")
    assert res_get_updated.status_code == 200
    assert res_get_updated.json()["configured"] is True
    assert res_get_updated.json()["apiUrl"] == "http://mock-llm.api"

    # 4. Delete config - should succeed
    res_delete = client.delete(f"/api/projects/{project_public_id}/llm-config")
    assert res_delete.status_code == 200
    assert res_delete.json()["message"] == "llm_config_deleted"

    # Get config after delete - should return configured=False
    res_get_post_delete = client.get(f"/api/projects/{project_public_id}/llm-config")
    assert res_get_post_delete.status_code == 200
    assert res_get_post_delete.json()["configured"] is False

    # 5. Role-based Access Control checks (Editor role)
    editor_id, editor_cookie = register_user(client, "editor@projllm.com", "password123")
    async with test_db() as session:
        # Add editor to project
        editor_member = ProjectMemberModel(
            project_id=project_id,
            user_id=editor_id,
            role="editor",
            status="active"
        )
        session.add(editor_member)
        await session.commit()

    # Login as editor
    client.cookies.clear()
    client.cookies.set("auth_session", editor_cookie)

    # Editor should be able to read config (GET)
    res_editor_get = client.get(f"/api/projects/{project_public_id}/llm-config")
    assert res_editor_get.status_code == 200

    # Editor should NOT be able to modify config (PUT) -> 403 Forbidden
    res_editor_put = client.put(
        f"/api/projects/{project_public_id}/llm-config",
        json={
            "apiUrl": "http://mock-llm.api",
            "apiKey": "sk-mock-key-12345",
            "modelName": "gpt-4o"
        }
    )
    assert res_editor_put.status_code == 403

    # Editor should NOT be able to delete config (DELETE) -> 403 Forbidden
    res_editor_delete = client.delete(f"/api/projects/{project_public_id}/llm-config")
    assert res_editor_delete.status_code == 403

    # Editor should NOT be able to test config (POST /test) -> 403 Forbidden
    res_editor_test = client.post(
        f"/api/projects/{project_public_id}/llm-config/test",
        json={
            "apiUrl": "http://mock-llm.api",
            "apiKey": "sk-mock-key-12345",
            "modelName": "gpt-4o"
        }
    )
    assert res_editor_test.status_code == 403

