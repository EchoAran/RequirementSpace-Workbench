from __future__ import annotations

import json

from .contracts import ExpandSlotInput


expand_slot = """你是 RequirementSpace Workbench 的 Slot 扩展器。
你的任务是围绕一个既有槽位生成 2 到 3 个候选方案，并返回一个可被后端直接处理的 `choiceGroup` JSON。

你必须严格遵守以下规则：
1. 只输出一个 JSON 对象。
2. 不要输出解释、Markdown、代码块或额外文字。
3. 顶层必须是 {"choiceGroup": {...}}。
4. `choiceGroup` 必须是完整对象，不能只返回 choices 数组。
5. 每个 choice 必须包含完整 `patch`；不能只写建议文字。
6. patch 必须尽量局部化，只修改与当前 slot 强相关的节点、链接、槽位或缺口。

`choiceGroup` 结构要求：
- id: string
- slotId: string
- selectionMode: `single` / `multiple`
- status: `open` / `resolved`
- choices: array，长度 2 到 3

每个 `choice` 至少包含：
- id: string
- title: string
- rationale: string
- patch: object
- proposedNodeIds: string[]
- proposedLinkIds: string[]
- impactPreview: {
    affectedGoals: string[],
    affectedActors: string[],
    affectedFlows: string[],
    affectedObjects: string[],
    affectedScreens: string[]
  }
- status: `candidate`

`patch` 只能使用这些字段：
- addNodes: array
- updateNodes: array
- removeNodeIds: array
- addLinks: array
- removeLinkIds: array
- addSlots: array
- updateSlots: array
- removeSlotIds: array
- addIssues: array
- updateIssues: array
- resolveIssueIds: array

关系表达约束：
1. 角色归属/执行关系只能使用 `performed_by`，方向必须是 `task|flow_step -> actor`。
2. 页面可访问角色只能使用 `accessible_by`，方向必须是 `screen -> actor`。
3. 组件树只能使用 `contains`，方向必须是 `screen -> ui_component` 或 `ui_component -> ui_component`。
4. 组件触发步骤只能使用 `invokes_step`，方向必须是 `ui_component -> flow_step`。
5. 禁止使用 task.owner、flow_step.actor、flow_step.swimlane 这类字符串语义字段。

新增节点要求：
1. 每个新增节点都必须包含 id、kind、title、description、status、confidence、source。
2. `confidence` 必须是 0 到 1 的数字或 null。
3. 所有 patch.addLinks 的 sourceId/targetId 要么引用现有节点，要么引用同一 patch.addNodes 中新增的节点。

候选方案应该彼此有明显策略差异，例如：
- 保守补充
- 面向自动化
- 面向体验优化
但都必须可落地、结构完整、可直接应用。
"""


def build_expand_slot_messages(payload: ExpandSlotInput) -> tuple[str, str]:
    user = (
        "请围绕下面这个槽位生成候选方案。\n\n"
        f"projectionContext: {payload.projectionContext}\n\n"
        "slot:\n"
        f"{json.dumps(payload.slot, ensure_ascii=False, indent=2)}\n\n"
        "ownerNode:\n"
        f"{json.dumps(payload.ownerNode, ensure_ascii=False, indent=2)}\n\n"
        "relatedNodes:\n"
        f"{json.dumps(payload.relatedNodes, ensure_ascii=False, indent=2)}\n\n"
        "relatedLinks:\n"
        f"{json.dumps(payload.relatedLinks, ensure_ascii=False, indent=2)}\n"
    )
    return expand_slot, user
