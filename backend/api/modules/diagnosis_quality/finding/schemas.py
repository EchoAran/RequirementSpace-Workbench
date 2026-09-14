
from pydantic import Field

from backend.api.base_schema import CamelModel
from backend.api.modules.diagnosis_quality.issue_repair.schemas import (
    IssueTargetResponse,
)


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
    target: IssueTargetResponse | None = None
    blocking_scope: str = "none"
    action_code: str | None = None
    metadata: dict = Field(default_factory=dict)
    capability: IssueCapabilityResponse | None = None

class ProjectFindingsResponse(CamelModel):
    project_id: str
    stage: str
    view: str
    findings: list[FindingResponse]

class FindingStatusUpdateRequest(CamelModel):
    finding_id: str
    status: str

class FindingStatusUpdateResponse(CamelModel):
    project_id: str
    finding_id: str
    status: str
