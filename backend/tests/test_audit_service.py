import logging

import pytest
from backend.core.actor_context import ActorContext, set_actor, get_current_actor
from backend.services.audit_service import AuditService
from backend.database.model import AuditLogModel, ProjectModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database.database import get_session, Base
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


audit_service = AuditService()


def _events(caplog):
    return [record for record in caplog.records if hasattr(record, "event")]


@pytest.mark.asyncio
async def test_audit_service_explicit_actor(test_db, monkeypatch, caplog):
    monkeypatch.setenv("LOG_ENABLED", "true")
    monkeypatch.setenv("LOG_ENABLED_CATEGORIES", "audit")
    async with test_db() as session:
        # Create a dummy project
        project = ProjectModel(
            name="Audit Test Project",
            owner_user_id=1,
            user_requirements="Reqs"
        )
        session.add(project)
        await session.commit()
        project_id = project.id

        # Record audit log with explicit actor context
        actor = ActorContext.user(user_id=1, request_id="req-123")
        diff = {"name": {"before": "Old Name", "after": "New Name"}}
        
        with caplog.at_level(logging.INFO):
            await audit_service.record(
                session=session,
                project_id=project_id,
                action_type="test_action",
                summary="This is a test action",
                target_type="project",
                target_id=project_id,
                actor=actor,
                diff=diff,
                task_id=99,
            )
        await session.commit()

        # Query the audit log back
        res = await session.execute(
            select(AuditLogModel).where(AuditLogModel.project_id == project_id)
        )
        log = res.scalar_one()

        assert log.action_type == "test_action"
        assert log.summary == "This is a test action"
        assert log.target_type == "project"
        assert log.target_id == str(project_id)
        assert log.actor_user_id == 1
        assert log.actor_type == "user"
        assert log.diff == diff
        assert log.request_id == "req-123"
        assert log.task_id == 99
        completed = [
            record for record in _events(caplog)
            if record.event == "audit_log_write_completed"
        ]
        assert len(completed) == 1
        assert completed[0].category == "audit"
        assert completed[0].log_fields["project_id"] == project_id
        assert completed[0].log_fields["actor_user_id"] == 1
        assert completed[0].log_fields["action_type"] == "test_action"
        assert completed[0].log_fields["target_type"] == "project"
        assert completed[0].log_fields["target_id"] == str(project_id)


@pytest.mark.asyncio
async def test_audit_service_context_var_fallback(test_db):
    async with test_db() as session:
        # Create a dummy project
        project = ProjectModel(
            name="Audit Test Project 2",
            owner_user_id=1,
            user_requirements="Reqs"
        )
        session.add(project)
        await session.commit()
        project_id = project.id

        # Setup current actor context using context manager
        actor = ActorContext.ai(user_id=1, request_id="req-ai-999")
        with set_actor(actor):
            assert get_current_actor() == actor
            
            # Record audit log without passing actor parameter
            await audit_service.record(
                session=session,
                project_id=project_id,
                action_type="ai_action",
                summary="AI generation action",
                target_type="project",
                target_id=project_id,
            )
            await session.commit()

        # Query the audit log back
        res = await session.execute(
            select(AuditLogModel).where(AuditLogModel.project_id == project_id)
        )
        log = res.scalar_one()

        assert log.action_type == "ai_action"
        assert log.summary == "AI generation action"
        assert log.actor_user_id == 1
        assert log.actor_type == "ai"
        assert log.request_id == "req-ai-999"
