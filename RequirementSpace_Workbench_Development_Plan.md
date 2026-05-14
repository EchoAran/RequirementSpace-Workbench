# RequirementSpace Workbench 后续开发计划方案

## 1. 开发目标

当前系统已经有前端工作台骨架和基础后端接口，下一步的核心目标是把它发展为一个围绕需求空间 IR 运转的 Human AI 协作系统。

系统最终要支持以下主流程：

```text
用户输入一句应用想法
系统生成初始需求空间 IR
用户通过五个投影查看和修正需求空间
系统发现 Issue 和 Slot
AI 围绕 Slot 生成 Choice
用户采纳或拒绝 Choice
GraphPatch 写入 IR
五个投影同步刷新
预览与验证页检查需求是否闭环
导出结构化需求方案
```

本阶段开发重点：

```text
1. 稳定需求空间 IR 数据结构
2. 建立 IR 后端引擎
3. 让候选方案真正修改需求空间
4. 建立确定性诊断机制
5. 接入 LLM 生成结构化结果
6. 让五个前端页面全部从 IR 投影派生
7. 完成导出和可演示闭环
```

## 2. 总体设计原则

### 2.1 IR 是唯一事实源

所有需求事实都存放在 `RequirementSpaceIR` 中。目标模型、角色模型、系统流程、数据模型、UI 模型都从同一份 IR 查询和渲染。

页面可以有不同交互形式，但不能各自维护独立数据。

### 2.2 投影负责看法，IR 负责事实

五个投影分别对应：

```text
目标投影：目标化能力树
角色投影：角色责任矩阵
系统投影：情境泳道流程图
数据投影：业务对象状态模型
UI 投影：角色视角交互组件树
```

投影只保存布局、折叠、选中、高亮等展示状态。节点、关系、状态、范围、候选、问题都放在 IR 中。

### 2.3 AI 只输出结构化变更

AI 不能直接输出一段普通文本后让前端解析。AI 输出必须是以下结构之一：

```text
RequirementSpaceIR
GraphPatch
Issue[]
Slot[]
ChoiceGroup
Proposal
```

这样做可以让系统校验、预览、采纳、回滚和追踪 AI 的输出。

### 2.4 用户是决策者

AI 负责发现缺口、生成候选、解释影响。用户负责确认、修改、采纳、拒绝、暂缓、排除。

系统不能默认把所有 AI 生成内容写入正式需求空间。AI 候选应先进入 Choice，用户采纳后再写入 Nodes 和 Links。

### 2.5 所有修改必须有作用域

AI 操作必须绑定到明确 scope：

```text
workspace
projection
node
slot
issue
choiceGroup
```

局部改写只能修改当前 scope 允许影响的节点和链接。这样可以避免一次自然语言命令导致整个需求空间失控。

## 3. 目标架构

### 3.1 前端层

前端保留五页结构：

```text
页面 01：概览
页面 02：要做什么
页面 03：怎么运作
页面 04：范围与交付
页面 05：预览与验证
```

每个页面只负责展示和交互。页面数据统一通过 selectors 从 IR 计算。

### 3.2 投影选择器层

新增统一 selector 模块：

```text
selectGoalProjection
selectRoleProjection
selectSystemProjection
selectDataProjection
selectUIProjection
selectDecisionQueue
selectReadiness
selectIssuesByProjection
selectSlotsByOwner
selectTrace
```

作用：

```text
1. 避免每个页面重复拼接 nodes 和 links
2. 保证不同页面看到同一套需求事实
3. 让投影逻辑可以被测试
4. 后续方便替换可视化组件
```

### 3.3 后端 IR 服务层

后端从普通 CRUD 升级为 IR Engine，包含：

```text
WorkspaceService
GraphPatchService
SlotService
ChoiceService
DiagnosisService
ProjectionService
ExportService
LLMService
```

### 3.4 AI 层

AI 只通过固定 Prompt 和 JSON Schema 工作：

```text
InitializeWorkspacePrompt
ExpandSlotPrompt
DiagnoseWorkspacePrompt
ScopedRewritePrompt
GenerateExportPrompt
```

每个 Prompt 都必须有输入 schema、输出 schema、校验逻辑、失败 fallback。

## 4. 需求空间 IR 数据结构冻结

### 4.1 需要做什么

将当前 `frontend/src/types.ts` 中的 IR 类型升级为稳定版本 `RequirementSpaceIR v0.2`，并让前后端共享一致语义。

目标结构：

```ts
type RequirementSpaceIR = {
  id: string
  name: string
  idea: string

  meta: ProjectMeta

  nodes: Record<string, RequirementNode>
  links: RequirementLink[]

  slots: Record<string, RequirementSlot>
  choiceGroups: Record<string, ChoiceGroup>
  proposals: Record<string, Proposal>

  issues: Record<string, Issue>

  projections: ProjectionState

  audit: AuditInfo
}
```

### 4.2 怎么做

新增目录：

```text
frontend/src/domain/ir/schema.ts
frontend/src/domain/ir/selectors.ts
frontend/src/domain/ir/invariants.ts
frontend/src/domain/ir/commands.ts

backend/app/ir/schema.py
backend/app/ir/validators.py
backend/app/ir/graph_patch.py
backend/app/ir/projections.py
backend/app/ir/diagnostics.py
backend/app/ir/services.py
```

将现有 `types.ts` 的内容迁入 `schema.ts`，并在后端用 Pydantic 定义同构 schema。

### 4.3 为什么

当前前端和后端已经有 IR 雏形，但部分字段仍存在兼容旧页面的混用情况，例如：

```text
actor 和 actorId 混用
owner 和 actorId 混用
stepType 使用中文自由文本
UI 组件关系依赖旧 link
Choice 缺少可应用 patch
```

先冻结 schema，可以避免后续页面、后端、AI 三方各自扩展，导致系统难以维护。

## 5. IR 字段调整

### 5.1 Choice 增加 GraphPatch

#### 需要做什么

把 Choice 改成真正可采纳的候选方案。

```ts
type Choice = {
  id: string
  title: string
  rationale: string
  patch: GraphPatch
  impactPreview: ImpactPreview
  status: 'candidate' | 'selected' | 'rejected' | 'archived'
}
```

#### 怎么做

1. 前端类型增加 `patch`
2. 后端 Choice 表增加 `patch` JSON 字段
3. 旧字段 `proposedNodeIds` 和 `proposedLinkIds` 暂时保留兼容
4. `accept_choice` 改为读取 `choice.patch`
5. 采纳时调用 `GraphPatchService.apply`

#### 为什么

候选方案的本质是“一组待写入需求空间的结构化变更”。如果 Choice 只保存标题和影响说明，采纳后无法真正改变 IR。

### 5.2 Slot 增加候选就绪状态

#### 需要做什么

Slot 状态改为：

```ts
type SlotStatus =
  | 'empty'
  | 'expanding'
  | 'candidate_ready'
  | 'filled'
  | 'deferred'
```

#### 怎么做

1. 前端类型更新
2. 后端 Slot 表继续用字符串状态
3. Slot expand 完成后设置为 `candidate_ready`
4. 用户采纳 Choice 后设置为 `filled`
5. 用户延后处理后设置为 `deferred`

#### 为什么

`expanding` 表示 AI 生成中，`candidate_ready` 表示候选已生成、等待用户决策。两者需要区分，否则前端无法准确显示待决策队列。

### 5.3 Slot 增加 ownerProjection

#### 需要做什么

Slot 结构增加归属投影：

```ts
type RequirementSlot = {
  id: string
  ownerNodeId: string
  ownerProjection: ProjectionKind
  name: string
  description?: string
  expectedKinds: NodeKind[]
  arity: 'one' | 'many'
  status: SlotStatus
  choiceGroupId?: string
  context: {
    projectionHints: ProjectionKind[]
    relatedNodeIds: string[]
    promptHints?: string[]
  }
}
```

#### 怎么做

1. 创建 Slot 时必须传入 `ownerProjection`
2. Issue 触发修复 Slot 时，根据 Issue.category 推导 ownerProjection
3. 前端按 ownerProjection 在对应页面显示 Slot
4. Overview 汇总所有未处理 Slot

#### 为什么

同一个 Slot 可能影响多个投影，但它需要一个主要出现位置。比如“审批退回后处理”优先属于系统投影，同时影响数据和 UI 投影。

### 5.4 LinkType 增加 UI 组件树关系

#### 需要做什么

增加这些 link 类型：

```ts
type LinkType =
  | 'realizes'
  | 'supports'
  | 'performed_by'
  | 'owns'
  | 'precedes'
  | 'branches_to'
  | 'guards'
  | 'reads'
  | 'writes'
  | 'changes_state'
  | 'depends_on'
  | 'diagnoses'
  | 'contains'
  | 'accessible_by'
  | 'binds_field'
  | 'invokes_step'
```

#### 怎么做

统一语义：

```text
Capability realizes Goal
Task supports Capability
FlowStep supports Task
Actor performed_by Task 或 FlowStep
FlowStep reads BusinessObject
FlowStep writes BusinessObject
FlowStep changes_state StateTransition
Rule guards FlowStep 或 StateTransition
Screen accessible_by Actor
Screen contains UIComponent
UIComponent contains UIComponent
UIComponent binds_field Field
UIComponent invokes_step FlowStep
Issue diagnoses Node
```

#### 为什么

UI 投影要成为角色视角交互组件树。组件树需要表达父子结构、字段绑定、动作绑定。仅靠 `displayed_on` 和 `triggered_by` 不够精确。

## 6. IR 不变量校验

### 6.1 需要做什么

后端每次写入后都要校验 IR 基本一致性。

### 6.2 怎么做

实现 `backend/app/ir/validators.py`，至少包含：

```text
所有 Link 的 sourceId 和 targetId 必须存在
所有 Slot 的 ownerNodeId 必须存在
所有 Choice.patch.addLinks 指向的节点必须存在或在同一 patch.addNodes 中
所有 FlowStep 必须能追溯到 Actor 或 system lane
所有 Screen 必须能追溯到 Actor
所有 UIComponent 必须归属于 Screen 或另一个 UIComponent
所有 StateTransition 必须有 fromStateId 和 toStateId
所有 accepted Choice 对应 Slot 必须进入 filled
所有 resolved Issue 必须保留操作记录
```

### 6.3 为什么

需求空间是图结构。只要链接断裂，五个投影就会出现不一致。后端校验可以防止坏数据进入工作台。

## 7. GraphPatchService

### 7.1 需要做什么

把所有结构化变更统一收敛到 GraphPatch。

```ts
type GraphPatch = {
  addNodes?: RequirementNode[]
  updateNodes?: Partial<RequirementNode>[]
  removeNodeIds?: string[]
  addLinks?: RequirementLink[]
  removeLinkIds?: string[]
  updateSlots?: Partial<RequirementSlot>[]
  resolveIssueIds?: string[]
  createIssues?: Issue[]
}
```

### 7.2 怎么做

重构后端 `apply_graph_patch`：

```text
1. 校验 patch 结构
2. 校验新增节点 ID 是否冲突
3. 校验新增 link 是否可连接
4. 删除节点时同步删除相关 link 和 slot
5. 更新节点时只允许合法字段
6. 更新 slot 状态
7. 解决 issue
8. 写 operationLog
9. 运行 IR validator
10. 返回最新 workspace
```

### 7.3 为什么

GraphPatch 是 Human AI 协作的写入边界。AI、用户、批量修复、候选采纳都通过同一种补丁机制进入 IR，系统才能做校验、影响预览和操作追踪。

## 8. Choice 采纳闭环

### 8.1 需要做什么

让用户采纳 Choice 后，需求空间真正变化。

### 8.2 怎么做

改造 `accept_choice`：

```text
1. 查询 Choice
2. 查询 ChoiceGroup
3. 查询关联 Slot
4. 读取 Choice.patch
5. 调用 GraphPatchService.apply
6. 设置 Choice.status = selected
7. 设置同组其他 Choice.status = rejected
8. 设置 ChoiceGroup.status = selected
9. 设置 Slot.status = filled
10. 根据 impactPreview 或 patch.resolveIssueIds 解决 Issue
11. 返回最新 IR
```

### 8.3 为什么

当前候选采纳主要改变候选状态。后续系统必须做到“采纳即写入需求空间”，否则用户无法通过 AI 候选逐步收敛 IR。

## 9. SlotService

### 9.1 需要做什么

把 Slot 从展示信息升级为 AI 生成入口。

### 9.2 怎么做

新增接口：

```http
POST /api/workspaces/{workspace_id}/slots
POST /api/workspaces/{workspace_id}/slots/{slot_id}/expand
PATCH /api/workspaces/{workspace_id}/slots/{slot_id}
```

`expand_slot` 流程：

```text
1. 读取 Slot
2. 读取 ownerNode
3. 收集 relatedNodeIds
4. 收集相关 links
5. 构造局部 IR slice
6. 调用 ExpandSlotPrompt
7. 生成 ChoiceGroup
8. 每个 Choice 携带 patch 和 impactPreview
9. Slot.status = candidate_ready
10. 返回最新 workspace
```

### 9.3 为什么

Slot 是需求空间中“待补充、待决策”的位置。系统要围绕 Slot 生成局部候选，用户再做决策。这是逐步探索需求空间的核心交互。

## 10. DiagnosisService

### 10.1 需要做什么

先实现确定性诊断，再接入 LLM 诊断。

### 10.2 怎么做

第一阶段实现规则诊断：

```text
P0：能力无任务
P0：任务无角色
P0：流程无开始节点
P0：流程无结束节点
P0：判断节点无分支
P0：流程步骤无 actorId
P0：本期能力无流程支撑
P1：业务对象无字段
P1：业务对象无状态
P1：状态迁移无触发流程
P1：页面无可访问角色
P1：UI 操作无流程绑定
P1：字段无业务对象归属
P2：通知节点无通知对象
P2：外部依赖无依赖方说明
```

每条诊断生成 Issue：

```ts
type Issue = {
  id: string
  title: string
  description: string
  severity: 'low' | 'medium' | 'high'
  category:
    | 'missing'
    | 'conflict'
    | 'ambiguity'
    | 'scope_risk'
    | 'flow_gap'
    | 'data_gap'
    | 'ui_gap'
    | 'rule_gap'
  relatedNodeIds: string[]
  suggestedProjection: ProjectionKind
  suggestedAction: string
  status: 'open' | 'resolved' | 'ignored'
  source: SourceRecord
}
```

第二阶段接入 LLM：

```text
输入：当前 IR 切片和确定性诊断结果
输出：语义层 Issue 和建议 Slot
```

### 10.3 为什么

诊断是系统区别于普通聊天生成工具的关键。它让需求空间可以被验证，而非只被生成。

## 11. ProjectionService

### 11.1 需要做什么

建立后端或前端统一投影计算逻辑。

### 11.2 怎么做

实现以下函数：

```text
buildGoalProjection(ir)
buildRoleProjection(ir)
buildSystemProjection(ir)
buildDataProjection(ir)
buildUIProjection(ir)
buildReadiness(ir)
buildDecisionQueue(ir)
buildTrace(ir, nodeId)
```

投影规则：

```text
目标投影读取 Goal、Capability、Task、realizes、supports
角色投影读取 Actor、Task、FlowStep、Screen、permissions
系统投影读取 Flow、FlowStep、Rule、precedes、branches_to
数据投影读取 BusinessObject、Field、StateMachine、StateTransition
UI 投影读取 Screen、UIComponent、contains、binds_field、invokes_step
```

### 11.3 为什么

五个页面现在已经能展示很多内容，但页面内存在不少临时拼接逻辑。投影计算独立后，页面更轻，后端和测试更稳定。

## 12. LLM 接入方案

### 12.1 需要做什么

接入真实 LLM，但保持结构化输出和 fallback。

### 12.2 怎么做

新增：

```text
backend/app/ir/llm.py
backend/app/ir/prompts.py
```

实现 5 个 Prompt。

#### InitializeWorkspacePrompt

输入：

```json
{
  "idea": "用户输入的一句话",
  "schemaVersion": "0.2",
  "templateHints": ["approval_lite"]
}
```

输出：

```json
{
  "ir": "RequirementSpaceIR"
}
```

最低要求生成：

```text
Goal
Capability
Actor
Task
Flow
FlowStep
BusinessObject
Screen
UIComponent
Slot
Issue
Link
ProjectionState
```

#### ExpandSlotPrompt

输入：

```json
{
  "slot": {},
  "ownerNode": {},
  "relatedNodes": [],
  "relatedLinks": [],
  "projectionContext": "system"
}
```

输出：

```json
{
  "choiceGroup": {}
}
```

每个 Choice 必须包含 patch。

#### DiagnoseWorkspacePrompt

输入：

```json
{
  "scope": {},
  "irSlice": {},
  "deterministicIssues": []
}
```

输出：

```json
{
  "issues": [],
  "slots": []
}
```

#### ScopedRewritePrompt

输入：

```json
{
  "scope": {},
  "instruction": "用户局部改写指令",
  "allowedNodeIds": [],
  "forbiddenNodeIds": [],
  "irSlice": {}
}
```

输出：

```json
{
  "proposal": {},
  "patch": {},
  "impactPreview": {}
}
```

#### GenerateExportPrompt

输入完整 IR，输出 Markdown。

### 12.3 为什么

LLM 的优势是补全、重写、解释、生成候选。系统的稳定性来自 schema、局部上下文、validator、GraphPatch。两者分工清楚后，AI 输出才可控。

## 13. 前端五页改造计划

### 13.1 页面 01：概览

#### 需要做什么

把概览页做成需求空间控制台。

保留：

```text
整体成熟度
阻塞问题
待决策 Slot
开放候选组
高优先级缺口
最近候选方案
```

新增：

```text
假设账本
下一步探索建议
草稿成熟度
五投影覆盖状态
信息状态图例
```

#### 怎么做

数据来源：

```text
成熟度：buildReadiness(ir)
假设账本：meta.assumptions
决策队列：open Issue + candidate_ready Slot + open ChoiceGroup
下一步建议：按 severity 和 ownerProjection 排序
```

#### 为什么

概览页负责告诉用户当前需求空间处于什么状态、最该处理什么问题、哪些内容来自 AI 假设。

### 13.2 页面 02：要做什么

#### 需要做什么

把页面 02 定义为目标、能力、角色、任务的结构化确认页。

展示：

```text
目标化能力树
角色责任矩阵
任务映射卡
能力覆盖度
每个能力的开放 Slot
```

#### 怎么做

1. 能力树从 Goal、Capability、realizes link 推导
2. 任务通过 supports link 挂到 Capability
3. 角色通过 performed_by link 挂到 Task
4. 每个任务显示关联 flowStep、businessObject、screen 数量
5. 点击任何节点进入右侧面板编辑

#### 为什么

页面 02 解决“本版本要做什么、谁参与、哪些任务支撑目标”。这些是后续流程、数据、UI 生成的前置条件。

### 13.3 页面 03：怎么运作

#### 需要做什么

把页面 03 定义为系统运行机制页。

展示：

```text
动态泳道流程图
规则节点
异常分支
业务对象状态摘要
流程 Slot
流程 Issue
```

#### 怎么做

1. 泳道从 ActorNode 动态生成
2. 增加 system lane
3. FlowStep 使用 actorId 归入泳道
4. precedes 表示主流程
5. branches_to 表示异常分支
6. Rule 通过 guards 挂到 FlowStep
7. StateTransition 通过 changes_state 挂到 FlowStep
8. Slot 以流程节点上的可点击空位出现

#### 为什么

页面 03 负责验证“需求能不能跑起来”。流程、规则、异常、状态变化都在这里显影。

### 13.4 页面 04：范围与交付

#### 需要做什么

把页面 04 定义为单版本范围收敛页。

展示：

```text
本期包含
暂缓
外部依赖
已排除
范围冲突
导出准备度
```

#### 怎么做

1. 读取所有带 scopeStatus 的节点
2. 按 scopeStatus 聚合成四栏
3. 支持修改节点范围状态
4. 检查 in_scope 能力是否有流程支撑
5. 检查 external_dependency 是否有依赖方说明
6. 检查 excluded 节点是否仍被流程或 UI 引用

#### 为什么

即使当前不做多版本管理，单版本仍需要清楚表达边界。范围状态是导出和实施沟通的关键。

### 13.5 页面 05：预览与验证

#### 需要做什么

把页面 05 定义为阶段性 checkpoint。

展示：

```text
阶段 checkpoint
系统级流程预览
角色视角原型
组件树视图
流程回放
问题与修复列表
导出入口
```

#### 怎么做

1. 增加 checkpoint 模式：
   ```text
   初始草稿
   结构草稿
   流程草稿
   交付草稿
   ```
2. 系统流程从 FlowStep、precedes、branches_to 生成
3. 角色原型从 Actor、Screen、UIComponent 生成
4. 组件树从 contains link 生成
5. Issue 卡显示影响范围和建议修复页面
6. 点击 Issue 可跳回对应页面并高亮节点
7. 导出前显示未解决问题数量

#### 为什么

页面 05 是需求空间验证页。它让用户看到当前方案如何运行、哪些角色如何使用、哪里还存在断点。

## 14. RightObjectPanel 改造

### 14.1 需要做什么

把右侧面板改成统一对象编辑器。

支持对象：

```text
Node
Slot
ChoiceGroup
Choice
Issue
LinkTrace
```

### 14.2 怎么做

拆分组件：

```text
NodeEditor
SlotEditor
ChoiceGroupEditor
ChoiceEditor
IssueEditor
TracePanel
ImpactPreviewPanel
```

通用操作：

```text
确认
标记待确认
暂缓
排除
编辑字段
生成候选
采纳候选
拒绝候选
查看影响
跳转来源
```

### 14.3 为什么

用户在五个投影中选择的对象类型不同，但编辑区域应统一。右侧面板是需求空间局部操作的核心入口。

## 15. ScopedAIBar 改造

### 15.1 需要做什么

让底部 AI 条真正按 scope 调用后端能力。

当前模式保留：

```text
展开 Slot
生成候选
检查一致性
局部改写
解释影响
```

### 15.2 怎么做

映射到后端接口：

```text
展开 Slot -> POST /slots/{slotId}/expand
生成候选 -> 按当前 scope 创建 Slot 或扩展 Slot
检查一致性 -> POST /diagnose
局部改写 -> POST /rewrite
解释影响 -> POST /impact
```

提交前要构造 scope：

```ts
type AIScope =
  | { kind: 'workspace' }
  | { kind: 'projection'; projection: ProjectionKind }
  | { kind: 'node'; nodeId: string }
  | { kind: 'slot'; slotId: string }
  | { kind: 'issue'; issueId: string }
  | { kind: 'choiceGroup'; choiceGroupId: string }
```

### 15.3 为什么

AI 操作必须带作用域。没有作用域，AI 难以控制修改范围，用户也无法判断影响。

## 16. 导出方案

### 16.1 需要做什么

导出 Markdown 和 JSON。

Markdown 内容：

```text
项目概述
原始想法
目标与成功标准
角色与职责
核心能力
关键任务
主流程
异常流程
业务规则
业务对象与状态
页面与交互组件
本期范围
暂缓项
外部依赖
待确认问题
已采纳候选记录
```

JSON 内容：

```text
完整 RequirementSpaceIR
```

### 16.2 怎么做

新增：

```http
GET /api/workspaces/{workspace_id}/export/json
GET /api/workspaces/{workspace_id}/export/markdown
```

Markdown 导出先用模板生成，后续再接 LLM 优化语言。

### 16.3 为什么

导出是工作台价值闭环。用户需要把结构化探索结果带到产品、开发、业务沟通场景中。

## 17. 开发阶段安排

### Sprint 1：IR Schema 稳定化

周期：3 到 5 天

要做：

```text
1. 整理 RequirementSpaceIR v0.2
2. 前端 schema.ts 和后端 schema.py 对齐
3. Choice 增加 patch
4. Slot 增加 candidate_ready 和 ownerProjection
5. LinkType 补齐 UI 组件树关系
6. 统一 actorId、flowId、objectId 等 ID 引用
7. seed 数据通过 schema 校验
```

验收：

```text
系统能正常启动
前端能读取默认工作区
后端返回 IR 能通过校验
导出 JSON 结构稳定
```

### Sprint 2：GraphPatch 与 Choice 闭环

周期：4 到 6 天

要做：

```text
1. 重构 GraphPatchService
2. 后端 Choice 保存 patch
3. accept_choice 调用 GraphPatchService
4. Slot 状态随候选采纳更新
5. Issue 可被 patch 解决
6. operationLog 记录关键操作
```

验收：

```text
点击采纳候选后，新增节点进入 IR
新增链接进入 IR
相关 Issue 变为 resolved
相关 Slot 变为 filled
五个页面同步更新
```

### Sprint 3：确定性诊断与 Slot 生成

周期：4 到 6 天

要做：

```text
1. 实现 DiagnosisService
2. 生成 Issue
3. Issue 可触发修复 Slot
4. Slot 可进入待展开状态
5. 页面 01 和页面 05 能显示诊断结果
6. 点击 Issue 可跳转到 suggestedProjection
```

验收：

```text
系统能发现至少 8 类结构性问题
每个 Issue 都有关联节点和建议修复页面
Issue 可以生成 Slot
Slot 可以等待候选展开
```

### Sprint 4：LLM 初始化与 Slot 展开

周期：5 到 7 天

要做：

```text
1. 接入 LLM Provider
2. 实现 InitializeWorkspacePrompt
3. 实现 ExpandSlotPrompt
4. 输出 JSON Schema 校验
5. 初始化失败 fallback 到审批类模板
6. Slot 展开失败给出可读错误
7. 记录 AI source 和 confidence
```

验收：

```text
用户输入一句应用想法
系统生成初始 IR
初始 IR 包含五个投影所需节点
系统生成初始 Issue 和 Slot
用户展开 Slot 后获得 2 到 3 个 Choice
Choice 采纳后真实修改 IR
```

### Sprint 5：五投影页面数据化

周期：5 到 7 天

要做：

```text
1. Overview 接入成熟度、假设账本、决策队列
2. WhatToDo 接入目标化能力树和角色责任矩阵
3. HowItWorks 接入动态泳道、规则、Slot
4. ScopeAndDelivery 接入 scopeStatus 聚合与范围诊断
5. Preview 接入 checkpoint、组件树、问题回跳
6. RightObjectPanel 完成统一对象编辑
```

验收：

```text
五个页面全部从同一份 IR 派生
任意节点修改后相关页面同步变化
所有 Issue 和 Slot 都能定位到来源节点
页面 05 能从问题回跳修复位置
```

### Sprint 6：导出、测试与演示

周期：3 到 5 天

要做：

```text
1. 导出 Markdown
2. 导出 JSON
3. 补齐空状态
4. 补齐错误状态
5. 准备审批类 demo
6. 准备第二个轻应用 demo
7. 进行 3 到 5 个用户测试
```

验收主线：

```text
输入一句话
生成需求空间
确认目标和角色
检查流程
展开 Slot
采纳候选
收敛范围
预览验证
导出方案
```

## 18. 优先级

### P0

```text
IR schema v0.2
GraphPatchService
Choice.patch
accept_choice 应用 patch
确定性诊断
Slot expand 接口
InitializeWorkspacePrompt
ExpandSlotPrompt
五投影 selectors
Markdown 导出
```

### P1

```text
假设账本
阶段 checkpoint
影响预览增强
ScopedRewritePrompt
组件树视图增强
Issue 回跳高亮
操作日志面板
```

### P2

```text
复杂流程画布
多模板组合算法
高保真原型
多用户协作
权限系统
外部系统集成
完整 traceability matrix
复杂版本管理
```

## 19. 风险控制

### 19.1 AI 输出失控

处理方式：

```text
1. 所有 AI 输出必须 JSON Schema 校验
2. 所有写入必须经过 GraphPatchService
3. 所有 patch 必须经过 IR validator
4. scoped rewrite 必须有 allowedNodeIds 和 forbiddenNodeIds
5. 失败时 fallback 到模板或返回可读错误
```

### 19.2 页面逻辑重复

处理方式：

```text
1. 建立 selectors
2. 页面只消费投影结果
3. 不在页面内直接拼复杂 link
4. 复杂派生逻辑写单元测试
```

### 19.3 数据结构膨胀

处理方式：

```text
1. 优先保持 Node + Link + Slot + Choice + Issue 核心结构
2. 新字段先进入 extra
3. 稳定后再进入强类型 schema
4. 避免为每个页面新增独立数据模型
```

### 19.4 UI 超前于后端

处理方式：

```text
1. 当前 UI 已足够支撑 MVP
2. 后续优先补 IR 引擎和 AI 结构化输出
3. 页面新增功能必须对应 IR 数据
4. 没有 IR 支撑的展示先不做
```

## 20. 最终验收标准

系统达到以下效果即完成当前阶段：

```text
1. 用户能从一句话创建工作台
2. 系统生成结构化需求空间 IR
3. 五个投影都能从 IR 渲染
4. 系统能发现结构性问题
5. 系统能为问题生成 Slot
6. AI 能为 Slot 生成 Choice
7. 用户采纳 Choice 后 IR 真实变化
8. 页面 05 能展示流程、角色原型、组件树和问题
9. 问题能回跳到对应页面修复
10. 系统能导出 Markdown 和 JSON
```

最终形态：

```text
RequirementSpace Workbench 的定位：

```text
围绕结构化需求空间 IR，让用户和 AI 逐步探索、决策、修复、验证和导出的工作台。
```
