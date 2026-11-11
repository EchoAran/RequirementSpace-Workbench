"""Unit and integration tests for FlowTransitionService.

Verifies workspace scoping on list/get/update/delete, cross-boundary validation,
and default transition uniqueness.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.modules.requirements_core.flow.application.flow_transition_service import (
    FlowTransitionService,
)
from backend.api.modules.requirements_core.flow.schemas import (
    FlowTransitionCreateRequest,
    FlowTransitionUpdateRequest,
)
from backend.database.database import Base
from backend.database.model import (
    BranchWorkspaceModel,
    DomainRuleModel,
    FlowModel,
    FlowStepModel,
    FlowTransitionModel,
    ProjectModel,
    RequirementBranchModel,
)
from backend.schemas import FlowStepType


@pytest.fixture
async def async_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _setup_workspace_and_flow(session: AsyncSession):
    project = ProjectModel(owner_user_id=1, name="Test Project", description="Desc", user_requirements="Reqs")
    session.add(project)
    await session.flush()

    branch = RequirementBranchModel(
        project_id=project.id,
        name="main",
    )
    session.add(branch)
    await session.flush()

    workspace = BranchWorkspaceModel(
        project_id=project.id,
        branch_id=branch.id,
        user_requirements="Reqs",
    )
    session.add(workspace)
    await session.flush()

    flow = FlowModel(
        project_id=project.id,
        workspace_id=workspace.id,
        name="Order Flow",
        description="Checkout flow",
    )
    session.add(flow)
    await session.flush()

    step1 = FlowStepModel(
        flow_id=flow.id,
        workspace_id=workspace.id,
        name="Step 1",
        step_type=FlowStepType.ACTOR_ACTION,
        position=0,
    )
    step2 = FlowStepModel(
        flow_id=flow.id,
        workspace_id=workspace.id,
        name="Step 2",
        step_type=FlowStepType.SYSTEM_ACTION,
        position=1,
    )
    step3 = FlowStepModel(
        flow_id=flow.id,
        workspace_id=workspace.id,
        name="Step 3",
        step_type=FlowStepType.SYSTEM_ACTION,
        position=2,
    )
    session.add_all([step1, step2, step3])
    await session.flush()

    return project, workspace, flow, step1, step2, step3


async def test_transition_crud_with_workspace_id(async_session: AsyncSession):
    project, workspace, flow, step1, step2, _ = await _setup_workspace_and_flow(async_session)

    service = FlowTransitionService()

    create_req = FlowTransitionCreateRequest(
        source_step_id=step1.id,
        target_step_id=step2.id,
        label="Proceed",
        condition_text="total > 0",
        is_default=True,
        semantic_tags=["happy_path"],
    )
    created = await service.create_transition(
        project_id=project.id,
        flow_id=flow.id,
        request=create_req,
        session=async_session,
        workspace_id=workspace.id,
    )
    assert created.label == "Proceed"
    assert created.condition_text == "total > 0"
    assert created.is_default is True
    assert created.workspace_id == workspace.id

    transitions = await service.list_transitions(
        project_id=project.id,
        flow_id=flow.id,
        session=async_session,
        workspace_id=workspace.id,
    )
    assert len(transitions) == 1
    assert transitions[0].id == created.id

    transitions_wrong_ws = await service.list_transitions(
        project_id=project.id,
        flow_id=flow.id,
        session=async_session,
        workspace_id=9999,
    )
    assert len(transitions_wrong_ws) == 0

    retrieved = await service.get_transition(
        project_id=project.id,
        flow_id=flow.id,
        transition_id=created.id,
        session=async_session,
        workspace_id=workspace.id,
    )
    assert retrieved.id == created.id

    with pytest.raises(HTTPException) as exc_info:
        await service.get_transition(
            project_id=project.id,
            flow_id=flow.id,
            transition_id=created.id,
            session=async_session,
            workspace_id=9999,
        )
    assert exc_info.value.status_code == 404

    updated = await service.update_transition(
        project_id=project.id,
        flow_id=flow.id,
        transition_id=created.id,
        request=FlowTransitionUpdateRequest(
            label="Updated Label",
            condition_text="total > 100",
        ),
        session=async_session,
        workspace_id=workspace.id,
    )
    assert updated.label == "Updated Label"
    assert updated.condition_text == "total > 100"

    with pytest.raises(HTTPException) as exc_info:
        await service.update_transition(
            project_id=project.id,
            flow_id=flow.id,
            transition_id=created.id,
            request=FlowTransitionUpdateRequest(label="Should Fail"),
            session=async_session,
            workspace_id=9999,
        )
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_transition(
            project_id=project.id,
            flow_id=flow.id,
            transition_id=created.id,
            session=async_session,
            workspace_id=9999,
        )
    assert exc_info.value.status_code == 404

    await service.delete_transition(
        project_id=project.id,
        flow_id=flow.id,
        transition_id=created.id,
        session=async_session,
        workspace_id=workspace.id,
    )

    remaining = await service.list_transitions(
        project_id=project.id,
        flow_id=flow.id,
        session=async_session,
        workspace_id=workspace.id,
    )
    assert len(remaining) == 0


async def test_cross_boundary_step_rejection(async_session: AsyncSession):
    project, workspace, flow, step1, _, _ = await _setup_workspace_and_flow(async_session)

    foreign_branch = RequirementBranchModel(
        project_id=project.id,
        name="foreign-branch",
    )
    async_session.add(foreign_branch)
    await async_session.flush()

    foreign_ws = BranchWorkspaceModel(
        project_id=project.id,
        branch_id=foreign_branch.id,
        user_requirements="",
    )
    async_session.add(foreign_ws)
    await async_session.flush()

    foreign_flow = FlowModel(
        project_id=project.id,
        workspace_id=foreign_ws.id,
        name="Foreign Flow",
        description="",
    )
    async_session.add(foreign_flow)
    await async_session.flush()

    foreign_step = FlowStepModel(
        flow_id=foreign_flow.id,
        workspace_id=foreign_ws.id,
        name="Foreign Step",
        step_type=FlowStepType.ACTOR_ACTION,
        position=0,
    )
    async_session.add(foreign_step)
    await async_session.flush()

    service = FlowTransitionService()

    with pytest.raises(HTTPException) as exc_info:
        await service.create_transition(
            project_id=project.id,
            flow_id=flow.id,
            request=FlowTransitionCreateRequest(
                source_step_id=step1.id,
                target_step_id=foreign_step.id,
            ),
            session=async_session,
            workspace_id=workspace.id,
        )
    assert exc_info.value.status_code == 404


async def test_cross_boundary_rule_rejection(async_session: AsyncSession):
    project, workspace, flow, step1, step2, _ = await _setup_workspace_and_flow(async_session)

    other_project = ProjectModel(owner_user_id=1, name="Other Project", description="", user_requirements="")
    async_session.add(other_project)
    await async_session.flush()

    foreign_rule = DomainRuleModel(
        project_id=other_project.id,
        workspace_id=None,
        title="Foreign Rule",
        statement="Rules from other project",
    )
    async_session.add(foreign_rule)
    await async_session.flush()

    service = FlowTransitionService()

    with pytest.raises(HTTPException) as exc_info:
        await service.create_transition(
            project_id=project.id,
            flow_id=flow.id,
            request=FlowTransitionCreateRequest(
                source_step_id=step1.id,
                target_step_id=step2.id,
                rule_ids=[foreign_rule.id],
            ),
            session=async_session,
            workspace_id=workspace.id,
        )
    assert exc_info.value.status_code == 400


async def test_default_transition_exclusivity_arbitration(async_session: AsyncSession):
    project, workspace, flow, step1, step2, step3 = await _setup_workspace_and_flow(async_session)

    service = FlowTransitionService()

    t1 = await service.create_transition(
        project_id=project.id,
        flow_id=flow.id,
        request=FlowTransitionCreateRequest(
            source_step_id=step1.id,
            target_step_id=step2.id,
            is_default=True,
        ),
        session=async_session,
        workspace_id=workspace.id,
    )
    assert t1.is_default is True

    # Creating second default transition resets the first one
    t2 = await service.create_transition(
        project_id=project.id,
        flow_id=flow.id,
        request=FlowTransitionCreateRequest(
            source_step_id=step1.id,
            target_step_id=step3.id,
            is_default=True,
        ),
        session=async_session,
        workspace_id=workspace.id,
    )
    assert t2.is_default is True

    # Check t1 is now is_default=False
    t1_refreshed = await service.get_transition(
        project_id=project.id,
        flow_id=flow.id,
        transition_id=t1.id,
        session=async_session,
        workspace_id=workspace.id,
    )
    assert t1_refreshed.is_default is False

    # List transitions and verify exactly one default exists for step1
    all_transitions = await service.list_transitions(
        project_id=project.id,
        flow_id=flow.id,
        session=async_session,
        workspace_id=workspace.id,
    )
    defaults = [t for t in all_transitions if t.source_step_id == step1.id and t.is_default]
    assert len(defaults) == 1
    assert defaults[0].id == t2.id


async def test_rule_link_cross_workspace_isolation(async_session: AsyncSession):
    """Verify RuleLinks are strictly scoped to workspace even when logical_uuid is shared across branches."""
    project = ProjectModel(owner_user_id=1, name="Isolation Project", description="Desc", user_requirements="Reqs")
    async_session.add(project)
    await async_session.flush()

    branch1 = RequirementBranchModel(project_id=project.id, name="branch-1")
    branch2 = RequirementBranchModel(project_id=project.id, name="branch-2")
    async_session.add_all([branch1, branch2])
    await async_session.flush()

    ws1 = BranchWorkspaceModel(project_id=project.id, branch_id=branch1.id, user_requirements="")
    ws2 = BranchWorkspaceModel(project_id=project.id, branch_id=branch2.id, user_requirements="")
    async_session.add_all([ws1, ws2])
    await async_session.flush()

    rule1 = DomainRuleModel(project_id=project.id, workspace_id=ws1.id, title="Rule 1", statement="Stmt 1")
    rule2 = DomainRuleModel(project_id=project.id, workspace_id=ws2.id, title="Rule 2", statement="Stmt 2")
    rule3 = DomainRuleModel(project_id=project.id, workspace_id=ws1.id, title="Rule 3", statement="Stmt 3")
    async_session.add_all([rule1, rule2, rule3])
    await async_session.flush()

    flow1 = FlowModel(project_id=project.id, workspace_id=ws1.id, name="Flow 1", description="")
    flow2 = FlowModel(project_id=project.id, workspace_id=ws2.id, name="Flow 2", description="")
    async_session.add_all([flow1, flow2])
    await async_session.flush()

    s1 = FlowStepModel(flow_id=flow1.id, workspace_id=ws1.id, name="S1", step_type=FlowStepType.ACTOR_ACTION, position=0)
    s2 = FlowStepModel(flow_id=flow1.id, workspace_id=ws1.id, name="S2", step_type=FlowStepType.SYSTEM_ACTION, position=1)
    s3 = FlowStepModel(flow_id=flow2.id, workspace_id=ws2.id, name="S3", step_type=FlowStepType.ACTOR_ACTION, position=0)
    s4 = FlowStepModel(flow_id=flow2.id, workspace_id=ws2.id, name="S4", step_type=FlowStepType.SYSTEM_ACTION, position=1)
    async_session.add_all([s1, s2, s3, s4])
    await async_session.flush()

    shared_uuid = "shared-uuid-across-branches"
    t1 = FlowTransitionModel(
        project_id=project.id,
        workspace_id=ws1.id,
        flow_id=flow1.id,
        source_step_id=s1.id,
        target_step_id=s2.id,
        logical_uuid=shared_uuid,
        label="Edge WS1",
        position=0,
    )
    t2 = FlowTransitionModel(
        project_id=project.id,
        workspace_id=ws2.id,
        flow_id=flow2.id,
        source_step_id=s3.id,
        target_step_id=s4.id,
        logical_uuid=shared_uuid,
        label="Edge WS2",
        position=0,
    )
    async_session.add_all([t1, t2])
    await async_session.flush()

    # Create rule links for both transitions with the same logical_uuid
    from backend.database.model import RuleLinkModel
    rl1 = RuleLinkModel(
        project_id=project.id,
        workspace_id=ws1.id,
        rule_id=rule1.id,
        target_kind="flow_transition",
        target_logical_uuid=shared_uuid,
    )
    rl2 = RuleLinkModel(
        project_id=project.id,
        workspace_id=ws2.id,
        rule_id=rule2.id,
        target_kind="flow_transition",
        target_logical_uuid=shared_uuid,
    )
    async_session.add_all([rl1, rl2])
    await async_session.flush()

    service = FlowTransitionService()

    # 1. Verify get_transition in ws1 only returns rule1.id
    resp1 = await service.get_transition(
        project_id=project.id,
        flow_id=flow1.id,
        transition_id=t1.id,
        session=async_session,
        workspace_id=ws1.id,
    )
    assert resp1.rule_ids == [rule1.id]

    # 2. Verify get_transition in ws2 only returns rule2.id
    resp2 = await service.get_transition(
        project_id=project.id,
        flow_id=flow2.id,
        transition_id=t2.id,
        session=async_session,
        workspace_id=ws2.id,
    )
    assert resp2.rule_ids == [rule2.id]

    # 3. Update rule links in ws1 (switch from rule1 to rule3)
    await service.update_transition(
        project_id=project.id,
        flow_id=flow1.id,
        transition_id=t1.id,
        request=FlowTransitionUpdateRequest(rule_ids=[rule3.id]),
        session=async_session,
        workspace_id=ws1.id,
    )

    # Verify ws2 rule links remain completely intact
    resp2_after = await service.get_transition(
        project_id=project.id,
        flow_id=flow2.id,
        transition_id=t2.id,
        session=async_session,
        workspace_id=ws2.id,
    )
    assert resp2_after.rule_ids == [rule2.id]

    # 4. Delete transition in ws1
    await service.delete_transition(
        project_id=project.id,
        flow_id=flow1.id,
        transition_id=t1.id,
        session=async_session,
        workspace_id=ws1.id,
    )

    # Verify ws2 transition and its rule link are still present
    resp2_final = await service.get_transition(
        project_id=project.id,
        flow_id=flow2.id,
        transition_id=t2.id,
        session=async_session,
        workspace_id=ws2.id,
    )
    assert resp2_final.rule_ids == [rule2.id]
