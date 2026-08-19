"""
Tests for Baseline Version Migration Service.
验证 migrate_project_to_version_control 能够创建 main 分支、BranchWorkspace 和首个基线 Commit，
且对既有实体正确回填 logical_uuid，多次执行具备幂等性。
"""
from sqlalchemy import select

from backend.database.model import (
    ProjectModel,
    RequirementBranchModel,
    RequirementCommitModel,
    BranchWorkspaceModel,
    ActorModel,
    FeatureModel,
)
from backend.api.modules.version_control.public import (
    migrate_project_to_version_control,
)


def test_migrate_empty_project_baseline(sync_db_session, seeded_project):
    """测试迁移空项目或仅有基本元数据的项目生成基线。"""
    res = migrate_project_to_version_control(sync_db_session, seeded_project)

    assert res["status"] == "success"
    assert res["project_id"] == seeded_project.id
    assert "main_branch_public_id" in res
    assert "head_commit_public_id" in res

    # 验证数据库状态
    main_branch = sync_db_session.scalars(
        select(RequirementBranchModel).where(
            RequirementBranchModel.project_id == seeded_project.id,
            RequirementBranchModel.name == "main",
        )
    ).first()

    assert main_branch is not None
    assert main_branch.is_protected is True
    assert main_branch.is_default is True

    workspace = sync_db_session.scalars(
        select(BranchWorkspaceModel).where(
            BranchWorkspaceModel.branch_id == main_branch.id
        )
    ).first()

    assert workspace is not None
    assert workspace.project_id == seeded_project.id

    commit = sync_db_session.scalars(
        select(RequirementCommitModel).where(
            RequirementCommitModel.id == main_branch.head_commit_id
        )
    ).first()

    assert commit is not None
    assert commit.project_id == seeded_project.id
    assert commit.author_user_id == seeded_project.owner_user_id
    assert len(commit.state_hash) == 64


def test_migrate_project_idempotency(sync_db_session, seeded_project):
    """测试重复对同一个项目执行迁移的幂等性。"""
    res1 = migrate_project_to_version_control(sync_db_session, seeded_project)
    assert res1["status"] == "success"

    res2 = migrate_project_to_version_control(sync_db_session, seeded_project)
    assert res2["status"] == "skipped"
    assert res2["project_id"] == seeded_project.id

    # 确认没有重复产生第二个 main 分支
    branches = sync_db_session.scalars(
        select(RequirementBranchModel).where(
            RequirementBranchModel.project_id == seeded_project.id,
            RequirementBranchModel.name == "main",
        )
    ).all()
    assert len(branches) == 1


def test_migrate_project_backfills_logical_uuid_and_workspace(sync_db_session, seeded_project):
    """测试迁移已有 Actor 和 Feature 的项目时，正确补齐 logical_uuid 并关联 workspace_id。"""
    actor = ActorModel(
        project_id=seeded_project.id,
        name="Customer",
        description="End customer",
    )
    feature = FeatureModel(
        project_id=seeded_project.id,
        name="Checkout",
        description="Checkout feature",
    )
    sync_db_session.add_all([actor, feature])
    sync_db_session.flush()

    res = migrate_project_to_version_control(sync_db_session, seeded_project)
    assert res["status"] == "success"
    assert res["summary"]["actor_count"] >= 1
    assert res["summary"]["feature_count"] >= 1

    sync_db_session.refresh(actor)
    sync_db_session.refresh(feature)

    assert actor.logical_uuid is not None
    assert feature.logical_uuid is not None
    assert actor.workspace_id is not None
    assert feature.workspace_id is not None


def test_migrate_all_projects_atomic_failure_rollback(sync_db_session, seeded_project, monkeypatch):
    """测试当某个项目在 migrate_all_projects_to_version_control 中迁移失败时，抛出 RuntimeError 且回滚该项目的 partial 变动。"""
    from backend.api.modules.version_control.application import baseline_migration

    def mock_fail(db, project):
        raise RuntimeError("Simulated project migration crash")

    monkeypatch.setattr(baseline_migration, "migrate_project_to_version_control", mock_fail)

    import pytest
    with pytest.raises(RuntimeError, match="Version control baseline migration failed"):
        baseline_migration.migrate_all_projects_to_version_control(sync_db_session)

    # 验证没有残留的 main 分支被提交
    branches = sync_db_session.scalars(select(RequirementBranchModel)).all()
    assert len(branches) == 0


def test_repeatable_catchup_backfill_strategy(sync_db_session, seeded_project):
    """验证当项目已有 main 分支时，再次运行迁移可补齐新插入的 workspace_id 为 NULL 的孤儿实体。"""
    from backend.api.modules.version_control.application.baseline_migration import migrate_project_to_version_control
    from backend.database.model import ActorModel, BranchWorkspaceModel

    # 1. 首次迁移，创建 main 与工作区
    res = migrate_project_to_version_control(sync_db_session, seeded_project)
    assert res["status"] == "success"

    # 2. 获取已创建的 main workspace.id
    ws = sync_db_session.scalars(
        select(BranchWorkspaceModel).where(BranchWorkspaceModel.project_id == seeded_project.id)
    ).first()
    assert ws is not None

    # 3. 模拟日常编辑创建 1 个 workspace_id=None 的 Actor 并更新项目元数据
    seeded_project.user_requirements = "Updated User Requirements Text"
    seeded_project.kano_status = "completed"
    new_actor = ActorModel(
        project_id=seeded_project.id,
        name="New Daily Actor",
        description="Created after baseline migration",
        workspace_id=None,
    )
    sync_db_session.add(new_actor)
    sync_db_session.commit()

    # 4. 再次运行迁移，触发 skipped 并执行 repeatable backfill 补齐与元数据同步策略
    res2 = migrate_project_to_version_control(sync_db_session, seeded_project)
    assert res2["status"] == "skipped"
    assert "Repeatable backfill completed" in res2["message"]

    # 5. 校验新 Actor 的 workspace_id 与 Project 元数据同步到 BranchWorkspace
    sync_db_session.refresh(new_actor)
    sync_db_session.refresh(ws)
    assert new_actor.workspace_id == ws.id
    assert new_actor.logical_uuid is not None
    assert ws.user_requirements == "Updated User Requirements Text"
    assert ws.kano_status == "completed"


def test_repeatable_backfill_preserves_other_branch_entities(sync_db_session, seeded_project):
    actor = ActorModel(project_id=seeded_project.id, name="Shared Actor")
    sync_db_session.add(actor)
    sync_db_session.flush()

    migrate_project_to_version_control(sync_db_session, seeded_project)
    main_branch = sync_db_session.scalars(
        select(RequirementBranchModel).where(
            RequirementBranchModel.project_id == seeded_project.id,
            RequirementBranchModel.name == "main",
        )
    ).one()
    other_branch = RequirementBranchModel(
        project_id=seeded_project.id,
        name="other",
        head_commit_id=main_branch.head_commit_id,
        source_commit_id=main_branch.head_commit_id,
    )
    sync_db_session.add(other_branch)
    sync_db_session.flush()
    other_workspace = BranchWorkspaceModel(
        project_id=seeded_project.id,
        branch_id=other_branch.id,
    )
    sync_db_session.add(other_workspace)
    sync_db_session.flush()
    branch_actor = ActorModel(
        project_id=seeded_project.id,
        workspace_id=other_workspace.id,
        logical_uuid=actor.logical_uuid,
        name=actor.name,
    )
    sync_db_session.add(branch_actor)
    sync_db_session.flush()

    result = migrate_project_to_version_control(sync_db_session, seeded_project)

    assert result["status"] == "skipped"
    assert branch_actor.workspace_id == other_workspace.id


def test_migration_only_what_data_and_state_consistency(sync_db_session, seeded_project):
    """验证“只有 What 数据”（仅 Feature/Actor，无 flow/scenario/scope）的项目基线迁移前后的数据一致性。"""
    from backend.api.modules.version_control.application.baseline_migration import migrate_project_to_version_control
    from backend.database.model import ActorModel, FeatureModel, FeatureRelationModel, BranchWorkspaceModel, RequirementCommitModel
    import json

    # 1. 构造“只有 What 数据”的 legacy 项目环境
    # 增加 1 个 Actor
    actor = ActorModel(
        project_id=seeded_project.id,
        name="Legacy Actor",
        description="Leg desc",
        workspace_id=None,
    )
    # 增加 2 个 Feature (一父一子)
    f_parent = FeatureModel(
        project_id=seeded_project.id,
        name="Legacy Parent Feature",
        description="P desc",
        workspace_id=None,
    )
    f_child = FeatureModel(
        project_id=seeded_project.id,
        name="Legacy Child Feature",
        description="C desc",
        workspace_id=None,
    )
    sync_db_session.add_all([actor, f_parent, f_child])
    sync_db_session.commit()

    # 创建父子特征关系
    rel = FeatureRelationModel(
        parent_feature_id=f_parent.id,
        child_feature_id=f_child.id,
        position=1,
        workspace_id=None,
    )
    sync_db_session.add(rel)
    sync_db_session.commit()

    # 2. 执行基线迁移
    res = migrate_project_to_version_control(sync_db_session, seeded_project)
    assert res["status"] == "success"

    # 3. 校验迁移前后的一致性
    ws = sync_db_session.scalars(
        select(BranchWorkspaceModel).where(BranchWorkspaceModel.project_id == seeded_project.id)
    ).first()
    assert ws is not None

    # 实体数量一致
    db_actors = sync_db_session.scalars(select(ActorModel).where(ActorModel.workspace_id == ws.id)).all()
    db_features = sync_db_session.scalars(select(FeatureModel).where(FeatureModel.workspace_id == ws.id)).all()
    assert len(db_actors) == 1
    assert len(db_features) == 2

    # 关系一致性校验
    db_rel = sync_db_session.scalars(select(FeatureRelationModel).where(FeatureRelationModel.workspace_id == ws.id)).first()
    assert db_rel is not None
    assert db_rel.parent_feature_id == f_parent.id
    assert db_rel.child_feature_id == f_child.id

    # 验证 Commit 中的 JSON 内容哈希与对象一致
    commit = sync_db_session.scalars(
        select(RequirementCommitModel).where(RequirementCommitModel.project_id == seeded_project.id)
    ).first()
    assert commit is not None
    
    state = json.loads(commit.state_json)
    # 验证 state_json 只含有 what 数据，其余列表均为空
    assert len(state["actors"]) == 1
    assert len(state["features"]) == 2
    assert len(state["feature_relations"]) == 1
    assert len(state["scenarios"]) == 0
    assert len(state["flows"]) == 0
    assert len(state["scopes"]) == 0

    assert state["actors"][0]["name"] == "Legacy Actor"
    assert state["features"][0]["name"] == "Legacy Child Feature" or state["features"][0]["name"] == "Legacy Parent Feature"


def test_requirement_commit_immutability(sync_db_session, seeded_project):
    """验证 RequirementCommitModel 的不可变性约束：修改已保存的 Commit 将被 ORM 事件监听器拒绝。"""
    from backend.api.modules.version_control.application.baseline_migration import migrate_project_to_version_control
    from backend.database.model import RequirementCommitModel
    import pytest

    # 1. 执行基线迁移，产生基线 Commit
    res = migrate_project_to_version_control(sync_db_session, seeded_project)
    assert res["status"] == "success"

    commit = sync_db_session.scalars(
        select(RequirementCommitModel).where(RequirementCommitModel.project_id == seeded_project.id)
    ).first()
    assert commit is not None

    # 2. 尝试修改 Commit 的 message 并提交，断言抛出 ValueError 不可变异常
    commit.message = "Mutated message after creation"
    with pytest.raises(ValueError, match="RequirementCommitModel is immutable and cannot be updated"):
        sync_db_session.commit()

    sync_db_session.rollback()

