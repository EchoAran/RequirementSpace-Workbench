import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Configure key before import
if "LLM_CONFIG_ENCRYPTION_KEY" not in os.environ:
    os.environ["LLM_CONFIG_ENCRYPTION_KEY"] = "rK9PjN_wO2v5gVjHqX8zL1_pT5yW3xM8mU7bC4tN2zI="

from backend.main import app
from backend.database.database import get_session, Base

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def crud_test_db():
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
    client.post("/api/auth/register", json=reg_payload)
    login_payload = {"email": "test_user@example.com", "password": "password123"}
    client.post("/api/auth/login", json=login_payload)


def test_project_crud_contract_flow(crud_test_db):
    client = TestClient(app)
    _register_and_login(client)

    # 1. Create a blank project
    create_payload = {
        "user_requirements": "Test PRD requirements",
        "project_name": "Test Project",
        "project_description": "Test Description"
    }
    response = client.post("/api/blank_projects", json=create_payload)
    assert response.status_code == 200
    data = response.json()
    assert "project_id" in data
    assert data["project_name"] == "Test Project"
    assert data["project_description"] == "Test Description"
    assert data["message"] == "project_created"
    
    project_id = data["project_id"]

    # 2. List projects
    response = client.get("/api/projects")
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) == 1
    p = projects[0]
    assert p["projectId"] == project_id
    assert p["name"] == "Test Project"
    assert p["statusCode"] == "not_started"
    assert p["issueCount"] == 0
    assert p["nodeCount"] == 0

    # 3. Get project detail
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["projectId"] == project_id
    assert detail["projectName"] == "Test Project"
    assert detail["projectDescription"] == "Test Description"
    assert detail["userRequirements"] == "Test PRD requirements"
    assert detail["kanoStatus"] == "missing"
    assert "unlockedStages" in detail

    # 4. Update project
    update_payload = {
        "name": "Updated Project Name",
        "description": "Updated Description"
    }
    response = client.put(f"/api/projects/{project_id}", json=update_payload)
    assert response.status_code == 200
    up = response.json()
    assert up["projectId"] == project_id
    assert up["name"] == "Updated Project Name"
    assert up["description"] == "Updated Description"
    assert up["message"] == "project_updated"

    # 5. Direct stage unlock must not be exposed.
    unlock_payload = {"stage": "what"}
    response = client.post(f"/api/projects/{project_id}/unlock-stage", json=unlock_payload)
    assert response.status_code == 404

    # 6. Delete perception slot
    response = client.delete(f"/api/projects/{project_id}/perception-slot")
    assert response.status_code == 200
    slot = response.json()
    assert slot["projectId"] == project_id
    assert slot["message"] == "perception_slot_deleted"

    # 7. Delete project
    response = client.delete(f"/api/projects/{project_id}")
    assert response.status_code == 200
    deleted = response.json()
    assert deleted["projectId"] == project_id
    assert deleted["message"] == "project_deleted"

    # 8. Check 404 for non-existent project
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "project_not_found"
