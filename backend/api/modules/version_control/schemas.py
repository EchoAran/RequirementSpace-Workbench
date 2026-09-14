"""
Version Control HTTP API Schemas.
定义分支管理与工作区状态的 HTTP 请求与响应 Schema 结构。
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class BranchPermissions(BaseModel):
    can_write: bool = Field(default=True)
    can_delete: bool = Field(default=False)
    can_rename: bool = Field(default=False)
    is_protected: bool = Field(default=False)


class WorkspaceDirtySummary(BaseModel):
    is_dirty: bool = Field(default=False)
    modified_entities_count: int = Field(default=0)


class BranchSummaryResponse(BaseModel):
    id: int
    public_id: str
    project_id: int
    name: str
    description: str | None = None
    head_commit_id: int | None = None
    head_commit_public_id: str | None = None
    source_commit_id: int | None = None
    source_commit_public_id: str | None = None
    is_protected: bool = False
    is_default: bool = False
    status: str = "active"
    created_at: datetime
    updated_at: datetime
    permissions: BranchPermissions | None = None
    workspace_dirty: WorkspaceDirtySummary | None = None


class BranchDetailResponse(BranchSummaryResponse):
    workspace_id: int | None = None
    user_requirements: str = ""
    kano_status: str = "missing"
    unlocked_stages: str = ""


class BranchCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    source_commit_public_id: str | None = None
    source_branch_public_id: str | None = None


class BranchUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


# ==========================================
# Commit Contracts
# ==========================================

class CommitCreateRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    expected_head_commit_id: int | None = None
    expected_head_commit_public_id: str | None = None

    @model_validator(mode="after")
    def _require_expected_head(self) -> "CommitCreateRequest":
        # 总体需求要求每次提交必须携带预期 head，让客户端在提交前显式参与并发控制
        # （head compare-and-swap）。恰好提供一个引用；缺失时由 Pydantic 校验层返回 422。
        provided = [
            name
            for name in ("expected_head_commit_id", "expected_head_commit_public_id")
            if getattr(self, name) is not None
        ]
        if len(provided) != 1:
            raise ValueError(
                "expected_head_commit_required: provide exactly one of "
                "expected_head_commit_id or expected_head_commit_public_id"
            )
        return self


class CommitRevertRequest(BaseModel):
    branch_ref: str | None = None
    message: str | None = None


class CommitSummaryResponse(BaseModel):
    id: int
    public_id: str
    short_id: str
    message: str
    state_hash: str
    schema_version: str = "2.0"
    summary: dict[str, Any] | None = None
    author_user_id: int | None = None
    author_email: str | None = None
    created_at: datetime
    parent_ids: list[int] = Field(default_factory=list)
    parent_public_ids: list[str] = Field(default_factory=list)
    is_merge: bool = False
    branch_public_ids: list[str] = Field(default_factory=list)
    branch_names: list[str] = Field(default_factory=list)


class CommitDetailResponse(CommitSummaryResponse):
    # 历史只读视图：由 Commit state_json 重建的规范化需求模型，不读取当前分支表。
    state: dict[str, Any] | None = None


class CommitListResponse(BaseModel):
    commits: list[CommitSummaryResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


# ==========================================
# Semantic Diff Contracts
# ==========================================

class DiffRefInfo(BaseModel):
    kind: str = "commit"  # commit | branch | workspace
    label: str = ""
    public_id: str | None = None
    branch_ref: str | None = None
    branch_name: str | None = None
    branch_is_protected: bool = False


class TextDiffBlock(BaseModel):
    kind: str = "replace"  # replace | add | remove
    before_lines: list[str] = Field(default_factory=list)
    after_lines: list[str] = Field(default_factory=list)


class DiffEntry(BaseModel):
    change_type: str  # entity_added|entity_removed|entity_updated|field_changed|relation_added|relation_removed|ordered_item_moved
    entity_type: str
    entity_uuid: str
    entity_name: str = ""
    parent_uuid: str | None = None
    parent_type: str | None = None
    path: str = ""
    field: str | None = None
    before: Any = None
    after: Any = None
    text_blocks: list[TextDiffBlock] = Field(default_factory=list)
    relation_type: str | None = None
    related_entity_type: str | None = None
    related_entity_uuid: str | None = None
    related_entity_name: str | None = None
    before_position: int | None = None
    after_position: int | None = None


class DiffTypeSummary(BaseModel):
    added: int = 0
    removed: int = 0
    modified: int = 0


class DiffSummary(BaseModel):
    by_type: dict[str, DiffTypeSummary] = Field(default_factory=dict)
    total_added: int = 0
    total_removed: int = 0
    total_modified: int = 0


class DiffResult(BaseModel):
    base: DiffRefInfo | None = None
    target: DiffRefInfo | None = None
    summary: DiffSummary
    entries: list[DiffEntry] = Field(default_factory=list)
    total: int = 0
    limit: int = 0
    offset: int = 0


class EntityDiffResponse(BaseModel):
    base: DiffRefInfo | None = None
    target: DiffRefInfo | None = None
    entity_uuid: str
    entity_type: str = ""
    entity_name: str = ""
    base_value: dict[str, Any] | None = None
    target_value: dict[str, Any] | None = None
    entries: list[DiffEntry] = Field(default_factory=list)


# ==========================================
# Merge Request Contracts
# ==========================================

_MR_STATUSES = frozenset(
    {"open", "approved", "changes_requested", "mergeable", "merged", "closed"}
)
_REVIEW_DECISIONS = frozenset({"approved", "changes_requested"})


class MergeReviewResponse(BaseModel):
    id: int
    reviewer_user_id: int | None = None
    reviewer_email: str | None = None
    decision: str = "approved"
    comment: str = ""
    status: str = "active"  # "active" | "stale"
    stale_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class MergeCommentResponse(BaseModel):
    id: int
    author_user_id: int | None = None
    author_email: str | None = None
    entity_uuid: str | None = None
    field_path: str | None = None
    relation_key: str | None = None
    comment: str
    required: bool = False
    status: str = "active"
    effective_source_head_id: int | None = None
    expired_by_source_head_id: int | None = None
    created_at: datetime


class MRDiffSummary(BaseModel):
    by_type: dict[str, DiffTypeSummary] = Field(default_factory=dict)
    total_added: int = 0
    total_removed: int = 0
    total_modified: int = 0


class MergeRequestSummaryResponse(BaseModel):
    id: int
    public_id: str
    project_id: int
    title: str
    description: str | None = None
    source_branch_name: str = ""
    target_branch_name: str = ""
    source_branch_public_id: str | None = None
    target_branch_public_id: str | None = None
    status: str = "open"
    author_user_id: int | None = None
    author_email: str | None = None
    diff_summary: MRDiffSummary | None = None
    active_review_count: int = 0
    total_comments: int = 0
    source_head_short: str | None = None
    target_head_short: str | None = None
    created_at: datetime
    updated_at: datetime


class MergeRequestDetailResponse(MergeRequestSummaryResponse):
    source_head_commit_id: int | None = None
    source_head_public_id: str | None = None
    target_head_commit_id: int | None = None
    target_head_public_id: str | None = None
    merge_base_commit_id: int | None = None
    merge_base_public_id: str | None = None
    merged_commit_id: int | None = None
    merged_commit_public_id: str | None = None
    reviews: list[MergeReviewResponse] = Field(default_factory=list)
    comments: list[MergeCommentResponse] = Field(default_factory=list)
    can_approve: bool = False
    can_merge: bool = False
    blocking_reasons: list[str] = Field(default_factory=list)


class MergeRequestPreviewRequest(BaseModel):
    source_branch_public_id: str
    target_branch_public_id: str


class MergeRequestPreviewResponse(BaseModel):
    merge_base_public_id: str | None = None
    source_head_public_id: str | None = None
    target_head_public_id: str | None = None
    diff_summary: MRDiffSummary = MRDiffSummary()


class MergeRequestCreateRequest(BaseModel):
    source_branch_id: int | None = None
    source_branch_name: str | None = None
    source_branch_public_id: str | None = None
    target_branch_id: int | None = None
    target_branch_name: str | None = None
    target_branch_public_id: str | None = None
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _require_identifiers(self) -> "MergeRequestCreateRequest":
        src = self.source_branch_id or self.source_branch_name or self.source_branch_public_id
        tgt = self.target_branch_id or self.target_branch_name or self.target_branch_public_id
        if not src:
            raise ValueError("source_branch_required")
        if not tgt:
            raise ValueError("target_branch_required")
        return self


class MergeReviewRequest(BaseModel):
    decision: str = "approved"
    comment: str | None = Field(default=None, max_length=2000)


class MergeCommentCreateRequest(BaseModel):
    entity_uuid: str | None = None
    field_path: str | None = None
    relation_key: str | None = None
    comment: str = Field(min_length=1, max_length=2000)
    required: bool = False


class MergeRequestListResponse(BaseModel):
    items: list[MergeRequestSummaryResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


# ==========================================
# Phase 6: Three-Way Merge & Conflict Resolution Contracts
# ==========================================

class ConflictItemResponse(BaseModel):
    """单个冲突项：携带 base/target/source 三侧值供解决界面展示与选择。"""
    conflict_id: str
    conflict_type: str  # same_field_different_value|delete_vs_modify|opposite_relation_ops|same_position_order|object_identity_parent
    entity_type: str
    entity_uuid: str
    entity_name: str = ""
    path: str = ""
    parent_uuid: str | None = None
    parent_type: str | None = None
    base_value: Any = None
    target_value: Any = None
    source_value: Any = None
    related_entity_type: str | None = None
    related_entity_uuid: str | None = None
    related_entity_name: str | None = None
    choices: list[str] = ["target", "source"]
    resolved: bool = False


class MergePreviewResponse(BaseModel):
    """MR 三方合并预览：可重建（每次按当前 heads 重算），列出待解决冲突与自动合并统计。"""
    merge_base_public_id: str | None = None
    source_head_public_id: str | None = None
    target_head_public_id: str | None = None
    conflict_count: int = 0
    conflicts: list[ConflictItemResponse] = Field(default_factory=list)
    auto_merged_summary: dict[str, int] = Field(default_factory=dict)


class ConflictResolution(BaseModel):
    """对单个冲突的解决选择：保留目标/来源/受限手工值。"""
    conflict_id: str
    choice: Literal["target", "source", "manual"] = "target"
    manual_value: Any = None


class MergeRequestPayload(BaseModel):
    """合并请求体：客户端一次性提交其对全部冲突的解决选择，并绑定预览时的三方 heads。

    三个 head 字段必填：合并执行时据此校验 source/target 是否在预览后推进，防止按陈旧
    heads 创建 merge commit。缺失任一字段即拒绝合并（返回 422），不允许绕过并发保护。
    """
    resolutions: list[ConflictResolution] = Field(default_factory=list)
    merge_base_public_id: str = Field(min_length=1)
    source_head_public_id: str = Field(min_length=1)
    target_head_public_id: str = Field(min_length=1)


class MergeResponse(BaseModel):
    """合并成功结果：目标分支产生带两个父节点的 merge commit。"""
    status: str
    merged_commit_public_id: str | None = None
    target_head_public_id: str | None = None
