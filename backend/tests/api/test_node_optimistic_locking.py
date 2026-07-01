import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.database.model import Base, ProjectModel, ActorModel, ProjectMemberModel
from backend.database.database import get_session

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
async def test_node_optimistic_locking_workflow(test_db):
    client = TestClient(app)

    # Register users
    owner_id, owner_cookie = register_user(client, "owner@lock.com", "password123")
    editor_id, editor_cookie = register_user(client, "editor@lock.com", "password123")

    async with test_db() as session:
        project = ProjectModel(
            name="Locking Project",
            owner_user_id=owner_id,
            user_requirements="Project description."
        )
        session.add(project)
        await session.commit()
        project_public_id = project.public_id
        project_id = project.id

        editor_member = ProjectMemberModel(project_id=project_id, user_id=editor_id, role="editor", status="active")
        session.add(editor_member)

        # Add Actor
        actor = ActorModel(project_id=project_id, name="Test Lock Actor", description="Lock Desc")
        session.add(actor)
        await session.commit()
        actor_id = actor.id
        actor_updated_at = actor.updated_at

    # 1. Update actor as editor with matching last_seen_updated_at -> Should succeed (200)
    client.cookies.set("auth_session", editor_cookie)
    res = client.put(
        f"/api/projects/{project_public_id}/actors/{actor_id}",
        json={
            "name": "Updated Name",
            "lastSeenUpdatedAt": actor_updated_at.isoformat()
        }
    )
    assert res.status_code == 200

    # 2. Update actor again with same stale last_seen_updated_at -> Should fail with 409
    res_stale = client.put(
        f"/api/projects/{project_public_id}/actors/{actor_id}",
        json={
            "name": "Another Update",
            "lastSeenUpdatedAt": actor_updated_at.isoformat()
        }
    )
    assert res_stale.status_code == 409
    detail = res_stale.json()["detail"]
    assert detail["message"] == "node_content_changed"
    assert "current_snapshot" in detail
    assert detail["current_snapshot"]["name"] == "Updated Name"
