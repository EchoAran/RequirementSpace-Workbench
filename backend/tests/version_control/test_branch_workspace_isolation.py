"""
Integration test for BranchWorkspace Model Isolation across concurrent branches.
"""
import pytest
from sqlalchemy import select

from backend.api.modules.version_control.application.clean_initialization import (
    create_initial_workspace,
    finalize_initial_commit,
    initialize_project_version_control,
)
from backend.api.modules.version_control.application.branch_service import (
    create_branch,
    resolve_branch_context,
)
from backend.api.modules.version_control.schemas import BranchCreateRequest
from backend.database.model import FeatureModel


def test_branch_workspace_isolation(sync_db_session, seeded_project):
    """验证从相同基线创建的 2 条分支修改同一需求功能时，其模型与 BranchWorkspace 100% 独立隔离。"""
    # 1. 产生基线并创建 1 个 Feature
    main_branch, main_workspace = create_initial_workspace(sync_db_session, seeded_project)
    feat = FeatureModel(
        project_id=seeded_project.id,
        name="Original Baseline Feature",
        description="Baseline description",
        workspace_id=main_workspace.id,
    )
    sync_db_session.add(feat)
    sync_db_session.flush()
    finalize_initial_commit(sync_db_session, seeded_project, main_branch, main_workspace)
    sync_db_session.commit()

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


def test_user_requirements_workspace_isolation(sync_db_session, seeded_project):
    """验证分支工作区的 user_requirements 独立隔离，不互相污染。"""
    initialize_project_version_control(sync_db_session, seeded_project)

    branch_a_res = create_branch(
        sync_db_session,
        seeded_project.id,
        BranchCreateRequest(name="feature/req-a", source_branch_public_id="main"),
    )
    branch_b_res = create_branch(
        sync_db_session,
        seeded_project.id,
        BranchCreateRequest(name="feature/req-b", source_branch_public_id="main"),
    )

    _, ws_a, _ = resolve_branch_context(sync_db_session, seeded_project.id, branch_a_res.public_id)
    _, ws_b, _ = resolve_branch_context(sync_db_session, seeded_project.id, branch_b_res.public_id)
    _, ws_main, _ = resolve_branch_context(sync_db_session, seeded_project.id, "main")

    ws_a.user_requirements = "Requirements for Feature A"
    ws_b.user_requirements = "Requirements for Feature B"
    sync_db_session.commit()

    sync_db_session.refresh(ws_a)
    sync_db_session.refresh(ws_b)
    sync_db_session.refresh(ws_main)

    assert ws_a.user_requirements == "Requirements for Feature A"
    assert ws_b.user_requirements == "Requirements for Feature B"
    assert ws_main.user_requirements != "Requirements for Feature A"
    assert ws_main.user_requirements != "Requirements for Feature B"


def test_resolve_branch_fail_closed(sync_db_session, seeded_project):
    """验证当分支存在但 BranchWorkspace 缺失时，resolve_branch_context 严格抛出异常 (Fail-Closed)。"""
    initialize_project_version_control(sync_db_session, seeded_project)

    branch_res = create_branch(
        sync_db_session,
        seeded_project.id,
        BranchCreateRequest(name="feature/broken-ws", source_branch_public_id="main"),
    )
    _, ws, _ = resolve_branch_context(sync_db_session, seeded_project.id, branch_res.public_id)

    # 模拟工作区意外缺失
    sync_db_session.delete(ws)
    sync_db_session.commit()

    with pytest.raises(ValueError, match="BranchWorkspace not found"):
        resolve_branch_context(sync_db_session, seeded_project.id, branch_res.public_id)
