from datetime import datetime
from typing import Optional
from backend.api.base_schema import CamelModel

class ProjectMemberResponse(CamelModel):
    member_id: int
    user_id: int
    email: str
    role: str
    status: str
    joined_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class ProjectMemberAddRequest(CamelModel):
    email: str
    role: str

class ProjectMemberUpdateRequest(CamelModel):
    role: str
    status: str
