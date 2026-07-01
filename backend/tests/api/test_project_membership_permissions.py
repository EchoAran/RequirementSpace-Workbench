import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

if "LLM_CONFIG_ENCRYPTION_KEY" not in os.environ:
    os.environ["LLM_CONFIG_ENCRYPTION_KEY"] = "rK9PjN_wO2v5gVjHqX8zL1_pT5yW3xM8mU7bC4tN2zI="

from backend.main import app
from backend.database.database import get_session, Base
from backend.database.model import ProjectModel, ProjectMemberModel, ProjectMemberRole, ProjectMemberStatus

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
    res = client.post("/api/auth/register", json={"email": email, "password": password})
    assert res.status_code == 200
    user_id = int(res.json()["id"])
    cookie = client.cookies.get("auth_session")
    assert cookie
    
    # Configure LLM config to avoid 409 llm_config_required errors
    res = client.put(
        "/api/account/llm-config",
        json={
            "api_url": "https://api.openai.com/v1",
            "api_key": "sk-proj-testkey123456789",
            "model_name": "gpt-4o",
        }
    )
    assert res.status_code == 200
    return user_id, cookie


@pytest.mark.asyncio
async def test_project_roles_and_permissions(test_db):
    client = TestClient(app)
    
    # 1. Register users
    owner_id, owner_cookie = register_user(client, "owner@perm.test", "password123")
    client.cookies.clear()
    editor_id, editor_cookie = register_user(client, "editor@perm.test", "password123")
    client.cookies.clear()
    viewer_id, viewer_cookie = register_user(client, "viewer@perm.test", "password123")
    client.cookies.clear()
    non_member_id, non_member_cookie = register_user(client, "nonmember@perm.test", "password123")
    
    # 2. Create project under Owner
    async with test_db() as session:
        # Note: auto_create_project_owner_member listener will run on commit
        p = ProjectModel(name="Test Collab", description="Desc", owner_user_id=owner_id, user_requirements="Reqs")
        session.add(p)
        await session.commit()
        project_id = p.public_id
        project_db_id = p.id
        
        # Add Editor membership manually
        med = ProjectMemberModel(
            project_id=project_db_id,
            user_id=editor_id,
            role=ProjectMemberRole.EDITOR.value,
            status=ProjectMemberStatus.ACTIVE.value
        )
        # Add Viewer membership manually
        mview = ProjectMemberModel(
            project_id=project_db_id,
            user_id=viewer_id,
            role=ProjectMemberRole.VIEWER.value,
            status=ProjectMemberStatus.ACTIVE.value
        )
        session.add(med)
        session.add(mview)
        await session.commit()

    # 3. Test Owner Access (Full Control)
    client.cookies.clear()
    client.cookies.set("auth_session", owner_cookie)
    
    # Read operation: GET actors
    res = client.get(f"/api/projects/{project_id}/actors")
    assert res.status_code == 200
    
    # Write operation: POST actor
    res = client.post(f"/api/projects/{project_id}/actors", json={"name": "Owner Actor", "description": "Desc"})
    assert res.status_code == 200
    
    # 4. Test Editor Access (Read + Write)
    client.cookies.clear()
    client.cookies.set("auth_session", editor_cookie)
    
    # Read operation: GET actors
    res = client.get(f"/api/projects/{project_id}/actors")
    assert res.status_code == 200
    
    # Write operation: POST actor
    res = client.post(f"/api/projects/{project_id}/actors", json={"name": "Editor Actor", "description": "Desc"})
    assert res.status_code == 200

    # 5. Test Viewer Access (Read only)
    client.cookies.clear()
    client.cookies.set("auth_session", viewer_cookie)
    
    # Read operation: GET actors
    res = client.get(f"/api/projects/{project_id}/actors")
    assert res.status_code == 200
    
    # Write operation: POST actor (should return 403 Forbidden)
    res = client.post(f"/api/projects/{project_id}/actors", json={"name": "Viewer Actor", "description": "Desc"})
    assert res.status_code == 403
    
    # 6. Test Non-Member Access (No access at all, returns 404 project_not_found)
    client.cookies.clear()
    client.cookies.set("auth_session", non_member_cookie)
    
    # Read operation: GET actors
    res = client.get(f"/api/projects/{project_id}/actors")
    assert res.status_code == 404
    
    # Write operation: POST actor
    res = client.post(f"/api/projects/{project_id}/actors", json={"name": "NonMember Actor", "description": "Desc"})
    assert res.status_code == 404

    # 7. Test Regression: Choice Group and Perception manual permission path (which uses request=None)
    # 7.1 Owner Access (insufficient role bypassed -> goes to business logic -> returns 404 because IDs are fake)
    client.cookies.clear()
    client.cookies.set("auth_session", owner_cookie)
    
    res = client.get(f"/api/projects/{project_id}/choice_groups")
    assert res.status_code == 200

    res = client.post(f"/api/projects/{project_id}/choices/9999/accept")
    assert res.status_code == 404  # bypassed permission, failed at choice_not_found
    assert res.json()["detail"] == "choice_not_found"
    
    res = client.post("/api/perception_slot_filling_drafts/actor", json={"project_id": project_id, "perception_job_id": 9999})
    assert res.status_code in (400, 404, 409)  # bypassed permission check!

    # 7.2 Viewer Access (blocked by permission check -> returns 403 Forbidden)
    client.cookies.clear()
    client.cookies.set("auth_session", viewer_cookie)
    
    # Viewer can read choice groups
    res = client.get(f"/api/projects/{project_id}/choice_groups")
    assert res.status_code == 200

    res = client.post(f"/api/projects/{project_id}/choices/9999/accept")
    assert res.status_code == 403
    assert res.json()["detail"] == "insufficient_project_role"
    
    res = client.post(f"/api/projects/{project_id}/choices/9999/regenerate")
    assert res.status_code == 403
    assert res.json()["detail"] == "insufficient_project_role"
    
    res = client.post("/api/perception_slot_filling_drafts/actor", json={"project_id": project_id, "perception_job_id": 9999})
    assert res.status_code == 403
    assert res.json()["detail"] == "insufficient_project_role"

    # 7.3 Non-Member Access (blocked by project membership -> returns 404 Not Found)
    client.cookies.clear()
    client.cookies.set("auth_session", non_member_cookie)
    
    res = client.get(f"/api/projects/{project_id}/choice_groups")
    assert res.status_code == 404

    res = client.post(f"/api/projects/{project_id}/choices/9999/accept")
    assert res.status_code == 404
    assert res.json()["detail"] == "project_not_found"
    
    res = client.post("/api/perception_slot_filling_drafts/actor", json={"project_id": project_id, "perception_job_id": 9999})
    assert res.status_code == 404
    assert res.json()["detail"] == "project_not_found"

