"""
Semantic Diff Application Service.
把用户可读的 ref（commit/branch/workspace）解析为规范化状态字典，再调用纯 Diff 引擎，
输出可被前端对象树直接渲染的语义差异结果。所有 ref 解析都限定在当前项目内，禁止跨项目读取。
"""
import json
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.api.modules.version_control.observability import (
    monitor_vc_operation,
    log_vc_duration,
)
from backend.core.logging.events import VC_DIFF_COMPLETED, VC_DIFF_FAILED

from backend.database.model import RequirementCommitModel
from backend.api.modules.version_control.application.branch_service import (
    resolve_branch_context,
)
from backend.api.modules.version_control.application.commit_service import (
    resolve_commit_in_project,
)
from backend.api.modules.version_control.application.workspace_serializer import (
    serialize_workspace,
)
from backend.api.modules.version_control.application.errors import (
    BranchNotFoundError,
    CommitNotFoundError,
    InvalidDiffRefError,
)
from backend.api.modules.version_control.domain.serializer import CURRENT_SCHEMA_VERSION
from backend.api.modules.version_control.domain.semantic_diff import (
    COLLECTION_KEYS,
    compute_semantic_diff,
    find_entity_meta,
)
from backend.api.modules.version_control.schemas import (
    DiffRefInfo,
    DiffEntry,
    DiffResult,
    DiffSummary,
    EntityDiffResponse,
)


def _empty_state() -> Dict[str, Any]:
    """构造空项目规范化状态，用于无提交分支等没有可比基线的场景。"""
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "project_metadata": {
            "user_requirements": "",
            "kano_status": "missing",
            "unlocked_stages": "",
        },
        "actors": [],
        "features": [],
        "feature_relations": [],
        "scenarios": [],
        "business_objects": [],
        "flows": [],
        "scopes": [],
    }


def _parse_ref(ref: str) -> Tuple[str, str]:
    """解析 ref 字符串为 (kind, value)，kind ∈ {commit, branch, workspace}。"""
    if ":" in ref:
        kind, value = ref.split(":", 1)
        if kind in ("commit", "branch", "workspace") and value.strip():
            return kind, value.strip()
    raise InvalidDiffRefError(f"Invalid diff ref '{ref}'")


def _branch_info(
    branch,
    permissions: Dict[str, Any],
    kind: str,
    label: str,
    public_id: Optional[str] = None,
) -> DiffRefInfo:
    """从分支对象构造 Diff 的 ref 元信息。"""
    return DiffRefInfo(
        kind=kind,
        label=label,
        public_id=public_id,
        branch_ref=branch.public_id,
        branch_name=branch.name,
        branch_is_protected=bool(permissions.get("is_protected", False)),
    )


def resolve_state(
    db: Session,
    project_id: int,
    ref: str,
) -> Tuple[Dict[str, Any], DiffRefInfo]:
    """按 ref 解析一份规范化状态与元信息。"""
    kind, value = _parse_ref(ref)

    if kind == "commit":
        commit = resolve_commit_in_project(db, project_id, value)
        if commit is None:
            raise CommitNotFoundError(f"Commit '{value}' not found in project {project_id}")
        state = json.loads(commit.state_json) if commit.state_json else _empty_state()
        info = DiffRefInfo(
            kind="commit",
            label=f"commit {commit.public_id[:8]}",
            public_id=commit.public_id,
        )
        return state, info

    branch, workspace, permissions = resolve_branch_context(db, project_id, value)
    if branch is None:
        raise BranchNotFoundError(f"Branch '{value}' not found in project {project_id}")

    if kind == "branch":
        if branch.head_commit_id is None:
            return _empty_state(), _branch_info(branch, permissions, "branch", f"branch {branch.name}（空）")
        head = db.get(RequirementCommitModel, branch.head_commit_id)
        state = json.loads(head.state_json) if head and head.state_json else _empty_state()
        return state, _branch_info(
            branch, permissions, "branch",
            f"branch {branch.name} @ {head.public_id[:8]}",
            public_id=head.public_id if head else None,
        )

    # kind == "workspace"
    state = serialize_workspace(db, workspace) if workspace else _empty_state()
    return state, _branch_info(branch, permissions, "workspace", f"branch {branch.name} 工作区")


def _resolve_base_state(
    db: Session,
    project_id: int,
    ref: Optional[str],
    branch_ref: Optional[str],
) -> Tuple[Dict[str, Any], DiffRefInfo]:
    """解析 Diff 基线：优先显式 ref，缺省为分支 head 提交。"""
    if ref:
        return resolve_state(db, project_id, ref)
    branch, _, permissions = resolve_branch_context(db, project_id, branch_ref or "main")
    if branch is None:
        raise BranchNotFoundError(f"Branch '{branch_ref or 'main'}' not found in project {project_id}")
    if branch.head_commit_id is None:
        return _empty_state(), _branch_info(branch, permissions, "branch", f"branch {branch.name}（空）")
    head = db.get(RequirementCommitModel, branch.head_commit_id)
    state = json.loads(head.state_json) if head and head.state_json else _empty_state()
    return state, _branch_info(
        branch, permissions, "branch",
        f"branch {branch.name} @ {head.public_id[:8]}",
        public_id=head.public_id if head else None,
    )


def _resolve_target_state(
    db: Session,
    project_id: int,
    ref: Optional[str],
    branch_ref: Optional[str],
) -> Tuple[Dict[str, Any], DiffRefInfo]:
    """解析 Diff 目标：优先显式 ref，缺省为分支当前工作区（未提交变更）。"""
    if ref:
        return resolve_state(db, project_id, ref)
    branch, workspace, permissions = resolve_branch_context(db, project_id, branch_ref or "main")
    if branch is None:
        raise BranchNotFoundError(f"Branch '{branch_ref or 'main'}' not found in project {project_id}")
    state = serialize_workspace(db, workspace) if workspace else _empty_state()
    return state, _branch_info(branch, permissions, "workspace", f"branch {branch.name} 工作区")


def get_diff(
    db: Session,
    project_id: int,
    base_ref: Optional[str] = None,
    target_ref: Optional[str] = None,
    branch_ref: Optional[str] = None,
    entity_type: Optional[str] = None,
    change_type: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> DiffResult:
    """
    计算任意两 ref 的语义差异；缺省时比较分支 head 与当前工作区（未提交改动）。

    支持按对象类型与变更种类筛选，先分页后组装，避免大项目一次传输全部变更。
    Diff 是高频只读路径，不写审计行，仅记 domain 日志（含耗时与变更量）供性能观测。
    """
    started = time.perf_counter()
    try:
        base_state, base_info = _resolve_base_state(db, project_id, base_ref, branch_ref)
        target_state, target_info = _resolve_target_state(db, project_id, target_ref, branch_ref)

        result = compute_semantic_diff(base_state, target_state)
        entries: List[Dict[str, Any]] = result["entries"]
        if entity_type:
            entries = [entry for entry in entries if entry["entity_type"] == entity_type]
        if change_type:
            entries = [entry for entry in entries if entry["change_type"] == change_type]

        total = len(entries)
        paged = entries[offset : offset + limit]
        log_vc_duration(
            VC_DIFF_COMPLETED, started,
            project_id=project_id,
            operation="semantic_diff",
            entries_total=total,
            changed_object_count=len({e["entity_uuid"] for e in entries}),
            filtered=(bool(entity_type) or bool(change_type)),
        )
        return DiffResult(
            base=base_info,
            target=target_info,
            summary=DiffSummary(**result["summary"]),
            entries=[DiffEntry(**entry) for entry in paged],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception:
        with monitor_vc_operation(
            "semantic_diff", failure_event=VC_DIFF_FAILED, project_id=project_id
        ):
            raise


def _find_entity_by_uuid(
    state: Dict[str, Any],
    entity_uuid: str,
) -> Optional[Dict[str, Any]]:
    """在规范化状态中按 logical_uuid 查找对象（含嵌套子对象与项目元数据）。"""
    if entity_uuid == "project":
        return {"project_metadata": state.get("project_metadata", {})}
    for key in COLLECTION_KEYS:
        for entity in state.get(key, []):
            if entity.get("logical_uuid") == entity_uuid:
                return entity
    for scenario in state.get("scenarios", []):
        for ac in scenario.get("acceptance_criteria", []):
            if ac.get("logical_uuid") == entity_uuid:
                return ac
    for business_object in state.get("business_objects", []):
        for attribute in business_object.get("attributes", []):
            if attribute.get("logical_uuid") == entity_uuid:
                return attribute
    for flow in state.get("flows", []):
        for step in flow.get("steps", []):
            if step.get("logical_uuid") == entity_uuid:
                return step
    return None


def get_entity_diff(
    db: Session,
    project_id: int,
    entity_uuid: str,
    base_ref: Optional[str] = None,
    target_ref: Optional[str] = None,
    branch_ref: Optional[str] = None,
) -> EntityDiffResponse:
    """
    返回单个对象的差异详情：对象自身与其子对象的全部变更条目，以及 base/target 的完整值。
    供前端选中对象树节点后展示字段/关系/顺序细节。
    """
    started = time.perf_counter()
    try:
        base_state, base_info = _resolve_base_state(db, project_id, base_ref, branch_ref)
        target_state, target_info = _resolve_target_state(db, project_id, target_ref, branch_ref)

        result = compute_semantic_diff(base_state, target_state)
        entries = [
            entry
            for entry in result["entries"]
            if entry["entity_uuid"] == entity_uuid or entry.get("parent_uuid") == entity_uuid
        ]
        meta = find_entity_meta(base_state, target_state, entity_uuid)
        log_vc_duration(
            VC_DIFF_COMPLETED, started,
            project_id=project_id,
            operation="entity_diff",
            entity_uuid=entity_uuid,
            entries_total=len(entries),
        )
        return EntityDiffResponse(
            base=base_info,
            target=target_info,
            entity_uuid=entity_uuid,
            entity_type=meta.get("entity_type", ""),
            entity_name=meta.get("name", entity_uuid),
            base_value=_find_entity_by_uuid(base_state, entity_uuid),
            target_value=_find_entity_by_uuid(target_state, entity_uuid),
            entries=[DiffEntry(**entry) for entry in entries],
        )
    except Exception:
        with monitor_vc_operation(
            "entity_diff", failure_event=VC_DIFF_FAILED, project_id=project_id
        ):
            raise
