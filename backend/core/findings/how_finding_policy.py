from backend.core.detectors import HowIssueDetector
from backend.core.findings.finding_factory import make_finding
from backend.schemas import BlockingScope, Finding, FindingType, IssueSeverity, IssueStage


class HowFindingPolicy:
    def __init__(self):
        self.detector = HowIssueDetector()

    async def get_findings(self, project_id: int, session, workspace_id: int | None = None) -> list[Finding]:
        issues = await self.detector.detect(project_id, session, workspace_id=workspace_id)
        flow_issues = [i for i in issues if i.code == "LEAF_FEATURE_WITHOUT_FLOW"]
        other_issues = [i for i in issues if i.code != "LEAF_FEATURE_WITHOUT_FLOW"]
        findings = [
            self._make_flow_issue_finding(issue)
            for issue in flow_issues
        ]
        findings.extend(
            self._make_other_issue_finding(issue)
            for issue in other_issues
        )
        if flow_issues:
            findings.append(self._make_flow_gate_finding(flow_issues))
        return findings

    @staticmethod
    def _make_flow_issue_finding(issue) -> Finding:
        return make_finding(
            stage=IssueStage.HOW,
            code=issue.code,
            severity=issue.severity,
            title=issue.title,
            description=issue.description,
            target=issue.target,
            action_code=issue.actionCode,
            metadata=issue.metadata or {},
        )

    @staticmethod
    def _make_other_issue_finding(issue) -> Finding:
        finding_type = FindingType.ISSUE
        blocking_scope = BlockingScope.NONE
        if issue.code == "BUSINESS_OBJECT_WITHOUT_USAGE":
            finding_type = FindingType.QUALITY_HINT
        elif issue.code == "BUSINESS_OBJECT_WITHOUT_ATTRIBUTES":
            finding_type = FindingType.QUALITY_HINT
            blocking_scope = BlockingScope.PREVIEW
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

    @staticmethod
    def _make_flow_gate_finding(flow_issues) -> Finding:
        missing_features = [
            {
                "feature_id": issue.target.targetId if issue.target else None,
                "description": issue.description,
            }
            for issue in flow_issues
        ]
        return make_finding(
            stage=IssueStage.HOW,
            code="LEAF_FEATURE_WITHOUT_FLOW",
            severity=IssueSeverity.WARNING,
            title="叶子功能缺少流程覆盖",
            description=f"检测到有 {len(flow_issues)} 个叶子功能尚未被流程覆盖，这会阻碍进入 Scope 阶段。",
            finding_type=FindingType.GATE_CONDITION,
            blocking_scope=BlockingScope.STAGE_TRANSITION,
            action_code="open_flow_feature_panel",
            metadata={"missing_features": missing_features},
            finding_id_override="how:LEAF_FEATURE_WITHOUT_FLOW:aggregate",
        )
