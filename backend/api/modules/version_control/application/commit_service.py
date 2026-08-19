"""
Commit Application Service.
负责需求空间提交的生命周期：
  - 创建提交：读取分支工作区 → 规范化序列化/哈希 → 预期 head compare-and-swap → 父关系 → 推进 head；
  - 提交图查询：分支标签、父节点、合并节点、分页、短标识，且所有查询都限定在当前项目内；
  - 历史只读视图：由 Commit state_json 重建规范化模型，绝不读取当前分支表。
提交一旦创建不可修改（RequirementCommitModel 的 before_update 事件强制），历史因此不可变。
"""
import json
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, load_only

from backend.database.model import (
    UserModel,
    RequirementBranchModel,
    RequirementCommitModel,
    RequirementCommitParentModel,
)
from backend.api.modules.version_control.application.branch_service import (
    resolve_branch_context,
)
from backend.api.modules.version_control.application.workspace_serializer import (
    serialize_workspace,
)
from backend.api.modules.version_control.application.errors import (
    BranchNotFoundError,
    CommitNotFoundError,
    HeadChangedError,
    ProtectedBranchError,
)
from backend.api.modules.version_control.domain.serializer import (
    CURRENT_SCHEMA_VERSION,
    to_deterministic_json,
    compute_state_hash,
)
from backend.api.modules.version_control.schemas import (
    CommitCreateRequest,
    CommitSummaryResponse,
    CommitDetailResponse,
    CommitListResponse,
)

_GRAPH_COLLECTION_KEYS = (
    "actors",
    "features",
    "feature_relations",
    "scenarios",
    "business_objects",
    "flows",
    "scopes",
)


def build_commit_summary(normalized_state: Dict[str, Any]) -> Dict[str, Any]:
    """按对象类型统计规范化状态的对象数量，作为提交的变更摘要载荷。"""
    return {
        key: len(normalized_state.get(key, []))
        for key in _GRAPH_COLLECTION_KEYS
    }


def resolve_commit_in_project(
    db: Session,
    project_id: int,
    commit_ref: str,
) -> Optional[RequirementCommitModel]:
    """在指定项目内解析提交引用：支持数字主键、完整 public_id 和短标识前缀。"""
    ref_str = str(commit_ref).strip()
    if ref_str.isdigit():
        commit = db.get(RequirementCommitModel, int(ref_str))
        if commit is not None and commit.project_id == project_id:
            return commit
        return None

    commit = db.scalars(
        select(RequirementCommitModel).where(
            RequirementCommitModel.public_id == ref_str,
            RequirementCommitModel.project_id == project_id,
        )
    ).first()
    if commit is not None:
        return commit

    # 短标识：取匹配前缀的第一条，保证结果确定。
    return db.scalars(
        select(RequirementCommitModel)
        .where(
            RequirementCommitModel.public_id.like(f"{ref_str}%"),
            RequirementCommitModel.project_id == project_id,
        )
        .order_by(RequirementCommitModel.id.asc())
    ).first()


def _resolve_expected_head(
    db: Session,
    project_id: int,
    branch: RequirementBranchModel,
    req: CommitCreateRequest,
) -> Optional[int]:
    """解析并校验预期 head；不一致时抛出 HeadChangedError 防止静默覆盖他人提交。"""
    expected_id: Optional[int] = None
    if req.expected_head_commit_id is not None:
        expected_id = req.expected_head_commit_id
    elif req.expected_head_commit_public_id:
        expected = resolve_commit_in_project(db, project_id, req.expected_head_commit_public_id)
        if expected is None:
            raise CommitNotFoundError(f"Expected head commit '{req.expected_head_commit_public_id}' not found")
        expected_id = expected.id

    if expected_id is None:
        return None
    if branch.head_commit_id != expected_id:
        current = db.get(RequirementCommitModel, branch.head_commit_id) if branch.head_commit_id else None
        raise HeadChangedError(
            "Branch head advanced since this edit was loaded; refresh and retry",
            current_head_commit_id=branch.head_commit_id,
            current_head_public_id=current.public_id if current else None,
        )
    return expected_id


def create_commit(
    db: Session,
    project_id: int,
    branch_ref: str,
    req: CommitCreateRequest,
    user_id: Optional[int] = None,
) -> CommitDetailResponse:
    """
    把分支工作区当前状态固化为一条不可变提交，并在同一事务内推进分支 head。

    :raises ProtectedBranchError: 目标分支受保护（main 只能经 MR 合入）
    :raises HeadChangedError: 预期 head 与当前 head 不一致（并发覆盖防护）
    """
    branch, workspace, permissions = resolve_branch_context(db, project_id, branch_ref, user_id)
    if branch is None or workspace is None:
        raise BranchNotFoundError(f"Branch '{branch_ref}' not found in project {project_id}")
    if not permissions.get("can_write", False):
        raise ProtectedBranchError(
            "Branch is protected; only the system may write to main and changes are merged via Merge Requests"
        )

    _resolve_expected_head(db, project_id, branch, req)

    # 读取工作区完整语义模型并规范化/哈希；提交存储完整状态而非补丁链，便于恢复、Diff 与审计。
    normalized_state = serialize_workspace(db, workspace)
    state_json = to_deterministic_json(normalized_state)
    state_hash = compute_state_hash(state_json)

    commit = RequirementCommitModel(
        project_id=project_id,
        message=req.message,
        state_json=state_json,
        state_hash=state_hash,
        schema_version=CURRENT_SCHEMA_VERSION,
        author_user_id=user_id,
        summary_json=build_commit_summary(normalized_state),
    )
    db.add(commit)
    db.flush()

    if branch.head_commit_id is not None:
        db.add(
            RequirementCommitParentModel(
                commit_id=commit.id,
                parent_commit_id=branch.head_commit_id,
                parent_order=0,
            )
        )
        db.flush()

    # head compare-and-swap：以读取到的 head 为条件推进，条件不满足说明他人已提交，返回 409。
    result = db.execute(
        update(RequirementBranchModel)
        .where(
            RequirementBranchModel.id == branch.id,
            RequirementBranchModel.head_commit_id == branch.head_commit_id,
        )
        .values(head_commit_id=commit.id)
    )
    if result.rowcount != 1:
        current = db.get(RequirementCommitModel, branch.head_commit_id) if branch.head_commit_id else None
        raise HeadChangedError(
            "Branch head changed concurrently; refresh and retry",
            current_head_commit_id=branch.head_commit_id,
            current_head_public_id=current.public_id if current else None,
        )
    # 同步 ORM 对象上的 head，保证同事务内后续查询（如分支标签）读到的是推进后的值。
    branch.head_commit_id = commit.id
    db.flush()

    return get_commit_detail(db, project_id, commit.public_id)


def build_branch_index(db: Session, project_id: int) -> Dict[int, List[RequirementBranchModel]]:
    """构建 head_commit_id → 指向该提交的活跃分支列表，用于提交图上的分支标签。"""
    branches = db.scalars(
        select(RequirementBranchModel).where(
            RequirementBranchModel.project_id == project_id,
            RequirementBranchModel.status == "active",
        )
    ).all()
    index: Dict[int, List[RequirementBranchModel]] = defaultdict(list)
    for branch in branches:
        if branch.head_commit_id is not None:
            index[branch.head_commit_id].append(branch)
    return index


def _load_project_commit_graph(
    db: Session,
    project_id: int,
) -> Tuple[Set[int], Dict[int, List[RequirementCommitParentModel]]]:
    """加载项目内提交 id 集合与父子关系（仅投影 id，不加载 state_json 大列）。

    供提交图可达性遍历与 merge base 计算使用。分页列表不依赖本函数（改走
    _load_commit_page 的 SQL 层分页），避免每次列表请求全量水合项目提交。
    """
    commit_ids = set(db.scalars(
        select(RequirementCommitModel.id).where(RequirementCommitModel.project_id == project_id)
    ).all())
    parent_rows = db.scalars(
        select(RequirementCommitParentModel).where(
            RequirementCommitParentModel.commit_id.in_(commit_ids)
        )
    ).all()
    parents_by_commit: Dict[int, List[RequirementCommitParentModel]] = defaultdict(list)
    for row in parent_rows:
        if row.parent_commit_id in commit_ids:
            parents_by_commit[row.commit_id].append(row)
    return commit_ids, parents_by_commit


def _reachable_commit_ids(
    head_commit_id: int,
    parents_by_commit: Dict[int, List[RequirementCommitParentModel]],
) -> Set[int]:
    """沿父链（含 merge 双父）收集从分支 head 可达的全部提交。"""
    seen: Set[int] = set()
    stack = [head_commit_id]
    while stack:
        commit_id = stack.pop()
        if commit_id in seen:
            continue
        seen.add(commit_id)
        stack.extend(row.parent_commit_id for row in parents_by_commit.get(commit_id, []))
    return seen


def _commit_summary_fields(
    db: Session,
    commit: RequirementCommitModel,
    parent_ids: List[int],
    parent_public_ids: List[str],
    branch_index: Dict[int, List[RequirementBranchModel]],
) -> Dict[str, Any]:
    """构造提交摘要响应字段（含作者邮箱与分支标签）。"""
    author_email: Optional[str] = None
    if commit.author_user_id is not None:
        author = db.get(UserModel, commit.author_user_id)
        if author is not None:
            author_email = author.email
    branches = branch_index.get(commit.id, [])
    return {
        "id": commit.id,
        "public_id": commit.public_id,
        "short_id": commit.public_id[:8],
        "message": commit.message,
        "state_hash": commit.state_hash,
        "schema_version": commit.schema_version,
        "summary": commit.summary_json,
        "author_user_id": commit.author_user_id,
        "author_email": author_email,
        "created_at": commit.created_at,
        "parent_ids": parent_ids,
        "parent_public_ids": parent_public_ids,
        "is_merge": len(parent_ids) == 2,
        "branch_public_ids": [branch.public_id for branch in branches],
        "branch_names": [branch.name for branch in branches],
    }


def _load_commit_page(
    db: Session,
    project_id: int,
    commit_ids: Optional[Set[int]],
    limit: int,
    offset: int,
) -> List[RequirementCommitModel]:
    """SQL 层分页加载提交（仅裁剪列，不加载 state_json 大列）。

    commit_ids 为 None 时表示全项目（all 模式）；否则按可达集过滤。
    """
    stmt = select(RequirementCommitModel).options(
        load_only(
            RequirementCommitModel.id,
            RequirementCommitModel.public_id,
            RequirementCommitModel.message,
            RequirementCommitModel.state_hash,
            RequirementCommitModel.schema_version,
            RequirementCommitModel.summary_json,
            RequirementCommitModel.author_user_id,
            RequirementCommitModel.created_at,
        )
    ).where(RequirementCommitModel.project_id == project_id)
    if commit_ids is not None:
        # 大可达集可能超 SQLite 变量上限：按 500 条分块并集。
        clauses = [
            RequirementCommitModel.id.in_(ids_chunk)
            for ids_chunk in _chunk(commit_ids, 500)
        ]
        if clauses:
            stmt = stmt.where(or_(*clauses))
        else:
            return []
    return db.scalars(
        stmt.order_by(RequirementCommitModel.created_at.desc(), RequirementCommitModel.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()


def _chunk(values: Set[int], size: int) -> List[Set[int]]:
    """把集合按固定大小切成多块，供 IN 子句分块（SQLite 变量上限规避）。"""
    items = list(values)
    return [set(items[i : i + size]) for i in range(0, len(items), size)]


def _count_commits(db: Session, project_id: int, commit_ids: Optional[Set[int]]) -> int:
    """统计分页范围内的提交总数（与 _load_commit_page 同谓词）。"""
    stmt = select(func.count()).select_from(RequirementCommitModel).where(
        RequirementCommitModel.project_id == project_id
    )
    if commit_ids is not None:
        clauses = [
            RequirementCommitModel.id.in_(ids_chunk)
            for ids_chunk in _chunk(commit_ids, 500)
        ]
        if clauses:
            stmt = stmt.where(or_(*clauses))
        else:
            return 0
    return db.scalar(stmt) or 0


def _page_parent_edges(
    db: Session,
    project_id: int,
    page_ids: List[int],
) -> Dict[int, List[int]]:
    """按 parent_order 加载分页提交的父 id 列表（仅取本页提交的父边）。"""
    if not page_ids:
        return {}
    rows = db.scalars(
        select(RequirementCommitParentModel).where(
            RequirementCommitParentModel.commit_id.in_(page_ids)
        )
    ).all()
    edges: Dict[int, List[int]] = defaultdict(list)
    for row in sorted(rows, key=lambda r: r.parent_order):
        edges[row.commit_id].append(row.parent_commit_id)
    return edges


def _parent_public_id_map(
    db: Session,
    parent_ids: Set[int],
) -> Dict[int, str]:
    """批量解析父提交 id → public_id（供提交图边渲染）。"""
    if not parent_ids:
        return {}
    rows = db.execute(
        select(RequirementCommitModel.id, RequirementCommitModel.public_id).where(
            RequirementCommitModel.id.in_(parent_ids)
        )
    ).all()
    return {cid: pub for cid, pub in rows}


def list_commits(
    db: Session,
    project_id: int,
    branch_ref: Optional[str] = None,
    all: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> CommitListResponse:
    """
    SQL 层分页列出提交，按 (created_at, id) 倒序。

    all=True 或未指定分支时返回全项目提交（供提交图渲染跨分支轨道）；
    否则返回指定分支 head 沿父链可达的提交。每条携带父节点、合并标记与分支标签。
    """
    branch_index = build_branch_index(db, project_id)

    if not all and branch_ref:
        branch, _, _ = resolve_branch_context(db, project_id, branch_ref)
        if branch is None or branch.head_commit_id is None:
            return CommitListResponse(commits=[], total=0, limit=limit, offset=offset)
        _, parents_by_commit = _load_project_commit_graph(db, project_id)
        commit_ids = _reachable_commit_ids(branch.head_commit_id, parents_by_commit)
    else:
        commit_ids = None

    total = _count_commits(db, project_id, commit_ids)
    page = _load_commit_page(db, project_id, commit_ids, limit, offset)

    edges = _page_parent_edges(db, project_id, [c.id for c in page])
    all_parent_ids = {pid for pids in edges.values() for pid in pids}
    pub_map = _parent_public_id_map(db, all_parent_ids)

    summaries: List[CommitSummaryResponse] = []
    for commit in page:
        parent_ids = edges.get(commit.id, [])
        parent_public_ids = [pub_map[pid] for pid in parent_ids if pid in pub_map]
        summaries.append(
            CommitSummaryResponse(
                **_commit_summary_fields(db, commit, parent_ids, parent_public_ids, branch_index)
            )
        )
    return CommitListResponse(commits=summaries, total=total, limit=limit, offset=offset)


def get_commit_detail(
    db: Session,
    project_id: int,
    commit_ref: str,
) -> CommitDetailResponse:
    """
    获取提交详情，并从 state_json 重建只读的历史视图模型。
    历史提交永远只读；任何想按提交改写工作区的调用都应被上层拒绝。
    """
    commit = resolve_commit_in_project(db, project_id, commit_ref)
    if commit is None:
        raise CommitNotFoundError(f"Commit '{commit_ref}' not found in project {project_id}")

    parent_rows = db.scalars(
        select(RequirementCommitParentModel)
        .where(RequirementCommitParentModel.commit_id == commit.id)
        .order_by(RequirementCommitParentModel.parent_order)
    ).all()
    parent_ids = [row.parent_commit_id for row in parent_rows]
    parent_commits = [db.get(RequirementCommitModel, pid) for pid in parent_ids]
    parent_public_ids = [
        parent.public_id for parent in parent_commits if parent is not None
    ]
    branch_index = build_branch_index(db, project_id)

    fields = _commit_summary_fields(db, commit, parent_ids, parent_public_ids, branch_index)
    fields["state"] = json.loads(commit.state_json) if commit.state_json else None
    return CommitDetailResponse(**fields)
