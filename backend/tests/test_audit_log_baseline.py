"""
Baseline tests for audit logs.
Verifies that:
1. Operations on node statuses write to the audit log.
2. We can list audit logs for a project via the API.
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
from backend.database.model import ProjectModel, ActorModel, AuditLogModel

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
async def test_audit_logs_baseline(test_db):
    client = TestClient(app)
    user_id, cookie = register_user(client, "audit@baseline.test", "password123")

    async with test_db() as session:
        project = ProjectModel(name="Proj", description="", owner_user_id=user_id, user_requirements="")
        session.add(project)
        await session.flush()

        actor = ActorModel(name="Actor 1", description="", project_id=project.id, confirmation_status="ai_assumption")
        session.add(actor)
        await session.commit()
        
        project_public_id = project.public_id
        actor_id = actor.id

    client.cookies.clear()
    client.cookies.set("auth_session", cookie)

    # 1. Update confirmation status
    payload = {
        "node_kind": "actor",
        "node_id": actor_id,
        "confirmation_status": "needs_confirmation"
    }
    res = client.patch(f"/api/projects/{project_public_id}/node-status", json=payload)
    assert res.status_code == 200

    # 2. Verify audit log is recorded and can be queried via API
    res = client.get(f"/api/projects/{project_public_id}/audit-logs")
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) >= 1
    
    status_log = next((l for l in logs if l["actionType"] == "update_confirmation_status"), None)
    assert status_log is not None
    assert status_log["targetType"] == "actor"
    assert status_log["targetId"] == str(actor_id)
    assert "old_status" in status_log["payload"]
    assert "new_status" in status_log["payload"]
