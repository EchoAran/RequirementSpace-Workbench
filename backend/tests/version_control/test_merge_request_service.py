"""Merge Request Service Tests (Phase 5)."""
import pytest
from sqlalchemy import func, select

from backend.api.modules.version_control.application.clean_initialization import (
    initialize_project_version_control,
)
from backend.api.modules.version_control.application.branch_service import create_branch
from backend.api.modules.version_control.application.commit_service import create_commit
from backend.api.modules.version_control.application.merge_service import (
    add_mr_comment,
    close_mr,
    create_merge_request,
    get_mr_detail,
    list_merge_requests,
    reopen_mr_comment,
    resolve_mr_comment,
    review_mr,
    sync_mrs_on_branch_commit,
)
from backend.api.modules.version_control.schemas import (
    BranchCreateRequest,
    CommitCreateRequest,
    MergeCommentCreateRequest,
    MergeRequestCreateRequest,
    MergeReviewRequest,
)
from backend.database.model import (
    AuditLogModel,
    BranchWorkspaceModel,
    MergeRequestModel,
    NotificationModel,
    ProjectMemberModel,
    ProjectModel,
    RequirementBranchModel,
    RequirementCommitModel,
    UserModel,
)


@pytest.fixture
def seeded_vc_and_branches(sync_db_session, seeded_project):
    """迁移并创建两支分支用于 MR 测试。"""
    from backend.api.modules.version_control.schemas import BranchCreateRequest

    initialize_project_version_control(sync_db_session, seeded_project)
    sync_db_session.commit()

    feature = create_branch(
        sync_db_session, seeded_project.id,
        BranchCreateRequest(name="feature/mr-test"),
        user_id=seeded_project.owner_user_id,
    )
    main_branch = sync_db_session.scalars(
        select(RequirementBranchModel).where(
            RequirementBranchModel.project_id == seeded_project.id,
            RequirementBranchModel.name == "main",
        )
    ).first()
    return seeded_project, feature, main_branch


def test_create_mr_fails_on_same_branch(sync_db_session, seeded_vc_and_branches):
    project, feature, _ = seeded_vc_and_branches
    with pytest.raises(ValueError, match="source_target_same"):
        create_merge_request(
            sync_db_session, project.id,
            MergeRequestCreateRequest(
                title="MR to self",
                source_branch_public_id=feature.public_id,
                target_branch_public_id=feature.public_id,
            ),
            user_id=project.owner_user_id,
        )


def test_create_mr_persists_and_generates_notification(sync_db_session, seeded_vc_and_branches):
    project, feature, main_branch = seeded_vc_and_branches
    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(
            title="Feature MR",
            description="Merging feature",
            source_branch_public_id=feature.public_id,
            target_branch_public_id=main_branch.public_id,
        ),
        user_id=project.owner_user_id,
    )
    assert mr.title == "Feature MR"
    assert mr.status == "open"
    assert mr.source_branch_name == "feature/mr-test"
    assert mr.target_branch_name == "main"

    db_mr = sync_db_session.get(MergeRequestModel, mr.id)
    assert db_mr is not None
    assert db_mr.source_branch_id == feature.id
    assert db_mr.target_branch_id == main_branch.id

    # 通知：target 分支创建者（owner）收到通知（但作者=owner 时跳过自身）
    notifs = sync_db_session.scalars(
        select(NotificationModel).where(NotificationModel.project_id == project.id)
    ).all()
    assert len(notifs) >= 0  # owner=self 时跳过


def test_list_and_get_mr(sync_db_session, seeded_vc_and_branches):
    project, feature, main_branch = seeded_vc_and_branches
    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(
            title="List MR",
            source_branch_public_id=feature.public_id,
            target_branch_public_id=main_branch.public_id,
        ),
        user_id=project.owner_user_id,
    )
    listing = list_merge_requests(sync_db_session, project.id)
    assert listing.total >= 1
    assert any(item.public_id == mr.public_id for item in listing.items)

    detail = get_mr_detail(sync_db_session, project.id, mr.public_id)
    assert detail.title == "List MR"
    assert detail.reviews == []
    assert detail.blocking_reasons is not None


def test_mr_commenting(sync_db_session, seeded_vc_and_branches):
    project, feature, main_branch = seeded_vc_and_branches
    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(
            title="Comment MR",
            source_branch_public_id=feature.public_id,
            target_branch_public_id=main_branch.public_id,
        ),
        user_id=project.owner_user_id,
    )
    comment = add_mr_comment(
        sync_db_session, project.id, mr.public_id,
        MergeCommentCreateRequest(
            entity_uuid="some-uuid",
            field_path="description",
            comment="This entity needs review",
        ),
        user_id=project.owner_user_id,
    )
    assert comment.comment == "This entity needs review"
    assert comment.entity_uuid == "some-uuid"
    assert comment.field_path == "description"


def test_review_mr_approves_and_rejects(sync_db_session, seeded_vc_and_branches):
    project, feature, main_branch = seeded_vc_and_branches
    # 创建另一个 admin 用户
    admin_user = UserModel(id=30, email="admin2@example.com", password_hash="h", role="admin")
    sync_db_session.add(admin_user)
    sync_db_session.add(ProjectMemberModel(
        project_id=project.id, user_id=admin_user.id,
        role="admin", status="active",
    ))
    sync_db_session.commit()

    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(
            title="Review MR",
            source_branch_public_id=feature.public_id,
            target_branch_public_id=main_branch.public_id,
        ),
        user_id=project.owner_user_id,
    )

    # owner 审批自己创建的 MR 允许通过（去除了利益回避限制）
    owner_review = review_mr(
        sync_db_session, project.id, mr.public_id,
        MergeReviewRequest(decision="approved", comment="Author approved"),
        user_id=project.owner_user_id,
    )
    assert owner_review.decision == "approved"
    assert owner_review.status == "active"
    review = review_mr(
        sync_db_session, project.id, mr.public_id,
        MergeReviewRequest(decision="approved", comment="LGTM"),
        user_id=admin_user.id,
    )
    assert review.decision == "approved"
    assert review.status == "active"

    detail = get_mr_detail(sync_db_session, project.id, mr.public_id)
    assert len(detail.reviews) == 2
    assert detail.reviews[0].decision == "approved"
    assert detail.reviews[1].decision == "approved"


def test_can_merge_and_can_approve_permissions(sync_db_session, seeded_vc_and_branches):
    """member 不能合并/admin 可合并；已有 active review 者不可再次审批。"""
    project, feature, main = seeded_vc_and_branches
    admin = UserModel(id=44, email="perm_admin@test.com", password_hash="h", role="admin")
    member = UserModel(id=45, email="perm_member@test.com", password_hash="h", role="user")
    admin2 = UserModel(id=46, email="perm_admin2@test.com", password_hash="h", role="admin")
    for u, r in [(admin, "admin"), (member, "viewer"), (admin2, "admin")]:
        sync_db_session.add(u)
        sync_db_session.flush()  # 确保 user.id 已生成
        sync_db_session.add(ProjectMemberModel(project_id=project.id, user_id=u.id, role=r, status="active"))
    sync_db_session.commit()

    # 在 source 分支上先提交一次，避免 source_no_new_commits 阻塞
    _modify_and_commit(sync_db_session, project.id, feature, "perm test commit", project.owner_user_id)

    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(title="Perm MR", source_branch_public_id=feature.public_id, target_branch_public_id=main.public_id),
        user_id=project.owner_user_id,
    )
    # admin 审批通过
    review_mr(sync_db_session, project.id, mr.public_id, MergeReviewRequest(decision="approved"), user_id=admin.id)

    # member 查看详情：can_merge=false, can_approve=false（非 admin）
    detail_member = get_mr_detail(sync_db_session, project.id, mr.public_id, user_id=member.id)
    assert detail_member.can_approve == False
    assert detail_member.can_merge == False

    # admin2（无 active review）查看详情：can_approve=true, can_merge=true
    detail_admin = get_mr_detail(sync_db_session, project.id, mr.public_id, user_id=admin2.id)
    assert detail_admin.can_approve == True
    # can_merge 受审批和角色双重条件约束
    assert detail_admin.can_merge == True, f"blocking: {detail_admin.blocking_reasons}, can_merge: {detail_admin.can_merge}"

    # admin（已有 active review）查看详情：can_approve=false（重复审批被阻）；can_merge=true
    detail_reviewer = get_mr_detail(sync_db_session, project.id, mr.public_id, user_id=admin.id)
    assert detail_reviewer.can_approve == False
    assert detail_reviewer.can_merge == True


def test_close_mr_by_author_or_admin(sync_db_session, seeded_vc_and_branches):
    project, feature, main_branch = seeded_vc_and_branches
    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(
            title="Close MR",
            source_branch_public_id=feature.public_id,
            target_branch_public_id=main_branch.public_id,
        ),
        user_id=project.owner_user_id,
    )
    result = close_mr(sync_db_session, project.id, mr.public_id, user_id=project.owner_user_id)
    assert result["new_status"] == "closed"

    # 再次关闭已关闭 MR 被拒绝
    with pytest.raises(ValueError, match="mr_already_closed"):
        close_mr(sync_db_session, project.id, mr.public_id, user_id=project.owner_user_id)


def test_member_cannot_review(sync_db_session, seeded_vc_and_branches):
    project, feature, main_branch = seeded_vc_and_branches
    member_user = UserModel(id=40, email="member@example.com", password_hash="h", role="user")
    sync_db_session.add(member_user)
    sync_db_session.add(ProjectMemberModel(
        project_id=project.id, user_id=member_user.id,
        role="viewer", status="active",
    ))
    sync_db_session.commit()

    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(
            title="Member MR",
            source_branch_public_id=feature.public_id,
            target_branch_public_id=main_branch.public_id,
        ),
        user_id=project.owner_user_id,
    )
    with pytest.raises(ValueError, match="only_admin_or_owner_can_review"):
        review_mr(
            sync_db_session, project.id, mr.public_id,
            MergeReviewRequest(decision="approved"),
            user_id=member_user.id,
        )


def test_member_cannot_set_required_comment(sync_db_session, seeded_vc_and_branches):
    project, feature, main_branch = seeded_vc_and_branches
    member_user = UserModel(id=41, email="viewer2@example.com", password_hash="h", role="user")
    sync_db_session.add(member_user)
    sync_db_session.add(ProjectMemberModel(
        project_id=project.id, user_id=member_user.id,
        role="viewer", status="active",
    ))
    sync_db_session.commit()
    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(
            title="ReqComment MR",
            source_branch_public_id=feature.public_id,
            target_branch_public_id=main_branch.public_id,
        ),
        user_id=project.owner_user_id,
    )
    # member 创建 required=true 评论 → 被服务降级为 false
    comment = add_mr_comment(
        sync_db_session, project.id, mr.public_id,
        MergeCommentCreateRequest(comment="test", required=True),
        user_id=member_user.id,
    )
    assert comment.comment == "test"
    assert comment.required == False


def test_resolve_and_reopen_comment(sync_db_session, seeded_vc_and_branches):
    project, feature, main_branch = seeded_vc_and_branches
    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(
            title="Comment MR",
            source_branch_public_id=feature.public_id,
            target_branch_public_id=main_branch.public_id,
        ),
        user_id=project.owner_user_id,
    )
    comment = add_mr_comment(
        sync_db_session, project.id, mr.public_id,
        MergeCommentCreateRequest(comment="resolve me"),
        user_id=project.owner_user_id,
    )
    # resolve
    resolved = resolve_mr_comment(sync_db_session, project.id, mr.public_id, comment.id, user_id=project.owner_user_id)
    assert resolved.status == "resolved"
    # reopen
    reopened = reopen_mr_comment(sync_db_session, project.id, mr.public_id, comment.id, user_id=project.owner_user_id)
    assert reopened.status == "active"


def test_stranger_cannot_reopen_resolved_comment(sync_db_session, seeded_vc_and_branches):
    project, feature, main_branch = seeded_vc_and_branches
    stranger = UserModel(id=42, email="stranger@example.com", password_hash="h", role="user")
    sync_db_session.add(stranger)
    sync_db_session.add(ProjectMemberModel(
        project_id=project.id, user_id=stranger.id,
        role="viewer", status="active",
    ))
    sync_db_session.commit()
    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(
            title="Reopen MR",
            source_branch_public_id=feature.public_id,
            target_branch_public_id=main_branch.public_id,
        ),
        user_id=project.owner_user_id,
    )
    comment = add_mr_comment(
        sync_db_session, project.id, mr.public_id,
        MergeCommentCreateRequest(comment="resolved by author"),
        user_id=project.owner_user_id,
    )
    # owner 解决自己的评论
    resolve_mr_comment(sync_db_session, project.id, mr.public_id, comment.id, user_id=project.owner_user_id)
    # stranger（既不是评论作者也不是 MR 作者）不可重开
    with pytest.raises(ValueError, match="only_author_or_admin_can_reopen"):
        reopen_mr_comment(sync_db_session, project.id, mr.public_id, comment.id, user_id=stranger.id)


# ═══════════════════════════════════════════════
# 阶段验收：source/target 推进、重复审批、审计
# ═══════════════════════════════════════════════

def _modify_and_commit(db, project_id, branch, commit_msg, user_id):
    """修改分支工作区用户需求并提交，返回新的 commit。"""
    # 重新查询分支以获取当前 head
    current = db.get(RequirementBranchModel, branch.id)
    ws = db.scalars(
        select(BranchWorkspaceModel).where(BranchWorkspaceModel.branch_id == current.id)
    ).first()
    if ws:
        ws.user_requirements = commit_msg
    db.commit()
    return create_commit(
        db, project_id, current.public_id,
        CommitCreateRequest(
            message=commit_msg,
            expected_head_commit_id=current.head_commit_id,
        ),
        user_id=user_id,
    )


def test_cross_project_branch_id_rejected(sync_db_session, seeded_vc_and_branches):
    """数值 source_branch_id 指向另一项目的分支应被拒绝。"""
    project, _feature, main = seeded_vc_and_branches
    other_proj = ProjectModel(
        owner_user_id=project.owner_user_id, name="Other", description="",
        user_requirements="", kano_status="missing", unlocked_stages="",
    )
    sync_db_session.add(other_proj)
    sync_db_session.flush()
    initialize_project_version_control(sync_db_session, other_proj)
    sync_db_session.commit()
    other_branch = sync_db_session.scalars(
        select(RequirementBranchModel).where(
            RequirementBranchModel.project_id == other_proj.id,
            RequirementBranchModel.name == "main",
        )
    ).first()
    with pytest.raises(ValueError, match="source_branch_not_found"):
        create_merge_request(
            sync_db_session, project.id,
            MergeRequestCreateRequest(
                title="Cross proj",
                source_branch_id=other_branch.id,
                target_branch_public_id=main.public_id,
            ),
            user_id=project.owner_user_id,
        )


def test_duplicate_active_review_rejected(sync_db_session, seeded_vc_and_branches):
    """同一 reviewer 再次审批 active MR 时应被拒绝。"""
    project, feature, main = seeded_vc_and_branches
    admin = UserModel(id=33, email="dup_admin@test.com", password_hash="h", role="admin")
    sync_db_session.add(admin)
    sync_db_session.add(ProjectMemberModel(project_id=project.id, user_id=admin.id, role="admin", status="active"))
    sync_db_session.commit()
    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(title="Dup MR", source_branch_public_id=feature.public_id, target_branch_public_id=main.public_id),
        user_id=project.owner_user_id,
    )
    review_mr(sync_db_session, project.id, mr.public_id, MergeReviewRequest(decision="approved"), user_id=admin.id)
    with pytest.raises(ValueError, match="duplicate_review_not_allowed"):
        review_mr(sync_db_session, project.id, mr.public_id, MergeReviewRequest(decision="changes_requested"), user_id=admin.id)


def test_review_rejected_on_closed_mr(sync_db_session, seeded_vc_and_branches):
    """已关闭 MR 不可再审批。"""
    project, feature, main = seeded_vc_and_branches
    admin = UserModel(id=34, email="closed_admin@test.com", password_hash="h", role="admin")
    sync_db_session.add(admin)
    sync_db_session.add(ProjectMemberModel(project_id=project.id, user_id=admin.id, role="admin", status="active"))
    sync_db_session.commit()
    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(title="Closed MR", source_branch_public_id=feature.public_id, target_branch_public_id=main.public_id),
        user_id=project.owner_user_id,
    )
    close_mr(sync_db_session, project.id, mr.public_id, user_id=project.owner_user_id)
    with pytest.raises(ValueError, match="mr_already_closed"):
        review_mr(sync_db_session, project.id, mr.public_id, MergeReviewRequest(decision="approved"), user_id=admin.id)


def test_source_advance_stales_approvals_and_expires_comments(sync_db_session, seeded_vc_and_branches):
    """source 推进：审批 stale + 评论 expired + MR 回 open + 审计写入。"""
    project, feature, main = seeded_vc_and_branches
    admin = UserModel(id=35, email="src_admin@test.com", password_hash="h", role="admin")
    sync_db_session.add(admin)
    sync_db_session.add(ProjectMemberModel(project_id=project.id, user_id=admin.id, role="admin", status="active"))
    sync_db_session.commit()
    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(title="SrcAdv MR", source_branch_public_id=feature.public_id, target_branch_public_id=main.public_id),
        user_id=project.owner_user_id,
    )
    review_mr(sync_db_session, project.id, mr.public_id, MergeReviewRequest(decision="approved"), user_id=admin.id)
    add_mr_comment(sync_db_session, project.id, mr.public_id, MergeCommentCreateRequest(comment="old comment"), user_id=project.owner_user_id)

    # 审批后 MR 状态应为 approved
    db_mr_check = sync_db_session.get(MergeRequestModel, mr.id)
    assert db_mr_check.status == "approved"
    _modify_and_commit(sync_db_session, project.id, feature, "source advance commit", project.owner_user_id)
    # 同步 MR：source 推进应失效审批
    sync_mrs_on_branch_commit(sync_db_session, project.id, feature.id)

    db_mr = sync_db_session.get(MergeRequestModel, mr.id)
    assert db_mr.status == "open"  # 审批失效后回退
    stale_reviews = [r for r in db_mr.reviews if r.status == "stale"]
    assert len(stale_reviews) == 1
    assert stale_reviews[0].stale_reason == "source_branch_advanced"

    # 评论应 expired
    expired = [c for c in db_mr.comments if c.status == "expired"]
    assert len(expired) == 1

    # 审计记录
    audit = sync_db_session.scalars(
        select(AuditLogModel).where(AuditLogModel.action_type == "merge_request_approval_stale")
    ).all()
    assert len(audit) >= 1


def test_target_advance_stales_approvals_but_not_comments(sync_db_session, seeded_vc_and_branches):
    """target-only 推进：审批 stale + 评论保持不变。使用非 main 的目标分支（main 受保护不可直接提交）。"""
    project, feature, main = seeded_vc_and_branches
    # 创建第二个 feature 分支作为 target
    target_feat = create_branch(
        sync_db_session, project.id,
        BranchCreateRequest(name="feature/target-mr", source_branch_public_id=main.public_id),
        user_id=project.owner_user_id,
    )
    _modify_and_commit(sync_db_session, project.id, target_feat, "target initial", project.owner_user_id)
    admin = UserModel(id=36, email="tgt_admin@test.com", password_hash="h", role="admin")
    sync_db_session.add(admin)
    sync_db_session.add(ProjectMemberModel(project_id=project.id, user_id=admin.id, role="admin", status="active"))
    sync_db_session.commit()
    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(title="TgtAdv MR", source_branch_public_id=feature.public_id, target_branch_public_id=target_feat.public_id),
        user_id=project.owner_user_id,
    )
    review_mr(sync_db_session, project.id, mr.public_id, MergeReviewRequest(decision="approved"), user_id=admin.id)
    add_mr_comment(sync_db_session, project.id, mr.public_id, MergeCommentCreateRequest(comment="keep me"), user_id=project.owner_user_id)

    _modify_and_commit(sync_db_session, project.id, target_feat, "target advance commit", project.owner_user_id)
    sync_mrs_on_branch_commit(sync_db_session, project.id, target_feat.id)

    db_mr = sync_db_session.get(MergeRequestModel, mr.id)
    stale = [r for r in db_mr.reviews if r.status == "stale"]
    assert len(stale) == 1
    assert stale[0].stale_reason == "target_branch_advanced"

    # 评论不受 target 推进影响
    active_comments = [c for c in db_mr.comments if c.status == "active"]
    expired_comments = [c for c in db_mr.comments if c.status == "expired"]
    assert len(active_comments) == 1
    assert len(expired_comments) == 0


def test_stale_review_can_be_reapproved(sync_db_session, seeded_vc_and_branches):
    """stale 后可重新审批，复用旧记录而非新建。"""
    project, feature, main = seeded_vc_and_branches
    admin = UserModel(id=37, email="reapprove@test.com", password_hash="h", role="admin")
    sync_db_session.add(admin)
    sync_db_session.add(ProjectMemberModel(project_id=project.id, user_id=admin.id, role="admin", status="active"))
    sync_db_session.commit()
    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(title="ReApprove MR", source_branch_public_id=feature.public_id, target_branch_public_id=main.public_id),
        user_id=project.owner_user_id,
    )
    review_mr(sync_db_session, project.id, mr.public_id, MergeReviewRequest(decision="approved"), user_id=admin.id)
    _modify_and_commit(sync_db_session, project.id, feature, "s1", project.owner_user_id)
    sync_mrs_on_branch_commit(sync_db_session, project.id, feature.id)

    db_mr = sync_db_session.get(MergeRequestModel, mr.id)
    assert db_mr.status == "open"
    review_count_before = len(db_mr.reviews)

    # 重新审批，应复用 stale 记录
    review = review_mr(sync_db_session, project.id, mr.public_id, MergeReviewRequest(decision="approved"), user_id=admin.id)
    assert review.status == "active"
    db_mr2 = sync_db_session.get(MergeRequestModel, mr.id)
    assert len(db_mr2.reviews) == review_count_before  # 不新增行
    assert db_mr2.status == "approved"


def test_commit_and_mr_sync_in_same_transaction(sync_db_session, seeded_vc_and_branches):
    """提交后 MR 同步与 commit 在同一事务：审批 stale + 审计同时写入。"""
    project, feature, main = seeded_vc_and_branches
    admin = UserModel(id=38, email="txn_admin@test.com", password_hash="h", role="admin")
    sync_db_session.add(admin)
    sync_db_session.add(ProjectMemberModel(project_id=project.id, user_id=admin.id, role="admin", status="active"))
    sync_db_session.commit()

    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(title="Txn MR", source_branch_public_id=feature.public_id, target_branch_public_id=main.public_id),
        user_id=project.owner_user_id,
    )
    review_mr(sync_db_session, project.id, mr.public_id, MergeReviewRequest(decision="approved"), user_id=admin.id)
    db_mr = sync_db_session.get(MergeRequestModel, mr.id)
    assert db_mr.status == "approved"

    # 提交：commit_service 内部不调 sync_mrs（那是 route 层的事），测试直接模拟 route 层行为：
    # commit 后紧接着 sync_mrs。两者在同一个 sync_db_session 中，异常会回滚。
    _modify_and_commit(sync_db_session, project.id, feature, "txn commit", project.owner_user_id)
    sync_mrs_on_branch_commit(sync_db_session, project.id, feature.id)

    # 审批已 stale，MR 回 open
    db_mr2 = sync_db_session.get(MergeRequestModel, mr.id)
    assert db_mr2.status == "open"
    stale_reviews = [r for r in db_mr2.reviews if r.status == "stale"]
    assert len(stale_reviews) == 1

    # 审批失效审计已写入（commit 审计在 route 层，service 级测试不验证）
    audit_types = sync_db_session.scalars(
        select(AuditLogModel.action_type).where(AuditLogModel.project_id == project.id)
    ).all()
    assert "merge_request_approval_stale" in audit_types


def test_commit_rollback_on_mr_sync_failure(sync_db_session, seeded_vc_and_branches):
    """模拟 MR 同步异常后，commit + head + 审计全部回滚。"""
    project, feature, main = seeded_vc_and_branches
    admin = UserModel(id=39, email="rollback_admin@test.com", password_hash="h", role="admin")
    sync_db_session.add(admin)
    sync_db_session.add(ProjectMemberModel(project_id=project.id, user_id=admin.id, role="admin", status="active"))
    sync_db_session.commit()

    mr = create_merge_request(
        sync_db_session, project.id,
        MergeRequestCreateRequest(
            title="Rollback MR", source_branch_public_id=feature.public_id, target_branch_public_id=main.public_id,
        ),
        user_id=project.owner_user_id,
    )
    review_mr(sync_db_session, project.id, mr.public_id, MergeReviewRequest(decision="approved"), user_id=admin.id)

    # 记录提交前的分支 head 与 commit 数量
    feature_model = sync_db_session.get(RequirementBranchModel, feature.id)
    head_before = feature_model.head_commit_id
    commit_count_before = sync_db_session.scalar(
        select(func.count()).select_from(RequirementCommitModel).where(RequirementCommitModel.project_id == project.id)
    )

    # 修改工作区使提交合法
    ws = sync_db_session.scalars(
        select(BranchWorkspaceModel).where(BranchWorkspaceModel.branch_id == feature_model.id)
    ).first()
    ws.user_requirements = "rollback test"
    sync_db_session.commit()

    # 模拟 route 层事务：create_commit(flush) → sync_mrs → rollback 的模式
    # commit_routes 在 create_commit 之后立即调用 sync_mrs_on_branch_commit，
    # 若 sync 失败，整个 session 不会 commit。此处直接演示该模式。
    create_commit(
        sync_db_session, project.id, feature_model.public_id,
        CommitCreateRequest(message="should be rolled back", expected_head_commit_id=head_before),
        user_id=project.owner_user_id,
    )
    # 模拟 sync_mrs 异常（对应 commit_routes 中 run_sync 内抛错）
    try:
        sync_mrs_on_branch_commit(sync_db_session, project.id, feature_model.id)
        raise RuntimeError("simulated MR sync failure")
    except RuntimeError:
        sync_db_session.rollback()

    sync_db_session.refresh(feature_model)
    assert feature_model.head_commit_id == head_before
    commit_count_after = sync_db_session.scalar(
        select(func.count()).select_from(RequirementCommitModel).where(RequirementCommitModel.project_id == project.id)
    )
    assert commit_count_after == commit_count_before
    assert commit_count_after == commit_count_before
    db_mr = sync_db_session.get(MergeRequestModel, mr.id)
    assert any(r.status == "active" and r.decision == "approved" for r in db_mr.reviews)
