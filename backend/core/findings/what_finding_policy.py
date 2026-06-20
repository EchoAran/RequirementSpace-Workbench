from backend.core.detectors import WhatIssueDetector
from backend.core.findings.finding_factory import make_finding
from backend.schemas import Finding, FindingType, BlockingScope, IssueStage, IssueSeverity


class WhatFindingPolicy:
    def __init__(self):
        self.detector = WhatIssueDetector()

    async def get_findings(self, project_id: int, session) -> list[Finding]:
        issues = await self.detector.detect(project_id, session)
        findings: list[Finding] = []

        # Separate FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO for aggregation
        pair_issues = [i for i in issues if i.code == "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO"]
        other_issues = [i for i in issues if i.code != "FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO"]

        # 1. Individual pair items as ISSUE (逐项修复)
        for issue in pair_issues:
            findings.append(
                make_finding(
                    stage=IssueStage.WHAT,
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

            if issue.code in ("ACTOR_WITHOUT_FEATURE", "DUPLICATE_SCENARIO_NAME"):
                finding_type = FindingType.QUALITY_HINT
            elif issue.code == "SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA":
                finding_type = FindingType.QUALITY_HINT
            elif issue.code in ("LEAF_FEATURE_WITHOUT_ACTOR", "SCENARIO_ACTOR_NOT_IN_FEATURE_ACTORS"):
                finding_type = FindingType.ISSUE
                blocking_scope = BlockingScope.STAGE_TRANSITION

            findings.append(
                make_finding(
                    stage=IssueStage.WHAT,
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

        # 3. Aggregate FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO as GATE_CONDITION
        if pair_issues:
            missing_pairs = [
                {
                    "feature_id": i.metadata.get("feature_id"),
                    "actor_id": i.metadata.get("actor_id"),
                    "description": i.description,
                }
                for i in pair_issues if i.metadata
            ]
            findings.append(
                make_finding(
                    stage=IssueStage.WHAT,
                    code="FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO",
                    severity=IssueSeverity.WARNING,
                    title="功能与参与者组合缺少场景",
                    description=f"检测到有 {len(pair_issues)} 个功能与参与者的组合尚未关联典型场景，这会阻碍进入 How 阶段。",
                    finding_type=FindingType.GATE_CONDITION,
                    blocking_scope=BlockingScope.STAGE_TRANSITION,
                    action_code="open_scenario_relation_panel",
                    metadata={"missing_pairs": missing_pairs},
                    finding_id_override="what:FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO:aggregate",
                )
            )

        return findings
