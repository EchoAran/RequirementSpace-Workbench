from pydantic import BaseModel, Field
from backend.api.modules.decision_workflow.public import ChoiceGroupResponse
from backend.api.modules.project_lifecycle.schemas.project import CamelModel


class ProjectCreationChoiceGroupCreateRequest(CamelModel):
    user_requirements: str = Field(min_length=1, description="原始需求")
    candidate_count: int | None = Field(
        default=None, ge=1, le=5,
        description="候选数量，覆盖默认配置",
    )
    user_feedback: str | None = Field(
        default=None,
        description="用户反馈或额外指导",
    )
    knowledge_workspace_id: str | None = Field(
        default=None,
        description="关联的项目创建期知识库临时工作区ID",
    )


class ProjectCreationChoiceGroupResponse(CamelModel):
    id: str
    status: str
    generation_type: str = "project_creation"
    user_requirements: str = ""
    candidate_count: int | None = None
    success_count: int | None = None
    failure_count: int | None = None
    status_detail: dict | None = None
    context_hash: str | None = None
    created_at: float | None = None
    updated_at: float | None = None
    resolved_project_id: str | None = None
    choices: list["ProjectCreationChoiceItem"] = []


class ProjectCreationChoiceItem(CamelModel):
    id: str
    title: str
    rationale: str = ""
    status: str
    draft_type: str = "project_creation"
    apply_mode: str = "draft_payload"
    payload: dict = {}
    preview: dict = {}
    score: dict | None = None
    comparison_summary: str = ""
    error: dict | None = None


class ProjectCreationChoiceAcceptResponse(CamelModel):
    project_id: str
    project_name: str
    project_description: str
    message: str = "project_created"


class ProjectCreationChoiceGroupDiscardResponse(CamelModel):
    message: str = "choice_group_discarded"
    group_id: str


class ProjectCreationChoiceGroupDeferResponse(CamelModel):
    project_id: str
    project_name: str
    project_description: str
    choice_group: ChoiceGroupResponse
    message: str = "project_created_with_deferred_choice_group"
