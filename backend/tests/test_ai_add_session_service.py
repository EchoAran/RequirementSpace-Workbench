"""
Integration tests for AIAddSessionService lifecycle.

Tests cover the end-to-end flow: create session -> send message -> ready ->
generate draft -> confirm/discard. Uses mocked LLM calls and an in-memory
SQLite database to avoid external dependencies.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.modules.ai_interaction.ai_add.application.interview_strategy import (
    BaseInterviewStrategy,
    InterviewStrategyRegistry,
)
from backend.api.modules.ai_interaction.ai_add.application.session import AIAddSessionService
from backend.database.model import AIAddMessageModel, AIAddSessionModel, Base, ProjectModel, BranchWorkspaceModel, RequirementBranchModel

# ---------------------------------------------------------------------------
# Fixtures - async in-memory SQLite database
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def seeded_project(db_session) -> int:
    """Create a seed project and return its ID."""
    project = ProjectModel(
        owner_user_id=1,
        name="测试项目",
        description="用于测试的项目",
        user_requirements="一个测试用的需求描述。",
    )
    db_session.add(project)
    await db_session.flush()
    return project.id


@pytest.fixture
async def seeded_workspace(db_session, seeded_project) -> int:
    branch = RequirementBranchModel(project_id=seeded_project, name="main")
    db_session.add(branch)
    await db_session.flush()
    workspace = BranchWorkspaceModel(project_id=seeded_project, branch_id=branch.id)
    db_session.add(workspace)
    await db_session.flush()
    return workspace.id


@pytest.fixture
async def seeded_project_public_id(db_session, seeded_project) -> str:
    proj = await db_session.get(ProjectModel, seeded_project)
    return proj.public_id


def _make_service_for_target(registry: InterviewStrategyRegistry, tt: str, ctx_keys: list[str]):
    """Register a stub strategy that marks ready on first message."""
    class StubStrategy(BaseInterviewStrategy):
        target_type = tt
        required_context = ctx_keys

        async def interview(self, project_context, anchor, current_summary, latest_user_message, llm_call_chat):
            return {
                "assistant_message": f"已收到: {latest_user_message}",
                "is_ready_to_generate": True,
                "summary": {
                    "target_type": tt,
                    "known_facts": [
                        {"key": "name", "value": latest_user_message, "source": "test"},
                    ],
                    "missing_facts": [],
                    "round_count": 1,
                },
            }
    registry.register(StubStrategy())


@pytest.fixture
def service():
    """Create an AIAddSessionService with stub strategies for all target types (add + edit)."""
    registry = InterviewStrategyRegistry()
    # Add-mode strategies
    _make_service_for_target(registry, "actor", ["actors"])
    _make_service_for_target(registry, "feature_leaf", ["features", "actors"])
    _make_service_for_target(registry, "feature_branch", ["features", "actors"])
    _make_service_for_target(registry, "flow", ["features", "flows"])
    _make_service_for_target(registry, "business_object", ["business_objects", "flows"])
    # Edit-mode strategies (same contract, different target_type)
    _make_service_for_target(registry, "edit_actor", ["actors", "features"])
    _make_service_for_target(registry, "edit_feature", ["features", "actors"])
    _make_service_for_target(registry, "edit_flow", ["features", "flows"])
    _make_service_for_target(registry, "edit_business_object", ["business_objects", "flows"])
    return AIAddSessionService(strategy_registry=registry)


# ---------------------------------------------------------------------------
# Session lifecycle tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_session_success(service, db_session, seeded_project_public_id, seeded_workspace):
    """Creating a session with valid parameters succeeds."""
    result = await service.create_session(
        owner_user_id=1,
        project_id=seeded_project_public_id,
        target_type="actor",
        anchor={"source": "test"},
        session=db_session,
    )
    assert result["session_id"] > 0
    assert result["target_type"] == "actor"
    assert result["status"] == "active"
    assert result["ready_to_generate"] is False

    db_result = await db_session.execute(
        select(AIAddSessionModel).where(AIAddSessionModel.id == result["session_id"])
    )
    assert db_result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_create_session_unsupported_target_type(service, db_session, seeded_project_public_id, seeded_workspace):
    """Creating a session with an unsupported target_type raises ValueError."""
    with pytest.raises(ValueError, match="unsupported_target_type"):
        await service.create_session(
            owner_user_id=1,
            project_id=seeded_project_public_id,
            target_type="unsupported_type",
            anchor={},
            session=db_session,
        )


@pytest.mark.asyncio
async def test_create_session_project_not_found(service, db_session):
    """Creating a session with a non-existent project raises ValueError."""
    with pytest.raises(ValueError, match="project_not_found"):
        await service.create_session(
            owner_user_id=1,
            project_id="nonexistent_uuid",
            target_type="actor",
            anchor={},
            session=db_session,
        )


@pytest.mark.asyncio
async def test_append_user_message_and_ready(service, db_session, seeded_project_public_id, seeded_workspace):
    """Sending a message transitions session to ready."""
    session = await service.create_session(
        owner_user_id=1,
        project_id=seeded_project_public_id,
        target_type="actor",
        anchor={},
        session=db_session,
    )
    session_id = session["session_id"]

    result = await service.append_user_message(
        session_id=session_id,
        content="测试用户",
        db_session=db_session,
    )

    assert result["assistant_message"] == "已收到: 测试用户"
    assert result["is_ready_to_generate"] is True
    assert "summary" in result

    db_session_obj = await db_session.execute(
        select(AIAddSessionModel).where(AIAddSessionModel.id == session_id)
    )
    ai_session = db_session_obj.scalar_one()
    assert ai_session.status == "ready"
    assert ai_session.ready_to_generate is True

    msg_result = await db_session.execute(
        select(AIAddMessageModel).where(AIAddMessageModel.session_id == session_id)
    )
    messages = msg_result.scalars().all()
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"


@pytest.mark.asyncio
async def test_append_user_message_session_not_active(service, db_session, seeded_project_public_id, seeded_workspace):
    """Sending a message to a non-active session raises ValueError."""
    session = await service.create_session(
        owner_user_id=1,
        project_id=seeded_project_public_id,
        target_type="actor",
        anchor={},
        session=db_session,
    )
    session_id = session["session_id"]

    db_session_obj = await db_session.execute(
        select(AIAddSessionModel).where(AIAddSessionModel.id == session_id)
    )
    ai_session = db_session_obj.scalar_one()
    ai_session.status = "confirmed"
    await db_session.flush()

    with pytest.raises(ValueError, match="session_not_active"):
        await service.append_user_message(
            session_id=session_id,
            content="test",
            db_session=db_session,
        )


@pytest.mark.asyncio
async def test_generate_draft_ready_session(service, db_session, seeded_project_public_id, seeded_workspace):
    """generate_draft succeeds when session is ready."""
    session = await service.create_session(
        owner_user_id=1,
        project_id=seeded_project_public_id,
        target_type="actor",
        anchor={},
        session=db_session,
    )
    session_id = session["session_id"]

    await service.append_user_message(
        session_id=session_id,
        content="测试用户",
        db_session=db_session,
    )

    mock_generator = AsyncMock()
    mock_generator.generate.return_value = {
        "actor": {"name": "对话创建的参与者", "description": "通过AI对话创建的用户角色"},
        "rationale": "系统需要此角色来完成测试流程。",
    }

    with patch.object(service, '_get_generator', return_value=mock_generator):
        result = await service.generate_draft(
            owner_user_id=1,
            session_id=session_id,
            db_session=db_session,
        )

    assert result["draft_id"] is not None
    assert result["target_type"] == "actor"
    assert "preview" in result

    db_session_obj = await db_session.execute(
        select(AIAddSessionModel).where(AIAddSessionModel.id == session_id)
    )
    ai_session = db_session_obj.scalar_one()
    assert ai_session.status == "draft_created"


@pytest.mark.asyncio
async def test_generate_draft_session_not_ready(service, db_session, seeded_project_public_id, seeded_workspace):
    """generate_draft on a non-ready session raises ValueError."""
    session = await service.create_session(
        owner_user_id=1,
        project_id=seeded_project_public_id,
        target_type="actor",
        anchor={},
        session=db_session,
    )
    session_id = session["session_id"]

    with pytest.raises(ValueError, match="session_not_ready"):
        await service.generate_draft(
            owner_user_id=1,
            session_id=session_id,
            db_session=db_session,
        )


@pytest.mark.asyncio
async def test_generate_draft_generator_parse_error(service, db_session, seeded_project_public_id, seeded_workspace):
    """generate_draft wraps JSON parse errors in a stable ValueError."""
    import json
    session = await service.create_session(
        owner_user_id=1,
        project_id=seeded_project_public_id,
        target_type="actor",
        anchor={},
        session=db_session,
    )
    session_id = session["session_id"]

    await service.append_user_message(
        session_id=session_id,
        content="测试用户",
        db_session=db_session,
    )

    mock_generator = AsyncMock()
    mock_generator.generate.side_effect = json.JSONDecodeError("Mock error", "", 0)

    with patch.object(service, '_get_generator', return_value=mock_generator):
        with pytest.raises(ValueError, match="generator_output_parse_failed"):
            await service.generate_draft(
                owner_user_id=1,
                session_id=session_id,
                db_session=db_session,
            )


# ---------------------------------------------------------------------------
# Draft lifecycle tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_discard_draft_updates_session(service, db_session, seeded_project_public_id, seeded_workspace):
    """Discarding a draft updates session status to 'discarded'."""
    session = await service.create_session(
        owner_user_id=1,
        project_id=seeded_project_public_id,
        target_type="actor",
        anchor={},
        session=db_session,
    )
    session_id = session["session_id"]

    await service.append_user_message(
        session_id=session_id,
        content="测试用户",
        db_session=db_session,
    )

    mock_generator = AsyncMock()
    mock_generator.generate.return_value = {
        "actor": {"name": "丢弃测试", "description": "测试丢弃"},
        "rationale": "test",
    }

    with patch.object(service, '_get_generator', return_value=mock_generator):
        draft_result = await service.generate_draft(
            owner_user_id=1,
            session_id=session_id,
            db_session=db_session,
        )

    draft_id = draft_result["draft_id"]
    discard_result = await service.discard_draft(draft_id, db_session, owner_user_id=1)

    assert discard_result["draft_id"] == draft_id
    assert discard_result["message"] == "draft_discarded"

    db_session_obj = await db_session.execute(
        select(AIAddSessionModel).where(AIAddSessionModel.id == session_id)
    )
    ai_session = db_session_obj.scalar_one()
    assert ai_session.status == "discarded"


@pytest.mark.asyncio
async def test_get_session_and_messages(service, db_session, seeded_project_public_id, seeded_workspace):
    """get_session and get_session_messages return correct data."""
    session = await service.create_session(
        owner_user_id=1,
        project_id=seeded_project_public_id,
        target_type="actor",
        anchor={"source": "test"},
        session=db_session,
    )
    session_id = session["session_id"]

    await service.append_user_message(
        session_id=session_id,
        content="测试用户",
        db_session=db_session,
    )

    session_info = await service.get_session(session_id, db_session)
    assert session_info["session_id"] == session_id
    assert session_info["target_type"] == "actor"
    assert session_info["ready_to_generate"] is True

    messages = await service.get_session_messages(session_id, db_session)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


# ---------------------------------------------------------------------------
# Strategy registry tests
# ---------------------------------------------------------------------------

def test_strategy_registry_dispatch():
    """Strategy registry returns correct strategy for target_type."""
    from backend.api.modules.ai_interaction.ai_add.application.interview_strategy import create_default_registry
    registry = create_default_registry()
    strategy = registry.get("actor")
    assert strategy.target_type == "actor"


def test_strategy_registry_unsupported():
    """Strategy registry raises ValueError for unsupported target_type."""
    from backend.api.modules.ai_interaction.ai_add.application.interview_strategy import InterviewStrategyRegistry
    registry = InterviewStrategyRegistry()
    with pytest.raises(ValueError, match="unsupported_target_type"):
        registry.get("nonexistent")


# ---------------------------------------------------------------------------
# Pre-confirm validation tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pre_confirm_validation_actor(service, db_session, seeded_project, seeded_workspace):
    """_pre_confirm_validation passes for a non-duplicate actor name."""
    generated = {"name": "唯一名称", "description": "test"}
    await AIAddSessionService._pre_confirm_validation(
        "actor", generated, seeded_project, db_session, seeded_workspace,
    )


@pytest.mark.asyncio
async def test_pre_confirm_validation_actor_duplicate(service, db_session, seeded_project, seeded_workspace):
    """_pre_confirm_validation raises for a duplicate actor name."""
    from backend.database.model import ActorModel
    db_session.add(ActorModel(project_id=seeded_project, workspace_id=seeded_workspace, name="重复名称"))
    await db_session.flush()

    generated = {"name": "重复名称", "description": "test"}
    with pytest.raises(ValueError, match="duplicate_actor_name"):
        await AIAddSessionService._pre_confirm_validation(
            "actor", generated, seeded_project, db_session, seeded_workspace,
        )


# ---------------------------------------------------------------------------
# End-to-end lifecycle tests for all target types
# ---------------------------------------------------------------------------

@pytest.fixture
async def seeded_feature_parent(db_session, seeded_project, seeded_workspace) -> int:
    """Create a root feature node to use as parent."""
    from backend.database.model import FeatureModel
    feat = FeatureModel(project_id=seeded_project, workspace_id=seeded_workspace, name="根模块")
    db_session.add(feat)
    await db_session.flush()
    return feat.id


@pytest.fixture
async def seeded_actors(db_session, seeded_project, seeded_workspace) -> list[int]:
    """Create test actors and return their IDs."""
    from backend.database.model import ActorModel
    ids = []
    for name in ["用户A", "用户B"]:
        a = ActorModel(project_id=seeded_project, workspace_id=seeded_workspace, name=name)
        db_session.add(a)
        await db_session.flush()
        ids.append(a.id)
    return ids


@pytest.fixture
async def seeded_features(db_session, seeded_project, seeded_feature_parent, seeded_workspace) -> list[int]:
    """Create test leaf features and return their IDs."""
    from backend.database.model import FeatureModel, FeatureRelationModel
    ids = []
    for pos, name in enumerate(["现有功能1", "现有功能2"]):
        f = FeatureModel(project_id=seeded_project, workspace_id=seeded_workspace, name=name)
        db_session.add(f)
        await db_session.flush()
        rel = FeatureRelationModel(
            workspace_id=seeded_workspace,
            parent_feature_id=seeded_feature_parent,
            child_feature_id=f.id,
            position=pos,
        )
        db_session.add(rel)
        ids.append(f.id)
    await db_session.flush()
    return ids


@pytest.fixture
async def seeded_flow(db_session, seeded_project, seeded_workspace) -> int:
    """Create a test flow and return its ID."""
    from backend.database.model import FlowModel
    f = FlowModel(project_id=seeded_project, workspace_id=seeded_workspace, name="已有流程")
    db_session.add(f)
    await db_session.flush()
    return f.id


def _make_generator_mock(return_value: dict):
    """Create a mock generator that returns the given value."""
    mock = AsyncMock()
    mock.generate.return_value = return_value
    return mock


async def _run_generate_draft_flow(service, session_id, db_session, mock_return):
    """Helper: send a message, generate a draft with mocked generator."""
    await service.append_user_message(
        session_id=session_id,
        content="测试对象",
        db_session=db_session,
    )

    mock_gen = _make_generator_mock(mock_return)
    with patch.object(service, '_get_generator', return_value=mock_gen):
        result = await service.generate_draft(
            owner_user_id=1,
            session_id=session_id,
            db_session=db_session,
        )
    return result


# --- Feature Leaf end-to-end ---

@pytest.mark.asyncio
async def test_feature_leaf_full_lifecycle(service, db_session, seeded_project_public_id, seeded_feature_parent, seeded_actors, seeded_workspace):
    """Create, chat, generate draft, and confirm a feature_leaf."""
    session = await service.create_session(
        owner_user_id=1,
        project_id=seeded_project_public_id, target_type="feature_leaf",
        anchor={"parent_feature_id": seeded_feature_parent}, session=db_session,
    )
    draft_result = await _run_generate_draft_flow(service, session["session_id"], db_session, {
        "feature": {
            "name": "新增叶子功能",
            "description": "通过AI对话创建",
            "parent_id": seeded_feature_parent,
            "actor_ids": seeded_actors[:1],
            "feature_kind": "leaf",
        },
        "rationale": "测试需要",
    })

    confirm_result = await service.confirm_draft(draft_result["draft_id"], db_session, owner_user_id=1, workspace_id=seeded_workspace)
    assert confirm_result["created_object_id"] is not None
    assert confirm_result["message"] == "confirmed"

    from backend.database.model import FeatureModel
    feat = await db_session.get(FeatureModel, confirm_result["created_object_id"])
    assert feat is not None
    assert feat.name == "新增叶子功能"


# --- Feature Branch end-to-end ---

@pytest.mark.asyncio
async def test_feature_branch_full_lifecycle(service, db_session, seeded_project_public_id, seeded_feature_parent, seeded_actors, seeded_workspace):
    """Create, chat, generate draft, and confirm a feature_branch."""
    session = await service.create_session(
        owner_user_id=1,
        project_id=seeded_project_public_id, target_type="feature_branch",
        anchor={"parent_feature_id": seeded_feature_parent}, session=db_session,
    )
    draft_result = await _run_generate_draft_flow(service, session["session_id"], db_session, {
        "feature": {
            "name": "新增功能模块",
            "description": "子功能模块",
            "parent_id": seeded_feature_parent,
            "actor_ids": [],
            "feature_kind": "branch",
        },
        "rationale": "模块拆分需要",
    })

    confirm_result = await service.confirm_draft(draft_result["draft_id"], db_session, owner_user_id=1, workspace_id=seeded_workspace)
    assert confirm_result["created_object_id"] is not None

    from backend.database.model import FeatureModel
    feat = await db_session.get(FeatureModel, confirm_result["created_object_id"])
    assert feat is not None
    assert feat.name == "新增功能模块"


# --- Flow end-to-end ---

@pytest.mark.asyncio
async def test_flow_full_lifecycle(service, db_session, seeded_project_public_id, seeded_features, seeded_workspace):
    """Create, chat, generate draft, and confirm a flow."""
    session = await service.create_session(
        owner_user_id=1,
        project_id=seeded_project_public_id, target_type="flow",
        anchor={"feature_ids": seeded_features[:1]}, session=db_session,
    )
    draft_result = await _run_generate_draft_flow(service, session["session_id"], db_session, {
        "flow": {
            "name": "新增流程",
            "description": "测试流程",
            "feature_ids": seeded_features[:1],
        },
        "rationale": "流程测试需要",
    })

    confirm_result = await service.confirm_draft(draft_result["draft_id"], db_session, owner_user_id=1, workspace_id=seeded_workspace)
    assert confirm_result["created_object_id"] is not None

    from backend.database.model import FlowModel
    flow = await db_session.get(FlowModel, confirm_result["created_object_id"])
    assert flow is not None
    assert flow.name == "新增流程"


# --- Business Object end-to-end ---

@pytest.mark.asyncio
async def test_business_object_full_lifecycle(service, db_session, seeded_project_public_id, seeded_flow, seeded_workspace):
    """Create, chat, generate draft, and confirm a business object."""
    session = await service.create_session(
        owner_user_id=1,
        project_id=seeded_project_public_id, target_type="business_object",
        anchor={"related_flow_id": seeded_flow}, session=db_session,
    )
    draft_result = await _run_generate_draft_flow(service, session["session_id"], db_session, {
        "business_object": {
            "name": "新增业务对象",
            "description": "测试业务对象",
            "attributes": [
                {"name": "名称", "description": "对象名称", "data_type": "string", "example": "test"},
                {"name": "数量", "description": "数量值", "data_type": "int", "example": "100"},
            ],
        },
        "rationale": "业务需要",
    })

    confirm_result = await service.confirm_draft(draft_result["draft_id"], db_session, owner_user_id=1, workspace_id=seeded_workspace)
    assert confirm_result["created_object_id"] is not None

    from backend.database.model import BusinessObjectAttributeModel, BusinessObjectModel
    bo = await db_session.get(BusinessObjectModel, confirm_result["created_object_id"])
    assert bo is not None
    assert bo.name == "新增业务对象"

    attr_result = await db_session.execute(
        select(BusinessObjectAttributeModel).where(
            BusinessObjectAttributeModel.business_object_id == bo.id,
        )
    )
    attrs = attr_result.scalars().all()
    assert len(attrs) == 2


# ---------------------------------------------------------------------------
# Generator Registry tests
# ---------------------------------------------------------------------------

def test_generator_registry_dispatch():
    """SingleObjectGeneratorRegistry correctly maps target_type to generators."""
    from backend.api.modules.ai_interaction.ai_add.application.generator_registry import (
        create_default_generator_registry,
    )
    from backend.core.generators.single_object.single_actor_generator import SingleActorGenerator

    registry = create_default_generator_registry()
    gen = registry.get("actor")
    assert isinstance(gen, SingleActorGenerator) or type(gen).__name__ == "SingleActorGenerator"


def test_generator_registry_unsupported():
    """Generator registry raises ValueError for unknown target_type."""
    from backend.api.modules.ai_interaction.ai_add.application.generator_registry import SingleObjectGeneratorRegistry
    registry = SingleObjectGeneratorRegistry()
    with pytest.raises(ValueError, match="unsupported_target_type"):
        registry.get("nonexistent")


# ---------------------------------------------------------------------------
# empty_summary_payload check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_draft_empty_summary(service, db_session, seeded_project_public_id, seeded_workspace):
    """generate_draft fails when summary_payload is empty."""
    session = await service.create_session(
        owner_user_id=1,
        project_id=seeded_project_public_id, target_type="actor",
        anchor={}, session=db_session,
    )
    session_id = session["session_id"]

    ai_session = await db_session.get(AIAddSessionModel, session_id)
    ai_session.ready_to_generate = True
    ai_session.summary_payload = None
    await db_session.flush()

    with pytest.raises(ValueError, match="empty_summary_payload"):
        await service.generate_draft(owner_user_id=1, session_id=session_id, db_session=db_session)


# ---------------------------------------------------------------------------
# Edit-mode lifecycle tests
# ---------------------------------------------------------------------------

async def _run_edit_lifecycle(service, db_session, seeded_project, target_type, anchor, mock_generator_return, base_type, assert_updated_field, seeded_workspace):
    """Helper: create edit session → send message → generate draft → confirm → verify."""
    from unittest.mock import patch


    session = await service.create_session(
        owner_user_id=1,
        project_id=seeded_project, target_type=target_type,
        anchor=anchor, session=db_session,
    )
    session_id = session["session_id"]

    await service.append_user_message(
        session_id=session_id,
        content="修改名称",
        db_session=db_session,
    )

    mock_gen = AsyncMock()
    mock_gen.generate.return_value = mock_generator_return

    with patch.object(service, '_get_generator', return_value=mock_gen):
        draft_result = await service.generate_draft(
            owner_user_id=1,
            session_id=session_id,
            db_session=db_session,
        )

    confirm_result = await service.confirm_draft(draft_result["draft_id"], db_session, owner_user_id=1, workspace_id=seeded_workspace)
    assert confirm_result["created_object_id"] is not None
    assert confirm_result["message"] == "confirmed"
    return confirm_result


@pytest.mark.asyncio
async def test_edit_actor_full_lifecycle(service, db_session, seeded_project, seeded_project_public_id, seeded_workspace):
    """Edit actor: modify name and description → confirm → verify update."""
    from backend.database.model import ActorModel

    # Create an actor to edit
    db_session.add(ActorModel(project_id=seeded_project, workspace_id=seeded_workspace, name="旧名称", description="旧描述"))
    await db_session.flush()

    actor_result = await db_session.execute(
        select(ActorModel).where(ActorModel.project_id == seeded_project)
    )
    target_id = actor_result.scalar_one().id

    await _run_edit_lifecycle(
        service, db_session, seeded_project_public_id,
        seeded_workspace=seeded_workspace,
        target_type="edit_actor",
        anchor={"target_id": target_id, "target_type": "actor"},
        mock_generator_return={
            "diff": {"name": {"old": "旧名称", "new": "新名称"}, "description": {"old": "旧描述", "new": "新描述"}},
            "rationale": "用户要求改名",
        },
        base_type="actor",
        assert_updated_field="name",
    )

    # Verify the update was persisted
    updated = await db_session.get(ActorModel, target_id)
    assert updated.name == "新名称"
    assert updated.description == "新描述"


@pytest.mark.asyncio
async def test_edit_feature_full_lifecycle(service, db_session, seeded_project, seeded_project_public_id, seeded_feature_parent, seeded_workspace):
    """Edit feature: modify name → confirm → verify update."""
    from backend.database.model import FeatureModel

    feat = FeatureModel(project_id=seeded_project, workspace_id=seeded_workspace, name="旧功能")
    db_session.add(feat)
    await db_session.flush()

    await _run_edit_lifecycle(
        service, db_session, seeded_project_public_id,
        seeded_workspace=seeded_workspace,
        target_type="edit_feature",
        anchor={"target_id": feat.id, "target_type": "feature"},
        mock_generator_return={
            "diff": {"name": {"old": "旧功能", "new": "新功能"}},
            "rationale": "改名",
        },
        base_type="feature",
        assert_updated_field="name",
    )

    updated = await db_session.get(FeatureModel, feat.id)
    assert updated.name == "新功能"


@pytest.mark.asyncio
async def test_edit_flow_full_lifecycle(service, db_session, seeded_project, seeded_project_public_id, seeded_features, seeded_workspace):
    """Edit flow: modify name → confirm → verify update."""
    from backend.database.model import FlowModel

    flow = FlowModel(project_id=seeded_project, workspace_id=seeded_workspace, name="旧流程")
    db_session.add(flow)
    await db_session.flush()

    await _run_edit_lifecycle(
        service, db_session, seeded_project_public_id,
        seeded_workspace=seeded_workspace,
        target_type="edit_flow",
        anchor={"target_id": flow.id, "target_type": "flow"},
        mock_generator_return={
            "diff": {"name": {"old": "旧流程", "new": "新流程"}},
            "rationale": "改名",
        },
        base_type="flow",
        assert_updated_field="name",
    )

    updated = await db_session.get(FlowModel, flow.id)
    assert updated.name == "新流程"


@pytest.mark.asyncio
async def test_edit_business_object_full_lifecycle(service, db_session, seeded_project, seeded_project_public_id, seeded_flow, seeded_workspace):
    """Edit business object: modify name → confirm → verify update."""
    from backend.database.model import BusinessObjectModel

    bo = BusinessObjectModel(project_id=seeded_project, workspace_id=seeded_workspace, name="旧对象")
    db_session.add(bo)
    await db_session.flush()

    await _run_edit_lifecycle(
        service, db_session, seeded_project_public_id,
        seeded_workspace=seeded_workspace,
        target_type="edit_business_object",
        anchor={"target_id": bo.id, "target_type": "business_object"},
        mock_generator_return={
            "diff": {"name": {"old": "旧对象", "new": "新对象"}},
            "rationale": "改名",
        },
        base_type="business_object",
        assert_updated_field="name",
    )

    updated = await db_session.get(BusinessObjectModel, bo.id)
    assert updated.name == "新对象"


# ---------------------------------------------------------------------------
# Edit generator registry tests
# ---------------------------------------------------------------------------

def test_edit_generator_registry_dispatch():
    """EditGeneratorRegistry maps edit_* target_type to generators."""
    from backend.api.modules.ai_interaction.ai_add.application.generator_registry import (
        create_default_edit_generator_registry,
    )

    registry = create_default_edit_generator_registry()
    gen = registry.get("edit_actor")
    assert gen is not None


def test_edit_generator_registry_unsupported():
    """EditGeneratorRegistry raises for unknown target_type."""
    from backend.api.modules.ai_interaction.ai_add.application.generator_registry import EditGeneratorRegistry

    registry = EditGeneratorRegistry()
    with pytest.raises(ValueError, match="unsupported_target_type"):
        registry.get("nonexistent")


@pytest.mark.asyncio
async def test_feature_add_uses_selected_branch_through_confirmation(
    service, db_session, seeded_project, seeded_project_public_id, seeded_workspace, seeded_actors,
):
    from backend.database.model import ActorModel, FeatureModel, feature_actor_table

    branch = RequirementBranchModel(project_id=seeded_project, name="feature-work")
    db_session.add(branch)
    await db_session.flush()
    workspace = BranchWorkspaceModel(project_id=seeded_project, branch_id=branch.id)
    db_session.add(workspace)
    await db_session.flush()
    source_actor = await db_session.get(ActorModel, seeded_actors[0])
    actor = ActorModel(project_id=seeded_project, workspace_id=workspace.id, name=source_actor.name)
    db_session.add_all([
        actor,
        FeatureModel(project_id=seeded_project, workspace_id=seeded_workspace, name="Added feature"),
    ])
    await db_session.flush()

    created = await service.create_session(
        owner_user_id=1,
        project_id=seeded_project_public_id, target_type="feature_leaf", anchor={}, session=db_session,
    )
    strategy = service.interactor._strategy_registry.get("feature_leaf")
    with patch.object(strategy, "interview", return_value={
        "assistant_message": "Ready", "is_ready_to_generate": True,
        "summary": {"target_type": "feature_leaf"},
    }) as interview:
        await service.append_user_message(
            created["session_id"], "Add a feature", db_session, branch_name=branch.public_id,
        )
    interview_context = interview.call_args.kwargs["project_context"]
    assert [item["id"] for item in interview_context["actors"]] == [actor.id]
    assert interview_context["features"] == []

    generator = AsyncMock()

    async def generate(gen_input):
        assert [item["id"] for item in gen_input.project_context["actors"]] == [actor.id]
        return {"feature": {
            "name": "Added feature", "feature_kind": "leaf",
            "actor_ids": [gen_input.project_context["actors"][0]["id"]],
        }}

    generator.generate.side_effect = generate
    with patch.object(service, "_get_generator", return_value=generator):
        draft = await service.generate_draft(
            created["session_id"], db_session, branch_name=branch.public_id, owner_user_id=1,
        )

    # Changes on another branch must not invalidate this draft's context.
    source_actor.description = "Changed on main"
    await db_session.flush()
    result = await service.confirm_draft(draft["draft_id"], db_session, workspace_id=workspace.id, owner_user_id=1)
    feature = await db_session.get(FeatureModel, result["created_object_id"])
    assert feature.workspace_id == workspace.id
    actor_ids = (await db_session.execute(
        select(feature_actor_table.c.actor_id).where(feature_actor_table.c.feature_id == feature.id)
    )).scalars().all()
    assert actor_ids == [actor.id]


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["message", "generate"])
async def test_ai_add_routes_forward_selected_branch(endpoint):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from backend.api.modules.ai_interaction.ai_add import routes
    from backend.api.modules.ai_interaction.ai_add.schemas import AIAddMessageRequest

    @asynccontextmanager
    async def llm_context(*args, **kwargs):
        yield

    service_mock = AsyncMock()
    arguments = {
        "branch": "feature-work", "user": SimpleNamespace(id=1),
        "ai_session": SimpleNamespace(id=7, project_id=1),
        "db_session": AsyncMock(), "commit_guard": None,
    }
    with patch.object(routes, "_get_service", return_value=service_mock), patch.object(
        routes, "llm_context_manager", llm_context,
    ):
        if endpoint == "message":
            await routes.send_ai_add_message(AIAddMessageRequest(content="Add feature"), **arguments)
            call = service_mock.append_user_message.call_args
        else:
            await routes.generate_ai_add_draft(**arguments)
            call = service_mock.generate_draft.call_args
    assert call.kwargs["branch_name"] == "feature-work"


@pytest.mark.asyncio
async def test_adopted_feature_parent_survives_branch_snapshot_and_restore(
    service, db_session, seeded_project, seeded_workspace,
):
    from backend.api.modules.ai_interaction.ai_add.application.session_draft_handler import AIAddDraftHandler
    from backend.api.modules.version_control.application.workspace_serializer import serialize_workspace
    from backend.api.modules.version_control.application.workspace_restoration import restore_workspace_from_state
    from backend.database.model import FeatureModel, FeatureRelationModel

    branch = RequirementBranchModel(project_id=seeded_project, name="exploration")
    db_session.add(branch)
    await db_session.flush()
    workspace = BranchWorkspaceModel(project_id=seeded_project, branch_id=branch.id)
    db_session.add(workspace)
    await db_session.flush()
    parent = FeatureModel(project_id=seeded_project, workspace_id=workspace.id, name="月底收支明细查看")
    db_session.add(parent)
    await db_session.flush()
    child_id = await AIAddDraftHandler(service)._persist_generated_object(
        "feature_leaf", {"name": "查看作废记录", "parent_id": parent.id},
        seeded_project, db_session, workspace.id,
    )
    state = await db_session.run_sync(
        lambda sync: serialize_workspace(sync, sync.get(BranchWorkspaceModel, workspace.id))
    )
    assert len(state["feature_relations"]) == 1
    relation = (await db_session.execute(
        select(FeatureRelationModel).where(FeatureRelationModel.child_feature_id == child_id)
    )).scalar_one()
    assert relation.workspace_id == workspace.id
    assert relation.parent_feature_id == parent.id

    restored_branch = RequirementBranchModel(project_id=seeded_project, name="restored")
    db_session.add(restored_branch)
    await db_session.flush()
    restored = BranchWorkspaceModel(project_id=seeded_project, branch_id=restored_branch.id)
    db_session.add(restored)
    await db_session.flush()
    await db_session.run_sync(lambda sync: restore_workspace_from_state(sync, restored, state))
    restored_state = await db_session.run_sync(lambda sync: serialize_workspace(sync, restored))
    assert restored_state["feature_relations"] == state["feature_relations"]
    assert (await db_session.execute(
        select(FeatureRelationModel).where(FeatureRelationModel.workspace_id == seeded_workspace)
    )).scalars().all() == []
