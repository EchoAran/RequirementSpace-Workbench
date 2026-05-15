from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .schema import (
    FlowStepType,
    IssueCategory,
    NodeKind,
    ProjectionKind,
    RequirementLink,
    RequirementNode,
    RequirementSpaceIR,
    ScopeStatus,
    Severity,
    UIComponentType,
)


@dataclass(frozen=True)
class DiagnosticIssue:
    title: str
    description: str
    severity: Severity
    category: IssueCategory
    related_node_ids: list[str]
    suggested_projection: ProjectionKind
    suggested_action: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "category": self.category.value,
            "relatedNodeIds": self.related_node_ids,
            "suggestedProjection": self.suggested_projection.value,
            "suggestedAction": self.suggested_action,
            "status": "open",
            "source": {"type": "system"},
        }


def run_deterministic_diagnosis(ir: RequirementSpaceIR) -> list[DiagnosticIssue]:
    nodes = list(ir.nodes.values())
    links = list(ir.links)
    by_kind = _by_kind(nodes)
    incoming, outgoing = _link_index(links)

    issues: list[DiagnosticIssue] = []

    actors = by_kind.get(NodeKind.ACTOR, [])
    goals = by_kind.get(NodeKind.GOAL, [])
    capabilities = by_kind.get(NodeKind.CAPABILITY, [])
    tasks = by_kind.get(NodeKind.TASK, [])
    flow_steps = by_kind.get(NodeKind.FLOW_STEP, [])
    business_objects = by_kind.get(NodeKind.BUSINESS_OBJECT, [])
    fields = by_kind.get(NodeKind.FIELD, [])
    state_machines = by_kind.get(NodeKind.STATE_MACHINE, [])
    state_transitions = by_kind.get(NodeKind.STATE_TRANSITION, [])
    screens = by_kind.get(NodeKind.SCREEN, [])
    ui_components = by_kind.get(NodeKind.UI_COMPONENT, [])

    actor_ids = {node.id for node in actors}
    capability_ids = {node.id for node in capabilities}
    task_ids = {node.id for node in tasks}
    step_ids = {node.id for node in flow_steps}
    field_ids = {node.id for node in fields}
    state_machine_ids = {node.id for node in state_machines}
    transition_ids = {node.id for node in state_transitions}

    if not actors:
        issues.append(
            DiagnosticIssue(
                title="缺少参与角色",
                description="当前需求空间没有角色节点，无法形成责任闭环。",
                severity=Severity.HIGH,
                category=IssueCategory.MISSING,
                related_node_ids=[],
                suggested_projection=ProjectionKind.ROLE,
                suggested_action="请补充至少一个业务角色。",
            )
        )

    for goal in goals:
        realized_capabilities = [
            link.sourceId
            for link in incoming.get(goal.id, [])
            if link.type.value == "realizes" and link.sourceId in capability_ids
        ]
        if not realized_capabilities:
            issues.append(
                DiagnosticIssue(
                    title="目标缺少能力承接",
                    description=f"目标 `{goal.title}` 当前没有任何 Capability 承接，无法继续细化实现路径。",
                    severity=Severity.HIGH,
                    category=IssueCategory.MISSING,
                    related_node_ids=[goal.id],
                    suggested_projection=ProjectionKind.GOAL,
                    suggested_action="为该目标补充至少一个 Capability，并用 realizes 连接到 Goal。",
                )
            )

    for capability in capabilities:
        supported_tasks = [
            link.sourceId
            for link in incoming.get(capability.id, [])
            if link.type.value == "supports" and link.sourceId in task_ids
        ]
        if not supported_tasks:
            issues.append(
                DiagnosticIssue(
                    title="能力缺少任务支撑",
                    description=f"能力 `{capability.title}` 当前没有任何任务支撑，无法落到可执行层。",
                    severity=Severity.HIGH,
                    category=IssueCategory.MISSING,
                    related_node_ids=[capability.id],
                    suggested_projection=ProjectionKind.GOAL,
                    suggested_action="为该能力补充 1-3 个关键任务，并用 supports 链接到能力。",
                )
            )

    for task in tasks:
        if not _has_actor_binding(task.id, outgoing, actor_ids):
            issues.append(
                DiagnosticIssue(
                    title="任务缺少责任角色",
                    description=f"任务 `{task.title}` 没有关联责任角色，无法形成责任闭环。",
                    severity=Severity.HIGH,
                    category=IssueCategory.MISSING,
                    related_node_ids=[task.id],
                    suggested_projection=ProjectionKind.ROLE,
                    suggested_action="为该任务关联一个或多个角色（performed_by）。",
                )
            )
        supporting_steps = [
            link.sourceId
            for link in incoming.get(task.id, [])
            if link.type.value == "supports" and link.sourceId in step_ids
        ]
        if not supporting_steps:
            issues.append(
                DiagnosticIssue(
                    title="任务缺少流程步骤支撑",
                    description=f"任务 `{task.title}` 没有关联任何 FlowStep，无法进入系统流程验证。",
                    severity=Severity.HIGH,
                    category=IssueCategory.FLOW_GAP,
                    related_node_ids=[task.id],
                    suggested_projection=ProjectionKind.SYSTEM,
                    suggested_action="为该任务补充至少一个 FlowStep，并用 supports 连接到 Task。",
                )
            )

    if not flow_steps:
        issues.append(
            DiagnosticIssue(
                title="缺少流程步骤",
                description="当前需求空间没有流程步骤，无法执行流程验证。",
                severity=Severity.HIGH,
                category=IssueCategory.FLOW_GAP,
                related_node_ids=[],
                suggested_projection=ProjectionKind.SYSTEM,
                suggested_action="请补充主流程步骤。",
            )
        )
    else:
        global_start_candidates = [
            step_id
            for step_id in step_ids
            if not any(
                link.type.value == "precedes" and link.sourceId in step_ids
                for link in incoming.get(step_id, [])
            )
        ]
        global_end_candidates = [
            step_id
            for step_id in step_ids
            if not any(
                link.type.value in {"precedes", "branches_to"} and link.targetId in step_ids
                for link in outgoing.get(step_id, [])
            )
        ]
        if not global_start_candidates:
            issues.append(
                DiagnosticIssue(
                    title="系统步骤图缺少开始节点",
                    description="当前 FlowStep 网络中所有步骤都有前置 precedes，无法识别系统入口步骤。",
                    severity=Severity.HIGH,
                    category=IssueCategory.FLOW_GAP,
                    related_node_ids=sorted(step_ids)[:6],
                    suggested_projection=ProjectionKind.SYSTEM,
                    suggested_action="补充一个没有前置 precedes 的开始步骤，或修正步骤连接方向。",
                )
            )
        if not global_end_candidates:
            issues.append(
                DiagnosticIssue(
                    title="系统步骤图缺少结束节点",
                    description="当前 FlowStep 网络中所有步骤都有后续 precedes 或 branches_to，无法识别系统收敛点。",
                    severity=Severity.HIGH,
                    category=IssueCategory.FLOW_GAP,
                    related_node_ids=sorted(step_ids)[:6],
                    suggested_projection=ProjectionKind.SYSTEM,
                    suggested_action="补充一个没有后续 precedes / branches_to 的结束步骤。",
                )
            )
        for step in flow_steps:
            if not _has_actor_binding(step.id, outgoing, actor_ids):
                issues.append(
                    DiagnosticIssue(
                        title="流程步骤缺少执行者",
                        description=f"流程步骤 `{step.title}` 缺少 performed_by 执行者，无法归入泳道。",
                        severity=Severity.HIGH,
                        category=IssueCategory.FLOW_GAP,
                        related_node_ids=[step.id],
                        suggested_projection=ProjectionKind.SYSTEM,
                        suggested_action="为该步骤关联执行者角色（performed_by）。",
                    )
                )

            step_type = getattr(step, "stepType", None)
            step_branch_count = sum(
                1
                for link in outgoing.get(step.id, [])
                if link.type.value == "branches_to" and link.targetId in step_ids
            )
            if step_type == FlowStepType.DECISION and step_branch_count == 0:
                issues.append(
                    DiagnosticIssue(
                        title="判断步骤缺少分支",
                        description=f"判断步骤 `{step.title}` 没有任何 branches_to 分支，异常路径不可见。",
                        severity=Severity.HIGH,
                        category=IssueCategory.FLOW_GAP,
                        related_node_ids=[step.id],
                        suggested_projection=ProjectionKind.SYSTEM,
                        suggested_action="为该判断步骤补充分支（branches_to）并说明条件。",
                    )
                )

    for capability in capabilities:
        if capability.scopeStatus != ScopeStatus.IN_SCOPE:
            continue
        task_ids_for_capability = [
            link.sourceId
            for link in incoming.get(capability.id, [])
            if link.type.value == "supports" and link.sourceId in task_ids
        ]
        if task_ids_for_capability and not any(
            link.type.value == "supports" and link.sourceId in step_ids
            for task_id in task_ids_for_capability
            for link in incoming.get(task_id, [])
        ):
            issues.append(
                DiagnosticIssue(
                    title="本期能力缺少流程支撑",
                    description=f"能力 `{capability.title}` 标记为本期范围，但没有流程步骤支撑其任务，可能无法落地交付。",
                    severity=Severity.HIGH,
                    category=IssueCategory.SCOPE_RISK,
                    related_node_ids=[capability.id],
                    suggested_projection=ProjectionKind.SYSTEM,
                    suggested_action="为关联任务补充流程步骤，并用 supports 链接到任务。",
                )
            )

    for business_object in business_objects:
        contains_field = any(
            link.type.value == "contains" and link.sourceId == business_object.id and link.targetId in field_ids
            for link in outgoing.get(business_object.id, [])
        )
        if not contains_field:
            issues.append(
                DiagnosticIssue(
                    title="业务对象缺少字段定义",
                    description=f"业务对象 `{business_object.title}` 当前没有字段定义，无法表达数据结构与校验。",
                    severity=Severity.MEDIUM,
                    category=IssueCategory.DATA_GAP,
                    related_node_ids=[business_object.id],
                    suggested_projection=ProjectionKind.DATA,
                    suggested_action="为该对象补充关键字段，并用 contains 链接到 Field。",
                )
            )

        contains_state_machine = any(
            link.type.value == "contains" and link.sourceId == business_object.id and link.targetId in state_machine_ids
            for link in outgoing.get(business_object.id, [])
        )
        if not contains_state_machine:
            issues.append(
                DiagnosticIssue(
                    title="业务对象缺少状态模型",
                    description=f"业务对象 `{business_object.title}` 当前没有状态机定义，流程无法表达状态迁移。",
                    severity=Severity.MEDIUM,
                    category=IssueCategory.DATA_GAP,
                    related_node_ids=[business_object.id],
                    suggested_projection=ProjectionKind.DATA,
                    suggested_action="为该对象补充状态机，并用 contains 链接状态与迁移。",
                )
            )

    for transition in state_transitions:
        has_trigger_step = any(
            link.type.value == "changes_state" and link.sourceId in step_ids and link.targetId == transition.id
            for link in incoming.get(transition.id, [])
        )
        if not has_trigger_step:
            issues.append(
                DiagnosticIssue(
                    title="状态迁移缺少触发流程",
                    description=f"状态迁移 `{transition.title}` 没有关联触发步骤，状态变化原因不可追溯。",
                    severity=Severity.MEDIUM,
                    category=IssueCategory.DATA_GAP,
                    related_node_ids=[transition.id],
                    suggested_projection=ProjectionKind.SYSTEM,
                    suggested_action="用 changes_state 将 FlowStep 链接到该状态迁移。",
                )
            )

    for screen in screens:
        has_actor = any(
            link.type.value == "accessible_by" and link.targetId in actor_ids
            for link in outgoing.get(screen.id, [])
        )
        if not has_actor:
            issues.append(
                DiagnosticIssue(
                    title="页面缺少可访问角色",
                    description=f"页面 `{screen.title}` 没有关联可访问角色，无法形成角色视角原型。",
                    severity=Severity.MEDIUM,
                    category=IssueCategory.UI_GAP,
                    related_node_ids=[screen.id],
                    suggested_projection=ProjectionKind.UI,
                    suggested_action="用 accessible_by 将页面关联到至少一个角色。",
                )
            )

    for component in ui_components:
        component_type = getattr(component, "componentType", None)
        is_action_like = (
            component_type == UIComponentType.BUTTON
            or "button" in component.title.lower()
            or "action" in component.title.lower()
        )
        if not is_action_like:
            continue
        has_step_binding = any(
            link.type.value == "invokes_step" and link.targetId in step_ids
            for link in outgoing.get(component.id, [])
        )
        if not has_step_binding:
            issues.append(
                DiagnosticIssue(
                    title="UI 操作缺少流程绑定",
                    description=f"交互组件 `{component.title}` 看起来是可执行动作，但没有绑定任何流程步骤。",
                    severity=Severity.MEDIUM,
                    category=IssueCategory.UI_GAP,
                    related_node_ids=[component.id],
                    suggested_projection=ProjectionKind.UI,
                    suggested_action="用 invokes_step 将该组件绑定到对应流程步骤。",
                )
            )

    contained_fields = {
        link.targetId
        for link in links
        if link.type.value == "contains" and ir.nodes.get(link.sourceId, None) and link.targetId in field_ids
    }
    bound_fields = {
        link.targetId
        for link in links
        if link.type.value == "binds_field" and link.targetId in field_ids
    }
    for field in fields:
        if field.id not in contained_fields:
            issues.append(
                DiagnosticIssue(
                    title="字段缺少业务对象归属",
                    description=f"字段 `{field.title}` 没有归属业务对象，无法映射到数据结构。",
                    severity=Severity.LOW,
                    category=IssueCategory.DATA_GAP,
                    related_node_ids=[field.id],
                    suggested_projection=ProjectionKind.DATA,
                    suggested_action="用 contains 将字段关联到所属业务对象。",
                )
            )
        if field.id not in bound_fields:
            issues.append(
                DiagnosticIssue(
                    title="字段缺少界面绑定",
                    description=f"字段 `{field.title}` 还没有任何 UIComponent 通过 binds_field 绑定，界面输入或展示路径不明确。",
                    severity=Severity.LOW,
                    category=IssueCategory.UI_GAP,
                    related_node_ids=[field.id],
                    suggested_projection=ProjectionKind.UI,
                    suggested_action="补充承载该字段的 UIComponent，并用 binds_field 建立绑定关系。",
                )
            )

    for state_machine in state_machines:
        contains_transition = any(
            link.type.value == "contains" and link.sourceId == state_machine.id and link.targetId in transition_ids
            for link in outgoing.get(state_machine.id, [])
        )
        if not contains_transition:
            issues.append(
                DiagnosticIssue(
                    title="状态机缺少迁移定义",
                    description=f"状态机 `{state_machine.title}` 没有状态迁移定义，生命周期不完整。",
                    severity=Severity.MEDIUM,
                    category=IssueCategory.DATA_GAP,
                    related_node_ids=[state_machine.id],
                    suggested_projection=ProjectionKind.DATA,
                    suggested_action="为状态机补充至少一个状态迁移，并用 contains 关联。",
                )
            )

    return issues


def _by_kind(nodes: list[RequirementNode]) -> dict[NodeKind, list[RequirementNode]]:
    result: dict[NodeKind, list[RequirementNode]] = {}
    for node in nodes:
        result.setdefault(node.kind, []).append(node)
    return result


def _link_index(links: list[RequirementLink]) -> tuple[dict[str, list[RequirementLink]], dict[str, list[RequirementLink]]]:
    incoming: dict[str, list[RequirementLink]] = {}
    outgoing: dict[str, list[RequirementLink]] = {}
    for link in links:
        outgoing.setdefault(link.sourceId, []).append(link)
        incoming.setdefault(link.targetId, []).append(link)
    return incoming, outgoing


def _has_actor_binding(node_id: str, outgoing: dict[str, list[RequirementLink]], actor_ids: set[str]) -> bool:
    return any(
        link.type.value == "performed_by" and link.targetId in actor_ids
        for link in outgoing.get(node_id, [])
    )
