"""
Baseline tests for node status updates.
Verifies that:
1. Owner can update a single node's confirmation status.
2. Owner can batch update multiple nodes' confirmation statuses.
3. Update fails for non-owners (returns 404).
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
from backend.database.model import ProjectModel, ActorModel, FeatureModel

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
async def test_node_status_updates_baseline(test_db):
    client = TestClient(app)
    user_a_id, cookie_a = register_user(client, "owner@node.test", "password123")
    client.cookies.clear()
    user_b_id, cookie_b = register_user(client, "other@node.test", "password123")

    async with test_db() as session:
        project = ProjectModel(name="Proj", description="", owner_user_id=user_a_id, user_requirements="")
        session.add(project)
        await session.flush()

        actor = ActorModel(name="Actor 1", description="", project_id=project.id, confirmation_status="ai_assumption")
        feature = FeatureModel(name="Feature 1", description="", project_id=project.id, confirmation_status="ai_assumption")
        session.add_all([actor, feature])
        await session.commit()
        
        project_public_id = project.public_id
        actor_id = actor.id
        feature_id = feature.id

    # 1. Owner updates single node status (ai_assumption -> needs_confirmation)
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_a)
    payload = {
        "node_kind": "actor",
        "node_id": actor_id,
        "confirmation_status": "needs_confirmation"
    }
    res = client.patch(f"/api/projects/{project_public_id}/node-status", json=payload)
    assert res.status_code == 200
    assert res.json()["confirmation_status"] == "needs_confirmation"

    # Verify database update
    async with test_db() as session:
        db_actor = await session.get(ActorModel, actor_id)
        assert db_actor.confirmation_status == "needs_confirmation"

    # 2. Owner batch updates multiple nodes (needs_confirmation / ai_assumption -> confirmed)
    batch_payload = {
        "nodes": [
            {"node_kind": "actor", "node_id": actor_id, "confirmation_status": "confirmed"},
            {"node_kind": "feature", "node_id": feature_id, "confirmation_status": "confirmed"}
        ],
        "confirmation_status": "confirmed"
    }
    res = client.patch(f"/api/projects/{project_public_id}/node-status/batch", json=batch_payload)
    assert res.status_code == 200
    assert res.json()["updated_count"] == 2

    # Verify database update
    async with test_db() as session:
        db_actor = await session.get(ActorModel, actor_id)
        db_feature = await session.get(FeatureModel, feature_id)
        assert db_actor.confirmation_status == "confirmed"
        assert db_feature.confirmation_status == "confirmed"

    # 3. Non-owner tries to update node status (returns 404)
    client.cookies.clear()
    client.cookies.set("auth_session", cookie_b)
    payload = {
        "node_kind": "actor",
        "node_id": actor_id,
        "confirmation_status": "needs_confirmation"
    }
    res = client.patch(f"/api/projects/{project_public_id}/node-status", json=payload)
    assert res.status_code == 404
