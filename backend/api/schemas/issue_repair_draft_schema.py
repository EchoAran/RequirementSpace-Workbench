from datetime import datetime

from pydantic import BaseModel, Field
from backend.api.schemas.project_schema import CamelModel


class IssueRepairDraftResponse(CamelModel):
    draft_id: str
    project_id: int
    issue_code: str
    issue_id: str
    stage: str
    repair_type: str
    title: str
    rationale: str
    proposal: dict = Field(default_factory=dict)
    patch: dict | None = None
    status: str
    issue_fingerprint: str | None = None
    context_hash: str | None = None
    created_at: datetime | None = None


class IssueRepairDraftActionResponse(CamelModel):
    message: str
    draft_id: str
    status: str
    resolved_issue_ids: list[str] = Field(default_factory=list)
    remaining_issue_ids: list[str] = Field(default_factory=list)
    new_issue_ids: list[str] = Field(default_factory=list)
    partially_resolved: bool = False
