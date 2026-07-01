from datetime import datetime
from pydantic import Field
from backend.api.base_schema import CamelModel



class ChoiceResponse(CamelModel):
    id: int
    choice_group_id: int
    title: str
    rationale: str
    status: str
    patch: dict
    impact_preview: dict | None = None
    # Phase 1: generation choice 扩展字段
    payload: dict | None = None
    draft_type: str | None = None
    apply_mode: str = "patch"
    preview: dict | None = None
    score: dict | None = None
    error: dict | None = None
    created_at: datetime
    updated_at: datetime


class ChoiceGroupResponse(CamelModel):
    id: int
    project_id: str
    slot_id: int | None = None
    status: str
    selection_mode: str
    source_type: str | None = None
    source_id: str | None = None
    issue_code: str | None = None
    issue_id: str | None = None
    stage: str | None = None
    target: dict | None = None
    context_hash: str | None = None
    # Phase 1: generation choice group 扩展
    generation_type: str | None = None
    origin_endpoint: str | None = None
    candidate_count: int | None = None
    success_count: int | None = None
    failure_count: int | None = None
    status_detail: dict | None = None
    choices: list[ChoiceResponse] = []
    created_at: datetime
    updated_at: datetime


class ProjectChoiceGroupsResponse(CamelModel):
    project_id: str
    choice_groups: list[ChoiceGroupResponse]


class ChoiceActionResponse(CamelModel):
    """采纳/拒绝 choice 的响应。extends 旧版以兼容 issue repair 的回归验证字段。"""
    message: str
    choice_id: int
    status: str
    resolved_issue_ids: list[str] = Field(default_factory=list)
    remaining_issue_ids: list[str] = Field(default_factory=list)
    new_issue_ids: list[str] = Field(default_factory=list)
    partially_resolved: bool = False
    # Phase 1: generation choice 扩展
    is_stale: bool = False
    stale_reason: str | None = None
    apply_behavior: str | None = Field(
        default=None,
        description="采纳行为: overwrite | append | merge",
    )
    apply_behavior_description: str | None = Field(
        default=None,
        description="用户可读的行为说明，如'将替换现有的 3 名参与者'",
    )




# === Phase 1: Generation Choice Group 专用 Schema ===

class GenerationChoiceGroupCreateRequest(CamelModel):
    """创建 AI 生成 choice group 的请求。"""
    project_id: str
    generation_type: str = Field(
        ...,
        description="生成类型: actor, scenario, feature, project_creation 等",
    )
    target: dict | None = Field(
        default=None,
        description="生成目标上下文，如 {'feature_id': 12, 'actor_id': 3}",
    )
    candidate_count: int | None = Field(
        default=None,
        description="候选数，覆盖默认配置 (1-5)",
    )
    user_feedback: str | None = Field(
        default=None,
        description="用户反馈或额外指导",
    )


class GenerationCandidateError(CamelModel):
    """单个候选失败的信息。"""
    index: int
    strategy: str
    error_type: str = Field(
        ...,
        description="timeout | llm_error | validation_error | unknown",
    )
    message: str = Field(..., description="用户可读的错误摘要")
    detail: str | None = Field(default=None, description="调试用完整错误")


class GenerationAcceptRequest(CamelModel):
    """采纳 generation choice 的请求，支持强制采纳 stale choice。"""
    force: bool = Field(
        default=False,
        description="跳过 stale 校验强制采纳",
    )
