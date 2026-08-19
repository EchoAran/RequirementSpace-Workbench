"""
Tests for Commit Creation, Commit Graph, Workspace Serialization and Diff Service (Phase 3).
覆盖阶段 03 验收：提交固化为不可变状态、预期 head 校验、main 保护、提交图/合并节点、
项目隔离、工作区序列化与当前工作区 vs head 的语义 Diff。
"""
import json

import pytest
from sqlalchemy import select

from backend.database.model import (
    ProjectModel,
    RequirementBranchModel,
    RequirementCommitModel,
    RequirementCommitParentModel,
    BranchWorkspaceModel,
    FeatureModel,
)
from backend.api.modules.version_control.application.branch_service import (
    create_branch,
    compute_workspace_dirty_summary,
)
from backend.api.modules.version_control.application.commit_service import (
    create_commit,
    list_commits,
    get_commit_detail,
    resolve_commit_in_project,
)
from backend.api.modules.version_control.application.workspace_serializer import (
    serialize_workspace,
)
from backend.api.modules.version_control.application.diff_service import (
    get_diff,
    get_entity_diff,
)
from backend.api.modules.version_control.application.errors import (
    CommitNotFoundError,
    HeadChangedError,
    ProtectedBranchError,
)
from backend.api.modules.version_control.domain.serializer import (
    compute_state_hash,
    to_deterministic_json,
)
from backend.api.modules.version_control.schemas import (
    BranchCreateRequest,
    CommitCreateRequest,
)


def _create_feature_branch(db, project_id, name, source_branch_public_id, user_id):
    req = BranchCreateRequest(name=name, description="", source_branch_public_id=source_branch_public_id)
    return create_branch(db, project_id, req, user_id=user_id)


def _modify_feature_description(db, workspace_id, feature_uuid, new_description):
    feature = db.scalars(
        select(FeatureModel).where(
            FeatureModel.workspace_id == workspace_id,
            FeatureModel.logical_uuid == feature_uuid,
        )
    ).first()
    assert feature is not None
    feature.description = new_description
    db.commit()
    return feature


def _workspace_of_branch(db, branch_id):
    return db.scalars(
        select(BranchWorkspaceModel).where(BranchWorkspaceModel.branch_id == branch_id)
    ).first()


def test_serialize_workspace_matches_baseline_and_is_deterministic(seeded_vc_project, sync_db_session):
    """迁移后 main 工作区序列化结果应与基线提交状态完全一致，且重复序列化哈希一致。"""
    p = seeded_vc_project
    baseline = sync_db_session.get(RequirementCommitModel, p.baseline_commit_id)
    state = serialize_workspace(sync_db_session, p.main_workspace)
    head_state = json.loads(baseline.state_json)
    assert state == head_state
    assert serialize_workspace(sync_db_session, p.main_workspace) == state
    assert compute_state_hash(to_deterministic_json(state)) == baseline.state_hash


def test_main_workspace_is_clean_after_baseline(seeded_vc_project, sync_db_session):
    """基线之后 main 工作区不应被标记为存在未提交变更。"""
    p = seeded_vc_project
    head = sync_db_session.get(RequirementCommitModel, p.baseline_commit_id)
    dirty = compute_workspace_dirty_summary(sync_db_session, p.main_workspace, head)
    assert not dirty.is_dirty
    assert dirty.modified_entities_count == 0


def test_create_commit_persists_workspace_state_and_advances_head(seeded_vc_project, sync_db_session):
    """分支上修改功能描述并提交：状态被固化、父关系正确、head 推进、哈希可复算。"""
    p = seeded_vc_project
    baseline = sync_db_session.get(RequirementCommitModel, p.baseline_commit_id)
    branch = _create_feature_branch(
        sync_db_session, p.project.id, "feature/payment", p.main_branch.public_id, p.user.id
    )
    workspace = _workspace_of_branch(sync_db_session, branch.id)
    _modify_feature_description(sync_db_session, workspace.id, p.feat_root.logical_uuid, "分支上的新描述")

    head = sync_db_session.get(RequirementCommitModel, branch.head_commit_id)
    dirty = compute_workspace_dirty_summary(sync_db_session, workspace, head)
    assert dirty.is_dirty

    result = create_commit(
        sync_db_session,
        p.project.id,
        branch.public_id,
        CommitCreateRequest(message="更新支付描述", expected_head_commit_public_id=baseline.public_id),
        user_id=p.user.id,
    )

    assert result.message == "更新支付描述"
    assert result.parent_public_ids == [baseline.public_id]
    assert not result.is_merge
    committed_feature = next(
        f for f in result.state["features"] if f["logical_uuid"] == p.feat_root.logical_uuid
    )
    assert committed_feature["description"] == "分支上的新描述"
    assert result.state_hash == compute_state_hash(to_deterministic_json(result.state))

    updated_branch = sync_db_session.get(RequirementBranchModel, branch.id)
    assert updated_branch.head_commit_id == result.id

    # 提交后工作区应恢复为干净状态（状态与新的 head 一致）
    after_dirty = compute_workspace_dirty_summary(sync_db_session, workspace, updated_branch.head_commit)
    assert not after_dirty.is_dirty


def test_create_commit_rejects_stale_expected_head(seeded_vc_project, sync_db_session):
    """预期 head 落后于分支当前 head 时应抛出 HeadChangedError（防并发覆盖）。"""
    p = seeded_vc_project
    baseline = sync_db_session.get(RequirementCommitModel, p.baseline_commit_id)
    branch = _create_feature_branch(
        sync_db_session, p.project.id, "feature/payment", p.main_branch.public_id, p.user.id
    )

    # 模拟他人已在同分支上提交：推进 head 到一条新提交。
    other = RequirementCommitModel(
        project_id=p.project.id,
        message="他人提交",
        state_json="{}",
        state_hash="o" * 64,
        schema_version="1.0",
        author_user_id=p.user.id,
    )
    sync_db_session.add(other)
    sync_db_session.flush()
    sync_db_session.add(
        RequirementCommitParentModel(commit_id=other.id, parent_commit_id=baseline.id, parent_order=0)
    )
    stored_branch = sync_db_session.get(RequirementBranchModel, branch.id)
    stored_branch.head_commit_id = other.id
    sync_db_session.commit()

    with pytest.raises(HeadChangedError):
        create_commit(
            sync_db_session,
            p.project.id,
            branch.public_id,
            CommitCreateRequest(message="基于过期 head 提交", expected_head_commit_public_id=baseline.public_id),
            user_id=p.user.id,
        )


def test_main_branch_rejects_direct_commit(seeded_vc_project, sync_db_session):
    """main 受保护：任何人都不允许直接提交，只能经 Merge Request 合入。"""
    p = seeded_vc_project
    baseline = sync_db_session.get(RequirementCommitModel, p.baseline_commit_id)
    with pytest.raises(ProtectedBranchError):
        create_commit(
            sync_db_session,
            p.project.id,
            "main",
            CommitCreateRequest(message="直接提交 main", expected_head_commit_public_id=baseline.public_id),
            user_id=p.user.id,
        )


def test_commit_graph_merge_node_and_branch_labels(seeded_vc_project, sync_db_session):
    """提交图：父链正确、merge commit 有两个父节点、分支标签准确。"""
    p = seeded_vc_project
    baseline = sync_db_session.get(RequirementCommitModel, p.baseline_commit_id)

    branch = _create_feature_branch(
        sync_db_session, p.project.id, "feature/payment", p.main_branch.public_id, p.user.id
    )
    workspace = _workspace_of_branch(sync_db_session, branch.id)
    _modify_feature_description(sync_db_session, workspace.id, p.feat_root.logical_uuid, "分支变更")
    branch_commit = create_commit(
        sync_db_session,
        p.project.id,
        branch.public_id,
        CommitCreateRequest(message="分支提交", expected_head_commit_public_id=baseline.public_id),
        user_id=p.user.id,
    )

    # 直接构造一个带两个父节点的 merge commit。
    merge = RequirementCommitModel(
        project_id=p.project.id,
        message="合并",
        state_json='{"a":1}',
        state_hash="m" * 64,
        schema_version="1.0",
        author_user_id=p.user.id,
    )
    sync_db_session.add(merge)
    sync_db_session.flush()
    sync_db_session.add(
        RequirementCommitParentModel(commit_id=merge.id, parent_commit_id=baseline.id, parent_order=0)
    )
    sync_db_session.add(
        RequirementCommitParentModel(commit_id=merge.id, parent_commit_id=branch_commit.id, parent_order=1)
    )
    sync_db_session.commit()

    merge_detail = get_commit_detail(sync_db_session, p.project.id, merge.public_id)
    assert merge_detail.is_merge
    assert len(merge_detail.parent_ids) == 2
    assert set(merge_detail.parent_public_ids) == {baseline.public_id, branch_commit.public_id}

    # 分支可达提交：基线 + 分支提交，不含 merge。
    listing = list_commits(sync_db_session, p.project.id, branch_ref=branch.public_id)
    public_ids = {c.public_id for c in listing.commits}
    assert baseline.public_id in public_ids
    assert branch_commit.public_id in public_ids
    assert merge.public_id not in public_ids
    # 分支 head 指向分支提交，因此该提交应带分支标签。
    branch_summary = next(c for c in listing.commits if c.public_id == branch_commit.public_id)
    assert branch.name in branch_summary.branch_names


def test_commit_queries_are_project_scoped(seeded_vc_project, sync_db_session):
    """提交查询必须限定在当前项目：不能跨项目读取他人提交。"""
    p = seeded_vc_project
    other_project = ProjectModel(
        owner_user_id=p.user.id,
        name="Other Project",
        description="",
        user_requirements="",
        kano_status="missing",
        unlocked_stages="",
    )
    sync_db_session.add(other_project)
    sync_db_session.flush()
    other_commit = RequirementCommitModel(
        project_id=other_project.id,
        message="other",
        state_json="{}",
        state_hash="z" * 64,
        schema_version="1.0",
        author_user_id=p.user.id,
    )
    sync_db_session.add(other_commit)
    sync_db_session.commit()

    assert resolve_commit_in_project(sync_db_session, p.project.id, other_commit.public_id) is None
    with pytest.raises(CommitNotFoundError):
        get_commit_detail(sync_db_session, p.project.id, other_commit.public_id)
    listing = list_commits(sync_db_session, p.project.id)
    assert other_commit.public_id not in {c.public_id for c in listing.commits}


def test_diff_service_workspace_vs_head(seeded_vc_project, sync_db_session):
    """当前工作区 vs head 的默认 Diff 应反映未提交变更，且实体详情返回 base/target 值。"""
    p = seeded_vc_project
    branch = _create_feature_branch(
        sync_db_session, p.project.id, "feature/payment", p.main_branch.public_id, p.user.id
    )
    workspace = _workspace_of_branch(sync_db_session, branch.id)
    _modify_feature_description(sync_db_session, workspace.id, p.feat_root.logical_uuid, "未提交的描述修改")

    result = get_diff(sync_db_session, p.project.id, branch_ref=branch.public_id)
    assert result.base is not None and result.target is not None
    assert result.target.kind == "workspace"
    assert result.summary.total_modified >= 1

    field = next(
        e for e in result.entries
        if e.change_type == "field_changed" and e.field == "description" and e.entity_type == "feature"
    )
    assert field.after == "未提交的描述修改"
    assert field.before == "初始描述"

    entity_diff = get_entity_diff(
        sync_db_session, p.project.id, p.feat_root.logical_uuid, branch_ref=branch.public_id
    )
    assert entity_diff.target_value["description"] == "未提交的描述修改"
    assert entity_diff.base_value["description"] == "初始描述"


def test_diff_between_two_commits(seeded_vc_project, sync_db_session):
    """两个提交之间的显式 ref Diff：只修改功能描述应获得正确分类。"""
    p = seeded_vc_project
    baseline = sync_db_session.get(RequirementCommitModel, p.baseline_commit_id)
    branch = _create_feature_branch(
        sync_db_session, p.project.id, "feature/payment", p.main_branch.public_id, p.user.id
    )
    workspace = _workspace_of_branch(sync_db_session, branch.id)
    _modify_feature_description(sync_db_session, workspace.id, p.feat_root.logical_uuid, "已提交的新描述")
    commit = create_commit(
        sync_db_session,
        p.project.id,
        branch.public_id,
        CommitCreateRequest(message="提交", expected_head_commit_public_id=baseline.public_id),
        user_id=p.user.id,
    )

    result = get_diff(
        sync_db_session,
        p.project.id,
        base_ref=f"commit:{baseline.public_id}",
        target_ref=f"commit:{commit.public_id}",
    )
    assert result.base.kind == "commit" and result.target.kind == "commit"
    field = next(
        e for e in result.entries
        if e.change_type == "field_changed" and e.field == "description"
    )
    assert field.after == "已提交的新描述"

    # 相同提交与自身比较应为空 Diff。
    same = get_diff(
        sync_db_session,
        p.project.id,
        base_ref=f"commit:{commit.public_id}",
        target_ref=f"commit:{commit.public_id}",
    )
    assert same.entries == []
    assert same.summary.total_modified == 0


def test_perception_confirm_writes_to_branch_workspace(seeded_vc_project, sync_db_session):
    """Perception 草稿确认必须写入分支工作区（workspace_id），而不是项目级模型。"""
    import asyncio

    from backend.api.modules.decision_workflow.draft_store import GenerativeDraftStore
    from backend.api.modules.diagnosis_quality.perception.application.draft_confirmer import (
        PerceptionDraftConfirmer,
    )
    from backend.database.model import ActorModel

    p = seeded_vc_project
    branch = _create_feature_branch(
        sync_db_session, p.project.id, "feature/perception", p.main_branch.public_id, p.user.id
    )
    workspace = _workspace_of_branch(sync_db_session, branch.id)

    draft_id = "draft-perception-branch"
    draft_payload = {
        "project_id": p.project.id,
        "filler_kind": "actor",
        "actors": [{"actor_name": "感知用户", "actor_description": "分支上的参与者"}],
        "branch_name": branch.name,
        "head_commit_id": branch.head_commit_id,
        "workspace_id": workspace.id,
    }
    asyncio.run(
        GenerativeDraftStore.save_draft(
            project_id=p.project.id,
            draft_id=draft_id,
            draft_type="perception_slot_filling",
            payload=draft_payload,
            owner_user_id=p.user.id,
            session=sync_db_session,
        )
    )

    result = asyncio.run(
        PerceptionDraftConfirmer().confirm_draft(
            draft_id=draft_id,
            owner_user_id=p.user.id,
            session=sync_db_session,
            branch_name=branch.name,
            head_commit_id=branch.head_commit_id,
            workspace_id=workspace.id,
        )
    )
    assert result["created_count"] == 1

    # 新增的参与者应归属分支工作区；项目级（无 workspace）不应出现该参与者。
    created = sync_db_session.scalars(
        select(ActorModel).where(ActorModel.name == "感知用户")
    ).all()
    assert len(created) == 1
    assert created[0].workspace_id == workspace.id



# ═══════════════════════════════════════════════
# Phase A: SQL 分页 + all 模式 + state_json 裁剪 + 复合索引
# ═══════════════════════════════════════════════

def _create_feature_branch_and_commit(db, project_id, branch_name, message, owner_id):
    """创建 feature 分支并提交一次，返回分支。"""
    from backend.api.modules.version_control.application.branch_service import create_branch
    from backend.api.modules.version_control.schemas import BranchCreateRequest
    branch = create_branch(
        db, project_id, BranchCreateRequest(name=branch_name), user_id=owner_id,
    )
    ws = db.scalars(
        select(BranchWorkspaceModel).where(BranchWorkspaceModel.branch_id == branch.id)
    ).first()
    ws.user_requirements = message
    db.flush()
    cur = db.get(RequirementBranchModel, branch.id)
    create_commit(
        db, project_id, cur.public_id,
        CommitCreateRequest(message=message, expected_head_commit_id=cur.head_commit_id),
        user_id=owner_id,
    )
    return branch


def test_list_commits_all_mode_includes_all_branches(sync_db_session, seeded_vc_project):
    """all=True 返回全项目提交（含 feature 分支提交）；分支过滤只返回该分支可达集。"""
    project = seeded_vc_project.project
    owner = project.owner_user_id
    feature = _create_feature_branch_and_commit(
        sync_db_session, project.id, "feature/all-mode", "branch commit", owner,
    )

    all_res = list_commits(sync_db_session, project.id, all=True)
    assert all_res.total >= 2  # baseline + feature commit
    assert any(c.message == "branch commit" for c in all_res.commits)

    main_only = list_commits(sync_db_session, project.id, branch_ref="main")
    assert main_only.total >= 1
    assert not any(c.message == "branch commit" for c in main_only.commits)


def test_list_commits_pagination_offset_limit_total(sync_db_session, seeded_vc_project):
    """分页 offset/limit/total 正确，且按 (created_at, id) 倒序。"""
    project = seeded_vc_project.project
    owner = project.owner_user_id
    # 在 main 上追加 5 个提交（用 feature 分支避免 main 受保护，但需算全图）。
    for i in range(5):
        _create_feature_branch_and_commit(
            sync_db_session, project.id, f"feature/page-{i}", f"commit-{i}", owner,
        )

    page1 = list_commits(sync_db_session, project.id, all=True, limit=2, offset=0)
    page2 = list_commits(sync_db_session, project.id, all=True, limit=2, offset=2)
    page3 = list_commits(sync_db_session, project.id, all=True, limit=2, offset=4)

    assert page1.total >= 6
    assert page2.total == page1.total
    assert page3.total == page1.total
    assert len(page1.commits) == 2
    assert len(page2.commits) == 2
    assert len(page3.commits) >= 2
    # 时间倒序：page1 的第一个比 page3 的第一个新。
    assert page1.commits[0].created_at >= page3.commits[-1].created_at


def test_list_commits_all_flag_ignores_branch(sync_db_session, seeded_vc_project):
    """all=True 时即使传 branch_ref 也返回全项目。"""
    project = seeded_vc_project.project
    owner = project.owner_user_id
    _create_feature_branch_and_commit(sync_db_session, project.id, "feature/ignored", "ignored commit", owner)

    res = list_commits(sync_db_session, project.id, branch_ref="main", all=True)
    assert any(c.message == "ignored commit" for c in res.commits)


def test_list_commits_page_does_not_load_state_json(sync_db_session, seeded_vc_project):
    """分页列表路径的提交 SELECT 不含 state_json 列（性能约束）。"""
    from sqlalchemy import event

    captured_columns = []

    @event.listens_for(sync_db_session.bind, "before_cursor_execute")
    def _capture(conn, cursor, statement, parameters, context, executemany):
        if "requirement_commits" in statement and "SELECT" in statement:
            captured_columns.append(statement)

    try:
        list_commits(sync_db_session, seeded_vc_project.project.id, all=True)
    finally:
        event.remove(sync_db_session.bind, "before_cursor_execute", _capture)

    # 列表查询的 SELECT 语句不应包含 state_json 列。
    assert captured_columns, "should have captured commit SELECT"
    assert not any("state_json" in stmt for stmt in captured_columns),         "list_commits should not load state_json column"
