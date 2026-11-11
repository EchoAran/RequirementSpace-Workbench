"""
Tests for Phase 4 adapters: acceptance_criteria, feature, flow, scope.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
    GenerationChoiceService,
    get_adapter,
)
from backend.database.model import (
    ActorModel,
    Base,
    BranchWorkspaceModel,
    RequirementBranchModel,
    FeatureModel,
    FlowModel,
    ProjectModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    ScopeModel,
    feature_actor_table,
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
        owner_user_id=1,
        name="测试项目", description="",
        user_requirements="需要一个内容管理系统，支持多角色和审批流程。",
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)

    branch = RequirementBranchModel(project_id=project.id, name="test-candidates")
    db_session.add(branch)
    await db_session.flush()
    workspace = BranchWorkspaceModel(
        project_id=project.id, branch_id=branch.id,
        user_requirements=project.user_requirements,
    )
    db_session.add(workspace)
    await db_session.flush()

    actor = ActorModel(project_id=project.id, workspace_id=workspace.id, name="编辑",
                       description="内容编辑", confirmation_status="ai_assumption")
    db_session.add(actor)
    await db_session.flush()
    await db_session.refresh(actor)

    feature = FeatureModel(project_id=project.id, workspace_id=workspace.id, name="内容管理",
                           description="管理内容", confirmation_status="ai_assumption")
    db_session.add(feature)
    await db_session.flush()
    await db_session.refresh(feature)
    await db_session.execute(
        feature_actor_table.insert().values(feature_id=feature.id, actor_id=actor.id)
    )

    scenario = ScenarioModel(
        project_id=project.id, workspace_id=workspace.id, feature_id=feature.id,
        actor_id=actor.id, name="创建内容", content="用户创建新内容",
        confirmation_status="ai_assumption",
    )
    db_session.add(scenario)
    await db_session.flush()
    await db_session.refresh(scenario)

    await db_session.flush()
    return project.id, actor.id, feature.id, scenario.id, workspace.id


@pytest.fixture(autouse=True)
def mock_candidate_generation(monkeypatch):
    from unittest.mock import AsyncMock

    candidates = {
        "acceptance_criteria": _make_ac_candidate(["Generated criterion"]),
        "feature": _make_feature_candidate(["Generated feature"]),
        "flow": _make_flow_candidate(["Generated flow"]),
        "scope": _make_scope_candidate([(1, "current")]),
    }
    for generation_type, candidate in candidates.items():
        monkeypatch.setattr(
            type(get_adapter(generation_type)),
            "generate_candidate",
            AsyncMock(return_value=candidate),
        )


# ═══════════════════════════════════════════════════════════════════
# AC Adapter Tests
# ═══════════════════════════════════════════════════════════════════

class TestACAdapter:
    def setup_method(self):
        self.adapter = get_adapter("acceptance_criteria")

    def test_is_duplicate(self):
        c1 = _make_ac_candidate(["标准A", "标准B"])
        c2 = _make_ac_candidate(["标准A", "标准B"])
        c3 = _make_ac_candidate(["标准C"])
        assert self.adapter.is_duplicate(c2, [c1])
        assert not self.adapter.is_duplicate(c3, [c1])


class TestACIntegration:
    @pytest.mark.asyncio
    async def test_create_choice_group_does_not_write_ac(self, db_session, seeded_project):
        p_id, _a_id, _f_id, s_id , workspace_id = seeded_project
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=p_id, generation_type="acceptance_criteria",
            target={"generation_mode": "single", "scenario_ids": [s_id]},
            candidate_count=1, session=db_session,
                           workspace_id=workspace_id,
        )
        assert result["status"] == "open"
        if result["status"] == "open":
            # AC model has no direct project_id; query via scenario
            acs = await db_session.execute(select(ScenarioAcceptanceCriterionModel))
            assert len(acs.scalars().all()) == 0


# ═══════════════════════════════════════════════════════════════════
# Feature Adapter Tests
# ═══════════════════════════════════════════════════════════════════

class TestFeatureAdapter:
    def setup_method(self):
        self.adapter = get_adapter("feature")

    def test_is_duplicate(self):
        c1 = _make_feature_candidate(["用户管理", "内容管理"])
        c2 = _make_feature_candidate(["用户管理", "内容管理"])
        c3 = _make_feature_candidate(["订单管理"])
        assert self.adapter.is_duplicate(c2, [c1])
        assert not self.adapter.is_duplicate(c3, [c1])


class TestFeatureIntegration:
    @pytest.mark.asyncio
    async def test_create_choice_group_does_not_write(self, db_session, seeded_project):
        p_id, _a_id, _f_id, _s_id , workspace_id = seeded_project
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=p_id, generation_type="feature",
            candidate_count=1, session=db_session,
                           workspace_id=workspace_id,
        )
        assert result["status"] == "open"
        if result["status"] == "open":
            features = await db_session.execute(
                select(FeatureModel).where(FeatureModel.project_id == p_id, FeatureModel.name != "内容管理")
            )
            assert len(features.scalars().all()) == 0


# ═══════════════════════════════════════════════════════════════════
# Flow Adapter Tests
# ═══════════════════════════════════════════════════════════════════

class TestFlowAdapter:
    def setup_method(self):
        self.adapter = get_adapter("flow")

    def test_is_duplicate(self):
        c1 = _make_flow_candidate(["审核流程", "发布流程"])
        c2 = _make_flow_candidate(["审核流程", "发布流程"])
        c3 = _make_flow_candidate(["退款流程"])
        assert self.adapter.is_duplicate(c2, [c1])
        assert not self.adapter.is_duplicate(c3, [c1])


class TestFlowIntegration:
    @pytest.mark.asyncio
    async def test_create_choice_group_does_not_write(self, db_session, seeded_project):
        p_id, _a_id, _f_id, _s_id , workspace_id = seeded_project
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=p_id, generation_type="flow",
            candidate_count=1, session=db_session,
                           workspace_id=workspace_id,
        )
        assert result["status"] == "open"
        if result["status"] == "open":
            flows = await db_session.execute(
                select(FlowModel).where(FlowModel.project_id == p_id)
            )
            assert len(flows.scalars().all()) == 0


# ═══════════════════════════════════════════════════════════════════
# Scope Adapter Tests
# ═══════════════════════════════════════════════════════════════════

class TestScopeAdapter:
    def setup_method(self):
        self.adapter = get_adapter("scope")

    def test_is_duplicate(self):
        c1 = _make_scope_candidate([(1, "current"), (2, "postponed")])
        c2 = _make_scope_candidate([(1, "current"), (2, "postponed")])
        c3 = _make_scope_candidate([(1, "exclude")])
        assert self.adapter.is_duplicate(c2, [c1])
        assert not self.adapter.is_duplicate(c3, [c1])


class TestScopeIntegration:
    @pytest.mark.asyncio
    async def test_create_choice_group_does_not_write(self, db_session, seeded_project):
        p_id, _a_id, _f_id, _s_id , workspace_id = seeded_project
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=p_id, generation_type="scope",
            candidate_count=1, session=db_session,
                           workspace_id=workspace_id,
        )
        assert result["status"] == "open"
        if result["status"] == "open":
            scopes = await db_session.execute(
                select(ScopeModel)
                .join(FeatureModel)
                .where(FeatureModel.project_id == p_id)
            )
            assert len(scopes.scalars().all()) == 0


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _make_ac_candidate(contents):
    from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
        GenerationCandidate,
    )
    return GenerationCandidate(
        title="test", rationale="",
        payload={"acceptance_criteria": [{"criterion_content": c} for c in contents]},
        preview={}, draft_type="acceptance_criteria", apply_mode="draft_payload",
    )


def _make_feature_candidate(names):
    from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
        GenerationCandidate,
    )
    return GenerationCandidate(
        title="test", rationale="",
        payload={"features": [{"feature_name": n, "feature_description": ""} for n in names]},
        preview={}, draft_type="feature", apply_mode="draft_payload",
    )


def _make_flow_candidate(names):
    from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
        GenerationCandidate,
    )
    return GenerationCandidate(
        title="test", rationale="",
        payload={"flows": [{"flow_name": n, "flow_steps": []} for n in names]},
        preview={}, draft_type="flow", apply_mode="draft_payload",
    )


def _make_scope_candidate(entries):
    from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
        GenerationCandidate,
    )
    return GenerationCandidate(
        title="test", rationale="",
        payload={"scopes": [{"feature_id": fid, "scope_status": st} for fid, st in entries]},
        preview={}, draft_type="scope", apply_mode="draft_payload",
    )
