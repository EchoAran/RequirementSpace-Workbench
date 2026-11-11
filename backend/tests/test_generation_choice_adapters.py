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
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
    CandidateContext,
    GenerationChoiceService,
    get_adapter,
)
from backend.database.model import (
    ActorModel,
    Base,
    BranchWorkspaceModel,
    BusinessObjectModel,
    FeatureModel,
    FlowModel,
    GherkinSpecModel,
    ProjectModel,
    RequirementBranchModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
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


@pytest.fixture(autouse=True)
def mock_generators():
    mock_actors_ret = {"actors": [{"actor_name": "普通用户", "actor_description": "普通系统用户"}]}
    mock_scenarios_ret = {
        "scenarios": [
            {
                "scenario_name": "查询用户",
                "scenario_content": "Given 管理员已登录, When 查询用户列表, Then 展现所有注册用户",
            }
        ]
    }
    mock_ac_ret = {
        "scenario_acceptance_criteria": [
            {
                "scenario_id": 1,
                "acceptance_criteria": [
                    "列表加载不超过500ms"
                ]
            }
        ]
    }
    async def _fake_flows_generate(input_data, **kwargs):
        feat_id = input_data.features[0].featureId if input_data.features else 1
        act_id = input_data.actors[0].actorId if input_data.actors else 1
        return {
            "business_objects": [
                {
                    "business_object_number": "B-001",
                    "business_object_name": "Cart",
                    "business_object_description": "Shopping cart",
                    "business_object_attributes": [
                        {
                            "business_object_attribute_name": "items",
                            "business_object_attribute_description": "list of items",
                            "business_object_attribute_type": "list",
                            "business_object_attribute_example": "[]",
                        }
                    ],
                }
            ],
            "flows": [
                {
                    "flow_name": "结账流程",
                    "flow_description": "完成结账",
                    "feature_ids": [feat_id],
                    "flow_steps": [
                        {
                            "step_number": "S-001",
                            "step_name": "点击结算",
                            "step_description": "用户点击结算按钮",
                            "step_type": "actorAction",
                            "actor_ids": [act_id],
                            "input_business_object_numbers": ["B-001"],
                            "output_business_object_numbers": [],
                        }
                    ],
                    "transitions": [],
                }
            ],
        }

    with patch("backend.core.generators.actors_generator.ActorsGenerator.generate", new_callable=AsyncMock) as m_actors, \
         patch("backend.core.generators.scenarios_generator.ScenariosGenerator.generate", new_callable=AsyncMock) as m_scenarios, \
         patch("backend.integration.skill_backed_services.scenario_generation_service.SkillBackedScenarioGenerationService._generate_scenario_result", new_callable=AsyncMock) as m_skill_scenarios, \
         patch("backend.core.generators.acceptance_criteria_generator.AcceptanceCriteriaGenerator.generate", new_callable=AsyncMock) as m_ac, \
         patch("backend.core.generators.flows_generator.FlowsGenerator.generate", new_callable=AsyncMock) as m_flows:
        m_actors.return_value = mock_actors_ret
        m_scenarios.return_value = mock_scenarios_ret
        m_skill_scenarios.return_value = {
            "story": {},
            "system": {},
            "gherkin": {
                "Generated feature": {
                    "Feature": "Generated feature",
                    "Scenarios": [{
                        "Scenario": mock_scenarios_ret["scenarios"][0]["scenario_name"],
                        "Given": ["The administrator is signed in"],
                        "When": ["The user list is requested"],
                        "Then": ["Registered users are shown"],
                    }],
                },
            },
        }
        m_ac.return_value = mock_ac_ret
        m_flows.side_effect = _fake_flows_generate
        yield


@pytest.fixture
async def seeded_project(db_session) -> int:
    project = ProjectModel(
        owner_user_id=1,
        name="测试项目", description="",
        user_requirements="需要一个用户管理系统，支持角色权限和内容管理。",
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)

    # Add an actor for scenario generation context
    branch = RequirementBranchModel(project_id=project.id, name="test-candidates")
    db_session.add(branch)
    await db_session.flush()
    workspace = BranchWorkspaceModel(
        project_id=project.id, branch_id=branch.id,
        user_requirements=project.user_requirements,
    )
    db_session.add(workspace)
    await db_session.flush()

    actor = ActorModel(
        project_id=project.id, workspace_id=workspace.id, name="管理员",
        description="系统管理员", confirmation_status="ai_assumption",
    )
    db_session.add(actor)
    await db_session.flush()
    await db_session.refresh(actor)

    # Add a feature for scenario generation context
    feature = FeatureModel(
        project_id=project.id, workspace_id=workspace.id, name="用户管理",
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

    return project.id, workspace.id


# ═══════════════════════════════════════════════════════════════════
# Actor Adapter Tests
# ═══════════════════════════════════════════════════════════════════

class TestActorGenerationChoiceAdapter:
    def setup_method(self):
        self.adapter = get_adapter("actor")

    @pytest.mark.asyncio
    async def test_generate_candidate_returns_valid_candidate(self, db_session, seeded_project):
        """generate_candidate should return a valid GenerationCandidate."""
        project_id, workspace_id = seeded_project
        ctx = CandidateContext(
            index=0, strategy="balanced",
            project_id=project_id, session=db_session,
                  workspace_id=workspace_id,
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
        project_id, workspace_id = seeded_project
        ctx = CandidateContext(
            index=0, strategy="balanced",
            project_id=project_id,
            target={"generation_mode": "pair", "feature_id": 1, "actor_id": 1},
            session=db_session,
                  workspace_id=workspace_id,
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
        project_id, workspace_id = seeded_project
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=project_id,
            generation_type="actor",
            candidate_count=1,
            session=db_session,
                           workspace_id=workspace_id,
        )
        assert result["status"] == "open"
        assert result["generation_type"] == "actor"

        actors = await db_session.execute(
            select(ActorModel).where(ActorModel.project_id == project_id)
        )
        # Only the seed actor should exist
        assert len(actors.scalars().all()) == 1

    @pytest.mark.asyncio
    async def test_accept_actor_choice_writes_actors_and_replaces(self, db_session, seeded_project):
        """采纳 actor choice 后应替换 ActorModel。"""
        project_id, workspace_id = seeded_project
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=project_id,
            generation_type="actor",
            candidate_count=1,
            session=db_session,
                           workspace_id=workspace_id,
        )
        choice_id = result["choices"][0]["id"]

        from backend.api.modules.decision_workflow.choice_group.application.choice_service import ChoiceService
        cs = ChoiceService()
        accept_result = await cs.accept_choice(
            project_id=project_id,
            choice_id=choice_id,
            session=db_session,
            force=True,
                                  workspace_id=workspace_id,
        )
        assert accept_result.status == "accepted"

        # Verify old actor was replaced
        actors = await db_session.execute(
            select(ActorModel).where(ActorModel.project_id == project_id)
        )
        all_actors = actors.scalars().all()
        # Old seed actor was deleted and new ones added
        assert len(all_actors) > 0
        assert all_actors[0].name != "管理员"  # old name replaced

    @pytest.mark.asyncio
    async def test_discard_actor_choice_group_does_not_write(self, db_session, seeded_project):
        """丢弃 actor choice group 后不应修改 ActorModel。"""
        project_id, workspace_id = seeded_project
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=project_id,
            generation_type="actor",
            candidate_count=1,
            session=db_session,
                           workspace_id=workspace_id,
        )
        group_id = result["id"]

        from backend.api.modules.decision_workflow.choice_group.application.choice_service import ChoiceService
        cs = ChoiceService()
        discard_result = await cs.discard_choice_group(
            project_id=project_id, group_id=group_id, session=db_session,
        )
        assert discard_result.status == "discarded"

        # Seed actor should still exist
        actors = await db_session.execute(
            select(ActorModel).where(ActorModel.project_id == project_id)
        )
        assert len(actors.scalars().all()) == 1  # only seed


# ═══════════════════════════════════════════════════════════════════
# Integration: Scenario Choice Group
# ═══════════════════════════════════════════════════════════════════

class TestScenarioChoiceGroupIntegration:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(("feature_count", "candidate_count"), [(2, 1), (5, 2)])
    async def test_batch_acceptance_preserves_selected_scope_and_gherkin(
        self, db_session, seeded_project, feature_count, candidate_count,
    ):
        from backend.api.modules.decision_workflow.choice_group.application.choice_service import ChoiceService

        project_id, workspace_id = seeded_project
        selected = [FeatureModel(
            project_id=project_id, workspace_id=workspace_id, name=f"Selected {index}", description="",
        ) for index in range(feature_count - 1)]
        unselected = FeatureModel(
            project_id=project_id, workspace_id=workspace_id, name="Unselected without actor", description="",
        )
        second_actor = ActorModel(
            project_id=project_id, workspace_id=workspace_id, name="Operator", description="",
        )
        db_session.add_all([*selected, unselected, second_actor])
        await db_session.flush()
        selected_ids = [1, *[feature.id for feature in selected]]
        expected_pairs = {(feature_id, actor_id) for feature_id in selected_ids for actor_id in [1, second_actor.id]}
        await db_session.execute(feature_actor_table.insert(), [
            {"feature_id": feature_id, "actor_id": actor_id}
            for feature_id, actor_id in sorted(expected_pairs)
            if (feature_id, actor_id) != (1, 1)
        ])
        old_selected = ScenarioModel(
            project_id=project_id, workspace_id=workspace_id, feature_id=1, actor_id=1,
            name="Old selected", content="Replace this scenario",
        )
        old_unselected = ScenarioModel(
            project_id=project_id, workspace_id=workspace_id, feature_id=unselected.id, actor_id=1,
            name="Old unselected", content="Keep this scenario",
        )
        db_session.add_all([old_selected, old_unselected])
        await db_session.flush()
        old_unselected_id = old_unselected.id

        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=project_id, generation_type="scenario",
            target={"generation_mode": "batch", "feature_ids": selected_ids},
            candidate_count=candidate_count, session=db_session, workspace_id=workspace_id,
        )
        assert result["status"] == "open"
        assert result["candidate_count"] == candidate_count
        # The generator fixture returns identical candidates, which are deduplicated.
        assert result["success_count"] == len(result["choices"]) == 1
        assert result["failure_count"] == 0
        assert not (await db_session.execute(select(GherkinSpecModel))).scalars().all()
        assert len((await db_session.execute(select(ScenarioModel))).scalars().all()) == 2

        accepted = await ChoiceService().accept_choice(
            project_id=project_id, choice_id=result["choices"][0]["id"],
            session=db_session, force=True, workspace_id=workspace_id,
        )
        assert accepted.status == "accepted"
        scenarios = (await db_session.execute(select(ScenarioModel))).scalars().all()
        generated = [scenario for scenario in scenarios if scenario.feature_id in selected_ids]
        assert {(scenario.feature_id, scenario.actor_id) for scenario in generated} == expected_pairs
        assert len(generated) == len(expected_pairs)
        preserved = next(scenario for scenario in scenarios if scenario.id == old_unselected_id)
        assert preserved.content == "Keep this scenario"
        specs = {spec.id: spec for spec in (await db_session.execute(select(GherkinSpecModel))).scalars()}
        assert len(specs) == len(expected_pairs)
        criteria = (await db_session.execute(select(ScenarioAcceptanceCriterionModel))).scalars().all()
        assert {criterion.scenario_id for criterion in criteria} == {scenario.id for scenario in generated}
        for scenario in generated:
            spec = specs[scenario.gherkin_spec_id]
            assert (spec.feature_id, spec.actor_id) == (scenario.feature_id, scenario.actor_id)
            assert scenario.gherkin_scenario_index == 0
            assert spec.gherkin_json["Generated feature"]["Scenarios"][0]["Then"] == ["Registered users are shown"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("feature_ids", [[], [1, 999]])
    async def test_invalid_batch_target_fails_before_model_call(self, db_session, seeded_project, feature_ids):
        project_id, workspace_id = seeded_project
        with patch(
            "backend.integration.skill_backed_services.scenario_generation_service."
            "SkillBackedScenarioGenerationService._generate_scenario_result",
            new_callable=AsyncMock,
        ) as generate:
            result = await GenerationChoiceService().create_choice_group(
                project_id=project_id, generation_type="scenario",
                target={"generation_mode": "batch", "feature_ids": feature_ids},
                candidate_count=1, session=db_session, workspace_id=workspace_id,
            )
        generate.assert_not_awaited()
        assert result["status"] == "failed"
        assert result["status_detail"]["errors"][0]["error_type"] == "validation_error"
        assert not (await db_session.execute(select(ScenarioModel))).scalars().all()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("scenarios", "message"), [
        ([{"Scenario": "Missing criteria"}], "empty_acceptance_criteria"),
        ([{"Scenario": "Valid", "Then": "Done"}, "Invalid scenario"], "invalid_scenario_payload"),
    ])
    async def test_invalid_skill_result_never_becomes_a_successful_candidate(
        self, db_session, seeded_project, scenarios, message,
    ):
        project_id, workspace_id = seeded_project
        with patch(
            "backend.integration.skill_backed_services.scenario_generation_service."
            "SkillBackedScenarioGenerationService._generate_scenario_result",
            new_callable=AsyncMock,
            return_value={"gherkin": {"Feature": {"Scenarios": scenarios}}},
        ):
            result = await GenerationChoiceService().create_choice_group(
                project_id=project_id, generation_type="scenario",
                target={"generation_mode": "batch", "feature_ids": [1]},
                candidate_count=1, session=db_session, workspace_id=workspace_id,
            )
        assert result["status"] == "failed"
        error = result["status_detail"]["errors"][0]
        assert error["error_type"] == "validation_error"
        assert error["message"] == message
        assert "feature_id=1 actor_id=1" in error["detail"]
        assert not (await db_session.execute(select(ScenarioModel))).scalars().all()
        assert not (await db_session.execute(select(GherkinSpecModel))).scalars().all()

    @pytest.mark.asyncio
    async def test_create_scenario_choice_group_does_not_write_scenarios(
        self, db_session, seeded_project
    ):
        """创建 scenario choice group 后不应写 ScenarioModel。"""
        project_id, workspace_id = seeded_project
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=project_id,
            generation_type="scenario",
            target={"generation_mode": "pair", "feature_id": 1, "actor_id": 1},
            candidate_count=1,
            session=db_session,
                           workspace_id=workspace_id,
        )
        assert result["status"] == "open"
        assert result["generation_type"] == "scenario"

        scenarios = await db_session.execute(
            select(ScenarioModel).where(ScenarioModel.project_id == project_id)
        )
        assert len(scenarios.scalars().all()) == 0

    @pytest.mark.asyncio
    async def test_accept_scenario_choice_writes_scenarios(self, db_session, seeded_project):
        """采纳 scenario choice 后应写 ScenarioModel 并且自动附加 AcceptanceCriterionModel。"""
        project_id, workspace_id = seeded_project
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=project_id,
            generation_type="scenario",
            target={"generation_mode": "pair", "feature_id": 1, "actor_id": 1},
            candidate_count=1,
            session=db_session,
                           workspace_id=workspace_id,
        )
        choice_id = result["choices"][0]["id"]

        from backend.api.modules.decision_workflow.choice_group.application.choice_service import ChoiceService
        cs = ChoiceService()
        accept_result = await cs.accept_choice(
            project_id=project_id,
            choice_id=choice_id,
            session=db_session,
            force=True,
                                  workspace_id=workspace_id,
        )
        assert accept_result.status == "accepted"

        scenarios = await db_session.execute(
            select(ScenarioModel).where(ScenarioModel.project_id == project_id)
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
        project_id, workspace_id = seeded_project
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=project_id,
            generation_type="scenario",
            target={"generation_mode": "pair", "feature_id": 1, "actor_id": 1},
            candidate_count=1,
            session=db_session,
                           workspace_id=workspace_id,
        )
        group_id = result["id"]

        from backend.api.modules.decision_workflow.choice_group.application.choice_service import ChoiceService
        cs = ChoiceService()
        discard_result = await cs.discard_choice_group(
            project_id=project_id, group_id=group_id, session=db_session,
        )
        assert discard_result.status == "discarded"

        scenarios = await db_session.execute(
            select(ScenarioModel).where(ScenarioModel.project_id == project_id)
        )
        assert len(scenarios.scalars().all()) == 0


# ═══════════════════════════════════════════════════════════════════
# Stale Detection
# ═══════════════════════════════════════════════════════════════════

class TestScenarioStaleDetection:
    @pytest.mark.asyncio
    async def test_scenario_stale_when_feature_deleted(self, db_session, seeded_project):
        """当 feature 被删除后，采纳 scenario choice 应返回 stale。"""
        project_id, workspace_id = seeded_project
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=project_id,
            generation_type="scenario",
            target={"generation_mode": "pair", "feature_id": 1, "actor_id": 1},
            candidate_count=1,
            session=db_session,
                           workspace_id=workspace_id,
        )
        choice_id = result["choices"][0]["id"]

        # Delete the feature
        feature = await db_session.get(FeatureModel, 1)
        if feature:
            await db_session.delete(feature)
            await db_session.flush()

        from backend.api.modules.decision_workflow.choice_group.application.choice_service import ChoiceService
        cs = ChoiceService()
        accept_result = await cs.accept_choice(
            project_id=project_id,
            choice_id=choice_id,
            session=db_session,
                                  workspace_id=workspace_id,
        )
        assert accept_result.is_stale is True
        assert accept_result.stale_reason is not None
        assert "删除" in accept_result.stale_reason or "适用" in accept_result.stale_reason

    @pytest.mark.asyncio
    async def test_force_accept_skips_stale_for_scenario(self, db_session, seeded_project):
        """force=True 应跳过 stale 校验，is_context_stale 不被调用。"""
        project_id, workspace_id = seeded_project
        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=project_id,
            generation_type="scenario",
            target={"generation_mode": "pair", "feature_id": 1, "actor_id": 1},
            candidate_count=1,
            session=db_session,
                           workspace_id=workspace_id,
        )
        choice_id = result["choices"][0]["id"]

        from backend.api.modules.decision_workflow.choice_group.application.choice_service import ChoiceService
        cs = ChoiceService()
        # force=True 且 feature 存在 → 正常采纳
        accept_result = await cs.accept_choice(
            project_id=project_id,
            choice_id=choice_id,
            session=db_session,
            force=True,
                                  workspace_id=workspace_id,
        )
        assert accept_result.status == "accepted"
        # is_stale 应为 False（未检查 stale，因为 force=True）
        assert accept_result.is_stale is False


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _make_actor_candidate(names: list[str]):
    """Create a GenerationCandidate with given actor names."""
    from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
        GenerationCandidate,
    )
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
    from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
        GenerationCandidate,
    )
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


# ═══════════════════════════════════════════════════════════════════
# Integration: Flow Choice Group
# ═══════════════════════════════════════════════════════════════════

class TestFlowChoiceGroupIntegration:
    @pytest.mark.asyncio
    async def test_create_and_accept_flow_choice_group(self, db_session, seeded_project):
        """创建 flow choice group 并采纳，验证 flow + business_objects 正常持久化且正确绑定 workspace_id。"""
        project_id, _ = seeded_project
        branch = RequirementBranchModel(
            project_id=project_id,
            name="feature/flow-test",
            created_by_user_id=1,
            head_commit_id=None,
        )
        db_session.add(branch)
        await db_session.flush()

        workspace = BranchWorkspaceModel(
            project_id=project_id,
            branch_id=branch.id,
            user_requirements="",
        )
        db_session.add(workspace)
        await db_session.flush()

        from backend.database.model import DomainRuleModel

        rule = DomainRuleModel(
            project_id=project_id,
            workspace_id=workspace.id,
            title="Flow generation prerequisite",
            statement="The generated flow must follow this rule.",
        )
        actor_branch = ActorModel(
            project_id=project_id,
            workspace_id=workspace.id,
            name="管理员",
            description="系统管理员",
            confirmation_status="ai_assumption",
        )
        feature_branch = FeatureModel(
            project_id=project_id,
            workspace_id=workspace.id,
            name="用户管理",
            description="管理用户",
            confirmation_status="ai_assumption",
        )
        db_session.add_all([rule, actor_branch, feature_branch])
        await db_session.flush()

        service = GenerationChoiceService()
        result = await service.create_choice_group(
            project_id=project_id,
            generation_type="flow",
            candidate_count=1,
            session=db_session,
            workspace_id=workspace.id,
        )
        assert result["generation_type"] == "flow"
        assert len(result["choices"]) == 1
        print("CHOICE IN TEST:", result["choices"][0])
        choice_id = result["choices"][0]["id"]

        from backend.api.modules.decision_workflow.choice_group.application.choice_service import ChoiceService
        cs = ChoiceService()
        accept_result = await cs.accept_choice(
            project_id=project_id,
            choice_id=choice_id,
            session=db_session,
            force=True,
            workspace_id=workspace.id,
        )
        assert accept_result.status == "accepted"

        flows = await db_session.execute(
            select(FlowModel).where(
                FlowModel.project_id == project_id,
                FlowModel.workspace_id == workspace.id,
            )
        )
        flows_list = flows.scalars().all()
        assert len(flows_list) == 1
        assert flows_list[0].name == "结账流程"
        assert flows_list[0].workspace_id == workspace.id

        bos = await db_session.execute(
            select(BusinessObjectModel).where(
                BusinessObjectModel.project_id == project_id,
                BusinessObjectModel.workspace_id == workspace.id,
            )
        )
        bos_list = bos.scalars().all()
        assert len(bos_list) == 1
        assert bos_list[0].name == "Cart"
        assert bos_list[0].workspace_id == workspace.id
