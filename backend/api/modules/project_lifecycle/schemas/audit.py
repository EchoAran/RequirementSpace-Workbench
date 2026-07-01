from pydantic import Field
from datetime import datetime
from typing import Optional
from backend.api.base_schema import CamelModel, DraftRegenerateRequest


class AuditLogResponse(CamelModel):
    id: int
    project_id: str
    action_type: str
    summary: str
    target_type: str
    target_id: str
    payload: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    
    actor_user_id: Optional[int] = None
    actor_type: str = "system"
    actor_email: Optional[str] = None
    diff: Optional[dict | list] = None
    request_id: Optional[str] = None
    task_id: Optional[int] = None


class UserRequirementsUpdateRequest(CamelModel):
    user_requirements: str = Field(..., description="Project raw user requirements text")


class UserRequirementsRefineRequest(CamelModel):
    user_feedback: Optional[str] = Field(None, description="Optional extra user suggestions or feedback to guide requirement refinement")


class UserRequirementsResponse(CamelModel):
    project_id: str
    user_requirements: str


