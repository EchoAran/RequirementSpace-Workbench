"""Flow graph topology, entry ambiguity, and branch explanation quality checks."""

from __future__ import annotations

import logging

from backend.core.detectors.issue_context import IssueProjectContext
from backend.core.path_projection import project_flow_paths
from backend.schemas import Issue, IssueSeverity, IssueStage, IssueTarget

logger = logging.getLogger(__name__)


def detect_flow_entry_issues(context: IssueProjectContext) -> list[Issue]:
    """Detect ambiguous or missing entry points in flows."""
    issues: list[Issue] = []

    for flow in context.flows:
        if len(flow.steps) <= 1:
            continue

        incoming_counts: dict[int, int] = {step.step_id: 0 for step in flow.steps}

        for trans in flow.transitions:
            if trans.target_step_id in incoming_counts:
                incoming_counts[trans.target_step_id] += 1

        entry_steps = [step_id for step_id, count in incoming_counts.items() if count == 0]

        if len(entry_steps) >= 2:
            issues.append(
                Issue(
                    code="FLOW_ENTRY_AMBIGUOUS",
                    stage=IssueStage.HOW,
                    severity=IssueSeverity.WARNING,
                    title="流程存在多个入口",
                    description=f"流程“{flow.name}”存在 {len(entry_steps)} 个无前驱的入口步骤，入口存在歧义。",
                    target=IssueTarget(
                        targetType="flow",
                        targetId=flow.flow_id,
                    ),
                    actionCode="open_flow_editor",
                )
            )
        elif len(entry_steps) == 0:
            issues.append(
                Issue(
                    code="FLOW_WITHOUT_ENTRY",
                    stage=IssueStage.HOW,
                    severity=IssueSeverity.WARNING,
                    title="流程缺少明确入口",
                    description=f"流程“{flow.name}”所有步骤均有前驱（可能存在闭环），缺少明确起始步骤。",
                    target=IssueTarget(
                        targetType="flow",
                        targetId=flow.flow_id,
                    ),
                    actionCode="open_flow_editor",
                )
            )

    return issues


def detect_branch_explanation_issues(context: IssueProjectContext) -> list[Issue]:
    """Detect unexplained multiple branches and missing default paths."""
    issues: list[Issue] = []

    applies_to_rules_by_target: dict[str, list[int]] = {}
    for link in context.rule_links:
        if link.link_purpose == "applies_to" and link.target_kind == "flow_transition":
            applies_to_rules_by_target.setdefault(link.target_logical_uuid, []).append(link.rule_id)

    for flow in context.flows:
        outgoing_by_source: dict[int, list] = {}
        for trans in flow.transitions:
            outgoing_by_source.setdefault(trans.source_step_id, []).append(trans)

        is_confirmed = flow.confirmation_status == "confirmed"

        for step in flow.steps:
            outgoing = outgoing_by_source.get(step.step_id, [])
            if len(outgoing) < 2:
                continue

            has_default = any(trans.is_default for trans in outgoing)
            if not has_default:
                issues.append(
                    Issue(
                        code="BRANCH_WITHOUT_DEFAULT",
                        stage=IssueStage.HOW,
                        severity=IssueSeverity.INFO,
                        title="多出口缺少默认路径",
                        description=f"步骤“{step.name}”包含 {len(outgoing)} 个出口分支，未标记默认流向。",
                        target=IssueTarget(
                            targetType="flow_step",
                            targetId=step.step_id,
                            parentType="flow",
                            parentId=flow.flow_id,
                        ),
                        actionCode="open_flow_transition_panel",
                    )
                )

            if is_confirmed:
                seen_signatures: set[tuple[str, str, tuple[int, ...]]] = set()
                for trans in outgoing:
                    linked_rule_ids = tuple(sorted(applies_to_rules_by_target.get(trans.logical_uuid, [])))
                    label = (trans.label or "").strip()
                    expr = (trans.condition_text or "").strip()
                    signature = (label, expr, linked_rule_ids)

                    if not label and not expr and not linked_rule_ids:
                        issues.append(
                            Issue(
                                code="BRANCH_WITHOUT_EXPLANATION",
                                stage=IssueStage.HOW,
                                severity=IssueSeverity.BLOCKING,
                                title="已确认分支缺少说明",
                                description=(
                                    f"流程“{flow.name}”已确认，但步骤“{step.name}”的分支跳转"
                                    "缺少区分条件或说明文本。"
                                ),
                                target=IssueTarget(
                                    targetType="flow_transition",
                                    targetId=trans.transition_id,
                                    parentType="flow",
                                    parentId=flow.flow_id,
                                ),
                                actionCode="open_flow_transition_panel",
                            )
                        )
                    elif signature in seen_signatures:
                        issues.append(
                            Issue(
                                code="BRANCH_WITHOUT_EXPLANATION",
                                stage=IssueStage.HOW,
                                severity=IssueSeverity.BLOCKING,
                                title="多出口分支条件不可区分",
                                description=(
                                    f"步骤“{step.name}”的多个出口分支使用了完全相同的标签与条件，"
                                    "分支路径无法明确区分。"
                                ),
                                target=IssueTarget(
                                    targetType="flow_transition",
                                    targetId=trans.transition_id,
                                    parentType="flow",
                                    parentId=flow.flow_id,
                                ),
                                actionCode="open_flow_transition_panel",
                            )
                        )
                    else:
                        seen_signatures.add(signature)

    return issues


def detect_path_truncation_issues(context: IssueProjectContext) -> list[Issue]:
    """Detect flows whose path combinatorial expansion exceeds projection safety limits."""
    issues: list[Issue] = []

    for flow in context.flows:
        summary = project_flow_paths(
            flow.flow_id,
            flow.steps,
            flow.transitions,
        )
        if summary.is_truncated:
            issues.append(
                Issue(
                    code="FLOW_PATH_TRUNCATED",
                    stage=IssueStage.HOW,
                    severity=IssueSeverity.WARNING,
                    title="流程路径展开超出安全限制",
                    description=(
                        f"流程“{flow.name}”的路径组合数超过安全上限 ({summary.total_paths})，"
                        "已自动截断以避免性能退化。"
                    ),
                    target=IssueTarget(
                        targetType="flow",
                        targetId=flow.flow_id,
                    ),
                    actionCode="open_flow_editor",
                )
            )

    return issues
