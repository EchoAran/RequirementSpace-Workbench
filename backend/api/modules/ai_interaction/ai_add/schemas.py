"""Schemas for AI-powered conversational single-object addition sessions."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from backend.api.base_schema import CamelModel


class AIAddSessionCreateRequest(BaseModel):
    project_id: str
    target_type: str = Field(..., min_length=1, max_length=50)
    anchor: dict = Field(default_factory=dict)


class AIAddMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)


class AIAddMessageResponse(CamelModel):
    session_id: int
    assistant_message: str
    is_ready_to_generate: bool
    summary: dict = Field(default_factory=dict)


class AIAddSessionResponse(CamelModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    project_id: str
    target_type: str
    anchor_payload: dict
    status: str
    summary_payload: dict | None = None
    ready_to_generate: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AIAddMessageItem(CamelModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    extra: dict | None = None
    created_at: datetime | None = None


class AIAddSessionMessagesResponse(CamelModel):
    session_id: int
    messages: list[AIAddMessageItem]


class AIAddGenerateDraftResponse(CamelModel):
    draft_id: str
    project_id: str
    target_type: str
    preview: dict = Field(default_factory=dict)
    message: str = "draft_created"


class AIAddConfirmDraftResponse(CamelModel):
    draft_id: str
    message: str = "confirmed"
    created_object_id: int | None = None


class AIAddDiscardDraftResponse(CamelModel):
    draft_id: str
    message: str = "draft_discarded"
