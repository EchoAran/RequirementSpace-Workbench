import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

if "LLM_CONFIG_ENCRYPTION_KEY" not in os.environ:
    os.environ["LLM_CONFIG_ENCRYPTION_KEY"] = "rK9PjN_wO2v5gVjHqX8zL1_pT5yW3xM8mU7bC4tN2zI="

from backend.main import app
from backend.database.database import get_session, Base
from backend.database.model import (
    ProjectModel,
    ProjectMemberModel,
    ProjectMemberRole,
    ProjectMemberStatus,
    AuditLogModel,
)

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
async def test_locale_preference_api_endpoints(test_db):
    client = TestClient(app)

    # 1. Register users
    owner_id, owner_cookie = register_user(client, "owner@locale.test", "password123")
    client.cookies.clear()
    admin_id, admin_cookie = register_user(client, "admin@locale.test", "password123")
    client.cookies.clear()
    editor_id, editor_cookie = register_user(client, "editor@locale.test", "password123")
    client.cookies.clear()
    reviewer_id, reviewer_cookie = register_user(client, "reviewer@locale.test", "password123")
    client.cookies.clear()
    viewer_id, viewer_cookie = register_user(client, "viewer@locale.test", "password123")
    client.cookies.clear()
    non_member_id, non_member_cookie = register_user(client, "nonmember@locale.test", "password123")

    # 2. Test User Personal Preference Endpoints
    # GET /api/auth/me should return default preferred_locale as "zh-CN"
    client.cookies.set("auth_session", owner_cookie)
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.json()["preferred_locale"] == "zh-CN"

    # PUT /api/account/preferences updates preference
    res = client.put("/api/account/preferences", json={"preferred_locale": "en-US"})
    assert res.status_code == 200
    assert res.json()["preferred_locale"] == "en-US"

    # Verify update persisted
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.json()["preferred_locale"] == "en-US"

    # PUT with invalid locale yields 400
    res = client.put("/api/account/preferences", json={"preferred_locale": "en-UK"})
    assert res.status_code == 400
    assert res.json()["detail"] == "invalid_preferred_locale"

    # 3. Create project under Owner
    client.cookies.clear()
    client.cookies.set("auth_session", owner_cookie)
    async with test_db() as session:
        # Create project model
        p = ProjectModel(name="Locale Config Test", description="Desc", owner_user_id=owner_id, user_requirements="Reqs")
        session.add(p)
        await session.commit()
        project_public_id = p.public_id
        project_id = p.id

        # Add memberships manually
        m_admin = ProjectMemberModel(
            project_id=project_id,
            user_id=admin_id,
            role=ProjectMemberRole.ADMIN.value,
            status=ProjectMemberStatus.ACTIVE.value
        )
        m_editor = ProjectMemberModel(
            project_id=project_id,
            user_id=editor_id,
            role=ProjectMemberRole.EDITOR.value,
            status=ProjectMemberStatus.ACTIVE.value
        )
        m_reviewer = ProjectMemberModel(
            project_id=project_id,
            user_id=reviewer_id,
            role=ProjectMemberRole.REVIEWER.value,
            status=ProjectMemberStatus.ACTIVE.value
        )
        m_viewer = ProjectMemberModel(
            project_id=project_id,
            user_id=viewer_id,
            role=ProjectMemberRole.VIEWER.value,
            status=ProjectMemberStatus.ACTIVE.value
        )
        session.add_all([m_admin, m_editor, m_reviewer, m_viewer])
        await session.commit()

    # 4. Test Project Configuration GET
    # Owner reads configuration: content_locale is null initially
    client.cookies.clear()
    client.cookies.set("auth_session", owner_cookie)
    res = client.get(f"/api/projects/{project_public_id}/configuration")
    assert res.status_code == 200
    data = res.json()
    assert data["content_locale"] is None

    # Editor reads configuration: OK
    client.cookies.clear()
    client.cookies.set("auth_session", editor_cookie)
    res = client.get(f"/api/projects/{project_public_id}/configuration")
    assert res.status_code == 200
    assert res.json()["content_locale"] is None

    # Non-member reads configuration: 404
    client.cookies.clear()
    client.cookies.set("auth_session", non_member_cookie)
    res = client.get(f"/api/projects/{project_public_id}/configuration")
    assert res.status_code == 404

    # 5. Test Project Configuration PUT (Updates)
    # Editor tries to update: Forbidden 403
    client.cookies.clear()
    client.cookies.set("auth_session", editor_cookie)
    res = client.put(f"/api/projects/{project_public_id}/configuration", json={"content_locale": "en-US"})
    assert res.status_code == 403
    res = client.get(f"/api/projects/{project_public_id}/configuration")
    assert res.status_code == 200
    assert res.json()["content_locale"] is None

    # Reviewer tries to update: Forbidden 403
    client.cookies.clear()
    client.cookies.set("auth_session", reviewer_cookie)
    res = client.put(f"/api/projects/{project_public_id}/configuration", json={"content_locale": "en-US"})
    assert res.status_code == 403

    # Viewer tries to update: Forbidden 403
    client.cookies.clear()
    client.cookies.set("auth_session", viewer_cookie)
    res = client.put(f"/api/projects/{project_public_id}/configuration", json={"content_locale": "en-US"})
    assert res.status_code == 403

    # Non-member tries to update: Not Found 404
    client.cookies.clear()
    client.cookies.set("auth_session", non_member_cookie)
    res = client.put(f"/api/projects/{project_public_id}/configuration", json={"content_locale": "en-US"})
    assert res.status_code == 404

    # Admin updates: success 200
    client.cookies.clear()
    client.cookies.set("auth_session", admin_cookie)
    res = client.put(f"/api/projects/{project_public_id}/configuration", json={"content_locale": "en-US"})
    assert res.status_code == 200
    assert res.json()["content_locale"] == "en-US"

    # Verify empty request body {} does not modify configuration
    res = client.put(f"/api/projects/{project_public_id}/configuration", json={})
    assert res.status_code == 200
    assert res.json()["content_locale"] == "en-US"

    # Owner updates with invalid locale: 400
    client.cookies.clear()
    client.cookies.set("auth_session", owner_cookie)
    res = client.put(f"/api/projects/{project_public_id}/configuration", json={"content_locale": "en-UK"})
    assert res.status_code == 400

    # Owner clears configuration: sets to null
    res = client.put(f"/api/projects/{project_public_id}/configuration", json={"content_locale": None})
    assert res.status_code == 200
    assert res.json()["content_locale"] is None

    # 6. Verify Audit Logs
    # We should have audit logs for the "update_project_locale" action type
    async with test_db() as session:
        stmt = select(AuditLogModel).where(
            AuditLogModel.project_id == project_id,
            AuditLogModel.action_type == "update_project_locale"
        ).order_by(AuditLogModel.created_at.desc())
        res_db = await session.execute(stmt)
        logs = res_db.scalars().all()
        
        # We did 2 successful modifications:
        # 1. Admin set to 'en-US' (old=None, new='en-US')
        # 2. Owner set to None (old='en-US', new=None)
        assert len(logs) == 2
        
        # Second log (clearing to None)
        assert logs[0].payload["old_locale"] == "en-US"
        assert logs[0].payload["new_locale"] is None
        assert "Updated project content language" in logs[0].summary
        
        # First log (setting to 'en-US')
        assert logs[1].payload["old_locale"] is None
        assert logs[1].payload["new_locale"] == "en-US"
        assert "Updated project content language" in logs[1].summary
