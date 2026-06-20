from backend.core.detectors import HowIssueDetector
from backend.core.findings.finding_factory import make_finding
from backend.schemas import Finding, FindingType, BlockingScope, IssueStage, IssueSeverity


class HowFindingPolicy:
    def __init__(self):
        self.detector = HowIssueDetector()

    async def get_findings(self, project_id: int, session) -> list[Finding]:
        issues = await self.detector.detect(project_id, session)
        findings: list[Finding] = []

        # Separate LEAF_FEATURE_WITHOUT_FLOW for aggregation
        flow_issues = [i for i in issues if i.code == "LEAF_FEATURE_WITHOUT_FLOW"]
        other_issues = [i for i in issues if i.code != "LEAF_FEATURE_WITHOUT_FLOW"]

        # 1. Individual flow items as ISSUE (逐项修复)
        #    聚合 GATE_CONDITION 负责阶段阻断，单项 Issue 仅用于逐项定位/修复
        for issue in flow_issues:
            findings.append(
                make_finding(
                    stage=IssueStage.HOW,
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

            if issue.code == "BUSINESS_OBJECT_WITHOUT_USAGE":
                finding_type = FindingType.QUALITY_HINT
            elif issue.code == "BUSINESS_OBJECT_WITHOUT_ATTRIBUTES":
                finding_type = FindingType.QUALITY_HINT
                blocking_scope = BlockingScope.PREVIEW
            elif issue.code in (
                "FLOW_WITHOUT_FEATURE",
                "ACTOR_ACTION_STEP_WITHOUT_ACTOR",
                "UNREACHABLE_FLOW_STEP",
                "JUDGMENT_STEP_WITH_TOO_FEW_BRANCHES",
                "FLOW_WITHOUT_STEPS",
            ):
                finding_type = FindingType.ISSUE
                blocking_scope = BlockingScope.STAGE_TRANSITION

            findings.append(
                make_finding(
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
            )

        # 3. Aggregate LEAF_FEATURE_WITHOUT_FLOW as GATE_CONDITION
        if flow_issues:
            missing_features = [
                {
                    "feature_id": i.target.targetId if i.target else None,
                    "description": i.description,
                }
                for i in flow_issues
            ]
            findings.append(
                make_finding(
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
            )

        return findings
