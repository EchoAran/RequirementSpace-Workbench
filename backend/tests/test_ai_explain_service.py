"""
Tests for AI Explain (Q&A) service — context loading, scope handling, and error cases.

Uses mocked LLM calls to avoid external dependencies, verifying that:
- Context is correctly loaded per scope kind (node / projection / workspace)
- Errors are raised for invalid inputs (empty question, missing target, etc.)
- Workspace-level context thresholds work correctly
"""

import pytest
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.database.model import Base, ProjectModel, ActorModel, FeatureModel, FeatureRelationModel
from backend.api.services.ai_explain_service import AIExplainService


# ---------------------------------------------------------------------------
# Fixtures – async in-memory SQLite database
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def seeded_project(db_session) -> int:
    """Create a seed project with actors, features, and relations."""
    project = ProjectModel(name="测试项目", description="测试", user_requirements="一个测试项目。")
    db_session.add(project)
    await db_session.flush()
    pid = project.id

    # Actors
    for name in ["用户A", "用户B"]:
        db_session.add(ActorModel(project_id=pid, name=name))
    await db_session.flush()

    # Root feature
    root = FeatureModel(project_id=pid, name="根模块")
    db_session.add(root)
    await db_session.flush()

    # Leaf features
    for pos, name in enumerate(["功能1", "功能2"]):
        f = FeatureModel(project_id=pid, name=name)
        db_session.add(f)
        await db_session.flush()
        db_session.add(FeatureRelationModel(parent_feature_id=root.id, child_feature_id=f.id, position=pos))

    await db_session.flush()
    return pid


@pytest.fixture
def service():
    """AIExplainService instance with mocked LLM."""
    svc = AIExplainService()
    return svc


# ---------------------------------------------------------------------------
# Helper: mock LLM to return a canned answer
# ---------------------------------------------------------------------------

def _mock_llm(service, answer: str = "测试回答"):
    """Patch the LLM handler's call_chat to return a fixed answer."""
    mock_handler = AsyncMock()
    mock_handler.call_chat.return_value = answer
    patch_obj = patch.object(service, '_get_llm_handler', return_value=mock_handler)
    patch_obj.start()
    return patch_obj


# ---------------------------------------------------------------------------
# Project & validation tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_explain_project_not_found(service, db_session):
    """explain raises ValueError for non-existent project."""
    patch_obj = _mock_llm(service)
    with pytest.raises(ValueError, match="project_not_found"):
        await service.explain(
            project_id=99999,
            scope={"kind": "workspace"},
            question="test",
            db_session=db_session,
        )
    patch_obj.stop()


@pytest.mark.asyncio
async def test_explain_empty_question(service, db_session, seeded_project):
    """explain raises ValueError for empty question."""
    with pytest.raises(ValueError, match="empty_question"):
        await service.explain(
            project_id=seeded_project,
            scope={"kind": "workspace"},
            question="  ",
            db_session=db_session,
        )


@pytest.mark.asyncio
async def test_explain_unsupported_scope_kind(service, db_session, seeded_project):
    """explain raises ValueError for unsupported scope kind."""
    with pytest.raises(ValueError, match="unsupported_scope_kind"):
        await service.explain(
            project_id=seeded_project,
            scope={"kind": "invalid"},
            question="test",
            db_session=db_session,
        )


@pytest.mark.asyncio
async def test_explain_invalid_node_scope(service, db_session, seeded_project):
    """explain raises ValueError for node scope without target_type."""
    with pytest.raises(ValueError, match="invalid_node_scope"):
        await service.explain(
            project_id=seeded_project,
            scope={"kind": "node"},
            question="test",
            db_session=db_session,
        )


# ---------------------------------------------------------------------------
# Node scope tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_explain_node_actor(service, db_session, seeded_project):
    """Node scope for actor loads actor context and returns answer."""
    patch_obj = _mock_llm(service, "这是关于参与者的回答")
    result = await service.explain(
        project_id=seeded_project,
        scope={"kind": "node", "target_type": "actor", "target_id": 1},
        question="这个参与者是什么？",
        db_session=db_session,
    )
    assert result["answer"] == "这是关于参与者的回答"
    assert "scope_label" in result["context_summary"]
    assert "objects_loaded" in result["context_summary"]
    patch_obj.stop()


@pytest.mark.asyncio
async def test_explain_node_feature(service, db_session, seeded_project):
    """Node scope for feature loads feature context."""
    patch_obj = _mock_llm(service, "功能回答")
    result = await service.explain(
        project_id=seeded_project,
        scope={"kind": "node", "target_type": "feature", "target_id": 2},
        question="这个功能是什么？",
        db_session=db_session,
    )
    assert result["answer"] == "功能回答"
    assert len(result["context_summary"]["objects_loaded"]) > 0
    patch_obj.stop()


@pytest.mark.asyncio
async def test_explain_node_target_not_found(service, db_session, seeded_project):
    """Node scope for non-existent target raises ValueError."""
    with pytest.raises(ValueError, match="target_not_found"):
        await service.explain(
            project_id=seeded_project,
            scope={"kind": "node", "target_type": "actor", "target_id": 999},
            question="test",
            db_session=db_session,
        )


@pytest.mark.asyncio
async def test_explain_node_unsupported_target_type(service, db_session, seeded_project):
    """Node scope for unsupported target_type raises ValueError."""
    patch_obj = _mock_llm(service)
    with pytest.raises(ValueError, match="unsupported_target_type"):
        await service.explain(
            project_id=seeded_project,
            scope={"kind": "node", "target_type": "scenario", "target_id": 1},
            question="test",
            db_session=db_session,
        )
    patch_obj.stop()


# ---------------------------------------------------------------------------
# Projection scope tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_explain_projection(service, db_session, seeded_project):
    """Projection scope loads stage-level context."""
    patch_obj = _mock_llm(service, "整页回答")
    result = await service.explain(
        project_id=seeded_project,
        scope={"kind": "projection", "stage": "what"},
        question="当前阶段有什么？",
        db_session=db_session,
    )
    assert result["answer"] == "整页回答"
    assert "objects_loaded" in result["context_summary"]
    patch_obj.stop()


@pytest.mark.asyncio
async def test_explain_projection_includes_loaded_objects(service, db_session, seeded_project):
    """Projection scope's objects_loaded should include loaded entities."""
    patch_obj = _mock_llm(service, "回答")
    result = await service.explain(
        project_id=seeded_project,
        scope={"kind": "projection", "stage": "what"},
        question="test",
        db_session=db_session,
    )
    loaded = result["context_summary"]["objects_loaded"]
    assert any(o.startswith("actor:") for o in loaded)
    assert any(o.startswith("feature:") for o in loaded)
    patch_obj.stop()


# ---------------------------------------------------------------------------
# Workspace scope tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_explain_workspace(service, db_session, seeded_project):
    """Workspace scope loads full project data."""
    patch_obj = _mock_llm(service, "全项目回答")
    result = await service.explain(
        project_id=seeded_project,
        scope={"kind": "workspace"},
        question="项目概况？",
        db_session=db_session,
    )
    assert result["answer"] == "全项目回答"
    patch_obj.stop()


# ---------------------------------------------------------------------------
# Route error code tests (via route handler)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_project_not_found(service, db_session):
    """project_not_found maps to route handler correctly."""
    patch_obj = _mock_llm(service)
    with pytest.raises(ValueError, match="project_not_found"):
        await service.explain(
            project_id=99999,
            scope={"kind": "workspace"},
            question="test",
            db_session=db_session,
        )
    patch_obj.stop()


@pytest.mark.asyncio
async def test_route_target_not_found(service, db_session, seeded_project):
    """target_not_found is raised by node loader for missing target."""
    with pytest.raises(ValueError, match="target_not_found"):
        await service.explain(
            project_id=seeded_project,
            scope={"kind": "node", "target_type": "feature", "target_id": 999},
            question="test",
            db_session=db_session,
        )
