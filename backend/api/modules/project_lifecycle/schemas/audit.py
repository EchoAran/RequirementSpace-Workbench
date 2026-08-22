from datetime import datetime

from pydantic import Field

from backend.api.base_schema import CamelModel


class AuditLogResponse(CamelModel):
    id: int
    project_id: str
    action_type: str
    summary: str
    target_type: str
    target_id: str
    payload: dict | None = None
    created_at: datetime
    updated_at: datetime

    actor_user_id: int | None = None
    actor_type: str = "system"
    actor_email: str | None = None
    diff: dict | list | None = None
    request_id: str | None = None
    task_id: int | None = None


class UserRequirementsUpdateRequest(CamelModel):
    user_requirements: str = Field(..., description="Project raw user requirements text")


class UserRequirementsRefineRequest(CamelModel):
    user_feedback: str | None = Field(None, description="Optional extra user suggestions or feedback to guide requirement refinement")


class UserRequirementsResponse(CamelModel):
    project_id: str
    user_requirements: str

