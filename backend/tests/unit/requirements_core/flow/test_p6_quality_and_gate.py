"""Unit tests for Phase P6 quality issue detection, finding policies, and criteria."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.detectors import HowIssueDetector
from backend.core.findings.how_finding_policy import HowFindingPolicy
from backend.core.stage_gates.stage_gate_context import (
    load_how_gate_context,
    load_scoped_feature_ids,
    load_what_gate_context,
)
from backend.core.stage_gates.stage_gate_criteria import evaluate_how_gate
from backend.database.model import (
    ActorModel,
    Base,
    BranchWorkspaceModel,
    BusinessObjectModel,
    ConfirmationStatus,
    DomainRuleModel,
    FeatureModel,
    FlowModel,
    FlowStepModel,
    FlowTransitionModel,
    ProjectModel,
    RequirementBranchModel,
    RuleLinkModel,
    RuleOrigin,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    ScopeModel,
    feature_actor_table,
)
from backend.schemas import BlockingScope, FindingType, IssueSeverity


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


async def _setup_minimal_what(session: AsyncSession, project_id: int, workspace_id: int):
    actor = ActorModel(project_id=project_id, name="User", description="Normal user", workspace_id=workspace_id)
    feature = FeatureModel(project_id=project_id, name="Login", description="User login", workspace_id=workspace_id)
    session.add_all([actor, feature])
    await session.flush()

    await session.execute(
        feature_actor_table.insert().values(feature_id=feature.id, actor_id=actor.id)
    )
    scenario = ScenarioModel(
        project_id=project_id,
        feature_id=feature.id,
        actor_id=actor.id,
        name="User logs in",
        content="Given user credentials, when submitted, then login succeeds",
                   workspace_id=workspace_id,
    )
    session.add(scenario)
    await session.flush()

    ac = ScenarioAcceptanceCriterionModel(
        scenario_id=scenario.id,
        position=1,
        content="User sees dashboard",
             workspace_id=workspace_id,
    )
    session.add(ac)
    await session.flush()
    return actor, feature, scenario


@pytest.mark.asyncio
async def test_domain_rule_required_detected_when_flows_exist(db_session):
    project = ProjectModel(owner_user_id=1, name="P6 Test", user_requirements="Reqs")
    db_session.add(project)
    await db_session.flush()
    branch = RequirementBranchModel(project_id=project.id, name="test-quality")
    db_session.add(branch)
    await db_session.flush()
    workspace = BranchWorkspaceModel(project_id=project.id, branch_id=branch.id,
                                     user_requirements=project.user_requirements)
    db_session.add(workspace)
    await db_session.flush()
    workspace_id = workspace.id
    await _setup_minimal_what(db_session, project.id, workspace_id=workspace_id)

    flow = FlowModel(project_id=project.id, name="Checkout flow", description="Desc", workspace_id=workspace_id)
    db_session.add(flow)
    await db_session.flush()

    detector = HowIssueDetector()
    issues = await detector.detect(project.id, db_session, workspace_id=workspace_id)
    codes = {i.code for i in issues}

    assert "DOMAIN_RULE_REQUIRED" in codes
    issue = next(i for i in issues if i.code == "DOMAIN_RULE_REQUIRED")
    assert issue.severity == IssueSeverity.BLOCKING


@pytest.mark.asyncio
async def test_rule_quality_checks_and_flow_rule_usage(db_session):
    project = ProjectModel(owner_user_id=1, name="P6 Test", user_requirements="Reqs")
    db_session.add(project)
    await db_session.flush()
    branch = RequirementBranchModel(project_id=project.id, name="test-quality")
    db_session.add(branch)
    await db_session.flush()
    workspace = BranchWorkspaceModel(project_id=project.id, branch_id=branch.id,
                                     user_requirements=project.user_requirements)
    db_session.add(workspace)
    await db_session.flush()
    workspace_id = workspace.id
    await _setup_minimal_what(db_session, project.id, workspace_id=workspace_id)

    # 1. AI assumption rule without source
    unlinked_ai_rule = DomainRuleModel(
        project_id=project.id,
        title="Payment limit",
        statement="Amount <= 1000",
        origin=RuleOrigin.AI_GENERATED.value,
        confirmation_status=ConfirmationStatus.NEEDS_CONFIRMATION.value,
                           workspace_id=workspace_id,
    )
    db_session.add(unlinked_ai_rule)

    # 2. Confirmed flow referencing unconfirmed rule
    flow = FlowModel(
        project_id=project.id,
        name="Payment flow",
        description="Process payment",
        confirmation_status=ConfirmationStatus.CONFIRMED.value,
               workspace_id=workspace_id,
    )
    db_session.add(flow)
    await db_session.flush()

    step = FlowStepModel(
        flow_id=flow.id,
        position=1,
        name="Submit payment",
        step_type="systemAction",
               workspace_id=workspace_id,
    )
    db_session.add(step)
    await db_session.flush()

    # Link flow to the unconfirmed rule
    link = RuleLinkModel(
        project_id=project.id,
        rule_id=unlinked_ai_rule.id,
        target_kind="flow",
        target_logical_uuid=flow.logical_uuid,
               workspace_id=workspace_id,
    )
    db_session.add(link)
    await db_session.flush()

    detector = HowIssueDetector()
    issues = await detector.detect(project.id, db_session, workspace_id=workspace_id)
    codes = {i.code for i in issues}

    assert "RULE_WITHOUT_SOURCE" in codes
    assert "FLOW_USES_UNCONFIRMED_RULE" in codes


@pytest.mark.asyncio
async def test_branch_explanation_issues_on_confirmed_flow(db_session):
    project = ProjectModel(owner_user_id=1, name="P6 Test", user_requirements="Reqs")
    db_session.add(project)
    await db_session.flush()
    branch = RequirementBranchModel(project_id=project.id, name="test-quality")
    db_session.add(branch)
    await db_session.flush()
    workspace = BranchWorkspaceModel(project_id=project.id, branch_id=branch.id,
                                     user_requirements=project.user_requirements)
    db_session.add(workspace)
    await db_session.flush()
    workspace_id = workspace.id

    flow = FlowModel(
        project_id=project.id,
        name="Approval Flow",
        description="Manager approval",
        confirmation_status=ConfirmationStatus.CONFIRMED.value,
               workspace_id=workspace_id,
    )
    db_session.add(flow)
    await db_session.flush()

    s1 = FlowStepModel(flow_id=flow.id, position=1, name="Check Status", step_type="judgment", workspace_id=workspace_id)
    s2 = FlowStepModel(flow_id=flow.id, position=2, name="Approve", step_type="systemAction", workspace_id=workspace_id)
    s3 = FlowStepModel(flow_id=flow.id, position=3, name="Reject", step_type="systemAction", workspace_id=workspace_id)
    db_session.add_all([s1, s2, s3])
    await db_session.flush()

    # Two transitions without explanation (no label, no condition)
    t1 = FlowTransitionModel(
        project_id=project.id,
        flow_id=flow.id,
        source_step_id=s1.id,
        target_step_id=s2.id,
        position=0,
        label="",
        condition_text="",
             workspace_id=workspace_id,
    )
    t2 = FlowTransitionModel(
        project_id=project.id,
        flow_id=flow.id,
        source_step_id=s1.id,
        target_step_id=s3.id,
        position=1,
        label="",
        condition_text="",
             workspace_id=workspace_id,
    )
    db_session.add_all([t1, t2])
    await db_session.flush()

    detector = HowIssueDetector()
    issues = await detector.detect(project.id, db_session, workspace_id=workspace_id)
    codes = {i.code for i in issues}

    assert "BRANCH_WITHOUT_EXPLANATION" in codes
    assert "BRANCH_WITHOUT_DEFAULT" in codes


@pytest.mark.asyncio
async def test_business_object_without_attributes_is_info_and_non_blocking(db_session):
    project = ProjectModel(owner_user_id=1, name="P6 Test", user_requirements="Reqs")
    db_session.add(project)
    await db_session.flush()
    branch = RequirementBranchModel(project_id=project.id, name="test-quality")
    db_session.add(branch)
    await db_session.flush()
    workspace = BranchWorkspaceModel(project_id=project.id, branch_id=branch.id,
                                     user_requirements=project.user_requirements)
    db_session.add(workspace)
    await db_session.flush()
    workspace_id = workspace.id

    bo = BusinessObjectModel(project_id=project.id, name="Account", description="User Account", workspace_id=workspace_id)
    db_session.add(bo)
    await db_session.flush()

    detector = HowIssueDetector()
    issues = await detector.detect(project.id, db_session, workspace_id=workspace_id)
    bo_issue = next((i for i in issues if i.code == "BUSINESS_OBJECT_WITHOUT_ATTRIBUTES"), None)

    assert bo_issue is not None
    assert bo_issue.severity == IssueSeverity.INFO

    policy = HowFindingPolicy()
    findings = await policy.get_findings(project.id, db_session, workspace_id=workspace_id)
    bo_finding = next((f for f in findings if f.code == "BUSINESS_OBJECT_WITHOUT_ATTRIBUTES"), None)

    assert bo_finding is not None
    assert bo_finding.type == FindingType.QUALITY_HINT
    assert bo_finding.blockingScope == BlockingScope.NONE


@pytest.mark.asyncio
async def test_transition_explained_by_applies_to_rule_avoids_branch_issue(db_session):
    """Verify that linking an applies_to domain rule explains a branch transition."""
    project = ProjectModel(owner_user_id=1, name="P6 Branch Test", user_requirements="Reqs")
    db_session.add(project)
    await db_session.flush()
    branch = RequirementBranchModel(project_id=project.id, name="test-quality")
    db_session.add(branch)
    await db_session.flush()
    workspace = BranchWorkspaceModel(project_id=project.id, branch_id=branch.id,
                                     user_requirements=project.user_requirements)
    db_session.add(workspace)
    await db_session.flush()
    workspace_id = workspace.id

    flow = FlowModel(
        project_id=project.id,
        name="Order Flow",
        description="Flow",
        confirmation_status="confirmed",
               workspace_id=workspace_id,
    )
    db_session.add(flow)
    await db_session.flush()

    s1 = FlowStepModel(flow_id=flow.id, position=1, name="Evaluate Order", step_type="judgment", workspace_id=workspace_id)
    s2 = FlowStepModel(flow_id=flow.id, position=2, name="Approve", step_type="systemAction", workspace_id=workspace_id)
    s3 = FlowStepModel(flow_id=flow.id, position=3, name="Reject", step_type="systemAction", workspace_id=workspace_id)
    db_session.add_all([s1, s2, s3])
    await db_session.flush()

    t1 = FlowTransitionModel(
        project_id=project.id,
        flow_id=flow.id,
        source_step_id=s1.id,
        target_step_id=s2.id,
        position=0,
        is_default=True,
        label="Approved",
        condition_text="amount < 1000",
             workspace_id=workspace_id,
    )
    t2 = FlowTransitionModel(
        project_id=project.id,
        flow_id=flow.id,
        source_step_id=s1.id,
        target_step_id=s3.id,
        position=1,
        is_default=False,
        label="",
        condition_text="",
             workspace_id=workspace_id,
    )
    db_session.add_all([t1, t2])
    await db_session.flush()

    rule = DomainRuleModel(
        project_id=project.id,
        title="High Value Approval Rule",
        statement="Orders over 1000 require manual review",
        origin=RuleOrigin.MANUAL.value,
        confirmation_status=ConfirmationStatus.CONFIRMED.value,
               workspace_id=workspace_id,
    )
    db_session.add(rule)
    await db_session.flush()

    link = RuleLinkModel(
        project_id=project.id,
        rule_id=rule.id,
        target_kind="flow_transition",
        target_logical_uuid=t2.logical_uuid,
        link_purpose="applies_to",
               workspace_id=workspace_id,
    )
    db_session.add(link)
    await db_session.flush()

    detector = HowIssueDetector()
    issues = await detector.detect(project.id, db_session, workspace_id=workspace_id)
    branch_unexplained = [i for i in issues if i.code == "BRANCH_WITHOUT_EXPLANATION"]
    assert len(branch_unexplained) == 0


@pytest.mark.asyncio
async def test_rule_source_link_does_not_trigger_flow_unconfirmed_rule(db_session):
    """Verify that source traceability links do not trigger FLOW_USES_UNCONFIRMED_RULE."""
    project = ProjectModel(owner_user_id=1, name="P6 Source Link Test", user_requirements="Reqs")
    db_session.add(project)
    await db_session.flush()
    branch = RequirementBranchModel(project_id=project.id, name="test-quality")
    db_session.add(branch)
    await db_session.flush()
    workspace = BranchWorkspaceModel(project_id=project.id, branch_id=branch.id,
                                     user_requirements=project.user_requirements)
    db_session.add(workspace)
    await db_session.flush()
    workspace_id = workspace.id

    flow = FlowModel(
        project_id=project.id,
        name="Confirmed Flow",
        description="Flow",
        confirmation_status="confirmed",
               workspace_id=workspace_id,
    )
    db_session.add(flow)
    await db_session.flush()

    step = FlowStepModel(flow_id=flow.id, position=1, name="Initial Step", step_type="userAction", workspace_id=workspace_id)
    db_session.add(step)
    await db_session.flush()

    unconfirmed_rule = DomainRuleModel(
        project_id=project.id,
        title="Extracted Rule",
        statement="Rule statement",
        origin=RuleOrigin.FLOW_REFINEMENT.value,
        confirmation_status=ConfirmationStatus.NEEDS_CONFIRMATION.value,
                           workspace_id=workspace_id,
    )
    db_session.add(unconfirmed_rule)
    await db_session.flush()

    source_link = RuleLinkModel(
        project_id=project.id,
        rule_id=unconfirmed_rule.id,
        target_kind="flow_step",
        target_logical_uuid=step.logical_uuid,
        link_purpose="source",
                      workspace_id=workspace_id,
    )
    db_session.add(source_link)
    await db_session.flush()

    detector = HowIssueDetector()
    issues = await detector.detect(project.id, db_session, workspace_id=workspace_id)
    uses_unconfirmed = [i for i in issues if i.code == "FLOW_USES_UNCONFIRMED_RULE"]
    assert len(uses_unconfirmed) == 0


@pytest.mark.asyncio
async def test_workspace_isolation_empty_branch_returns_zero_items(db_session):
    """Verify that querying an empty branch workspace does not fall back to main workspace."""
    project = ProjectModel(owner_user_id=1, name="P6 Isolation Test", user_requirements="Reqs")
    db_session.add(project)
    await db_session.flush()

    main_flow = FlowModel(
        project_id=project.id,
        workspace_id=None,
        name="Main Workspace Flow",
        description="Desc",
    )
    db_session.add(main_flow)
    await db_session.flush()

    how_context = await load_how_gate_context(project.id, db_session, workspace_id=999)
    assert len(how_context.flow_ids) == 0
    assert len(how_context.steps) == 0
    assert len(how_context.domain_rules) == 0


@pytest.mark.asyncio
async def test_open_panel_solver_handles_all_p6_codes(db_session):
    """Verify that all 11 new HOW finding codes resolve cleanly without error."""
    from backend.core.issue_resolution.open_panel_solver import OpenPanelIssueSolver
    from backend.schemas import IssueTarget

    solver = OpenPanelIssueSolver()
    p6_codes = [
        "DOMAIN_RULE_REQUIRED",
        "RULE_WITHOUT_SOURCE",
        "RULE_NOT_APPLIED",
        "FLOW_USES_UNCONFIRMED_RULE",
        "FLOW_ENTRY_AMBIGUOUS",
        "FLOW_WITHOUT_ENTRY",
        "BRANCH_WITHOUT_EXPLANATION",
        "BRANCH_WITHOUT_DEFAULT",
        "TRANSITION_RULE_STALE",
        "FLOW_PATH_TRUNCATED",
    ]

    target = IssueTarget(targetType="flow", targetId=1)
    for code in p6_codes:
        res = await solver.resolve(
            project_id=1,
            issue_code=code,
            target=target,
            metadata={"flow_id": 1},
            session=db_session,
        )
        assert res.issueCode == code
        assert res.resolutionType == "open_panel"
        assert res.action is not None


@pytest.mark.asyncio
async def test_business_object_and_scope_workspace_isolation(db_session):
    """Verify that BO and Scope data are strictly isolated between main and branch workspaces."""
    project = ProjectModel(owner_user_id=1, name="BO Scope Isolation Project", user_requirements="Reqs")
    db_session.add(project)
    await db_session.flush()

    branch = RequirementBranchModel(
        project_id=project.id,
        name="feature-branch",
    )
    db_session.add(branch)
    await db_session.flush()

    branch_workspace = BranchWorkspaceModel(
        project_id=project.id,
        branch_id=branch.id,
    )
    db_session.add(branch_workspace)
    await db_session.flush()

    # Main BO
    main_bo = BusinessObjectModel(
        project_id=project.id,
        workspace_id=None,
        name="MainOrder",
        description="Main BO",
    )
    # Branch BO
    branch_bo = BusinessObjectModel(
        project_id=project.id,
        workspace_id=branch_workspace.id,
        name="BranchOrder",
        description="Branch BO",
    )
    db_session.add_all([main_bo, branch_bo])
    await db_session.flush()

    main_how_ctx = await load_how_gate_context(project.id, db_session, workspace_id=None)
    assert main_bo.id in main_how_ctx.business_object_ids
    assert branch_bo.id not in main_how_ctx.business_object_ids

    branch_how_ctx = await load_how_gate_context(project.id, db_session, workspace_id=branch_workspace.id)
    assert branch_bo.id in branch_how_ctx.business_object_ids
    assert main_bo.id not in branch_how_ctx.business_object_ids

    # Features and scopes
    main_feat = FeatureModel(
        project_id=project.id,
        workspace_id=None,
        name="MainFeature",
        description="Main Feature",
    )
    branch_feat = FeatureModel(
        project_id=project.id,
        workspace_id=branch_workspace.id,
        name="BranchFeature",
        description="Branch Feature",
    )
    db_session.add_all([main_feat, branch_feat])
    await db_session.flush()

    main_scope = ScopeModel(
        feature_id=main_feat.id,
        workspace_id=None,
        status="in_scope",
        reason="Included in core",
    )
    branch_scope = ScopeModel(
        feature_id=branch_feat.id,
        workspace_id=branch_workspace.id,
        status="in_scope",
        reason="Included in branch",
    )
    db_session.add_all([main_scope, branch_scope])
    await db_session.flush()

    main_scoped_ids = await load_scoped_feature_ids(project.id, db_session, workspace_id=None)
    assert main_feat.id in main_scoped_ids
    assert branch_feat.id not in main_scoped_ids

    branch_scoped_ids = await load_scoped_feature_ids(project.id, db_session, workspace_id=branch_workspace.id)
    assert branch_feat.id in branch_scoped_ids
    assert main_feat.id not in branch_scoped_ids


def test_path_truncation_issues_propagates_exceptions_fail_closed(monkeypatch):
    """Verify that exceptions from path projection are not silently swallowed."""
    from backend.core.detectors.how.topology_checks import detect_path_truncation_issues
    from types import SimpleNamespace

    fake_flow = SimpleNamespace(
        flow_id=42,
        name="Crashing Flow",
        steps=[],
        transitions=[],
    )
    context = SimpleNamespace(flows=[fake_flow])

    def _failing_project(*args, **kwargs):
        raise RuntimeError("Projection engine failure")

    monkeypatch.setattr(
        "backend.core.detectors.how.topology_checks.project_flow_paths",
        _failing_project,
    )

    with pytest.raises(RuntimeError, match="Projection engine failure"):
        detect_path_truncation_issues(context)


def test_rule_link_purpose_counterexamples():
    """Verify that link_purpose strictly drives source/applied classification."""
    from backend.core.detectors.how.rule_checks import detect_rule_quality_issues
    from types import SimpleNamespace

    # Case 1: source -> flow must NOT count as applied (triggers RULE_NOT_APPLIED)
    rule1 = SimpleNamespace(
        rule_id=1,
        logical_uuid="rule-1",
        title="Rule 1",
        origin="ai_generated",
        confirmation_status="confirmed",
    )
    link1 = SimpleNamespace(
        rule_id=1,
        target_kind="flow",
        target_logical_uuid="flow-1",
        link_purpose="source",
    )
    ctx1 = SimpleNamespace(
        domain_rules=[rule1],
        rule_links=[link1],
        flows=[],
    )
    issues1 = detect_rule_quality_issues(ctx1)
    issue_codes1 = {i.code for i in issues1}
    assert "RULE_NOT_APPLIED" in issue_codes1
    assert "RULE_WITHOUT_SOURCE" not in issue_codes1

    # Case 2: applies_to -> scenario must NOT count as source (triggers RULE_WITHOUT_SOURCE for non-manual)
    rule2 = SimpleNamespace(
        rule_id=2,
        logical_uuid="rule-2",
        title="Rule 2",
        origin="ai_generated",
        confirmation_status="confirmed",
    )
    link2 = SimpleNamespace(
        rule_id=2,
        target_kind="scenario",
        target_logical_uuid="scen-1",
        link_purpose="applies_to",
    )
    ctx2 = SimpleNamespace(
        domain_rules=[rule2],
        rule_links=[link2],
        flows=[],
    )
    issues2 = detect_rule_quality_issues(ctx2)
    issue_codes2 = {i.code for i in issues2}
    assert "RULE_WITHOUT_SOURCE" in issue_codes2
    assert "RULE_NOT_APPLIED" not in issue_codes2


def test_rule_link_missing_or_invalid_purpose_fails_explicitly():
    """Verify that detect_rule_quality_issues raises ValueError when link_purpose is missing or invalid."""
    from backend.core.detectors.how.rule_checks import detect_rule_quality_issues
    from types import SimpleNamespace

    rule = SimpleNamespace(
        rule_id=1,
        logical_uuid="rule-1",
        title="Rule 1",
        origin="manual",
        confirmation_status="confirmed",
    )

    # Missing link_purpose (None)
    link_none = SimpleNamespace(
        link_id=101,
        rule_id=1,
        target_kind="flow",
        target_logical_uuid="flow-1",
        link_purpose=None,
    )
    with pytest.raises(ValueError, match="invalid_rule_link_purpose"):
        detect_rule_quality_issues(
            SimpleNamespace(domain_rules=[rule], rule_links=[link_none], flows=[])
        )

    # Missing link_purpose (empty string)
    link_empty = SimpleNamespace(
        link_id=102,
        rule_id=1,
        target_kind="flow",
        target_logical_uuid="flow-1",
        link_purpose="",
    )
    with pytest.raises(ValueError, match="invalid_rule_link_purpose"):
        detect_rule_quality_issues(
            SimpleNamespace(domain_rules=[rule], rule_links=[link_empty], flows=[])
        )

    # Invalid link_purpose (unknown value)
    link_invalid = SimpleNamespace(
        link_id=103,
        rule_id=1,
        target_kind="flow",
        target_logical_uuid="flow-1",
        link_purpose="invalid_custom_purpose",
    )
    with pytest.raises(ValueError, match="Invalid link purpose"):
        detect_rule_quality_issues(
            SimpleNamespace(domain_rules=[rule], rule_links=[link_invalid], flows=[])
        )
