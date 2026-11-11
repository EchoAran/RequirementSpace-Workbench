"""
Pytest fixtures for Version Control tests.
提供内存 SQLite 上的同步及异步数据库 Session 与 Seed 项目数据。
"""
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from backend.api.modules.version_control.application.clean_initialization import (
    create_initial_workspace,
    finalize_initial_commit,
)
from backend.database.model import (
    ActorModel,
    Base,
    BranchWorkspaceModel,
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    FeatureModel,
    FeatureRelationModel,
    FlowModel,
    FlowStepModel,
    ProjectModel,
    RequirementBranchModel,
    ScenarioAcceptanceCriterionModel,
    ScenarioModel,
    ScopeModel,
    UserModel,
)


@pytest.fixture
def vc_db_path(tmp_path):
    """每个测试独立的 SQLite 文件库，供同步/异步两个 Session 共享同一份数据。"""
    return str(tmp_path / "vc_test.db")


@pytest.fixture
def sync_db_session(vc_db_path):
    """创建一个单次测试隔离的 SQLite 同步 Session。"""
    engine = create_engine(
        f"sqlite:///{vc_db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


@pytest.fixture
async def async_db_session(vc_db_path):
    """与 sync_db_session 共享同一数据库的异步 Session，供 async 服务函数使用。"""
    engine = create_async_engine(f"sqlite+aiosqlite:///{vc_db_path}")
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def seeded_project(sync_db_session: Session) -> ProjectModel:
    """在测试数据库中预先塞入默认用户与目标项目。"""
    user = UserModel(
        id=2,
        email="test_owner@example.com",
        password_hash="hashed_password",
        role="user",
        preferred_locale="zh-CN",
    )
    sync_db_session.add(user)
    sync_db_session.commit()

    project = ProjectModel(
        owner_user_id=user.id,
        name="Version Control Seed Project",
        description="Testing baseline migration and versioning",
        user_requirements="Initial user requirements text",
        kano_status="pending",
        unlocked_stages="what,flow,scope",
    )
    sync_db_session.add(project)
    sync_db_session.commit()
    return project


def _gen_uuid() -> str:
    """生成一个稳定但唯一的 logical_uuid，供测试种子数据使用。"""
    return str(uuid.uuid4())


@pytest.fixture
def seeded_vc_project(sync_db_session: Session) -> SimpleNamespace:
    """构造一个已迁移版本控制、拥有完整需求模型（参与者/功能树/场景/业务对象/流程/范围）的项目。"""
    user = UserModel(
        id=2,
        email="test_owner@example.com",
        password_hash="hashed_password",
        role="user",
        preferred_locale="zh-CN",
    )
    sync_db_session.add(user)
    sync_db_session.commit()

    project = ProjectModel(
        owner_user_id=user.id,
        name="VC Seed Project",
        description="Seed for phase 3 tests",
        user_requirements="初始用户需求",
        kano_status="pending",
        unlocked_stages="what,flow,scope",
    )
    sync_db_session.add(project)
    sync_db_session.flush()

    main_branch, workspace = create_initial_workspace(sync_db_session, project)

    actor = ActorModel(
        project_id=project.id,
        workspace_id=workspace.id,
        logical_uuid=_gen_uuid(),
        name="用户",
        description="",
        confirmation_status="ai_assumption",
    )
    feat_root = FeatureModel(
        project_id=project.id,
        workspace_id=workspace.id,
        logical_uuid=_gen_uuid(),
        name="订单支付",
        description="初始描述",
        confirmation_status="ai_assumption",
    )
    feat_child = FeatureModel(
        project_id=project.id,
        workspace_id=workspace.id,
        logical_uuid=_gen_uuid(),
        name="订单确认",
        description="",
        confirmation_status="ai_assumption",
    )
    sync_db_session.add_all([actor, feat_root, feat_child])
    sync_db_session.flush()

    feature_relation = FeatureRelationModel(
        workspace_id=workspace.id,
        logical_uuid=_gen_uuid(),
        parent_feature_id=feat_root.id,
        child_feature_id=feat_child.id,
        position=0,
    )
    scenario = ScenarioModel(
        project_id=project.id,
        workspace_id=workspace.id,
        logical_uuid=_gen_uuid(),
        feature_id=feat_root.id,
        actor_id=actor.id,
        name="支付场景",
        content="用户完成支付",
        confirmation_status="ai_assumption",
    )
    business_object = BusinessObjectModel(
        project_id=project.id,
        workspace_id=workspace.id,
        logical_uuid=_gen_uuid(),
        name="订单",
        description="",
        confirmation_status="ai_assumption",
    )
    flow = FlowModel(
        project_id=project.id,
        workspace_id=workspace.id,
        logical_uuid=_gen_uuid(),
        name="支付流程",
        description="",
        confirmation_status="ai_assumption",
    )
    sync_db_session.add_all([feature_relation, scenario, business_object, flow])
    sync_db_session.flush()

    acceptance_criterion = ScenarioAcceptanceCriterionModel(
        workspace_id=workspace.id,
        logical_uuid=_gen_uuid(),
        scenario_id=scenario.id,
        position=0,
        content="支付成功",
        confirmation_status="ai_assumption",
    )
    attribute = BusinessObjectAttributeModel(
        workspace_id=workspace.id,
        logical_uuid=_gen_uuid(),
        business_object_id=business_object.id,
        name="金额",
        data_type="number",
        description="",
        example="",
        confirmation_status="ai_assumption",
    )
    step = FlowStepModel(
        workspace_id=workspace.id,
        logical_uuid=_gen_uuid(),
        flow_id=flow.id,
        position=0,
        name="发起支付",
        description="",
        step_type="task",
        confirmation_status="ai_assumption",
    )
    scope = ScopeModel(
        workspace_id=workspace.id,
        logical_uuid=_gen_uuid(),
        feature_id=feat_root.id,
        status="in_scope",
        reason="核心能力",
        confirmation_status="ai_assumption",
    )
    sync_db_session.add_all([acceptance_criterion, attribute, step, scope])
    sync_db_session.commit()

    finalize_initial_commit(sync_db_session, project, main_branch, workspace)
    sync_db_session.commit()

    return SimpleNamespace(
        project=project,
        user=user,
        main_branch=main_branch,
        main_workspace=workspace,
        baseline_commit_id=main_branch.head_commit_id,
        actor=actor,
        feat_root=feat_root,
        feat_child=feat_child,
        scenario=scenario,
        business_object=business_object,
        flow=flow,
        step=step,
        scope=scope,
    )
