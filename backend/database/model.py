from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, validates


class Base(DeclarativeBase):
    pass

from zoneinfo import ZoneInfo

BEIJING_TZ = ZoneInfo("Asia/Shanghai")

def beijing_now() -> datetime:
    return datetime.now(BEIJING_TZ)

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=beijing_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=beijing_now,
        onupdate=beijing_now,
        nullable=False,
    )

class UserRole(enum.StrEnum):
    ADMIN = "admin"
    USER = "user"


class UserModel(TimestampMixin, Base):
    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint("preferred_locale IN ('zh-CN', 'en-US')", name="check_user_preferred_locale"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default=UserRole.USER.value, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    preferred_locale: Mapped[str] = mapped_column(String(16), default="zh-CN", nullable=False)

    @validates("preferred_locale")
    def validate_preferred_locale(self, key, value):
        from backend.core.locale import is_valid_locale
        if not is_valid_locale(value):
            raise ValueError(f"Invalid preferred_locale: {value}")
        return value

    # Relationships
    projects: Mapped[list[ProjectModel]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    auth_sessions: Mapped[list[AuthSessionModel]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    llm_config: Mapped[UserLLMConfigModel | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    generative_drafts: Mapped[list[GenerativeDraftModel]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    project_memberships: Mapped[list[ProjectMemberModel]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[ProjectMemberModel.user_id]",
    )


class UserLLMConfigModel(TimestampMixin, Base):
    __tablename__ = "user_llm_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    api_url: Mapped[str] = mapped_column(String(500), nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)

    user: Mapped[UserModel] = relationship(back_populates="llm_config")


class AuthSessionModel(TimestampMixin, Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[UserModel] = relationship(back_populates="auth_sessions")


class ProjectMemberRole(enum.StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class ProjectMemberStatus(enum.StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    REMOVED = "removed"


class ProjectMemberModel(TimestampMixin, Base):
    __tablename__ = "project_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(50),
        default=ProjectMemberRole.VIEWER.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=ProjectMemberStatus.ACTIVE.value,
        nullable=False,
    )
    invited_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    project: Mapped[ProjectModel] = relationship(back_populates="members")
    user: Mapped[UserModel] = relationship(
        back_populates="project_memberships",
        foreign_keys=[user_id],
    )
    invited_by: Mapped[UserModel | None] = relationship(
        foreign_keys=[invited_by_user_id],
    )

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member_user"),
    )


class ConfirmationStatus(enum.StrEnum):
    """标记对象的确认状态：AI生成、待确认、已确认"""
    AI_ASSUMPTION = "ai_assumption"
    NEEDS_CONFIRMATION = "needs_confirmation"
    CONFIRMED = "confirmed"

# 显式映射供 Alembic 和 schema 层引用
CONFIRMATION_STATUS_VALUES = [s.value for s in ConfirmationStatus]

feature_actor_table = Table(
    "feature_actor",
    Base.metadata,
    Column(
        "feature_id",
        ForeignKey("features.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "actor_id",
        ForeignKey("actors.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

flow_feature_table = Table(
    "flow_feature",
    Base.metadata,
    Column(
        "flow_id",
        ForeignKey("flows.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "feature_id",
        ForeignKey("features.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

flow_step_actor_table = Table(
    "flow_step_actor",
    Base.metadata,
    Column(
        "flow_step_id",
        ForeignKey("flow_steps.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "actor_id",
        ForeignKey("actors.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

flow_step_input_business_object_table = Table(
    "flow_step_input_business_object",
    Base.metadata,
    Column(
        "flow_step_id",
        ForeignKey("flow_steps.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "business_object_id",
        ForeignKey("business_objects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

flow_step_output_business_object_table = Table(
    "flow_step_output_business_object",
    Base.metadata,
    Column(
        "flow_step_id",
        ForeignKey("flow_steps.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "business_object_id",
        ForeignKey("business_objects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

flow_step_next_table = Table(
    "flow_step_next",
    Base.metadata,
    Column(
        "source_step_id",
        ForeignKey("flow_steps.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "target_step_id",
        ForeignKey("flow_steps.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class ProjectModel(TimestampMixin, Base):
    __tablename__ = "projects"

    __table_args__ = (
        CheckConstraint("content_locale IS NULL OR content_locale IN ('zh-CN', 'en-US')", name="check_project_content_locale"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
        index=True,
    )
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_locale: Mapped[str | None] = mapped_column(String(16), nullable=True)

    @validates("content_locale")
    def validate_content_locale(self, key, value):
        from backend.core.locale import is_valid_locale
        if value is not None and not is_valid_locale(value):
            raise ValueError(f"Invalid content_locale: {value}")
        return value

    owner: Mapped[UserModel] = relationship(back_populates="projects")
    members: Mapped[list[ProjectMemberModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    user_requirements: Mapped[str] = mapped_column(Text, default="", nullable=False)
    kano_status: Mapped[str] = mapped_column(String(50), default="missing", nullable=False)
    unlocked_stages: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    perception_slots: Mapped[list[PerceptionSlotModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

    @property
    def perception_slot(self) -> PerceptionSlotModel | None:
        return self.perception_slots[0] if self.perception_slots else None
    perception_jobs: Mapped[list[PerceptionJobModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    actors: Mapped[list[ActorModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    features: Mapped[list[FeatureModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    scenarios: Mapped[list[ScenarioModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    gherkin_specs: Mapped[list[GherkinSpecModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    prototype_previews: Mapped[list[PrototypePreviewModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    business_objects: Mapped[list[BusinessObjectModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    flows: Mapped[list[FlowModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    choice_groups: Mapped[list[ChoiceGroupModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list[AuditLogModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    preview_shadow_drafts: Mapped[list[PreviewShadowDraftModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    generative_drafts: Mapped[list[GenerativeDraftModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    issue_repair_drafts: Mapped[list[IssueRepairDraftModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    issue_overrides: Mapped[list[IssueOverrideModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    finding_overrides: Mapped[list[FindingOverrideModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    ai_add_sessions: Mapped[list[AIAddSessionModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    branches: Mapped[list[RequirementBranchModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    commits: Mapped[list[RequirementCommitModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    workspaces: Mapped[list[BranchWorkspaceModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class PerceptionSlotModel(TimestampMixin, Base):
    __tablename__ = "perception_slots"
    __table_args__ = (
        Index(
            "uq_perception_slots_workspace",
            "project_id",
            "workspace_id",
            unique=True,
            sqlite_where=text("workspace_id IS NOT NULL"),
            postgresql_where=text("workspace_id IS NOT NULL"),
        ),
        Index(
            "uq_perception_slots_legacy",
            "project_id",
            unique=True,
            sqlite_where=text("workspace_id IS NULL"),
            postgresql_where=text("workspace_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("branch_workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    perception_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped[ProjectModel] = relationship(back_populates="perception_slots")
    workspace: Mapped[BranchWorkspaceModel | None] = relationship(back_populates="perception_slots")


class PerceptionJobModel(TimestampMixin, Base):
    __tablename__ = "perception_jobs"
    __table_args__ = (
        Index(
            "uq_perception_jobs_workspace_context",
            "project_id",
            "workspace_id",
            "stage",
            "perception_kind",
            "target_type",
            "target_id",
            "context_hash",
            unique=True,
            sqlite_where=text("workspace_id IS NOT NULL"),
            postgresql_where=text("workspace_id IS NOT NULL"),
        ),
        Index(
            "uq_perception_jobs_legacy_context",
            "project_id",
            "stage",
            "perception_kind",
            "target_type",
            "target_id",
            "context_hash",
            unique=True,
            sqlite_where=text("workspace_id IS NULL"),
            postgresql_where=text("workspace_id IS NULL"),
        ),
        Index("ix_perception_jobs_project_stage", "project_id", "stage"),
        Index("ix_perception_jobs_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    perception_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(
        String(100),
        default="project",
        nullable=False,
    )
    target_id: Mapped[str] = mapped_column(
        String(255),
        default="",
        nullable=False,
    )
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    result_slot_payload: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    triggered_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("branch_workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    project: Mapped[ProjectModel] = relationship(back_populates="perception_jobs")
    workspace: Mapped[BranchWorkspaceModel | None] = relationship(back_populates="perception_jobs")


class RequirementBranchModel(TimestampMixin, Base):
    """
    项目内的需求空间分支模型。
    对应 Git 的 Branch 语义，包含逻辑名称、Head Commit 引用以及绑定的分支工作区。
    """
    __tablename__ = "requirement_branches"

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_requirement_branch_project_name"),
        Index("ix_requirement_branches_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
        index=True,
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    head_commit_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirement_commits.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_commit_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirement_commits.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_protected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    # Relationships
    project: Mapped[ProjectModel] = relationship(back_populates="branches")
    workspace: Mapped[BranchWorkspaceModel | None] = relationship(
        back_populates="branch",
        cascade="all, delete-orphan",
        uselist=False,
    )
    head_commit: Mapped[RequirementCommitModel | None] = relationship(
        foreign_keys=[head_commit_id],
    )
    source_commit: Mapped[RequirementCommitModel | None] = relationship(
        foreign_keys=[source_commit_id],
    )
    created_by: Mapped[UserModel | None] = relationship(
        foreign_keys=[created_by_user_id],
    )


class RequirementCommitModel(TimestampMixin, Base):
    """
    不可变的需求状态提交记录。
    保存完整、规范化的需求模型 JSON 快照 state_json，以及 SHA-256 state_hash 签名。
    """
    __tablename__ = "requirement_commits"
    __table_args__ = (
        Index("ix_requirement_commits_created_at", "created_at"),
        # 提交列表 SQL 分页的复合索引：按 (project_id, created_at, id) 排序。
        Index(
            "ix_requirement_commits_project_created_id",
            "project_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
        index=True,
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    state_json: Mapped[str] = mapped_column(Text, nullable=False)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    project: Mapped[ProjectModel] = relationship(back_populates="commits")
    author: Mapped[UserModel | None] = relationship(
        foreign_keys=[author_user_id],
    )
    parent_relations: Mapped[list[RequirementCommitParentModel]] = relationship(
        back_populates="commit",
        foreign_keys="[RequirementCommitParentModel.commit_id]",
        cascade="all, delete-orphan",
    )


class RequirementCommitParentModel(Base):
    """
    提交父子图关系表。
    支持 1 个父节点（普通 Commit）或 2 个父节点（Merge Commit），parent_order 标识主父/副父。
    """
    __tablename__ = "requirement_commit_parents"

    __table_args__ = (
        UniqueConstraint("commit_id", "parent_commit_id", name="uq_commit_parent"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    commit_id: Mapped[int] = mapped_column(
        ForeignKey("requirement_commits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_commit_id: Mapped[int] = mapped_column(
        ForeignKey("requirement_commits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    commit: Mapped[RequirementCommitModel] = relationship(
        foreign_keys=[commit_id],
        back_populates="parent_relations",
    )
    parent_commit: Mapped[RequirementCommitModel] = relationship(
        foreign_keys=[parent_commit_id],
    )


from sqlalchemy import event, select
from sqlalchemy.orm import Session


@event.listens_for(RequirementCommitModel, "before_update")
def prevent_commit_update(mapper, connection, target: RequirementCommitModel):
    """RequirementCommitModel 是不可变快照，禁止任何 UPDATE 操作。"""
    raise ValueError("RequirementCommitModel is immutable and cannot be updated")


@event.listens_for(RequirementBranchModel, "before_insert")
@event.listens_for(RequirementBranchModel, "before_update")
def validate_branch_model(mapper, connection, target: RequirementBranchModel):
    """验证分支引用的 head 和 source 提交属于相同项目。"""
    session = Session.object_session(target)
    if session is not None:
        if target.head_commit_id is not None:
            commit = session.get(RequirementCommitModel, target.head_commit_id)
            if commit and commit.project_id != target.project_id:
                raise ValueError("Branch head commit must belong to the same project")
        if target.source_commit_id is not None:
            commit = session.get(RequirementCommitModel, target.source_commit_id)
            if commit and commit.project_id != target.project_id:
                raise ValueError("Branch source commit must belong to the same project")


@event.listens_for(RequirementCommitParentModel, "before_insert")
@event.listens_for(RequirementCommitParentModel, "before_update")
def validate_commit_parent_model(mapper, connection, target: RequirementCommitParentModel):
    """验证提交父子关系的防环约束与跨项目约束。"""
    if target.commit_id == target.parent_commit_id:
        raise ValueError("Commit cannot have itself as a parent (self-loop)")

    session = Session.object_session(target)
    if session is not None:
        commit = session.get(RequirementCommitModel, target.commit_id)
        parent_commit = session.get(RequirementCommitModel, target.parent_commit_id)
        if commit and parent_commit and commit.project_id != parent_commit.project_id:
            raise ValueError("Parent and child commits must belong to the same project")

        visited = set()
        queue = [target.parent_commit_id]
        while queue:
            curr_id = queue.pop(0)
            if curr_id == target.commit_id:
                raise ValueError("Cycle detected in commit parent graph")
            if curr_id in visited:
                continue
            visited.add(curr_id)
            parents = session.execute(
                select(RequirementCommitParentModel.parent_commit_id).where(
                    RequirementCommitParentModel.commit_id == curr_id
                )
            ).scalars().all()
            queue.extend(parents)


class BranchWorkspaceModel(TimestampMixin, Base):
    """
    分支独立建模工作区。
    存储某分支尚未提交或最新处于编辑状态的需求空间元数据，所有正式需求实体在此约束下持久化。
    """
    __tablename__ = "branch_workspaces"
    __table_args__ = (
        Index("ix_branch_workspaces_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("requirement_branches.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    user_requirements: Mapped[str] = mapped_column(Text, default="", nullable=False)
    kano_status: Mapped[str] = mapped_column(String(50), default="missing", nullable=False)
    unlocked_stages: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    # Relationships
    project: Mapped[ProjectModel] = relationship(back_populates="workspaces")
    branch: Mapped[RequirementBranchModel] = relationship(back_populates="workspace")
    perception_slots: Mapped[list[PerceptionSlotModel]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    perception_jobs: Mapped[list[PerceptionJobModel]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
    )


class ActorModel(TimestampMixin, Base):
    __tablename__ = "actors"
    __table_args__ = (
        Index("ix_actors_project_id", "project_id"),
        UniqueConstraint("workspace_id", "logical_uuid", name="uq_actors_workspace_logical_uuid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    logical_uuid: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("branch_workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # 确认状态：ai_assumption / needs_confirmation / confirmed
    confirmation_status: Mapped[str] = mapped_column(
        String(20),
        default=ConfirmationStatus.AI_ASSUMPTION.value,
        nullable=False,
        server_default=ConfirmationStatus.AI_ASSUMPTION.value,
    )

    project: Mapped[ProjectModel] = relationship(back_populates="actors")
    features: Mapped[list[FeatureModel]] = relationship(
        secondary=feature_actor_table,
        back_populates="actors",
    )
    scenarios: Mapped[list[ScenarioModel]] = relationship(
        back_populates="actor",
        cascade="all, delete",
        passive_deletes=True,
    )
    gherkin_specs: Mapped[list[GherkinSpecModel]] = relationship(
        back_populates="actor",
        cascade="all, delete",
        passive_deletes=True,
    )
    flow_steps: Mapped[list[FlowStepModel]] = relationship(
        secondary=flow_step_actor_table,
        back_populates="actors",
    )


class FeatureRelationModel(TimestampMixin, Base):
    __tablename__ = "feature_relations"
    __table_args__ = (
        UniqueConstraint(
            "parent_feature_id",
            "position",
            name="uq_feature_relation_parent_position",
        ),
        UniqueConstraint(
            "parent_feature_id",
            "child_feature_id",
            name="uq_feature_relation_parent_child",
        ),
        Index("ix_feature_relations_parent", "parent_feature_id"),
        Index("ix_feature_relations_child", "child_feature_id"),
        UniqueConstraint("workspace_id", "logical_uuid", name="uq_feature_relations_workspace_logical_uuid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    logical_uuid: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("branch_workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    parent_feature_id: Mapped[int] = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False,
    )

    child_feature_id: Mapped[int] = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False,
    )

    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    parent: Mapped[FeatureModel] = relationship(
        "FeatureModel",
        foreign_keys=[parent_feature_id],
        back_populates="child_relations",
    )

    child: Mapped[FeatureModel] = relationship(
        "FeatureModel",
        foreign_keys=[child_feature_id],
        back_populates="parent_relation",
    )


class FeatureModel(TimestampMixin, Base):
    __tablename__ = "features"
    __table_args__ = (
        Index("ix_features_project_id", "project_id"),
        UniqueConstraint("workspace_id", "logical_uuid", name="uq_features_workspace_logical_uuid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    logical_uuid: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("branch_workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # 确认状态：ai_assumption / needs_confirmation / confirmed
    confirmation_status: Mapped[str] = mapped_column(
        String(20),
        default=ConfirmationStatus.AI_ASSUMPTION.value,
        nullable=False,
        server_default=ConfirmationStatus.AI_ASSUMPTION.value,
    )

    project: Mapped[ProjectModel] = relationship(
        back_populates="features",
        foreign_keys=[project_id],
    )

    child_relations: Mapped[list[FeatureRelationModel]] = relationship(
        "FeatureRelationModel",
        foreign_keys="FeatureRelationModel.parent_feature_id",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="FeatureRelationModel.position",
    )

    parent_relation: Mapped[FeatureRelationModel | None] = relationship(
        "FeatureRelationModel",
        foreign_keys="FeatureRelationModel.child_feature_id",
        back_populates="child",
        uselist=False,
        passive_deletes=True,
    )

    actors: Mapped[list[ActorModel]] = relationship(
        secondary=feature_actor_table,
        back_populates="features",
    )

    scenarios: Mapped[list[ScenarioModel]] = relationship(
        back_populates="feature",
        cascade="all, delete-orphan",
    )
    gherkin_specs: Mapped[list[GherkinSpecModel]] = relationship(
        back_populates="feature",
    )

    flows: Mapped[list[FlowModel]] = relationship(
        secondary=flow_feature_table,
        back_populates="features",
    )

    scope: Mapped[ScopeModel | None] = relationship(
        back_populates="feature",
        cascade="all, delete-orphan",
        uselist=False,
    )

class ScopeModel(TimestampMixin, Base):
    __tablename__ = "feature_scopes"
    __table_args__ = (
        UniqueConstraint("workspace_id", "logical_uuid", name="uq_feature_scopes_workspace_logical_uuid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    logical_uuid: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("branch_workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    feature_id: Mapped[int] = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(String(50), nullable=False)

    positive_picture: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )

    negative_picture: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )

    positive_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    negative_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    kano_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    kano_category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 确认状态：ai_assumption / needs_confirmation / confirmed（与 scope.status 范围决策正交）
    confirmation_status: Mapped[str] = mapped_column(
        String(20),
        default=ConfirmationStatus.AI_ASSUMPTION.value,
        nullable=False,
        server_default=ConfirmationStatus.AI_ASSUMPTION.value,
    )

    feature: Mapped[FeatureModel] = relationship(
        back_populates="scope",
    )

class ScenarioAcceptanceCriterionModel(TimestampMixin, Base):
    __tablename__ = "scenario_acceptance_criteria"
    __table_args__ = (
        UniqueConstraint(
            "scenario_id",
            "position",
            name="uq_scenario_acceptance_position",
        ),
        UniqueConstraint("workspace_id", "logical_uuid", name="uq_scenario_ac_workspace_logical_uuid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    logical_uuid: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("branch_workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 确认状态：ai_assumption / needs_confirmation / confirmed
    confirmation_status: Mapped[str] = mapped_column(
        String(20),
        default=ConfirmationStatus.AI_ASSUMPTION.value,
        nullable=False,
        server_default=ConfirmationStatus.AI_ASSUMPTION.value,
    )

    scenario: Mapped[ScenarioModel] = relationship(
        back_populates="acceptance_criteria",
    )


class GherkinSpecModel(TimestampMixin, Base):
    __tablename__ = "gherkin_specs"
    __table_args__ = (
        Index("ix_gherkin_specs_project_id", "project_id"),
        Index("ix_gherkin_specs_feature_id", "feature_id"),
        Index("ix_gherkin_specs_actor_id", "actor_id"),
        Index(
            "ix_gherkin_specs_project_feature_actor",
            "project_id",
            "feature_id",
            "actor_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    feature_id: Mapped[int] = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[int] = mapped_column(
        ForeignKey("actors.id", ondelete="CASCADE"),
        nullable=False,
    )
    gherkin_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(
        String(50),
        default="scenario_generation_skill",
        nullable=False,
    )

    project: Mapped[ProjectModel] = relationship(back_populates="gherkin_specs")
    feature: Mapped[FeatureModel] = relationship(back_populates="gherkin_specs")
    actor: Mapped[ActorModel] = relationship(back_populates="gherkin_specs")
    scenarios: Mapped[list[ScenarioModel]] = relationship(
        back_populates="gherkin_spec",
    )


class PrototypePreviewModel(TimestampMixin, Base):
    __tablename__ = "prototype_previews"
    __table_args__ = (
        Index("ix_prototype_previews_project_id", "project_id"),
        Index("ix_prototype_previews_project_created", "project_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="ready",
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(50),
        default="placeholder",
        nullable=False,
    )
    html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    javascript: Mapped[str] = mapped_column(Text, default="", nullable=False)
    css: Mapped[str] = mapped_column(Text, default="", nullable=False)
    pages: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    input_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    gherkin_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped[ProjectModel] = relationship(
        back_populates="prototype_previews",
    )


class ScenarioModel(TimestampMixin, Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        Index("ix_scenarios_project_id", "project_id"),
        Index("ix_scenarios_feature_id", "feature_id"),
        Index("ix_scenarios_actor_id", "actor_id"),
        Index("ix_scenarios_gherkin_spec_id", "gherkin_spec_id"),
        UniqueConstraint("workspace_id", "logical_uuid", name="uq_scenarios_workspace_logical_uuid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    logical_uuid: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("branch_workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    feature_id: Mapped[int] = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[int] = mapped_column(
        ForeignKey("actors.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    gherkin_spec_id: Mapped[int | None] = mapped_column(
        ForeignKey("gherkin_specs.id", ondelete="SET NULL"),
        nullable=True,
    )
    gherkin_scenario_index: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    # 确认状态：ai_assumption / needs_confirmation / confirmed
    confirmation_status: Mapped[str] = mapped_column(
        String(20),
        default=ConfirmationStatus.AI_ASSUMPTION.value,
        nullable=False,
        server_default=ConfirmationStatus.AI_ASSUMPTION.value,
    )

    project: Mapped[ProjectModel] = relationship(back_populates="scenarios")
    feature: Mapped[FeatureModel] = relationship(back_populates="scenarios")
    actor: Mapped[ActorModel] = relationship(back_populates="scenarios")
    gherkin_spec: Mapped[GherkinSpecModel | None] = relationship(
        back_populates="scenarios",
    )
    acceptance_criteria: Mapped[list[ScenarioAcceptanceCriterionModel]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="ScenarioAcceptanceCriterionModel.position",
    )


class BusinessObjectModel(TimestampMixin, Base):
    __tablename__ = "business_objects"
    __table_args__ = (
        Index("ix_business_objects_project_id", "project_id"),
        UniqueConstraint("workspace_id", "logical_uuid", name="uq_business_objects_workspace_logical_uuid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    logical_uuid: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("branch_workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # 确认状态：ai_assumption / needs_confirmation / confirmed
    confirmation_status: Mapped[str] = mapped_column(
        String(20),
        default=ConfirmationStatus.AI_ASSUMPTION.value,
        nullable=False,
        server_default=ConfirmationStatus.AI_ASSUMPTION.value,
    )

    project: Mapped[ProjectModel] = relationship(back_populates="business_objects")
    attributes: Mapped[list[BusinessObjectAttributeModel]] = relationship(
        back_populates="business_object",
        cascade="all, delete-orphan",
    )
    input_flow_steps: Mapped[list[FlowStepModel]] = relationship(
        secondary=flow_step_input_business_object_table,
        back_populates="input_business_objects",
    )
    output_flow_steps: Mapped[list[FlowStepModel]] = relationship(
        secondary=flow_step_output_business_object_table,
        back_populates="output_business_objects",
    )


class BusinessObjectAttributeModel(TimestampMixin, Base):
    __tablename__ = "business_object_attributes"
    __table_args__ = (
        Index("ix_business_object_attributes_object_id", "business_object_id"),
        UniqueConstraint("workspace_id", "logical_uuid", name="uq_bo_attributes_workspace_logical_uuid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    logical_uuid: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("branch_workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    business_object_id: Mapped[int] = mapped_column(
        ForeignKey("business_objects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    data_type: Mapped[str] = mapped_column(String(100), nullable=False)
    example: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # 确认状态：ai_assumption / needs_confirmation / confirmed
    confirmation_status: Mapped[str] = mapped_column(
        String(20),
        default=ConfirmationStatus.AI_ASSUMPTION.value,
        nullable=False,
        server_default=ConfirmationStatus.AI_ASSUMPTION.value,
    )

    business_object: Mapped[BusinessObjectModel] = relationship(back_populates="attributes")


class FlowModel(TimestampMixin, Base):
    __tablename__ = "flows"
    __table_args__ = (
        Index("ix_flows_project_id", "project_id"),
        UniqueConstraint("workspace_id", "logical_uuid", name="uq_flows_workspace_logical_uuid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    logical_uuid: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("branch_workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # 确认状态：ai_assumption / needs_confirmation / confirmed
    confirmation_status: Mapped[str] = mapped_column(
        String(20),
        default=ConfirmationStatus.AI_ASSUMPTION.value,
        nullable=False,
        server_default=ConfirmationStatus.AI_ASSUMPTION.value,
    )

    project: Mapped[ProjectModel] = relationship(back_populates="flows")
    features: Mapped[list[FeatureModel]] = relationship(
        secondary=flow_feature_table,
        back_populates="flows",
    )
    steps: Mapped[list[FlowStepModel]] = relationship(
        back_populates="flow",
        cascade="all, delete-orphan",
        order_by="FlowStepModel.position",
    )


class FlowStepModel(TimestampMixin, Base):
    __tablename__ = "flow_steps"
    __table_args__ = (
        Index("ix_flow_steps_flow_id", "flow_id"),
        UniqueConstraint("flow_id", "position", name="uq_flow_step_position"),
        UniqueConstraint("workspace_id", "logical_uuid", name="uq_flow_steps_workspace_logical_uuid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    logical_uuid: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("branch_workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    flow_id: Mapped[int] = mapped_column(
        ForeignKey("flows.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # 确认状态：ai_assumption / needs_confirmation / confirmed
    confirmation_status: Mapped[str] = mapped_column(
        String(20),
        default=ConfirmationStatus.AI_ASSUMPTION.value,
        nullable=False,
        server_default=ConfirmationStatus.AI_ASSUMPTION.value,
    )

    flow: Mapped[FlowModel] = relationship(back_populates="steps")
    actors: Mapped[list[ActorModel]] = relationship(
        secondary=flow_step_actor_table,
        back_populates="flow_steps",
    )
    input_business_objects: Mapped[list[BusinessObjectModel]] = relationship(
        secondary=flow_step_input_business_object_table,
        back_populates="input_flow_steps",
    )
    output_business_objects: Mapped[list[BusinessObjectModel]] = relationship(
        secondary=flow_step_output_business_object_table,
        back_populates="output_flow_steps",
    )
    next_steps: Mapped[list[FlowStepModel]] = relationship(
        "FlowStepModel",
        secondary=flow_step_next_table,
        primaryjoin=lambda: FlowStepModel.id == flow_step_next_table.c.source_step_id,
        secondaryjoin=lambda: FlowStepModel.id == flow_step_next_table.c.target_step_id,
        back_populates="previous_steps",
    )
    previous_steps: Mapped[list[FlowStepModel]] = relationship(
        "FlowStepModel",
        secondary=flow_step_next_table,
        primaryjoin=lambda: FlowStepModel.id == flow_step_next_table.c.target_step_id,
        secondaryjoin=lambda: FlowStepModel.id == flow_step_next_table.c.source_step_id,
        back_populates="next_steps",
    )


class ChoiceGroupModel(TimestampMixin, Base):
    __tablename__ = "choice_groups"
    __table_args__ = (
        UniqueConstraint("workspace_id", "logical_uuid", name="uq_choice_groups_workspace_logical_uuid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    logical_uuid: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("branch_workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slot_id: Mapped[int | None] = mapped_column(
        ForeignKey("perception_slots.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    selection_mode: Mapped[str] = mapped_column(String(50), default="single", nullable=False)

    # P3: issue repair source tracking
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    source_id: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    issue_code: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    issue_id: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    stage: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)
    target: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    context_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)

    # Phase 1: choice group 扩展，支持 AI 生成任务的元信息
    generation_type: Mapped[str | None] = mapped_column(
        String(80), nullable=True, default=None,
        comment="候选生成类型: actor, scenario, feature, project_creation 等"
    )
    origin_endpoint: Mapped[str | None] = mapped_column(
        String(200), nullable=True, default=None,
        comment="触发此 choice group 的 API endpoint"
    )
    candidate_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None,
        comment="请求的候选总数"
    )
    success_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None,
        comment="成功生成的候选数"
    )
    failure_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None,
        comment="失败的候选数"
    )
    status_detail: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None,
        comment="扩展状态信息: 错误汇总、候选失败详情、跨候选差异摘要等"
    )

    project: Mapped[ProjectModel] = relationship(back_populates="choice_groups")
    choices: Mapped[list[ChoiceModel]] = relationship(
        back_populates="choice_group",
        cascade="all, delete-orphan",
    )


class ChoiceModel(TimestampMixin, Base):
    __tablename__ = "choices"
    __table_args__ = (
        UniqueConstraint("workspace_id", "logical_uuid", name="uq_choices_workspace_logical_uuid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    logical_uuid: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("branch_workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    choice_group_id: Mapped[int] = mapped_column(
        ForeignKey("choice_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="candidate", nullable=False)
    patch: Mapped[dict] = mapped_column(JSON, nullable=False)
    impact_preview: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Phase 1: generation choice 扩展字段
    payload: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None,
        comment="候选草稿的完整 payload（非 patch 型生成结果）"
    )
    draft_type: Mapped[str | None] = mapped_column(
        String(80), nullable=True, default=None,
        comment="候选类型: actor, scenario, feature, project_creation 等"
    )
    apply_mode: Mapped[str] = mapped_column(
        String(50), default="patch", nullable=False,
        comment="采纳模式: patch 沿用 issue repair, draft_payload 用 payload 写入"
    )
    preview: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None,
        comment="前端展示用摘要，避免 UI 直接理解所有 payload 细节"
    )
    score: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None,
        comment="模型自评: completeness, risk, novelty, fit 等"
    )
    validation_report: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None,
        comment="采纳前校验结果"
    )
    error: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None,
        comment="候选生成失败时的错误信息。失败候选可保留 error 但 status 为 failed"
    )

    strategy_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default=None,
        comment="生成此候选所使用的策略 ID 快照"
    )
    strategy_label: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default=None,
        comment="生成此候选所使用的策略 Label 快照"
    )

    choice_group: Mapped[ChoiceGroupModel] = relationship(back_populates="choices")


class AuditLogModel(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("idx_audit_project_created", "project_id", "created_at"),
        Index("idx_audit_actor_created", "actor_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_type: Mapped[str] = mapped_column(
        String(50),
        default="system",
        nullable=False,
        server_default="system",
    )
    diff: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    project: Mapped[ProjectModel] = relationship(back_populates="audit_logs")
    actor_user: Mapped[UserModel | None] = relationship()


class PreviewShadowDraftModel(TimestampMixin, Base):
    __tablename__ = "preview_shadow_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    draft_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="generating", nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="shadow_project", nullable=False)

    base_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    shadow_snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    base_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    shadow_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    patch_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    prototype_preview_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[ProjectModel] = relationship(back_populates="preview_shadow_drafts")


class GenerativeDraftModel(TimestampMixin, Base):
    __tablename__ = "generative_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    draft_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    draft_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    project: Mapped[ProjectModel | None] = relationship(back_populates="generative_drafts")
    owner: Mapped[UserModel] = relationship(back_populates="generative_drafts")


class IssueRepairDraftModel(TimestampMixin, Base):
    """AI-generated repair draft for a specific issue.

    Created when an issue is resolved via AI, and confirmed/discarded
    by the user. Stale detection is based on context_hash.
    """

    __tablename__ = "issue_repair_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draft_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    issue_code: Mapped[str] = mapped_column(String(100), nullable=False)
    issue_id: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    stage: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    target: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    issue_fingerprint: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    repair_type: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    proposal: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    patch: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_report: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    project: Mapped[ProjectModel] = relationship(back_populates="issue_repair_drafts")


class IssueOverrideModel(TimestampMixin, Base):
    __tablename__ = "issue_overrides"
    __table_args__ = (
        UniqueConstraint("project_id", "issue_id", name="uq_issue_override_project_issue"),
        Index("ix_issue_overrides_project_status", "project_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    issue_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ignored")

    project: Mapped[ProjectModel] = relationship(back_populates="issue_overrides")


class FindingOverrideModel(TimestampMixin, Base):
    __tablename__ = "finding_overrides"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "workspace_id",
            "finding_id",
            name="uq_finding_override_project_workspace_finding",
        ),
        Index(
            "ix_finding_overrides_project_type_status",
            "project_id",
            "finding_type",
            "status",
        ),
        Index(
            "ix_finding_overrides_project_status",
            "project_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("branch_workspaces.id", ondelete="CASCADE"),
        nullable=True,
    )
    finding_id: Mapped[str] = mapped_column(String(255), nullable=False)
    finding_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    context_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    project: Mapped[ProjectModel] = relationship(back_populates="finding_overrides")


class UserBranchPreferenceModel(TimestampMixin, Base):
    __tablename__ = "user_branch_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_user_project_branch_preference"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    branch_name: Mapped[str] = mapped_column(String(100), nullable=False)



class AIAddSessionModel(TimestampMixin, Base):
    __tablename__ = "ai_add_sessions"
    __table_args__ = (
        Index("ix_ai_add_sessions_project_id", "project_id"),
        Index("ix_ai_add_sessions_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    anchor_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    summary_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ready_to_generate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[ProjectModel] = relationship(back_populates="ai_add_sessions")
    messages: Mapped[list[AIAddMessageModel]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class AIAddMessageModel(TimestampMixin, Base):
    __tablename__ = "ai_add_messages"
    __table_args__ = (
        Index("ix_ai_add_messages_session_id", "session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("ai_add_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    extra: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    session: Mapped[AIAddSessionModel] = relationship(back_populates="messages")


class CollaborationTaskModel(TimestampMixin, Base):
    __tablename__ = "collaboration_tasks"
    __table_args__ = (
        Index("idx_collab_proj_status", "project_id", "status"),
        Index("idx_collab_assignee_status", "assigned_to_user_id", "status"),
        Index("idx_collab_creator_status", "created_by_user_id", "status"),
        Index("idx_collab_target", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)  # confirm_node
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    targets: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # open, done, rejected, cancelled, superseded
    priority: Mapped[str] = mapped_column(String(50), default="normal", server_default="normal", nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_to_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_snapshot: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[ProjectModel] = relationship(foreign_keys=[project_id])
    creator: Mapped[UserModel] = relationship(foreign_keys=[created_by_user_id])
    assignee: Mapped[UserModel] = relationship(foreign_keys=[assigned_to_user_id])


class ProjectLLMConfigModel(TimestampMixin, Base):
    __tablename__ = "project_llm_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    api_url: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    updated_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    project: Mapped[ProjectModel] = relationship(foreign_keys=[project_id])


class NotificationModel(TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_notification_recipient", "recipient_user_id"),
        Index("idx_notification_unread", "recipient_user_id", "read_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("collaboration_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    recipient: Mapped[UserModel] = relationship(foreign_keys=[recipient_user_id])
    project: Mapped[ProjectModel] = relationship(foreign_keys=[project_id])
    task: Mapped[CollaborationTaskModel | None] = relationship(foreign_keys=[task_id])


class TaskCommentModel(TimestampMixin, Base):
    __tablename__ = "task_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("collaboration_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    task: Mapped[CollaborationTaskModel] = relationship(foreign_keys=[task_id])
    author: Mapped[UserModel] = relationship(foreign_keys=[author_user_id])


class TaskAssigneeModel(TimestampMixin, Base):
    __tablename__ = "task_assignees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("collaboration_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assignee_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task: Mapped[CollaborationTaskModel] = relationship(foreign_keys=[task_id])
    assignee: Mapped[UserModel] = relationship(foreign_keys=[assignee_user_id])


class KnowledgeWorkspaceModel(TimestampMixin, Base):
    __tablename__ = "knowledge_workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
        index=True,
    )
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scope: Mapped[str] = mapped_column(String(50), default="project_creation", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # active, attached, expired

    owner: Mapped[UserModel] = relationship(foreign_keys=[owner_user_id])
    project: Mapped[ProjectModel | None] = relationship(foreign_keys=[project_id])


class KnowledgeDocumentModel(TimestampMixin, Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    markdown_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)  # uploaded, converting, ready, failed, deleted
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    workspace: Mapped[KnowledgeWorkspaceModel | None] = relationship(foreign_keys=[workspace_id])
    project: Mapped[ProjectModel | None] = relationship(foreign_keys=[project_id])
    owner: Mapped[UserModel] = relationship(foreign_keys=[owner_user_id])


class KnowledgeChunkModel(TimestampMixin, Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    document: Mapped[KnowledgeDocumentModel] = relationship(foreign_keys=[document_id])
    project: Mapped[ProjectModel | None] = relationship(foreign_keys=[project_id])
    workspace: Mapped[KnowledgeWorkspaceModel | None] = relationship(foreign_keys=[workspace_id])


class ProjectGenerationStrategyConfigModel(TimestampMixin, Base):
    __tablename__ = "project_generation_strategy_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    knowledge_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    strategies: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    project: Mapped[ProjectModel] = relationship(foreign_keys=[project_id])
    updated_by: Mapped[UserModel | None] = relationship(foreign_keys=[updated_by_user_id])


from sqlalchemy import event, text

# ============================================================
# Merge Request Models (Phase 5)
# ============================================================

class MergeRequestModel(TimestampMixin, Base):
    """将来源分支变更审阅并合入目标分支的协作对象。

    source 新提交或 target 推进后需撤销已有审批（stale_reviews），但历史评论保留。
    """
    __tablename__ = "merge_requests"
    __table_args__ = (
        UniqueConstraint("project_id", "title", name="uq_merge_request_project_title"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
        index=True,
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_branch_id: Mapped[int] = mapped_column(
        ForeignKey("requirement_branches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_branch_id: Mapped[int] = mapped_column(
        ForeignKey("requirement_branches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        default="open",
        nullable=False,
    )
    merge_base_commit_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirement_commits.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_head_commit_id: Mapped[int] = mapped_column(
        ForeignKey("requirement_commits.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_head_commit_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirement_commits.id", ondelete="SET NULL"),
        nullable=True,
    )
    author_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    merged_commit_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirement_commits.id", ondelete="SET NULL"),
        nullable=True,
    )
    closed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    project: Mapped[ProjectModel] = relationship(foreign_keys=[project_id])
    source_branch: Mapped[RequirementBranchModel] = relationship(foreign_keys=[source_branch_id])
    target_branch: Mapped[RequirementBranchModel] = relationship(foreign_keys=[target_branch_id])
    merge_base: Mapped[RequirementCommitModel | None] = relationship(foreign_keys=[merge_base_commit_id])
    source_head: Mapped[RequirementCommitModel | None] = relationship(foreign_keys=[source_head_commit_id])
    target_head: Mapped[RequirementCommitModel | None] = relationship(foreign_keys=[target_head_commit_id])
    author: Mapped[UserModel | None] = relationship(foreign_keys=[author_user_id])
    merged_commit: Mapped[RequirementCommitModel | None] = relationship(foreign_keys=[merged_commit_id])
    closed_by: Mapped[UserModel | None] = relationship(foreign_keys=[closed_by_user_id])
    reviews: Mapped[list[MergeReviewModel]] = relationship(
        back_populates="merge_request",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list[MergeCommentModel]] = relationship(
        back_populates="merge_request",
        cascade="all, delete-orphan",
    )

    def _validate_mr(self) -> None:
        if self.source_branch_id == self.target_branch_id:
            raise ValueError("Merge Request source and target branches must be different")


@event.listens_for(MergeRequestModel, "before_insert")
@event.listens_for(MergeRequestModel, "before_update")
def validate_merge_request_branches(mapper, connection, target: MergeRequestModel) -> None:
    target._validate_mr()


class MergeReviewModel(TimestampMixin, Base):
    """审批记录：approve / request changes / comment only。

    审批人不能是 MR 作者；每次 source 新提交或 target 推进后标记 stale。
    """
    __tablename__ = "merge_reviews"
    __table_args__ = (
        UniqueConstraint(
            "merge_request_id", "reviewer_user_id",
            name="uq_merge_review_reviewer",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    merge_request_id: Mapped[int] = mapped_column(
        ForeignKey("merge_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    decision: Mapped[str] = mapped_column(
        String(30),
        default="approved",
        nullable=False,
    )  # "approved" | "changes_requested"
    comment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
    )  # "active" | "stale"
    stale_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stale_source_head_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirement_commits.id", ondelete="CASCADE"),
        nullable=True,
    )
    stale_target_head_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirement_commits.id", ondelete="CASCADE"),
        nullable=True,
    )

    merge_request: Mapped[MergeRequestModel] = relationship(back_populates="reviews")
    reviewer: Mapped[UserModel | None] = relationship(foreign_keys=[reviewer_user_id])
    stale_source_head: Mapped[RequirementCommitModel | None] = relationship(foreign_keys=[stale_source_head_id])
    stale_target_head: Mapped[RequirementCommitModel | None] = relationship(foreign_keys=[stale_target_head_id])


class MergeCommentModel(TimestampMixin, Base):
    """行内评论，锚定到 entity_uuid、字段路径或关系键。

    来源新提交后标记 expired 但不删除历史评论。
    """
    __tablename__ = "merge_comments"
    __table_args__ = ()

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    merge_request_id: Mapped[int] = mapped_column(
        ForeignKey("merge_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    entity_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    field_path: Mapped[str | None] = mapped_column(String(200), nullable=True)
    relation_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
    )
    effective_source_head_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirement_commits.id", ondelete="SET NULL"),
        nullable=True,
    )
    expired_by_source_head_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirement_commits.id", ondelete="SET NULL"),
        nullable=True,
    )

    merge_request: Mapped[MergeRequestModel] = relationship(back_populates="comments")
    author: Mapped[UserModel | None] = relationship(foreign_keys=[author_user_id])

@event.listens_for(ProjectModel, 'after_insert')
def auto_create_project_owner_member(mapper, connection, target):
    res = connection.execute(
        text("SELECT 1 FROM project_members WHERE project_id = :project_id AND user_id = :user_id"),
        {"project_id": target.id, "user_id": target.owner_user_id}
    )
    if not res.fetchone():
        now = beijing_now()
        connection.execute(
            text(
                "INSERT INTO project_members (project_id, user_id, role, status, joined_at, created_at, updated_at) "
                "VALUES (:project_id, :user_id, 'owner', 'active', :joined_at, :created_at, :updated_at)"
            ),
            {
                "project_id": target.id,
                "user_id": target.owner_user_id,
                "joined_at": target.created_at or now,
                "created_at": target.created_at or now,
                "updated_at": target.updated_at or now,
            }
        )
