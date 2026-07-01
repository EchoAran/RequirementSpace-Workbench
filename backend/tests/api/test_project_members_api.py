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
    return user_id, cookie


@pytest.mark.asyncio
async def test_project_members_crud_api(test_db):
    client = TestClient(app)
    
    # 1. Register Owner, Editor, and Guest users
    owner_id, owner_cookie = register_user(client, "owner@mem.test", "password123")
    client.cookies.clear()
    editor_id, editor_cookie = register_user(client, "editor@mem.test", "password123")
    client.cookies.clear()
    guest_id, guest_cookie = register_user(client, "guest@mem.test", "password123")
    
    # 2. Create Project under Owner
    async with test_db() as session:
        p = ProjectModel(name="Crud Project", description="", owner_user_id=owner_id, user_requirements="")
        session.add(p)
        await session.commit()
        project_id = p.public_id
        project_db_id = p.id
        
        # Add Editor membership
        med = ProjectMemberModel(
            project_id=project_db_id,
            user_id=editor_id,
            role=ProjectMemberRole.EDITOR.value,
            status=ProjectMemberStatus.ACTIVE.value
        )
        session.add(med)
        await session.commit()

    # 3. Test GET list members (Owner access)
    client.cookies.clear()
    client.cookies.set("auth_session", owner_cookie)
    res = client.get(f"/api/projects/{project_id}/members")
    assert res.status_code == 200
    members = res.json()
    assert len(members) == 2
    emails = [m["email"] for m in members]
    assert "owner@mem.test" in emails
    assert "editor@mem.test" in emails

    # 4. Test POST add member (Owner adds Guest as reviewer)
    res = client.post(
        f"/api/projects/{project_id}/members",
        json={"email": "guest@mem.test", "role": "reviewer"}
    )
    assert res.status_code == 200
    guest_member = res.json()
    assert guest_member["email"] == "guest@mem.test"
    assert guest_member["role"] == "reviewer"
    assert guest_member["status"] == "active"
    guest_member_id = guest_member["memberId"]

    # 5. Test PATCH update member role (Owner upgrades Guest to admin)
    res = client.patch(
        f"/api/projects/{project_id}/members/{guest_member_id}",
        json={"role": "admin", "status": "active"}
    )
    assert res.status_code == 200
    assert res.json()["role"] == "admin"

    # 6. Test guard: Cannot remove or demote the last active owner
    # Look up owner member ID from list
    res = client.get(f"/api/projects/{project_id}/members")
    owner_member_id = [m["memberId"] for m in res.json() if m["email"] == "owner@mem.test"][0]
    
    # Try to demote owner to reviewer
    res = client.patch(
        f"/api/projects/{project_id}/members/{owner_member_id}",
        json={"role": "reviewer", "status": "active"}
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "cannot_remove_last_owner"

    # Try to remove owner
    res = client.delete(f"/api/projects/{project_id}/members/{owner_member_id}")
    assert res.status_code == 400
    assert res.json()["detail"] == "cannot_remove_last_owner"

    # 7. Test Editor access restrictions (Editor cannot manage members)
    client.cookies.clear()
    client.cookies.set("auth_session", editor_cookie)
    
    # Try to add member
    res = client.post(
        f"/api/projects/{project_id}/members",
        json={"email": "some_other@mem.test", "role": "viewer"}
    )
    assert res.status_code == 403  # Editor cannot add members

    # Try to remove member
    res = client.delete(f"/api/projects/{project_id}/members/{guest_member_id}")
    assert res.status_code == 403
