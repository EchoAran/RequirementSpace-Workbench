import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sqlalchemy as sa
from backend.main import app
from backend.database.database import get_session, Base
from backend.database.model import (
    ProjectModel,
    UserModel,
    ActorModel,
    CollaborationTaskModel,
    ProjectMemberModel,
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
    return user_id, cookie

@pytest.mark.asyncio
async def test_task_workspace_queries_workflow(test_db):
    client = TestClient(app)
    
    # Register users
    owner_id, owner_cookie = register_user(client, "owner@queries.com", "password123")
    editor_id, editor_cookie = register_user(client, "editor@queries.com", "password123")
    reviewer_id, reviewer_cookie = register_user(client, "reviewer@queries.com", "password123")

    async with test_db() as session:
        project = ProjectModel(
            name="Queries Project",
            owner_user_id=owner_id,
            user_requirements="Requirement details."
        )
        session.add(project)
        await session.commit()
        project_id = project.id
        project_public_id = project.public_id

        editor_member = ProjectMemberModel(project_id=project_id, user_id=editor_id, role="editor", status="active")
        session.add(editor_member)
        reviewer_member = ProjectMemberModel(project_id=project_id, user_id=reviewer_id, role="reviewer", status="active")
        session.add(reviewer_member)

        # Add Actor
        actor = ActorModel(project_id=project_id, name="Test Actor", description="Hello", confirmation_status="needs_confirmation")
        session.add(actor)
        await session.commit()
        actor_id = actor.id

        # Seed tasks
        # Task 1: assigned to reviewer, created by editor
        task1 = CollaborationTaskModel(
            project_id=project_id,
            task_type="confirm_node",
            title="Task 1",
            status="open",
            created_by_user_id=editor_id,
            assigned_to_user_id=reviewer_id,
            target_type="actor",
            target_id=str(actor_id),
            content_hash="some-hash",
        )
        # Task 2: assigned to editor, created by owner
        task2 = CollaborationTaskModel(
            project_id=project_id,
            task_type="confirm_node",
            title="Task 2",
            status="done",
            created_by_user_id=owner_id,
            assigned_to_user_id=editor_id,
            target_type="actor",
            target_id=str(actor_id),
        )
        session.add(task1)
        session.add(task2)
        await session.commit()

    # 1. Query reviewer tasks as assignee (default role)
    client.cookies.set("auth_session", reviewer_cookie)
    res = client.get("/api/me/tasks")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["task"]["title"] == "Task 1"
    assert data[0]["task"]["status"] == "open"
    assert data[0]["task"]["creatorEmail"] == "editor@queries.com"
    assert data[0]["task"]["assigneeEmail"] == "reviewer@queries.com"
    assert data[0]["projectSummary"]["projectName"] == "Queries Project"
    assert data[0]["targetSummary"]["nodeKind"] == "actor"
    assert data[0]["targetSummary"]["nodeName"] == "Test Actor"

    # 2. Query editor tasks as assignee
    client.cookies.set("auth_session", editor_cookie)
    res = client.get("/api/me/tasks")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["task"]["title"] == "Task 2"
    assert data[0]["task"]["status"] == "done"

    # 3. Query editor tasks as creator
    res = client.get("/api/me/tasks?role=creator")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["task"]["title"] == "Task 1"

    # 4. Query editor tasks as both roles, with comma-separated status
    res = client.get("/api/me/tasks?role=both&status=open,done")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2

    # 5. Test pagination (limit, offset)
    res = client.get("/api/me/tasks?role=both&status=open,done&limit=1&offset=0")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1

    # 6. Test content changed calculation mismatch on actor change
    client.cookies.set("auth_session", reviewer_cookie)
    res = client.get("/api/me/tasks")
    assert res.status_code == 200
    data = res.json()
    assert data[0]["contentChanged"] is True

