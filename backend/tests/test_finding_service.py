import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text

from backend.database.model import Base, ProjectModel, ActorModel, FeatureModel, FindingOverrideModel, feature_actor_table, ScenarioModel
from backend.api.modules.diagnosis_quality.finding.application.finding_service import FindingService
from backend.schemas import FindingType, BlockingScope, IssueStage, IssueSeverity

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
        name="Finding测试项目",
        description="用于测试Finding相关的模型、策略和Service的项目",
        user_requirements="测试需求描述",
        kano_status="pending",
        unlocked_stages="what,how",
    )
    db_session.add(project)
    await db_session.flush()
    return project.id


@pytest.mark.asyncio
async def test_list_findings_invalid_parameters(db_session, seeded_project):
    service = FindingService()
    
    # Invalid stage
    with pytest.raises(ValueError, match="invalid_stage"):
        await service.list_findings(
            project_id=seeded_project,
            stage="invalid_stage",
            view="issues",
            action=None,
            session=db_session
        )
        
    # Invalid view
    with pytest.raises(ValueError, match="invalid_view"):
        await service.list_findings(
            project_id=seeded_project,
            stage="what",
            view="invalid_view",
            action=None,
            session=db_session
        )


@pytest.mark.asyncio
async def test_list_findings_issues_and_quality_hints(db_session, seeded_project):
    # Setup actors and features
    # actor1 is linked to f1 (so f1 has actor, actor1 has feature)
    # actor2 is unlinked -> triggers QUALITY_HINT (ACTOR_WITHOUT_FEATURE)
    # f2 is unlinked -> triggers ISSUE (LEAF_FEATURE_WITHOUT_ACTOR)
    actor1 = ActorModel(project_id=seeded_project, name="管理员", description="系统管理员")
    actor2 = ActorModel(project_id=seeded_project, name="访客", description="系统访客")
    f1 = FeatureModel(project_id=seeded_project, name="用户设置", description="管理用户设置")
    f2 = FeatureModel(project_id=seeded_project, name="系统设置", description="管理系统设置")
    
    db_session.add_all([actor1, actor2, f1, f2])
    await db_session.flush()

    await db_session.execute(
        feature_actor_table.insert().values(
            feature_id=f1.id,
            actor_id=actor1.id
        )
    )
    await db_session.flush()

    service = FindingService()
    
    # 1. Check issues view
    issues = await service.list_findings(
        project_id=seeded_project,
        stage="what",
        view="issues",
        action=None,
        session=db_session
    )
    # LEAF_FEATURE_WITHOUT_ACTOR should be here since it's an ISSUE type
    issue_codes = {f.code for f in issues}
    assert "LEAF_FEATURE_WITHOUT_ACTOR" in issue_codes
    assert "ACTOR_WITHOUT_FEATURE" not in issue_codes
    for f in issues:
        assert f.type == FindingType.ISSUE
        
    # 2. Check health view
    health_findings = await service.list_findings(
        project_id=seeded_project,
        stage="what",
        view="health",
        action=None,
        session=db_session
    )
    # ACTOR_WITHOUT_FEATURE should be here since it's a QUALITY_HINT type
    health_codes = {f.code for f in health_findings}
    assert "ACTOR_WITHOUT_FEATURE" in health_codes
    assert "LEAF_FEATURE_WITHOUT_ACTOR" not in health_codes
    for f in health_findings:
        assert f.type == FindingType.QUALITY_HINT


@pytest.mark.asyncio
async def test_list_findings_gate_filtering(db_session, seeded_project):
    # Setup actors and features
    # actor1 is linked to f1 (so f1 has actor, actor1 has feature)
    # f2 is unlinked -> triggers ISSUE (LEAF_FEATURE_WITHOUT_ACTOR) which is a transition blocker
    actor1 = ActorModel(project_id=seeded_project, name="管理员", description="系统管理员")
    f1 = FeatureModel(project_id=seeded_project, name="用户设置", description="管理用户设置")
    f2 = FeatureModel(project_id=seeded_project, name="系统设置", description="管理系统设置")
    
    db_session.add_all([actor1, f1, f2])
    await db_session.flush()

    await db_session.execute(
        feature_actor_table.insert().values(
            feature_id=f1.id,
            actor_id=actor1.id
        )
    )
    await db_session.flush()

    service = FindingService()
    
    # Get all gate findings
    gates = await service.list_findings(
        project_id=seeded_project,
        stage="what",
        view="gate",
        action=None,
        session=db_session
    )
    # Since it's a stage transition blocker (blockingScope=STAGE_TRANSITION), it should show up.
    gate_codes = {f.code for f in gates}
    assert "LEAF_FEATURE_WITHOUT_ACTOR" in gate_codes
    
    # Filter gates by enter_how action
    enter_how_gates = await service.list_findings(
        project_id=seeded_project,
        stage="what",
        view="gate",
        action="enter_how",
        session=db_session
    )
    assert len(enter_how_gates) > 0
    assert any(g.code == "LEAF_FEATURE_WITHOUT_ACTOR" for g in enter_how_gates)

    # Filter gates by enter_scope action (for what stage transition, should not block enter_scope)
    enter_scope_gates = await service.list_findings(
        project_id=seeded_project,
        stage="what",
        view="gate",
        action="enter_scope",
        session=db_session
    )
    assert len(enter_scope_gates) == 0


@pytest.mark.asyncio
async def test_set_finding_status_and_overrides(db_session, seeded_project):
    # Setup actors and features
    # actor1 is linked to f1 (so f1 has actor, actor1 has feature)
    # f2 is unlinked -> triggers ISSUE (LEAF_FEATURE_WITHOUT_ACTOR)
    actor1 = ActorModel(project_id=seeded_project, name="管理员", description="系统管理员")
    f1 = FeatureModel(project_id=seeded_project, name="用户设置", description="管理用户设置")
    f2 = FeatureModel(project_id=seeded_project, name="系统设置", description="管理系统设置")
    
    db_session.add_all([actor1, f1, f2])
    await db_session.flush()

    await db_session.execute(
        feature_actor_table.insert().values(
            feature_id=f1.id,
            actor_id=actor1.id
        )
    )
    await db_session.flush()

    service = FindingService()
    
    # List issues to find the findingId
    issues = await service.list_findings(
        project_id=seeded_project,
        stage="what",
        view="issues",
        action=None,
        session=db_session
    )
    assert len(issues) > 0
    finding = issues[0]
    finding_id = finding.findingId
    
    # Override status to "ignored"
    res = await service.set_finding_status(
        project_id=seeded_project,
        finding_id=finding_id,
        status="ignored",
        session=db_session
    )
    assert res["status"] == "ignored"
    assert res["finding_id"] == finding_id
    
    # Verify it is stored in database
    override_res = await db_session.execute(
        select(FindingOverrideModel).where(
            FindingOverrideModel.project_id == seeded_project,
            FindingOverrideModel.finding_id == finding_id
        )
    )
    override = override_res.scalar_one_or_none()
    assert override is not None
    assert override.status == "ignored"
    assert override.finding_type == FindingType.ISSUE.value
    
    # List findings again, should not return the ignored finding
    issues_after = await service.list_findings(
        project_id=seeded_project,
        stage="what",
        view="issues",
        action=None,
        session=db_session
    )
    assert finding_id not in {f.findingId for f in issues_after}
    
    # Reset status to "open"
    res = await service.set_finding_status(
        project_id=seeded_project,
        finding_id=finding_id,
        status="open",
        session=db_session
    )
    assert res["status"] == "open"
    
    # Verify database record is deleted
    override_res_after = await db_session.execute(
        select(FindingOverrideModel).where(
            FindingOverrideModel.project_id == seeded_project,
            FindingOverrideModel.finding_id == finding_id
        )
    )
    assert override_res_after.scalar_one_or_none() is None
    
    # List findings again, should return the finding now
    issues_final = await service.list_findings(
        project_id=seeded_project,
        stage="what",
        view="issues",
        action=None,
        session=db_session
    )
    assert finding_id in {f.findingId for f in issues_final}


@pytest.mark.asyncio
async def test_aggregate_finding_id_stability(db_session, seeded_project):
    # Setup actors and features to trigger FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO (which will trigger aggregate gate finding)
    actor1 = ActorModel(project_id=seeded_project, name="管理员", description="系统管理员")
    actor2 = ActorModel(project_id=seeded_project, name="访客", description="系统访客")
    f1 = FeatureModel(project_id=seeded_project, name="用户设置", description="管理用户设置")
    f2 = FeatureModel(project_id=seeded_project, name="系统设置", description="管理系统设置")
    
    db_session.add_all([actor1, actor2, f1, f2])
    await db_session.flush()

    await db_session.execute(
        feature_actor_table.insert().values(
            feature_id=f1.id,
            actor_id=actor1.id
        )
    )
    await db_session.execute(
        feature_actor_table.insert().values(
            feature_id=f2.id,
            actor_id=actor2.id
        )
    )
    await db_session.flush()

    # Seed at least one scenario for f1 to satisfy non-equilibrium (len(scenarios) > 0)
    scenario = ScenarioModel(
        project_id=seeded_project,
        feature_id=f1.id,
        actor_id=actor1.id,
        name="修改用户密码",
        content="管理员修改用户密码并且保存"
    )
    db_session.add(scenario)
    await db_session.flush()

    service = FindingService()
    
    # Get gate findings
    gates = await service.list_findings(
        project_id=seeded_project,
        stage="what",
        view="gate",
        action=None,
        session=db_session
    )
    
    aggregate_findings = [g for g in gates if g.code == "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO"]
    assert len(aggregate_findings) == 1
    f_aggregate = aggregate_findings[0]
    assert f_aggregate.findingId == "what:FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO:aggregate"
    
    # Check that there is 1 missing pair in metadata (since f1 is covered by the seeded scenario)
    assert len(f_aggregate.metadata["missing_pairs"]) == 1
    
    # Now add another actor and feature and link them -> metadata changes (size becomes 2)
    actor3 = ActorModel(project_id=seeded_project, name="开发者", description="开发者")
    f3 = FeatureModel(project_id=seeded_project, name="代码管理", description="管理代码")
    db_session.add_all([actor3, f3])
    await db_session.flush()
    
    await db_session.execute(
        feature_actor_table.insert().values(
            feature_id=f3.id,
            actor_id=actor3.id
        )
    )
    await db_session.flush()
    
    # Get gate findings again
    gates_after = await service.list_findings(
        project_id=seeded_project,
        stage="what",
        view="gate",
        action=None,
        session=db_session
    )
    aggregate_findings_after = [g for g in gates_after if g.code == "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO"]
    assert len(aggregate_findings_after) == 1
    f_aggregate_after = aggregate_findings_after[0]
    
    # Finding ID must stay EXACTLY the same to preserve user overrides
    assert f_aggregate_after.findingId == "what:FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO:aggregate"
    # Metadata has updated to 2 missing pairs
    assert len(f_aggregate_after.metadata["missing_pairs"]) == 2


@pytest.mark.asyncio
async def test_data_migration_override_copy(db_session, seeded_project):
    # Setup some structure to trigger an issue
    actor1 = ActorModel(project_id=seeded_project, name="管理员", description="系统管理员")
    f1 = FeatureModel(project_id=seeded_project, name="用户设置", description="管理用户设置")
    f2 = FeatureModel(project_id=seeded_project, name="系统设置", description="管理系统设置")
    db_session.add_all([actor1, f1, f2])
    await db_session.flush()
    await db_session.execute(
        feature_actor_table.insert().values(feature_id=f1.id, actor_id=actor1.id)
    )
    await db_session.flush()

    # Verify that the active issue initially is visible
    service = FindingService()
    issues_before = await service.list_findings(
        project_id=seeded_project,
        stage="what",
        view="issues",
        action=None,
        session=db_session
    )
    assert any(f.code == "LEAF_FEATURE_WITHOUT_ACTOR" for f in issues_before)
    target_finding = [f for f in issues_before if f.code == "LEAF_FEATURE_WITHOUT_ACTOR"][0]
    finding_id = target_finding.findingId

    # Replicate the migration by inserting into issue_overrides, then executing the data migration SQL
    from backend.database.model import IssueOverrideModel
    from backend.database.model import beijing_now
    
    # Insert historic record in issue_overrides
    db_session.add(
        IssueOverrideModel(
            project_id=seeded_project,
            issue_id=finding_id,
            status="ignored",
            created_at=beijing_now(),
            updated_at=beijing_now()
        )
    )
    await db_session.flush()
    
    # Execute the migration SQL wrapped in text()
    migration_sql = """
    INSERT INTO finding_overrides (
        project_id, finding_id, finding_type, status, stage, code, target_type, target_id, context_hash, created_at, updated_at
    )
    SELECT
        project_id, issue_id AS finding_id, 'issue' AS finding_type, status, NULL, NULL, NULL, NULL, NULL, created_at, updated_at
    FROM issue_overrides
    WHERE status IN ('ignored', 'resolved');
    """
    await db_session.execute(text(migration_sql))
    await db_session.flush()
    
    # Query finding_overrides to check if it's there
    override_res = await db_session.execute(
        select(FindingOverrideModel).where(
            FindingOverrideModel.project_id == seeded_project,
            FindingOverrideModel.finding_id == finding_id
        )
    )
    override = override_res.scalar_one_or_none()
    assert override is not None
    assert override.status == "ignored"
    assert override.finding_type == "issue"

    # Now verify that FindingService correctly filters it out because of the copied override!
    issues_after = await service.list_findings(
        project_id=seeded_project,
        stage="what",
        view="issues",
        action=None,
        session=db_session
    )
    assert not any(f.findingId == finding_id for f in issues_after)


@pytest.mark.asyncio
async def test_set_finding_status_dismissed_rejected(db_session, seeded_project):
    service = FindingService()
    
    # Try to set finding status to "dismissed", should raise ValueError
    with pytest.raises(ValueError, match="invalid_finding_status"):
        await service.set_finding_status(
            project_id=seeded_project,
            finding_id="what:LEAF_FEATURE_WITHOUT_ACTOR:feature:12",
            status="dismissed",
            session=db_session
        )


@pytest.mark.asyncio
async def test_set_finding_status_gate_condition_rejected(db_session, seeded_project):
    # Setup structure to trigger FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO gate condition
    actor1 = ActorModel(project_id=seeded_project, name="管理员", description="系统管理员")
    actor2 = ActorModel(project_id=seeded_project, name="访客", description="系统访客")
    f1 = FeatureModel(project_id=seeded_project, name="用户设置", description="管理用户设置")
    f2 = FeatureModel(project_id=seeded_project, name="系统设置", description="管理系统设置")
    
    db_session.add_all([actor1, actor2, f1, f2])
    await db_session.flush()

    await db_session.execute(
        feature_actor_table.insert().values(feature_id=f1.id, actor_id=actor1.id)
    )
    await db_session.execute(
        feature_actor_table.insert().values(feature_id=f2.id, actor_id=actor2.id)
    )
    await db_session.flush()

    # Seed one scenario for f1 so we have at least one scenario
    scenario = ScenarioModel(
        project_id=seeded_project,
        feature_id=f1.id,
        actor_id=actor1.id,
        name="修改用户密码",
        content="管理员修改用户密码并且保存"
    )
    db_session.add(scenario)
    await db_session.flush()

    service = FindingService()
    
    gate_id = "what:FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO:aggregate"

    # 1. Assert ignored is rejected for gate
    with pytest.raises(ValueError, match="invalid_finding_status"):
        await service.set_finding_status(
            project_id=seeded_project,
            finding_id=gate_id,
            status="ignored",
            session=db_session
        )

    # 2. Assert resolved is rejected for gate
    with pytest.raises(ValueError, match="invalid_finding_status"):
        await service.set_finding_status(
            project_id=seeded_project,
            finding_id=gate_id,
            status="resolved",
            session=db_session
        )

    # 3. Verify that no override record was created in the database
    override_res = await db_session.execute(
        select(FindingOverrideModel).where(
            FindingOverrideModel.project_id == seeded_project,
            FindingOverrideModel.finding_id == gate_id
        )
    )
    assert override_res.scalar_one_or_none() is None


class TestFindingClassificationContract:
    """Table-driven classification contract tests.

    Every known detector code must have a defined:
      - FindingType (ISSUE / QUALITY_HINT / GATE_CONDITION)
      - BlockingScope (NONE / STAGE_TRANSITION / PREVIEW)
      - Capability (ai_repair / generation_draft / open_panel / unsupported)

    Adding a new detector code requires updating this table,
    ensuring all three dimensions are explicitly decided.
    """

    # code -> (expected_finding_type, expected_blocking_scope)
    CLASSIFICATION_TABLE: dict[str, tuple[str, str]] = {
        # What stage
        "ACTOR_WITHOUT_FEATURE":                    ("quality_hint",   "none"),
        "LEAF_FEATURE_WITHOUT_ACTOR":               ("issue",          "stage_transition"),
        "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO":      ("issue",          "none"),  # aggregate → gate_condition
        "SCENARIO_ACTOR_NOT_IN_FEATURE_ACTORS":      ("issue",          "stage_transition"),
        "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA":      ("quality_hint",   "none"),
        "DUPLICATE_SCENARIO_NAME":                   ("quality_hint",   "none"),
        # How stage
        "LEAF_FEATURE_WITHOUT_FLOW":                 ("issue",          "none"),  # aggregate → gate_condition
        "FLOW_WITHOUT_FEATURE":                      ("issue",          "stage_transition"),
        "FLOW_WITHOUT_STEPS":                        ("issue",          "stage_transition"),
        "ACTOR_ACTION_STEP_WITHOUT_ACTOR":           ("issue",          "stage_transition"),
        "JUDGMENT_STEP_WITH_TOO_FEW_BRANCHES":       ("issue",          "stage_transition"),
        "UNREACHABLE_FLOW_STEP":                     ("issue",          "stage_transition"),
        "BUSINESS_OBJECT_WITHOUT_USAGE":             ("quality_hint",   "none"),
        "BUSINESS_OBJECT_WITHOUT_ATTRIBUTES":        ("quality_hint",   "preview"),
        # Scope stage
        "LEAF_FEATURE_WITHOUT_SCOPE":                ("issue",          "none"),  # aggregate → gate_condition
        "SCOPE_WITHOUT_REASON":                      ("quality_hint",   "none"),
    }

    def test_all_known_codes_have_classification(self):
        """Every code in KNOWN_ISSUE_CODES must appear in the classification table."""
        from backend.core.issue_capabilities import KNOWN_ISSUE_CODES

        missing = KNOWN_ISSUE_CODES - self.CLASSIFICATION_TABLE.keys()
        assert not missing, f"Codes missing classification: {missing}"

    def test_all_classifications_correspond_to_known(self):
        """No extra codes in the classification table."""
        from backend.core.issue_capabilities import KNOWN_ISSUE_CODES

        extra = set(self.CLASSIFICATION_TABLE.keys()) - KNOWN_ISSUE_CODES
        assert not extra, f"Extra codes in classification table: {extra}"

    def test_classification_finding_type_values(self):
        """All FindingType values are valid."""
        valid_types = {"issue", "quality_hint", "gate_condition", "next_suggestion"}
        for code, (ftype, _) in self.CLASSIFICATION_TABLE.items():
            assert ftype in valid_types, f"{code} invalid FindingType: {ftype}"

    def test_classification_blocking_scope_values(self):
        """All BlockingScope values are valid."""
        valid_scopes = {"none", "stage_transition", "preview", "export", "checkpoint"}
        for code, (_, scope) in self.CLASSIFICATION_TABLE.items():
            assert scope in valid_scopes, f"{code} invalid BlockingScope: {scope}"

    def test_classification_matches_capability(self):
        """Each code's capability must be consistent with its FindingType and BlockingScope.

        Rules:
          - quality_hint codes: capability must not be unsupported (always actionable)
          - stage_transition blocking: capability must be ai_repair, generation_draft, or open_panel
          - none blocking: capability can be anything (including unsupported)
        """
        from backend.core.issue_capabilities import get_issue_capability, IssueCapabilityKind

        for code, (ftype, scope) in self.CLASSIFICATION_TABLE.items():
            cap = get_issue_capability(code)

            if ftype == "quality_hint":
                assert cap.kind != IssueCapabilityKind.UNSUPPORTED, (
                    f"{code} is quality_hint but unsupported"
                )

            if scope == "stage_transition":
                assert cap.kind in (
                    IssueCapabilityKind.AI_REPAIR,
                    IssueCapabilityKind.GENERATION_DRAFT,
                    IssueCapabilityKind.OPEN_PANEL,
                ), f"{code} blocks stage_transition but capability is {cap.kind}"
