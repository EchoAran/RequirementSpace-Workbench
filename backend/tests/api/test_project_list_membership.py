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
async def test_project_list_membership_filtering(test_db):
    client = TestClient(app)

    # 1. Register User A and User B
    user_a_id, cookie_a = register_user(client, "usera@list.test", "password123")
    client.cookies.clear()
    user_b_id, cookie_b = register_user(client, "userb@list.test", "password123")

    # 2. Create projects and memberships
    async with test_db() as session:
        # Project A owned by User A (automatic owner membership created by event listener)
        pa = ProjectModel(name="Project A", description="", owner_user_id=user_a_id, user_requirements="")
        session.add(pa)
        
        # Project B owned by User B
        pb = ProjectModel(name="Project B", description="", owner_user_id=user_b_id, user_requirements="")
        session.add(pb)
        await session.commit()
        
        proj_a_public_id = pa.public_id
        proj_b_public_id = pb.public_id
        proj_b_db_id = pb.id

        # Add User A as an editor member of Project B
        mb = ProjectMemberModel(
            project_id=proj_b_db_id,
            user_id=user_a_id,
            role=ProjectMemberRole.EDITOR.value,
            status=ProjectMemberStatus.ACTIVE.value
        )
        session.add(mb)
        await session.commit()

    # 3. User A lists projects (should see both Project A and Project B)
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_a)
    res = client.get("/api/projects")
    assert res.status_code == 200
    projects_a = res.json()
    assert len(projects_a) == 2
    ids_a = [p["id"] for p in projects_a]
    assert proj_a_public_id in ids_a
    assert proj_b_public_id in ids_a

    # Check that membership fields are populated
    proj_b_item = [p for p in projects_a if p["id"] == proj_b_public_id][0]
    assert proj_b_item["membershipRole"] == "editor"
    assert proj_b_item["ownerUserId"] == user_b_id
    assert proj_b_item["memberCount"] == 2  # Owner B + Editor A

    # 4. User B lists projects (should see ONLY Project B)
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)
    res = client.get("/api/projects")
    assert res.status_code == 200
    projects_b = res.json()
    assert len(projects_b) == 1
    assert projects_b[0]["id"] == proj_b_public_id
    assert projects_b[0]["membershipRole"] == "owner"
    assert projects_b[0]["memberCount"] == 2
