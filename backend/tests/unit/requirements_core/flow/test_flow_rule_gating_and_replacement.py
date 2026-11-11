"""Unit tests for flow generation rule gating and replace_flow_set semantics."""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.modules.requirements_core.flow.application.choice_adapter import (
    FlowGenerationChoiceAdapter,
)
from backend.api.modules.requirements_core.generation_context import (
    load_flow_generation_context,
)
from backend.database.database import Base
from backend.database.model import (
    ActorModel,
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
    RuleLinkPurpose,
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
async def flow_test_project(session_factory):
    async with session_factory() as session:
        project = ProjectModel(
            name="Flow Gating Test Project",
            owner_user_id=1,
            user_requirements="Order payment and delivery management.",
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

        actor = ActorModel(
            project_id=project.id,
            workspace_id=workspace.id,
            name="Customer",
            description="Buyer",
        )
        session.add(actor)
        await session.flush()

        feature = FeatureModel(
            project_id=project.id,
            workspace_id=workspace.id,
            name="Payment Feature",
            description="Payment management",
        )
        session.add(feature)
        await session.flush()

        scenario = ScenarioModel(
            project_id=project.id,
            workspace_id=workspace.id,
            feature_id=feature.id,
            actor_id=actor.id,
            name="Pay Order",
            content="Given order ready, When pay, Then success.",
        )
        session.add(scenario)
        await session.flush()

        ac = ScenarioAcceptanceCriterionModel(
            workspace_id=workspace.id,
            scenario_id=scenario.id,
            position=1,
            content="Payment executes within 2s",
        )
        session.add(ac)
        await session.flush()

        rule = DomainRuleModel(
            project_id=project.id,
            workspace_id=workspace.id,
            title="Payment Security",
            statement="Card must have 3D Secure enabled.",
            confirmation_status=ConfirmationStatus.CONFIRMED.value,
        )
        session.add(rule)
        await session.commit()

        return project.id, workspace.id, rule.id, rule.logical_uuid


@pytest.mark.asyncio
async def test_flow_context_requires_domain_rule(session_factory, flow_test_project):
    """Verify flow generation fails fast when the workspace has no rules."""
    project_id, workspace_id, rule_id, rule_uuid = flow_test_project

    async with session_factory() as session:
        rule = await session.get(DomainRuleModel, rule_id)
        await session.delete(rule)
        await session.flush()
        with pytest.raises(ValueError) as exc_info:
            await load_flow_generation_context(
                session=session,
                project_id=project_id,
                workspace_id=workspace_id,
            )
        assert "domain_rule_required" in str(exc_info.value)


@pytest.mark.asyncio
async def test_flow_context_succeeds_with_domain_rule(session_factory, flow_test_project):
    """Verify flow generation context is available when a rule exists."""
    project_id, workspace_id, rule_id, rule_uuid = flow_test_project

    async with session_factory() as session:
        context = await load_flow_generation_context(
            session=session,
            project_id=project_id,
            workspace_id=workspace_id,
        )

        assert len(context.rules) == 1
        assert context.rules[0]["logical_uuid"] == rule_uuid
        assert context.rules[0]["title"] == "Payment Security"


@pytest.mark.asyncio
async def test_replace_flow_set_preserves_confirmed_business_objects(
    session_factory, flow_test_project
):
    """Verify apply_candidate cascades delete only to flows, steps, transitions and their links,

    while strictly PRESERVING existing confirmed BusinessObjectModel entities.
    """
    project_id, workspace_id, rule_id, rule_uuid = flow_test_project

    async with session_factory() as session:
        # Pre-seed existing confirmed business object
        existing_bo = BusinessObjectModel(
            project_id=project_id,
            workspace_id=workspace_id,
            name="ConfirmedOrder",
            description="Existing order object that must not be deleted",
            confirmation_status=ConfirmationStatus.CONFIRMED.value,
        )
        session.add(existing_bo)

        # Pre-seed existing flow to be replaced
        old_flow = FlowModel(
            project_id=project_id,
            workspace_id=workspace_id,
            name="Old Flow To Replace",
            description="Old flow description",
        )
        session.add(old_flow)
        await session.flush()

        old_step1 = FlowStepModel(
            workspace_id=workspace_id,
            flow_id=old_flow.id,
            position=1,
            name="Old Step 1",
            description="Old step 1 desc",
            step_type="actorAction",
        )
        old_step2 = FlowStepModel(
            workspace_id=workspace_id,
            flow_id=old_flow.id,
            position=2,
            name="Old Step 2",
            description="Old step 2 desc",
            step_type="systemAction",
        )
        session.add_all([old_step1, old_step2])
        await session.flush()

        old_transition = FlowTransitionModel(
            flow_id=old_flow.id,
            project_id=project_id,
            workspace_id=workspace_id,
            source_step_id=old_step1.id,
            target_step_id=old_step2.id,
            label="Old transition",
            condition_text="true",
            is_default=True,
            semantic_tags=[],
        )
        session.add(old_transition)
        await session.flush()

        old_link = RuleLinkModel(
            project_id=project_id,
            workspace_id=workspace_id,
            rule_id=rule_id,
            target_kind="flow_transition",
            target_logical_uuid=old_transition.logical_uuid,
            link_purpose=RuleLinkPurpose.APPLIES_TO.value,
            context_text="Applies to old transition",
        )
        session.add(old_link)
        await session.commit()

        # Build candidate payload with new flow and new business object
        from backend.api.modules.requirements_core.flow.application.choice_adapter import _get_current_workspace_state_hash
        current_hash = await _get_current_workspace_state_hash(session, project_id, workspace_id)
        payload = {
            "project_id": project_id,
            "workspace_id": workspace_id,
            "expected_workspace_version": current_hash,
            "flows": [
                {
                    "flow_name": "New Modern Flow",
                    "flow_description": "New modern payment flow",
                    "rule_refs": [rule_uuid, rule_uuid],
                    "feature_ids": [],
                    "flow_steps": [
                        {
                            "step_number": "S-NEW-1",
                            "step_name": "New Step 1",
                            "step_description": "Initiate payment",
                            "rule_refs": [rule_uuid, rule_uuid],
                            "step_type": "actorAction",
                            "actor_ids": [],
                            "input_business_object_numbers": ["BO-001"],
                            "output_business_object_numbers": [],
                        },
                        {
                            "step_number": "S-NEW-2",
                            "step_name": "New Step 2",
                            "step_description": "Complete payment",
                            "step_type": "systemAction",
                            "actor_ids": [],
                            "input_business_object_numbers": [],
                            "output_business_object_numbers": [],
                        },
                    ],
                    "transitions": [
                        {
                            "source_step_number": "S-NEW-1",
                            "target_step_number": "S-NEW-2",
                            "label": "Card Verified",
                            "condition_text": "3D Secure passed",
                            "is_default": True,
                            "semantic_tags": ["security"],
                            "rule_refs": [rule_uuid],
                        }
                    ],
                }
            ],
            "business_objects": [
                {
                    "business_object_number": "BO-001",
                    "business_object_name": "PaymentToken",
                    "business_object_description": "New payment token object",
                    "business_object_attributes": [],
                }
            ],
        }

        adapter = FlowGenerationChoiceAdapter()
        applied = await adapter.apply_candidate(
            payload, session, project_id=project_id, workspace_id=workspace_id
        )
        await session.commit()

        assert applied["flow_count"] == 1

        # 1. Verify old flow, steps, and transitions are deleted
        old_flows_res = await session.execute(
            select(FlowModel).where(
                FlowModel.project_id == project_id,
                FlowModel.workspace_id == workspace_id,
                FlowModel.name == "Old Flow To Replace",
            )
        )
        assert old_flows_res.scalars().first() is None

        old_steps_res = await session.execute(
            select(FlowStepModel).where(
                FlowStepModel.logical_uuid.in_([old_step1.logical_uuid, old_step2.logical_uuid]),
            )
        )
        assert len(old_steps_res.scalars().all()) == 0

        old_transitions_res = await session.execute(
            select(FlowTransitionModel).where(
                FlowTransitionModel.logical_uuid == old_transition.logical_uuid,
            )
        )
        assert len(old_transitions_res.scalars().all()) == 0

        # 2. Verify old rule link to old transition was cleaned up
        old_link_res = await session.execute(
            select(RuleLinkModel).where(
                RuleLinkModel.project_id == project_id,
                RuleLinkModel.workspace_id == workspace_id,
                RuleLinkModel.target_logical_uuid == old_transition.logical_uuid,
            )
        )
        assert old_link_res.scalars().first() is None

        # 3. CRITICAL: Verify confirmed business object was PRESERVED!
        bo_res = await session.execute(
            select(BusinessObjectModel).where(
                BusinessObjectModel.project_id == project_id,
                BusinessObjectModel.workspace_id == workspace_id,
                BusinessObjectModel.name == "ConfirmedOrder",
            )
        )
        preserved_bo = bo_res.scalars().first()
        assert preserved_bo is not None
        assert preserved_bo.confirmation_status == ConfirmationStatus.CONFIRMED.value

        # 4. Verify new flow and its transitions and rule links exist
        new_flow_res = await session.execute(
            select(FlowModel).where(
                FlowModel.project_id == project_id,
                FlowModel.workspace_id == workspace_id,
                FlowModel.name == "New Modern Flow",
            )
        )
        new_flow = new_flow_res.scalars().first()
        assert new_flow is not None

        new_trans_res = await session.execute(
            select(FlowTransitionModel).where(
                FlowTransitionModel.flow_id == new_flow.id,
            )
        )
        new_transitions = new_trans_res.scalars().all()
        assert len(new_transitions) == 1
        new_trans = new_transitions[0]
        assert new_trans.label == "Card Verified"

        new_link_res = await session.execute(
            select(RuleLinkModel).where(
                RuleLinkModel.project_id == project_id,
                RuleLinkModel.workspace_id == workspace_id,
                RuleLinkModel.target_kind == "flow_transition",
                RuleLinkModel.target_logical_uuid == new_trans.logical_uuid,
            )
        )
        new_links = new_link_res.scalars().all()
        assert len(new_links) == 1
        assert new_links[0].rule_id == rule_id
        assert new_links[0].link_purpose == RuleLinkPurpose.APPLIES_TO.value
        direct_links = list((await session.execute(select(RuleLinkModel).where(
            RuleLinkModel.workspace_id == workspace_id,
            RuleLinkModel.target_kind.in_(["flow", "flow_step"]),
        ))).scalars().all())
        new_steps = list((await session.execute(select(FlowStepModel).where(
            FlowStepModel.flow_id == new_flow.id,
        ).order_by(FlowStepModel.position))).scalars().all())
        assert {(link.target_kind, link.target_logical_uuid) for link in direct_links} == {
            ("flow", new_flow.logical_uuid), ("flow_step", new_steps[0].logical_uuid),
        }
        assert len(direct_links) == 2
        assert all(link.rule_id == rule_id and link.link_purpose == "applies_to" for link in direct_links)
