import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.modules.requirements_core.feature.schemas import FeatureCreateRequest
from backend.api.modules.requirements_core.flow.schemas import FlowStepCreateRequest
from backend.api.modules.requirements_core.public import ACCreateRequest, FeatureService, FlowService, ScenarioService
from backend.database.model import (
    ActorModel,
    BranchWorkspaceModel,
    RequirementBranchModel,
    Base,
    FeatureModel,
    FeatureRelationModel,
    FlowModel,
    FlowStepModel,
    ProjectModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
)


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
        owner_user_id=1,
        name="测试项目",
        description="用于测试的项目",
        user_requirements="一个测试用的需求描述。",
    )
    db_session.add(project)
    await db_session.flush()
    branch = RequirementBranchModel(project_id=project.id, name="test-position")
    db_session.add(branch)
    await db_session.flush()
    workspace = BranchWorkspaceModel(
        project_id=project.id, branch_id=branch.id,
        user_requirements=project.user_requirements,
    )
    db_session.add(workspace)
    await db_session.flush()
    return project.id, workspace.id

@pytest.mark.asyncio
async def test_create_ac_position_robustness(db_session, seeded_project):
    """
    Test that manual AC creation successfully determines the next position
    even when there are existing ACs with position offsets (e.g. 1-indexed or custom).
    """
    project_id, workspace_id = seeded_project
    # Seed Actor and Feature first
    actor = ActorModel(project_id=project_id, workspace_id=workspace_id, name="用户", description="测试角色")
    feature = FeatureModel(project_id=project_id, workspace_id=workspace_id, name="叶子功能", description="测试功能")
    db_session.add_all([actor, feature])
    await db_session.flush()

    # Seed Scenario
    scenario = ScenarioModel(
        project_id=project_id, workspace_id=workspace_id,
        feature_id=feature.id,
        actor_id=actor.id,
        name="测试场景",
        content="测试内容"
    )
    db_session.add(scenario)
    await db_session.flush()

    # Seed an existing AC with position 1 (simulating AI generator off-by-one behavior)
    existing_ac = ScenarioAcceptanceCriterionModel(
        scenario_id=scenario.id,
        workspace_id=workspace_id,
        position=1,
        content="AI生成的验收标准",
    )
    db_session.add(existing_ac)
    await db_session.flush()

    # Attempt to manually create a new AC with position=None
    scenario_service = ScenarioService()
    req = ACCreateRequest(content="手动新增的验收标准", position=None)
    response = await scenario_service.create_acceptance_criterion(
        project_id=project_id, workspace_id=workspace_id,
        scenario_id=scenario.id,
        req=req,
        session=db_session
    )

    assert response.position == 2
    assert response.content == "手动新增的验收标准"

    # Verify both ACs exist in the DB
    stmt = select(ScenarioAcceptanceCriterionModel).where(
        ScenarioAcceptanceCriterionModel.scenario_id == scenario.id
    ).order_by(ScenarioAcceptanceCriterionModel.position.asc())
    db_acs = (await db_session.execute(stmt)).scalars().all()
    assert len(db_acs) == 2
    assert db_acs[0].position == 1
    assert db_acs[1].position == 2

@pytest.mark.asyncio
async def test_create_feature_position_robustness(db_session, seeded_project):
    """
    Test that manual feature creation successfully determines the child relation position
    even when there are existing children with position offsets (e.g. 1-indexed).
    """
    project_id, workspace_id = seeded_project
    # Create parent feature
    parent_feature = FeatureModel(project_id=project_id, workspace_id=workspace_id, name="父模块", description="测试")
    db_session.add(parent_feature)
    await db_session.flush()

    # Create child feature with position 1
    child_feature1 = FeatureModel(project_id=project_id, workspace_id=workspace_id, name="子模块1", description="测试")
    db_session.add(child_feature1)
    await db_session.flush()

    rel1 = FeatureRelationModel(
        parent_feature_id=parent_feature.id,
        child_feature_id=child_feature1.id,
        position=1
    )
    db_session.add(rel1)
    await db_session.flush()

    # Attempt to manually create a new feature under the same parent
    feature_service = FeatureService()
    req = FeatureCreateRequest(name="子模块2", description="测试", parent_id=parent_feature.id)
    response = await feature_service.create_feature(
        project_id=project_id, workspace_id=workspace_id,
        req=req,
        session=db_session
    )

    assert response.parent_id == parent_feature.id

    # Verify relations in database
    stmt = select(FeatureRelationModel).where(
        FeatureRelationModel.parent_feature_id == parent_feature.id
    ).order_by(FeatureRelationModel.position.asc())
    rels = (await db_session.execute(stmt)).scalars().all()
    assert len(rels) == 2
    assert rels[0].position == 1
    assert rels[1].position == 2

@pytest.mark.asyncio
async def test_create_flow_step_position_robustness(db_session, seeded_project):
    """
    Test that manual flow step creation successfully determines step position
    even when there are existing steps with position offsets.
    """
    project_id, workspace_id = seeded_project
    # Create flow
    flow = FlowModel(project_id=project_id, workspace_id=workspace_id, name="业务流程", description="测试")
    db_session.add(flow)
    await db_session.flush()

    # Seed flow step with position 2 (custom or off-by-one)
    existing_step = FlowStepModel(
        flow_id=flow.id,
        workspace_id=workspace_id,
        position=2,
        name="步骤1",
        description="测试",
        step_type="systemAction"
    )
    db_session.add(existing_step)
    await db_session.flush()

    # Attempt to manually create a new flow step
    flow_service = FlowService()
    req = FlowStepCreateRequest(
        name="步骤2",
        description="测试",
        step_type="systemAction",
        actor_ids=[],
        input_business_object_ids=[],
        output_business_object_ids=[]
    )
    response = await flow_service.create_flow_step(
        project_id=project_id, workspace_id=workspace_id,
        flow_id=flow.id,
        req=req,
        session=db_session
    )

    assert response.position == 3

    # Verify both steps in database
    stmt = select(FlowStepModel).where(
        FlowStepModel.flow_id == flow.id
    ).order_by(FlowStepModel.position.asc())
    steps = (await db_session.execute(stmt)).scalars().all()
    assert len(steps) == 2
    assert steps[0].position == 2
    assert steps[1].position == 3
