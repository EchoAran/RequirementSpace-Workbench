import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database.model import Base, ActorModel, ProjectModel
from backend.api.modules.collaboration.application.node_snapshot_service import NodeSnapshotService

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
    yield session_factory
    await engine.dispose()

@pytest.mark.asyncio
async def test_node_snapshot_semantic_hashing(test_db):
    service = NodeSnapshotService()

    async with test_db() as session:
        # Create a test project and actor
        project = ProjectModel(
            name="Test Hash Project",
            owner_user_id=1,
            user_requirements="Initial reqs"
        )
        session.add(project)
        await session.commit()
        project_id = project.id

        actor = ActorModel(
            project_id=project_id,
            name="Semantic Actor",
            description="This is a test actor",
            confirmation_status="ai_assumption"
        )
        session.add(actor)
        await session.commit()
        actor_id = actor.id

    # 1. Fetch initial snapshot and hash
    async with test_db() as session:
        res1 = await service.get_snapshot_and_hash(session, "actor", actor_id)
        hash1 = res1["hash"]
        snapshot1 = res1["snapshot"]
        assert snapshot1 == {"name": "Semantic Actor", "description": "This is a test actor"}

    # 2. Modify non-semantic field (confirmation_status) and verify hash remains unchanged
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        actor_db.confirmation_status = "confirmed"
        await session.commit()

    async with test_db() as session:
        res2 = await service.get_snapshot_and_hash(session, "actor", actor_id)
        hash2 = res2["hash"]
        assert hash1 == hash2

    # 3. Modify semantic field (description) and verify hash changes
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        actor_db.description = "Updated description"
        await session.commit()

    async with test_db() as session:
        res3 = await service.get_snapshot_and_hash(session, "actor", actor_id)
        hash3 = res3["hash"]
        assert hash1 != hash3
        assert res3["snapshot"] == {"name": "Semantic Actor", "description": "Updated description"}


@pytest.mark.asyncio
async def test_node_optimistic_locking(test_db):
    service = NodeSnapshotService()
    from datetime import datetime, timedelta
    from fastapi import HTTPException

    async with test_db() as session:
        project = ProjectModel(
            name="Test Lock Project",
            owner_user_id=1,
            user_requirements="Initial requirements text"
        )
        session.add(project)
        await session.commit()
        project_id = project.id

        actor = ActorModel(
            project_id=project_id,
            name="Locking Actor",
            description="Testing optimistic locking description"
        )
        session.add(actor)
        await session.commit()
        actor_id = actor.id
        initial_updated_at = actor.updated_at

    # 1. Matching timestamps should pass without error
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        await service.check_optimistic_lock(session, "actor", actor_db, initial_updated_at)
        await service.check_optimistic_lock(session, "actor", actor_db, initial_updated_at.isoformat())

    # 2. Mismatched timestamps should raise 409 HTTPException
    async with test_db() as session:
        actor_db = await session.get(ActorModel, actor_id)
        stale_updated_at = initial_updated_at - timedelta(seconds=10)
        with pytest.raises(HTTPException) as exc_info:
            await service.check_optimistic_lock(session, "actor", actor_db, stale_updated_at)
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["message"] == "node_content_changed"
        assert exc_info.value.detail["current_snapshot"]["name"] == "Locking Actor"

