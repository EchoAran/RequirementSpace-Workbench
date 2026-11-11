"""Tests for P6 Perception Architecture, context hashing, and fail-closed handling."""

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.modules.diagnosis_quality.perception.application.job_executor import (
    PerceptionJobExecutor,
)
from backend.core.detectors.issue_context import (
    DomainRuleIssueItem,
    FlowIssueItem,
    FlowStepIssueItem,
    FlowTransitionIssueItem,
    IssueProjectContext,
    RuleLinkIssueItem,
)
from backend.core.perceptrons.rules_perceptron import (
    RulePerceptron,
    RulePerceptronInput,
)
from backend.database.model import (
    Base,
    PerceptionJobModel,
    PerceptionSlotModel,
    ProjectModel,
)
from backend.schemas import (
    PerceptionJobStatus,
    PerceptionKindType,
)


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


def _create_sample_context() -> IssueProjectContext:
    """Create a populated sample IssueProjectContext for testing hashing."""
    return IssueProjectContext(
        project_id=1,
        user_requirements="Requirement text",
        actors=[],
        features=[],
        scenarios=[],
        flows=[
            FlowIssueItem(
                flow_id=1,
                name="Main Flow",
                description="Primary user flow",
                feature_ids=[101],
                steps=[
                    FlowStepIssueItem(
                        step_id=11,
                        flow_id=1,
                        position=1,
                        name="Start Step",
                        description="User enters details",
                        step_type="user_action",
                        actor_ids=[1],
                        input_business_object_ids=[10],
                        output_business_object_ids=[],
                    ),
                    FlowStepIssueItem(
                        step_id=12,
                        flow_id=1,
                        position=2,
                        name="Process Step",
                        description="System validates",
                        step_type="system_action",
                        actor_ids=[],
                        input_business_object_ids=[10],
                        output_business_object_ids=[20],
                    ),
                ],
                transitions=[
                    FlowTransitionIssueItem(
                        transition_id=101,
                        flow_id=1,
                        source_step_id=11,
                        target_step_id=12,
                        label="Next",
                        condition_text="valid == true",
                        is_default=True,
                    )
                ],
            )
        ],
        business_objects=[],
        scopes=[],
        domain_rules=[
            DomainRuleIssueItem(
                rule_id=201,
                logical_uuid="uuid-r1",
                title="Min age",
                statement="Age >= 18",
                origin="manual",
                confirmation_status="confirmed",
            )
        ],
        rule_links=[
            RuleLinkIssueItem(
                link_id=301,
                logical_uuid="uuid-l1",
                rule_id=201,
                target_kind="flow_step",
                target_logical_uuid="uuid-s1",
                link_purpose="applies_to",
            )
        ],
    )


def test_flow_context_hash_invalidation():
    """Verify that flow context hash responds to semantic changes and remains stable."""
    executor = PerceptionJobExecutor()
    ctx1 = _create_sample_context()
    hash1 = executor._build_flow_context_hash(ctx1)

    # Hash should be stable and deterministic
    assert hash1 == executor._build_flow_context_hash(ctx1)

    # Modifying transition condition should invalidate the hash
    ctx_transition_changed = _create_sample_context()
    ctx_transition_changed.flows[0].transitions[0] = FlowTransitionIssueItem(
        transition_id=101,
        flow_id=1,
        source_step_id=11,
        target_step_id=12,
        label="Next",
        condition_text="valid == false",
        is_default=False,
    )
    assert executor._build_flow_context_hash(ctx_transition_changed) != hash1

    # Modifying domain rules should invalidate flow hash
    ctx_rule_changed = _create_sample_context()
    ctx_rule_changed.domain_rules[0] = DomainRuleIssueItem(
        rule_id=201,
        logical_uuid="uuid-r1",
        title="Min age updated",
        statement="Age >= 21",
            origin="manual",
        confirmation_status="confirmed",
    )
    assert executor._build_flow_context_hash(ctx_rule_changed) != hash1


def test_rule_context_hash_invalidation():
    """Verify that rule context hash responds to rule and source changes."""
    executor = PerceptionJobExecutor()
    ctx1 = _create_sample_context()
    hash1 = executor._build_rule_context_hash(ctx1)

    # Hash is deterministic
    assert hash1 == executor._build_rule_context_hash(ctx1)

    # Rule link changed
    ctx2 = _create_sample_context()
    ctx2.rule_links.append(
        RuleLinkIssueItem(
            link_id=302,
            logical_uuid="uuid-l2",
            rule_id=201,
            target_kind="flow_step",
            target_logical_uuid="uuid-s2",
            link_purpose="source",
        )
    )
    assert executor._build_rule_context_hash(ctx2) != hash1

@pytest.mark.asyncio
async def test_rule_perceptron_invocation():
    """Verify RulePerceptron formats input and calls LLM handler."""
    perceptron = RulePerceptron()
    fake_response = '{"perception_description": "Rule 201 needs clarification on boundary"}'

    with patch.object(perceptron._llm_handler, "call_llm", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = fake_response
        result = await perceptron.perceive(
            RulePerceptronInput(
                user_requirements="Req text",
                domain_rules=[{"rule_id": 1, "title": "R1", "statement": "Stmt"}],
            )
        )
        assert result == {"perception_description": "Rule 201 needs clarification on boundary"}
        assert mock_call.called


@pytest.mark.asyncio
async def test_job_failure_fail_closed(db_session):
    """Verify that perception failure marks job FAILED and removes any slots."""
    project = ProjectModel(owner_user_id=1, name="Fail Test", user_requirements="Reqs")
    db_session.add(project)
    await db_session.flush()

    job = PerceptionJobModel(
        project_id=project.id,
        stage="how",
        perception_kind=PerceptionKindType.RULE.name,
        target_type="project",
        target_id=str(project.id),
        context_hash="hash123",
        status=PerceptionJobStatus.RUNNING.value,
        result_slot_payload={"dummy": "payload"},
    )
    db_session.add(job)
    await db_session.commit()

    slot = PerceptionSlotModel(
        id=job.id,
        project_id=project.id,
        perception_kind=PerceptionKindType.RULE.value,
        description="Old description",
    )
    db_session.add(slot)
    await db_session.commit()

    executor = PerceptionJobExecutor()
    await executor._handle_job_failure(
        job_id=job.id,
        error=RuntimeError("LLM service unavailable"),
        session=db_session,
        start_time=0.0,
    )

    await db_session.refresh(job)
    assert job.status == PerceptionJobStatus.FAILED.value
    assert job.result_slot_payload is None
    assert "LLM service unavailable" in (job.error_message or "")

    # Slot must be deleted
    slot_check = await db_session.get(PerceptionSlotModel, job.id)
    assert slot_check is None


def test_normalize_perception_description_fail_closed():
    """Verify that malformed or missing perception payload raises ValueError."""
    executor = PerceptionJobExecutor()

    with pytest.raises(ValueError, match="missing perception_description"):
        executor._normalize_perception_description({})

    with pytest.raises(ValueError, match="missing perception_description"):
        executor._normalize_perception_description({"unexpected_key": "some value"})

    with pytest.raises(ValueError, match="cannot be blank"):
        executor._normalize_perception_description({"perception_description": "   "})

    with pytest.raises(ValueError, match="must be a string"):
        executor._normalize_perception_description({"perception_description": 123})

    # Valid empty markers
    assert executor._normalize_perception_description({"perception_description": "无需补充"}) is None
    assert executor._normalize_perception_description({"perception_description": "不需要"}) is None
    assert executor._normalize_perception_description({"perception_description": "None"}) is None

    # Valid non-empty suggestion
    result = executor._normalize_perception_description({"perception_description": "建议为登录流程补充短信超时规则"})
    assert result == "建议为登录流程补充短信超时规则"


def test_normalize_perception_description_exact_match_preserves_legitimate_suggestions():
    """Verify that suggestions starting with words like 'none' or '不需要' are not falsely dropped."""
    executor = PerceptionJobExecutor()

    # Legitimate suggestions with no-slot prefix words
    assert (
        executor._normalize_perception_description(
            {"perception_description": "none but add a missing exception path"}
        )
        == "none but add a missing exception path"
    )
    assert (
        executor._normalize_perception_description(
            {"perception_description": "不需要额外的流程，但请补充库存校验规则"}
        )
        == "不需要额外的流程，但请补充库存校验规则"
    )

    # Exact no-slot markers must still resolve to None (DONE_EMPTY)
    assert executor._normalize_perception_description({"perception_description": "none"}) is None
    assert executor._normalize_perception_description({"perception_description": "none."}) is None
    assert executor._normalize_perception_description({"perception_description": "不需要"}) is None
    assert executor._normalize_perception_description({"perception_description": "[no_suggestion]"}) is None
    assert executor._normalize_perception_description({"perception_description": "暂无建议"}) is None


@pytest.mark.asyncio
async def test_how_perception_orchestrates_rule_before_flow():
    """Verify that get_next_how_suggestion dispatches RULE perception before FLOW."""
    from backend.api.modules.diagnosis_quality.perception.application.job import PerceptionJobService

    service = PerceptionJobService()
    recorded_kinds: list[str] = []

    async def mock_get_suggestion(**kwargs):
        kind = kwargs.get("perception_kind")
        recorded_kinds.append(kind)
        if kind == "RULE":
            # Simulate returning a suggestion for RULE
            return {"kind": "RULE_SUGGESTION"}
        return None

    with patch.object(service, "_get_perception_suggestion", side_effect=mock_get_suggestion):
        with patch("backend.api.modules.diagnosis_quality.perception.application.job.load_issue_project_context") as mock_load:
            mock_load.return_value = IssueProjectContext(
                project_id=1,
                user_requirements="Reqs",
                actors=[],
                features=[],
                scenarios=[],
                flows=[],
                business_objects=[],
                scopes=[],
                domain_rules=[],
                rule_links=[],
            )
            result = await service.get_next_how_suggestion(
                project_id=1,
                session=AsyncMock(),
                workspace_id=2,
            )
            assert result == {"kind": "RULE_SUGGESTION"}
            assert recorded_kinds == ["RULE"]


def test_build_rule_link_payloads_fails_on_missing_empty_or_invalid_purpose():
    """Verify _build_rule_link_payloads enforces strict fail-closed purpose validation."""
    executor = PerceptionJobExecutor()

    def _make_ctx(rule_links):
        return IssueProjectContext(
            project_id=1,
            user_requirements="",
            actors=[],
            features=[],
            scenarios=[],
            flows=[],
            business_objects=[],
            scopes=[],
            rule_links=rule_links,
        )

    # 1b. link_purpose is None
    none_link = SimpleNamespace(
        link_id=1,
        rule_id=10,
        target_kind="flow_step",
        target_logical_uuid="uuid-1",
        link_purpose=None,
    )
    with pytest.raises(ValueError, match="Invalid link purpose 'None'"):
        executor._build_rule_link_payloads(_make_ctx([none_link]))

    # 2. Empty link_purpose ("")
    empty_link = SimpleNamespace(
        link_id=1,
        rule_id=10,
        target_kind="flow_step",
        target_logical_uuid="uuid-1",
        link_purpose="",
    )
    with pytest.raises(ValueError, match="Invalid link purpose ''"):
        executor._build_rule_link_payloads(_make_ctx([empty_link]))

    # 3. Invalid link_purpose ("invalid_custom" or old purpose not in RULE_LINK_PURPOSE_VALUES)
    invalid_link = SimpleNamespace(
        link_id=1,
        rule_id=10,
        target_kind="flow_step",
        target_logical_uuid="uuid-1",
        link_purpose="invalid_custom_purpose",
    )
    with pytest.raises(ValueError, match="Invalid link purpose 'invalid_custom_purpose'"):
        executor._build_rule_link_payloads(_make_ctx([invalid_link]))

    # Positive case: valid link_purpose ("source" and "applies_to")
    valid_link_source = SimpleNamespace(
        link_id=1,
        rule_id=10,
        target_kind="flow_step",
        target_logical_uuid="uuid-1",
        link_purpose="source",
    )
    valid_link_applies = SimpleNamespace(
        link_id=2,
        rule_id=10,
        target_kind="scenario",
        target_logical_uuid="uuid-2",
        link_purpose="applies_to",
    )
    payloads = executor._build_rule_link_payloads(_make_ctx([valid_link_source, valid_link_applies]))
    assert len(payloads) == 2
    assert payloads[0]["link_purpose"] == "source"
    assert payloads[1]["link_purpose"] == "applies_to"

def test_build_rule_link_payloads_fails_on_invalid_target_fields():
    """Verify _build_rule_link_payloads enforces strict target field validation (fail‑closed)."""
    executor = PerceptionJobExecutor()

    def _make_ctx(rule_links):
        return IssueProjectContext(
            project_id=1,
            user_requirements="",
            actors=[],
            features=[],
            scenarios=[],
            flows=[],
            business_objects=[],
            scopes=[],
            rule_links=rule_links,
        )

    # 1. Null target_kind
    missing_kind = SimpleNamespace(
        target_kind=None,
        link_id=1,
        rule_id=10,
        target_logical_uuid="uuid-1",
        link_purpose="source",
    )
    with pytest.raises(ValueError, match="Unsupported target kind 'None'"):
        executor._build_rule_link_payloads(_make_ctx([missing_kind]))

    # 2. Null target_logical_uuid
    missing_uuid = SimpleNamespace(
        target_logical_uuid=None,
        link_id=1,
        rule_id=10,
        target_kind="flow_step",
        link_purpose="source",
    )
    with pytest.raises(ValueError, match="Target logical UUID cannot be empty"):
        executor._build_rule_link_payloads(_make_ctx([missing_uuid]))

    # 3. Empty target_logical_uuid
    empty_uuid = SimpleNamespace(
        link_id=1,
        rule_id=10,
        target_kind="flow_step",
        target_logical_uuid="",
        link_purpose="source",
    )
    with pytest.raises(ValueError, match="Target logical UUID cannot be empty"):
        executor._build_rule_link_payloads(_make_ctx([empty_uuid]))

    # 4. Invalid target_kind
    invalid_kind = SimpleNamespace(
        link_id=1,
        rule_id=10,
        target_kind="invalid_kind",
        target_logical_uuid="uuid-1",
        link_purpose="source",
    )
    with pytest.raises(ValueError, match="Unsupported target kind 'invalid_kind'"):
        executor._build_rule_link_payloads(_make_ctx([invalid_kind]))

    # Positive case (valid target fields)
    valid_link = SimpleNamespace(
        link_id=1,
        rule_id=10,
        target_kind="flow_step",
        target_logical_uuid="uuid-1",
        link_purpose="source",
    )
    payloads = executor._build_rule_link_payloads(_make_ctx([valid_link]))
    assert len(payloads) == 1
    assert payloads[0]["target_kind"] == "flow_step"
    assert payloads[0]["target_logical_uuid"] == "uuid-1"
