"""
Pytest fixtures for Version Control tests.
提供内存 SQLite 上的同步及异步数据库 Session 与 Seed 项目数据。
"""
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.database.model import (
    Base,
    UserModel,
    ProjectModel,
    RequirementBranchModel,
    BranchWorkspaceModel,
    ActorModel,
    FeatureModel,
    FeatureRelationModel,
    ScenarioModel,
    ScenarioAcceptanceCriterionModel,
    BusinessObjectModel,
    BusinessObjectAttributeModel,
    FlowModel,
    FlowStepModel,
    ScopeModel,
)
from backend.api.modules.version_control.application.baseline_migration import (
    migrate_project_to_version_control,
)


from sqlalchemy.pool import StaticPool


@pytest.fixture
def sync_db_session():
    """创建一个单次测试隔离的内存 SQLite 同步 Session。"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


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

    # 项目级遗留实体（尚无 workspace），迁移时会被回填 logical_uuid 与 workspace_id。
    actor = ActorModel(
        project_id=project.id,
        logical_uuid=_gen_uuid(),
        name="用户",
        description="",
        confirmation_status="ai_assumption",
    )
    feat_root = FeatureModel(
        project_id=project.id,
        logical_uuid=_gen_uuid(),
        name="订单支付",
        description="初始描述",
        confirmation_status="ai_assumption",
    )
    feat_child = FeatureModel(
        project_id=project.id,
        logical_uuid=_gen_uuid(),
        name="订单确认",
        description="",
        confirmation_status="ai_assumption",
    )
    sync_db_session.add_all([actor, feat_root, feat_child])
    sync_db_session.flush()

    feature_relation = FeatureRelationModel(
        logical_uuid=_gen_uuid(),
        parent_feature_id=feat_root.id,
        child_feature_id=feat_child.id,
        position=0,
    )
    scenario = ScenarioModel(
        project_id=project.id,
        logical_uuid=_gen_uuid(),
        feature_id=feat_root.id,
        actor_id=actor.id,
        name="支付场景",
        content="用户完成支付",
        confirmation_status="ai_assumption",
    )
    business_object = BusinessObjectModel(
        project_id=project.id,
        logical_uuid=_gen_uuid(),
        name="订单",
        description="",
        confirmation_status="ai_assumption",
    )
    flow = FlowModel(
        project_id=project.id,
        logical_uuid=_gen_uuid(),
        name="支付流程",
        description="",
        confirmation_status="ai_assumption",
    )
    sync_db_session.add_all([feature_relation, scenario, business_object, flow])
    sync_db_session.flush()

    acceptance_criterion = ScenarioAcceptanceCriterionModel(
        logical_uuid=_gen_uuid(),
        scenario_id=scenario.id,
        position=0,
        content="支付成功",
        confirmation_status="ai_assumption",
    )
    attribute = BusinessObjectAttributeModel(
        logical_uuid=_gen_uuid(),
        business_object_id=business_object.id,
        name="金额",
        data_type="number",
        description="",
        example="",
        confirmation_status="ai_assumption",
    )
    step = FlowStepModel(
        logical_uuid=_gen_uuid(),
        flow_id=flow.id,
        position=0,
        name="发起支付",
        description="",
        step_type="task",
        confirmation_status="ai_assumption",
    )
    scope = ScopeModel(
        logical_uuid=_gen_uuid(),
        feature_id=feat_root.id,
        status="in_scope",
        reason="核心能力",
        confirmation_status="ai_assumption",
    )
    sync_db_session.add_all([acceptance_criterion, attribute, step, scope])
    sync_db_session.commit()

    # 执行基线迁移：创建 main、工作区与基线提交。
    migrate_project_to_version_control(sync_db_session, project)
    sync_db_session.commit()

    main_branch = sync_db_session.scalars(
        select(RequirementBranchModel).where(
            RequirementBranchModel.project_id == project.id,
            RequirementBranchModel.name == "main",
        )
    ).first()
    workspace = sync_db_session.scalars(
        select(BranchWorkspaceModel).where(
            BranchWorkspaceModel.project_id == project.id,
            BranchWorkspaceModel.branch_id == main_branch.id,
        )
    ).first()

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
