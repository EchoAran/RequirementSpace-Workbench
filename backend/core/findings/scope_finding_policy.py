from backend.core.detectors import ScopeIssueDetector
from backend.core.findings.finding_factory import make_finding
from backend.schemas import Finding, FindingType, BlockingScope, IssueStage, IssueSeverity


class ScopeFindingPolicy:
    def __init__(self):
        self.detector = ScopeIssueDetector()

    async def get_findings(self, project_id: int, session) -> list[Finding]:
        issues = await self.detector.detect(project_id, session)
        findings: list[Finding] = []

        # Separate LEAF_FEATURE_WITHOUT_SCOPE for aggregation
        scope_issues = [i for i in issues if i.code == "LEAF_FEATURE_WITHOUT_SCOPE"]
        other_issues = [i for i in issues if i.code != "LEAF_FEATURE_WITHOUT_SCOPE"]

        # 1. Individual scope items as ISSUE (逐项修复)
        #    聚合 GATE_CONDITION 负责阶段阻断，单项 Issue 仅用于逐项定位/修复
        for issue in scope_issues:
            findings.append(
                make_finding(
                    stage=IssueStage.SCOPE,
                    code=issue.code,
                    severity=issue.severity,
                    title=issue.title,
                    description=issue.description,
                    target=issue.target,
                    action_code=issue.actionCode,
                    metadata=issue.metadata or {},
                )
            )

        # 2. Other issues
        for issue in other_issues:
            finding_type = FindingType.ISSUE
            blocking_scope = BlockingScope.NONE

            if issue.code == "SCOPE_WITHOUT_REASON":
                finding_type = FindingType.QUALITY_HINT

            findings.append(
                make_finding(
                    stage=IssueStage.SCOPE,
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
            )

        # 3. Aggregate LEAF_FEATURE_WITHOUT_SCOPE as GATE_CONDITION
        if scope_issues:
            missing_features = [
                {
                    "feature_id": i.target.targetId if i.target else None,
                    "description": i.description,
                }
                for i in scope_issues
            ]
            findings.append(
                make_finding(
                    stage=IssueStage.SCOPE,
                    code="LEAF_FEATURE_WITHOUT_SCOPE",
                    severity=IssueSeverity.WARNING,
                    title="叶子功能缺少范围结论",
                    description=f"检测到有 {len(scope_issues)} 个叶子功能尚未设定范围结论，这会阻碍生成预览。",
                    finding_type=FindingType.GATE_CONDITION,
                    blocking_scope=BlockingScope.STAGE_TRANSITION,
                    action_code="create_scope_generation_draft",
                    metadata={"missing_features": missing_features},
                    finding_id_override="scope:LEAF_FEATURE_WITHOUT_SCOPE:aggregate",
                )
            )

        return findings
