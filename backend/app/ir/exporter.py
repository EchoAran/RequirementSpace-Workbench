from __future__ import annotations

from typing import Any

from .validators import validate_ir


def _by_kind(nodes: dict[str, dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [n for n in nodes.values() if n.get("kind") == kind]


def _title(nodes: dict[str, dict[str, Any]], node_id: str) -> str:
    n = nodes.get(node_id)
    return (n or {}).get("title") or node_id


def _group_links(links: list[dict[str, Any]], link_type: str) -> list[dict[str, Any]]:
    return [l for l in links if l.get("type") == link_type]


def export_markdown(ir_payload: dict[str, Any]) -> str:
    ir = validate_ir(ir_payload).model_dump()

    nodes: dict[str, dict[str, Any]] = ir.get("nodes") or {}
    links: list[dict[str, Any]] = ir.get("links") or []
    slots: dict[str, dict[str, Any]] = ir.get("slots") or {}
    issues: dict[str, dict[str, Any]] = ir.get("issues") or {}
    choice_groups: dict[str, dict[str, Any]] = ir.get("choiceGroups") or {}

    idea = ir.get("idea") or ""
    name = ir.get("name") or ir.get("id") or "RequirementSpace"

    lines: list[str] = []
    lines.append(f"# {name}")
    lines.append("")
    lines.append("## 项目概述")
    lines.append(f"- 项目 ID：{ir.get('id')}")
    lines.append("")
    lines.append("## 原始想法")
    lines.append(idea or "（空）")
    lines.append("")

    goals = _by_kind(nodes, "goal")
    lines.append("## 目标与成功标准")
    if goals:
        for g in goals:
            lines.append(f"- {g.get('title')}")
            if g.get("description"):
                lines.append(f"  - 说明：{g.get('description')}")
            sc = g.get("successCriteria")
            if isinstance(sc, list) and sc:
                lines.append("  - 成功标准：")
                for c in sc:
                    lines.append(f"    - {c}")
    else:
        lines.append("- （未定义）")
    lines.append("")

    actors = _by_kind(nodes, "actor")
    lines.append("## 角色与职责")
    if actors:
        for a in actors:
            lines.append(f"- {a.get('title')}")
            if a.get("description"):
                lines.append(f"  - 说明：{a.get('description')}")
    else:
        lines.append("- （未定义）")
    lines.append("")

    capabilities = _by_kind(nodes, "capability")
    tasks = _by_kind(nodes, "task")
    lines.append("## 核心能力")
    if capabilities:
        for c in capabilities:
            tag = c.get("priority") or ""
            prefix = f"[{tag}] " if tag else ""
            lines.append(f"- {prefix}{c.get('title')}")
            if c.get("description"):
                lines.append(f"  - 说明：{c.get('description')}")
    else:
        lines.append("- （未定义）")
    lines.append("")

    lines.append("## 关键任务")
    if tasks:
        for t in tasks:
            lines.append(f"- {t.get('title')}")
            if t.get("description"):
                lines.append(f"  - 说明：{t.get('description')}")
            performer_ids = [
                l.get("targetId")
                for l in _group_links(links, "performed_by")
                if l.get("sourceId") == t.get("id") and l.get("targetId")
            ]
            if performer_ids:
                lines.append(f"  - 执行者：{', '.join(_title(nodes, pid) for pid in performer_ids)}")
            if t.get("result"):
                lines.append(f"  - 结果：{t.get('result')}")
    else:
        lines.append("- （未定义）")
    lines.append("")

    flow_steps = _by_kind(nodes, "flow_step")
    precedes = _group_links(links, "precedes")
    branches = _group_links(links, "branches_to")

    def _ordered_steps() -> list[str]:
        step_ids = {s.get("id") for s in flow_steps if s.get("id")}
        indeg = {sid: 0 for sid in step_ids}
        outgoing = {sid: [] for sid in step_ids}
        for l in precedes:
            s = l.get("sourceId")
            t = l.get("targetId")
            if s in step_ids and t in step_ids:
                outgoing[s].append(t)
                indeg[t] += 1
        starts = [sid for sid, d in indeg.items() if d == 0]
        if not starts:
            return [s.get("id") for s in flow_steps if s.get("id")]
        order: list[str] = []
        visited: set[str] = set()
        stack = list(starts)
        while stack:
            cur = stack.pop(0)
            if cur in visited:
                continue
            visited.add(cur)
            order.append(cur)
            for nxt in outgoing.get(cur, []):
                if nxt not in visited:
                    stack.append(nxt)
        for sid in step_ids:
            if sid not in visited:
                order.append(sid)
        return order

    lines.append("## 主流程")
    if flow_steps:
        performed_by_links = _group_links(links, "performed_by")
        for sid in _ordered_steps():
            step = nodes.get(sid) or {}
            performer_ids = [
                l.get("targetId")
                for l in performed_by_links
                if l.get("sourceId") == sid and l.get("targetId")
            ]
            who = ", ".join(_title(nodes, pid) for pid in performer_ids) if performer_ids else "（未指定）"
            st = step.get("stepType") or ""
            st_tag = f"（{st}）" if st else ""
            lines.append(f"- {step.get('title')}{st_tag} - 执行者：{who}")
    else:
        lines.append("- （未定义）")
    lines.append("")

    lines.append("## 异常流程")
    if branches:
        for l in branches:
            s = l.get("sourceId")
            t = l.get("targetId")
            if not s or not t:
                continue
            lines.append(f"- {_title(nodes, s)} -> {_title(nodes, t)}")
    else:
        lines.append("- （未定义）")
    lines.append("")

    rules = _by_kind(nodes, "rule")
    lines.append("## 业务规则")
    if rules:
        for r in rules:
            lines.append(f"- {r.get('title')}")
            if r.get("naturalLanguage"):
                lines.append(f"  - 规则：{r.get('naturalLanguage')}")
            elif r.get("expression"):
                lines.append(f"  - 表达式：{r.get('expression')}")
    else:
        lines.append("- （未定义）")
    lines.append("")

    business_objects = _by_kind(nodes, "business_object")
    fields = _by_kind(nodes, "field")
    lines.append("## 业务对象与状态")
    if business_objects:
        for obj in business_objects:
            oid = obj.get("id")
            lines.append(f"- {obj.get('title')}")
            if obj.get("description"):
                lines.append(f"  - 说明：{obj.get('description')}")
            if oid:
                obj_fields = [f for f in fields if f.get("objectId") == oid]
                if obj_fields:
                    lines.append("  - 字段：")
                    for f in obj_fields[:20]:
                        lines.append(f"    - {f.get('title')}")
    else:
        lines.append("- （未定义）")
    lines.append("")

    screens = _by_kind(nodes, "screen")
    ui_components = _by_kind(nodes, "ui_component")
    displayed_on = _group_links(links, "displayed_on")
    reads = _group_links(links, "reads")
    accessible_by = _group_links(links, "accessible_by")
    contains = _group_links(links, "contains")

    lines.append("## 页面与交互组件")
    if screens:
        for s in screens:
            sid = s.get("id")
            lines.append(f"- 页面：{s.get('title')}")
            if s.get("description"):
                lines.append(f"  - 说明：{s.get('description')}")
            if sid:
                actor_ids = [
                    l.get("targetId")
                    for l in (accessible_by + reads)
                    if l.get("sourceId") == sid and l.get("targetId")
                ]
                if actor_ids:
                    lines.append(f"  - 可访问角色：{', '.join(_title(nodes, aid) for aid in actor_ids)}")

                comp_ids = [l.get("sourceId") for l in displayed_on if l.get("targetId") == sid and l.get("sourceId")]
                if not comp_ids:
                    comp_ids = [l.get("targetId") for l in contains if l.get("sourceId") == sid and l.get("targetId")]
                if comp_ids:
                    lines.append("  - 组件：")
                    for cid in comp_ids[:30]:
                        lines.append(f"    - {_title(nodes, cid)}")
    else:
        lines.append("- （未定义）")
    lines.append("")

    lines.append("## 本期范围")
    in_scope = [n for n in nodes.values() if n.get("scopeStatus") == "in_scope"]
    if in_scope:
        for n in in_scope:
            lines.append(f"- {n.get('title')}（{n.get('kind')}）")
    else:
        lines.append("- （未定义）")
    lines.append("")

    lines.append("## 暂缓项")
    deferred = [n for n in nodes.values() if n.get("scopeStatus") == "deferred"]
    if deferred:
        for n in deferred:
            lines.append(f"- {n.get('title')}（{n.get('kind')}）")
    else:
        lines.append("- （无）")
    lines.append("")

    lines.append("## 外部依赖")
    deps = [n for n in nodes.values() if n.get("scopeStatus") == "external_dependency"]
    if deps:
        for n in deps:
            lines.append(f"- {n.get('title')}（{n.get('kind')}）")
    else:
        lines.append("- （无）")
    lines.append("")

    lines.append("## 待确认问题")
    open_issues = [i for i in issues.values() if i.get("status") == "open"]
    if open_issues:
        for i in open_issues:
            lines.append(f"- [{i.get('severity')}] {i.get('title')}")
            if i.get("description"):
                lines.append(f"  - {i.get('description')}")
    else:
        lines.append("- （无）")
    lines.append("")

    lines.append("## 已采纳候选记录")
    selected_choices: list[dict[str, Any]] = []
    for cg in choice_groups.values():
        for c in cg.get("choices") or []:
            if c.get("status") == "selected":
                selected_choices.append(c)
    if selected_choices:
        for c in selected_choices:
            lines.append(f"- {c.get('title')}")
            if c.get("rationale"):
                lines.append(f"  - 原因：{c.get('rationale')}")
    else:
        lines.append("- （无）")

    return "\n".join(lines).strip() + "\n"
