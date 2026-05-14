from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .. import models


@dataclass(frozen=True)
class DiagnosticIssue:
    title: str
    description: str
    severity: str
    category: str
    related_node_ids: list[str]
    suggested_projection: str
    suggested_action: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "category": self.category,
            "relatedNodeIds": self.related_node_ids,
            "suggestedProjection": self.suggested_projection,
            "suggestedAction": self.suggested_action,
            "status": "open",
            "source": {"type": "system"},
        }


def _by_kind(nodes: list[models.Node]) -> dict[str, list[models.Node]]:
    res: dict[str, list[models.Node]] = {}
    for n in nodes:
        res.setdefault(n.kind, []).append(n)
    return res


def _link_index(links: list[models.Link]) -> tuple[dict[str, list[models.Link]], dict[str, list[models.Link]]]:
    incoming: dict[str, list[models.Link]] = {}
    outgoing: dict[str, list[models.Link]] = {}
    for l in links:
        outgoing.setdefault(l.source_id, []).append(l)
        incoming.setdefault(l.target_id, []).append(l)
    return incoming, outgoing


def run_deterministic_diagnosis(ws: models.Workspace) -> list[DiagnosticIssue]:
    nodes = list(ws.nodes or [])
    links = list(ws.links or [])
    by_kind = _by_kind(nodes)
    incoming, outgoing = _link_index(links)
    node_by_id = {n.id: n for n in nodes}

    issues: list[DiagnosticIssue] = []

    actors = by_kind.get("actor", [])
    if not actors:
        issues.append(
            DiagnosticIssue(
                title="缺少参与角色",
                description="当前需求空间没有角色节点，无法形成责任闭环。",
                severity="high",
                category="missing",
                related_node_ids=[],
                suggested_projection="role",
                suggested_action="请补充至少一个业务角色。",
            )
        )

    capabilities = by_kind.get("capability", [])
    tasks = by_kind.get("task", [])
    task_ids = {t.id for t in tasks}

    for cap in capabilities:
        supported_tasks = [
            l.source_id
            for l in incoming.get(cap.id, [])
            if l.type == "supports" and l.source_id in task_ids
        ]
        if not supported_tasks:
            issues.append(
                DiagnosticIssue(
                    title="能力缺少任务支撑",
                    description=f"能力 `{cap.title}` 当前没有任何任务（Task）支撑，无法落到可执行层。",
                    severity="high",
                    category="missing",
                    related_node_ids=[cap.id],
                    suggested_projection="goal",
                    suggested_action="为该能力补充 1-3 个关键任务，并用 supports 链接到能力。",
                )
            )

    actor_ids = {a.id for a in actors}
    for task in tasks:
        performed_by = [
            l.target_id
            for l in outgoing.get(task.id, [])
            if l.type == "performed_by" and l.target_id in actor_ids
        ]
        if not performed_by:
            issues.append(
                DiagnosticIssue(
                    title="任务缺少责任角色",
                    description=f"任务 `{task.title}` 没有关联责任角色，无法形成责任闭环。",
                    severity="high",
                    category="missing",
                    related_node_ids=[task.id],
                    suggested_projection="role",
                    suggested_action="为该任务关联一个或多个角色（performed_by）。",
                )
            )

    flow_steps = by_kind.get("flow_step", [])
    step_ids = {s.id for s in flow_steps}

    if not flow_steps:
        issues.append(
            DiagnosticIssue(
                title="缺少流程步骤",
                description="当前需求空间没有流程步骤，无法执行预览验证。",
                severity="high",
                category="flow_gap",
                related_node_ids=[],
                suggested_projection="system",
                suggested_action="请补充主流程步骤。",
            )
        )
    else:
        in_degree = {sid: 0 for sid in step_ids}
        out_degree = {sid: 0 for sid in step_ids}
        out_branches = {sid: 0 for sid in step_ids}

        for l in links:
            if l.type == "precedes" and l.source_id in step_ids and l.target_id in step_ids:
                out_degree[l.source_id] += 1
                in_degree[l.target_id] += 1
            if l.type == "branches_to" and l.source_id in step_ids and l.target_id in step_ids:
                out_branches[l.source_id] += 1

        start_candidates = [sid for sid, deg in in_degree.items() if deg == 0]
        if not start_candidates:
            issues.append(
                DiagnosticIssue(
                    title="流程缺少开始节点",
                    description="所有流程步骤都存在前置步骤，导致无法确定主流程开始点。",
                    severity="high",
                    category="flow_gap",
                    related_node_ids=list(step_ids)[:6],
                    suggested_projection="system",
                    suggested_action="补充一个没有前置的开始步骤，或修正 precedes 链接方向。",
                )
            )

        end_candidates = [
            sid for sid in step_ids if out_degree.get(sid, 0) == 0 and out_branches.get(sid, 0) == 0
        ]
        if not end_candidates:
            issues.append(
                DiagnosticIssue(
                    title="流程缺少结束节点",
                    description="所有流程步骤都有后续步骤或分支，导致无法确定主流程结束点。",
                    severity="high",
                    category="flow_gap",
                    related_node_ids=list(step_ids)[:6],
                    suggested_projection="system",
                    suggested_action="补充一个终止步骤（无后续 precedes / branches_to）。",
                )
            )

        for step in flow_steps:
            performed_by = [
                l.target_id
                for l in outgoing.get(step.id, [])
                if l.type == "performed_by" and l.target_id in actor_ids
            ]
            if not performed_by:
                issues.append(
                    DiagnosticIssue(
                        title="流程步骤缺少执行者",
                        description=f"流程步骤 `{step.title}` 缺少 performed_by 执行者，无法归入泳道。",
                        severity="high",
                        category="flow_gap",
                        related_node_ids=[step.id],
                        suggested_projection="system",
                        suggested_action="为该步骤关联执行者角色（performed_by）。",
                    )
                )

            step_type = str((step.extra or {}).get("stepType") or "")
            if ("判断" in step_type or "decision" in step_type.lower()) and out_branches.get(step.id, 0) == 0:
                issues.append(
                    DiagnosticIssue(
                        title="判断步骤缺少分支",
                        description=f"判断步骤 `{step.title}` 没有任何 branches_to 分支，异常路径不可见。",
                        severity="high",
                        category="flow_gap",
                        related_node_ids=[step.id],
                        suggested_projection="system",
                        suggested_action="为该判断步骤补充分支（branches_to）并说明条件。",
                    )
                )

    in_scope_caps = [
        c for c in capabilities if _safe_scope_status(c) == "in_scope"
    ]
    for cap in in_scope_caps:
        cap_task_ids = [
            l.source_id
            for l in incoming.get(cap.id, [])
            if l.type == "supports" and l.source_id in task_ids
        ]
        if not cap_task_ids:
            continue
        supported_by_flow = False
        for tid in cap_task_ids:
            for l in incoming.get(tid, []):
                if l.type == "supports" and l.source_id in step_ids:
                    supported_by_flow = True
                    break
            if supported_by_flow:
                break
        if not supported_by_flow:
            issues.append(
                DiagnosticIssue(
                    title="本期能力缺少流程支撑",
                    description=f"能力 `{cap.title}` 标记为本期范围（in_scope），但没有任何流程步骤支撑其任务，可能无法落地交付。",
                    severity="high",
                    category="scope_risk",
                    related_node_ids=[cap.id],
                    suggested_projection="system",
                    suggested_action="为关联任务补充流程步骤，并用 supports 链接到任务。",
                )
            )

    business_objects = by_kind.get("business_object", [])
    fields = by_kind.get("field", [])
    state_machines = by_kind.get("state_machine", [])
    object_states = by_kind.get("object_state", [])
    state_transitions = by_kind.get("state_transition", [])

    for obj in business_objects:
        has_field = any((f.extra or {}).get("objectId") == obj.id for f in fields)
        if not has_field:
            issues.append(
                DiagnosticIssue(
                    title="业务对象缺少字段定义",
                    description=f"业务对象 `{obj.title}` 当前没有字段（Field）定义，无法表达数据结构与校验。",
                    severity="medium",
                    category="data_gap",
                    related_node_ids=[obj.id],
                    suggested_projection="data",
                    suggested_action="为该对象补充关键字段，并将 Field.objectId 指向该对象。",
                )
            )

        has_state = any((sm.extra or {}).get("objectId") == obj.id for sm in state_machines) or any(
            (s.extra or {}).get("objectId") == obj.id for s in object_states
        )
        if not has_state:
            issues.append(
                DiagnosticIssue(
                    title="业务对象缺少状态模型",
                    description=f"业务对象 `{obj.title}` 当前没有状态（State）/状态机定义，流程无法表达状态迁移。",
                    severity="medium",
                    category="data_gap",
                    related_node_ids=[obj.id],
                    suggested_projection="data",
                    suggested_action="为该对象补充状态机与状态列表，并定义关键状态迁移。",
                )
            )

    transition_ids = {t.id for t in state_transitions}
    for tr in state_transitions:
        trigger_step_id = (tr.extra or {}).get("triggerStepId")
        has_changes_state = any(
            l.type == "changes_state" and l.source_id in step_ids and l.target_id == tr.id for l in incoming.get(tr.id, [])
        )
        if (trigger_step_id and trigger_step_id not in step_ids) or (not trigger_step_id and not has_changes_state):
            issues.append(
                DiagnosticIssue(
                    title="状态迁移缺少触发流程",
                    description=f"状态迁移 `{tr.title}` 没有关联触发步骤（FlowStep），状态变化原因不可追溯。",
                    severity="medium",
                    category="data_gap",
                    related_node_ids=[tr.id],
                    suggested_projection="system",
                    suggested_action="用 changes_state 链接流程步骤到该状态迁移，或补充 triggerStepId。",
                )
            )

    screens = by_kind.get("screen", [])
    for screen in screens:
        linked = [
            l.target_id
            for l in outgoing.get(screen.id, [])
            if l.type in {"accessible_by", "reads"} and l.target_id in actor_ids
        ]
        if not linked:
            issues.append(
                DiagnosticIssue(
                    title="页面缺少可访问角色",
                    description=f"页面 `{screen.title}` 没有关联可访问角色，无法形成角色视角原型。",
                    severity="medium",
                    category="ui_gap",
                    related_node_ids=[screen.id],
                    suggested_projection="ui",
                    suggested_action="用 accessible_by（或 reads 兼容）将页面关联到至少一个角色。",
                )
            )

    ui_components = by_kind.get("ui_component", [])
    for comp in ui_components:
        comp_type = str((comp.extra or {}).get("componentType") or "")
        is_action_like = "button" in comp_type.lower() or "button" in comp.title.lower() or "action" in comp.title.lower()
        if not is_action_like:
            continue
        has_binding = any(
            l.type in {"invokes_step", "triggered_by"} and l.source_id == comp.id and l.target_id in step_ids
            for l in outgoing.get(comp.id, [])
        )
        if not has_binding:
            issues.append(
                DiagnosticIssue(
                    title="UI 操作缺少流程绑定",
                    description=f"交互组件 `{comp.title}` 看起来是可执行动作，但没有绑定任何流程步骤（FlowStep）。",
                    severity="medium",
                    category="ui_gap",
                    related_node_ids=[comp.id],
                    suggested_projection="ui",
                    suggested_action="用 invokes_step（或 triggered_by 兼容）将该组件绑定到对应流程步骤。",
                )
            )

    for f in fields:
        if not (f.extra or {}).get("objectId"):
            issues.append(
                DiagnosticIssue(
                    title="字段缺少业务对象归属",
                    description=f"字段 `{f.title}` 没有 objectId 归属，无法映射到业务对象。",
                    severity="low",
                    category="data_gap",
                    related_node_ids=[f.id],
                    suggested_projection="data",
                    suggested_action="为字段补充 objectId，指向所属业务对象。",
                )
            )

    return issues


def _safe_scope_status(node: models.Node) -> str | None:
    if node.scope_status:
        return node.scope_status
    raw = (node.extra or {}).get("scopeStatus")
    return raw

