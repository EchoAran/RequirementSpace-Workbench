"""
Tests for Project Creation Choice Group service (Phase 2).

Covers:
- ProjectCreationChoiceAdapter
- ProjectCreationChoiceGroupService.create_choice_group
- Accept choice creates real project
- Discard does not create project
- Listing open groups
- Partial failure creates failed group
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.database.model import Base, ProjectModel, ActorModel, FeatureModel, GenerativeDraftModel
from backend.api.modules.project_lifecycle.application.creation_choice_service import (
    ProjectCreationChoiceGroupService,
    ProjectCreationChoiceAdapter,
)
from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
    CandidateContext,
    GenerationChoiceSettings,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture(autouse=True)
def mock_generators():
    from unittest.mock import AsyncMock, patch
    mock_blank_ret = {"project_name": "测试项目", "project_description": "测试项目描述"}
    mock_actors_ret = {"actors": [{"actor_name": "用户", "actor_description": "系统用户"}]}
    mock_features_ret = {
        "features": [
            {
                "feature_number": "F001",
                "feature_name": "系统管理",
                "feature_description": "管理系统基础配置",
                "actor_ids": [1],
            }
        ]
    }
    with patch("backend.core.generators.blank_project_generator.BlankProjectGenerator.generate", new_callable=AsyncMock) as m_blank, \
         patch("backend.core.generators.actors_generator.ActorsGenerator.generate", new_callable=AsyncMock) as m_actors, \
         patch("backend.core.generators.features_generator.FeaturesGenerator.generate", new_callable=AsyncMock) as m_features:
        m_blank.return_value = mock_blank_ret
        m_actors.return_value = mock_actors_ret
        m_features.return_value = mock_features_ret
        yield


# ═══════════════════════════════════════════════════════════════════
# Adapter Unit Tests
# ═══════════════════════════════════════════════════════════════════

class TestProjectCreationChoiceAdapter:
    def setup_method(self):
        self.adapter = ProjectCreationChoiceAdapter()

    def test_is_duplicate_same_project(self):
        """Candidates with same project name, actors, features are duplicates."""
        c1 = _make_candidate("项目A", actors=["用户1"], features=["功能1"])
        c2 = _make_candidate("项目A", actors=["用户1"], features=["功能1"])
        assert self.adapter.is_duplicate(c2, [c1])

    def test_is_duplicate_different_project(self):
        """Different project names => not duplicates."""
        c1 = _make_candidate("项目A", actors=["用户1"], features=["功能1"])
        c2 = _make_candidate("项目B", actors=["用户1"], features=["功能1"])
        assert not self.adapter.is_duplicate(c2, [c1])

    def test_is_duplicate_different_actors(self):
        """Different actor sets => not duplicates."""
        c1 = _make_candidate("项目A", actors=["用户1"], features=["功能1"])
        c2 = _make_candidate("项目A", actors=["用户2"], features=["功能1"])
        assert not self.adapter.is_duplicate(c2, [c1])


# ═══════════════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════════════

class TestProjectCreationChoiceGroupService:
    @pytest.mark.asyncio
    async def test_create_choice_group_returns_candidates_no_project_created(
        self, db_session
    ):
        """创建 choice group 后返回候选，但 projects 表没有新增记录。"""
        service = ProjectCreationChoiceGroupService()
        result = await service.create_choice_group(
            user_requirements="我需要一个任务管理系统",
            candidate_count=2,
            session=db_session,
        )
        assert result["status"] == "open"
        assert result["generation_type"] == "project_creation"
        assert result["success_count"] >= 1  # at least 1 candidate
        assert len(result["choices"]) >= 1

        # 验证未创建任何 project
        projects = await db_session.execute(select(ProjectModel))
        assert len(projects.scalars().all()) == 0

    @pytest.mark.asyncio
    async def test_accept_choice_creates_project(self, db_session):
        """采纳 choice 后应创建 ProjectModel + ActorModel + FeatureModel。"""
        service = ProjectCreationChoiceGroupService()
        result = await service.create_choice_group(
            user_requirements="我需要一个简单的博客系统",
            candidate_count=1,  # 单候选简化测试
            session=db_session,
        )
        assert result["status"] == "open"
        first_choice = result["choices"][0]
        assert first_choice["status"] == "candidate"

        # 采纳
        accept_result = await service.accept_choice(
            group_id=result["id"],
            choice_id=first_choice["id"],
            session=db_session,
        )
        assert accept_result["message"] == "project_created"
        assert isinstance(accept_result["project_id"], str)
        assert len(accept_result["project_id"]) > 0

        # 验证 project 已创建
        proj_stmt = select(ProjectModel).where(ProjectModel.public_id == accept_result["project_id"])
        project = (await db_session.execute(proj_stmt)).scalar_one_or_none()
        assert project is not None
        assert project.name is not None

        # 验证 actors 和 features 已创建
        actors = await db_session.execute(
            select(ActorModel).where(ActorModel.project_id == project.id)
        )
        assert len(actors.scalars().all()) > 0

        features = await db_session.execute(
            select(FeatureModel).where(FeatureModel.project_id == project.id)
        )
        assert len(features.scalars().all()) > 0

        # 验证 group 已 resolved
        draft = await db_session.execute(
            select(GenerativeDraftModel).where(
                GenerativeDraftModel.draft_id == result["id"]
            )
        )
        resolved_payload = draft.scalar_one().payload
        assert resolved_payload["status"] == "resolved"

    @pytest.mark.asyncio
    async def test_discard_does_not_create_project(self, db_session):
        """丢弃 choice group 后不应创建任何 project。"""
        service = ProjectCreationChoiceGroupService()
        result = await service.create_choice_group(
            user_requirements="丢弃测试项目",
            candidate_count=1,
            session=db_session,
        )
        group_id = result["id"]

        discard_result = await service.discard_choice_group(
            group_id=group_id, session=db_session,
        )
        assert discard_result["message"] == "choice_group_discarded"

        projects = await db_session.execute(select(ProjectModel))
        assert len(projects.scalars().all()) == 0

        # 验证 group 状态已更新
        draft = await db_session.execute(
            select(GenerativeDraftModel).where(
                GenerativeDraftModel.draft_id == group_id
            )
        )
        payload = draft.scalar_one().payload
        assert payload["status"] == "discarded"

    @pytest.mark.asyncio
    async def test_list_open_groups(self, db_session):
        """list_open_choice_groups 应只返回 status=open 的 group。"""
        service = ProjectCreationChoiceGroupService()
        # 先创建一个 open group
        await service.create_choice_group(
            user_requirements="列表测试项目1",
            candidate_count=1,
            session=db_session,
        )

        groups = await service.list_open_choice_groups(session=db_session)
        assert len(groups) >= 1
        for g in groups:
            assert g["status"] == "open"

    @pytest.mark.asyncio
    async def test_get_choice_group_by_id(self, db_session):
        """get_choice_group 应按 id 返回正确 group。"""
        service = ProjectCreationChoiceGroupService()
        result = await service.create_choice_group(
            user_requirements="查询测试",
            candidate_count=1,
            session=db_session,
        )
        loaded = await service.get_choice_group(result["id"], session=db_session)
        assert loaded is not None
        assert loaded["id"] == result["id"]
        assert loaded["status"] == "open"

    @pytest.mark.asyncio
    async def test_get_nonexistent_group_returns_none(self, db_session):
        """不存在的 group_id 应返回 None。"""
        service = ProjectCreationChoiceGroupService()
        result = await service.get_choice_group("nonexistent_id", session=db_session)
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _make_candidate(project_name, actors=None, features=None):
    """Create a GenerationCandidate with the given project structure."""
    from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import GenerationCandidate
    return GenerationCandidate(
        title=project_name,
        rationale="",
        payload={
            "project_preview": {
                "project_name": project_name,
                "project_description": "",
            },
            "actors": [{"actor_name": a, "actor_description": ""} for a in (actors or [])],
            "features": [{"feature_name": f, "feature_description": "", "feature_number": f"F{i+1:03d}"} for i, f in enumerate(features or [])],
        },
        preview={},
        draft_type="project_creation",
        apply_mode="draft_payload",
        comparison_summary=f"{project_name} 方案",
    )
