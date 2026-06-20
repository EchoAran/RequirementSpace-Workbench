from typing import List, Optional
from pydantic import Field
from backend.api.schemas.project_schema import CamelModel
from backend.api.schemas.issue_schema import IssueTargetResponse


class IssueCapabilityResponse(CamelModel):
    kind: str
    action_label: str
    enabled: bool = True


class FindingResponse(CamelModel):
    finding_id: str
    type: str
    stage: str
    code: str
    severity: str
    title: str
    description: str
    target: Optional[IssueTargetResponse] = None
    blocking_scope: str = "none"
    action_code: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    capability: Optional[IssueCapabilityResponse] = None

class ProjectFindingsResponse(CamelModel):
    project_id: str
    stage: str
    view: str
    findings: List[FindingResponse]

class FindingStatusUpdateRequest(CamelModel):
    finding_id: str
    status: str

class FindingStatusUpdateResponse(CamelModel):
    project_id: str
    finding_id: str
    status: str
