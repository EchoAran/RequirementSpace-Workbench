from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class KnowledgeWorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    public_id: str
    owner_user_id: int
    project_id: int | None = None
    scope: str
    status: str
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    public_id: str
    workspace_id: int | None = None
    project_id: int | None = None
    owner_user_id: int
    original_filename: str
    content_type: str
    file_size: int
    sha256: str
    status: str
    ai_enabled: bool
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentPatchRequest(BaseModel):
    ai_enabled: bool
