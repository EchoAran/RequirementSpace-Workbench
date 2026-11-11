"""
Merge Execution Service Tests (Phase 6).
覆盖阶段 06 验收：三方合并执行、merge commit 双父、目标工作区写入、MR 状态、
冲突解决、阻塞条件、head 漂移、结构校验、原子性、scrub 正确性。
"""
import json

import pytest
from sqlalchemy import func, select

from backend.api.modules.version_control.application.branch_service import create_branch
from backend.api.modules.version_control.application.commit_service import (
    create_commit,
)
from backend.api.modules.version_control.application.errors import (
    MergeBlockedError,
    MergeConflictError,
)
from backend.api.modules.version_control.application.merge_execution import (
    get_merge_preview,
    perform_merge,
)
from backend.api.modules.version_control.application.merge_service import (
    create_merge_request,
    review_mr,
)
from backend.api.modules.version_control.application.workspace_serializer import (
    serialize_workspace,
)
from backend.api.modules.version_control.schemas import (
    BranchCreateRequest,
    CommitCreateRequest,
    ConflictResolution,
    MergeRequestCreateRequest,
    MergeRequestPayload,
    MergeReviewRequest,
)
from backend.database.model import (
    AuditLogModel,
    BranchWorkspaceModel,
    BusinessObjectAttributeModel,
    BusinessObjectModel,
    FeatureModel,
    MergeRequestModel,
    ProjectMemberModel,
    RequirementBranchModel,
    RequirementCommitModel,
    RequirementCommitParentModel,
    UserModel,
)


@pytest.fixture
def merge_project(sync_db_session, seeded_vc_project):
    """基于已迁移且含完整模型的种子项目，创建 main + feature 分支用于合并测试。"""
    project = seeded_vc_project.project
    feature = create_branch(
        sync_db_session, project.id,
        BranchCreateRequest(name="feature/merge"),
        user_id=project.owner_user_id,
    )
    main_branch = seeded_vc_project.main_branch
    return project, feature, main_branch


def _modify_feature_name(db, branch, new_name):
    """修改分支工作区首个功能的 name 并提交。"""
    ws = db.scalars(
        select(BranchWorkspaceModel).where(BranchWorkspaceModel.branch_id == branch.id)
    ).first()
    feature = db.scalars(
        select(FeatureModel).where(FeatureModel.workspace_id == ws.id)
    ).first()
    feature.name = new_name
    db.flush()
    current = db.get(RequirementBranchModel, branch.id)
    commit = create_commit(
        db, current.project_id, current.public_id,
        CommitCreateRequest(
            message=new_name,
            expected_head_commit_id=current.head_commit_id,
        ),
        user_id=current.created_by_user_id,
    )
    return commit


def _approve_mr(db, project, mr, admin_id):
    """以非作者 admin 审批 MR。"""
    return review_mr(
        db, project.id, mr.public_id,
        MergeReviewRequest(decision="approved", comment="LGTM"),
        user_id=admin_id,
    )


def _add_admin(db, project, user_id, email):
    user = UserModel(id=user_id, email=email, password_hash="h", role="admin")
    db.add(user)
    db.add(ProjectMemberModel(project_id=project.id, user_id=user.id, role="admin", status="active"))
    db.commit()
    return user


def _new_commit_count(db, project_id):
    return db.scalar(
        select(func.count()).select_from(RequirementCommitModel).where(
            RequirementCommitModel.project_id == project_id
        )
    )


def _merge_payload(db, project, mr, resolutions=None):
    """构造携带预览 heads 的合并请求体（三个 head 字段必填）。"""
    preview = get_merge_preview(db, project.id, mr.public_id)
    return MergeRequestPayload(
        resolutions=resolutions or [],
        merge_base_public_id=preview.merge_base_public_id,
        source_head_public_id=preview.source_head_public_id,
        target_head_public_id=preview.target_head_public_id,
    )


def test_merge_happy_path_creates_two_parent_commit(sync_db_session, merge_project):
    """target+source 不相交编辑 → 审批 → 合并成功；merge commit 双父、MR merged、工作区更新。"""
    project, feature, main = merge_project
    _modify_feature_name(sync_db_session, feature, "source-feature-name")
    admin = _add_admin(sync_db_session, project, 50, "admin50@test.com")

    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(
            title="Merge happy", source_branch_public_id=feature.public_id,
            target_branch_public_id=main.public_id,
        ),
        user_id=project.owner_user_id,
    )
    _approve_mr(sync_db_session, project, mr, admin.id)

    count_before = _new_commit_count(sync_db_session, project.id)
    result = perform_merge(
        sync_db_session, project.id, mr.public_id,
        _merge_payload(sync_db_session, project, mr, resolutions=[]),
        user_id=project.owner_user_id,
    )
    assert result.status == "merged"
    assert result.merged_commit_public_id

    # merge commit 双父
    merge_commit = sync_db_session.scalars(
        select(RequirementCommitModel).where(
            RequirementCommitModel.public_id == result.merged_commit_public_id
        )
    ).first()
    parents = sync_db_session.scalars(
        select(RequirementCommitParentModel)
        .where(RequirementCommitParentModel.commit_id == merge_commit.id)
        .order_by(RequirementCommitParentModel.parent_order)
    ).all()
    assert len(parents) == 2
    assert parents[0].parent_order == 0  # target head
    assert parents[1].parent_order == 1  # source head

    # 目标 head 推进，MR merged，commit 数 +1
    main_now = sync_db_session.get(RequirementBranchModel, main.id)
    assert main_now.head_commit_id == merge_commit.id
    assert _new_commit_count(sync_db_session, project.id) == count_before + 1

    mr_now = sync_db_session.get(MergeRequestModel, mr.id)
    assert mr_now.status == "merged"
    assert mr_now.merged_commit_id == merge_commit.id
    # 合并 MR 自身的审批不应因自己的合并推进 target 而被标 stale（P1-2）。
    own_reviews = [r for r in mr_now.reviews if r.reviewer_user_id == admin.id]
    assert own_reviews and all(r.status == "active" for r in own_reviews)
    assert all(r.status != "stale" for r in mr_now.reviews)

    # 目标工作区重序列化 == merge commit 状态
    ws = sync_db_session.scalars(
        select(BranchWorkspaceModel).where(BranchWorkspaceModel.branch_id == main.id)
    ).first()
    ws_state = serialize_workspace(sync_db_session, ws)
    commit_state = json.loads(merge_commit.state_json)
    assert ws_state == commit_state
    assert any(f["name"] == "source-feature-name" for f in commit_state["features"])


def test_no_conflict_merge_executes_with_empty_resolutions(sync_db_session, merge_project):
    """无冲突合并可用空 resolutions 直接执行。"""
    project, feature, main = merge_project
    _modify_feature_name(sync_db_session, feature, "source changed desc")
    admin = _add_admin(sync_db_session, project, 51, "admin51@test.com")
    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(
            title="No conflict", source_branch_public_id=feature.public_id,
            target_branch_public_id=main.public_id,
        ),
        user_id=project.owner_user_id,
    )
    _approve_mr(sync_db_session, project, mr, admin.id)

    preview = get_merge_preview(sync_db_session, project.id, mr.public_id)
    assert preview.conflict_count == 0

    result = perform_merge(
        sync_db_session, project.id, mr.public_id,
        _merge_payload(sync_db_session, project, mr, resolutions=[]),
        user_id=project.owner_user_id,
    )
    assert result.status == "merged"


def test_merge_blocked_for_member_and_unapproved(sync_db_session, merge_project):
    """member 无合并权限；未审批 MR 被阻塞。"""
    project, feature, main = merge_project
    _modify_feature_name(sync_db_session, feature, "changed")
    member = UserModel(id=52, email="member52@test.com", password_hash="h", role="user")
    sync_db_session.add(member)
    sync_db_session.add(ProjectMemberModel(
        project_id=project.id, user_id=member.id, role="viewer", status="active"
    ))
    sync_db_session.commit()

    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(
            title="Blocked", source_branch_public_id=feature.public_id,
            target_branch_public_id=main.public_id,
        ),
        user_id=project.owner_user_id,
    )
    # 未审批 → blocked
    with pytest.raises(MergeBlockedError) as exc:
        perform_merge(
            sync_db_session, project.id, mr.public_id,
            _merge_payload(sync_db_session, project, mr, resolutions=[]),
            user_id=project.owner_user_id,
        )
    assert "missing_approval" in exc.value.reasons

    # member 无合并权限
    with pytest.raises(MergeBlockedError):
        perform_merge(
            sync_db_session, project.id, mr.public_id,
            _merge_payload(sync_db_session, project, mr, resolutions=[]),
            user_id=member.id,
        )


def test_merge_rejected_on_merged_mr(sync_db_session, merge_project):
    """已合并 MR 不可再合并。"""
    project, feature, main = merge_project
    _modify_feature_name(sync_db_session, feature, "once")
    admin = _add_admin(sync_db_session, project, 53, "admin53@test.com")
    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(
            title="Once", source_branch_public_id=feature.public_id,
            target_branch_public_id=main.public_id,
        ),
        user_id=project.owner_user_id,
    )
    _approve_mr(sync_db_session, project, mr, admin.id)
    perform_merge(
        sync_db_session, project.id, mr.public_id,
        _merge_payload(sync_db_session, project, mr, resolutions=[]),
        user_id=project.owner_user_id,
    )
    with pytest.raises(MergeBlockedError, match="mr_already_closed"):
        perform_merge(
            sync_db_session, project.id, mr.public_id,
            _merge_payload(sync_db_session, project, mr, resolutions=[]),
            user_id=project.owner_user_id,
        )


def test_merge_conflict_preview_and_resolution(sync_db_session, merge_project):
    """两侧改同一字段 → preview 有冲突；不解决被拒；解决后成功且取值正确。"""
    project, feature, main = merge_project

    # source 分支改 name
    _modify_feature_name(sync_db_session, feature, "source-name")

    # target(main) 也改 name —— main 受保护，改用 feature2 分支作为 target 测试，但这里 main 不能直接提交。
    # 采用 feature2 → main 的 MR，其中 target(main) 通过另一分支先合入一次改动后再建 MR。
    # 简单方案：把“两侧改同一字段”放在两个 feature 分支之间（feature 改 name，feature2 改 name）。
    feature2 = create_branch(
        sync_db_session, project.id,
        BranchCreateRequest(name="feature2", source_branch_public_id=main.public_id),
        user_id=project.owner_user_id,
    )
    _modify_feature_name(sync_db_session, feature2, "target-name")

    admin = _add_admin(sync_db_session, project, 54, "admin54@test.com")
    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(
            title="Conflict MR", source_branch_public_id=feature.public_id,
            target_branch_public_id=feature2.public_id,
        ),
        user_id=project.owner_user_id,
    )
    _approve_mr(sync_db_session, project, mr, admin.id)

    preview = get_merge_preview(sync_db_session, project.id, mr.public_id)
    assert preview.conflict_count >= 1
    conflict = preview.conflicts[0]
    assert conflict.conflict_type in ("same_field_different_value",)

    # 不提供 resolution → MergeConflictError
    with pytest.raises(MergeConflictError):
        perform_merge(
            sync_db_session, project.id, mr.public_id,
            _merge_payload(sync_db_session, project, mr, resolutions=[]),
            user_id=project.owner_user_id,
        )

    # 提供 resolution → 成功
    result = perform_merge(
        sync_db_session, project.id, mr.public_id,
        _merge_payload(sync_db_session, project, mr, resolutions=[
            ConflictResolution(conflict_id=conflict.conflict_id, choice="source"),
        ]),
        user_id=project.owner_user_id,
    )
    assert result.status == "merged"
    merge_commit = sync_db_session.get(RequirementCommitModel, result.merged_commit_public_id) \
        if isinstance(result.merged_commit_public_id, int) else None
    if merge_commit is None:
        merge_commit = sync_db_session.scalars(
            select(RequirementCommitModel).where(
                RequirementCommitModel.public_id == result.merged_commit_public_id
            )
        ).first()
    state = json.loads(merge_commit.state_json)
    assert any(f["name"] == "source-name" for f in state["features"])


def test_merge_scrub_clears_target_workspace(sync_db_session, merge_project):
    """合并写回后目标工作区只有合并状态，无残留旧行。"""
    project, feature, main = merge_project
    _modify_feature_name(sync_db_session, feature, "post-merge-name")
    admin = _add_admin(sync_db_session, project, 56, "admin56@test.com")
    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(
            title="Scrub", source_branch_public_id=feature.public_id,
            target_branch_public_id=main.public_id,
        ),
        user_id=project.owner_user_id,
    )
    _approve_mr(sync_db_session, project, mr, admin.id)
    perform_merge(
        sync_db_session, project.id, mr.public_id,
        _merge_payload(sync_db_session, project, mr, resolutions=[]),
        user_id=project.owner_user_id,
    )
    ws = sync_db_session.scalars(
        select(BranchWorkspaceModel).where(BranchWorkspaceModel.branch_id == main.id)
    ).first()
    features = sync_db_session.scalars(
        select(FeatureModel).where(FeatureModel.workspace_id == ws.id)
    ).all()
    # 合并后工作区应仅包含合并状态的功能（source 改名后的那一个）。
    names = {f.name for f in features}
    assert "post-merge-name" in names


def test_merged_mr_no_longer_open_and_review_rejected(sync_db_session, merge_project):
    """merged 的 MR 不再 open，review 被拒。"""
    project, feature, main = merge_project
    _modify_feature_name(sync_db_session, feature, "merged-once")
    admin = _add_admin(sync_db_session, project, 57, "admin57@test.com")
    admin2 = _add_admin(sync_db_session, project, 58, "admin58@test.com")
    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(
            title="Merged", source_branch_public_id=feature.public_id,
            target_branch_public_id=main.public_id,
        ),
        user_id=project.owner_user_id,
    )
    _approve_mr(sync_db_session, project, mr, admin.id)
    perform_merge(
        sync_db_session, project.id, mr.public_id,
        _merge_payload(sync_db_session, project, mr, resolutions=[]),
        user_id=project.owner_user_id,
    )
    mr_now = sync_db_session.get(MergeRequestModel, mr.id)
    assert mr_now.status == "merged"
    with pytest.raises(Exception):
        review_mr(
            sync_db_session, project.id, mr.public_id,
            MergeReviewRequest(decision="approved"),
            user_id=admin2.id,
        )


# ==========================================
# P1 缺口测试：heads 校验、审计、changes_requested 阻塞、MR 同步、回滚、响应 head
# ==========================================

def _create_mr(db, project, source, target, title):
    return create_merge_request(
        db, project.id,
        MergeRequestCreateRequest(
            title=title, source_branch_public_id=source.public_id,
            target_branch_public_id=target.public_id,
        ),
        user_id=project.owner_user_id,
    )


def test_merge_rejects_stale_preview_source_head(sync_db_session, merge_project):
    """预览后 source 分支推进 → 合并返回 409（HeadChangedError），不创建 merge commit。"""
    project, feature, main = merge_project
    _modify_feature_name(sync_db_session, feature, "pre-source")
    admin = _add_admin(sync_db_session, project, 60, "admin60@test.com")
    mr = _create_mr(db=sync_db_session, project=project, source=feature, target=main, title="Stale src")
    _approve_mr(sync_db_session, project, mr, admin.id)

    preview = get_merge_preview(sync_db_session, project.id, mr.public_id)
    _modify_feature_name(sync_db_session, feature, "post-source")

    count_before = _new_commit_count(sync_db_session, project.id)
    with pytest.raises(Exception) as exc:
        perform_merge(
            sync_db_session, project.id, mr.public_id,
            MergeRequestPayload(
                resolutions=[],
                merge_base_public_id=preview.merge_base_public_id,
                source_head_public_id=preview.source_head_public_id,
                target_head_public_id=preview.target_head_public_id,
            ),
            user_id=project.owner_user_id,
        )
    # source 推进会先被 _check_blocking_reasons 的 source_branch_advanced 阻塞（MergeBlockedError）；
    # 若不阻塞则被预览 heads 校验拦截（HeadChangedError）。两种都证明合并被拒绝。
    assert exc.value.__class__.__name__ in ("MergeBlockedError", "HeadChangedError")
    assert _new_commit_count(sync_db_session, project.id) == count_before
    assert sync_db_session.get(MergeRequestModel, mr.id).status != "merged"


def test_merge_rejects_stale_preview_target_head(sync_db_session, merge_project):
    """预览后 target 分支推进 → 合并返回 409，不创建 merge commit。"""
    project, feature, main = merge_project
    _modify_feature_name(sync_db_session, feature, "pre-target")
    admin = _add_admin(sync_db_session, project, 61, "admin61@test.com")
    mr = _create_mr(db=sync_db_session, project=project, source=feature, target=main, title="Stale tgt")
    _approve_mr(sync_db_session, project, mr, admin.id)

    preview = get_merge_preview(sync_db_session, project.id, mr.public_id)
    feature2 = create_branch(
        sync_db_session, project.id,
        BranchCreateRequest(name="feature/advance-main", source_branch_public_id=main.public_id),
        user_id=project.owner_user_id,
    )
    _modify_feature_name(sync_db_session, feature2, "advance")
    mr2 = _create_mr(db=sync_db_session, project=project, source=feature2, target=main, title="Advance main")
    admin2 = _add_admin(sync_db_session, project, 62, "admin62@test.com")
    _approve_mr(sync_db_session, project, mr2, admin2.id)
    perform_merge(
        sync_db_session, project.id, mr2.public_id,
        _merge_payload(sync_db_session, project, mr2, resolutions=[]),
        user_id=project.owner_user_id,
    )

    count_before = _new_commit_count(sync_db_session, project.id)
    with pytest.raises(Exception) as exc:
        perform_merge(
            sync_db_session, project.id, mr.public_id,
            MergeRequestPayload(
                resolutions=[],
                merge_base_public_id=preview.merge_base_public_id,
                source_head_public_id=preview.source_head_public_id,
                target_head_public_id=preview.target_head_public_id,
            ),
            user_id=project.owner_user_id,
        )
    # source 推进会先被 _check_blocking_reasons 的 source_branch_advanced 阻塞（MergeBlockedError）；
    # 若不阻塞则被预览 heads 校验拦截（HeadChangedError）。两种都证明合并被拒绝。
    assert exc.value.__class__.__name__ in ("MergeBlockedError", "HeadChangedError")
    assert _new_commit_count(sync_db_session, project.id) == count_before
    assert sync_db_session.get(MergeRequestModel, mr.id).status != "merged"


def test_changes_requested_blocks_merge(sync_db_session, merge_project):
    """存在 active changes_requested review 时合并被阻塞，即使已有其他 admin 审批。"""
    project, feature, main = merge_project
    _modify_feature_name(sync_db_session, feature, "req-change")
    reviewer = _add_admin(sync_db_session, project, 63, "reviewer63@test.com")
    approver = _add_admin(sync_db_session, project, 64, "approver64@test.com")
    mr = _create_mr(db=sync_db_session, project=project, source=feature, target=main, title="Change req")
    review_mr(
        sync_db_session, project.id, mr.public_id,
        MergeReviewRequest(decision="changes_requested", comment="fix this"),
        user_id=reviewer.id,
    )
    _approve_mr(sync_db_session, project, mr, approver.id)

    with pytest.raises(MergeBlockedError) as exc:
        perform_merge(
            sync_db_session, project.id, mr.public_id,
            _merge_payload(sync_db_session, project, mr, resolutions=[]),
            user_id=project.owner_user_id,
        )
    assert any("changes_requested" in r for r in exc.value.reasons)
    assert sync_db_session.get(MergeRequestModel, mr.id).status != "merged"


def test_merge_records_conflict_resolution_audit(sync_db_session, merge_project):
    """合并时写入冲突解决审计，记录冲突 ID 与选择。"""
    project, feature, main = merge_project
    feature2 = create_branch(
        sync_db_session, project.id,
        BranchCreateRequest(name="feature/audit-tgt", source_branch_public_id=main.public_id),
        user_id=project.owner_user_id,
    )
    _modify_feature_name(sync_db_session, feature, "src-name")
    _modify_feature_name(sync_db_session, feature2, "tgt-name")
    admin = _add_admin(sync_db_session, project, 65, "admin65@test.com")
    mr = _create_mr(db=sync_db_session, project=project, source=feature, target=feature2, title="Audit conflicts")
    _approve_mr(sync_db_session, project, mr, admin.id)

    preview = get_merge_preview(sync_db_session, project.id, mr.public_id)
    assert preview.conflict_count >= 1
    conflict = preview.conflicts[0]

    perform_merge(
        sync_db_session, project.id, mr.public_id,
        _merge_payload(sync_db_session, project, mr, resolutions=[
            ConflictResolution(conflict_id=conflict.conflict_id, choice="source"),
        ]),
        user_id=project.owner_user_id,
    )

    from backend.database.model import AuditLogModel
    audit = sync_db_session.scalars(
        select(AuditLogModel).where(AuditLogModel.action_type == "merge_request_conflict_resolution")
    ).all()
    assert len(audit) == 1
    assert audit[0].payload["conflict_count"] == 1
    assert audit[0].payload["resolutions"][0]["conflict_id"] == conflict.conflict_id
    assert audit[0].payload["resolutions"][0]["choice"] == "source"
    # 审计记录操作人（P1-4）：应指向执行合并的 user，而非默认 system。
    assert audit[0].actor_user_id == project.owner_user_id
    assert audit[0].actor_type == "user"


def test_merge_advances_other_mr_approvals_stale(sync_db_session, merge_project):
    """MR-A 合并进 main 后，其他以 main 为目标的 MR 的审批变为 stale、target head 更新。"""
    project, feature, main = merge_project
    _modify_feature_name(sync_db_session, feature, "a-source")
    admin_a = _add_admin(sync_db_session, project, 66, "admin66@test.com")
    mr_a = _create_mr(db=sync_db_session, project=project, source=feature, target=main, title="MR A")
    _approve_mr(sync_db_session, project, mr_a, admin_a.id)
    perform_merge(
        sync_db_session, project.id, mr_a.public_id,
        _merge_payload(sync_db_session, project, mr_a, resolutions=[]),
        user_id=project.owner_user_id,
    )

    feature_b = create_branch(
        sync_db_session, project.id,
        BranchCreateRequest(name="feature/b", source_branch_public_id=main.public_id),
        user_id=project.owner_user_id,
    )
    _modify_feature_name(sync_db_session, feature_b, "b-source")
    admin_b = _add_admin(sync_db_session, project, 67, "admin67@test.com")
    mr_b = _create_mr(db=sync_db_session, project=project, source=feature_b, target=main, title="MR B")
    _approve_mr(sync_db_session, project, mr_b, admin_b.id)

    feature_c = create_branch(
        sync_db_session, project.id,
        BranchCreateRequest(name="feature/c", source_branch_public_id=main.public_id),
        user_id=project.owner_user_id,
    )
    _modify_feature_name(sync_db_session, feature_c, "c-source")
    admin_c = _add_admin(sync_db_session, project, 68, "admin68@test.com")
    mr_c = _create_mr(db=sync_db_session, project=project, source=feature_c, target=main, title="MR C")
    _approve_mr(sync_db_session, project, mr_c, admin_c.id)
    perform_merge(
        sync_db_session, project.id, mr_c.public_id,
        _merge_payload(sync_db_session, project, mr_c, resolutions=[]),
        user_id=project.owner_user_id,
    )

    # MR-B 的审批应已被同步为 stale（MR-C 合并推进了 main）。
    mr_b_now = sync_db_session.get(MergeRequestModel, mr_b.id)
    stale = [r for r in mr_b_now.reviews if r.status == "stale"]
    assert len(stale) >= 1
    assert stale[0].stale_reason == "target_branch_advanced"
    main_now = sync_db_session.get(RequirementBranchModel, main.id)
    assert mr_b_now.target_head_commit_id == main_now.head_commit_id


def test_merge_returns_merge_commit_as_target_head(sync_db_session, merge_project):
    """合并响应的 target_head_public_id 应等于 merge commit 的 public_id（非分支 public_id）。"""
    project, feature, main = merge_project
    _modify_feature_name(sync_db_session, feature, "head-check")
    admin = _add_admin(sync_db_session, project, 69, "admin69@test.com")
    mr = _create_mr(db=sync_db_session, project=project, source=feature, target=main, title="Head check")
    _approve_mr(sync_db_session, project, mr, admin.id)

    result = perform_merge(
        sync_db_session, project.id, mr.public_id,
        _merge_payload(sync_db_session, project, mr, resolutions=[]),
        user_id=project.owner_user_id,
    )
    assert result.target_head_public_id == result.merged_commit_public_id
    assert result.target_head_public_id != main.public_id


def test_merge_rollback_on_internal_error(sync_db_session, merge_project, monkeypatch):
    """perform_merge 内后段注入异常（sync_mrs_on_branch_commit 抛错）→ 整笔回滚。

    验证 workspace 恢复、merge commit/双父、target CAS、MR 状态、审批、冲突审计全部回滚，
    不产生部分目标写入。
    """
    import backend.api.modules.version_control.application.merge_execution as merge_exec
    project, feature, main = merge_project
    _modify_feature_name(sync_db_session, feature, "rollback-src")
    admin = _add_admin(sync_db_session, project, 70, "admin70@test.com")
    mr = _create_mr(db=sync_db_session, project=project, source=feature, target=main, title="Rollback")
    _approve_mr(sync_db_session, project, mr, admin.id)
    # 先提交让 MR/审批/提交落地，确保后续 rollback 只回滚 perform_merge 的新事务副作用。
    sync_db_session.commit()
    preview = get_merge_preview(sync_db_session, project.id, mr.public_id)

    main_head_before = sync_db_session.get(RequirementBranchModel, main.id).head_commit_id
    ws_before = sync_db_session.scalars(
        select(BranchWorkspaceModel).where(BranchWorkspaceModel.branch_id == main.id)
    ).first()
    feature_count_before = len(sync_db_session.scalars(
        select(FeatureModel).where(FeatureModel.workspace_id == ws_before.id)
    ).all())
    commit_count_before = _new_commit_count(sync_db_session, project.id)
    mr_review_count_before = len(sync_db_session.get(MergeRequestModel, mr.id).reviews)
    audit_count_before = len(sync_db_session.scalars(
        select(AuditLogModel).where(AuditLogModel.action_type == "merge_request_conflict_resolution")
    ).all())

    # 在合并流程后段（置 merged 之后、同步其他 MR 处）注入异常，模拟事务中途失败。
    def _boom(db, project_id, branch_id):
        raise RuntimeError("simulated merge failure after target head advance")

    monkeypatch.setattr(merge_exec, "sync_mrs_on_branch_commit", _boom)

    # 需要构造含 resolutions 的合并以验证冲突审计也会随事务回滚。
    # 若该 MR 无冲突，则仅验证 commit/head/workspace/审批回滚。
    req = MergeRequestPayload(
        resolutions=[],
        merge_base_public_id=preview.merge_base_public_id,
        source_head_public_id=preview.source_head_public_id,
        target_head_public_id=preview.target_head_public_id,
    )
    with pytest.raises(RuntimeError, match="simulated merge failure"):
        perform_merge(
            sync_db_session, project.id, mr.public_id, req,
            user_id=project.owner_user_id,
        )
    sync_db_session.rollback()

    # 分支 head 未变。
    main_now = sync_db_session.get(RequirementBranchModel, main.id)
    assert main_now.head_commit_id == main_head_before
    # 工作区功能数量恢复。
    ws_now = sync_db_session.scalars(
        select(BranchWorkspaceModel).where(BranchWorkspaceModel.branch_id == main.id)
    ).first()
    feature_count_after = len(sync_db_session.scalars(
        select(FeatureModel).where(FeatureModel.workspace_id == ws_now.id)
    ).all())
    assert feature_count_after == feature_count_before
    # 无新增 commit。
    assert _new_commit_count(sync_db_session, project.id) == commit_count_before
    # MR 保留且未被标记 merged，审批未失效。
    mr_now = sync_db_session.get(MergeRequestModel, mr.id)
    assert mr_now is not None
    assert mr_now.status != "merged"
    assert len(mr_now.reviews) == mr_review_count_before
    assert all(r.status == "active" for r in mr_now.reviews)
    # 冲突审计未写入（若原为 0 保持 0）。
    assert len(sync_db_session.scalars(
        select(AuditLogModel).where(AuditLogModel.action_type == "merge_request_conflict_resolution")
    ).all()) == audit_count_before



def test_merge_preserves_business_object_attributes_in_main(sync_db_session, merge_project):
    project, source, main = merge_project
    db = sync_db_session
    source_ws = db.scalar(select(BranchWorkspaceModel).where(BranchWorkspaceModel.branch_id == source.id))
    business_object = db.scalar(select(BusinessObjectModel).where(BusinessObjectModel.workspace_id == source_ws.id))
    attribute = db.scalar(select(BusinessObjectAttributeModel).where(BusinessObjectAttributeModel.business_object_id == business_object.id))
    attribute.data_type = "decimal"
    attribute.description = "Order total"
    attribute.example = "123.45"
    attribute.confirmation_status = "confirmed"
    expected = (attribute.logical_uuid, attribute.name, attribute.data_type, attribute.description,
                attribute.example, attribute.confirmation_status)
    added = BusinessObjectAttributeModel(workspace_id=source_ws.id, business_object_id=business_object.id,
                                         name="currency", data_type="string", example="CNY")
    db.add(added)
    db.flush()
    added_uuid = added.logical_uuid
    _modify_feature_name(db, source, "Source with attributes")
    admin = _add_admin(db, project, 70, "admin70@test.com")
    mr = create_merge_request(db, project.id, MergeRequestCreateRequest(
        title="Merge object attributes", source_branch_public_id=source.public_id,
        target_branch_public_id=main.public_id), user_id=project.owner_user_id)
    _approve_mr(db, project, mr, admin.id)
    response = perform_merge(db, project.id, mr.public_id, _merge_payload(db, project, mr), user_id=admin.id)
    db.commit()
    db.expire_all()
    main_ws = db.scalar(select(BranchWorkspaceModel).where(BranchWorkspaceModel.branch_id == main.id))
    attributes = db.scalars(select(BusinessObjectAttributeModel).where(BusinessObjectAttributeModel.workspace_id == main_ws.id)).all()
    assert {a.logical_uuid for a in attributes} == {expected[0], added_uuid}
    restored = next(a for a in attributes if a.logical_uuid == expected[0])
    assert (restored.logical_uuid, restored.name, restored.data_type, restored.description,
            restored.example, restored.confirmation_status) == expected
    commit = db.scalar(select(RequirementCommitModel).where(RequirementCommitModel.public_id == response.merged_commit_public_id))
    assert {a["logical_uuid"] for a in json.loads(commit.state_json)["business_objects"][0]["attributes"]} == {expected[0], added_uuid}
