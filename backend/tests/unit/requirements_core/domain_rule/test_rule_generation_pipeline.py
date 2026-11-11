"""Unit tests for RuleGenerationService and RuleGenerationChoiceAdapter."""

import json
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.modules.decision_workflow.candidate_generation.application.generation_choice_service import (
    CandidateContext,
)
from backend.api.modules.requirements_core.domain_rule.application.choice_adapter import (
    RuleGenerationChoiceAdapter,
)
from backend.api.modules.requirements_core.domain_rule.application.rule_generation_service import (
    RuleGenerationService,
)
from backend.database.database import Base
from backend.core.generators.rules_generator import RulesGenerator, RulesGeneratorInput
from backend.database.model import (
    BranchWorkspaceModel,
    DomainRuleModel,
    ProjectModel,
    RequirementBranchModel,
    RuleLinkModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
)


@pytest_asyncio.fixture
async def session_factory():
    """Create in-memory SQLite database."""
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
async def seeded_test_project(session_factory):
    async with session_factory() as session:
        project = ProjectModel(
            name="Rule Generation Test Project",
            owner_user_id=1,
            user_requirements="The user needs to pay for orders. Orders over $100 get free shipping.",
        )
        session.add(project)
        await session.flush()

        branch = RequirementBranchModel(
            project_id=project.id,
            name="main",
            created_by_user_id=1,
        )
        session.add(branch)
        await session.flush()

        workspace = BranchWorkspaceModel(
            project_id=project.id,
            branch_id=branch.id,
            user_requirements=project.user_requirements,
        )
        session.add(workspace)
        await session.flush()

        from backend.database.model import ActorModel, FeatureModel
        actor = ActorModel(
            project_id=project.id,
            workspace_id=workspace.id,
            name="Customer",
            description="End user buying products",
        )
        session.add(actor)
        await session.flush()

        feature = FeatureModel(
            project_id=project.id,
            workspace_id=workspace.id,
            name="Payment Feature",
            description="Payment and checkout management",
        )
        session.add(feature)
        await session.flush()

        scenario = ScenarioModel(
            project_id=project.id,
            workspace_id=workspace.id,
            feature_id=feature.id,
            actor_id=actor.id,
            name="Checkout with high total",
            content="Given order total is $150, When user proceeds to checkout, Then shipping fee is waived.",
        )
        session.add(scenario)
        await session.flush()

        ac = ScenarioAcceptanceCriterionModel(
            workspace_id=workspace.id,
            scenario_id=scenario.id,
            position=1,
            content="Shipping fee is waived when total > 100",
        )
        session.add(ac)
        await session.commit()

        return project.id, workspace.id, scenario.id, scenario.logical_uuid, ac.id, ac.logical_uuid


@pytest.mark.asyncio
async def test_load_rule_generation_context(session_factory, seeded_test_project):
    """Verify that rule generation context loads project requirements, scenarios, and acceptance criteria."""
    project_id, workspace_id, scenario_id, scenario_uuid, ac_id, ac_uuid = seeded_test_project
    service = RuleGenerationService()

    async with session_factory() as session:
        input_data, context_hash = await service.load_rule_generation_context(
            session=session,
            project_id=project_id,
            workspace_id=workspace_id,
        )

        assert "free shipping" in input_data.user_requirements
        assert len(input_data.scenarios) == 1
        assert input_data.scenarios[0]["id"] == scenario_id
        assert input_data.scenarios[0]["name"] == "Checkout with high total"
        assert len(input_data.acceptance_criteria) == 1
        assert input_data.acceptance_criteria[0]["scenario_id"] == scenario_id
        assert input_data.acceptance_criteria[0]["content"] == "Shipping fee is waived when total > 100"
        assert context_hash != ""


@pytest.mark.asyncio
async def test_rules_generator_resolves_local_source_refs_to_canonical_ids():
    generator = RulesGenerator()
    input_data = RulesGeneratorInput(
        user_requirements="Orders require approval.",
        scenarios=[
            {
                "id": 10,
                "logical_uuid": "scenario-canonical-uuid",
                "name": "Approve order",
                "content": "Given an order requires approval",
            }
        ],
        acceptance_criteria=[
            {
                "id": 20,
                "logical_uuid": "criterion-canonical-uuid",
                "scenario_id": 10,
                "content": "Then the approver must be recorded",
            }
        ],
        knowledge_fragments=[
            {
                "fragment_id": "chunk-42",
                "document_name": "approval-policy.pdf",
                "content": "Approval is required above the threshold.",
            }
        ],
    )
    prompt = generator._build_prompt(input_data)
    assert "SCN-1" in prompt
    assert "AC-1" in prompt
    assert "KNOW-1" in prompt
    assert "scenario-canonical-uuid" not in prompt
    assert "criterion-canonical-uuid" not in prompt
    assert "chunk-42" not in prompt

    generator._llm_handler.call_llm = AsyncMock(
        return_value=json.dumps(
            {
                "rules": [
                    {
                        "temp_id": "rule-1",
                        "title": "Approval audit rule",
                        "statement": "Every approval must record its approver.",
                        "parent_rule_ref": None,
                        "confirmation_status": "ai_assumption",
                        "source_links": [
                            {
                                "target_kind": "acceptance_criterion",
                                "target_ref": "AC-1",
                                "context_text": "The approver must be recorded",
                            }
                        ],
                    }
                ]
            }
        )
    )

    result = await generator.generate(input_data)

    assert result["rules"][0]["source_links"] == [
        {
            "target_kind": "acceptance_criterion",
            "target_logical_uuid": "criterion-canonical-uuid",
            "context_text": "The approver must be recorded",
        }
    ]


@pytest.mark.asyncio
async def test_rules_generator_rejects_unknown_local_source_ref():
    generator = RulesGenerator()
    input_data = RulesGeneratorInput(
        user_requirements="Orders require approval.",
        acceptance_criteria=[
            {
                "logical_uuid": "criterion-canonical-uuid",
                "content": "The approver must be recorded",
            }
        ],
    )
    generator._llm_handler.call_llm = AsyncMock(
        return_value=json.dumps(
            {
                "rules": [
                    {
                        "temp_id": "rule-1",
                        "title": "Approval audit rule",
                        "statement": "Every approval must record its approver.",
                        "parent_rule_ref": None,
                        "confirmation_status": "ai_assumption",
                        "source_links": [
                            {
                                "target_kind": "acceptance_criterion",
                                "target_ref": "AC-9999",
                                "context_text": None,
                            }
                        ],
                    }
                ]
            }
        )
    )

    with pytest.raises(ValueError, match="invalid_source_reference"):
        await generator.generate(input_data)

    assert generator._llm_handler.call_llm.await_count == 2


@pytest.mark.asyncio
async def test_rules_generator_retries_invalid_source_ref_with_exact_catalog():
    generator = RulesGenerator()
    input_data = RulesGeneratorInput(
        user_requirements="Orders require approval.",
        acceptance_criteria=[
            {
                "logical_uuid": "criterion-canonical-uuid",
                "content": "The approver must be recorded",
            }
        ],
    )
    invalid_response = json.dumps(
        {
            "rules": [
                {
                    "temp_id": "rule-1",
                    "title": "Approval audit rule",
                    "statement": "Every approval must record its approver.",
                    "parent_rule_ref": None,
                    "source_links": [
                        {
                            "target_kind": "acceptance_criterion",
                            "target_ref": "AC-001",
                            "context_text": None,
                        }
                    ],
                }
            ]
        }
    )
    valid_response = invalid_response.replace('"AC-001"', '"AC-1"')
    generator._llm_handler.call_llm = AsyncMock(
        side_effect=[invalid_response, valid_response]
    )

    result = await generator.generate(input_data)

    assert result["rules"][0]["source_links"][0]["target_logical_uuid"] == (
        "criterion-canonical-uuid"
    )
    retry_query = generator._llm_handler.call_llm.await_args_list[1].kwargs["query"]
    assert "AC-1" in retry_query
    assert "Do not output UUIDs" in retry_query


@pytest.mark.asyncio
async def test_rules_generator_canonicalizes_duplicate_source_links():
    generator = RulesGenerator()
    input_data = RulesGeneratorInput(
        user_requirements="Certificates must be validated.",
        scenarios=[
            {
                "logical_uuid": "scenario-uuid",
                "name": "Maintain certificate",
                "content": "The administrator edits certificate information.",
            }
        ],
    )
    generator._llm_handler.call_llm = AsyncMock(
        return_value=json.dumps(
            {
                "rules": [
                    {
                        "temp_id": "rule-1",
                        "title": "Certificate validation",
                        "statement": "Certificate fields must be validated before saving.",
                        "parent_rule_ref": None,
                        "source_links": [
                            {
                                "target_kind": "scenario",
                                "target_ref": "SCN-1",
                                "context_text": "Edit certificate",
                            },
                            {
                                "target_kind": "scenario",
                                "target_ref": "SCN-1",
                                "context_text": "The administrator edits certificate information.",
                            },
                        ],
                    }
                ]
            }
        )
    )

    result = await generator.generate(input_data)

    assert result["rules"][0]["source_links"] == [
        {
            "target_kind": "scenario",
            "target_logical_uuid": "scenario-uuid",
            "context_text": "The administrator edits certificate information.",
        }
    ]


@pytest.mark.asyncio
async def test_rule_candidate_apply_persists_duplicate_source_once(
    session_factory,
    seeded_test_project,
):
    project_id, workspace_id, _, scenario_uuid, _, _ = seeded_test_project
    payload = {
        "project_id": project_id,
        "workspace_id": workspace_id,
        "rules": [
            {
                "temp_id": "rule-1",
                "title": "Certificate validation",
                "statement": "Certificate fields must be validated before saving.",
                "source_links": [
                    {
                        "target_kind": "scenario",
                        "target_logical_uuid": scenario_uuid,
                        "context_text": "Edit certificate",
                    },
                    {
                        "target_kind": "scenario",
                        "target_logical_uuid": scenario_uuid,
                        "context_text": "The administrator edits certificate information.",
                    },
                ],
            }
        ],
    }

    async with session_factory() as session:
        result = await RuleGenerationChoiceAdapter().apply_candidate(payload, session, workspace_id=workspace_id)
        links = (await session.execute(select(RuleLinkModel))).scalars().all()

    assert result["rule_count"] == 1
    assert len(links) == 1
    assert links[0].context_text == "The administrator edits certificate information."


@pytest.mark.asyncio
async def test_generate_rules_service(session_factory, seeded_test_project):
    """Verify rule generation service invokes generator and formats results."""
    project_id, workspace_id, scenario_id, scenario_uuid, ac_id, ac_uuid = seeded_test_project
    service = RuleGenerationService()

    mock_llm_response = {
        "rules": [
            {
                "temp_id": "RULE-001",
                "title": "Free Shipping Threshold",
                "statement": "When order amount exceeds $100, shipping fee is $0.",
                "rationale": "Marketing incentive for larger orders.",
                "source_links": [
                    {
                        "target_kind": "scenario",
                        "target_logical_uuid": scenario_uuid,
                        "description": "Applies to high total checkout",
                    }
                ],
            }
        ]
    }

    with patch(
        "backend.core.generators.rules_generator.RulesGenerator.generate",
        new_callable=AsyncMock,
    ) as mock_generate:
        mock_generate.return_value = mock_llm_response

        async with session_factory() as session:
            result, context_hash = await service.generate_rules(
                session=session,
                project_id=project_id,
                workspace_id=workspace_id,
            )

            assert len(result["rules"]) == 1
            rule = result["rules"][0]
            assert rule["temp_id"] == "RULE-001"
            assert rule["title"] == "Free Shipping Threshold"
            assert rule["statement"] == "When order amount exceeds $100, shipping fee is $0."
            assert len(rule["source_links"]) == 1
            assert rule["source_links"][0]["target_logical_uuid"] == scenario_uuid
            assert context_hash != ""


@pytest.mark.asyncio
async def test_rule_generation_choice_adapter_apply_candidate(session_factory, seeded_test_project):
    """Verify RuleGenerationChoiceAdapter applies candidates and creates domain rules with source links."""
    project_id, workspace_id, scenario_id, scenario_uuid, ac_id, ac_uuid = seeded_test_project
    adapter = RuleGenerationChoiceAdapter()

    payload = {
        "project_id": project_id,
        "workspace_id": workspace_id,
        "rules": [
            {
                "temp_id": "RULE-001",
                "title": "Free Shipping Threshold",
                "statement": "When order amount exceeds $100, shipping fee is $0.",
                "rationale": "Marketing incentive for larger orders.",
                "source_links": [
                    {
                        "target_kind": "scenario",
                        "target_logical_uuid": scenario_uuid,
                        "description": "Applies to high total checkout",
                    }
                ],
            }
        ],
    }

    async with session_factory() as session:
        applied = await adapter.apply_candidate(payload, session, project_id=project_id, workspace_id=workspace_id)
        await session.commit()

        assert applied["rule_count"] == 1

        # Check persisted domain rule
        rule_stmt = select(DomainRuleModel).where(
            DomainRuleModel.project_id == project_id,
            DomainRuleModel.workspace_id == workspace_id,
        )
        res = await session.execute(rule_stmt)
        rules = res.scalars().all()
        assert len(rules) == 1
        rule = rules[0]
        assert rule.title == "Free Shipping Threshold"
        assert rule.statement == "When order amount exceeds $100, shipping fee is $0."
        assert rule.confirmation_status == "ai_assumption"

        # Check persisted source link
        link_stmt = select(RuleLinkModel).where(
            RuleLinkModel.rule_id == rule.id,
        )
        link_res = await session.execute(link_stmt)
        links = link_res.scalars().all()
        assert len(links) == 1
        link = links[0]
        assert link.target_kind == "scenario"
        assert link.target_logical_uuid == scenario_uuid
        assert link.link_purpose == "source"


@pytest.mark.asyncio
async def test_rule_generation_choice_adapter_deduplication():
    """Verify statement fingerprint deduplication for rule candidates."""
    adapter = RuleGenerationChoiceAdapter()

    candidate1 = AsyncMock()
    candidate1.payload = {
        "rules": [
            {"statement": "Users must be at least 18 years old."}
        ]
    }

    candidate2_same = AsyncMock()
    candidate2_same.payload = {
        "rules": [
            {"statement": "users must be at least 18 years old. "}
        ]
    }

    candidate3_diff = AsyncMock()
    candidate3_diff.payload = {
        "rules": [
            {"statement": "Orders require valid credit card."}
        ]
    }

    assert adapter.is_duplicate(candidate2_same, [candidate1]) is True
    assert adapter.is_duplicate(candidate3_diff, [candidate1]) is False
