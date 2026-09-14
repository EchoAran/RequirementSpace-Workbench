from datetime import datetime

from pydantic import Field

from backend.api.base_schema import CamelModel


class IssueRepairDraftResponse(CamelModel):
    draft_id: str
    project_id: str
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


class IssueTargetResponse(CamelModel):
    target_type: str
    target_id: int | str | None = None
    parent_type: str | None = None
    parent_id: int | str | None = None


class IssueResolveRequest(CamelModel):
    issue_id: str | None = None
    issue_code: str
    stage: str | None = None
    target: IssueTargetResponse | None = None
    metadata: dict = Field(default_factory=dict)




class IssueResolutionActionResponse(CamelModel):
    kind: str
    route: str | None = None
    panel: str | None = None
    draft_type: str | None = None
    endpoint: str | None = None
    payload: dict = Field(default_factory=dict)


class IssueResolutionResponse(CamelModel):
    project_id: str
    issue_code: str
    resolution_type: str
    title: str
    description: str
    action: IssueResolutionActionResponse
    draft_id: str | None = None
    draft: dict = Field(default_factory=dict)
    patch: dict | None = None
    issue_fingerprint: str | None = None
    context_hash: str | None = None
