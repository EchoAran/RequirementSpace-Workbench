"""
Version Control HTTP API Schemas.
定义分支管理与工作区状态的 HTTP 请求与响应 Schema 结构。
"""
from typing import Any, Dict, List, Literal, Optional
from datetime import datetime
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
    description: Optional[str] = None
    head_commit_id: Optional[int] = None
    head_commit_public_id: Optional[str] = None
    source_commit_id: Optional[int] = None
    source_commit_public_id: Optional[str] = None
    is_protected: bool = False
    is_default: bool = False
    status: str = "active"
    created_at: datetime
    updated_at: datetime
    permissions: Optional[BranchPermissions] = None
    workspace_dirty: Optional[WorkspaceDirtySummary] = None


class BranchDetailResponse(BranchSummaryResponse):
    workspace_id: Optional[int] = None
    user_requirements: str = ""
    kano_status: str = "missing"
    unlocked_stages: str = ""


class BranchCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    source_commit_public_id: Optional[str] = None
    source_branch_public_id: Optional[str] = None


class BranchUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)


# ==========================================
# Commit Contracts
# ==========================================

class CommitCreateRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    expected_head_commit_id: Optional[int] = None
    expected_head_commit_public_id: Optional[str] = None

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


class CommitSummaryResponse(BaseModel):
    id: int
    public_id: str
    short_id: str
    message: str
    state_hash: str
    schema_version: str = "1.0"
    summary: Optional[Dict[str, Any]] = None
    author_user_id: Optional[int] = None
    author_email: Optional[str] = None
    created_at: datetime
    parent_ids: List[int] = Field(default_factory=list)
    parent_public_ids: List[str] = Field(default_factory=list)
    is_merge: bool = False
    branch_public_ids: List[str] = Field(default_factory=list)
    branch_names: List[str] = Field(default_factory=list)


class CommitDetailResponse(CommitSummaryResponse):
    # 历史只读视图：由 Commit state_json 重建的规范化需求模型，不读取当前分支表。
    state: Optional[Dict[str, Any]] = None


class CommitListResponse(BaseModel):
    commits: List[CommitSummaryResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


# ==========================================
# Semantic Diff Contracts
# ==========================================

class DiffRefInfo(BaseModel):
    kind: str = "commit"  # commit | branch | workspace
    label: str = ""
    public_id: Optional[str] = None
    branch_ref: Optional[str] = None
    branch_name: Optional[str] = None
    branch_is_protected: bool = False


class TextDiffBlock(BaseModel):
    kind: str = "replace"  # replace | add | remove
    before_lines: List[str] = Field(default_factory=list)
    after_lines: List[str] = Field(default_factory=list)


class DiffEntry(BaseModel):
    change_type: str  # entity_added|entity_removed|entity_updated|field_changed|relation_added|relation_removed|ordered_item_moved
    entity_type: str
    entity_uuid: str
    entity_name: str = ""
    parent_uuid: Optional[str] = None
    parent_type: Optional[str] = None
    path: str = ""
    field: Optional[str] = None
    before: Any = None
    after: Any = None
    text_blocks: List[TextDiffBlock] = Field(default_factory=list)
    relation_type: Optional[str] = None
    related_entity_type: Optional[str] = None
    related_entity_uuid: Optional[str] = None
    related_entity_name: Optional[str] = None
    before_position: Optional[int] = None
    after_position: Optional[int] = None


class DiffTypeSummary(BaseModel):
    added: int = 0
    removed: int = 0
    modified: int = 0


class DiffSummary(BaseModel):
    by_type: Dict[str, DiffTypeSummary] = Field(default_factory=dict)
    total_added: int = 0
    total_removed: int = 0
    total_modified: int = 0


class DiffResult(BaseModel):
    base: Optional[DiffRefInfo] = None
    target: Optional[DiffRefInfo] = None
    summary: DiffSummary
    entries: List[DiffEntry] = Field(default_factory=list)
    total: int = 0
    limit: int = 0
    offset: int = 0


class EntityDiffResponse(BaseModel):
    base: Optional[DiffRefInfo] = None
    target: Optional[DiffRefInfo] = None
    entity_uuid: str
    entity_type: str = ""
    entity_name: str = ""
    base_value: Optional[Dict[str, Any]] = None
    target_value: Optional[Dict[str, Any]] = None
    entries: List[DiffEntry] = Field(default_factory=list)


# ==========================================
# Merge Request Contracts
# ==========================================

_MR_STATUSES = frozenset(
    {"open", "approved", "changes_requested", "mergeable", "merged", "closed"}
)
_REVIEW_DECISIONS = frozenset({"approved", "changes_requested"})


class MergeReviewResponse(BaseModel):
    id: int
    reviewer_user_id: Optional[int] = None
    reviewer_email: Optional[str] = None
    decision: str = "approved"
    comment: str = ""
    status: str = "active"  # "active" | "stale"
    stale_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MergeCommentResponse(BaseModel):
    id: int
    author_user_id: Optional[int] = None
    author_email: Optional[str] = None
    entity_uuid: Optional[str] = None
    field_path: Optional[str] = None
    relation_key: Optional[str] = None
    comment: str
    required: bool = False
    status: str = "active"
    effective_source_head_id: Optional[int] = None
    expired_by_source_head_id: Optional[int] = None
    created_at: datetime


class MRDiffSummary(BaseModel):
    by_type: Dict[str, DiffTypeSummary] = Field(default_factory=dict)
    total_added: int = 0
    total_removed: int = 0
    total_modified: int = 0


class MergeRequestSummaryResponse(BaseModel):
    id: int
    public_id: str
    project_id: int
    title: str
    description: Optional[str] = None
    source_branch_name: str = ""
    target_branch_name: str = ""
    source_branch_public_id: Optional[str] = None
    target_branch_public_id: Optional[str] = None
    status: str = "open"
    author_user_id: Optional[int] = None
    author_email: Optional[str] = None
    diff_summary: Optional[MRDiffSummary] = None
    active_review_count: int = 0
    total_comments: int = 0
    source_head_short: Optional[str] = None
    target_head_short: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MergeRequestDetailResponse(MergeRequestSummaryResponse):
    source_head_commit_id: Optional[int] = None
    source_head_public_id: Optional[str] = None
    target_head_commit_id: Optional[int] = None
    target_head_public_id: Optional[str] = None
    merge_base_commit_id: Optional[int] = None
    merge_base_public_id: Optional[str] = None
    merged_commit_id: Optional[int] = None
    merged_commit_public_id: Optional[str] = None
    reviews: List[MergeReviewResponse] = Field(default_factory=list)
    comments: List[MergeCommentResponse] = Field(default_factory=list)
    can_approve: bool = False
    can_merge: bool = False
    blocking_reasons: List[str] = Field(default_factory=list)


class MergeRequestPreviewRequest(BaseModel):
    source_branch_public_id: str
    target_branch_public_id: str


class MergeRequestPreviewResponse(BaseModel):
    merge_base_public_id: Optional[str] = None
    source_head_public_id: Optional[str] = None
    target_head_public_id: Optional[str] = None
    diff_summary: MRDiffSummary = MRDiffSummary()


class MergeRequestCreateRequest(BaseModel):
    source_branch_id: Optional[int] = None
    source_branch_name: Optional[str] = None
    source_branch_public_id: Optional[str] = None
    target_branch_id: Optional[int] = None
    target_branch_name: Optional[str] = None
    target_branch_public_id: Optional[str] = None
    title: str = Field(min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=2000)

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
    comment: Optional[str] = Field(default=None, max_length=2000)


class MergeCommentCreateRequest(BaseModel):
    entity_uuid: Optional[str] = None
    field_path: Optional[str] = None
    relation_key: Optional[str] = None
    comment: str = Field(min_length=1, max_length=2000)
    required: bool = False


class MergeRequestListResponse(BaseModel):
    items: List[MergeRequestSummaryResponse] = Field(default_factory=list)
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
    parent_uuid: Optional[str] = None
    parent_type: Optional[str] = None
    base_value: Any = None
    target_value: Any = None
    source_value: Any = None
    related_entity_type: Optional[str] = None
    related_entity_uuid: Optional[str] = None
    related_entity_name: Optional[str] = None
    choices: List[str] = ["target", "source"]
    resolved: bool = False


class MergePreviewResponse(BaseModel):
    """MR 三方合并预览：可重建（每次按当前 heads 重算），列出待解决冲突与自动合并统计。"""
    merge_base_public_id: Optional[str] = None
    source_head_public_id: Optional[str] = None
    target_head_public_id: Optional[str] = None
    conflict_count: int = 0
    conflicts: List[ConflictItemResponse] = Field(default_factory=list)
    auto_merged_summary: Dict[str, int] = Field(default_factory=dict)


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
    resolutions: List[ConflictResolution] = Field(default_factory=list)
    merge_base_public_id: str = Field(min_length=1)
    source_head_public_id: str = Field(min_length=1)
    target_head_public_id: str = Field(min_length=1)


class MergeResponse(BaseModel):
    """合并成功结果：目标分支产生带两个父节点的 merge commit。"""
    status: str
    merged_commit_public_id: Optional[str] = None
    target_head_public_id: Optional[str] = None
