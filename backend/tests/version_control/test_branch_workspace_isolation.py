"""
Integration test for BranchWorkspace Model Isolation across concurrent branches.
"""
import pytest
from sqlalchemy import select
from backend.api.modules.version_control.application.baseline_migration import migrate_project_to_version_control
from backend.api.modules.version_control.application.branch_service import (
    resolve_branch_context,
    create_branch,
)
from backend.api.modules.version_control.schemas import BranchCreateRequest
from backend.database.model import FeatureModel, ActorModel, BranchWorkspaceModel


def test_branch_workspace_isolation(sync_db_session, seeded_project):
    """验证从相同基线创建的 2 条分支修改同一需求功能时，其模型与 BranchWorkspace 100% 独立隔离。"""
    # 1. 产生基线并创建 1 个 Feature
    feat = FeatureModel(
        project_id=seeded_project.id,
        name="Original Baseline Feature",
        description="Baseline description",
        workspace_id=None,
    )
    sync_db_session.add(feat)
    sync_db_session.commit()
    migrate_project_to_version_control(sync_db_session, seeded_project)

    # 2. 从 main 分支分别创建 Branch A 和 Branch B
    branch_a_res = create_branch(
        sync_db_session,
        seeded_project.id,
        BranchCreateRequest(name="feature/branch-a", source_branch_public_id="main"),
    )
    branch_b_res = create_branch(
        sync_db_session,
        seeded_project.id,
        BranchCreateRequest(name="feature/branch-b", source_branch_public_id="main"),
    )

    _, ws_a, _ = resolve_branch_context(sync_db_session, seeded_project.id, branch_a_res.public_id)
    _, ws_b, _ = resolve_branch_context(sync_db_session, seeded_project.id, branch_b_res.public_id)

    assert ws_a.id != ws_b.id

    # 3. 分别在 Branch A 和 Branch B 的工作区中查询属于该 workspace 的 Feature
    stmt_a = select(FeatureModel).where(FeatureModel.workspace_id == ws_a.id)
    feat_a = sync_db_session.scalars(stmt_a).first()

    stmt_b = select(FeatureModel).where(FeatureModel.workspace_id == ws_b.id)
    feat_b = sync_db_session.scalars(stmt_b).first()

    assert feat_a is not None
    assert feat_b is not None
    assert feat_a.id != feat_b.id
    # 继承相同的逻辑 UUID
    assert feat_a.logical_uuid == feat_b.logical_uuid

    # 4. 在 Branch A 中修改 Feature 名称为 "Feature A Spec"
    feat_a.name = "Feature A Spec"
    sync_db_session.flush()

    # 在 Branch B 中修改 Feature 名称为 "Feature B Spec"
    feat_b.name = "Feature B Spec"
    sync_db_session.flush()
    sync_db_session.commit()

    # 5. 重新刷新并验证隔离性
    sync_db_session.refresh(feat_a)
    sync_db_session.refresh(feat_b)

    assert feat_a.name == "Feature A Spec"
    assert feat_b.name == "Feature B Spec"
