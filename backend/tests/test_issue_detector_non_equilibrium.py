import pytest
from backend.api.modules.version_control.application.clean_initialization import create_initial_workspace
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.detectors import (
    HowIssueDetector,
    ScopeIssueDetector,
    WhatIssueDetector,
)
from backend.core.suggestions import (
    HowSuggestionPolicy,
    ScopeSuggestionPolicy,
    WhatSuggestionPolicy,
)
from backend.database.model import (
    ActorModel,
    Base,
    DomainRuleModel,
    FeatureModel,
    FlowModel,
    ProjectModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    feature_actor_table,
)

# ---------------------------------------------------------------------------
# Fixtures
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
async def seeded_project(db_session) -> tuple[int, int]:
    """Create a seed project and return its ID."""
    project = ProjectModel(
        owner_user_id=1,
        name="非均衡测试项目",
        description="用于测试非均衡Issue检测逻辑的项目",
        user_requirements="测试需求描述",
        kano_status="pending",
    )
    db_session.add(project)
    await db_session.flush()
    _, workspace = await db_session.run_sync(lambda s: create_initial_workspace(s, project))
    return project.id, workspace.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_what_detector_non_equilibrium_scenarios_empty(db_session, seeded_project):
    """
    When scenarios are completely empty, WhatIssueDetector should NOT report
    FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO or SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA.
    """
    # 1. Setup actor and feature with actor binding
    actor = ActorModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="管理员", description="系统管理员")
    feature = FeatureModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="系统设置", description="管理系统设置")
    db_session.add_all([actor, feature])
    await db_session.flush()

    await db_session.execute(
        feature_actor_table.insert().values(
            feature_id=feature.id,
            actor_id=actor.id
        )
    )
    await db_session.flush()

    # 2. Run detection
    detector = WhatIssueDetector()
    issues = await detector.detect(seeded_project[0], db_session, workspace_id=seeded_project[1])

    # 3. Assertions
    issue_codes = {i.code for i in issues}
    assert "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO" not in issue_codes
    assert "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA" not in issue_codes
    assert "LEAF_FEATURE_WITHOUT_ACTOR" not in issue_codes


@pytest.mark.asyncio
async def test_what_detector_non_equilibrium_scenarios_exist_but_missing(db_session, seeded_project):
    """
    When scenarios exist but some feature-actor pairs are missing scenarios,
    WhatIssueDetector should report FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO for the missing ones.
    """
    # 1. Setup 1 actor and 2 features
    actor = ActorModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="管理员", description="系统管理员")
    f1 = FeatureModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="系统设置", description="管理系统设置")
    f2 = FeatureModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="用户设置", description="管理用户设置")
    db_session.add_all([actor, f1, f2])
    await db_session.flush()

    # Bind actor to both features
    await db_session.execute(
        feature_actor_table.insert().values(
            [{"feature_id": f1.id, "actor_id": actor.id},
             {"feature_id": f2.id, "actor_id": actor.id}]
        )
    )
    await db_session.flush()

    # Create scenario for f1 only
    scenario = ScenarioModel(
        project_id=seeded_project[0], workspace_id=seeded_project[1],
        feature_id=f1.id,
        actor_id=actor.id,
        name="修改系统时区",
        content="管理员选择并修改系统时区"
    )
    db_session.add(scenario)
    await db_session.flush()

    # 2. Run detection
    detector = WhatIssueDetector()
    issues = await detector.detect(seeded_project[0], db_session, workspace_id=seeded_project[1])

    # 3. Assertions: f2-actor pair is missing scenario, f1-actor has scenario
    issue_codes = {i.code for i in issues}
    assert "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO" in issue_codes

    pair_issues = [i for i in issues if i.code == "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO"]
    assert len(pair_issues) == 1
    assert pair_issues[0].metadata["feature_id"] == f2.id
    assert pair_issues[0].metadata["actor_id"] == actor.id


@pytest.mark.asyncio
async def test_what_detector_non_equilibrium_ac_empty(db_session, seeded_project):
    """
    When scenarios exist but total AC count is 0,
    WhatIssueDetector should NOT report SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA.
    """
    actor = ActorModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="管理员", description="系统管理员")
    feature = FeatureModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="系统设置", description="管理系统设置")
    db_session.add_all([actor, feature])
    await db_session.flush()

    await db_session.execute(
        feature_actor_table.insert().values(
            feature_id=feature.id,
            actor_id=actor.id
        )
    )
    await db_session.flush()

    scenario = ScenarioModel(
        project_id=seeded_project[0], workspace_id=seeded_project[1],
        feature_id=feature.id,
        actor_id=actor.id,
        name="修改系统时区",
        content="管理员选择并修改系统时区"
    )
    db_session.add(scenario)
    await db_session.flush()

    # Run detection
    detector = WhatIssueDetector()
    issues = await detector.detect(seeded_project[0], db_session, workspace_id=seeded_project[1])

    issue_codes = {i.code for i in issues}
    assert "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA" not in issue_codes


@pytest.mark.asyncio
async def test_what_detector_non_equilibrium_ac_exist_but_missing(db_session, seeded_project):
    """
    When some scenarios have ACs and some do not,
    WhatIssueDetector should report SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA for the ones lacking.
    """
    actor = ActorModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="管理员", description="系统管理员")
    feature = FeatureModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="系统设置", description="管理系统设置")
    db_session.add_all([actor, feature])
    await db_session.flush()

    await db_session.execute(
        feature_actor_table.insert().values(
            feature_id=feature.id,
            actor_id=actor.id
        )
    )
    await db_session.flush()

    s1 = ScenarioModel(
        project_id=seeded_project[0], workspace_id=seeded_project[1],
        feature_id=feature.id,
        actor_id=actor.id,
        name="修改系统时区",
        content="管理员选择并修改系统时区"
    )
    s2 = ScenarioModel(
        project_id=seeded_project[0], workspace_id=seeded_project[1],
        feature_id=feature.id,
        actor_id=actor.id,
        name="重启系统服务",
        content="管理员重启系统后台服务"
    )
    db_session.add_all([s1, s2])
    await db_session.flush()

    # Add AC to s1 only
    ac = ScenarioAcceptanceCriterionModel(
        workspace_id=seeded_project[1],
        scenario_id=s1.id,
        content="系统显示成功修改提示且时间变更",
        position=1
    )
    db_session.add(ac)
    await db_session.flush()

    # Run detection
    detector = WhatIssueDetector()
    issues = await detector.detect(seeded_project[0], db_session, workspace_id=seeded_project[1])

    issue_codes = {i.code for i in issues}
    assert "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA" in issue_codes

    ac_issues = [i for i in issues if i.code == "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA"]
    assert len(ac_issues) == 1
    assert ac_issues[0].target.targetId == s2.id


@pytest.mark.asyncio
async def test_how_detector_does_not_require_leaf_flow_coverage(db_session, seeded_project):
    """
    A leaf feature does not need to be linked to a flow.
    """
    feature = FeatureModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="叶子功能", description="无子功能")
    flow = FlowModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="其他流程", description="不关联该功能")
    db_session.add_all([feature, flow])
    await db_session.flush()

    detector = HowIssueDetector()
    issues = await detector.detect(seeded_project[0], db_session, workspace_id=seeded_project[1])

    issue_codes = {i.code for i in issues}
    assert "LEAF_FEATURE_WITHOUT_FLOW" not in issue_codes


@pytest.mark.asyncio
async def test_how_detector_non_equilibrium_all_flows_lack_steps(db_session, seeded_project):
    """
    When all flows lack steps, HowIssueDetector should NOT report FLOW_WITHOUT_STEPS.
    """
    flow = FlowModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="空流程", description="无步骤")
    db_session.add(flow)
    await db_session.flush()

    detector = HowIssueDetector()
    issues = await detector.detect(seeded_project[0], db_session, workspace_id=seeded_project[1])

    issue_codes = {i.code for i in issues}
    assert "FLOW_WITHOUT_STEPS" not in issue_codes


@pytest.mark.asyncio
async def test_scope_detector_non_equilibrium_scopes_empty(db_session, seeded_project):
    """
    When scopes are completely empty, ScopeIssueDetector should NOT report LEAF_FEATURE_WITHOUT_SCOPE.
    """
    feature = FeatureModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="叶子功能", description="无子功能")
    db_session.add(feature)
    await db_session.flush()

    detector = ScopeIssueDetector()
    issues = await detector.detect(seeded_project[0], db_session, workspace_id=seeded_project[1])

    issue_codes = {i.code for i in issues}
    assert "LEAF_FEATURE_WITHOUT_SCOPE" not in issue_codes


@pytest.mark.asyncio
async def test_what_suggestion_policy_suggests_ac_generation(db_session, seeded_project):
    """
    When scenarios exist but total AC count is 0,
    WhatSuggestionPolicy should suggest GENERATE_ACCEPTANCE_CRITERIA.
    """
    actor = ActorModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="管理员", description="系统管理员")
    feature = FeatureModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="系统设置", description="管理系统设置")
    db_session.add_all([actor, feature])
    await db_session.flush()

    await db_session.execute(
        feature_actor_table.insert().values(
            feature_id=feature.id,
            actor_id=actor.id
        )
    )
    await db_session.flush()

    scenario = ScenarioModel(
        project_id=seeded_project[0], workspace_id=seeded_project[1],
        feature_id=feature.id,
        actor_id=actor.id,
        name="修改系统时区",
        content="管理员选择并修改系统时区"
    )
    db_session.add(scenario)
    await db_session.flush()

    policy = WhatSuggestionPolicy()
    suggestion = await policy.get_next(seeded_project[0], db_session, workspace_id=seeded_project[1])

    assert suggestion.code == "GENERATE_ACCEPTANCE_CRITERIA"
    assert suggestion.action["draft_type"] == "acceptance_criteria_generation"
    assert suggestion.action["endpoint"] == "/api/acceptance_criteria_generation_drafts/full"


@pytest.mark.asyncio
async def test_what_suggestion_policy_suggests_generate_scenarios(db_session, seeded_project):
    """
    When features and actors exist but scenarios are completely empty,
    WhatSuggestionPolicy should suggest GENERATE_SCENARIOS.
    """
    actor = ActorModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="管理员", description="系统管理员")
    feature = FeatureModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="系统设置", description="管理系统设置")
    db_session.add_all([actor, feature])
    await db_session.flush()

    await db_session.execute(
        feature_actor_table.insert().values(
            feature_id=feature.id,
            actor_id=actor.id
        )
    )
    await db_session.flush()

    policy = WhatSuggestionPolicy()
    suggestion = await policy.get_next(seeded_project[0], db_session, workspace_id=seeded_project[1])

    assert suggestion.code == "GENERATE_SCENARIOS"
    assert suggestion.action["draft_type"] == "scenario_generation"
    assert suggestion.action["endpoint"] == "/api/scenario_generation_drafts/full"


@pytest.mark.asyncio
async def test_how_suggestion_policy_suggests_generate_rules_first(db_session, seeded_project):
    """
    How starts with rule discovery before flow generation.
    """
    policy = HowSuggestionPolicy()
    suggestion = await policy.get_next(seeded_project[0], db_session, workspace_id=seeded_project[1])

    assert suggestion.code == "GENERATE_RULES"
    assert suggestion.action["draft_type"] == "rule_generation"


@pytest.mark.asyncio
async def test_how_suggestion_policy_suggests_generate_flows_with_existing_rules(db_session, seeded_project):
    db_session.add(DomainRuleModel(
        project_id=seeded_project[0], workspace_id=seeded_project[1],
        title="审批规则",
        statement="大额订单需要审批",
    ))
    await db_session.flush()

    suggestion = await HowSuggestionPolicy().get_next(seeded_project[0], db_session, workspace_id=seeded_project[1])

    assert suggestion.code == "GENERATE_FLOWS_AND_BUSINESS_OBJECTS"
    assert suggestion.action["draft_type"] == "flow_generation"


@pytest.mark.asyncio
async def test_scope_suggestion_policy_suggests_generate_scope(db_session, seeded_project):
    """
    When scopes are completely empty, ScopeSuggestionPolicy should suggest
    GENERATE_SCOPE.
    """
    policy = ScopeSuggestionPolicy()
    suggestion = await policy.get_next(seeded_project[0], db_session, workspace_id=seeded_project[1])

    assert suggestion.code == "GENERATE_SCOPE"
    assert suggestion.action["draft_type"] == "scope_generation"
    assert suggestion.action["endpoint"] == "/api/scope_generation_drafts"


@pytest.mark.asyncio
async def test_how_suggestion_policy_all_flows_lack_steps_suggests_complete_steps(db_session, seeded_project):
    """
    When flows exist but all flows lack steps, HowSuggestionPolicy should suggest
    COMPLETE_FLOW_STEPS with open_panel action instead of ENTER_SCOPE.
    (Phase 4 fix for the known non-equilibrium gap.)
    """
    # Seed a flow without steps
    flow = FlowModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="空流程", description="无步骤")
    # Also seed a business object to satisfy HowSuggestionPolicy flow generation check
    from backend.database.model import BusinessObjectModel
    bo = BusinessObjectModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="系统配置", description="配置项")
    rule = DomainRuleModel(
        project_id=seeded_project[0], workspace_id=seeded_project[1],
        title="流程规则",
        statement="流程必须包含可执行步骤",
    )
    db_session.add_all([flow, bo, rule])
    await db_session.flush()

    policy = HowSuggestionPolicy()
    suggestion = await policy.get_next(seeded_project[0], db_session, workspace_id=seeded_project[1])

    assert suggestion.code == "COMPLETE_FLOW_STEPS", (
        f"Expected COMPLETE_FLOW_STEPS, got {suggestion.code}"
    )
    assert suggestion.action["kind"] == "open_panel"
    assert suggestion.action["panel"] == "flow_editor"
    assert "flow_id" in suggestion.action.get("payload", {})
    assert suggestion.target is not None
    assert suggestion.target["type"] == "flow"
    assert suggestion.target["id"] == flow.id


@pytest.mark.asyncio
async def test_how_detector_detects_invalid_step_actor_and_business_object(db_session, seeded_project):
    """
    Test that HowIssueDetector detects steps referencing non-existent/deleted
    actors and business objects.
    """
    from backend.database.model import (
        BusinessObjectModel,
        FlowStepModel,
        flow_step_actor_table,
        flow_step_input_business_object_table,
    )

    feat = FeatureModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="核心功能", description="测试功能")
    flow = FlowModel(project_id=seeded_project[0], workspace_id=seeded_project[1], name="核心流程", description="测试流程")
    db_session.add_all([feat, flow])
    await db_session.flush()

    # Step with an invalid actor ID (9999) and invalid BO ID (8888)
    step = FlowStepModel(
        workspace_id=seeded_project[1],
        flow_id=flow.id,
        position=1,
        name="无效步骤",
        description="关联了不存在的实体",
        step_type="actorAction",
    )
    db_session.add(step)
    await db_session.flush()

    # Create Actor and BO in a different project
    other_proj = ProjectModel(owner_user_id=1, name="其他项目", user_requirements="需求")
    db_session.add(other_proj)
    await db_session.flush()

    _, other_workspace = await db_session.run_sync(lambda s: create_initial_workspace(s, other_proj))
    other_actor = ActorModel(project_id=other_proj.id, workspace_id=other_workspace.id, name="其他项目角色")
    other_bo = BusinessObjectModel(project_id=other_proj.id, workspace_id=other_workspace.id, name="其他项目对象")
    db_session.add_all([other_actor, other_bo])
    await db_session.flush()

    # Step in seeded_project associates to actor and BO belonging to other_proj
    await db_session.execute(
        flow_step_actor_table.insert().values(flow_step_id=step.id, actor_id=other_actor.id)
    )
    await db_session.execute(
        flow_step_input_business_object_table.insert().values(
            flow_step_id=step.id,
            business_object_id=other_bo.id,
        )
    )
    await db_session.flush()

    detector = HowIssueDetector()
    issues = await detector.detect(seeded_project[0], db_session, workspace_id=seeded_project[1])
    issue_codes = {issue.code for issue in issues}

    assert "INVALID_STEP_ACTOR" in issue_codes
    assert "INVALID_STEP_BUSINESS_OBJECT" in issue_codes
