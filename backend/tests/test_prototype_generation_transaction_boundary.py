import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.database.model import Base, ProjectModel, ActorModel, FeatureModel, PrototypePreviewModel
from backend.api.modules.preview_convergence.application.prototype_generation import PrototypeGenerationService


@pytest.fixture
async def test_session_factory():
    """Create a fresh in-memory database and return session factory."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
async def seeded_project(test_session_factory) -> tuple[int, str]:
    """Create a seed project with actor and feature."""
    async with test_session_factory() as session:
        project = ProjectModel(
            name="测试原型项目",
            description="测试原型生成",
            user_requirements="需要有登录和展示数据功能。",
            kano_status="pending",
        )
        session.add(project)
        await session.flush()

        actor = ActorModel(project_id=project.id, name="用户", description="普通用户")
        session.add(actor)
        await session.flush()

        feature = FeatureModel(project_id=project.id, name="登录模块", description="实现登录")
        session.add(feature)
        await session.flush()
        
        await session.commit()
        return project.id, project.public_id


@pytest.mark.asyncio
async def test_transaction_boundary_split(test_session_factory, seeded_project):
    """Verify that read session is closed before LLM generation starts, and write session is created after."""
    service = PrototypeGenerationService(session_factory=test_session_factory)
    project_id, public_id = seeded_project
    
    call_sequence = []
    original_session_factory = service.session_factory
    
    def wrapped_factory(*args, **kwargs):
        session = original_session_factory(*args, **kwargs)
        call_sequence.append(("session_created", id(session)))
        
        # Override close to log when the session exits its context
        orig_close = session.close
        async def mock_close():
            call_sequence.append(("session_closed", id(session)))
            await orig_close()
        session.close = mock_close
        return session
        
    service.session_factory = wrapped_factory
    
    orig_generate_pages = service._generate_pages
    async def mock_generate_pages(*args, **kwargs):
        call_sequence.append(("llm_started", None))
        res = await orig_generate_pages(*args, **kwargs)
        call_sequence.append(("llm_finished", None))
        return res
        
    service._generate_pages = mock_generate_pages
    
    # Mock generator to avoid real LLM calls
    mock_code = {"HTML": "<html></html>", "CSS": "", "Javascript": ""}
    with patch.object(service._generator, "generate_page", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_code
        
        await service.generate_preview(
            project_id=project_id,
            force_regenerate=True,
        )
        
    # Extract only event names
    event_names = [event for event, _ in call_sequence]
    
    # Assert sequence of operations
    assert event_names == [
        "session_created",
        "session_closed",
        "llm_started",
        "llm_finished",
        "session_created",
        "session_closed"
    ]


@pytest.mark.asyncio
async def test_write_error_rolls_back_and_closes_session(test_session_factory, seeded_project):
    """Verify that a database error during the write phase rolls back the session and does not write partial data."""
    service = PrototypeGenerationService(session_factory=test_session_factory)
    project_id, public_id = seeded_project

    # Mock _build_preview_model to return a model that will fail database constraints
    # (e.g. status=None when status is non-nullable, or project_id = 99999 violating foreign key if FK is enforced,
    # or just mocking session.commit to throw an error)
    original_session_factory = service.session_factory
    mock_sessions = []
    
    def wrapped_factory(*args, **kwargs):
        session = original_session_factory(*args, **kwargs)
        mock_sessions.append(session)
        return session
        
    service.session_factory = wrapped_factory

    # Mock generator to avoid real LLM calls
    mock_code = {"HTML": "<html></html>", "CSS": "", "Javascript": ""}
    with patch.object(service._generator, "generate_page", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_code
        
        # We will mock the commit of the second session (the write session) to raise an Exception
        with patch("sqlalchemy.ext.asyncio.AsyncSession.commit", side_effect=ValueError("db_commit_failed")):
            with pytest.raises(ValueError, match="db_commit_failed"):
                await service.generate_preview(
                    project_id=project_id,
                    force_regenerate=True,
                )

    # Verify that the write session was indeed rolled back
    # The last session in mock_sessions is the write session.
    write_session = mock_sessions[-1]
    assert write_session is not None
    
    # Verify no PrototypePreviewModel was written
    async with test_session_factory() as session:
        result = await session.execute(select(PrototypePreviewModel).where(PrototypePreviewModel.project_id == project_id))
        previews = result.scalars().all()
        assert len(previews) == 0
