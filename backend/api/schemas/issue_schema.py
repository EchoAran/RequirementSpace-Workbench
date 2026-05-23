from pydantic import BaseModel, Field


class IssueTargetResponse(BaseModel):
    target_type: str
    target_id: int | str | None = None
    parent_type: str | None = None
    parent_id: int | str | None = None


class IssueResponse(BaseModel):
    issue_id: str
    code: str
    stage: str
    severity: str
    title: str
    description: str
    target: IssueTargetResponse | None = None
    resolver_code: str | None = None
    metadata: dict = Field(default_factory=dict)


class ProjectIssuesResponse(BaseModel):
    project_id: int
    stage: str
    issues: list[IssueResponse]


class IssueResolveRequest(BaseModel):
    issue_code: str
    target: IssueTargetResponse | None = None
    metadata: dict = Field(default_factory=dict)


class IssueResolutionActionResponse(BaseModel):
    kind: str
    route: str | None = None
    panel: str | None = None
    draft_type: str | None = None
    endpoint: str | None = None
    payload: dict = Field(default_factory=dict)


class IssueResolutionResponse(BaseModel):
    project_id: int
    issue_code: str
    resolution_type: str
    title: str
    description: str
    action: IssueResolutionActionResponse
    draft_id: str | None = None
    draft: dict = Field(default_factory=dict)
    patch: dict | None = None
