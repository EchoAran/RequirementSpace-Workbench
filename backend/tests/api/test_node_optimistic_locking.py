
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.modules.version_control.application.clean_initialization import create_initial_workspace
from backend.database.database import get_session
from backend.database.model import (
    ActorModel,
    Base,
    BranchWorkspaceModel,
    ProjectMemberModel,
    ProjectModel,
    RequirementBranchModel,
)
from backend.main import app

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
    owner_id, _owner_cookie = register_user(client, "owner@lock.com", "password123")
    editor_id, editor_cookie = register_user(client, "editor@lock.com", "password123")

    async with test_db() as session:
        project = ProjectModel(
            name="Locking Project",
            owner_user_id=owner_id,
            user_requirements="Project description."
        )
        session.add(project)
        await session.commit()
        # New-world invariant: every project owns a protected main branch and workspace.
        await session.run_sync(lambda s: create_initial_workspace(s, project))
        project_public_id = project.public_id
        project_id = project.id

        editor_member = ProjectMemberModel(project_id=project_id, user_id=editor_id, role="editor", status="active")
        session.add(editor_member)
        await session.commit()

    # Editor creates a writable feature branch (branch author gains can_write).
    client.cookies.set("auth_session", editor_cookie)
    branch_resp = client.post(
        f"/api/projects/{project_public_id}/branches",
        json={"name": "feature/locking", "from_ref": "main"}
    )
    assert branch_resp.status_code == 201

    async with test_db() as session:
        feature_ws = (await session.execute(
            select(BranchWorkspaceModel).join(
                RequirementBranchModel, RequirementBranchModel.id == BranchWorkspaceModel.branch_id
            ).where(
                BranchWorkspaceModel.project_id == project_id,
                RequirementBranchModel.name == "feature/locking",
            )
        )).scalar_one()

        # Add Actor into the feature workspace
        actor = ActorModel(
            project_id=project_id, workspace_id=feature_ws.id,
            name="Test Lock Actor", description="Lock Desc"
        )
        session.add(actor)
        await session.commit()
        actor_id = actor.id
        actor_updated_at = actor.updated_at

    # 1. Update actor as editor with matching last_seen_updated_at -> Should succeed (200)
    res = client.put(
        f"/api/projects/{project_public_id}/actors/{actor_id}?branch=feature/locking",
        json={
            "name": "Updated Name",
            "lastSeenUpdatedAt": actor_updated_at.isoformat()
        }
    )
    assert res.status_code == 200

    # 2. Update actor again with same stale last_seen_updated_at -> Should fail with 409
    res_stale = client.put(
        f"/api/projects/{project_public_id}/actors/{actor_id}?branch=feature/locking",
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
