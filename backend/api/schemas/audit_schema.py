from pydantic import Field
from datetime import datetime
from typing import Optional
from backend.api.schemas.project_schema import CamelModel

class AuditLogResponse(CamelModel):
    id: int
    project_id: int
    action_type: str
    summary: str
    target_type: str
    target_id: str
    payload: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class UserRequirementsUpdateRequest(CamelModel):
    user_requirements: str = Field(..., description="Project raw user requirements text")


class UserRequirementsRefineRequest(CamelModel):
    user_feedback: Optional[str] = Field(None, description="Optional extra user suggestions or feedback to guide requirement refinement")


class UserRequirementsResponse(CamelModel):
    project_id: int
    user_requirements: str


class DraftRegenerateRequest(CamelModel):
    user_feedback: Optional[str] = Field(None, description="Optional modification suggestions or feedback to steer the regeneration process")
