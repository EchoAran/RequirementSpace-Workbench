"""
Merge Request Application Service.
MR 的完整生命周期：创建、列表、详情、评论、审批、审批失效、关闭与合并前置校验。
"""
import itertools
import json
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.database.model import (
    UserModel,
    ProjectModel,
    ProjectMemberModel,
    RequirementBranchModel,
    RequirementCommitModel,
    RequirementCommitParentModel,
    MergeRequestModel,
    MergeReviewModel,
    MergeCommentModel,
    NotificationModel,
)
from backend.api.modules.version_control.application.commit_service import (
    resolve_commit_in_project,
    _load_project_commit_graph,
    _reachable_commit_ids,
)
from backend.api.modules.version_control.application.branch_service import (
    resolve_branch_context,
)
from backend.api.modules.version_control.domain.semantic_diff import (
    compute_semantic_diff,
)
from backend.api.modules.version_control.schemas import (
    MRDiffSummary,
    DiffTypeSummary,
    MergeRequestCreateRequest,
    MergeReviewRequest,
    MergeCommentCreateRequest,
    MergeRequestSummaryResponse,
    MergeRequestDetailResponse,
    MergeReviewResponse,
    MergeCommentResponse,
    MergeRequestListResponse,
)

NOTIFY_MR_CREATED = "merge_request_created"
NOTIFY_MR_REVIEW = "merge_request_reviewed"
NOTIFY_MR_CLOSED = "merge_request_closed"
NOTIFY_MR_COMMENT = "merge_request_commented"
NOTIFY_MR_APPROVAL_STALE = "merge_request_approval_stale"


def _user_role_in_project(db: Session, project_id: int, user_id: int) -> Optional[str]:
    project = db.get(ProjectModel, project_id)
    if project and project.owner_user_id == user_id:
        return "owner"
    member = db.scalars(
        select(ProjectMemberModel).where(
            ProjectMemberModel.project_id == project_id,
            ProjectMemberModel.user_id == user_id,
        )
    ).first()
    return member.role if member else None


def _is_admin_or_owner(role: Optional[str]) -> bool:
    return role in ("owner", "admin")


def _resolve_branch_ref(db: Session, project_id: int, ref: RequirementBranchModel | None) -> str:
    return ref.name if ref else "(deleted)"


def _build_notification(
    project_id: int,
    recipient_user_id: int,
    event_type: str,
    title: str,
    body: str,
) -> NotificationModel:
    return NotificationModel(
        project_id=project_id,
        recipient_user_id=recipient_user_id,
        event_type=event_type,
        title=title,
        body=body,
    )


def _find_merge_base(
    db: Session,
    project_id: int,
    source_head_id: int,
    target_head_id: int,
) -> Optional[int]:
    """找到 source 和 target 提交图的最近共同祖先（merge base）。"""
    _, parents_by_commit = _load_project_commit_graph(db, project_id)
    source_ancestors = _reachable_commit_ids(source_head_id, parents_by_commit)
    target_ancestors = _reachable_commit_ids(target_head_id, parents_by_commit)
    common = sorted(
        source_ancestors & target_ancestors,
        key=lambda cid: _ancestor_distance(cid, source_head_id, parents_by_commit),
    )
    return common[0] if common else None


def _ancestor_distance(
    commit_id: int,
    from_id: int,
    parents_by_commit: Dict[int, List[RequirementCommitParentModel]],
    max_depth: int = 200,
) -> int:
    queue = [(from_id, 0)]
    seen: Set[int] = set()
    while queue:
        cid, d = queue.pop(0)
        if cid == commit_id:
            return d
        if cid in seen or d > max_depth:
            continue
        seen.add(cid)
        queue.extend(
            (row.parent_commit_id, d + 1)
            for row in parents_by_commit.get(cid, [])
        )
    return 99999


def _compute_diff_summary(
    db: Session,
    project_id: int,
    source_head_id: int,
    merge_base_id: int,
) -> MRDiffSummary:
    """计算 merge_base → source_head 的语义差异摘要。"""
    base_commit = db.get(RequirementCommitModel, merge_base_id)
    source_commit = db.get(RequirementCommitModel, source_head_id)
    if not base_commit or not source_commit:
        return MRDiffSummary()
    base_state = json.loads(base_commit.state_json) if base_commit.state_json else {}
    target_state = json.loads(source_commit.state_json) if source_commit.state_json else {}
    result = compute_semantic_diff(base_state, target_state)
    return MRDiffSummary(
        by_type={
            entity_type: DiffTypeSummary(
                added=values.get("added", 0),
                removed=values.get("removed", 0),
                modified=values.get("modified", 0),
            )
            for entity_type, values in result["summary"]["by_type"].items()
        },
        total_added=result["summary"]["total_added"],
        total_removed=result["summary"]["total_removed"],
        total_modified=result["summary"]["total_modified"],
    )


def _author_email(db: Session, user_id: Optional[int]) -> Optional[str]:
    if user_id:
        user = db.get(UserModel, user_id)
        return user.email if user else None
    return None


def _review_response(review: MergeReviewModel, db: Session) -> MergeReviewResponse:
    return MergeReviewResponse(
        id=review.id,
        reviewer_user_id=review.reviewer_user_id,
        reviewer_email=_author_email(db, review.reviewer_user_id),
        decision=review.decision,
        comment=review.comment,
        status=review.status,
        stale_reason=review.stale_reason,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


def _comment_response(comment: MergeCommentModel, db: Session) -> MergeCommentResponse:
    return MergeCommentResponse(
        id=comment.id,
        author_user_id=comment.author_user_id,
        author_email=_author_email(db, comment.author_user_id),
        entity_uuid=comment.entity_uuid,
        field_path=comment.field_path,
        relation_key=comment.relation_key,
        comment=comment.comment,
        required=comment.required,
        status=comment.status,
        effective_source_head_id=comment.effective_source_head_id,
        expired_by_source_head_id=comment.expired_by_source_head_id,
        created_at=comment.created_at,
    )


def _check_blocking_reasons(
    db: Session,
    mr: MergeRequestModel,
    user_role: Optional[str],
    user_id: int | None = None,
) -> Tuple[bool, bool, List[str]]:
    """检查合并前阻塞原因。返回 (can_approve, can_merge, reasons)。"""
    reasons: List[str] = []
    can_approve = (
        _is_admin_or_owner(user_role)
        and (user_id is None or mr.author_user_id != user_id)
        # 已有 active review 的审批人不可重复审批（与写接口的 duplicate_review 一致）
        and not any(r.status == "active" and r.reviewer_user_id == user_id for r in mr.reviews)
    )
    # 已合并/关闭 → 不可再审批或合并
    if mr.status in ("merged", "closed"):
        reasons.append("mr_already_closed")
        return False, False, reasons

    source_branch = db.get(RequirementBranchModel, mr.source_branch_id)
    target_branch = db.get(RequirementBranchModel, mr.target_branch_id)

    # 来源无新提交（与 merge_base 相同）
    if mr.source_head_commit_id and mr.merge_base_commit_id and mr.source_head_commit_id == mr.merge_base_commit_id:
        reasons.append("source_no_new_commits")

    # 来源分支与目标分支不能相同
    if mr.source_branch_id == mr.target_branch_id:
        reasons.append("source_target_same")
        return False, False, reasons

    # 有效审批：至少一个非作者 active approved review
    active_approvals = [
        r for r in mr.reviews
        if r.status == "active" and r.decision == "approved" and r.reviewer_user_id != mr.author_user_id
    ]
    if not active_approvals:
        reasons.append("missing_approval")

    # 存在 active 的 changes_requested review → 阻塞合并（请求修改仍有效时不能合入）
    active_change_requests = [
        r for r in mr.reviews
        if r.status == "active" and r.decision == "changes_requested" and r.reviewer_user_id != mr.author_user_id
    ]
    if active_change_requests:
        reasons.append("changes_requested_active")
    # MR 状态为 changes_requested（可能存在历史有效审批但整体仍处于请求修改态）
    if mr.status == "changes_requested":
        reasons.append("mr_status_changes_requested")

    # 目标分支 head 是否变化（同步已保存当前值，这里比较分支当前 head 与 MR 记录值判断已过期）
    if target_branch and mr.target_head_commit_id and target_branch.head_commit_id != mr.target_head_commit_id:
        reasons.append("target_branch_advanced")

    # 来源 head 是否变化（同理，_sync_mr_heads 之后这些值才一致，判断时直接比较分支实际值）
    if source_branch and mr.source_head_commit_id and source_branch.head_commit_id != mr.source_head_commit_id:
        reasons.append("source_branch_advanced")

    # 未解决的必需评论才阻塞合并
    blocking_comments = [c for c in mr.comments if c.required and c.status == "active"]
    if blocking_comments:
        reasons.append("unresolved_required_comments")

    # 合并前必须同时满足：①角色为 admin/owner；②无阻塞原因；③有有效审批
    can_merge_ok = len(reasons) == 0 and len(active_approvals) > 0
    can_merge = can_merge_ok and _is_admin_or_owner(user_role)

    return can_approve, can_merge, reasons


def _stale_mr_reviews(db: Session, mr: MergeRequestModel, reason: str) -> None:
    """分支新提交后，标记有效审批为 stale，并重置 MR 状态。"""
    stale_count = 0
    for review in mr.reviews:
        if review.status != "active":
            continue
        review.status = "stale"
        review.stale_reason = reason
        review.stale_source_head_id = mr.source_head_commit_id
        review.stale_target_head_id = mr.target_head_commit_id
        stale_count += 1
    # 审批失效后 MR 恢复到 open 状态（之前的 approved/changes_requested 不再有效）
    if stale_count and mr.status in ("approved", "changes_requested", "mergeable"):
        mr.status = "open"
    if stale_count:
        # 审计记录
        from backend.database.model import AuditLogModel
        for review in mr.reviews:
            if review.status == "stale" and review.stale_reason == reason:
                db.add(
                    AuditLogModel(
                        project_id=mr.project_id,
                        action_type="merge_request_approval_stale",
                        summary=f"MR 审批失效 ({reason})",
                        target_type="merge_review",
                        target_id=str(review.id),
                        payload={"mr_id": mr.public_id, "reason": reason},
                    )
                )
        # 通知
        author_id = mr.author_user_id
        if author_id:
            db.add(
                _build_notification(
                    mr.project_id,
                    author_id,
                    NOTIFY_MR_APPROVAL_STALE,
                    f"Merge request approvals invalidated ({reason})",
                    f"{stale_count} approval(s) on MR {mr.title} were invalidated because the {reason}",
                )
            )


def _expire_mr_comments(db: Session, mr: MergeRequestModel, new_source_head_id: int | None) -> None:
    """来源分支新提交后，所有锚定在旧提交上的评论标记为 expired。"""
    if not new_source_head_id:
        return
    for comment in mr.comments:
        if comment.status != "active":
            continue
        comment.status = "expired"
        comment.expired_by_source_head_id = new_source_head_id


def compute_mr_preview(
    db: Session,
    project_id: int,
    source_branch_public_id: str,
    target_branch_public_id: str,
) -> Dict[str, Any]:
    """预计算 MR 变更摘要（merge_base → source_head），与创建 MR 后的一致。"""
    source = db.scalars(
        select(RequirementBranchModel).where(
            RequirementBranchModel.project_id == project_id,
            RequirementBranchModel.public_id == source_branch_public_id,
        )
    ).first()
    target = db.scalars(
        select(RequirementBranchModel).where(
            RequirementBranchModel.project_id == project_id,
            RequirementBranchModel.public_id == target_branch_public_id,
        )
    ).first()
    if not source or not source.head_commit_id:
        raise ValueError("source_branch_not_found")
    if not target or not target.head_commit_id:
        raise ValueError("target_branch_not_found")

    base_id = _find_merge_base(db, project_id, source.head_commit_id, target.head_commit_id)
    base = db.get(RequirementCommitModel, base_id) if base_id else None
    diff_summary = _compute_diff_summary(db, project_id, source.head_commit_id, base_id) if base_id else MRDiffSummary()

    return {
        "merge_base_commit_id": base_id,
        "merge_base_public_id": base.public_id if base else None,
        "source_head_commit_id": source.head_commit_id,
        "source_head_public_id": source.head_commit.public_id if source.head_commit else None,
        "target_head_commit_id": target.head_commit_id,
        "target_head_public_id": target.head_commit.public_id if target.head_commit else None,
        "diff_summary": diff_summary,
    }


def sync_mrs_on_branch_commit(db: Session, project_id: int, branch_id: int) -> None:
    """提交创建后，刷新涉及该分支的打开 MR（使 source/target 变更生效）。

    由 commit_routes 在成功提交后调用，使失效/阻塞及时反映到列表和详情。
    """
    open_mrs = db.scalars(
        select(MergeRequestModel)
        .options(
            selectinload(MergeRequestModel.reviews),
            selectinload(MergeRequestModel.comments),
        )
        .where(
            MergeRequestModel.project_id == project_id,
            MergeRequestModel.status.in_(["open", "approved", "changes_requested", "mergeable"]),
            (MergeRequestModel.source_branch_id == branch_id)
            | (MergeRequestModel.target_branch_id == branch_id),
        )
    ).all()
    for mr in open_mrs:
        _sync_mr_heads(db, mr)


def _sync_mr_heads(db: Session, mr: MergeRequestModel) -> None:
    """同步 MR 的 source/target head；先保存旧 head，再更新，最后比较变化并处理失效。"""
    old_source = mr.source_head_commit_id
    old_target = mr.target_head_commit_id
    source_branch = db.get(RequirementBranchModel, mr.source_branch_id)
    target_branch = db.get(RequirementBranchModel, mr.target_branch_id)
    new_source = source_branch.head_commit_id if source_branch else None
    new_target = target_branch.head_commit_id if target_branch else None

    mr.source_head_commit_id = new_source
    mr.target_head_commit_id = new_target

    if new_source and new_target:
        base = _find_merge_base(db, mr.project_id, new_source, new_target)
        if base is not None:
            mr.merge_base_commit_id = base

    # 审批：任意一方推进都使审批失效（阶段文档明确要求 target 推进也失效审批）。
    # 评论：仅在 source 推进时标记过期（评论锚定 source 内容，target 推进不影响其有效性）。
    source_advanced = old_source is not None and old_source != new_source
    target_advanced = old_target is not None and old_target != new_target
    if source_advanced or target_advanced:
        reason = "source_branch_advanced" if source_advanced else "target_branch_advanced"
        _stale_mr_reviews(db, mr, reason)
    if source_advanced:
        _expire_mr_comments(db, mr, new_source)


def _summarize_fields(db: Session, mr: MergeRequestModel, user_role: Optional[str]) -> Dict[str, Any]:
    """构建常用 MR 摘要字段。"""
    source_branch = db.get(RequirementBranchModel, mr.source_branch_id)
    target_branch = db.get(RequirementBranchModel, mr.target_branch_id)

    diff_summary = None
    if mr.source_head_commit_id and mr.merge_base_commit_id:
        diff_summary = _compute_diff_summary(
            db, mr.project_id, mr.source_head_commit_id, mr.merge_base_commit_id
        )

    active_reviews = sum(1 for r in mr.reviews if r.status == "active")
    total_comments = sum(1 for c in mr.comments if c.status == "active")

    source_head = db.get(RequirementCommitModel, mr.source_head_commit_id) if mr.source_head_commit_id else None
    target_head = db.get(RequirementCommitModel, mr.target_head_commit_id) if mr.target_head_commit_id else None

    return {
        "id": mr.id,
        "public_id": mr.public_id,
        "project_id": mr.project_id,
        "title": mr.title,
        "description": mr.description,
        "source_branch_name": source_branch.name if source_branch else "(deleted)",
        "target_branch_name": target_branch.name if target_branch else "(deleted)",
        "source_branch_public_id": source_branch.public_id if source_branch else None,
        "target_branch_public_id": target_branch.public_id if target_branch else None,
        "status": mr.status,
        "author_user_id": mr.author_user_id,
        "author_email": _author_email(db, mr.author_user_id),
        "diff_summary": diff_summary,
        "active_review_count": active_reviews,
        "total_comments": total_comments,
        "source_head_short": source_head.public_id[:8] if source_head else None,
        "target_head_short": target_head.public_id[:8] if target_head else None,
        "created_at": mr.created_at,
        "updated_at": mr.updated_at,
    }


def create_merge_request(
    db: Session,
    project_id: int,
    req: MergeRequestCreateRequest,
    user_id: int,
) -> MergeRequestDetailResponse:
    """创建 MR：校验分支、计算变更摘要并记录。"""
    user_role = _user_role_in_project(db, project_id, user_id)

    # 解析来源分支（数值 ID 路径必须校验 project_id，防止跨项目引用）
    source: Optional[RequirementBranchModel] = None
    if req.source_branch_id:
        source = db.get(RequirementBranchModel, req.source_branch_id)
        if source and source.project_id != project_id:
            source = None
    elif req.source_branch_public_id:
        source = db.scalars(
            select(RequirementBranchModel).where(
                RequirementBranchModel.project_id == project_id,
                RequirementBranchModel.public_id == req.source_branch_public_id,
            )
        ).first()
    elif req.source_branch_name:
        source = db.scalars(
            select(RequirementBranchModel).where(
                RequirementBranchModel.project_id == project_id,
                RequirementBranchModel.name == req.source_branch_name,
            )
        ).first()
    if not source:
        raise ValueError("source_branch_not_found")
    if not source.head_commit_id:
        raise ValueError("source_branch_empty")

    # 解析目标分支（同源分支，需校验 project_id）
    target: Optional[RequirementBranchModel] = None
    if req.target_branch_id:
        target = db.get(RequirementBranchModel, req.target_branch_id)
        if target and target.project_id != project_id:
            target = None
    elif req.target_branch_public_id:
        target = db.scalars(
            select(RequirementBranchModel).where(
                RequirementBranchModel.project_id == project_id,
                RequirementBranchModel.public_id == req.target_branch_public_id,
            )
        ).first()
    elif req.target_branch_name:
        target = db.scalars(
            select(RequirementBranchModel).where(
                RequirementBranchModel.project_id == project_id,
                RequirementBranchModel.name == req.target_branch_name,
            )
        ).first()
    if not target:
        raise ValueError("target_branch_not_found")

    if source.id == target.id:
        raise ValueError("source_target_same")

    # 检查重复
    existing = db.scalars(
        select(MergeRequestModel).where(
            MergeRequestModel.project_id == project_id,
            MergeRequestModel.source_branch_id == source.id,
            MergeRequestModel.target_branch_id == target.id,
            MergeRequestModel.status.in_(["open", "approved", "changes_requested", "mergeable"]),
        )
    ).first()
    if existing:
        raise ValueError("duplicate_open_mr")

    mr = MergeRequestModel(
        project_id=project_id,
        source_branch_id=source.id,
        target_branch_id=target.id,
        title=req.title,
        description=req.description or "",
        author_user_id=user_id,
        status="open",
    )
    db.add(mr)
    db.flush()
    _sync_mr_heads(db, mr)
    db.flush()

    # 通知目标分支 owner / admins（通知审批需求）
    target_owner_id = target.created_by_user_id
    if target_owner_id and target_owner_id != user_id:
        db.add(
            _build_notification(
                project_id, target_owner_id,
                NOTIFY_MR_CREATED,
                f"New merge request: {mr.title}",
                f"{source.name} → {target.name}",
            )
        )

    return get_mr_detail(db, project_id, mr.public_id)


def list_merge_requests(
    db: Session,
    project_id: int,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> MergeRequestListResponse:
    stmt = select(MergeRequestModel).where(MergeRequestModel.project_id == project_id)
    if status:
        stmt = stmt.where(MergeRequestModel.status == status)
    stmt = stmt.order_by(MergeRequestModel.created_at.desc()).offset(offset).limit(limit)

    mrs = db.scalars(stmt).all()
    from sqlalchemy import func
    total_stmt = select(func.count()).select_from(MergeRequestModel).where(MergeRequestModel.project_id == project_id)
    if status:
        total_stmt = total_stmt.where(MergeRequestModel.status == status)
    total = db.scalar(total_stmt) or 0

    items = [
        MergeRequestSummaryResponse(
            **_summarize_fields(db, mr, None)
        )
        for mr in mrs
    ]
    return MergeRequestListResponse(items=items, total=total, limit=limit, offset=offset)


def get_mr_detail(
    db: Session,
    project_id: int,
    mr_ref: str,
    user_id: int | None = None,
) -> MergeRequestDetailResponse:
    mr = _load_mr(db, project_id, mr_ref)
    # GET 不得产生业务写入：提交路由已负责同步 MR head，详情仅读取已同步状态。

    fields = _summarize_fields(db, mr, None)

    source_head = db.get(RequirementCommitModel, mr.source_head_commit_id) if mr.source_head_commit_id else None
    target_head = db.get(RequirementCommitModel, mr.target_head_commit_id) if mr.target_head_commit_id else None
    merge_base = db.get(RequirementCommitModel, mr.merge_base_commit_id) if mr.merge_base_commit_id else None
    merged = db.get(RequirementCommitModel, mr.merged_commit_id) if mr.merged_commit_id else None

    user_role = _user_role_in_project(db, project_id, user_id) if user_id else None
    can_approve, can_merge, blocking = _check_blocking_reasons(db, mr, user_role, user_id)

    return MergeRequestDetailResponse(
        **fields,
        source_head_commit_id=mr.source_head_commit_id,
        source_head_public_id=source_head.public_id if source_head else None,
        target_head_commit_id=mr.target_head_commit_id,
        target_head_public_id=target_head.public_id if target_head else None,
        merge_base_commit_id=mr.merge_base_commit_id,
        merge_base_public_id=merge_base.public_id if merge_base else None,
        merged_commit_id=mr.merged_commit_id,
        merged_commit_public_id=merged.public_id if merged else None,
        reviews=[_review_response(r, db) for r in mr.reviews],
        comments=[_comment_response(c, db) for c in mr.comments],
        can_approve=can_approve,
        can_merge=can_merge,
        blocking_reasons=blocking,
    )


def _load_mr(db: Session, project_id: int, mr_ref: str) -> MergeRequestModel:
    # 数字 ID 解析必须加 project_id 条件，防止跨项目引用分支。
    is_numeric = mr_ref.isdigit()
    mr = db.scalars(
        select(MergeRequestModel)
        .options(
            joinedload(MergeRequestModel.reviews),
            joinedload(MergeRequestModel.comments),
            joinedload(MergeRequestModel.source_head),
            joinedload(MergeRequestModel.target_head),
            joinedload(MergeRequestModel.merge_base),
            joinedload(MergeRequestModel.merged_commit),
        )
        .where(
            *([
                (MergeRequestModel.project_id == project_id)
                & (
                    (MergeRequestModel.public_id == mr_ref)
                    | (MergeRequestModel.id == int(mr_ref))
                ),
            ] if is_numeric else [
                (MergeRequestModel.project_id == project_id)
                & (MergeRequestModel.public_id == mr_ref),
            ])
        )
    ).first()
    if not mr:
        raise ValueError("merge_request_not_found")
    return mr


def add_mr_comment(
    db: Session,
    project_id: int,
    mr_ref: str,
    req: MergeCommentCreateRequest,
    user_id: int,
) -> MergeCommentResponse:
    mr = _load_mr(db, project_id, mr_ref)
    user_role = _user_role_in_project(db, project_id, user_id)

    # required 评论可阻塞合并，仅 admin/owner 可标记
    effective_required = req.required and _is_admin_or_owner(user_role)
    comment = MergeCommentModel(
        merge_request_id=mr.id,
        author_user_id=user_id,
        entity_uuid=req.entity_uuid,
        field_path=req.field_path,
        relation_key=req.relation_key,
        comment=req.comment,
        required=effective_required,
        status="active",
        effective_source_head_id=mr.source_head_commit_id,
    )
    db.add(comment)
    db.flush()

    # 通知 MR 作者
    if mr.author_user_id and mr.author_user_id != user_id:
        db.add(
            _build_notification(
                mr.project_id, mr.author_user_id,
                NOTIFY_MR_COMMENT,
                f"New comment on MR: {mr.title}",
                req.comment[:100],
            )
        )
    return _comment_response(comment, db)


def resolve_mr_comment(
    db: Session,
    project_id: int,
    mr_ref: str,
    comment_id: int,
    user_id: int,
) -> MergeCommentResponse:
    """将评论标记为已解决。作者、MR 作者或 admin 均可操作。"""
    mr = _load_mr(db, project_id, mr_ref)
    comment = db.get(MergeCommentModel, comment_id)
    if comment is None or comment.merge_request_id != mr.id:
        raise ValueError("comment_not_found")
    user_role = _user_role_in_project(db, project_id, user_id)
    if comment.author_user_id != user_id and mr.author_user_id != user_id and not _is_admin_or_owner(user_role):
        raise ValueError("only_author_or_admin_can_resolve")
    if comment.status != "active":
        raise ValueError("comment_not_active")
    comment.status = "resolved"
    db.flush()
    return _comment_response(comment, db)


def reopen_mr_comment(
    db: Session,
    project_id: int,
    mr_ref: str,
    comment_id: int,
    user_id: int,
) -> MergeCommentResponse:
    """重新打开已解决的评论。仅评论作者、MR 作者或 admin/owner 可操作。"""
    mr = _load_mr(db, project_id, mr_ref)
    comment = db.get(MergeCommentModel, comment_id)
    if comment is None or comment.merge_request_id != mr.id:
        raise ValueError("comment_not_found")
    if comment.status != "resolved":
        raise ValueError("comment_not_resolved")
    user_role = _user_role_in_project(db, project_id, user_id)
    if comment.author_user_id != user_id and mr.author_user_id != user_id and not _is_admin_or_owner(user_role):
        raise ValueError("only_author_or_admin_can_reopen")
    comment.status = "active"
    db.flush()
    return _comment_response(comment, db)


def review_mr(
    db: Session,
    project_id: int,
    mr_ref: str,
    req: MergeReviewRequest,
    user_id: int,
) -> MergeReviewResponse:
    mr = _load_mr(db, project_id, mr_ref)
    user_role = _user_role_in_project(db, project_id, user_id)

    if mr.author_user_id == user_id:
        raise ValueError("author_cannot_review_own_mr")
    if not _is_admin_or_owner(user_role):
        raise ValueError("only_admin_or_owner_can_review")
    if req.decision not in ("approved", "changes_requested"):
        raise ValueError("invalid_review_decision")
    if mr.status in ("merged", "closed"):
        raise ValueError("mr_already_closed")

    # 已有 active review → 拒绝重复审批。
    existing = db.scalars(
        select(MergeReviewModel).where(
            MergeReviewModel.merge_request_id == mr.id,
            MergeReviewModel.reviewer_user_id == user_id,
            MergeReviewModel.status == "active",
        )
    ).first()
    if existing:
        raise ValueError("duplicate_review_not_allowed")

    # 曾有过 stale review → 复用记录改为 active 重新审批（避免唯一约束冲突）。
    stale_review = db.scalars(
        select(MergeReviewModel).where(
            MergeReviewModel.merge_request_id == mr.id,
            MergeReviewModel.reviewer_user_id == user_id,
            MergeReviewModel.status == "stale",
        )
    ).first()
    if stale_review:
        stale_review.decision = req.decision
        stale_review.comment = req.comment or ""
        stale_review.status = "active"
        stale_review.stale_reason = None
        stale_review.stale_source_head_id = None
        stale_review.stale_target_head_id = None
        review = stale_review
        db.flush()
    else:
        review = MergeReviewModel(
            merge_request_id=mr.id,
            reviewer_user_id=user_id,
            decision=req.decision,
            comment=req.comment or "",
            status="active",
        )
        db.add(review)
        db.flush()

    # 更新 MR 状态：从 DB 重新查询决策（避免关系缓存未包含刚新增/更新的 review）
    db.refresh(mr)
    all_decisions = {r.decision for r in mr.reviews if r.status == "active"}
    if "changes_requested" in all_decisions or req.decision == "changes_requested":
        mr.status = "changes_requested"
    elif "approved" in all_decisions:
        mr.status = "approved"

    # 通知 MR 作者
    if mr.author_user_id and mr.author_user_id != user_id:
        db.add(
            _build_notification(
                mr.project_id, mr.author_user_id,
                NOTIFY_MR_REVIEW,
                f"MR reviewed: {req.decision}",
                f"{mr.title} is now {mr.status}",
            )
        )

    return _review_response(review, db)


def close_mr(
    db: Session,
    project_id: int,
    mr_ref: str,
    user_id: int,
) -> Dict[str, Any]:
    mr = _load_mr(db, project_id, mr_ref)
    user_role = _user_role_in_project(db, project_id, user_id)
    if mr.author_user_id != user_id and not _is_admin_or_owner(user_role):
        raise ValueError("only_author_or_admin_can_close")
    if mr.status in ("merged", "closed"):
        raise ValueError("mr_already_closed")
    mr.status = "closed"
    mr.closed_by_user_id = user_id
    db.flush()

    if mr.author_user_id and mr.author_user_id != user_id:
        db.add(
            _build_notification(
                mr.project_id, mr.author_user_id,
                NOTIFY_MR_CLOSED,
                f"MR closed: {mr.title}",
                f"MR has been closed",
            )
        )
    return {"status": "success", "mr_public_id": mr.public_id, "new_status": "closed"}
