# RequirementSpace Workbench 后续开发计划方案 v0.2

## 0. 开发目标

本阶段的目标是把当前前端工作台升级为一个真正围绕 `RequirementSpaceIR` 运转的需求空间探索系统。

系统最终要支持：

```text
用户输入一句话
→ 系统生成初始需求空间 IR
→ 用户通过五个投影查看和编辑需求空间
→ 系统发现 Issue 和 Slot
→ AI 围绕 Slot 生成多个 Choice
→ 用户选择或修改 Choice
→ Choice.patch 写入 IR
→ 五个投影同步刷新
→ 页面 05 执行预览与验证
→ 导出结构化需求方案
```

本阶段的开发重点不是继续堆页面效果，而是建立稳定的 IR 数据模型、GraphPatch 写入机制、Slot 展开机制、Choice 采纳机制、诊断机制和投影派生机制。

---

## 1. 核心设计原则

### 1.1 IR 是唯一事实源

需要做什么：

所有需求事实都必须进入 `RequirementSpaceIR`。目标、角色、流程、数据、UI、问题、候选、来源记录都从 IR 中读取。

怎么做：

前端页面不保存独立业务事实，只通过 selector 从 IR 派生展示数据。后端不维护多套结构化模型，只维护 IR 对象、节点、链接、Slot、Choice、Issue、Audit。

为什么：

五个投影如果各自维护数据，会产生不一致。IR 作为唯一事实源，可以保证一个节点被修改后，目标投影、角色投影、系统投影、数据投影和 UI 投影全部同步变化。

---

### 1.2 投影不是页面

需要做什么：

区分“需求空间投影”和“前端页面”。

五个投影是：

```text
目标投影：目标化能力树
角色投影：角色责任矩阵
系统投影：情境泳道流程图
数据投影：业务对象状态模型
UI 投影：角色视角交互组件树
```

当前五个页面是：

```text
页面 01：概览
页面 02：要做什么
页面 03：怎么运作
页面 04：范围与交付
页面 05：预览与验证
```

怎么做：

页面通过 selector 读取一个或多个投影。比如：

```text
页面 01 读取五个投影的成熟度、Issue、Slot、Choice
页面 02 读取目标投影和角色投影
页面 03 读取系统投影和数据投影
页面 04 读取所有节点的 scopeStatus 和 status
页面 05 读取系统投影、数据投影、UI 投影和 Issue
```

为什么：

页面是用户操作流程，投影是需求空间表达方式。二者分离后，前端页面可以变化，IR 结构仍然稳定。

---

### 1.3 所有 AI 输出都必须结构化

需要做什么：

AI 输出只能进入三类结构：

```text
GraphPatch
Issue
ChoiceGroup
```

怎么做：

所有 Prompt 输出都必须经过 JSON Schema 校验。禁止把自然语言直接写入页面作为正式需求事实。AI 可以解释原因，但正式写入 IR 的内容必须是结构化节点、链接、Slot、Choice、Issue 或 Patch。

为什么：

需求空间工作台要支持可验证、可修改、可追踪的协作过程。自然语言无法可靠地驱动五个投影同步刷新。

---

### 1.4 每次 AI 操作必须有作用域

需要做什么：

AI 操作必须明确作用范围：

```text
workspace
projection
node
slot
issue
choiceGroup
```

怎么做：

ScopedAIBar 发起操作时，必须传入 scope。后端根据 scope 构造局部 IR slice，并限制输出 patch 的影响范围。

为什么：

局部作用域可以避免 AI 因一次局部请求重写整个需求空间。用户更容易理解、比较和采纳 AI 候选。

---

## 2. RequirementSpaceIR v0.2 数据模型

### 2.1 顶层结构

需要做什么：

将后续开发统一到 `RequirementSpaceIR v0.2`。

```ts
type RequirementSpaceIR = {
  id: string
  name: string
  idea: string

  meta: ProjectMeta

  nodes: Record<NodeId, RequirementNode>
  links: RequirementLink[]

  slots: Record<SlotId, RequirementSlot>
  choiceGroups: Record<ChoiceGroupId, ChoiceGroup>
  proposals: Record<ProposalId, Proposal>

  issues: Record<IssueId, Issue>

  projections: ProjectionState

  audit: AuditInfo
}
```

怎么做：

前端 `frontend/src/types.ts` 和后端 Pydantic schema 必须同步。建议新增：

```text
frontend/src/domain/ir/schema.ts
backend/app/ir/schema.py
```

为什么：

当前前后端已有 IR 雏形，但字段语义仍有混用。冻结 v0.2 后，前端、后端、AI 输出、测试用例可以统一对齐。

---

### 2.2 Meta

需要做什么：

`meta` 保存项目上下文和初始化信息。

```ts
type ProjectMeta = {
  domain?: string
  taskType?: string
  templateId?: string
  inputPrompt: string
  assumptions: Assumption[]
}
```

怎么做：

初始化工作区时，把用户原始输入写入 `inputPrompt`。如果系统基于模板或任务类型做推断，要写入 `taskType`、`templateId` 和 `assumptions`。

为什么：

初始输入通常很少，AI 会做推断。把这些推断显式保存，用户才能区分“用户确认的信息”和“AI 假设的信息”。

---

### 2.3 Nodes

需要做什么：

所有需求事实都用统一节点表达。

```ts
type BaseNode = {
  id: NodeId
  kind: NodeKind
  title: string
  description?: string

  status: NodeStatus
  scopeStatus?: ScopeStatus
  confidence?: number

  source: SourceRecord
  slots?: SlotId[]
  tags?: string[]
}
```

节点状态：

```ts
type NodeStatus =
  | 'ai_assumption'
  | 'needs_confirmation'
  | 'confirmed'
  | 'conflict'
  | 'deferred'
  | 'excluded'
```

范围状态：

```ts
type ScopeStatus =
  | 'in_scope'
  | 'out_of_scope'
  | 'external_dependency'
  | 'deferred'
```

怎么做：

保留 `NodeStatus.excluded`。不要把 `excluded` 放入 `ScopeStatus`。页面 04 可以展示“已排除”，但数据来源应是：

```ts
node.status === 'excluded'
```

为什么：

`scopeStatus` 表示范围归属，`status` 表示节点协作状态。两者混用会导致范围页面和节点确认状态产生冲突。

---

### 2.4 NodeKind

需要做什么：

节点类型保持最小完备。

```ts
type NodeKind =
  | 'goal'
  | 'capability'
  | 'actor'
  | 'task'
  | 'flow'
  | 'flow_step'
  | 'rule'
  | 'business_object'
  | 'field'
  | 'state_machine'
  | 'object_state'
  | 'state_transition'
  | 'screen'
  | 'ui_component'
```

怎么做：

后端 seed、AI 输出、前端类型必须使用统一枚举。禁止继续使用临时字符串字段表达正式语义，例如 `actor: '员工'`、`owner: '直属经理'`。应改为 `actorId`，或通过 Link 表达。

为什么：

统一 NodeKind 后，五个投影才能稳定派生。字符串字段只适合展示，不适合作为结构化关系。

---

## 3. 五个投影的实现要求

### 3.1 目标投影：目标化能力树

需要做什么：

目标投影表达：

```text
为什么做
要形成哪些能力
能力属于本期还是暂缓
能力有什么验收点
能力支撑哪个目标
```

核心节点：

```text
GoalNode
CapabilityNode
```

核心链接：

```text
Capability realizes Goal
Task supports Capability
```

怎么做：

前端实现 `selectGoalProjection(ir)`：

```ts
type GoalProjection = {
  roots: GoalViewNode[]
}

type GoalViewNode = {
  goal: GoalNode
  capabilities: CapabilityViewNode[]
}

type CapabilityViewNode = {
  capability: CapabilityNode
  tasks: TaskNode[]
  scopeStatus?: ScopeStatus
  openSlots: RequirementSlot[]
  issues: Issue[]
}
```

为什么：

目标投影承担价值和范围收束。如果能力无法追溯到目标，或范围内能力没有任务支撑，就应产生 Issue。

---

### 3.2 角色投影：角色责任矩阵

需要做什么：

角色投影表达：

```text
谁参与
谁负责
谁执行哪些任务
谁操作哪些流程步骤
谁访问哪些页面
谁操作哪些数据
```

核心节点：

```text
ActorNode
TaskNode
FlowStepNode
ScreenNode
BusinessObjectNode
```

核心链接：

```text
Task performed_by Actor
FlowStep performed_by Actor
Screen accessible_by Actor
Actor owns BusinessObject
```

怎么做：

前端实现 `selectRoleProjection(ir)`：

```ts
type RoleProjection = {
  rows: RoleResponsibilityRow[]
}

type RoleResponsibilityRow = {
  actor: ActorNode
  tasks: TaskNode[]
  flowSteps: FlowStepNode[]
  screens: ScreenNode[]
  objects: BusinessObjectNode[]
  permissions: string[]
  issues: Issue[]
}
```

为什么：

角色是责任边界。目标、流程、数据、UI 都要能回到角色。角色不清会导致流程无法执行、页面权限不清、数据责任不清。

---

### 3.3 系统投影：情境泳道流程图

需要做什么：

系统投影表达：

```text
谁在什么条件下做什么
系统如何响应
流程如何前进
异常如何分支
规则在哪里生效
对象状态在哪里变化
```

核心节点：

```text
FlowNode
FlowStepNode
RuleNode
StateTransitionNode
ActorNode
BusinessObjectNode
```

核心链接：

```text
Flow contains FlowStep
FlowStep precedes FlowStep
FlowStep branches_to FlowStep
FlowStep performed_by Actor
Rule guards FlowStep
FlowStep reads BusinessObject
FlowStep writes BusinessObject
FlowStep changes_state StateTransition
```

怎么做：

前端实现 `selectSystemProjection(ir)`，动态生成泳道：

```ts
type SystemProjection = {
  flows: FlowView[]
}

type FlowView = {
  flow: FlowNode
  lanes: Swimlane[]
}

type Swimlane = {
  actorOrSystemId: string
  label: string
  steps: FlowStepView[]
}
```

泳道不能写死为员工、经理、HR。应从 ActorNode 和系统节点动态生成。

为什么：

系统投影是需求空间的运行视图。它让用户看到需求是否能跑起来，也让系统发现流程断点、规则缺口、异常缺口。

---

### 3.4 数据投影：业务对象状态模型

需要做什么：

数据投影表达：

```text
系统处理什么业务对象
对象有哪些字段
对象有哪些状态
状态如何流转
哪些流程步骤读写对象
哪些页面展示对象
```

核心节点：

```text
BusinessObjectNode
FieldNode
StateMachineNode
ObjectStateNode
StateTransitionNode
FlowStepNode
ScreenNode
UIComponentNode
```

核心链接：

```text
BusinessObject contains Field
BusinessObject owns StateMachine
StateMachine contains ObjectState
StateMachine contains StateTransition
FlowStep reads BusinessObject
FlowStep writes BusinessObject
FlowStep changes_state StateTransition
UIComponent binds_field Field
```

怎么做：

前端实现 `selectDataProjection(ir)`：

```ts
type DataProjection = {
  objects: BusinessObjectView[]
}

type BusinessObjectView = {
  object: BusinessObjectNode
  fields: FieldNode[]
  states: ObjectStateNode[]
  transitions: StateTransitionNode[]
  relatedFlowSteps: FlowStepNode[]
  relatedScreens: ScreenNode[]
  issues: Issue[]
}
```

为什么：

轻应用需求经常在状态流转上出问题，例如提交、审批、退回、撤回、归档。业务对象状态模型能把流程、规则、数据和 UI 串起来。

---

### 3.5 UI 投影：角色视角交互组件树

需要做什么：

UI 投影表达：

```text
每个角色有哪些页面
页面包含哪些组件
组件展示哪些字段
组件触发哪些流程步骤
页面暴露哪些缺口
```

核心节点：

```text
ScreenNode
UIComponentNode
ActorNode
FieldNode
FlowStepNode
BusinessObjectNode
```

核心链接：

```text
Screen accessible_by Actor
Screen contains UIComponent
UIComponent contains UIComponent
UIComponent binds_field Field
UIComponent invokes_step FlowStep
UIComponent reads BusinessObject
```

怎么做：

新增 UI LinkType：

```ts
type LinkType =
  | ...
  | 'contains'
  | 'accessible_by'
  | 'binds_field'
  | 'invokes_step'
```

旧字段兼容策略：

```text
displayed_on：保留旧数据兼容，新数据不再优先使用
triggered_by：保留旧数据兼容，新数据不再优先使用
```

前端实现 `selectUIProjection(ir)`：

```ts
type UIProjection = {
  roleViews: RoleView[]
}

type RoleView = {
  actor: ActorNode
  screens: ScreenView[]
}

type ScreenView = {
  screen: ScreenNode
  componentTree: UIComponentView
}
```

为什么：

低保真原型只是 UI 投影的渲染结果。真正的需求表达应是组件树，这样 AI 才能局部生成、局部替换、绑定字段、绑定流程动作。

---

## 4. Links 语义统一

### 4.1 Link 基础结构

需要做什么：

所有跨视角关系用 Link 表达。

```ts
type RequirementLink = {
  id: string
  sourceId: NodeId
  targetId: NodeId
  type: LinkType
  status: 'active' | 'suspected' | 'invalid'
  source: SourceRecord
}
```

怎么做：

后端写入 Link 前校验：

```text
sourceId 必须存在
targetId 必须存在
type 必须合法
sourceId 和 targetId 的 NodeKind 必须符合 LinkType 约束
```

为什么：

Links 是五个投影形成统一需求空间的关键。没有 Links，五个投影会退化成五份材料。

---

### 4.2 推荐 Link 方向

需要做什么：

统一 Link 方向，避免前后端写反。

推荐方向：

```text
Capability realizes Goal
Task supports Capability
Flow contains FlowStep
Task supports FlowStep
Task performed_by Actor
FlowStep performed_by Actor
FlowStep precedes FlowStep
FlowStep branches_to FlowStep
Rule guards FlowStep
Rule guards StateTransition
FlowStep reads BusinessObject
FlowStep writes BusinessObject
FlowStep changes_state StateTransition
Screen accessible_by Actor
Screen contains UIComponent
UIComponent contains UIComponent
UIComponent binds_field Field
UIComponent invokes_step FlowStep
Issue diagnoses Node
```

怎么做：

建立 `linkRules.ts` 和 `link_rules.py`：

```ts
const LINK_RULES = {
  performed_by: [
    ['task', 'actor'],
    ['flow_step', 'actor']
  ],
  contains: [
    ['flow', 'flow_step'],
    ['screen', 'ui_component'],
    ['ui_component', 'ui_component'],
    ['business_object', 'field'],
    ['state_machine', 'object_state'],
    ['state_machine', 'state_transition']
  ]
}
```

为什么：

Link 方向一旦混乱，投影选择器会越来越复杂，诊断规则也会失准。

---

## 5. Slot 机制

### 5.1 Slot 定义

需要做什么：

Slot 表达需求空间中的待展开空洞。

```ts
type RequirementSlot = {
  id: SlotId
  ownerNodeId: NodeId
  ownerProjection: ProjectionKind

  name: string
  description: string

  expectedKinds: NodeKind[]
  arity: 'one' | 'many'

  status:
    | 'empty'
    | 'expanding'
    | 'candidate_ready'
    | 'filled'
    | 'deferred'

  choiceGroupId?: ChoiceGroupId

  context: {
    projectionHints: ProjectionKind[]
    relatedNodeIds: NodeId[]
    promptHints?: string[]
  }
}
```

怎么做：

每个 Slot 必须有：

```text
ownerNodeId
ownerProjection
expectedKinds
context.relatedNodeIds
```

为什么：

Slot 是 AI 局部生成入口。没有 ownerNodeId，无法限定生成范围；没有 expectedKinds，AI 输出无法约束为结构化节点；没有 ownerProjection，前端无法知道这个 Slot 应在哪里显影。

---

### 5.2 Slot 生命周期

需要做什么：

Slot 生命周期统一为：

```text
empty
expanding
candidate_ready
filled
deferred
```

怎么做：

状态变化规则：

```text
创建 Slot：empty
开始 AI 展开：expanding
候选生成完成：candidate_ready
用户采纳候选：filled
用户暂缓处理：deferred
```

为什么：

`candidate_ready` 能区分“AI 已生成候选但用户还没决策”和“Slot 已完成”。这对决策队列和成熟度计算很重要。

---

### 5.3 Slot 展开接口

需要做什么：

新增专门的 Slot 展开接口。

```http
POST /api/workspaces/{workspace_id}/slots/{slot_id}/expand
```

怎么做：

前端 `generateChoices(slotId)` 调用该接口。不要再用 `runDiagnosis` 代替 Slot 展开。

处理流程：

```text
读取 Slot
读取 ownerNode
读取 context.relatedNodeIds
构造局部 IR slice
调用 ExpandSlotPrompt 或规则生成器
生成 ChoiceGroup
Slot.status = candidate_ready
返回更新后的 workspace
```

为什么：

诊断和展开是两件事。诊断负责发现问题，Slot 展开负责生成候选解决方案。混在一起会导致后端语义不清。

---

## 6. ChoiceGroup 和 GraphPatch

### 6.1 ChoiceGroup 定义

需要做什么：

ChoiceGroup 保存一个 Slot 下的多个候选分支。

```ts
type ChoiceGroup = {
  id: ChoiceGroupId
  slotId: SlotId
  choices: Choice[]
  selectedChoiceId?: string
  selectionMode: 'single' | 'multiple'
  status: 'open' | 'selected' | 'dismissed'
}
```

怎么做：

每个 Slot 最多绑定一个 active ChoiceGroup。需要重新生成时，可以把旧 ChoiceGroup 标记为 `dismissed`，再创建新的 ChoiceGroup。

为什么：

用户需要比较多个候选方案。保留 ChoiceGroup 可以支持回看、拒绝、归档和后续修改。

---

### 6.2 Choice 增加 patch

需要做什么：

`Choice.patch` 是 v0.2 必须新增字段。

```ts
type Choice = {
  id: string
  title: string
  rationale: string

  patch: GraphPatch

  proposedNodeIds?: NodeId[]
  proposedLinkIds?: string[]

  impactPreview: ImpactPreview
  status: 'candidate' | 'selected' | 'rejected' | 'archived'
}
```

怎么做：

AI 生成候选时，必须生成可应用的 `patch`。`proposedNodeIds` 和 `proposedLinkIds` 从 patch 中派生，用于兼容旧 UI。

为什么：

候选的本质是“如果用户采纳，将对 IR 做什么变更”。没有 patch，候选只是说明文字，无法真正进入需求空间。

---

### 6.3 GraphPatch 定义

需要做什么：

统一所有结构化变更。

```ts
type GraphPatch = {
  addNodes?: RequirementNode[]
  updateNodes?: Partial<RequirementNode & { id: string }>[]
  removeNodeIds?: NodeId[]

  addLinks?: RequirementLink[]
  removeLinkIds?: string[]

  addSlots?: RequirementSlot[]
  updateSlots?: Partial<RequirementSlot & { id: string }>[]
  removeSlotIds?: SlotId[]

  addIssues?: Issue[]
  updateIssues?: Partial<Issue & { id: string }>[]
  resolveIssueIds?: IssueId[]
}
```

怎么做：

后端所有 AI 变更、用户局部改写、候选采纳都统一走 `GraphPatchService.apply()`。

为什么：

统一写入入口可以集中做校验、审计、回滚准备和一致性诊断。否则后端会出现多条不一致的数据修改路径。

---

### 6.4 Choice 采纳流程

需要做什么：

`accept_choice` 要真正应用 patch。

怎么做：

流程：

```text
读取 Choice
读取 Choice.patch
校验 patch
应用 patch
Choice.status = selected
ChoiceGroup.status = selected
ChoiceGroup.selectedChoiceId = choice.id
同组其他 candidate 变为 rejected
Slot.status = filled
resolveIssueIds 对应 Issue 标记 resolved
写入 operationLog
重新运行受影响范围诊断
返回 workspace
```

为什么：

用户采纳候选后，需求空间必须真实改变。仅修改候选状态无法支撑五个投影同步更新。

---

## 7. Proposal、Choice、Patch、Audit 的分工

### 7.1 Proposal

需要做什么：

Proposal 记录一次 AI 行为。

```ts
type Proposal = {
  id: ProposalId
  targetSlotId?: SlotId
  targetNodeId?: NodeId
  targetIssueId?: IssueId

  intent: string
  rationale: string

  createdChoiceGroupIds?: ChoiceGroupId[]
  patch?: GraphPatch

  status:
    | 'draft'
    | 'presented'
    | 'accepted'
    | 'rejected'
    | 'edited'

  createdBy: 'ai'
  createdAt: string
}
```

怎么做：

AI 每次被调用时创建 Proposal。Proposal 可以生成一个 ChoiceGroup，也可以直接生成一个 Patch 草案。

为什么：

Proposal 用来解释“AI 这次做了什么”。Choice 用来表达候选分支。Patch 用来表达结构化变更。三者职责不同。

---

### 7.2 三者关系

需要做什么：

明确关系：

```text
Proposal：一次 AI 行为记录
Choice：某个 Slot 下的可选方案
GraphPatch：采纳方案后要写入 IR 的结构化变更
```

怎么做：

推荐流程：

```text
AI 生成 Proposal
Proposal 创建 ChoiceGroup
ChoiceGroup 包含多个 Choice
每个 Choice 携带 GraphPatch
用户采纳 Choice
GraphPatch 写入 IR
Audit 记录 select_choice 和 apply_patch
```

为什么：

这样可以同时满足解释性、可比较性和可执行性。

---

### 7.3 Audit

需要做什么：

所有关键操作写入 `operationLog`。

```ts
type OperationRecord = {
  id: string
  actionType:
    | 'create_node'
    | 'update_node'
    | 'delete_node'
    | 'create_link'
    | 'delete_link'
    | 'create_slot'
    | 'expand_slot'
    | 'select_choice'
    | 'reject_choice'
    | 'apply_patch'
    | 'create_issue'
    | 'resolve_issue'
  targetIds: string[]
  actor: 'user' | 'ai' | 'system'
  timestamp: string
  summary?: string
}
```

怎么做：

GraphPatchService、SlotService、ChoiceService、DiagnosisService 都必须写 audit。

为什么：

单版本内部也需要来源和操作痕迹。用户需要知道某个节点来自用户输入、AI 假设、模板初始化还是后续候选采纳。

---

## 8. Issue 诊断机制

### 8.1 Issue 定义

需要做什么：

Issue 作为诊断覆盖层。

```ts
type Issue = {
  id: IssueId
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

  relatedNodeIds: NodeId[]
  suggestedProjection: ProjectionKind
  suggestedAction: string

  status: 'open' | 'resolved' | 'ignored'
  source: SourceRecord
}
```

怎么做：

Issue 不直接改变需求事实，只指向相关节点。修复 Issue 时，应生成 Slot 或 Choice，而不是直接修改自然语言说明。

为什么：

Issue 是诊断结果。把 Issue 和正式需求事实分开，可以让用户先理解问题，再选择是否修复。

---

### 8.2 确定性诊断规则

需要做什么：

先实现稳定规则诊断，再接入 LLM 语义诊断。

P0 规则：

```text
目标没有能力
范围内能力没有任务
任务没有角色
流程没有开始节点
流程没有结束节点
判断节点没有分支
流程步骤没有 actorId 或 system lane
范围内能力没有 flow_step 支撑
screen 没有 accessible_by actor
ui_component 没有归属 screen 或父组件
```

P1 规则：

```text
业务对象没有字段
业务对象没有状态机
状态迁移没有触发流程步骤
流程步骤写入对象但对象没有字段
UI 操作没有 invokes_step
UI 字段没有 binds_field
通知节点没有通知对象或渠道
外部依赖没有依赖方说明
```

怎么做：

新增：

```text
backend/app/ir/diagnostics.py
frontend/src/domain/ir/invariants.ts
```

每条诊断输出标准 Issue。

为什么：

确定性诊断可测试、稳定、成本低，是页面 05 预览与验证的基础。

---

### 8.3 Issue 触发 Slot

需要做什么：

高价值 Issue 可以自动创建修复 Slot。

怎么做：

例如：

```text
Issue：退回逻辑分支断层
relatedNodeIds：经理审批 FlowStep
suggestedProjection：system
```

自动生成：

```text
Slot：补充退回后处理方式
ownerNodeId：经理审批 FlowStep
ownerProjection：system
expectedKinds：rule、flow_step、state_transition、ui_component
```

为什么：

Issue 发现问题，Slot 打开修复入口，Choice 提供候选方案。这个链路构成完整协作闭环。

---

## 9. 后端服务拆分

### 9.1 目录结构

需要做什么：

把业务逻辑从路由和 crud 中拆出来。

```text
backend/app/ir/
  schema.py
  validators.py
  link_rules.py
  graph_patch.py
  projections.py
  diagnostics.py
  prompts.py
  llm.py
  services.py
```

怎么做：

`main.py` 保留路由。`crud.py` 只做数据库读写。IR 业务逻辑全部进入 `backend/app/ir/`。

为什么：

当前后端功能会快速增长，如果继续堆在 crud 和 main 中，后续会难以维护和测试。

---

### 9.2 WorkspaceService

需要做什么：

管理工作区生命周期。

```text
create_workspace
load_workspace
serialize_workspace
export_workspace
```

怎么做：

接管当前 bootstrap、get、export 逻辑。初始化时先走 LLM，失败时使用本地模板 fallback。

为什么：

Workspace 是 IR 的容器。集中管理可以统一初始化、序列化和导出。

---

### 9.3 GraphPatchService

需要做什么：

作为所有结构化变更的唯一写入入口。

```text
validate_patch
apply_patch
write_audit
run_post_diagnosis
```

怎么做：

所有 Choice 采纳、局部改写、手动编辑的结构变更都调用 GraphPatchService。

为什么：

这样可以保证每次写入都经过校验和审计。

---

### 9.4 SlotService

需要做什么：

管理 Slot。

```text
create_slot
expand_slot
defer_slot
fill_slot
```

怎么做：

实现 `/slots/{slot_id}/expand`。Slot 展开时读取局部 IR slice，生成 ChoiceGroup。

为什么：

Slot 是 AI 探索入口，应独立于诊断服务。

---

### 9.5 ChoiceService

需要做什么：

管理候选分支。

```text
accept_choice
reject_choice
archive_choice
preview_choice_impact
```

怎么做：

`accept_choice` 调用 GraphPatchService。`reject_choice` 只改 Choice 状态，不改 IR 事实节点。

为什么：

候选管理和图写入要解耦。这样可以支持比较、拒绝、回看、重写。

---

### 9.6 DiagnosisService

需要做什么：

生成 Issue 和修复 Slot。

```text
run_deterministic_diagnosis
run_semantic_diagnosis
create_repair_slots
```

怎么做：

先实现确定性诊断。LLM 诊断放到后续阶段。

为什么：

诊断是系统差异化能力，也是页面 05 的核心数据来源。

---

### 9.7 ProjectionService

需要做什么：

从 IR 计算五个投影。

```text
build_goal_projection
build_role_projection
build_system_projection
build_data_projection
build_ui_projection
build_readiness
build_decision_queue
```

怎么做：

ProjectionService 只计算，不写入事实。可以缓存，但缓存必须能从 IR 重建。

为什么：

ProjectionState 只保存“怎么看”，不能成为第二份事实源。

---

## 10. 前端改造

### 10.1 前端目录结构

需要做什么：

拆出 domain 层。

```text
frontend/src/domain/ir/
  schema.ts
  linkRules.ts
  selectors.ts
  invariants.ts
  commands.ts

frontend/src/domain/projections/
  goal.ts
  role.ts
  system.ts
  data.ts
  ui.ts
```

怎么做：

`useWorkspaceStore.ts` 只保存：

```text
当前 IR
当前选中对象
加载状态
错误状态
当前页面
```

复杂查询全部迁移到 selectors。

为什么：

页面组件不应直接遍历 IR 拼业务逻辑。否则五页会出现重复计算和语义不一致。

---

### 10.2 ScopedAIBar 改造

需要做什么：

ScopedAIBar 的操作必须对接真实后端能力。

模式：

```text
展开 Slot
生成候选
检查一致性
局部改写
解释影响
```

怎么做：

映射：

```text
展开 Slot → POST /slots/{slot_id}/expand
生成候选 → 如果选中 Issue，先创建修复 Slot，再 expand
检查一致性 → POST /diagnose
局部改写 → POST /rewrite
解释影响 → POST /impact-preview
```

为什么：

当前 ScopedAIBar 已有作用域概念，但后端功能尚未真实对应。打通后，它将成为 Human AI 协作的主入口。

---

### 10.3 RightObjectPanel 改造

需要做什么：

右侧面板拆成对象编辑器。

```text
NodeEditor
SlotEditor
ChoiceGroupEditor
ChoiceEditor
IssueEditor
TracePanel
```

怎么做：

根据 selectedObject 类型渲染不同编辑器。

为什么：

Node、Slot、Choice、Issue 的操作语义不同。混在一个大面板里会导致交互复杂、代码难维护。

---

### 10.4 页面 01：概览

需要做什么：

页面 01 展示全局状态、假设账本、成熟度、决策队列。

核心模块：

```text
整体成熟度
五投影覆盖度
高风险 Issue
待决策 Slot
开放 ChoiceGroup
假设账本
下一步建议
```

怎么做：

读取：

```text
selectReadiness(ir)
selectDecisionQueue(ir)
selectAssumptions(ir)
selectOpenIssues(ir)
selectCandidateReadySlots(ir)
```

为什么：

概览页是控制台。用户需要知道当前需求空间哪里已收敛、哪里仍需决策。

---

### 10.5 页面 02：要做什么

需要做什么：

页面 02 展示目标化能力树和角色责任矩阵。

核心模块：

```text
主目标
能力树
角色责任矩阵
任务映射
范围状态
开放 Slot
```

怎么做：

读取：

```text
selectGoalProjection(ir)
selectRoleProjection(ir)
```

为什么：

这个页面回答“做什么”和“谁参与”。它应优先帮助用户确认目标、能力、角色和任务。

---

### 10.6 页面 03：怎么运作

需要做什么：

页面 03 展示动态情境泳道流程图和业务对象状态摘要。

核心模块：

```text
动态泳道
FlowStep 卡片
流程分支
规则节点
Slot 空洞
业务对象状态摘要
流程 Issue
```

怎么做：

读取：

```text
selectSystemProjection(ir)
selectDataProjection(ir)
selectIssuesByProjection(ir, 'system')
```

为什么：

这个页面回答“需求如何运行”。Slot 主要在这里被显影和展开。

---

### 10.7 页面 04：范围与交付

需要做什么：

页面 04 聚合所有节点的范围状态。

核心模块：

```text
本期包含
暂缓
外部依赖
范围外
已排除
范围冲突
导出准备度
```

怎么做：

数据规则：

```text
本期包含：scopeStatus = in_scope
暂缓：scopeStatus = deferred
外部依赖：scopeStatus = external_dependency
范围外：scopeStatus = out_of_scope
已排除：status = excluded
```

为什么：

范围是节点属性，不是独立需求对象。用聚合视图展示即可，避免创建第六个投影。

---

### 10.8 页面 05：预览与验证

需要做什么：

页面 05 成为贯穿过程的 checkpoint。

核心模块：

```text
阶段性 checkpoint
系统级流程预览
角色视角原型
组件树视图
流程回放
遗留 Issue
问题回跳修复
导出入口
```

怎么做：

Checkpoint 阶段：

```text
初始草稿 checkpoint：看假设和关键缺口
结构草稿 checkpoint：看目标、角色、任务
流程草稿 checkpoint：看流程、规则、状态
交付草稿 checkpoint：看 UI、范围、导出准备度
```

为什么：

页面 05 的价值是让需求空间“跑一遍”，暴露跨视角问题，并把用户带回对应位置修复。

---

## 11. LLM 接入计划

### 11.1 Prompt 类型

需要做什么：

先实现 5 个稳定 Prompt。

```text
InitializeWorkspacePrompt
DiagnoseWorkspacePrompt
ExpandSlotPrompt
ScopedRewritePrompt
GenerateExportPrompt
```

怎么做：

所有 Prompt 输出都用 JSON Schema 校验。失败时使用 fallback 模板或返回结构化错误。

为什么：

稳定 Prompt 比复杂 Agent 更容易落地，也更适合当前 MVP。

---

### 11.2 InitializeWorkspacePrompt

输入：

```json
{
  "idea": "用户输入的一句话",
  "templateHints": ["approval_lite"],
  "schemaVersion": "0.2"
}
```

输出：

```json
{
  "ir": "RequirementSpaceIR"
}
```

要求：

```text
必须生成 Goal、Capability、Actor、Task、Flow、FlowStep、BusinessObject、Screen、初始 Issue、初始 Slot
所有节点必须有 status、source、confidence
所有结构关系必须用 Link 表达
```

为什么：

初始化是第一步体验。它必须生成一个能被五投影立即展示的 IR，而非自然语言摘要。

---

### 11.3 ExpandSlotPrompt

输入：

```json
{
  "slot": "...",
  "ownerNode": "...",
  "relatedNodes": [],
  "relatedLinks": [],
  "projectionContext": "system"
}
```

输出：

```json
{
  "choiceGroup": {
    "slotId": "...",
    "choices": [
      {
        "title": "...",
        "rationale": "...",
        "patch": {},
        "impactPreview": {}
      }
    ]
  }
}
```

为什么：

Slot 展开是核心协作动作。AI 给出多个可比较方案，用户选择后写入 IR。

---

### 11.4 DiagnoseWorkspacePrompt

输入：

```json
{
  "scope": "...",
  "irSlice": "...",
  "deterministicIssues": []
}
```

输出：

```json
{
  "issues": [],
  "repairSlots": []
}
```

为什么：

LLM 诊断用于发现确定性规则覆盖不到的业务语义问题。它应作为确定性诊断的补充。

---

### 11.5 ScopedRewritePrompt

输入：

```json
{
  "scope": "...",
  "instruction": "...",
  "allowedNodeIds": [],
  "forbiddenNodeIds": [],
  "irSlice": "..."
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

为什么：

用户经常会用自然语言局部修改某个节点或投影。ScopedRewritePrompt 能把自然语言修改转成结构化 Patch。

---

## 12. API 设计

### 12.1 保留现有接口

```http
GET  /api/health
GET  /api/workspaces
POST /api/workspaces/bootstrap
GET  /api/workspaces/{workspace_id}
PATCH /api/workspaces/{workspace_id}/nodes/{node_id}
PATCH /api/workspaces/{workspace_id}/nodes/{node_id}/status
PATCH /api/workspaces/{workspace_id}/nodes/{node_id}/scope
POST /api/workspaces/{workspace_id}/diagnose
POST /api/workspaces/{workspace_id}/patch
GET  /api/workspaces/{workspace_id}/export
```

### 12.2 新增接口

```http
POST /api/workspaces/{workspace_id}/slots
POST /api/workspaces/{workspace_id}/slots/{slot_id}/expand
PATCH /api/workspaces/{workspace_id}/slots/{slot_id}

POST /api/workspaces/{workspace_id}/choices/{choice_id}/accept
POST /api/workspaces/{workspace_id}/choices/{choice_id}/reject

POST /api/workspaces/{workspace_id}/rewrite
POST /api/workspaces/{workspace_id}/impact-preview

GET  /api/workspaces/{workspace_id}/projections/{projection_kind}
```

### 12.3 接口职责

```text
slots/{slot_id}/expand：生成 ChoiceGroup
choices/{choice_id}/accept：应用 Choice.patch
rewrite：把局部自然语言修改转成 Proposal 或 Patch
impact-preview：解释某个 Choice 或 Patch 会影响哪些投影
projections/{kind}：返回后端计算的投影结果
```

为什么：

接口按业务语义组织后，前端调用会更清晰，也能避免把诊断、展开、改写、采纳混成一个接口。

---

## 13. 开发阶段计划

### Sprint 1：IR v0.2 稳定化

目标：

统一前后端 schema，修正字段语义。

需要做什么：

```text
1. 新增 frontend/src/domain/ir/schema.ts
2. 新增 backend/app/ir/schema.py
3. 修正 ScopeStatus，移除 excluded
4. Slot 增加 candidate_ready、ownerProjection
5. Choice 增加 patch
6. LinkType 增加 contains、accessible_by、binds_field、invokes_step
7. 建立 Link 方向规则
8. 统一 FlowStep.stepType 英文枚举
9. 统一 actorId、flowId、capabilityId、objectId
10. seed 数据升级为 v0.2
```

怎么做：

先不接 LLM。用现有 seed 数据升级和测试。

为什么：

Schema 不稳定时继续开发功能，会导致后续大量返工。

验收标准：

```text
前后端类型一致
seed IR 可通过校验
页面可正常加载
所有 link 都能通过规则校验
```

---

### Sprint 2：GraphPatch 与 Choice 采纳闭环

目标：

让候选方案真正改变 IR。

需要做什么：

```text
1. 实现 GraphPatchService
2. Choice 表增加 patch 字段
3. accept_choice 调用 GraphPatchService
4. reject_choice 只修改 Choice 状态
5. apply_patch 写 operationLog
6. 采纳后自动填充 Slot 状态
7. 采纳后解决相关 Issue
```

怎么做：

先用手写 Choice.patch 测试，不接 LLM。

为什么：

这是工作台从“展示候选”变成“用户决策后改变需求空间”的关键。

验收标准：

```text
点击采纳候选
新增节点进入 nodes
新增链接进入 links
相关投影同步刷新
相关 Issue 被解决
Audit 有操作记录
```

---

### Sprint 3：确定性诊断与修复 Slot

目标：

让系统能稳定发现结构缺口，并生成修复入口。

需要做什么：

```text
1. 实现 diagnostics.py
2. 实现 P0 和 P1 诊断规则
3. Issue 可自动创建
4. 高价值 Issue 可生成 repair Slot
5. 页面 05 可展示 Issue 并回跳高亮
```

怎么做：

先不使用 LLM。每条诊断规则都写测试用例。

为什么：

确定性诊断是可靠的基础能力，也是页面 05 的主要价值来源。

验收标准：

```text
缺角色时产生 Issue
缺流程时产生 Issue
判断节点无分支时产生 Issue
对象无状态时产生 Issue
UI 操作无流程绑定时产生 Issue
Issue 可生成 Slot
Slot 可进入决策队列
```

---

### Sprint 4：Slot 展开与 LLM 候选生成

目标：

打通 Slot → ChoiceGroup → Choice.patch。

需要做什么：

```text
1. 接入 LLM Provider
2. 实现 ExpandSlotPrompt
3. 输出 ChoiceGroup JSON
4. 每个 Choice 必须包含 patch
5. JSON Schema 校验失败时返回结构化错误
6. 支持 fallback 规则候选
```

怎么做：

先支持审批类场景中最常见的 Slot：

```text
退回后处理
通知策略
对象状态集合
页面字段补充
审批分支
外部依赖边界
```

为什么：

Slot 展开是 Human AI 协作的核心体验。用户需要在结构化位置比较候选，而非让 AI 一次性重写需求。

验收标准：

```text
点击 Slot 展开
生成 2 到 3 个候选
候选有 rationale
候选有 patch
候选有 impactPreview
采纳后 IR 变化
```

---

### Sprint 5：初始化 IR 生成

目标：

从一句话生成真实需求空间 IR。

需要做什么：

```text
1. 实现 InitializeWorkspacePrompt
2. 输出完整 RequirementSpaceIR
3. 后端校验 IR
4. 失败时 fallback 到本地模板
5. 初始化后自动运行一次确定性诊断
6. 初始化后生成初始 Slot 和 Issue
```

怎么做：

优先支持申请与审批类轻应用。

初始化输出至少包含：

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
Issue
Slot
Link
ProjectionState
Audit
```

为什么：

用户第一步体验必须能看到一个可探索的结构化需求空间，而非静态 demo 数据。

验收标准：

```text
输入一句话
生成可展示 IR
五个页面都有内容
至少产生一个待确认假设
至少产生一个 Slot 或 Issue
```

---

### Sprint 6：五页投影数据化

目标：

让五个页面全部从 selector 派生数据。

需要做什么：

```text
1. Overview 使用 selectReadiness、selectDecisionQueue、selectAssumptions
2. WhatToDo 使用 selectGoalProjection、selectRoleProjection
3. HowItWorks 使用 selectSystemProjection、selectDataProjection
4. ScopeAndDelivery 使用 selectScopeProjection
5. Preview 使用 selectSystemProjection、selectUIProjection、selectIssues
6. RightObjectPanel 支持 Node、Slot、Choice、Issue 编辑
```

怎么做：

逐页替换当前页面内的直接遍历和临时计算逻辑。

为什么：

五页必须展示同一个 IR 的不同侧面，不能各自形成局部模型。

验收标准：

```text
修改一个节点后，相关页面同步变化
修改 scopeStatus 后，范围页同步变化
采纳 Choice 后，流程页和预览页同步变化
解决 Issue 后，概览页和预览页同步变化
```

---

### Sprint 7：预览、回放与导出

目标：

形成可演示 MVP 闭环。

需要做什么：

```text
1. 页面 05 增加阶段性 checkpoint
2. 实现系统流程预览
3. 实现角色视角原型
4. 实现 UI 组件树视图
5. 实现流程回放基础版
6. 实现 Markdown 导出
7. 实现 JSON 导出
```

怎么做：

导出内容包含：

```text
项目目标
能力范围
角色责任
核心任务
主流程
关键规则
业务对象与状态
页面与组件树摘要
本期范围
暂缓项
外部依赖
已排除项
未解决 Issue
AI 假设清单
```

为什么：

导出是工作台结果的外部沟通形式。页面 05 是导出前验证入口。

验收标准：

```text
页面 05 能发现遗留问题
问题能回跳到对应页面
导出文件可读
导出内容能追溯到 IR 节点
```

---

## 14. 当前代码优先修复清单

### 14.1 修复 ScopeStatus

当前需要检查：

```ts
type ScopeStatus = 'in_scope' | 'out_of_scope' | 'deferred' | 'external_dependency' | 'excluded'
```

改为：

```ts
type ScopeStatus = 'in_scope' | 'out_of_scope' | 'deferred' | 'external_dependency'
```

“已排除”使用：

```ts
node.status = 'excluded'
```

---

### 14.2 修复 FlowStep.stepType

当前 seed 中的中文 stepType 需要改为英文枚举：

```text
用户输入 → user_action
系统规则 → decision 或 system_action
界面操作 → user_action
后台动作 → system_action
```

前端展示层负责翻译中文。

---

### 14.3 修复 actor 字符串字段

当前 FlowStep 可能存在：

```ts
actor: '员工'
swimlane: '员工'
```

后续应使用：

```ts
actorId: 'a_employee'
```

或 Link：

```text
FlowStep performed_by Actor
```

旧字段可暂时保留展示兼容，但新逻辑必须使用结构关系。

---

### 14.4 修复 UI 关系

旧关系：

```text
screen -> actor reads
component -> screen displayed_on
component -> flowStep triggered_by
```

新关系：

```text
Screen accessible_by Actor
Screen contains UIComponent
UIComponent invokes_step FlowStep
UIComponent binds_field Field
```

旧关系保留兼容，后续迁移。

---

### 14.5 修改 generateChoices

当前逻辑中，Slot 没有 choiceGroup 时可能调用诊断。应改为：

```ts
generateChoices(slotId) {
  POST /api/workspaces/{id}/slots/{slotId}/expand
}
```

诊断调用保持：

```ts
runDiagnosis(scope) {
  POST /api/workspaces/{id}/diagnose
}
```

---

## 15. 最终验收主线

开发完成后，系统必须稳定支持以下路径：

```text
1. 用户输入一句应用想法
2. 系统生成初始 RequirementSpaceIR
3. 页面 01 显示成熟度、假设、Issue、Slot、Choice
4. 页面 02 确认目标、能力、角色、任务
5. 页面 03 查看流程，发现并展开流程 Slot
6. AI 生成多个 Choice，每个 Choice 带 patch 和影响预览
7. 用户采纳 Choice，GraphPatch 写入 IR
8. 页面 04 调整本期范围、暂缓项、外部依赖、已排除项
9. 页面 05 运行 checkpoint，查看流程、数据、UI 和遗留 Issue
10. 用户回跳修复问题
11. 导出结构化 Markdown 和 JSON
```

MVP 成功标准：

```text
用户能看懂当前需求空间处于什么状态
用户能区分已确认信息和 AI 假设
用户能看到缺口在哪里
用户能围绕 Slot 选择候选方案
用户采纳候选后，五个投影同步变化
用户能通过页面 05 发现跨视角问题
用户能导出可沟通的需求方案
```

---

## 16. 开发优先级总结

```text
P0：IR v0.2 schema 稳定
P0：GraphPatch 写入闭环
P0：Choice.patch 采纳闭环
P0：Slot 展开接口
P0：确定性诊断
P0：五页从 IR selector 派生数据

P1：LLM 初始化
P1：LLM Slot 展开
P1：ScopedRewrite
P1：页面 05 checkpoint
P1：Markdown 导出

P2：流程回放增强
P2：多模板支持
P2：更复杂的 UI 原型交互
P2：高级影响分析
P2：版本管理
```

当前应先完成 P0。P0 完成后，系统才具备真实的需求空间工作台能力。
