import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.engines.patch_engine import GraphPatchEngine
from backend.database.model import (
    ActorModel,
    Base,
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    FeatureModel,
    FeatureRelationModel,
    FlowModel,
    ProjectModel,
    ScenarioModel,
    ScopeModel,
    feature_actor_table,
    flow_feature_table,
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


async def _add_project(session: AsyncSession, name: str) -> ProjectModel:
    project = ProjectModel(
        name=name,
        description="图补丁特征测试",
        owner_user_id=1,
        user_requirements="维护业务图谱",
    )
    session.add(project)
    await session.flush()
    return project


@pytest.mark.asyncio
async def test_apply_patch_preserves_reference_aliases_order_and_updates(db_session):
    project = await _add_project(db_session, "图补丁")
    removed_actor = ActorModel(
        project_id=project.id,
        name="待删除角色",
        description="旧角色",
    )
    scoped_feature = FeatureModel(
        project_id=project.id,
        name="已有功能",
        description="用于更新范围",
    )
    db_session.add_all([removed_actor, scoped_feature])
    await db_session.flush()
    scope = ScopeModel(
        feature_id=scoped_feature.id,
        status="POSTPONED",
        reason="原原因",
    )
    db_session.add(scope)
    await db_session.flush()

    patch = {
        "deleteNodes": [{"kind": "actor", "id": removed_actor.id}],
        "addNodes": [
            {
                "kind": "actor",
                "tempId": "tmp_actor",
                "actorName": "管理员",
                "actorDescription": "初始描述",
            },
            {
                "kind": "feature",
                "temp_id": "tmp_parent",
                "featureName": "订单管理",
                "featureDescription": "父功能",
            },
            {
                "kind": "feature",
                "temp_id": "tmp_child_a",
                "featureName": "创建订单",
                "featureDescription": "子功能 A",
                "parentId": "feature:tmp_parent",
            },
            {
                "kind": "feature",
                "temp_id": "tmp_child_b",
                "name": "提交订单",
                "description": "子功能 B",
                "parent_id": "tmp_parent",
            },
            {
                "kind": "feature",
                "temp_id": "tmp_child_c",
                "name": "审核订单",
                "description": "子功能 C",
                "parent_id": "feature:tmp_parent",
            },
            {
                "kind": "scenario",
                "temp_id": "tmp_scenario",
                "scenarioName": "创建成功",
                "scenarioContent": "初始内容",
                "featureId": "feature:tmp_child_a",
                "actorId": "actor:tmp_actor",
            },
            {
                "kind": "business_object",
                "temp_id": "tmp_bo",
                "boName": "订单",
                "boDescription": "初始订单描述",
            },
            {
                "kind": "business_object_attribute",
                "businessObjectId": "business_object:tmp_bo",
                "name": "编号",
                "type": "string",
                "example": "SO-1",
            },
            {
                "kind": "flow",
                "temp_id": "tmp_flow",
                "flowName": "创建流程",
                "flowDescription": "初始流程",
            },
        ],
        "updateNodes": [
            {
                "kind": "actor",
                "id": "actor:tmp_actor",
                "description": "更新后的描述",
            },
            {
                "kind": "feature",
                "id": "feature:tmp_child_a",
                "featureName": "创建订单（更新）",
            },
            {
                "kind": "scenario",
                "id": "scenario:tmp_scenario",
                "scenarioContent": "更新后的场景",
            },
            {
                "kind": "business_object",
                "id": "business_object:tmp_bo",
                "boDescription": "更新后的订单描述",
            },
            {
                "kind": "flow",
                "id": "flow:tmp_flow",
                "flowName": "创建订单流程（更新）",
            },
            {
                "kind": "scope",
                "id": scope.id,
                "reason": "改为本期",
                "scopeStatus": "CURRENT",
            },
        ],
        "addLinks": [
            {
                "type": "feature_actor",
                "source": "actor:tmp_actor",
                "target": "feature:tmp_child_a",
            },
            {
                "type": "feature_actor_relation",
                "sourceId": "actor:tmp_actor",
                "targetId": "feature:tmp_child_a",
            },
            {
                "type": "flow_feature",
                "source": "feature:tmp_child_a",
                "target": "flow:tmp_flow",
            },
        ],
    }

    await GraphPatchEngine().apply_patch(project.id, patch, db_session)
    await db_session.flush()

    actors = (
        await db_session.execute(
            select(ActorModel).where(ActorModel.project_id == project.id)
        )
    ).scalars().all()
    assert [(actor.name, actor.description) for actor in actors] == [
        ("管理员", "更新后的描述")
    ]
    features = (
        await db_session.execute(
            select(FeatureModel).where(FeatureModel.project_id == project.id)
        )
    ).scalars().all()
    feature_by_name = {feature.name: feature for feature in features}
    relations = (
        await db_session.execute(
            select(FeatureRelationModel).order_by(
                FeatureRelationModel.position
            )
        )
    ).scalars().all()
    assert [
        (relation.child_feature_id, relation.position)
        for relation in relations
    ] == [
        (feature_by_name["创建订单（更新）"].id, 0),
        (feature_by_name["提交订单"].id, 1),
        (feature_by_name["审核订单"].id, 2),
    ]

    scenario = (
        await db_session.execute(
            select(ScenarioModel).where(ScenarioModel.project_id == project.id)
        )
    ).scalar_one()
    assert (
        scenario.name,
        scenario.content,
        scenario.feature_id,
        scenario.actor_id,
    ) == (
        "创建成功",
        "更新后的场景",
        feature_by_name["创建订单（更新）"].id,
        actors[0].id,
    )
    business_object = (
        await db_session.execute(
            select(BusinessObjectModel).where(
                BusinessObjectModel.project_id == project.id
            )
        )
    ).scalar_one()
    assert business_object.description == "更新后的订单描述"
    attribute = (
        await db_session.execute(select(BusinessObjectAttributeModel))
    ).scalar_one()
    assert (
        attribute.business_object_id,
        attribute.name,
        attribute.data_type,
    ) == (business_object.id, "编号", "string")
    flow = (
        await db_session.execute(
            select(FlowModel).where(FlowModel.project_id == project.id)
        )
    ).scalar_one()
    assert flow.name == "创建订单流程（更新）"
    assert (scope.status, scope.reason) == ("CURRENT", "改为本期")

    feature_actor_count = await db_session.scalar(
        select(func.count()).select_from(feature_actor_table)
    )
    flow_feature_count = await db_session.scalar(
        select(func.count()).select_from(flow_feature_table)
    )
    assert (feature_actor_count, flow_feature_count) == (1, 1)


@pytest.mark.asyncio
async def test_apply_patch_preserves_recursive_feature_deletion(db_session):
    project = await _add_project(db_session, "递归删除")
    root = FeatureModel(
        project_id=project.id,
        name="根功能",
        description="根",
    )
    child = FeatureModel(
        project_id=project.id,
        name="子功能",
        description="子",
    )
    grandchild = FeatureModel(
        project_id=project.id,
        name="孙功能",
        description="孙",
    )
    survivor = FeatureModel(
        project_id=project.id,
        name="保留功能",
        description="保留",
    )
    db_session.add_all([root, child, grandchild, survivor])
    await db_session.flush()
    db_session.add_all(
        [
            FeatureRelationModel(
                parent_feature_id=root.id,
                child_feature_id=child.id,
                position=0,
            ),
            FeatureRelationModel(
                parent_feature_id=child.id,
                child_feature_id=grandchild.id,
                position=0,
            ),
        ]
    )
    await db_session.flush()

    await GraphPatchEngine().apply_patch(
        project.id,
        {"deleteNodes": [{"kind": "feature", "featureId": root.id}]},
        db_session,
    )

    remaining_names = (
        await db_session.execute(
            select(FeatureModel.name).where(
                FeatureModel.project_id == project.id
            )
        )
    ).scalars().all()
    assert remaining_names == ["保留功能"]
