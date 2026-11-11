from dataclasses import asdict
from backend.api.modules.version_control.application.clean_initialization import create_initial_workspace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.detectors.issue_context_loader import (
    load_issue_project_context,
)
from backend.database.model import (
    ActorModel,
    Base,
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    FeatureModel,
    FeatureRelationModel,
    FlowModel,
    FlowStepModel,
    ProjectModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    ScopeModel,
    feature_actor_table,
    flow_feature_table,
    flow_step_actor_table,
    flow_step_input_business_object_table,
    FlowTransitionModel,
    flow_step_output_business_object_table,
)


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_load_issue_project_context_preserves_full_graph_shape(db_session):
    project = ProjectModel(
        name="问题上下文测试",
        description="锁定图谱查询结果",
        owner_user_id=1,
        user_requirements="管理员维护订单",
    )
    db_session.add(project)
    await db_session.flush()
    _, workspace = await db_session.run_sync(lambda s: create_initial_workspace(s, project))
    workspace_id = workspace.id

    admin = ActorModel(
        project_id=project.id, workspace_id=workspace_id,
        name="管理员",
        description="维护系统",
    )
    operator = ActorModel(
        project_id=project.id, workspace_id=workspace_id,
        name="操作员",
        description="处理订单",
    )
    parent = FeatureModel(
        project_id=project.id, workspace_id=workspace_id,
        name="订单管理",
        description="父功能",
    )
    child = FeatureModel(
        project_id=project.id, workspace_id=workspace_id,
        name="创建订单",
        description="叶子功能",
    )
    order = BusinessObjectModel(
        project_id=project.id, workspace_id=workspace_id,
        name="订单",
        description="订单数据",
    )
    flow = FlowModel(
        project_id=project.id, workspace_id=workspace_id,
        name="创建订单流程",
        description="从录入到保存",
    )
    db_session.add_all([admin, operator, parent, child, order, flow])
    await db_session.flush()

    scenario = ScenarioModel(
        project_id=project.id, workspace_id=workspace_id,
        feature_id=child.id,
        actor_id=operator.id,
        name="创建成功",
        content="操作员创建订单",
    )
    first_step = FlowStepModel(
        workspace_id=workspace_id,
        flow_id=flow.id,
        position=2,
        name="保存订单",
        description="持久化",
        step_type="systemAction",
    )
    second_step = FlowStepModel(
        workspace_id=workspace_id,
        flow_id=flow.id,
        position=1,
        name="录入订单",
        description="填写信息",
        step_type="actorAction",
    )
    db_session.add_all([scenario, first_step, second_step])
    await db_session.flush()

    db_session.add_all(
        [
            FeatureRelationModel(
                parent_feature_id=parent.id,
                child_feature_id=child.id,
                position=0,
            ),
            ScenarioAcceptanceCriterionModel(
        workspace_id=workspace_id,
                scenario_id=scenario.id,
                position=2,
                content="订单已保存",
            ),
            ScenarioAcceptanceCriterionModel(
        workspace_id=workspace_id,
                scenario_id=scenario.id,
                position=1,
                content="订单编号已生成",
            ),
            BusinessObjectAttributeModel(
        workspace_id=workspace_id,
                business_object_id=order.id,
                name="编号",
                description="订单编号",
                data_type="string",
                example="SO-1",
            ),
            BusinessObjectAttributeModel(
        workspace_id=workspace_id,
                business_object_id=order.id,
                name="金额",
                description="订单金额",
                data_type="decimal",
                example="100",
            ),
            ScopeModel(
        workspace_id=workspace_id,
                feature_id=child.id,
                status="CURRENT",
                reason="本期交付",
            ),
        ]
    )
    await db_session.execute(
        feature_actor_table.insert().values(
            [
                {"feature_id": child.id, "actor_id": operator.id},
                {"feature_id": child.id, "actor_id": admin.id},
            ]
        )
    )
    await db_session.execute(
        flow_feature_table.insert().values(
            flow_id=flow.id,
            feature_id=child.id,
        )
    )
    await db_session.execute(
        flow_step_actor_table.insert().values(
            flow_step_id=second_step.id,
            actor_id=operator.id,
        )
    )
    await db_session.execute(
        flow_step_input_business_object_table.insert().values(
            flow_step_id=first_step.id,
            business_object_id=order.id,
        )
    )
    await db_session.execute(
        flow_step_output_business_object_table.insert().values(
            flow_step_id=second_step.id,
            business_object_id=order.id,
        )
    )
    db_session.add(
        FlowTransitionModel(
            project_id=project.id, workspace_id=workspace_id,
            flow_id=flow.id,
            source_step_id=second_step.id,
            target_step_id=first_step.id,
            condition_text="",
            label="",
            is_default=False,
            position=0,
        )
    )
    await db_session.flush()

    context = await load_issue_project_context(project.id, db_session, workspace_id=workspace_id)

    assert context.project_id == project.id
    assert context.user_requirements == "管理员维护订单"
    assert [item.name for item in context.actors] == ["管理员", "操作员"]
    feature_by_id = {item.feature_id: item for item in context.features}
    assert asdict(feature_by_id[parent.id]) == {
        "feature_id": parent.id,
        "name": "订单管理",
        "description": "父功能",
        "actor_ids": [],
        "parent_id": None,
        "child_ids": [child.id],
    }
    assert asdict(feature_by_id[child.id]) == {
        "feature_id": child.id,
        "name": "创建订单",
        "description": "叶子功能",
        "actor_ids": [admin.id, operator.id],
        "parent_id": parent.id,
        "child_ids": [],
    }
    assert [item.feature_id for item in context.leaf_features] == [child.id]

    loaded_scenario = context.scenarios[0]
    assert loaded_scenario.acceptance_criteria_count == 2
    assert [
        (criterion.position, criterion.content)
        for criterion in loaded_scenario.acceptance_criteria
    ] == [(1, "订单编号已生成"), (2, "订单已保存")]

    loaded_flow = context.flows[0]
    assert loaded_flow.feature_ids == [child.id]
    assert [step.position for step in loaded_flow.steps] == [1, 2]
    step_by_id = {step.step_id: step for step in loaded_flow.steps}
    assert step_by_id[second_step.id].actor_ids == [operator.id]
    assert step_by_id[second_step.id].output_business_object_ids == [
        order.id
    ]
    assert loaded_flow.transitions[0].source_step_id == second_step.id
    assert loaded_flow.transitions[0].target_step_id == first_step.id
    assert step_by_id[first_step.id].input_business_object_ids == [order.id]

    loaded_object = context.business_objects[0]
    assert loaded_object.attribute_count == 2
    assert loaded_object.usage_count == 2
    assert [asdict(scope) for scope in context.scopes] == [
        {
            "scope_id": context.scopes[0].scope_id,
            "feature_id": child.id,
            "status": "CURRENT",
            "reason": "本期交付",
        }
    ]


@pytest.mark.asyncio
async def test_load_issue_project_context_keeps_missing_project_error(db_session):
    with pytest.raises(ValueError, match="^project_not_found$"):
        await load_issue_project_context(999999, db_session, workspace_id=999999)
