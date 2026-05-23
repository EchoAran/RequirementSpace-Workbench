from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class AuditLogResponse(BaseModel):
    id: int
    project_id: int
    action_type: str
    summary: str
    target_type: str
    target_id: str
    payload: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserRequirementsUpdateRequest(BaseModel):
    user_requirements: str = Field(..., description="Project raw user requirements text")


class UserRequirementsRefineRequest(BaseModel):
    user_feedback: Optional[str] = Field(None, description="Optional extra user suggestions or feedback to guide requirement refinement")


class UserRequirementsResponse(BaseModel):
    project_id: int
    user_requirements: str


class DraftRegenerateRequest(BaseModel):
    user_feedback: Optional[str] = Field(None, description="Optional modification suggestions or feedback to steer the regeneration process")
