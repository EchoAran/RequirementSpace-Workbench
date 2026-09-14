"""Domain rule quality checks for the HOW stage."""

from __future__ import annotations

from backend.core.detectors.issue_context import IssueProjectContext
from backend.core.model_invariants.rule_invariants import validate_rule_link_purpose
from backend.schemas import Issue, IssueSeverity, IssueStage, IssueTarget


def detect_required_rule_issue(context: IssueProjectContext) -> list[Issue]:
    """Detect flows that exist without the required rule foundation."""
    if not context.flows or context.domain_rules:
        return []
    return [
        Issue(
            code="DOMAIN_RULE_REQUIRED",
            stage=IssueStage.HOW,
            severity=IssueSeverity.BLOCKING,
            title="流程缺少业务规则基础",
            description="业务流程必须依赖至少一条业务规则。",
            target=IssueTarget(
                targetType="project",
                targetId=context.project_id,
            ),
            actionCode="open_domain_rules_panel",
        )
    ]


def detect_rule_quality_issues(context: IssueProjectContext) -> list[Issue]:
    """Detect rule traceability, unapplied rules, and unconfirmed rule usages."""
    issues: list[Issue] = []
    rules_by_id = {rule.rule_id: rule for rule in context.domain_rules}
    rules_by_uuid = {rule.logical_uuid: rule for rule in context.domain_rules}

    rule_sources_map: dict[int, list[str]] = {}
    rule_applications_map: dict[int, list[str]] = {}

    for link in context.rule_links:
        purpose = getattr(link, "link_purpose", None)
        if not purpose or not isinstance(purpose, str):
            raise ValueError(
                f"invalid_rule_link_purpose: rule link {getattr(link, 'link_id', '')} "
                f"is missing link_purpose: {purpose!r}"
            )
        validate_rule_link_purpose(purpose)
        if purpose == "source":
            rule_sources_map.setdefault(link.rule_id, []).append(link.target_logical_uuid)
        elif purpose == "applies_to":
            rule_applications_map.setdefault(link.rule_id, []).append(link.target_logical_uuid)

    for rule in context.domain_rules:
        if rule.origin != "manual" and not rule_sources_map.get(rule.rule_id):
            issues.append(
                Issue(
                    code="RULE_WITHOUT_SOURCE",
                    stage=IssueStage.HOW,
                    severity=IssueSeverity.WARNING,
                    title="规则缺少需求来源",
                    description=f"规则“{rule.title}”为非手工创建，但尚未关联任何需求来源。",
                    target=IssueTarget(
                        targetType="domain_rule",
                        targetId=rule.rule_id,
                    ),
                    actionCode="open_rule_source_panel",
                )
            )

        if not rule_applications_map.get(rule.rule_id):
            issues.append(
                Issue(
                    code="RULE_NOT_APPLIED",
                    stage=IssueStage.HOW,
                    severity=IssueSeverity.INFO,
                    title="规则未应用至流程",
                    description=f"规则“{rule.title}”尚未关联到任何流程、步骤或分支跳转。",
                    target=IssueTarget(
                        targetType="domain_rule",
                        targetId=rule.rule_id,
                    ),
                    actionCode="open_rule_link_panel",
                )
            )

    links_by_target: dict[str, list] = {}
    for link in context.rule_links:
        links_by_target.setdefault(link.target_logical_uuid, []).append(link)

    for flow in context.flows:
        step_uuids = {step.logical_uuid for step in flow.steps if step.logical_uuid}
        trans_uuids = {trans.logical_uuid for trans in flow.transitions if trans.logical_uuid}
        all_flow_uuids = {flow.logical_uuid} | step_uuids | trans_uuids

        if flow.confirmation_status == "confirmed":
            for target_uuid in all_flow_uuids:
                if not target_uuid:
                    continue
                for link in links_by_target.get(target_uuid, []):
                    if link.link_purpose != "applies_to":
                        continue
                    linked_rule = rules_by_id.get(link.rule_id) or rules_by_uuid.get(str(link.rule_id))
                    if linked_rule and linked_rule.confirmation_status != "confirmed":
                        issues.append(
                            Issue(
                                code="FLOW_USES_UNCONFIRMED_RULE",
                                stage=IssueStage.HOW,
                                severity=IssueSeverity.BLOCKING,
                                title="已确认流程依赖未确认规则",
                                description=(
                                    f"流程“{flow.name}”已确认，但引用的规则“{linked_rule.title}”"
                                    "仍处于未确认状态。"
                                ),
                                target=IssueTarget(
                                    targetType="flow",
                                    targetId=flow.flow_id,
                                ),
                                actionCode="open_domain_rules_panel",
                            )
                        )

        # Detect stale rules linked to transitions
        for trans in flow.transitions:
            if not trans.logical_uuid:
                continue
            for link in links_by_target.get(trans.logical_uuid, []):
                if link.link_purpose != "applies_to":
                    continue
                linked_rule = rules_by_id.get(link.rule_id) or rules_by_uuid.get(str(link.rule_id))
                if linked_rule is None or getattr(linked_rule, "confirmation_status", "") == "rejected":
                    issues.append(
                        Issue(
                            code="TRANSITION_RULE_STALE",
                            stage=IssueStage.HOW,
                            severity=IssueSeverity.BLOCKING,
                            title="跳转分支引用了已失效规则",
                            description="流程分支跳转引用的业务规则不存在或已被废弃。",
                            target=IssueTarget(
                                targetType="flow_transition",
                                targetId=trans.transition_id,
                                parentType="flow",
                                parentId=flow.flow_id,
                            ),
                            actionCode="open_flow_transition_panel",
                        )
                    )

    return issues
