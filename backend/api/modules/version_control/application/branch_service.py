"""
Branch Application Service.
负责分支的生命周期管理（创建、列表、详情、重命名、删除）与分支上下文解析。
基于 SQLAlchemy Session 提供高内聚的同步领域函数。
"""
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.modules.version_control.application.workspace_restoration import (
    copy_workspace,
    restore_workspace_from_state,
)
from backend.api.modules.version_control.schemas import (
    BranchCreateRequest,
    BranchDetailResponse,
    BranchPermissions,
    BranchSummaryResponse,
    BranchUpdateRequest,
    WorkspaceDirtySummary,
)
from backend.database.model import (
    BranchWorkspaceModel,
    ProjectMemberModel,
    ProjectModel,
    RequirementBranchModel,
    RequirementCommitModel,
)


def _can_legacy_write(db: Session, project_id: int, user_id: int | None) -> bool:
    """判断未迁移项目（无 main 分支）的过渡期写权限：owner/admin/editor 可写，reviewer/viewer 只读。

    该判断对齐版本控制引入前 require_project_role("editor") 的语义，避免绕过角色限制。
    """
    if user_id is None:
        return False
    project = db.get(ProjectModel, project_id)
    if project is not None and project.owner_user_id == user_id:
        return True
    member = db.scalars(
        select(ProjectMemberModel).where(
            ProjectMemberModel.project_id == project_id,
            ProjectMemberModel.user_id == user_id,
        )
    ).first()
    return member is not None and member.role in ("owner", "admin", "editor")


def resolve_branch_context(
    db: Session,
    project_id: int,
    branch_ref: str | None = None,
    user_id: int | None = None,
) -> tuple[RequirementBranchModel | None, BranchWorkspaceModel | None, dict[str, Any]]:
    """
    根据请求中的 branch_ref (支持 public_id, id, name) 解析对应的分支与 BranchWorkspace。
    如果未传入 branch_ref，则默认回退至 main 主分支。
    """
    branch: RequirementBranchModel | None = None
    from sqlalchemy.orm import joinedload

    if branch_ref is not None and str(branch_ref).strip() != "":
        ref_str = str(branch_ref).strip()
        # 1. 尝试按 public_id 或 name 匹配
        stmt = select(RequirementBranchModel).options(joinedload(RequirementBranchModel.head_commit)).where(
            RequirementBranchModel.project_id == project_id,
            (RequirementBranchModel.public_id == ref_str) | (RequirementBranchModel.name == ref_str)
        )
        branch = db.scalars(stmt).first()

        # 2. 如果是数字，尝试按主键 id 匹配
        if not branch and ref_str.isdigit():
            stmt = select(RequirementBranchModel).options(joinedload(RequirementBranchModel.head_commit)).where(
                RequirementBranchModel.project_id == project_id,
                RequirementBranchModel.id == int(ref_str)
            )
            branch = db.scalars(stmt).first()

        if not branch:
            raise ValueError(f"Branch '{branch_ref}' not found in project {project_id}")
    else:
        # 回退至默认 main 分支
        stmt = select(RequirementBranchModel).options(joinedload(RequirementBranchModel.head_commit)).where(
            RequirementBranchModel.project_id == project_id,
            RequirementBranchModel.name == "main",
        )
        branch = db.scalars(stmt).first()

    if not branch:
        # 尚未迁移版本控制（无 main 分支）的项目仍处于过渡期：owner/admin/editor 保持既有
        # 直接编辑能力（让无 branch 上下文的历史 CRUD 继续工作），reviewer/viewer 只读；
        # 一旦基线迁移生成 main，写入统一受 main 保护。
        return None, None, {
            "can_write": _can_legacy_write(db, project_id, user_id),
            "can_delete": False,
            "can_rename": False,
            "is_protected": False,
        }

    workspace = db.scalars(
        select(BranchWorkspaceModel).where(
            BranchWorkspaceModel.project_id == project_id,
            BranchWorkspaceModel.branch_id == branch.id,
        )
    ).first()

    if not workspace:
        raise ValueError(
            f"BranchWorkspace not found for branch '{branch.name}' (id: {branch.id}) in project {project_id}"
        )

    # 查找用户的项目角色与写/增/删权限
    is_owner_or_admin = False
    is_editor_or_above = False
    if user_id is not None:
        project = db.get(ProjectModel, project_id)
        if project and project.owner_user_id == user_id:
            is_owner_or_admin = True
            is_editor_or_above = True
        else:
            from backend.database.model import ProjectMemberModel
            member = db.scalars(
                select(ProjectMemberModel).where(
                    ProjectMemberModel.project_id == project_id,
                    ProjectMemberModel.user_id == user_id,
                )
            ).first()
            if member:
                if member.role in ("owner", "admin"):
                    is_owner_or_admin = True
                    is_editor_or_above = True
                elif member.role == "editor":
                    is_editor_or_above = True

    is_author = (user_id is not None and branch.created_by_user_id == user_id)
    is_protected_branch = bool(branch.is_protected or branch.is_default or branch.name == "main")

    if is_protected_branch:
        can_write = False
        can_delete = False
        can_rename = False
    else:
        # 可写条件必须同时满足“角色允许写（editor 及以上）”和“是作者或 admin/owner”
        can_write = is_editor_or_above and (is_owner_or_admin or is_author)
        can_delete = is_editor_or_above and (is_owner_or_admin or is_author)
        can_rename = is_editor_or_above and (is_owner_or_admin or is_author)

    permissions = {
        "can_write": can_write,
        "can_delete": can_delete,
        "can_rename": can_rename,
        "is_protected": is_protected_branch,
    }

    return branch, workspace, permissions


def compute_workspace_dirty_summary(
    db: Session,
    workspace: BranchWorkspaceModel | None,
    head_commit: RequirementCommitModel | None,
) -> WorkspaceDirtySummary:
    """比较工作区当前状态与 head commit 状态，返回是否脏及修改实体数量。

    该比较必须基于与 Commit state_json 同构的规范化状态，否则物理主键差异会误报脏数据。
    序列化失败属于真实错误，直接向上抛出让调用方感知，而不是静默返回“未修改”。
    """
    if not workspace or not head_commit or not head_commit.state_json:
        return WorkspaceDirtySummary(is_dirty=False, modified_entities_count=0)

    import json

    from backend.api.modules.version_control.application.workspace_serializer import (
        serialize_workspace,
    )
    current_state = serialize_workspace(db, workspace)
    head_state = json.loads(head_commit.state_json)
    if current_state == head_state:
        return WorkspaceDirtySummary(is_dirty=False, modified_entities_count=0)

    modified_count = 0
    if current_state.get("project_metadata") != head_state.get("project_metadata"):
        modified_count += 1
    for key in (
        "actors",
        "features",
        "feature_relations",
        "scenarios",
        "business_objects",
        "flows",
        "scopes",
    ):
        current_items = {e["logical_uuid"]: e for e in current_state.get(key, [])}
        head_items = {e["logical_uuid"]: e for e in head_state.get(key, [])}
        modified_count += len(set(current_items) - set(head_items))
        modified_count += len(set(head_items) - set(current_items))
        for entity_uuid in set(current_items) & set(head_items):
            if current_items[entity_uuid] != head_items[entity_uuid]:
                modified_count += 1
    return WorkspaceDirtySummary(is_dirty=True, modified_entities_count=modified_count)


def list_branches(
    db: Session,
    project_id: int,
    user_id: int | None = None,
) -> list[BranchSummaryResponse]:
    """列表列出项目下的所有活跃分支及其上下文数据。"""
    stmt = (
        select(RequirementBranchModel)
        .where(
            RequirementBranchModel.project_id == project_id,
            RequirementBranchModel.status == "active",
        )
        .order_by(RequirementBranchModel.is_default.desc(), RequirementBranchModel.created_at.asc())
    )
    branches = db.scalars(stmt).all()

    result: list[BranchSummaryResponse] = []
    for b in branches:
        head_commit = db.get(RequirementCommitModel, b.head_commit_id) if b.head_commit_id else None
        source_commit = db.get(RequirementCommitModel, b.source_commit_id) if b.source_commit_id else None

        _, ws, perms = resolve_branch_context(db, project_id, b.public_id, user_id)
        dirty_summary = compute_workspace_dirty_summary(db, ws, head_commit)

        result.append(
            BranchSummaryResponse(
                id=b.id,
                public_id=b.public_id,
                project_id=b.project_id,
                name=b.name,
                description=b.description,
                head_commit_id=b.head_commit_id,
                head_commit_public_id=head_commit.public_id if head_commit else None,
                source_commit_id=b.source_commit_id,
                source_commit_public_id=source_commit.public_id if source_commit else None,
                is_protected=b.is_protected or b.is_default or b.name == "main",
                is_default=b.is_default,
                status=b.status,
                created_at=b.created_at,
                updated_at=b.updated_at,
                permissions=BranchPermissions(**perms),
                workspace_dirty=dirty_summary,
            )
        )
    return result


def get_branch_detail(
    db: Session,
    project_id: int,
    branch_ref: str,
    user_id: int | None = None,
) -> BranchDetailResponse:
    """获取单个分支的详细建模信息与 BranchWorkspace 摘要。"""
    branch, workspace, permissions = resolve_branch_context(db, project_id, branch_ref, user_id)
    if not branch or not workspace:
        raise ValueError(f"Branch '{branch_ref}' not found in project {project_id}")

    head_commit = db.get(RequirementCommitModel, branch.head_commit_id) if branch.head_commit_id else None
    source_commit = db.get(RequirementCommitModel, branch.source_commit_id) if branch.source_commit_id else None
    dirty_summary = compute_workspace_dirty_summary(db, workspace, head_commit)

    return BranchDetailResponse(
        id=branch.id,
        public_id=branch.public_id,
        project_id=branch.project_id,
        name=branch.name,
        description=branch.description,
        head_commit_id=branch.head_commit_id,
        head_commit_public_id=head_commit.public_id if head_commit else None,
        source_commit_id=branch.source_commit_id,
        source_commit_public_id=source_commit.public_id if source_commit else None,
        is_protected=branch.is_protected or branch.is_default or branch.name == "main",
        is_default=branch.is_default,
        status=branch.status,
        created_at=branch.created_at,
        updated_at=branch.updated_at,
        permissions=BranchPermissions(**permissions),
        workspace_id=workspace.id,
        user_requirements=workspace.user_requirements,
        kano_status=workspace.kano_status,
        unlocked_stages=workspace.unlocked_stages,
        workspace_dirty=dirty_summary,
    )


def create_branch(
    db: Session,
    project_id: int,
    req: BranchCreateRequest,
    user_id: int | None = None,
) -> BranchDetailResponse:
    """从指定 Commit 或源分支 Head 创建新分支，并恢复全新的 BranchWorkspace 实体数据。"""
    # 0. 验证权限：创建分支至少需要 editor 角色
    if user_id is not None:
        project = db.get(ProjectModel, project_id)
        is_editor_or_above = False
        if project and project.owner_user_id == user_id:
            is_editor_or_above = True
        else:
            from backend.database.model import ProjectMemberModel
            member = db.scalars(
                select(ProjectMemberModel).where(
                    ProjectMemberModel.project_id == project_id,
                    ProjectMemberModel.user_id == user_id,
                )
            ).first()
            if member and member.role in ("owner", "admin", "editor"):
                is_editor_or_above = True
        if not is_editor_or_above:
            raise PermissionError("insufficient_project_role: Branch creation requires at least 'editor' role.")

    # 1. 检查重名
    stmt = select(RequirementBranchModel).where(
        RequirementBranchModel.project_id == project_id,
        RequirementBranchModel.name == req.name,
    )
    if db.scalars(stmt).first():
        raise ValueError(f"Branch name '{req.name}' already exists in project {project_id}")

    # 2. 寻找源 Commit 与源 Workspace
    source_commit: RequirementCommitModel | None = None
    source_workspace: BranchWorkspaceModel | None = None

    if req.source_commit_public_id:
        c_stmt = select(RequirementCommitModel).where(
            RequirementCommitModel.project_id == project_id,
            RequirementCommitModel.public_id == req.source_commit_public_id,
        )
        source_commit = db.scalars(c_stmt).first()
        if not source_commit:
            raise ValueError(f"Source commit '{req.source_commit_public_id}' not found")
    elif req.source_branch_public_id:
        b_stmt = select(RequirementBranchModel).where(
            RequirementBranchModel.project_id == project_id,
            (RequirementBranchModel.public_id == req.source_branch_public_id) | (RequirementBranchModel.name == req.source_branch_public_id)
        )
        src_branch = db.scalars(b_stmt).first()
        if not src_branch:
            raise ValueError(f"Source branch '{req.source_branch_public_id}' not found")
        source_commit = db.get(RequirementCommitModel, src_branch.head_commit_id) if src_branch.head_commit_id else None
        ws_stmt = select(BranchWorkspaceModel).where(
            BranchWorkspaceModel.project_id == project_id,
            BranchWorkspaceModel.branch_id == src_branch.id,
        )
        source_workspace = db.scalars(ws_stmt).first()
    else:
        # 默认基于 main 主分支 head
        m_stmt = select(RequirementBranchModel).where(
            RequirementBranchModel.project_id == project_id,
            RequirementBranchModel.name == "main",
        )
        main_branch = db.scalars(m_stmt).first()
        if main_branch:
            source_commit = db.get(RequirementCommitModel, main_branch.head_commit_id) if main_branch.head_commit_id else None
            ws_stmt = select(BranchWorkspaceModel).where(
                BranchWorkspaceModel.project_id == project_id,
                BranchWorkspaceModel.branch_id == main_branch.id,
            )
            source_workspace = db.scalars(ws_stmt).first()

    # 3. 创建 RequirementBranchModel 实体
    head_commit_id = source_commit.id if source_commit else None
    new_branch = RequirementBranchModel(
        project_id=project_id,
        name=req.name,
        description=req.description or "",
        head_commit_id=head_commit_id,
        source_commit_id=head_commit_id,
        is_protected=False,
        is_default=False,
        created_by_user_id=user_id,
        status="active",
    )
    db.add(new_branch)
    db.flush()

    # 4. 创建对应的 BranchWorkspaceModel 实体
    new_workspace = BranchWorkspaceModel(
        project_id=project_id,
        branch_id=new_branch.id,
        user_requirements="",
        kano_status="missing",
        unlocked_stages="",
    )
    db.add(new_workspace)
    db.flush()

    # 5. 还原或深拷贝工作区结构
    if source_commit and source_commit.state_json:
        import json
        state_dict = json.loads(source_commit.state_json)
        restore_workspace_from_state(db, new_workspace, state_dict)
    elif source_workspace:
        copy_workspace(db, source_workspace, new_workspace)

    db.flush()

    return get_branch_detail(db, project_id, new_branch.public_id, user_id)


def rename_branch(
    db: Session,
    project_id: int,
    branch_ref: str,
    req: BranchUpdateRequest,
    user_id: int | None = None,
) -> BranchDetailResponse:
    """重命名非受保护分支。"""
    branch, _workspace, permissions = resolve_branch_context(db, project_id, branch_ref, user_id)
    if not branch:
        raise ValueError(f"Branch '{branch_ref}' not found")
    if not permissions.get("can_rename", False):
        raise ValueError("Cannot rename protected main branch or branch owned by another user")

    if req.name and req.name != branch.name:
        stmt = select(RequirementBranchModel).where(
            RequirementBranchModel.project_id == project_id,
            RequirementBranchModel.name == req.name,
            RequirementBranchModel.id != branch.id,
        )
        if db.scalars(stmt).first():
            raise ValueError(f"Branch name '{req.name}' already exists in project {project_id}")
        branch.name = req.name

    if req.description is not None:
        branch.description = req.description

    db.flush()

    return get_branch_detail(db, project_id, branch.public_id, user_id)


def delete_branch(
    db: Session,
    project_id: int,
    branch_ref: str,
    user_id: int | None = None,
) -> dict[str, Any]:
    """删除非受保护分支及关联的 BranchWorkspace。"""
    branch, _workspace, permissions = resolve_branch_context(db, project_id, branch_ref, user_id)
    if not branch:
        raise ValueError(f"Branch '{branch_ref}' not found")
    if not permissions.get("can_delete", False):
        raise ValueError("Cannot delete protected or default main branch, or branch owned by another user")

    # 检查是否有未关闭/未合并的 Merge Request（覆盖 source 与 target 两侧）
    from backend.database.model import MergeRequestModel
    active_mr = db.scalars(
        select(MergeRequestModel).where(
            MergeRequestModel.status.in_(["open", "approved", "changes_requested", "mergeable"]),
            (MergeRequestModel.source_branch_id == branch.id)
            | (MergeRequestModel.target_branch_id == branch.id),
        )
    ).first()
    if active_mr:
        raise ValueError(
            f"Cannot delete branch '{branch.name}' because it is involved in active Merge Request "
            f"'{active_mr.title}' (status: {active_mr.status})"
        )

    db.delete(branch)
    db.flush()

    return {
        "status": "success",
        "message": f"Branch '{branch_ref}' deleted successfully",
        "project_id": project_id,
    }


def get_active_branch_preference(db: Session, project_id: int, user_id: int) -> str:
    """获取用户在指定项目中的当前活跃分支偏好，默认回退为 main。"""
    from backend.database.model import RequirementBranchModel, UserBranchPreferenceModel
    pref = db.execute(
        select(UserBranchPreferenceModel.branch_name).where(
            UserBranchPreferenceModel.user_id == user_id,
            UserBranchPreferenceModel.project_id == project_id,
        )
    ).scalar_one_or_none()
    if pref:
        b = db.execute(
            select(RequirementBranchModel).where(
                RequirementBranchModel.project_id == project_id,
                RequirementBranchModel.name == pref,
                RequirementBranchModel.status == "active",
            )
        ).scalar_one_or_none()
        if b:
            return pref
    return "main"


def set_active_branch_preference(db: Session, project_id: int, user_id: int, branch_name: str) -> str:
    """更新用户在指定项目中的当前活跃分支偏好。"""
    from backend.database.model import RequirementBranchModel, UserBranchPreferenceModel
    b = db.execute(
        select(RequirementBranchModel).where(
            RequirementBranchModel.project_id == project_id,
            RequirementBranchModel.name == branch_name,
            RequirementBranchModel.status == "active",
        )
    ).scalar_one_or_none()
    if not b:
        raise ValueError(f"Branch '{branch_name}' not found or inactive")

    pref = db.execute(
        select(UserBranchPreferenceModel).where(
            UserBranchPreferenceModel.user_id == user_id,
            UserBranchPreferenceModel.project_id == project_id,
        )
    ).scalar_one_or_none()
    if not pref:
        pref = UserBranchPreferenceModel(
            user_id=user_id,
            project_id=project_id,
            branch_name=branch_name,
        )
        db.add(pref)
    else:
        pref.branch_name = branch_name
    db.flush()
    return branch_name
