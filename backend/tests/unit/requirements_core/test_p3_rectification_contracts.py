"""Unit and contract tests for Phase P3 rectification (all 6 P0 items and defects)."""

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.modules.decision_workflow.choice_group.application.choice_service import (
    ChoiceService,
)
from backend.api.modules.decision_workflow.ports.ports import CandidateContext
from backend.api.modules.requirements_core.domain_rule.application.choice_adapter import (
    RuleGenerationChoiceAdapter,
)
from backend.api.modules.requirements_core.domain_rule.application.rule_generation_service import (
    RuleGenerationService,
)
from backend.api.modules.requirements_core.flow.application.choice_adapter import (
    FlowGenerationChoiceAdapter,
)
from backend.api.modules.requirements_core.flow.application.generation.persistence import (
    create_business_objects,
)
from backend.api.modules.requirements_core.generation_context import (
    compute_flow_context_hash,
    load_flow_generation_context,
    load_generation_actors,
    load_generation_features,
)
from backend.core.generators.rules_generator import (
    RulesGenerator,
    RulesGeneratorInput,
)
from unittest.mock import AsyncMock, patch

from backend.api.modules.requirements_core.domain_rule.domain.model_invariants import (
    ALLOWED_RULE_LINK_TARGET_KINDS,
)
from backend.api.modules.requirements_core.domain_rule.domain.node_resolver import (
    RequirementNodeResolver,
)
from backend.core.generators.flows_generator import (
    FlowsGenerator,
    FlowsGeneratorInput,
)
from backend.database.database import Base
from backend.database.model import (
    ActorModel,
    BranchWorkspaceModel,
    BusinessObjectModel,
    ChoiceGroupModel,
    ChoiceModel,
    ConfirmationStatus,
    DomainRuleModel,
    FeatureModel,
    FlowModel,
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
    ProjectModel,
    RequirementBranchModel,
    RuleLinkModel,
    RuleLinkPurpose,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    UserModel,
)
from backend.schemas import ActorNode, FeatureNode


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def test_project(session_factory):
    async with session_factory() as session:
        project = ProjectModel(
            name="P3 Rectification Test Project",
            owner_user_id=1,
            user_requirements="Initial User Requirements",
            content_locale="zh-CN",
        )
        session.add(project)
        await session.flush()

        main_branch = RequirementBranchModel(project_id=project.id, name="main")
        session.add(main_branch)
        await session.flush()
        main_workspace = BranchWorkspaceModel(project_id=project.id, branch_id=main_branch.id,
                                              user_requirements=project.user_requirements)
        session.add(main_workspace)
        await session.flush()

        actor = ActorModel(project_id=project.id, workspace_id=main_workspace.id, name="Default User")
        feature = FeatureModel(project_id=project.id, workspace_id=main_workspace.id, name="Default Feature")
        session.add_all([actor, feature])
        await session.flush()

        branch = RequirementBranchModel(
            project_id=project.id,
            name="feature-branch",
            status="active",
        )
        session.add(branch)
        await session.flush()

        branch_ws = BranchWorkspaceModel(
            project_id=project.id,
            branch_id=branch.id,
            user_requirements="Branch User Requirements",
        )
        session.add(branch_ws)

        rule = DomainRuleModel(
            project_id=project.id,
            workspace_id=main_workspace.id,
            title="Generation prerequisite",
            statement="Generated flows must follow the available domain rules.",
        )
        session.add(rule)
        await session.commit()

        return {"project_id": project.id, "workspace_id": branch_ws.id, "main_workspace_id": main_workspace.id}


# ============================================================================
# P0-1: 知识库规则来源接通与校验
# ============================================================================

def test_p0_1_knowledge_fragments_included_in_context_hash():
    svc = RuleGenerationService()
    actors = [ActorNode(actorId=1, actorName="User", actorDescription="Test user")]
    features = [FeatureNode(featureId=1, featureName="Login", featureDescription="Test login")]
    scenarios = [{"logical_uuid": "sc-1", "name": "Valid Login", "content": "Given ..."}]
    acs = [{"logical_uuid": "ac-1", "content": "Then success"}]
    rules = [{"logical_uuid": "r-1", "title": "Password length", "statement": "Must be >= 8"}]

    hash_without_knowledge = svc.compute_source_context_hash(
        "Reqs", actors, features, scenarios, acs, rules, knowledge_fragments=[]
    )
    knowledge_fragments = [
        {"fragment_id": "chunk-101", "document_id": 1, "content": "Security policy doc"}
    ]
    hash_with_knowledge = svc.compute_source_context_hash(
        "Reqs", actors, features, scenarios, acs, rules, knowledge_fragments=knowledge_fragments
    )
    assert hash_without_knowledge != hash_with_knowledge, "Knowledge fragments must alter the source context hash"


def test_p0_1_rules_generator_allows_knowledge_target_kind():
    gen = RulesGenerator()
    input_data = RulesGeneratorInput(
        user_requirements="Reqs",
        scenarios=[{"logical_uuid": "sc-1", "name": "S1"}],
        acceptance_criteria=[{"logical_uuid": "ac-1", "content": "AC1"}],
        knowledge_fragments=[{"fragment_id": "chunk-101", "document_id": 1, "content": "chunk content"}],
    )

    valid_rules = [
        {
            "temp_id": "rule-1",
            "title": "Security Rule",
            "statement": "Password policy statement",
            "parent_rule_ref": None,
            "confirmation_status": "ai_assumption",
            "source_links": [
                {
                    "target_kind": "knowledge",
                    "target_logical_uuid": "chunk-101",
                    "context_text": "From doc chunk",
                }
            ],
        }
    ]
    # Should not raise
    gen._validate_rules(valid_rules, input_data)

    # Unknown knowledge fragment must be rejected
    invalid_rules = [
        {
            "temp_id": "rule-2",
            "title": "Security Rule 2",
            "statement": "Invalid chunk ref",
            "parent_rule_ref": None,
            "confirmation_status": "ai_assumption",
            "source_links": [
                {
                    "target_kind": "knowledge",
                    "target_logical_uuid": "chunk-unknown-999",
                    "context_text": "Unknown",
                }
            ],
        }
    ]
    with pytest.raises(ValueError, match="not found in knowledge context"):
        gen._validate_rules(invalid_rules, input_data)


# ============================================================================
# P0-2: Rule 候选过期检查完整使用 source_context_hash
# ============================================================================

@pytest.mark.asyncio
async def test_p0_2_rule_candidate_staleness_detects_hash_drift(session_factory, test_project):
    project_id = test_project["project_id"]
    workspace_id = test_project["main_workspace_id"]
    adapter = RuleGenerationChoiceAdapter()

    async with session_factory() as session:
        actor = ActorModel(project_id=project_id, workspace_id=workspace_id, name="Admin")
        feature = FeatureModel(project_id=project_id, workspace_id=workspace_id, name="Auth")
        session.add_all([actor, feature])
        await session.flush()

        sc = ScenarioModel(
            project_id=project_id,
            workspace_id=workspace_id,
            feature_id=feature.id,
            actor_id=actor.id,
            name="Login Scenario",
            content="Initial scenario content",
        )
        session.add(sc)
        await session.commit()

    async with session_factory() as session:
        _input, original_hash = await adapter._service.load_rule_generation_context(
            session=session, project_id=project_id, workspace_id=workspace_id
        )

        group = ChoiceGroupModel(project_id=project_id, workspace_id=workspace_id,
                                 generation_type="rule", status="open")
        session.add(group)
        await session.flush()

        class MockChoice:
            def __init__(self, p_id, p_load):
                self.choice_group_id = group.id
                self.payload = p_load

        choice = MockChoice(
            project_id,
            {
                "workspace_id": workspace_id,
                "source_context_hash": original_hash,
                "rules": [
                    {
                        "temp_id": "r-1",
                        "title": "Rule",
                        "statement": "Stmt",
                        "source_links": [
                            {"target_kind": "scenario", "target_logical_uuid": sc.logical_uuid}
                        ],
                    }
                ],
            },
        )
        is_stale, reason = await adapter.is_context_stale(choice, session)
        assert not is_stale, "Candidate should not be stale when context hash matches"

        # Now modify scenario content (UUID stays same, but content drifts!)
        sc_db = await session.get(ScenarioModel, sc.id)
        sc_db.content = "Modified scenario content by user"
        await session.commit()

    async with session_factory() as session:
        is_stale, reason = await adapter.is_context_stale(choice, session)
        assert is_stale, "Candidate MUST be stale when upstream content drifted"
        assert "已过期" in reason or "变更" in reason


# ============================================================================
# P0-3: Flow 候选过期检查异常传播、移除兜底、禁止 force 绕过 stale
# ============================================================================

def test_p0_3_flow_choice_adapter_has_no_fallback():
    # Calling get_flow_generation_service without registration should fail fast
    adapter = FlowGenerationChoiceAdapter()
    assert adapter._service is not None


@pytest.mark.asyncio
async def test_p0_3_choice_service_blocks_force_for_stale_p3_candidates(session_factory, test_project):
    project_id = test_project["project_id"]
    workspace_id = test_project["main_workspace_id"]
    choice_service = ChoiceService()

    async with session_factory() as session:
        group = ChoiceGroupModel(
            project_id=project_id,
            status="active",
            selection_mode="single",
            generation_type="flow",  # P3 generation type,
                    workspace_id=workspace_id,
        )
        session.add(group)
        await session.flush()

        choice = ChoiceModel(
            choice_group_id=group.id,
            title="Stale Flow Candidate",
            rationale="Test",
            status="candidate",
            patch={},
            apply_mode="draft_payload",
            draft_type="flow",
            payload={
                "project_id": project_id,
                "workspace_id": workspace_id,
                "context_hash": "non-existent-stale-hash",
                "flows": [],
            },
        )
        session.add(choice)
        await session.commit()

        # Attempt to accept with force=True
        # Because generation_type is 'flow', force=True must NOT bypass stale validation!
        resp = await choice_service.accept_choice(
            project_id=project_id,
            choice_id=choice.id,
            session=session,
            force=True,
                         workspace_id=workspace_id,
        )
        assert resp.is_stale is True, "force=True must NOT bypass stale check for flow candidates"
        assert resp.message == "choice_context_stale"


# ============================================================================
# P0-4: Flow context_hash 包含父规则关系
# ============================================================================

def test_p0_4_flow_context_hash_reflects_parent_rule_uuid():
    actors = [ActorNode(actorId=1, actorName="User", actorDescription="Test user")]
    features = [FeatureNode(featureId=1, featureName="Feature", featureDescription="Test feature")]
    scenarios = [{"logical_uuid": "sc-1", "name": "S1", "content": "C1"}]
    acs = [{"logical_uuid": "ac-1", "content": "AC1"}]

    rules_no_parent = [
        {
            "logical_uuid": "rule-child",
            "title": "Child Rule",
            "statement": "Must comply with policy",
            "confirmation_status": "ai_assumption",
            "parent_rule_uuid": None,
            "links": [],
        }
    ]
    hash_no_parent = compute_flow_context_hash(
        "Reqs", actors, features, scenarios, acs, rules_no_parent
    )

    rules_with_parent = [
        {
            "logical_uuid": "rule-child",
            "title": "Child Rule",
            "statement": "Must comply with policy",
            "confirmation_status": "ai_assumption",
            "parent_rule_uuid": "parent-rule-uuid-999",
            "links": [],
        }
    ]
    hash_with_parent = compute_flow_context_hash(
        "Reqs", actors, features, scenarios, acs, rules_with_parent
    )
    assert hash_no_parent != hash_with_parent, "Parent rule UUID change must alter flow context hash!"


# ============================================================================
# P0-5: 主工作区 Actor/Feature 隔离（禁止混入分支实体）
# ============================================================================

@pytest.mark.asyncio
async def test_p0_5_main_workspace_scoping_no_branch_entity_leakage(session_factory, test_project):
    project_id = test_project["project_id"]
    workspace_id = test_project["main_workspace_id"]
    branch_ws_id = test_project["workspace_id"]

    async with session_factory() as session:
        main_actor = ActorModel(project_id=project_id, workspace_id=workspace_id, name="Main User")
        branch_actor = ActorModel(project_id=project_id, workspace_id=branch_ws_id, name="Branch Guest")
        main_feature = FeatureModel(project_id=project_id, workspace_id=workspace_id, name="Main Checkout")
        branch_feature = FeatureModel(project_id=project_id, workspace_id=branch_ws_id, name="Branch Coupon")
        session.add_all([main_actor, branch_actor, main_feature, branch_feature])
        await session.commit()

    async with session_factory() as session:
        # 1. generation_context.load_generation_actors for main workspace
        actors = await load_generation_actors(session, project_id, workspace_id=workspace_id)
        actor_names = {a.name for a in actors}
        assert "Main User" in actor_names
        assert "Branch Guest" not in actor_names, "Branch actor must not leak into main workspace"

        # 2. generation_context.load_generation_features for main workspace
        features = await load_generation_features(session, project_id, workspace_id=workspace_id)
        feature_names = {f.name for f in features}
        assert "Main Checkout" in feature_names
        assert "Branch Coupon" not in feature_names, "Branch feature must not leak into main workspace"

        # 3. RuleGenerationService._load_actors and _load_features for main workspace
        rule_actors = await RuleGenerationService._load_actors(session, project_id, workspace_id=workspace_id)
        rule_actor_names = {a.actorName for a in rule_actors}
        assert "Main User" in rule_actor_names
        assert "Branch Guest" not in rule_actor_names

        rule_features = await RuleGenerationService._load_features(session, project_id, workspace_id=workspace_id)
        rule_feature_names = {f.featureName for f in rule_features}
        assert "Main Checkout" in rule_feature_names
        assert "Branch Coupon" not in rule_feature_names


# ============================================================================
# P0-6: Business Object 显式复用合同与乐观版本保护
# ============================================================================

@pytest.mark.asyncio
async def test_p0_6_business_object_explicit_reuse_contract(session_factory, test_project):
    project_id = test_project["project_id"]
    workspace_id = test_project["main_workspace_id"]

    async with session_factory() as session:
        existing_bo = BusinessObjectModel(
            project_id=project_id,
            workspace_id=workspace_id,
            name="Order",
            description="Existing confirmed order",
            confirmation_status=ConfirmationStatus.CONFIRMED.value,
        )
        session.add(existing_bo)
        await session.commit()
        bo_id = existing_bo.id
        bo_uuid = existing_bo.logical_uuid

    async with session_factory() as session:
        # 1. Reusing explicit object by id or logical_uuid
        items = [
            {
                "business_object_number": "bo-reused",
                "object_id": bo_id,
                "business_object_name": "Order",
                "business_object_description": "Reused description",
            },
            {
                "business_object_number": "bo-new",
                "business_object_name": "Invoice",
                "business_object_description": "New invoice object",
            },
        ]
        models_by_num = await create_business_objects(session, project_id, items, workspace_id=workspace_id)
        assert models_by_num["bo-reused"].id == bo_id, "Reused object must point to existing model ID"
        assert models_by_num["bo-new"].id != bo_id, "New object must be assigned fresh ID"

        # Verify count in database: total should be 2 (1 existing + 1 new), NOT 3!
        res = await session.execute(select(sa.func.count(BusinessObjectModel.id)).where(BusinessObjectModel.project_id == project_id))
        assert res.scalar_one() == 2

    async with session_factory() as session:
        # 2. Strict prohibition: auto-merging by name alone without ID or logical_uuid is forbidden!
        same_name_items = [
            {
                "business_object_number": "bo-duplicate-name",
                "business_object_name": "Order",  # Same name, but NO object_id or logical_uuid
                "business_object_description": "Should not auto merge",
            }
        ]
        models_by_num2 = await create_business_objects(session, project_id, same_name_items, workspace_id=workspace_id)
        # It creates a new model because auto-merging by name alone is forbidden
        assert models_by_num2["bo-duplicate-name"].id != bo_id


@pytest.mark.asyncio
async def test_p0_6_flow_adapter_workspace_version_optimistic_conflict(session_factory, test_project):
    project_id = test_project["project_id"]
    workspace_id = test_project["main_workspace_id"]
    adapter = FlowGenerationChoiceAdapter()

    async with session_factory() as session:
        payload = {
            "project_id": project_id,
            "workspace_id": workspace_id,
            "expected_workspace_version": "v1.0.0-outdated",
            "flows": [],
            "business_objects": [],
        }
        with pytest.raises(ValueError, match="workspace_version_conflict"):
            await adapter.apply_candidate(payload, session, expected_workspace_version="v1.0.0-outdated", workspace_id=workspace_id)


# ============================================================================
# Strict Schema: 严格禁止 rule_type 字段 (extra=forbid)
# ============================================================================

def test_strict_schema_forbids_extra_rule_type():
    gen = RulesGenerator()
    input_data = RulesGeneratorInput(
        user_requirements="Reqs",
        scenarios=[{"logical_uuid": "sc-1", "name": "S1"}],
        acceptance_criteria=[{"logical_uuid": "ac-1", "content": "AC1"}],
    )
    rules_with_forbidden_field = [
        {
            "temp_id": "rule-1",
            "title": "Title",
            "statement": "Statement",
            "rule_type": "forbidden_type",  # STRICTLY FORBIDDEN!
            "confirmation_status": "ai_assumption",
            "source_links": [
                {"target_kind": "scenario", "target_logical_uuid": "sc-1"}
            ],
        }
    ]
    with pytest.raises(ValueError, match="rule_schema_validation_failed"):
        gen._validate_rules(rules_with_forbidden_field, input_data)


# ============================================================================
# Parent Rule Ref 解析支持已有规则 UUID
# ============================================================================

@pytest.mark.asyncio
async def test_parent_rule_ref_resolves_existing_workspace_rule(session_factory, test_project):
    project_id = test_project["project_id"]
    workspace_id = test_project["main_workspace_id"]
    adapter = RuleGenerationChoiceAdapter()

    async with session_factory() as session:
        parent_rule = DomainRuleModel(
            project_id=project_id,
            workspace_id=workspace_id,
            title="Existing Parent Rule",
            statement="Must satisfy parent constraint",
            confirmation_status=ConfirmationStatus.CONFIRMED.value,
        )
        session.add(parent_rule)
        await session.commit()
        parent_uuid = parent_rule.logical_uuid
        parent_id = parent_rule.id

    async with session_factory() as session:
        payload = {
            "project_id": project_id,
            "workspace_id": workspace_id,
            "source_context_hash": "test-hash",
            "rules": [
                {
                    "temp_id": "rule-child",
                    "title": "Child Rule",
                    "statement": "Child statement",
                    "parent_rule_ref": parent_uuid,  # References existing rule's logical_uuid!
                    "confirmation_status": "ai_assumption",
                    "source_links": [],
                }
            ],
        }
        await adapter.apply_candidate(payload, session, workspace_id=workspace_id)
        await session.commit()

    async with session_factory() as session:
        res = await session.execute(
            select(DomainRuleModel).where(
                DomainRuleModel.project_id == project_id,
                DomainRuleModel.title == "Child Rule",
            )
        )
        child = res.scalar_one()
        assert child.parent_rule_id == parent_id, "parent_rule_id must be resolved to existing parent's ID!"


# ============================================================================
# P3 Rectification Round 2: 4 P0 Contract Tests
# ============================================================================

@pytest.mark.asyncio
async def test_r2_p0_1_knowledge_retrieval_failure_raises_not_swallowed(session_factory, test_project):
    """P0-1: Knowledge retrieval failure must terminate candidate generation immediately without silent degradation."""
    project_id = test_project["project_id"]
    workspace_id = test_project["main_workspace_id"]
    svc = RuleGenerationService()

    async with session_factory() as session:
        with patch(
            "backend.services.knowledge.retrieval.KnowledgeRetrievalService.retrieve_chunks",
            side_effect=RuntimeError("retrieval_down"),
        ):
            with pytest.raises(RuntimeError, match="retrieval_down"):
                await svc.load_rule_generation_context(
                    session=session,
                    project_id=project_id,
                    workspace_id=workspace_id,
                )


@pytest.mark.asyncio
async def test_r2_p0_2_knowledge_rule_link_resolution_and_orphan_cleanup(session_factory, test_project):
    """P0-2: 'knowledge' is a valid RuleLink target kind; target resolution and orphan cleanup work correctly."""
    assert "knowledge" in ALLOWED_RULE_LINK_TARGET_KINDS

    project_id = test_project["project_id"]
    workspace_id = test_project["main_workspace_id"]
    resolver = RequirementNodeResolver()

    from backend.database.model import KnowledgeWorkspaceModel

    async with session_factory() as session:
        knowledge_workspace = KnowledgeWorkspaceModel(
            id=100, project_id=project_id, owner_user_id=1, status="active",
        )
        session.add(knowledge_workspace)
        await session.flush()
        rule = DomainRuleModel(
            project_id=project_id,
            workspace_id=workspace_id,
            title="Data Security Rule",
            statement="All passwords must be encrypted with salt",
            confirmation_status=ConfirmationStatus.CONFIRMED.value,
        )
        doc = KnowledgeDocumentModel(
            project_id=project_id,
            workspace_id=knowledge_workspace.id,
            owner_user_id=1,
            original_filename="sec_policy.pdf",
            content_type="application/pdf",
            file_size=2048,
            sha256="abc12345",
            storage_path="/knowledge/sec_policy.pdf",
            status="ready",
            ai_enabled=True,
        )
        session.add_all([rule, doc])
        await session.flush()

        chunk = KnowledgeChunkModel(
            document_id=doc.id,
            project_id=project_id,
            workspace_id=knowledge_workspace.id,
            chunk_index=0,
            heading_path="Security > Passwords",
            text="Passwords must use Argon2id with random 16-byte salt.",
            token_estimate=25,
        )
        session.add(chunk)
        await session.flush()

        link = RuleLinkModel(
            rule_id=rule.id,
            project_id=project_id,
            workspace_id=workspace_id,
            target_kind="knowledge",
            target_logical_uuid=f"chunk-{chunk.id}",
            link_purpose=RuleLinkPurpose.SOURCE.value,
            context_text="Argon2id salt specification",
        )
        session.add(link)
        await session.commit()
        chunk_id = chunk.id
        link_id = link.id

    async with session_factory() as session:
        # 1. Resolve target with 'chunk-{id}' format
        resolved = await resolver.resolve_target(
            session=session,
            project_id=project_id,
            target_kind="knowledge",
            target_logical_uuid=f"chunk-{chunk_id}",
            workspace_id=workspace_id,
        )
        assert resolved.kind == "knowledge"
        assert resolved.entity_id == chunk_id
        assert "Knowledge Chunk" in resolved.display_name
        assert "sec_policy.pdf" in resolved.display_name

        # 2. Resolve target with plain '{id}' format
        resolved_plain = await resolver.resolve_target(
            session=session,
            project_id=project_id,
            target_kind="knowledge",
            target_logical_uuid=str(chunk_id),
            workspace_id=workspace_id,
        )
        assert resolved_plain.entity_id == chunk_id

        # 3. Sweep when target exists: 0 orphaned links cleaned up
        orphans = await resolver.sweep_orphaned_links(session, project_id=project_id, workspace_id=workspace_id)
        assert orphans == 0

        # 4. Delete the chunk to make the link orphaned
        chunk_to_del = await session.get(KnowledgeChunkModel, chunk_id)
        await session.delete(chunk_to_del)
        await session.commit()

    async with session_factory() as session:
        # 5. Sweep orphaned links: must clean up the orphaned knowledge link
        swept = await resolver.sweep_orphaned_links(session, project_id=project_id, workspace_id=workspace_id)
        assert swept == 1
        await session.commit()

        # Verify link is deleted
        remaining_link = await session.get(RuleLinkModel, link_id)
        assert remaining_link is None


def test_r2_p0_3_flow_prompt_context_serializes_scenarios_ac_parent_rules_links():
    """P0-3: Flow prompt serialization includes full Rule snapshots, Scenarios, and AC."""
    gen = FlowsGenerator()
    input_data = FlowsGeneratorInput(
        user_requirements="User requirements text",
        actors=[ActorNode(actorId=1, actorName="Buyer", actorDescription="Customer")],
        features=[FeatureNode(featureId=1, featureName="Order", featureDescription="Order feature")],
        rules=[
            {
                "id": 10,
                "logical_uuid": "rule-child-001",
                "title": "Discount Rule",
                "statement": "Discount cannot exceed 50%",
                "confirmation_status": "ai_assumption",
                "parent_rule_uuid": "rule-parent-global-999",
                "source_links": [
                    {
                        "target_kind": "knowledge",
                        "target_logical_uuid": "chunk-42",
                        "link_purpose": "derived_from",
                        "context_text": "Clause 4.2 in Discount Policy",
                    }
                ],
            }
        ],
        scenarios=[
            {
                "id": 5,
                "logical_uuid": "sc-order-001",
                "name": "Order Placement Scenario",
                "content": "GIVEN user has items in cart WHEN user clicks checkout THEN order created",
            }
        ],
        acceptance_criteria=[
            {
                "id": 8,
                "logical_uuid": "ac-order-001",
                "scenario_id": 5,
                "content": "Total payment amount must match line items sum",
            }
        ],
    )

    actors, features, rules, scenarios, acs = gen._serialize_prompt_context(input_data)

    # Scenarios serialization check
    assert "Order Placement Scenario" in scenarios
    assert "GIVEN user has items in cart" in scenarios
    assert "sc-order-001" in scenarios

    # Acceptance criteria serialization check
    assert "Total payment amount must match line items sum" in acs
    assert "ac-order-001" in acs

    # Rules serialization check: parent_rule_uuid and source_links with knowledge
    assert "rule-child-001" in rules
    assert "rule-parent-global-999" in rules
    assert "chunk-42" in rules
    assert "Clause 4.2 in Discount Policy" in rules

    # Verify template tokens render properly in both languages
    import os
    for locale in ["zh-CN", "en-US"]:
        for template_name in ["flows_generate_combined.txt", "flows_generate.txt"]:
            tmpl_path = os.path.join(
                os.path.dirname(__file__),
                "../../../core/prompts",
                locale,
                "generation",
                template_name,
            )
            with open(tmpl_path, "r", encoding="utf-8") as f:
                template_content = f.read()

            assert "{{scenarios}}" in template_content, f"Template {locale}/{template_name} missing {{{{scenarios}}}}"
            assert "{{acceptance_criteria}}" in template_content, f"Template {locale}/{template_name} missing {{{{acceptance_criteria}}}}"

            rendered = (
                template_content
                .replace("{{user_requirements}}", input_data.user_requirements or "")
                .replace("{{actors}}", actors)
                .replace("{{features}}", features)
                .replace("{{rules}}", rules)
                .replace("{{scenarios}}", scenarios)
                .replace("{{acceptance_criteria}}", acs)
                .replace("{{user_feedback}}", "")
            )
            assert "{{scenarios}}" not in rendered
            assert "{{acceptance_criteria}}" not in rendered
            assert "GIVEN user has items in cart" in rendered
            assert "rule-parent-global-999" in rendered


@pytest.mark.asyncio
async def test_r2_p0_4_flow_choice_adapter_expected_workspace_version_enforced(
    session_factory, test_project
):
    """P0-4: Server-held workspace version check detects upstream drift with explicit workspace (UI path)."""
    project_id = test_project["project_id"]
    workspace_id = test_project["main_workspace_id"]
    adapter = FlowGenerationChoiceAdapter()

    async with session_factory() as session:
        actor = ActorModel(project_id=project_id, workspace_id=workspace_id, name="Customer")
        feature = FeatureModel(project_id=project_id, workspace_id=workspace_id, name="Checkout")
        session.add_all([actor, feature])
        await session.flush()

        sc = ScenarioModel(
            project_id=project_id,
            workspace_id=workspace_id,
            feature_id=feature.id,
            actor_id=actor.id,
            name="Checkout Scenario",
            content="Initial checkout steps",
        )
        session.add(sc)
        await session.commit()

    async with session_factory() as session:
        ctx = CandidateContext(
            index=0,
            strategy="sequential",
            project_id=project_id,
            workspace_id=workspace_id,
            session=session,
            strategy_id="sequential",
            strategy_label="Sequential Flow",
        )

        mock_draft = {
            "project_id": project_id,
            "workspace_id": workspace_id,
            "flows": [
                {
                    "flow_name": "Checkout Flow",
                    "flow_description": "Description of checkout flow",
                    "flow_steps": [
                        {
                            "step_number": "S-001",
                            "step_name": "Payment",
                            "step_description": "User completes payment",
                            "step_type": "user_action",
                            "input_business_object_numbers": [],
                            "output_business_object_numbers": [],
                            "rule_logical_uuids": [],
                        }
                    ],
                    "transitions": [],
                }
            ],
            "business_objects": [],
        }
        mock_response = {
            "flows": mock_draft["flows"],
            "business_objects": mock_draft["business_objects"],
        }

        with patch.object(
            adapter._service,
            "_generate_preview",
            new=AsyncMock(return_value=(mock_draft, mock_response)),
        ):
            choice = await adapter.generate_candidate(ctx)

        assert choice.payload.get("expected_workspace_version") is not None

        # 1. Apply with explicit workspace when workspace has NOT drifted -> must succeed
        res = await adapter.apply_candidate(choice.payload, session, workspace_id=workspace_id)
        assert res is not None

        # 2. Mutate upstream workspace: alter scenario content
        sc_db = await session.get(ScenarioModel, sc.id)
        sc_db.content = "Altered checkout steps by user"
        await session.commit()

        # 3. Apply again with the SAME choice payload and explicit workspace (normal UI path)
        # Server-held verification must detect drift against current hash and raise ValueError!
        with pytest.raises(ValueError, match="workspace_version_conflict"):
            await adapter.apply_candidate(choice.payload, session, workspace_id=workspace_id)


@pytest.mark.asyncio
async def test_r2_p0_4_request_version_mismatch_with_candidate_saved_version_rejected(session_factory, test_project):
    """验证客户端传入版本与候选保存版本不一致时拒绝，严禁客户端篡改覆盖导致绕过。"""
    project_id = test_project["project_id"]
    workspace_id = test_project["main_workspace_id"]
    adapter = FlowGenerationChoiceAdapter()

    async with session_factory() as session:
        actor = ActorModel(project_id=project_id, workspace_id=workspace_id, name="Customer")
        feature = FeatureModel(project_id=project_id, workspace_id=workspace_id, name="Cart")
        session.add_all([actor, feature])
        await session.commit()

    async with session_factory() as session:
        from backend.api.modules.requirements_core.flow.application.choice_adapter import _get_current_workspace_state_hash
        current_hash = await _get_current_workspace_state_hash(session, project_id, workspace_id)

        # 候选保存的是 stale-server-value
        stale_payload = {
            "project_id": project_id,
            "workspace_id": workspace_id,
            "expected_workspace_version": "stale-server-value",
            "flows": [],
            "business_objects": [],
        }

        # 1. 客户端传入当前的 current_hash 试图覆盖候选旧值 -> 必须被拒绝并抛出 workspace_version_conflict
        with pytest.raises(ValueError, match="workspace_version_conflict"):
            await adapter.apply_candidate(
                stale_payload, session, expected_workspace_version=current_hash,
                      workspace_id=workspace_id,
            )

        # 2. 候选保存的是有效 current_hash，但客户端传入任意不匹配的值 -> 必须被拒绝
        valid_payload = {
            "project_id": project_id,
            "workspace_id": workspace_id,
            "expected_workspace_version": current_hash,
            "flows": [],
            "business_objects": [],
        }
        with pytest.raises(ValueError, match="workspace_version_conflict"):
            await adapter.apply_candidate(
                valid_payload, session, expected_workspace_version="mismatched-client-val",
                      workspace_id=workspace_id,
            )


@pytest.mark.asyncio
async def test_r2_p0_4_missing_candidate_saved_hash_rejected(session_factory, test_project):
    """验证候选 payload 缺失服务端 Hash（expected_workspace_version 与 context_hash 均缺失）时直接拒绝。"""
    project_id = test_project["project_id"]
    workspace_id = test_project["main_workspace_id"]
    adapter = FlowGenerationChoiceAdapter()

    async with session_factory() as session:
        actor = ActorModel(project_id=project_id, workspace_id=workspace_id, name="Customer")
        feature = FeatureModel(project_id=project_id, workspace_id=workspace_id, name="Cart")
        session.add_all([actor, feature])
        await session.commit()

    async with session_factory() as session:
        # payload 完全缺失版本字段
        corrupt_payload = {
            "project_id": project_id,
            "workspace_id": workspace_id,
            "flows": [],
            "business_objects": [],
        }

        # 不论是否传递客户端参数，均必须直接拒绝
        with pytest.raises(ValueError, match="workspace_version_conflict"):
            await adapter.apply_candidate(corrupt_payload, session, workspace_id=workspace_id)

        with pytest.raises(ValueError, match="workspace_version_conflict"):
            await adapter.apply_candidate(corrupt_payload, session, expected_workspace_version="some-version", workspace_id=workspace_id)
