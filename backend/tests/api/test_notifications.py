import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

from backend.main import app
from backend.database.model import Base, ProjectModel, ProjectMemberModel, CollaborationTaskModel, NotificationModel, ActorModel
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
async def test_notification_flow(test_db):
    client = TestClient(app)

    owner_id, owner_cookie = register_user(client, "owner@notif.com", "password123")
    assignee_id, assignee_cookie = register_user(client, "assignee@notif.com", "password123")

    async with test_db() as session:
        project = ProjectModel(
            name="Notification Project",
            owner_user_id=owner_id,
            user_requirements="Project requirements."
        )
        session.add(project)
        await session.commit()
        project_public_id = project.public_id
        project_id = project.id

        m2 = ProjectMemberModel(project_id=project_id, user_id=assignee_id, role="editor", status="active")
        session.add(m2)

        # Create actor
        actor = ActorModel(project_id=project_id, name="Notif Actor", description="Initial")
        session.add(actor)
        await session.commit()
        actor_id = actor.id

    client.cookies.set("auth_session", owner_cookie)

    # 1. Create a confirmation task -> Should create notification for assignee
    res_task = client.post(
        f"/api/projects/{project_public_id}/tasks/confirm-node",
        json={
            "title": "Please confirm actor",
            "assignedToUserId": assignee_id,
            "nodeKind": "actor",
            "nodeId": actor_id
        }
    )
    assert res_task.status_code == 200
    task_id = res_task.json()["id"]

    # 2. Log in as assignee and check notifications
    client.cookies.set("auth_session", assignee_cookie)
    res_notif = client.get("/api/me/notifications")
    assert res_notif.status_code == 200
    notifs = res_notif.json()
    assert len(notifs) >= 1
    assert notifs[0]["eventType"] == "task_assigned"
    assert notifs[0]["title"] == "collaboration.notifications.singleTaskAssigned.title"
    assert notifs[0]["body"] == "collaboration.notifications.singleTaskAssigned.body"
    assert notifs[0]["recipientUserId"] == assignee_id
    assert notifs[0]["readAt"] is None
    notif_id = notifs[0]["id"]

    # 3. Decide on the task (approve) -> Should notify the creator (owner)
    res_decide = client.patch(
        f"/api/projects/{project_public_id}/tasks/{task_id}/decision",
        json={
            "decision": "approve",
            "note": "Approved by assignee"
        }
    )
    assert res_decide.status_code == 200

    # 4. Log in as owner and check notifications
    client.cookies.set("auth_session", owner_cookie)
    res_owner_notif = client.get("/api/me/notifications")
    assert res_owner_notif.status_code == 200
    owner_notifs = res_owner_notif.json()
    assert len(owner_notifs) >= 1
    assert owner_notifs[0]["eventType"] == "task_decided"
    assert owner_notifs[0]["title"] == "collaboration.notifications.singleTaskApproved.title"
    assert owner_notifs[0]["body"] == "collaboration.notifications.singleTaskApproved.body"
    assert owner_notifs[0]["recipientUserId"] == owner_id

    # 5. Mark assignee notification as read
    client.cookies.set("auth_session", assignee_cookie)
    res_read = client.put(
        "/api/me/notifications/read",
        json={"notificationIds": [notif_id]}
    )
    assert res_read.status_code == 200
    assert res_read.json() == {"message": "notifications_marked_read"}

    # Check that it's now marked read
    res_notif_read = client.get("/api/me/notifications")
    assert res_notif_read.status_code == 200
    assert res_notif_read.json()[0]["readAt"] is not None

    client.cookies.set("auth_session", owner_cookie)
    res_default_title = client.post(
        f"/api/projects/{project_public_id}/tasks/confirm-node",
        json={
            "assignedToUserId": assignee_id,
            "nodeKind": "actor",
            "nodeId": actor_id,
        },
    )
    assert res_default_title.status_code == 200
    assert res_default_title.json()["title"] == "collaboration.taskTitles.singleConfirmation"
