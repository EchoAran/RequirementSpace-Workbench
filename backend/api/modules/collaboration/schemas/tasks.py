from datetime import datetime

from pydantic import Field

from backend.api.base_schema import CamelModel


class TargetNodeInput(CamelModel):
    node_kind: str = Field(..., description="Target node kind, e.g. actor, feature, scenario")
    node_id: int = Field(..., description="Target node ID")

class TaskCreateRequest(CamelModel):
    node_kind: str = Field(..., description="Target node kind, e.g. actor, feature, scenario")
    node_id: int = Field(..., description="Target node ID")
    assigned_to_user_id: int = Field(..., description="User ID to assign the confirmation task to")
    title: str | None = Field(None, description="Optional custom title for the task")
    description: str | None = Field(None, description="Optional description details")
    priority: str = Field("normal", description="Task priority: low, normal, high")
    due_at: datetime | None = Field(None, description="Optional deadline for the task")

class BatchTaskCreateRequest(CamelModel):
    targets: list[TargetNodeInput] = Field(..., description="List of target nodes")
    assigned_to_user_id: int = Field(..., description="User ID to assign the confirmation task to")
    title: str | None = Field(None, description="Optional custom title for the task")
    description: str | None = Field(None, description="Optional description details")
    priority: str = Field("normal", description="Task priority: low, normal, high")
    due_at: datetime | None = Field(None, description="Optional deadline for the task")

class TaskDecisionRequest(CamelModel):
    decision: str = Field(..., description="approve or reject")
    decision_note: str | None = Field(None, description="Optional note for approval or rejection")

class TaskResponse(CamelModel):
    id: int
    project_id: int
    task_type: str
    title: str
    description: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    targets: dict | list | None = None
    status: str
    priority: str
    created_by_user_id: int
    assigned_to_user_id: int
    content_snapshot: dict | list | None = None
    content_hash: str | None = None
    decision_note: str | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # Rich fields for the assignee and creator
    creator_email: str | None = None
    assignee_email: str | None = None

    # Node summary name for rendering in task center
    node_name: str | None = None

    # Flag indicating whether node content has changed since the task was created
    content_changed: bool = False

class UserTaskProjectSummary(CamelModel):
    project_id: str
    project_name: str

class UserTaskTargetSummary(CamelModel):
    node_kind: str | None = None
    node_id: int | None = None
    node_name: str | None = None

class UserTaskUserSummary(CamelModel):
    user_id: int
    email: str

class UserTaskResponse(CamelModel):
    task: TaskResponse
    project_summary: UserTaskProjectSummary
    target_summary: UserTaskTargetSummary
    creator_summary: UserTaskUserSummary
    assignee_summary: UserTaskUserSummary
    content_changed: bool

class ConfirmationSummaryResponse(CamelModel):
    ai_assumption_count: int
    open_task_count: int
    assigned_to_me_count: int
    created_by_me_count: int
    rejected_count: int
    by_node_kind: dict[str, int]
    by_assignee: dict[str, int]
