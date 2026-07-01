import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

from backend.main import app
from backend.database.model import Base, ProjectModel, GenerativeDraftModel, CollaborationTaskModel, NotificationModel, ActorModel
from backend.database.database import get_session
from backend.api.modules.ai_interaction.ai_add.application.session import AIAddSessionService
from backend.core.issue_resolution.fingerprint import compute_context_hash

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
async def test_ai_conflict_resolution_and_task_spawning(test_db):
    client = TestClient(app)

    owner_id, owner_cookie = register_user(client, "ai_owner@conflict.com", "password123")

    async with test_db() as session:
        # Create project
        project = ProjectModel(
            name="AI Conflict Project",
            owner_user_id=owner_id,
            user_requirements="Requirement details"
        )
        session.add(project)
        await session.commit()
        project_public_id = project.public_id
        project_id = project.id

        # Compute initial context hash for target_type = "actor"
        ai_service = AIAddSessionService()
        project_context = await ai_service._load_context(project_id, ["actors"], session)
        initial_hash = compute_context_hash(project_context)

        # Seed the draft with this context_hash
        draft = GenerativeDraftModel(
            draft_id="ai_draft_conflict_test",
            owner_user_id=owner_id,
            project_id=project_id,
            draft_type="single_actor",
            payload={
                "project_id": project_id,
                "target_type": "actor",
                "generated_object": {
                    "name": "New AI Actor",
                    "description": "Created by generator"
                },
                "context_hash": initial_hash
            }
        )
        session.add(draft)

        # Create another actor to disrupt the context hash (e.g. concurrent edits)
        other_actor = ActorModel(
            project_id=project_id,
            name="Concurrent Actor",
            description="Created by another user"
        )
        session.add(other_actor)
        await session.commit()

    client.cookies.set("auth_session", owner_cookie)

    # Now, attempt to confirm the draft -> Should raise 409 and detect conflict
    res_confirm = client.post(f"/api/ai_object_generation_drafts/ai_draft_conflict_test/confirm")
    assert res_confirm.status_code == 409
    data = res_confirm.json()
    assert data["detail"]["message"] == "ai_draft_conflict_detected"
    task_id = data["detail"]["task_id"]

    # Verify a resolve_conflict task is created in database
    async with test_db() as session:
        task = await session.get(CollaborationTaskModel, task_id)
        assert task is not None
        assert task.task_type == "resolve_conflict"
        assert task.status == "open"
        assert task.payload["original_context_hash"] == initial_hash
        assert task.payload["stale_ai_result"]["name"] == "New AI Actor"

        # Verify a notification was created
        stmt = select(NotificationModel).where(NotificationModel.recipient_user_id == owner_id)
        notif = (await session.execute(stmt)).scalars().first()
        assert notif is not None
        assert notif.event_type == "conflict_detected"
        assert "New AI Actor" not in notif.body  # just a general description

        # Verify draft is deleted
        stmt_draft = select(GenerativeDraftModel).where(GenerativeDraftModel.draft_id == "ai_draft_conflict_test")
        draft_db = (await session.execute(stmt_draft)).scalar_one_or_none()
        assert draft_db is None

    # 4. Decide on the conflict task (approve it to force persist)
    res_decide = client.patch(
        f"/api/projects/{project_public_id}/tasks/{task_id}/decision",
        json={
            "decision": "approve",
            "note": "Forcing confirmation of conflict"
        }
    )
    assert res_decide.status_code == 200

    # Verify task status is done and actor is persisted
    async with test_db() as session:
        task_db = await session.get(CollaborationTaskModel, task_id)
        assert task_db.status == "done"

        stmt_actor = select(ActorModel).where(ActorModel.name == "New AI Actor")
        actor_db = (await session.execute(stmt_actor)).scalar_one_or_none()
        assert actor_db is not None
        assert actor_db.description == "Created by generator"
