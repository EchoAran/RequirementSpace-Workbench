from __future__ import annotations

import json

from .contracts import ExpandSlotInput
from .schema_reference import (
    CHOICE_GROUP_STATUS_ENUM,
    CHOICE_STATUS_ENUM,
    GRAPH_PATCH_FIELDS_BULLETS,
    LINK_STATUS_ENUM,
    LINK_TYPE_ENUM,
    NODE_KIND_ENUM,
    NODE_STATUS_ENUM,
    SLOT_STATUS_ENUM,
)


expand_slot = f"""你是 RequirementSpace Workbench 的 Slot 扩展器。
你的任务是围绕一个既有槽位生成 2 到 3 个候选方案，并返回一个可被后端直接处理的 `choiceGroup` JSON。

你必须严格遵守以下规则：
1. 只输出一个 JSON 对象。
2. 不要输出解释、Markdown、代码块或额外文字。
3. 顶层必须是 {{"choiceGroup": {{...}}}}。
4. `choiceGroup` 必须是完整对象，不能只返回 choices 数组。
5. 每个 choice 必须包含完整 `patch`；不能只写建议文字。
6. patch 必须尽量局部化，只修改与当前 slot 强相关的节点、链接、槽位或缺口。
7. 禁止输出任何未定义的 kind、link type、status。
8. `confidence` 必须是 number 或 null，禁止输出字符串 confidence。

完整枚举白名单：
- Node.kind: {NODE_KIND_ENUM}
- Node.status: {NODE_STATUS_ENUM}
- Link.type: {LINK_TYPE_ENUM}
- Link.status: {LINK_STATUS_ENUM}
- Slot.status: {SLOT_STATUS_ENUM}
- ChoiceGroup.status: {CHOICE_GROUP_STATUS_ENUM}
- Choice.status: {CHOICE_STATUS_ENUM}

`choiceGroup` 结构要求：
- id: string
- slotId: string
- selectionMode: `single` / `multiple`
- status: {CHOICE_GROUP_STATUS_ENUM}
- selectedChoiceIds: string[]
- choices: array，长度 2 到 3

每个 `choice` 至少包含：
- id: string
- choiceGroupId: string
- title: string
- rationale: string
- patch: object
- impactPreview: {{
    affectedGoals: string[],
    affectedActors: string[],
    affectedFlows: string[],
    affectedObjects: string[],
    affectedScreens: string[]
  }}
- status: `candidate`，不可输出其他值

`patch` 只能使用这些字段：
{GRAPH_PATCH_FIELDS_BULLETS}

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

最小合法 JSON 示例：
{{
  "choiceGroup": {{
    "id": "cg_notification_strategy",
    "slotId": "slot_notification_strategy",
    "selectionMode": "single",
    "status": "open",
    "selectedChoiceIds": [],
    "choices": [
      {{
        "id": "choice_add_notification_rule",
        "choiceGroupId": "cg_notification_strategy",
        "title": "补充审批通知规则",
        "rationale": "先补齐关键通知链路，改动最小。",
        "patch": {{
          "addNodes": [
            {{
              "id": "rule_notify_leave_result",
              "kind": "rule",
              "title": "审批结果通知规则",
              "description": "审批通过或驳回后通知申请人",
              "status": "ai_assumption",
              "confidence": 0.72,
              "source": {{"type": "ai"}}
            }}
          ],
          "addLinks": [],
          "updateNodes": [],
          "removeNodeIds": [],
          "removeLinkIds": [],
          "addSlots": [],
          "updateSlots": [],
          "removeSlotIds": [],
          "addChoiceGroups": [],
          "updateChoiceGroups": [],
          "addIssues": [],
          "updateIssues": [],
          "resolveIssueIds": []
        }},
        "impactPreview": {{
          "affectedGoals": [],
          "affectedActors": [],
          "affectedFlows": [],
          "affectedObjects": [],
          "affectedScreens": []
        }},
        "status": "candidate"
      }}
    ]
  }}
}}
"""


def build_expand_slot_messages(payload: ExpandSlotInput) -> tuple[str, str]:
    slot_payload = payload.slot.model_dump(mode="json")
    owner_node_payload = payload.ownerNode.model_dump(mode="json")
    related_nodes_payload = [node.model_dump(mode="json") for node in payload.relatedNodes]
    related_links_payload = [link.model_dump(mode="json") for link in payload.relatedLinks]

    user = (
        "请围绕下面这个槽位生成候选方案。\n\n"
        f"projectionContext: {payload.projectionContext}\n\n"
        "slot:\n"
        f"{json.dumps(slot_payload, ensure_ascii=False, indent=2)}\n\n"
        "ownerNode:\n"
        f"{json.dumps(owner_node_payload, ensure_ascii=False, indent=2)}\n\n"
        "relatedNodes:\n"
        f"{json.dumps(related_nodes_payload, ensure_ascii=False, indent=2)}\n\n"
        "relatedLinks:\n"
        f"{json.dumps(related_links_payload, ensure_ascii=False, indent=2)}\n"
    )
    return expand_slot, user
