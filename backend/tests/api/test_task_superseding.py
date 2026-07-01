import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

from backend.main import app
from backend.database.model import Base, ProjectModel, ActorModel, ProjectMemberModel, CollaborationTaskModel, AuditLogModel, NotificationModel
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
async def test_auto_task_superseding(test_db):
    client = TestClient(app)

    owner_id, owner_cookie = register_user(client, "owner@super.com", "password123")
    assignee_id, assignee_cookie = register_user(client, "assignee@super.com", "password123")

    async with test_db() as session:
        project = ProjectModel(
            name="Superseding Project",
            owner_user_id=owner_id,
            user_requirements="Requirement text."
        )
        session.add(project)
        await session.commit()
        project_public_id = project.public_id
        project_id = project.id

        # Add project members
        m2 = ProjectMemberModel(project_id=project_id, user_id=assignee_id, role="editor", status="active")
        session.add(m2)

        # Create Actor
        actor = ActorModel(project_id=project_id, name="Actor To Check", description="Initial description")
        session.add(actor)
        await session.commit()
        actor_id = actor.id
        actor_updated_at = actor.updated_at

        # Calculate snapshot and hash
        from backend.api.modules.collaboration.application.task_service import snapshot_service
        snap_res = await snapshot_service.get_snapshot_and_hash(session, "actor", actor_id)
        actor_hash = snap_res["hash"]

        # Create a confirmation task
        task = CollaborationTaskModel(
            project_id=project_id,
            task_type="confirm_node",
            target_type="actor",
            target_id=str(actor_id),
            title="Confirm Actor",
            status="open",
            content_hash=actor_hash,
            assigned_to_user_id=assignee_id,
            created_by_user_id=owner_id
        )
        session.add(task)
        await session.commit()
        task_id = task.id

    # 1. Update the actor's description -> Should succeed and trigger task superseding
    client.cookies.set("auth_session", owner_cookie)
    res = client.put(
        f"/api/projects/{project_public_id}/actors/{actor_id}",
        json={
            "description": "Updated description",
            "lastSeenUpdatedAt": actor_updated_at.isoformat()
        }
    )
    assert res.status_code == 200

    # 2. Verify task status is superseded and notification & audit logs are created
    async with test_db() as session:
        # Check task
        stmt_task = select(CollaborationTaskModel).where(CollaborationTaskModel.id == task_id)
        task_db = (await session.execute(stmt_task)).scalar_one()
        assert task_db.status == "superseded"

        # Check notification
        stmt_notif = select(NotificationModel).where(NotificationModel.recipient_user_id == assignee_id)
        notif = (await session.execute(stmt_notif)).scalars().all()
        assert len(notif) >= 1
        assert notif[0].event_type == "task_superseded"

        # Check audit log
        stmt_audit = select(AuditLogModel).where(AuditLogModel.action_type == "task_superseded_by_node_update")
        audit = (await session.execute(stmt_audit)).scalars().all()
        assert len(audit) >= 1
