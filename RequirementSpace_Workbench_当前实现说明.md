# RequirementSpace Workbench 实现说明

## 1. 文档目的

本文档描述当前仓库代码对应的实现状态，用于说明系统定位、核心模型、交互链路、接口结构和现阶段约束。

文档内容以当前仓库中的后端与前端代码为事实来源。


## 2. 产品定位

RequirementSpace Workbench 是一个面向需求早期探索的 AI 协作建模工作台。

系统的核心目标包括：

- 用结构化 IR 表达需求空间。
- 用五个投影视角组织需求信息与决策上下文。
- 用 `Slot -> ChoiceGroup -> Choice` 机制表达待补全位置与候选方案。
- 用 `Issue` 表达缺口、风险、冲突和不明确点。
- 用 `Proposal` 承载局部改写建议。
- 用 `GraphPatch` 作为结构化变更的统一写入形式。

系统定位是“结构化需求建模 + AI 协作决策”工作台，重点是需求空间的逐步澄清、约束收敛与可追踪变更，而不是单向的 PRD 生成器或纯原型工具。


## 3. 系统架构

### 3.1 技术栈

后端：

- FastAPI
- SQLAlchemy
- SQLite
- Pydantic v2

前端：

- React
- TypeScript
- Zustand
- Vite

AI 相关：

- 通过 `backend/app/ir/llm.py` 调用兼容 OpenAI Chat Completions 的接口
- Prompt 输出采用 JSON 结构
- LLM 输出先经过 schema 校验，再经过业务规则校验


### 3.2 总体结构

仓库主要分为两部分：

- `backend/`：负责 IR 校验、持久化、GraphPatch 应用、Prompt 调用、诊断、投影派生、影响预览和导出接口。
- `frontend/`：负责五个页面视图、选择器派生、工作区状态管理，以及 `Issue / Slot / Choice / Proposal` 的交互。


## 4. IR 模型

IR 顶层对象为 `RequirementSpaceIR`，包含以下部分：

- `id`
- `name`
- `idea`
- `meta`
- `nodes`
- `links`
- `slots`
- `choiceGroups`
- `proposals`
- `issues`
- `projections`
- `audit`

结构特点如下：

- `nodes`、`slots`、`choiceGroups`、`proposals`、`issues` 为以业务 `id` 为 key 的映射。
- `links` 为数组。
- `projections` 保存页面状态与投影视图相关 UI 状态。
- `audit` 保存创建时间、更新时间、来源摘要和操作日志。


### 4.1 Node

支持的 `NodeKind`：

- `goal`
- `capability`
- `actor`
- `task`
- `flow`
- `flow_step`
- `rule`
- `business_object`
- `field`
- `state_machine`
- `object_state`
- `state_transition`
- `screen`
- `ui_component`

通用字段：

- `id`
- `kind`
- `title`
- `description`
- `status`
- `scopeStatus`
- `confidence`
- `source`
- `tags`

不同节点类型带有各自的结构字段，例如：

- `goal.successCriteria`
- `capability.priority`
- `actor.roleType`
- `task.outcome`
- `flow.trigger`
- `flow_step.stepType`
- `rule.ruleType / expression / naturalLanguage`
- `field.fieldType / required / valueSource`
- `screen.purpose / route`
- `ui_component.componentType`

约束：

- `confidence` 为 `0..1` 区间内的数字或空值。
- `kind`、`status`、`scopeStatus` 为严格枚举。
- 后端节点模型采用严格 schema，不接受未定义字段。


### 4.2 Link

支持的 `LinkType`：

- `realizes`
- `supports`
- `performed_by`
- `owns`
- `precedes`
- `branches_to`
- `guards`
- `reads`
- `writes`
- `changes_state`
- `contains`
- `accessible_by`
- `binds_field`
- `invokes_step`
- `depends_on`
- `diagnoses`

关系语义由 `backend/app/ir/link_rules.py` 约束。当前系统中，业务关系统一通过 `links` 表达。

常见关系包括：

- `performed_by`：`task | flow_step -> actor`
- `accessible_by`：`screen -> actor`
- `contains`：层级结构关系
- `invokes_step`：`ui_component -> flow_step`
- `binds_field`：`ui_component -> field`
- `reads / writes`：主要用于 `flow_step -> business_object`
- `changes_state`：`flow_step -> state_transition`


### 4.3 Slot

`Slot` 表达需求空间中的待补全位置。

字段：

- `id`
- `ownerNodeId`
- `ownerProjection`
- `name`
- `description`
- `expectedKinds`
- `arity`
- `status`
- `context`

状态：

- `empty`
- `expanding`
- `candidate_ready`
- `filled`
- `deferred`

`context` 用于描述相关投影、相关节点和提示信息，包含：

- `projectionHints`
- `relatedNodeIds`
- `promptHints`


### 4.4 ChoiceGroup 与 Choice

`ChoiceGroup` 表达某个 `Slot` 下的一组选项。

`ChoiceGroup` 字段：

- `id`
- `slotId`
- `choices`
- `selectedChoiceIds`
- `selectionMode`
- `status`

`ChoiceGroup.status`：

- `open`
- `selected`
- `dismissed`

`Choice` 字段：

- `id`
- `choiceGroupId`
- `title`
- `rationale`
- `patch`
- `impactPreview`
- `status`

`Choice.status`：

- `candidate`
- `selected`
- `rejected`
- `archived`

约束：

- `ChoiceGroup` 通过 `slotId` 关联 `Slot`。
- 单选模式下 `selectedChoiceIds` 最多为 1 个。
- 每个 `Choice` 都带有 `patch` 和 `impactPreview`。


### 4.5 Issue

`Issue` 表达当前 IR 中已知的缺口、风险、冲突或不明确点。

字段：

- `id`
- `title`
- `description`
- `severity`
- `category`
- `relatedNodeIds`
- `suggestedProjection`
- `suggestedAction`
- `status`
- `source`

状态：

- `open`
- `resolved`
- `ignored`

类别：

- `missing`
- `conflict`
- `ambiguity`
- `scope_risk`
- `flow_gap`
- `data_gap`
- `ui_gap`
- `rule_gap`


### 4.6 Proposal

`Proposal` 表达局部改写建议，是独立的一等决策对象。

字段：

- `id`
- `workspaceId`
- `title`
- `summary`
- `scope`
- `patch`
- `impactPreview`
- `status`
- `createdAt`
- `source`

状态：

- `draft`
- `candidate`
- `accepted`
- `rejected`
- `archived`

`Proposal` 可以被直接采纳，也可以转换为某个 `Slot` 下的 `Choice`。


### 4.7 ProjectionState

系统包含五个投影视角：

- `goal`
- `role`
- `system`
- `data`
- `ui`

`ProjectionState` 主要保存各页面的 UI 状态：

- `goal`
  - `expandedNodeIds`
  - `filters`
  - `layout`
- `role`
  - `activeActorId`
  - `filters`
  - `layout`
- `system`
  - `swimlaneBy`
  - `highlightedNodeIds`
  - `filters`
  - `layout`
- `data`
  - `showFields`
  - `showStates`
  - `filters`
  - `layout`
- `ui`
  - `activeActorId`
  - `activeScreenId`
  - `filters`
  - `layout`


## 5. 投影视角定义

### 5.1 Goal 投影

Goal 投影围绕以下内容组织需求：

- `goal`
- `capability`
- `task`
- `actor`
- `realizes`
- `supports`
- `performed_by`
- 相关 `Issue`
- 所属 `Slot`
- 所属 `ChoiceGroup`

该视角主要回答：

- 要做什么
- 谁参与
- 哪些能力支撑目标
- 哪些任务和分岔仍待确认


### 5.2 Role 投影

Role 投影围绕以下内容组织需求：

- `actor`
- `task`
- `flow_step`
- `screen`
- `performed_by`
- `accessible_by`
- 相关 `Issue`
- 所属 `Slot`

该视角主要回答：

- 谁参与
- 谁负责什么任务或步骤
- 哪个角色能访问哪些页面


### 5.3 System 投影

System 投影围绕以下内容组织需求：

- `flow`
- `flow_step`
- `rule`
- `state_transition`
- `precedes`
- `branches_to`
- `performed_by`
- `guards`
- `changes_state`
- 相关 `Issue`
- 所属 `Slot`
- 所属 `ChoiceGroup`

该视角主要回答：

- 主流程如何推进
- 哪些地方存在异常分支
- 哪些规则参与流程约束
- 哪些状态迁移参与流程闭环


### 5.4 Data 投影

Data 投影围绕以下内容组织需求：

- `business_object`
- `field`
- `state_machine`
- `object_state`
- `state_transition`
- `contains`
- `reads`
- `writes`
- `changes_state`
- 相关 `Issue`
- 所属 `Slot`

该视角主要回答：

- 系统处理哪些对象
- 对象有哪些字段
- 对象状态如何变化
- 哪些流程步骤读写哪些对象


### 5.5 UI 投影

UI 投影围绕以下内容组织需求：

- `screen`
- `ui_component`
- `field`
- `flow_step`
- `actor`
- `contains`
- `binds_field`
- `invokes_step`
- `accessible_by`
- 相关 `Issue`
- 所属 `Slot`
- 所属 `ChoiceGroup`

该视角主要回答：

- 哪个角色能访问哪个页面
- 页面中有哪些组件
- 组件绑定了哪个字段
- 组件触发哪个流程步骤


## 6. 决策与变更机制

### 6.1 GraphPatch

所有结构化修改统一通过 `GraphPatch` 进入系统。

核心字段包括：

- `addNodes`
- `updateNodes`
- `removeNodeIds`
- `addLinks`
- `updateLinks`
- `removeLinkIds`
- `addSlots`
- `updateSlots`
- `removeSlotIds`
- `addChoiceGroups`
- `updateChoiceGroups`
- `addIssues`
- `updateIssues`
- `resolveIssueIds`

`GraphPatchService` 负责：

- 校验 patch
- 物化 ID
- 计算影响预览
- 应用变更
- 追加审计记录
- 对结果 IR 再次校验


### 6.2 Issue -> Slot -> ChoiceGroup -> Choice -> Patch

主链路如下：

1. 诊断或用户创建 `Issue`
2. 从 `Issue` 生成修复 `Slot`
3. 自动或手动展开 `Slot` 生成 `ChoiceGroup`
4. 用户选择某个 `Choice`
5. 应用 `choice.patch`
6. 更新 `ChoiceGroup.selectedChoiceIds` 与 `Slot.status`
7. 视情况 resolve 关联 `Issue`


### 6.3 Proposal 决策链

`Proposal` 链路如下：

1. 用户在某个 scope 上发起局部改写
2. LLM 返回 `Proposal`
3. 后端执行 `RewriteOutput` schema 校验
4. 执行 `Proposal` 业务校验
5. 对 `proposal.patch` 执行 `GraphPatchService.validate`
6. Proposal 入库
7. 前端可审阅、采纳、拒绝或转换为 `Choice`


## 7. LLM 输出约束

当前三类 Prompt 输出采用严格 JSON 合约：

- `InitializeWorkspaceOutput`
- `ExpandSlotOutput`
- `RewriteOutput`

规则包括：

- Prompt 中嵌入完整枚举白名单
- Prompt 中提供最小合法 JSON 示例
- 输出必须符合 schema 中的 kind、link type、status 与字段结构
- `confidence` 必须为数值类型
- 所有输出先做 schema 校验，再做业务规则校验


## 8. 后端接口

主要接口如下。

工作区：

- `GET /api/health`
- `GET /api/workspaces`
- `POST /api/workspaces/bootstrap`
- `GET /api/workspaces/default`
- `GET /api/workspaces/{workspace_id}`

Issue / Slot / Choice：

- `POST /api/workspaces/{workspace_id}/issues`
- `POST /api/workspaces/{workspace_id}/issues/{issue_id}/slots`
- `POST /api/workspaces/{workspace_id}/slots`
- `POST /api/workspaces/{workspace_id}/slots/{slot_id}/expand`
- `POST /api/workspaces/{workspace_id}/choice-groups/{choice_group_id}/choices`
- `POST /api/workspaces/{workspace_id}/choices/{choice_id}/accept`
- `POST /api/workspaces/{workspace_id}/choices/{choice_id}/reject`

诊断 / Patch / Proposal：

- `POST /api/workspaces/{workspace_id}/diagnose`
- `POST /api/workspaces/{workspace_id}/patch`
- `POST /api/workspaces/{workspace_id}/rewrite`
- `GET /api/workspaces/{workspace_id}/proposals`
- `POST /api/workspaces/{workspace_id}/proposals/{proposal_id}/accept`
- `POST /api/workspaces/{workspace_id}/proposals/{proposal_id}/reject`
- `POST /api/workspaces/{workspace_id}/proposals/{proposal_id}/convert-to-choice`
- `POST /api/workspaces/{workspace_id}/impact-preview`

投影与导出：

- `GET /api/workspaces/{workspace_id}/projections/{projection_kind}`
- `GET /api/workspaces/{workspace_id}/export`
- `GET /api/workspaces/{workspace_id}/export/json`
- `GET /api/workspaces/{workspace_id}/export/markdown`


## 9. 前端页面与交互

主页面如下：

- `/`：Overview
- `/what`：WhatToDo
- `/flow`：HowItWorks
- `/scope`：ScopeAndDelivery
- `/preview`：Preview

全局交互中枢为 `frontend/src/store/useWorkspaceStore.ts`。

重要行为包括：

- 初始化或打开工作区
- 选择节点、Slot、ChoiceGroup、Choice、Proposal
- 点击空 `Slot` 时直接展开
- 从 `Issue` 自动创建并展开 `Slot`
- 采纳或拒绝 `Choice`
- 生成、采纳、拒绝、转换 `Proposal`
- 显示全局反馈与错误状态


## 10. 校验与一致性策略

### 10.1 Schema 校验

后端核心对象使用 Pydantic 严格模型，主要特征包括：

- `extra = forbid`
- 严格枚举
- `confidence` 数字范围校验
- 判别联合节点模型


### 10.2 业务校验

关键业务校验包括：

- `links` 必须连接合法 kind
- `sourceId / targetId` 必须存在
- `Slot.ownerNodeId` 必须存在
- `ChoiceGroup.slotId` 必须存在
- `Choice.choiceGroupId` 必须与所属 group 一致
- `selectedChoiceIds` 必须引用组内 `Choice`
- `Proposal.workspaceId` 必须与当前 workspace 一致
- `ProjectionState` 中的引用型 UI 状态必须指向存在节点
- `audit.operationLog` 中的目标对象引用必须满足校验规则


## 11. 持久化模型

数据库采用“内部自增主键 + workspace 维度业务 id”的设计。

特点：

- 表内主键使用 `row_id`
- 业务对象使用 `workspace_id + id` 唯一约束
- 业务对象以 workspace 维度隔离
- `Proposal` 使用独立表存储


## 12. 当前实现特征

当前实现呈现出以下特点：

- `IR` 作为结构化事实基础
- 五个投影视角围绕同一份 IR 派生
- `Issue`、`Slot`、`ChoiceGroup`、`Choice`、`Proposal` 都是正式对象
- `GraphPatch` 是结构化变更的统一写入口
- `audit` 记录工作区级的操作日志
- 前端页面围绕“澄清需求、补齐缺口、审阅候选、收敛范围、确认交付”组织


## 13. 后续工作关注点

当前代码已经具备完整主链路，但仍有若干值得持续优化的方向：

- 前端结构化编辑与 link 驱动模型的进一步统一
- 诊断规则的持续增强
- 审计与导出能力的进一步细化
- 页面级的回归测试与交互测试补充


## 14. 结论

当前仓库实现形成了如下稳定主线：

- IR 承载需求空间的结构化表达
- 五个投影视角围绕 IR 组织信息
- `Issue` 用于发现和表达问题
- `Slot` 用于表达待补全位置
- `ChoiceGroup / Choice` 用于表达候选方案与采纳决策
- `Proposal` 用于表达局部改写建议
- `GraphPatch` 用于表达和应用结构化变更
- `audit` 用于记录关键操作过程

本文档描述的即为当前代码状态对应的实现说明。
