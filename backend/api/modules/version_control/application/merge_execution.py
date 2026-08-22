"""
Merge Request Execution Service (Phase 6).
在满足 MR 审批后执行三方语义合并：预览（可重建）、冲突解决与原子合并。

流程：
  - get_merge_preview：按 MR 当前 base/source/target heads 重算三方合并，返回未解决冲突列表（只读，不提交）；
  - perform_merge：重校验 MR 前置条件与审批 → 应用 resolutions 重算合并 → 结构校验 →
    清空目标工作区 → 恢复合并后状态 → 创建双父 merge commit → CAS 推进目标 head → 置 MR 为 merged。
合并是服务端单一事务：任何校验失败都抛异常，调用方不提交即整体回滚，不产生部分目标写入。
"""
import json
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.api.modules.version_control.application.branch_service import (
    resolve_branch_context,
)
from backend.api.modules.version_control.application.commit_service import (
    build_commit_summary,
)
from backend.api.modules.version_control.application.errors import (
    HeadChangedError,
    MergeBlockedError,
    MergeConflictError,
)
from backend.api.modules.version_control.application.merge_service import (
    _check_blocking_reasons,
    _find_merge_base,
    _load_mr,
    _user_role_in_project,
    sync_mrs_on_branch_commit,
)
from backend.api.modules.version_control.application.workspace_restoration import (
    restore_workspace_from_state,
    scrub_workspace,
)
from backend.api.modules.version_control.domain.semantic_merge import (
    compute_three_way_merge,
)
from backend.api.modules.version_control.domain.serializer import (
    CURRENT_SCHEMA_VERSION,
    compute_state_hash,
    to_deterministic_json,
)
from backend.api.modules.version_control.schemas import (
    ConflictItemResponse,
    MergePreviewResponse,
    MergeRequestPayload,
    MergeResponse,
)
from backend.database.model import (
    AuditLogModel,
    MergeRequestModel,
    RequirementBranchModel,
    RequirementCommitModel,
    RequirementCommitParentModel,
)


def _load_commit_state(db: Session, commit_id: int | None) -> dict[str, Any]:
    """读取 Commit 的规范化状态字典；提交缺失或空时返回空状态。"""
    if not commit_id:
        return {}
    commit = db.get(RequirementCommitModel, commit_id)
    if commit is None or not commit.state_json:
        return {}
    return json.loads(commit.state_json)


def _merge_inputs(
    db: Session,
    mr: MergeRequestModel,
) -> tuple[int, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """从分支当前 heads 读取 base/source/target 状态。

    返回 (base_commit_id, base_state, target_state, source_state)。base_commit_id 是依据
    当前 source/target heads 实时计算的最近共同祖先；预览元数据（base/source/target head）
    必须基于同一组提交生成，避免“用当前 heads 算 LCA 却返回 MR 缓存的旧 merge base”的自相矛盾。
    """
    target_branch = db.get(RequirementBranchModel, mr.target_branch_id)
    source_branch = db.get(RequirementBranchModel, mr.source_branch_id)

    source_head_id = source_branch.head_commit_id if source_branch else None
    target_head_id = target_branch.head_commit_id if target_branch else None
    if source_head_id and target_head_id:
        base_id = _find_merge_base(db, mr.project_id, source_head_id, target_head_id)
    else:
        base_id = mr.merge_base_commit_id
    base_state = _load_commit_state(db, base_id)
    target_state = _load_commit_state(db, target_head_id)
    source_state = _load_commit_state(db, source_head_id)
    return base_id, base_state, target_state, source_state


def _resolve_commit_public_id(db: Session, commit_id: int | None) -> str | None:
    """取 Commit 的 public_id；提交缺失时返回 None。"""
    if not commit_id:
        return None
    commit = db.get(RequirementCommitModel, commit_id)
    return commit.public_id if commit else None


def _merge_preview_meta(db: Session, mr: MergeRequestModel, base_id: int) -> dict[str, str | None]:
    """构造预览返回所需的 heads 元信息（与 _merge_inputs 同源，避免自相矛盾）。"""
    source_branch = db.get(RequirementBranchModel, mr.source_branch_id)
    target_branch = db.get(RequirementBranchModel, mr.target_branch_id)
    return {
        "merge_base_public_id": _resolve_commit_public_id(db, base_id),
        "source_head_public_id": _resolve_commit_public_id(db, source_branch.head_commit_id if source_branch else None),
        "target_head_public_id": _resolve_commit_public_id(db, target_branch.head_commit_id if target_branch else None),
    }


def _resolve_by_public_id(db: Session, project_id: int, public_id: str | None) -> RequirementCommitModel | None:
    """按 public_id 在项目内解析提交；未提供或不属于本项目时返回 None。"""
    if not public_id:
        return None
    return db.scalars(
        select(RequirementCommitModel).where(
            RequirementCommitModel.public_id == public_id,
            RequirementCommitModel.project_id == project_id,
        )
    ).first()


def _verify_preview_heads(
    db: Session,
    req: MergeRequestPayload,
    *,
    project_id: int,
    current_base_id: int | None,
    current_source_head_id: int | None,
    current_target_head_id: int | None,
) -> None:
    """校验客户端预览绑定的三方 heads 与当前分支 heads 完全一致。

    预览后 source 或 target 推进意味着预览与审批已过期：若仍按旧 heads 创建 merge commit
    并把 MR 标记 merged，会把未审阅的 source 提交合入目标。任一不一致（含无法解析的 public_id，
    解析为 None 即视为不匹配）都抛出 HeadChangedError(409)。
    """
    def _expect(public_id: str, current_id: int | None, label: str) -> None:
        commit = _resolve_by_public_id(db, project_id, public_id)
        if commit is None or commit.id != current_id:
            raise HeadChangedError(
                f"Merge preview is stale: {label} advanced since preview",
                current_head_commit_id=current_target_head_id,
                current_head_public_id=_resolve_commit_public_id(db, current_target_head_id),
            )

    _expect(req.merge_base_public_id, current_base_id, "merge_base")
    _expect(req.source_head_public_id, current_source_head_id, "source_head")
    _expect(req.target_head_public_id, current_target_head_id, "target_head")


def _conflict_resolution_payload(
    req: MergeRequestPayload,
    source_head_id: int | None,
    target_head_id: int | None,
) -> dict[str, Any]:
    """构造冲突解决的审计载荷：冲突 ID、选择、手工值摘要与对应 heads。

    手工值不做完整记录以免在审计中留存敏感内容，只记录类型与长度摘要。
    """
    resolutions = []
    for item in req.resolutions:
        entry: dict[str, Any] = {"conflict_id": item.conflict_id, "choice": item.choice}
        if item.manual_value is not None:
            entry["manual_value_kind"] = type(item.manual_value).__name__
            entry["manual_value_length"] = len(str(item.manual_value))
        resolutions.append(entry)
    return {
        "conflict_count": len(req.resolutions),
        "resolutions": resolutions,
        "source_head_commit_id": source_head_id,
        "target_head_commit_id": target_head_id,
    }


def _resolutions_dict(req: MergeRequestPayload) -> dict[str, dict[str, Any]]:
    """把请求体的 resolutions 列表规整为 conflict_id → 选择 的映射。"""
    result: dict[str, dict[str, Any]] = {}
    for item in req.resolutions:
        entry: dict[str, Any] = {"choice": item.choice}
        if item.manual_value is not None:
            entry["manual_value"] = item.manual_value
        result[item.conflict_id] = entry
    return result


def _conflict_response(item: dict[str, Any]) -> ConflictItemResponse:
    """把纯引擎冲突项映射为 HTTP 响应模型。"""
    return ConflictItemResponse(
        conflict_id=item["conflict_id"],
        conflict_type=item["conflict_type"],
        entity_type=item["entity_type"],
        entity_uuid=item["entity_uuid"],
        entity_name=item.get("entity_name", ""),
        path=item.get("path", ""),
        parent_uuid=item.get("parent_uuid"),
        parent_type=item.get("parent_type"),
        base_value=item.get("base_value"),
        target_value=item.get("target_value"),
        source_value=item.get("source_value"),
        related_entity_type=item.get("related_entity_type"),
        related_entity_uuid=item.get("related_entity_uuid"),
        related_entity_name=item.get("related_entity_name"),
        choices=list(item.get("choices", ["target", "source"])),
        resolved=item.get("resolved", False),
    )


def get_merge_preview(
    db: Session,
    project_id: int,
    mr_ref: str,
) -> MergePreviewResponse:
    """计算 MR 的三方合并预览（只读）。

    每次调用都按当前 heads 重算，可重建、无服务端状态。只读取数据，不做任何写入，
    与 get_mr_detail 保持一致，避免 GET 产生副作用。
    """
    mr = _load_mr(db, project_id, mr_ref)
    base_id, base_state, target_state, source_state = _merge_inputs(db, mr)
    result = compute_three_way_merge(base_state, target_state, source_state)
    meta = _merge_preview_meta(db, mr, base_id)

    return MergePreviewResponse(
        merge_base_public_id=meta["merge_base_public_id"],
        source_head_public_id=meta["source_head_public_id"],
        target_head_public_id=meta["target_head_public_id"],
        conflict_count=len(result["conflicts"]),
        conflicts=[_conflict_response(c) for c in result["conflicts"]],
        auto_merged_summary=result["auto_merged"],
    )


def _validate_merged_structure(
    db: Session,
    project_id: int,
    merged_state: dict[str, Any],
) -> None:
    """校验合并后的规范化状态满足结构不变量：关系闭包、无重复 uuid、位置唯一。

    闭包校验与 restore_workspace_from_state 的校验一致，提前在提交前发现悬挂引用，
    使错误定位到 logical_uuid 与关系，而不是在写入目标工作区时才抛错。
    """
    feature_uuids = {e["logical_uuid"] for e in merged_state.get("features", [])}
    actor_uuids = {e["logical_uuid"] for e in merged_state.get("actors", [])}
    bo_uuids = {e["logical_uuid"] for e in merged_state.get("business_objects", [])}
    step_uuids: dict[str, str] = {}
    for flow in merged_state.get("flows", []):
        for step in flow.get("steps", []):
            step_uuids[step["logical_uuid"]] = flow["logical_uuid"]

    errors: list[str] = []
    for rel in merged_state.get("feature_relations", []):
        if rel["parent_feature_logical_uuid"] not in feature_uuids:
            errors.append(f"feature_relation {rel['logical_uuid']} refers to missing parent feature {rel['parent_feature_logical_uuid']}")
        if rel["child_feature_logical_uuid"] not in feature_uuids:
            errors.append(f"feature_relation {rel['logical_uuid']} refers to missing child feature {rel['child_feature_logical_uuid']}")
    for scenario in merged_state.get("scenarios", []):
        if scenario["feature_logical_uuid"] not in feature_uuids:
            errors.append(f"scenario {scenario['logical_uuid']} refers to missing feature {scenario['feature_logical_uuid']}")
        if scenario["actor_logical_uuid"] not in actor_uuids:
            errors.append(f"scenario {scenario['logical_uuid']} refers to missing actor {scenario['actor_logical_uuid']}")
    for flow in merged_state.get("flows", []):
        for f_uuid in flow.get("feature_logical_uuids", []):
            if f_uuid not in feature_uuids:
                errors.append(f"flow {flow['logical_uuid']} refers to missing feature {f_uuid}")
        for step in flow.get("steps", []):
            for a_uuid in step.get("actor_logical_uuids", []):
                if a_uuid not in actor_uuids:
                    errors.append(f"flow_step {step['logical_uuid']} refers to missing actor {a_uuid}")
            for in_uuid in step.get("input_business_object_logical_uuids", []):
                if in_uuid not in bo_uuids:
                    errors.append(f"flow_step {step['logical_uuid']} input refers to missing business object {in_uuid}")
            for out_uuid in step.get("output_business_object_logical_uuids", []):
                if out_uuid not in bo_uuids:
                    errors.append(f"flow_step {step['logical_uuid']} output refers to missing business object {out_uuid}")
            for nxt_uuid in step.get("next_step_logical_uuids", []):
                if nxt_uuid not in step_uuids:
                    errors.append(f"flow_step {step['logical_uuid']} next refers to missing step {nxt_uuid}")
                elif step_uuids[nxt_uuid] != flow["logical_uuid"]:
                    errors.append(f"flow_step {step['logical_uuid']} next step {nxt_uuid} belongs to a different flow")
    for scope in merged_state.get("scopes", []):
        if scope["feature_logical_uuid"] not in feature_uuids:
            errors.append(f"scope {scope['logical_uuid']} refers to missing feature {scope['feature_logical_uuid']}")

    if errors:
        raise MergeConflictError("merge_structure_invalid", structure_errors=errors)


def perform_merge(
    db: Session,
    project_id: int,
    mr_ref: str,
    req: MergeRequestPayload,
    user_id: int,
) -> MergeResponse:
    """执行三方语义合并并创建 merge commit（原子事务）。

    步骤：重校验 MR 前置条件 → 应用 resolutions 重算合并 → 结构校验 → 清空并恢复目标工作区
    → 创建双父 merge commit → CAS 推进目标 head → 置 MR 为 merged。
    任一校验失败抛异常，调用方不提交即整体回滚。

    :raises MergeBlockedError: 前置条件未满足（缺审批、目标推进、存在阻塞原因）
    :raises MergeConflictError: 仍有未解决冲突或合并后结构校验失败
    :raises HeadChangedError: source/target 分支 head 并发变化（409）
    """
    import time

    from backend.api.modules.version_control.observability import log_vc_duration
    from backend.core.logging.events import VC_MERGE_COMPLETED
    started = time.perf_counter()
    mr = _load_mr(db, project_id, mr_ref)
    if mr.status in ("merged", "closed"):
        raise MergeBlockedError("mr_already_closed", reasons=["mr_already_closed"])

    # 事务级锁住 source/target 分支行：合并期间其他提交/合并不能并发推进这两条分支的 head。
    # PostgreSQL 下 with_for_update 加行锁；SQLite 不支持行锁，退化为普通读，但整个合并仍在单事务中。
    target_branch = db.scalars(
        select(RequirementBranchModel)
        .where(RequirementBranchModel.id == mr.target_branch_id)
        .with_for_update()
    ).first()
    source_branch = db.scalars(
        select(RequirementBranchModel)
        .where(RequirementBranchModel.id == mr.source_branch_id)
        .with_for_update()
    ).first()
    if target_branch is None or source_branch is None:
        raise MergeBlockedError("merge_blocked", reasons=["target_or_source_branch_not_found"])

    # heads 校验优先于阻塞原因检查：source/target 在预览后推进应返回 409（HeadChangedError），
    # 而不是被 _check_blocking_reasons 的 source_branch_advanced 当作 400 阻塞处理。
    # 三个 head 字段必填（Pydantic 校验），此处仅校验一致性；无法解析的 ID 也视为不匹配。
    base_id, base_state, target_state, source_state = _merge_inputs(db, mr)
    current_source_head_id = source_branch.head_commit_id
    current_target_head_id = target_branch.head_commit_id
    current_base_id = base_id
    _verify_preview_heads(
        db, req,
        project_id=project_id,
        current_base_id=current_base_id,
        current_source_head_id=current_source_head_id,
        current_target_head_id=current_target_head_id,
    )

    role = _user_role_in_project(db, project_id, user_id)
    _, can_merge, reasons = _check_blocking_reasons(db, mr, role, user_id)
    if not can_merge:
        raise MergeBlockedError("merge_blocked", reasons=reasons)

    # 合并是目标分支（可能是受保护的 main）的授权写路径，这里不再校验 can_write。
    _, workspace, _ = resolve_branch_context(db, project_id, target_branch.public_id, user_id)
    if workspace is None:
        raise MergeBlockedError("merge_blocked", reasons=["target_workspace_not_found"])

    result = compute_three_way_merge(
        base_state, target_state, source_state,
        resolutions=_resolutions_dict(req),
    )
    if result["conflicts"]:
        raise MergeConflictError(
            "merge_conflicts_remaining",
            conflict_ids=[c["conflict_id"] for c in result["conflicts"]],
        )

    merged_state = result["merged_state"]
    _validate_merged_structure(db, project_id, merged_state)

    # 原子写目标工作区：先清空旧行（restore 只新增行），再恢复合并后完整模型。
    scrub_workspace(db, workspace.id)
    restore_workspace_from_state(db, workspace, merged_state)

    # 创建双父 merge commit（parent_order 0 = target head，1 = source head）。
    state_json = to_deterministic_json(merged_state)
    state_hash = compute_state_hash(state_json)
    current_head = current_target_head_id
    merge_commit = RequirementCommitModel(
        project_id=project_id,
        message=f"Merge {source_branch.name} into {target_branch.name}",
        state_json=state_json,
        state_hash=state_hash,
        schema_version=CURRENT_SCHEMA_VERSION,
        author_user_id=user_id,
        summary_json=build_commit_summary(merged_state),
    )
    db.add(merge_commit)
    db.flush()
    if current_head is not None:
        db.add(RequirementCommitParentModel(
            commit_id=merge_commit.id,
            parent_commit_id=current_head,
            parent_order=0,
        ))
    if current_source_head_id is not None:
        db.add(RequirementCommitParentModel(
            commit_id=merge_commit.id,
            parent_commit_id=current_source_head_id,
            parent_order=1,
        ))
    db.flush()

    # 目标 head compare-and-swap：条件不满足说明他人已合并/提交，返回 409 要求刷新。
    cas = db.execute(
        update(RequirementBranchModel)
        .where(
            RequirementBranchModel.id == target_branch.id,
            RequirementBranchModel.head_commit_id == current_head,
        )
        .values(head_commit_id=merge_commit.id)
    )
    if cas.rowcount != 1:
        current = db.get(RequirementCommitModel, target_branch.head_commit_id) if target_branch.head_commit_id else None
        raise HeadChangedError(
            "Target branch head changed concurrently; refresh and retry",
            current_head_commit_id=target_branch.head_commit_id,
            current_head_public_id=current.public_id if current else None,
        )
    target_branch.head_commit_id = merge_commit.id

    # 先置当前 MR 为 merged 并 flush，再同步其他 MR：sync_mrs_on_branch_commit 按活动状态
    # （open/approved/changes_requested/mergeable）查询，若当前 MR 仍为活动状态，会因自己的合并
    # 推进 target head 而把自身审批标为 stale，污染已合并 MR 的评审历史。因此必须先改状态。
    mr.status = "merged"
    mr.merged_commit_id = merge_commit.id
    db.flush()

    # 合并推进目标 head 后，同一事务内同步所有涉及目标分支的其他打开 MR：
    # 使它们的审批 stale、target head 缓存更新，避免其他 MR 因“旧审批仍 active + target 已推进”
    # 而进入不可恢复的阻塞状态。当前 MR 已为 merged，不在同步范围内。
    sync_mrs_on_branch_commit(db, project_id, target_branch.id)
    db.flush()

    # 记录冲突解决明细到审计（总体需求要求冲突解决可审计，能解释最终结果为何采用某一侧）。
    if req.resolutions:
        db.add(
            AuditLogModel(
                project_id=project_id,
                action_type="merge_request_conflict_resolution",
                summary=f"MR {mr_ref} 冲突解决 ({len(req.resolutions)} 项)",
                target_type="merge_request",
                target_id=mr.public_id,
                actor_user_id=user_id,
                actor_type="user",
                payload=_conflict_resolution_payload(req, current_source_head_id, current_target_head_id),
            )
        )
        db.flush()

    log_vc_duration(
        VC_MERGE_COMPLETED, started,
        project_id=project_id,
        mr_ref=mr_ref,
        resolution_count=len(req.resolutions or []),
        auto_merged_counts=result["auto_merged"],
        merged_commit_public_id=merge_commit.public_id,
        source_branch=source_branch.name,
        target_branch=target_branch.name,
    )

    return MergeResponse(
        status="merged",
        merged_commit_public_id=merge_commit.public_id,
        target_head_public_id=merge_commit.public_id,
    )
