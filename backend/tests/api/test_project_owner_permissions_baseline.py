"""
Baseline tests for project owner permissions.
Verifies that:
1. Owner can list and fetch their own projects.
2. Non-owner cannot list or fetch other users' projects (returns 404).
"""
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
from backend.database.model import ProjectModel

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
async def test_project_owner_permissions_isolation(test_db):
    client = TestClient(app)
    user_a_id, cookie_a = register_user(client, "user_a@perm.test", "passwordA123")
    client.cookies.clear()
    user_b_id, cookie_b = register_user(client, "user_b@perm.test", "passwordB123")

    # User A creates a project
    async with test_db() as session:
        pa = ProjectModel(name="Project A", description="A description", owner_user_id=user_a_id, user_requirements="Req A")
        session.add(pa)
        await session.commit()
        proj_a_public_id = pa.public_id

    # User A accesses Project A
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_a)
    
    # Can list Project A
    res = client.get("/api/projects")
    assert res.status_code == 200
    ids = [p["id"] for p in res.json()]
    assert proj_a_public_id in ids

    # Can get Project A details
    res = client.get(f"/api/projects/{proj_a_public_id}")
    assert res.status_code == 200
    assert res.json()["projectName"] == "Project A"

    # User B tries to access Project A
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)
    
    # Cannot list Project A
    res = client.get("/api/projects")
    assert res.status_code == 200
    ids = [p["id"] for p in res.json()]
    assert proj_a_public_id not in ids

    # Cannot get Project A details (returns 404)
    res = client.get(f"/api/projects/{proj_a_public_id}")
    assert res.status_code == 404
