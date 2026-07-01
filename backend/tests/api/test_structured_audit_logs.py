import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.main import app
from backend.database.database import get_session, Base
from backend.database.model import ProjectModel, AuditLogModel, ProjectMemberModel, UserRole
import unittest.mock

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
async def test_structured_audit_logs_endpoints(test_db):
    client = TestClient(app)
    user_id, cookie = register_user(client, "auditor@test.com", "password123")

    # Create project and register owner as active member
    async with test_db() as session:
        project = ProjectModel(
            name="Test Audit Project",
            owner_user_id=user_id,
            user_requirements="Initial Requirements content."
        )
        session.add(project)
        await session.commit()
        project_public_id = project.public_id
        project_id = project.id

    # 1. Test updating user requirements via API logs correct audit event
    client.cookies.set("auth_session", cookie)
    res = client.put(
        f"/api/projects/{project_public_id}/user-requirements",
        json={"user_requirements": "Updated Requirements content."}
    )
    assert res.status_code == 200

    # Verify the audit log exists in the DB
    async with test_db() as session:
        import sqlalchemy as sa
        res_db = await session.execute(
            sa.select(AuditLogModel).where(
                AuditLogModel.project_id == project_id,
                AuditLogModel.action_type == "update_user_requirements"
            )
        )
        log = res_db.scalar_one_or_none()
        assert log is not None
        assert log.actor_user_id == user_id
        assert log.actor_type == "user"
        assert log.diff == {
            "user_requirements": {
                "before": "Initial Requirements content.",
                "after": "Updated Requirements content."
            }
        }
        assert log.request_id is not None

    # 2. Test LLM refinement logs an AI audit event
    from backend.api.dependencies.llm import get_llm_context
    app.dependency_overrides[get_llm_context] = lambda: unittest.mock.AsyncMock()

    try:
        with unittest.mock.patch("backend.services.LLM_service.LLMHandler.call_llm", new_callable=unittest.mock.AsyncMock) as mock_call:
            mock_call.return_value = "Refined Requirements content."
            res = client.post(
                f"/api/projects/{project_public_id}/user-requirements/refine",
                json={"user_feedback": "Please optimize it."}
            )
            assert res.status_code == 200
    finally:
        app.dependency_overrides.pop(get_llm_context, None)

    # Verify the audit log for LLM refinement
    async with test_db() as session:
        import sqlalchemy as sa
        res_db = await session.execute(
            sa.select(AuditLogModel).where(
                sa.and_(
                    AuditLogModel.project_id == project_id,
                    AuditLogModel.action_type == "refine_user_requirements"
                )
            )
        )
        log_refine = res_db.scalar_one_or_none()
        assert log_refine is not None
        assert log_refine.actor_user_id == user_id
        assert log_refine.actor_type == "ai"
        assert log_refine.diff == {
            "user_requirements": {
                "before": "Updated Requirements content.",
                "after": "Refined Requirements content."
            }
        }

    # 3. Test listing and filtering audit logs endpoint
    # Retrieve all audit logs without filters
    res = client.get(f"/api/projects/{project_public_id}/audit-logs")
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) >= 2

    # Check structure of the serialized audit log response
    first_log = logs[0]
    assert "actorType" in first_log
    assert "actorUserId" in first_log
    assert "diff" in first_log
    assert "requestId" in first_log

    # Filter by actorType = ai
    res_ai = client.get(f"/api/projects/{project_public_id}/audit-logs?actor_type=ai")
    assert res_ai.status_code == 200
    ai_logs = res_ai.json()
    assert len(ai_logs) == 1
    assert ai_logs[0]["actionType"] == "refine_user_requirements"
    assert ai_logs[0]["actorType"] == "ai"

    # Filter by action_type = update_user_requirements
    res_update = client.get(f"/api/projects/{project_public_id}/audit-logs?action_type=update_user_requirements")
    assert res_update.status_code == 200
    update_logs = res_update.json()
    assert len(update_logs) == 1
    assert update_logs[0]["actionType"] == "update_user_requirements"
    assert update_logs[0]["actorType"] == "user"


@pytest.mark.asyncio
async def test_actor_creation_audit_actor_user(test_db):
    client = TestClient(app)
    user_id, cookie = register_user(client, "crud_actor@test.com", "password123")

    # Create project and register owner as active member
    async with test_db() as session:
        project = ProjectModel(
            name="Test CRUD Audit Project",
            owner_user_id=user_id,
            user_requirements="Some initial contents."
        )
        session.add(project)
        await session.commit()
        project_public_id = project.public_id
        project_id = project.id

    client.cookies.set("auth_session", cookie)

    # 1. Create Actor via API
    res = client.post(
        f"/api/projects/{project_public_id}/actors",
        json={"name": "Audited Actor", "description": "This actor creation should be audited with current user id"}
    )
    assert res.status_code == 200
    actor_data = res.json()
    actor_id = actor_data["actor_id"]

    # 2. Verify that audit log has actor_user_id == user_id
    async with test_db() as session:
        import sqlalchemy as sa
        res_db = await session.execute(
            sa.select(AuditLogModel).where(
                AuditLogModel.project_id == project_id,
                AuditLogModel.action_type == "create_actor"
            )
        )
        log = res_db.scalar_one_or_none()
        assert log is not None
        assert log.actor_user_id == user_id
        assert log.actor_type == "user"
        assert log.diff is not None
        diff_val = log.diff
        while isinstance(diff_val, str):
            import json
            diff_val = json.loads(diff_val)
        assert diff_val["name"] == "Audited Actor"
        assert log.request_id is not None

