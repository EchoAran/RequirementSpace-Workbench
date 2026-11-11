"""Unit tests for FlowObjectUsageService and PathProjectionService."""

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.modules.requirements_core.flow.application.flow_object_usage_service import (
    FlowObjectUsageService,
)
from backend.api.modules.requirements_core.flow.application.path_projection_service import (
    PathProjectionService,
)
from backend.database.database import Base
from backend.database.model import (
    BranchWorkspaceModel,
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    FlowModel,
    FlowStepModel,
    FlowTransitionModel,
    ProjectModel,
    RequirementBranchModel,
)


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


@pytest.mark.asyncio
async def test_path_projection_service_computes_paths_and_handles_missing_flow(async_session: AsyncSession):
    session = async_session
    proj = ProjectModel(owner_user_id=1, name="Test Proj", description="", user_requirements="")
    session.add(proj)
    await session.flush()

    branch = RequirementBranchModel(project_id=proj.id, name="main", head_commit_id=None)
    session.add(branch)
    await session.flush()

    ws = BranchWorkspaceModel(project_id=proj.id, branch_id=branch.id)
    session.add(ws)
    await session.flush()

    flow = FlowModel(project_id=proj.id, workspace_id=ws.id, name="Checkout Flow", description="")
    session.add(flow)
    await session.flush()

    step1 = FlowStepModel(
        flow_id=flow.id,
        workspace_id=ws.id,
        position=1,
        name="Cart Review",
        description="",
        step_type="actorAction",
    )
    step2 = FlowStepModel(
        flow_id=flow.id,
        workspace_id=ws.id,
        position=2,
        name="Payment",
        description="",
        step_type="systemAction",
    )
    session.add_all([step1, step2])
    await session.flush()

    trans = FlowTransitionModel(
        project_id=proj.id,
        flow_id=flow.id,
        workspace_id=ws.id,
        source_step_id=step1.id,
        target_step_id=step2.id,
        position=1,
        label="Proceed to Pay",
        is_default=True,
    )
    session.add(trans)
    await session.commit()

    service = PathProjectionService()
    res = await service.get_path_projections(
        project_id=proj.id,
        flow_id=flow.id,
        session=session,
        workspace_id=ws.id,
    )

    assert res.flow_id == flow.id
    assert len(res.paths) >= 1
    assert res.paths[0].step_ids == [step1.id, step2.id]
    assert res.paths[0].transition_ids == [trans.id]

    with pytest.raises(HTTPException) as exc:
        await service.get_path_projections(
            project_id=proj.id,
            flow_id=99999,
            session=session,
            workspace_id=ws.id,
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_flow_object_usage_service_projects_inputs_outputs_and_cross_flow_references(
    async_session: AsyncSession,
):
    session = async_session
    proj = ProjectModel(owner_user_id=1, name="Store Proj", description="", user_requirements="")
    session.add(proj)
    await session.flush()

    branch = RequirementBranchModel(project_id=proj.id, name="main", head_commit_id=None)
    session.add(branch)
    await session.flush()

    ws = BranchWorkspaceModel(project_id=proj.id, branch_id=branch.id)
    session.add(ws)
    await session.flush()

    # Create business objects with attributes
    bo_order = BusinessObjectModel(
        project_id=proj.id,
        workspace_id=ws.id,
        name="Order",
        description="Customer order entity",
    )
    bo_payment = BusinessObjectModel(
        project_id=proj.id,
        workspace_id=ws.id,
        name="PaymentRecord",
        description="Payment transaction",
    )
    session.add_all([bo_order, bo_payment])
    await session.flush()

    attr1 = BusinessObjectAttributeModel(
        business_object_id=bo_order.id,
        workspace_id=ws.id,
        name="order_number",
        data_type="string",
        description="Unique identifier",
        example="ORD-1001",
    )
    attr2 = BusinessObjectAttributeModel(
        business_object_id=bo_order.id,
        workspace_id=ws.id,
        name="total_amount",
        data_type="decimal",
        description="Total charge",
        example="99.90",
    )
    session.add_all([attr1, attr2])
    await session.flush()

    # Flow 1: uses bo_order as input and output, uses bo_payment as output
    flow1 = FlowModel(project_id=proj.id, workspace_id=ws.id, name="Checkout Flow", description="")
    flow2 = FlowModel(project_id=proj.id, workspace_id=ws.id, name="Refund Flow", description="")
    session.add_all([flow1, flow2])
    await session.flush()

    step1 = FlowStepModel(
        flow_id=flow1.id,
        workspace_id=ws.id,
        position=1,
        name="Create Order",
        description="",
        step_type="actorAction",
    )
    step1.output_business_objects.append(bo_order)

    step2 = FlowStepModel(
        flow_id=flow1.id,
        workspace_id=ws.id,
        position=2,
        name="Process Payment",
        description="",
        step_type="systemAction",
    )
    step2.input_business_objects.append(bo_order)
    step2.output_business_objects.append(bo_payment)

    # Flow 2 step also references bo_order
    flow2_step = FlowStepModel(
        flow_id=flow2.id,
        workspace_id=ws.id,
        position=1,
        name="Lookup Order For Refund",
        description="",
        step_type="actorAction",
    )
    flow2_step.input_business_objects.append(bo_order)

    session.add_all([step1, step2, flow2_step])
    await session.commit()

    service = FlowObjectUsageService()
    usage = await service.get_flow_object_usage(
        project_id=proj.id,
        flow_id=flow1.id,
        session=session,
        workspace_id=ws.id,
    )

    assert usage.flow_id == flow1.id
    assert len(usage.objects) == 2

    # Order BO assertions
    order_proj = next(o for o in usage.objects if o.business_object_id == bo_order.id)
    assert order_proj.name == "Order"
    assert order_proj.input_at_step_ids == [step2.id]
    assert order_proj.output_at_step_ids == [step1.id]
    assert order_proj.used_by_step_ids == [step1.id, step2.id]
    assert len(order_proj.attributes) == 2
    assert {a.name for a in order_proj.attributes} == {"order_number", "total_amount"}

    # Cross-flow notice assertions: bo_order is also used in "Refund Flow"
    assert order_proj.other_flows_count == 1
    assert order_proj.other_flow_names == ["Refund Flow"]

    # PaymentRecord BO assertions: only used in flow 1
    payment_proj = next(o for o in usage.objects if o.business_object_id == bo_payment.id)
    assert payment_proj.name == "PaymentRecord"
    assert payment_proj.input_at_step_ids == []
    assert payment_proj.output_at_step_ids == [step2.id]
    assert payment_proj.other_flows_count == 0
    assert payment_proj.other_flow_names == []

    # Non-existent flow returns 404
    with pytest.raises(HTTPException) as exc:
        await service.get_flow_object_usage(
            project_id=proj.id,
            flow_id=88888,
            session=session,
            workspace_id=ws.id,
        )
    assert exc.value.status_code == 404
