from backend.core.detectors import HowIssueDetector
from backend.core.findings.finding_factory import make_finding
from backend.schemas import BlockingScope, Finding, FindingType, IssueSeverity, IssueStage


class HowFindingPolicy:
    def __init__(self):
        self.detector = HowIssueDetector()

    async def get_findings(self, project_id: int, session, workspace_id: int) -> list[Finding]:
        issues = await self.detector.detect(project_id, session, workspace_id=workspace_id)
        return [
            self._make_other_issue_finding(issue)
            for issue in issues
        ]

    @staticmethod
    def _make_other_issue_finding(issue) -> Finding:
        finding_type = FindingType.ISSUE
        blocking_scope = BlockingScope.NONE
        if issue.severity == IssueSeverity.BLOCKING:
            blocking_scope = BlockingScope.STAGE_TRANSITION
        elif issue.severity == IssueSeverity.INFO:
            finding_type = FindingType.QUALITY_HINT
        elif issue.code in (
            "FLOW_WITHOUT_FEATURE",
            "ACTOR_ACTION_STEP_WITHOUT_ACTOR",
            "INVALID_STEP_ACTOR",
            "INVALID_STEP_BUSINESS_OBJECT",
            "UNREACHABLE_FLOW_STEP",
            "JUDGMENT_STEP_WITH_TOO_FEW_BRANCHES",
            "FLOW_WITHOUT_STEPS",
        ):
            blocking_scope = BlockingScope.STAGE_TRANSITION
        return make_finding(
            stage=IssueStage.HOW,
            code=issue.code,
            severity=issue.severity,
            title=issue.title,
            description=issue.description,
            target=issue.target,
            finding_type=finding_type,
            blocking_scope=blocking_scope,
            action_code=issue.actionCode,
            metadata=issue.metadata or {},
        )
