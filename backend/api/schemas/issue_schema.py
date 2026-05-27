from pydantic import BaseModel, Field
from backend.api.schemas.project_schema import CamelModel


class IssueTargetResponse(CamelModel):
    target_type: str
    target_id: int | str | None = None
    parent_type: str | None = None
    parent_id: int | str | None = None


class IssueResponse(CamelModel):
    issue_id: str
    code: str
    stage: str
    severity: str
    title: str
    description: str
    target: IssueTargetResponse | None = None
    resolver_code: str | None = None
    metadata: dict = Field(default_factory=dict)


class ProjectIssuesResponse(CamelModel):
    project_id: int
    stage: str
    issues: list[IssueResponse]


class IssueResolveRequest(CamelModel):
    issue_code: str
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
    project_id: int
    issue_code: str
    resolution_type: str
    title: str
    description: str
    action: IssueResolutionActionResponse
    draft_id: str | None = None
    draft: dict = Field(default_factory=dict)
    patch: dict | None = None
