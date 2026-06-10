"""
Tests for ActorGenerationChoiceAdapter and ScenarioGenerationChoiceAdapter (Phase 3).

Covers:
- Adapter generate_candidate
- Adapter is_duplicate
- Adapter is_context_stale
- Choice group creation via GenerationChoiceService (no real model write)
- Accept choice writes real model
- Discard does not write
- Stale detection on context change
"""
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.database.model import (
    Base, ProjectModel, ActorModel, FeatureModel,
    ScenarioModel, ScenarioAcceptanceCriterionModel, feature_actor_table,
)
from backend.api.services.generation_choice_service import (
    GenerationChoiceService,
    CandidateContext,
    get_adapter,
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


@pytest.fixture
async def seeded_project(db_session) -> int:
    project = ProjectModel(
        name="测试项目", description="",
        user_requirements="需要一个用户管理系统，支持角色权限和内容管理。",
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)

    # Add an actor for scenario generation context
    actor = ActorModel(
        project_id=project.id, name="管理员",
        description="系统管理员", confirmation_status="ai_assumption",
    )
    db_session.add(actor)
    await db_session.flush()
    await db_session.refresh(actor)

    # Add a feature for scenario generation context
    feature = FeatureModel(
        project_id=project.id, name="用户管理",
        description="管理用户", confirmation_status="ai_assumption",
    )
    db_session.add(feature)
    await db_session.flush()
    await db_session.refresh(feature)

    # Link feature to actor
    await db_session.execute(
        feature_actor_table.insert().values(feature_id=feature.id, actor_id=actor.id)
    )
    await db_session.flush()

    return project.id


# ═══════════════════════════════════════════════════════════════════
# Actor Adapter Tests
# ═══════════════════════════════════════════════════════════════════

class TestActorGenerationChoiceAdapter:
    def setup_method(self):
        self.adapter = get_adapter("actor")

    @pytest.mark.asyncio
    async def test_generate_candidate_returns_valid_candidate(self, db_session, seeded_project):
        """generate_candidate should return a valid GenerationCandidate."""
        ctx = CandidateContext(
            index=0, strategy="balanced",
            project_id=seeded_project, session=db_session,
        )
        candidate = await self.adapter.generate_candidate(ctx)
        assert candidate.title is not None
        assert len(candidate.title) > 0
        assert candidate.draft_type == "actor"
        assert candidate.apply_mode == "draft_payload"
        assert "actors" in candidate.payload
        assert candidate.comparison_summary != ""

    def test_is_duplicate_same_actors(self):
        """Candidates with same actor name set are duplicates."""
        c1 = _make_actor_candidate(["管理员", "用户"])
        c2 = _make_actor_candidate(["管理员", "用户"])
        assert self.adapter.is_duplicate(c2, [c1])

    def test_is_duplicate_different_actors(self):
        """Candidates with different actor name sets are not duplicates."""
        c1 = _make_actor_candidate(["管理员"])
        c2 = _make_actor_candidate(["访客"])
        assert not self.adapter.is_duplicate(c2, [c1])


# ═══════════════════════════════════════════════════════════════════
# Scenario Adapter Tests
# ═══════════════════════════════════════════════════════════════════

class TestScenarioGenerationChoiceAdapter:
    def setup_method(self):
        self.adapter = get_adapter("scenario")

    @pytest.mark.asyncio
    async def test_generate_candidate_returns_valid_candidate(self, db_session, seeded_project):
        """generate_candidate should work for pair mode with valid context."""
        ctx = CandidateContext(
            index=0, strategy="balanced",
            project_id=seeded_project,
            target={"generation_mode": "pair", "feature_id": 1, "actor_id": 1},
            session=db_session,
        )
        candidate = await self.adapter.generate_candidate(ctx)
        assert candidate.title is not None
        assert candidate.draft_type == "scenario"
        assert "scenarios" in candidate.payload
        assert candidate.comparison_summary != ""

    def test_is_duplicate_same_scenarios(self):
        """Candidates with same scenario name set are duplicates."""
        c1 = _make_scenario_candidate(["登录验证", "权限检查"])
        c2 = _make_scenario_candidate(["登录验证", "权限检查"])
        assert self.adapter.is_duplicate(c2, [c1])

    def test_is_duplicate_different_scenarios(self):
        """Candidates with different scenario names are not duplicates."""
        c1 = _make_scenario_candidate(["登录验证"])
        c2 = _make_scenario_candidate(["用户注册"])
        assert not self.adapter.is_duplicate(c2, [c1])


# ═══════════════════════════════════════════════════════════════════
# Integration: Actor Choice Group
# ═══════════════════════════════════════════════════════════════════

class TestActorChoiceGroupIntegration:
    @pytest.mark.asyncio
    async def test_create_actor_choice_group_does_not_write_actors(self, db_session, seeded_project):
        """创建 actor choice group 后不应写 ActorModel。"""
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="actor",
            candidate_count=1,
            session=db_session,
        )
        assert result["status"] == "open"
        assert result["generation_type"] == "actor"

        actors = await db_session.execute(
            select(ActorModel).where(ActorModel.project_id == seeded_project)
        )
        # Only the seed actor should exist
        assert len(actors.scalars().all()) == 1

    @pytest.mark.asyncio
    async def test_accept_actor_choice_writes_actors_and_replaces(self, db_session, seeded_project):
        """采纳 actor choice 后应替换 ActorModel。"""
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="actor",
            candidate_count=1,
            session=db_session,
        )
        choice_id = result["choices"][0]["id"]

        from backend.api.services.choice_service import ChoiceService
        cs = ChoiceService()
        accept_result = await cs.accept_choice(
            project_id=seeded_project,
            choice_id=choice_id,
            session=db_session,
            force=True,
        )
        assert accept_result.status == "accepted"

        # Verify old actor was replaced
        actors = await db_session.execute(
            select(ActorModel).where(ActorModel.project_id == seeded_project)
        )
        all_actors = actors.scalars().all()
        # Old seed actor was deleted and new ones added
        assert len(all_actors) > 0
        assert all_actors[0].name != "管理员"  # old name replaced

    @pytest.mark.asyncio
    async def test_discard_actor_choice_group_does_not_write(self, db_session, seeded_project):
        """丢弃 actor choice group 后不应修改 ActorModel。"""
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="actor",
            candidate_count=1,
            session=db_session,
        )
        group_id = result["id"]

        from backend.api.services.choice_service import ChoiceService
        cs = ChoiceService()
        discard_result = await cs.discard_choice_group(
            project_id=seeded_project, group_id=group_id, session=db_session,
        )
        assert discard_result.status == "discarded"

        # Seed actor should still exist
        actors = await db_session.execute(
            select(ActorModel).where(ActorModel.project_id == seeded_project)
        )
        assert len(actors.scalars().all()) == 1  # only seed


# ═══════════════════════════════════════════════════════════════════
# Integration: Scenario Choice Group
# ═══════════════════════════════════════════════════════════════════

class TestScenarioChoiceGroupIntegration:
    @pytest.mark.asyncio
    async def test_create_scenario_choice_group_does_not_write_scenarios(
        self, db_session, seeded_project
    ):
        """创建 scenario choice group 后不应写 ScenarioModel。"""
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="scenario",
            target={"generation_mode": "pair", "feature_id": 1, "actor_id": 1},
            candidate_count=1,
            session=db_session,
        )
        assert result["status"] == "open"
        assert result["generation_type"] == "scenario"

        scenarios = await db_session.execute(
            select(ScenarioModel).where(ScenarioModel.project_id == seeded_project)
        )
        assert len(scenarios.scalars().all()) == 0

    @pytest.mark.asyncio
    async def test_accept_scenario_choice_writes_scenarios(self, db_session, seeded_project):
        """采纳 scenario choice 后应写 ScenarioModel 并且自动附加 AcceptanceCriterionModel。"""
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="scenario",
            target={"generation_mode": "pair", "feature_id": 1, "actor_id": 1},
            candidate_count=1,
            session=db_session,
        )
        choice_id = result["choices"][0]["id"]

        from backend.api.services.choice_service import ChoiceService
        cs = ChoiceService()
        accept_result = await cs.accept_choice(
            project_id=seeded_project,
            choice_id=choice_id,
            session=db_session,
            force=True,
        )
        assert accept_result.status == "accepted"

        scenarios = await db_session.execute(
            select(ScenarioModel).where(ScenarioModel.project_id == seeded_project)
        )
        scenarios_list = scenarios.scalars().all()
        assert len(scenarios_list) > 0
        scenario_ids = [s.id for s in scenarios_list]

        # Verify acceptance criteria were automatically generated and saved
        criteria = await db_session.execute(
            select(ScenarioAcceptanceCriterionModel).where(ScenarioAcceptanceCriterionModel.scenario_id.in_(scenario_ids))
        )
        criteria_list = criteria.scalars().all()
        assert len(criteria_list) > 0
        for ac in criteria_list:
            assert ac.scenario_id in scenario_ids

    @pytest.mark.asyncio
    async def test_discard_scenario_choice_group_does_not_write(
        self, db_session, seeded_project
    ):
        """丢弃 scenario choice group 后不应写 ScenarioModel。"""
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="scenario",
            target={"generation_mode": "pair", "feature_id": 1, "actor_id": 1},
            candidate_count=1,
            session=db_session,
        )
        group_id = result["id"]

        from backend.api.services.choice_service import ChoiceService
        cs = ChoiceService()
        discard_result = await cs.discard_choice_group(
            project_id=seeded_project, group_id=group_id, session=db_session,
        )
        assert discard_result.status == "discarded"

        scenarios = await db_session.execute(
            select(ScenarioModel).where(ScenarioModel.project_id == seeded_project)
        )
        assert len(scenarios.scalars().all()) == 0


# ═══════════════════════════════════════════════════════════════════
# Stale Detection
# ═══════════════════════════════════════════════════════════════════

class TestScenarioStaleDetection:
    @pytest.mark.asyncio
    async def test_scenario_stale_when_feature_deleted(self, db_session, seeded_project):
        """当 feature 被删除后，采纳 scenario choice 应返回 stale。"""
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="scenario",
            target={"generation_mode": "pair", "feature_id": 1, "actor_id": 1},
            candidate_count=1,
            session=db_session,
        )
        choice_id = result["choices"][0]["id"]

        # Delete the feature
        feature = await db_session.get(FeatureModel, 1)
        if feature:
            await db_session.delete(feature)
            await db_session.flush()

        from backend.api.services.choice_service import ChoiceService
        cs = ChoiceService()
        accept_result = await cs.accept_choice(
            project_id=seeded_project,
            choice_id=choice_id,
            session=db_session,
        )
        assert accept_result.is_stale is True
        assert accept_result.stale_reason is not None
        assert "删除" in accept_result.stale_reason or "适用" in accept_result.stale_reason

    @pytest.mark.asyncio
    async def test_force_accept_skips_stale_for_scenario(self, db_session, seeded_project):
        """force=True 应跳过 stale 校验，is_context_stale 不被调用。"""
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=seeded_project,
            generation_type="scenario",
            target={"generation_mode": "pair", "feature_id": 1, "actor_id": 1},
            candidate_count=1,
            session=db_session,
        )
        choice_id = result["choices"][0]["id"]

        from backend.api.services.choice_service import ChoiceService
        cs = ChoiceService()
        # force=True 且 feature 存在 → 正常采纳
        accept_result = await cs.accept_choice(
            project_id=seeded_project,
            choice_id=choice_id,
            session=db_session,
            force=True,
        )
        assert accept_result.status == "accepted"
        # is_stale 应为 False（未检查 stale，因为 force=True）
        assert accept_result.is_stale is False


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _make_actor_candidate(names: list[str]):
    """Create a GenerationCandidate with given actor names."""
    from backend.api.services.generation_choice_service import GenerationCandidate
    return GenerationCandidate(
        title="test",
        rationale="",
        payload={
            "actors": [{"actor_name": n, "actor_description": ""} for n in names],
        },
        preview={},
        draft_type="actor",
        apply_mode="draft_payload",
    )


def _make_scenario_candidate(names: list[str]):
    """Create a GenerationCandidate with given scenario names."""
    from backend.api.services.generation_choice_service import GenerationCandidate
    return GenerationCandidate(
        title="test",
        rationale="",
        payload={
            "scenarios": [
                {"scenario_name": n, "scenario_content": "", "feature_id": 1, "actor_id": 1}
                for n in names
            ],
        },
        preview={},
        draft_type="scenario",
        apply_mode="draft_payload",
    )
