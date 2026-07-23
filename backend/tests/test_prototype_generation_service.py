import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.database.model import Base, ProjectModel, ActorModel, FeatureModel, GherkinSpecModel, PrototypePreviewModel
from backend.api.modules.preview_convergence.public import PrototypeGenerationService
from backend.integration.skill_backed_services.prototype_generation_service import SkillBackedPrototypePageGenerator


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
async def test_prototype_generation_with_page_generator(test_session_factory, seeded_project):
    service = PrototypeGenerationService(session_factory=test_session_factory)
    project_id, public_id = seeded_project

    pages = [{
        "page_id": "page-1",
        "role_id": 1,
        "role_name": "User",
        "feature_id": 1,
        "feature_name": "Feature",
        "html": "<html></html>",
        "css": "body {}",
        "javascript": "console.log(1)",
        "source": "test_generator",
        "status": "ready",
    }]
    with patch.object(service, "_generate_pages", new=AsyncMock(return_value=pages)), \
         patch.object(service, "_preview_source", return_value="test_generator"):
        response = await service.generate_preview(
            project_id=project_id,
            force_regenerate=True,
        )

        assert response.project_id == public_id
        assert response.status == "ready"
        assert response.source == "test_generator"
        assert response.html == "<html></html>"
        assert response.css == "body {}"
        assert response.javascript == "console.log(1)"
        assert len(response.pages) > 0
        assert response.pages[0].html == "<html></html>"


@pytest.mark.asyncio
async def test_skill_backed_prototype_generation(test_session_factory, seeded_project):
    """Test skill-backed prototype generation logic and response structure."""
    page_gen = SkillBackedPrototypePageGenerator()
    service = PrototypeGenerationService(
        session_factory=test_session_factory,
        page_generator=page_gen,
    )
    project_id, public_id = seeded_project

    # Mock SkillBackedLLMJsonClient to return code payload
    mock_code = {"HTML": "<h1>Skill</h1>", "CSS": "h1 {color: red;}", "Javascript": "alert(1);"}
    with patch.object(page_gen._llm_json_client, "ask_json", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = mock_code

        response = await service.generate_preview(
            project_id=project_id,
            force_regenerate=True,
        )

        assert response.project_id == public_id
        assert response.status == "ready"
        assert response.source == "role_feature_pages"
        assert response.html == "<h1>Skill</h1>"
        assert response.css == "h1 {color: red;}"
        assert response.javascript == "alert(1);"
        assert all(
            call.kwargs["timeout_seconds"] == 300.0
            for call in mock_ask.await_args_list
        )


@pytest.mark.asyncio
async def test_prototype_generation_force_regenerate_false(test_session_factory, seeded_project):
    """Test caching logic when force_regenerate=False."""
    service = PrototypeGenerationService(session_factory=test_session_factory)
    project_id, public_id = seeded_project

    # Seed an existing preview
    async with test_session_factory() as session:
        existing_preview = PrototypePreviewModel(
            project_id=project_id,
            status="ready",
            source="placeholder",
            html="<p>Cached</p>",
            javascript="",
            css="",
            pages=[],
            input_snapshot={},
        )
        session.add(existing_preview)
        await session.commit()

    # The generate_preview call should return the cached one without invoking page generation
    with patch.object(service, "_generate_pages", new_callable=AsyncMock) as mock_gen:
        response = await service.generate_preview(
            project_id=project_id,
            force_regenerate=False,
        )
        mock_gen.assert_not_called()
        assert response.html == "<p>Cached</p>"
        assert response.project_id == public_id


@pytest.mark.asyncio
async def test_prototype_generation_fails_when_no_targets_exist(test_session_factory):
    async with test_session_factory() as session:
        project = ProjectModel(
            name="空项目",
            description="无任何节点",
            user_requirements="无",
            kano_status="pending",
        )
        session.add(project)
        await session.commit()
        pid = project.id

    service = PrototypeGenerationService(session_factory=test_session_factory)
    with pytest.raises(ValueError, match="prototype_targets_empty"):
        await service.generate_preview(
            project_id=pid,
            force_regenerate=True,
        )
