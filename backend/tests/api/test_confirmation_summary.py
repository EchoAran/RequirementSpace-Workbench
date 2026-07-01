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
    FeatureModel,
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
async def test_confirmation_summary_workflow(test_db):
    client = TestClient(app)
    
    owner_id, owner_cookie = register_user(client, "owner@summary.com", "password123")
    reviewer_id, reviewer_cookie = register_user(client, "reviewer@summary.com", "password123")

    async with test_db() as session:
        project = ProjectModel(
            name="Summary Project",
            owner_user_id=owner_id,
            user_requirements="Requirement details."
        )
        session.add(project)
        await session.commit()
        project_id = project.id
        project_public_id = project.public_id

        reviewer_member = ProjectMemberModel(project_id=project_id, user_id=reviewer_id, role="reviewer", status="active")
        session.add(reviewer_member)

        # 1. Add some nodes with ai_assumption status
        actor = ActorModel(project_id=project_id, name="Actor 1", description="desc", confirmation_status="ai_assumption")
        feat = FeatureModel(project_id=project_id, name="Feature 1", description="desc", confirmation_status="ai_assumption")
        session.add(actor)
        session.add(feat)
        await session.commit()

        # 2. Add some open/rejected tasks
        task1 = CollaborationTaskModel(
            project_id=project_id,
            task_type="confirm_node",
            title="Task 1",
            status="open",
            created_by_user_id=owner_id,
            assigned_to_user_id=reviewer_id,
            target_type="actor",
            target_id=str(actor.id),
        )
        task2 = CollaborationTaskModel(
            project_id=project_id,
            task_type="confirm_node",
            title="Task 2",
            status="rejected",
            created_by_user_id=owner_id,
            assigned_to_user_id=reviewer_id,
            target_type="feature",
            target_id=str(feat.id),
        )
        session.add(task1)
        session.add(task2)
        await session.commit()

    # Query summary
    client.cookies.set("auth_session", owner_cookie)
    res = client.get(f"/api/projects/{project_public_id}/confirmation-summary")
    assert res.status_code == 200
    data = res.json()
    assert data["aiAssumptionCount"] == 2
    assert data["openTaskCount"] == 1
    assert data["assignedToMeCount"] == 0
    assert data["createdByMeCount"] == 1
    assert data["rejectedCount"] == 1
    assert data["byNodeKind"]["actor"] == 1
    assert data["byAssignee"]["reviewer@summary.com"] == 1
