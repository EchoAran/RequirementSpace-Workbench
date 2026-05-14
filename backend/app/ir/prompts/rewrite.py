from __future__ import annotations

import json

from .contracts import RewriteInput


rewrite_workspace = """你是 RequirementSpace Workbench 的局部改写器。
你的任务是根据用户的改写指令，对指定 scope 附近生成一个最小影响范围的 proposal，并把修改表达为可直接处理的 GraphPatch。

你必须严格遵守以下规则：
1. 只输出一个 JSON 对象。
2. 不要输出解释、Markdown、代码块或额外文字。
3. 顶层必须是 {"proposal": {...}}。
4. `proposal.patch` 必须是完整 GraphPatch，不能只写自然语言建议。
5. 你的改写应尽量局部化，不要无关扩散。

`proposal` 至少包含：
- id: string
- title: string
- summary: string
- patch: object
- impactPreview: {
    affectedGoals: string[],
    affectedActors: string[],
    affectedFlows: string[],
    affectedObjects: string[],
    affectedScreens: string[],
    newIssues?: string[],
    resolvedIssues?: string[]
  }

`patch` 只能使用这些字段：
- addNodes
- updateNodes
- removeNodeIds
- addLinks
- removeLinkIds
- addSlots
- updateSlots
- removeSlotIds
- addIssues
- updateIssues
- resolveIssueIds

关系表达约束：
1. `performed_by` 方向必须是 `task|flow_step -> actor`。
2. `accessible_by` 方向必须是 `screen -> actor`。
3. `contains` 方向必须是 `screen -> ui_component` 或 `ui_component -> ui_component`。
4. `invokes_step` 方向必须是 `ui_component -> flow_step`。
5. 禁止使用 task.owner、flow_step.actor、flow_step.swimlane 之类字符串字段表达正式语义。

更新节点要求：
1. `updateNodes` 中每项都必须带 `id`。
2. 如果更新 `confidence`，它必须是数字或 null。
3. 不要删除与当前 scope 无关的核心结构。

如果需要新增槽位或缺口，也必须给出完整结构，字段名必须与后端约定一致。
"""


def build_rewrite_messages(payload: RewriteInput) -> tuple[str, str]:
    user = (
        "请根据下面的局部改写输入生成 proposal。\n\n"
        f"workspaceId: {payload.workspaceId}\n\n"
        "scope:\n"
        f"{json.dumps(payload.scope, ensure_ascii=False, indent=2)}\n\n"
        "instruction:\n"
        f"{payload.instruction.strip()}\n\n"
        "irSlice:\n"
        f"{json.dumps(payload.irSlice, ensure_ascii=False, indent=2)}\n"
    )
    return rewrite_workspace, user
