# 需求空间表示

## 总览

RML主要分为四类OPSD，从四个视角对需求进行分析和描述。

![](E:\Typora\需求工程\OPSD.webp)

### **O： Object 目标模型**

主要用于描述系统的业务价值，并且根据系统的价值设置功能和需求的优先级。

业务目标模型：说明业务目标、收益、问题和项目动因，用来对齐“为什么做”。
目标链：把高层目标逐层分解到可执行目标，展示目标之间的因果或支撑关系。
关键绩效指标模型，KPIM：定义衡量目标达成情况的指标、度量方式和目标值。
特性树：把产品或系统能力按层级拆成特性，便于范围管理和版本规划。
需求映射矩阵，RMM：把需求与目标、特性、来源、测试等对象建立追踪关系，便于发现遗漏和无关需求。

### **P：Person人员模型**

主要用于描述干系人以及他们的业务流程和目的。

组织结构图：展示组织、部门、角色和汇报关系，用来识别干系人和职责边界。
处理流程：描述人参与的业务处理步骤，重点看人员之间如何协作完成工作。
用例：描述用户或外部角色与系统交互以达成目标的场景。
角色权限矩阵：列出角色与功能、数据或操作权限的对应关系。

### **S：System系统模型**

主要用于描述存在什么系统，用户界面是怎样的，如何交互，如何响应。

生态系统图：展示目标系统与外部系统、用户、组织之间的边界和交互。
系统流程：描述系统内部或系统间的处理流、触发点和顺序。
用户界面流程，UI流程：展示界面之间的跳转路径和用户导航。
显示，动作，响应，DAR模型：把界面显示内容、用户动作、系统响应对应起来。
决策表：用表格表达条件组合与系统行为结果，适合复杂规则。
决策树：用树形路径表达判断逻辑，适合顺序性决策。
系统界面表：列出系统与系统之间的接口、数据、方向、频率和约束。

### **D：Data数据模型**

主要用来描述从最终用户的角度看待业务数据对象之间的关系。
从最终用户，从业务的角度进行分析。干系人想要用数据来做什么，数据是怎么传递和计算的。

业务数据图，BDD：展示业务概念、数据对象及其关系。
数据流图，DFD：展示数据如何在流程、系统、存储和外部实体之间流动。
数据字典：定义数据项、字段含义、格式、约束和来源。
状态表：用表格列出对象状态、触发事件和状态转换。
状态图：用图形展示对象生命周期中的状态变化。
报告表：定义报表内容、字段、来源、计算规则、展示方式和使用者。

## 选择

从四个视角中选择一到两个，在满足完整表达需求空间的基础上，去除冗余以及作用较小的建模类型，保留简洁重要的最优建模簇：

```
目标投影：目标化能力树
角色投影：角色责任矩阵
系统投影：情境泳道流程图
数据投影：业务对象状态模型
UI 投影：角色视角交互组件树
```

## 表达

**RML提到一个非常重要的观点，就是模型的相互验证。**
综合 SQUIRE 的关键启发。

最终需求空间 IR 可以定义为：

```
RequirementSpaceIR =
  Meta
  + Nodes
  + Links
  + Slots
  + ChoiceGroups
  + Issues
  + ProjectionState
  + Audit
```

它的核心原则是：五个视角共享同一份结构化需求事实，目标模型、角色模型、系统模型、数据模型、UI 模型只是对这份 IR 的不同查询和渲染。

SQUIRE 的 SqireIR 启发点在于：用树状中间表示表达结构，用 slot 表达待展开空洞，用 choice 表达可比较候选，用显式作用域控制局部修改，并通过可视化表示帮助用户评审生成结果。论文中明确说明 SqireIR 支持 null operators、choice operators、datum instances、instance identifiers，并强调所有交互都有明确作用域，可保证修改范围可控。 《软件需求可视化模型》则把需求模型组织为目标、人员、系统、数据四大类，这支持我们用 OPSD 作为需求空间的主投影框架。

## 1. 顶层结构

```
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

这样设计的原因：

```
meta 保存项目输入和上下文
nodes 保存需求事实
links 保存跨视角关系
slots 保存待探索空洞
choiceGroups 保存 AI 候选分支
issues 保存一致性诊断
projections 保存前端投影状态
audit 保存来源、置信度、操作痕迹
```

这个顶层结构把“需求表达”和“前端展示”分开。前端页面可以调整，IR 仍然稳定。

## 2. Meta：项目上下文

```
type ProjectMeta = {
  domain?: string
  taskType?: string
  templateId?: string
  inputPrompt: string
  assumptions: Assumption[]
}
```

设计原因：

用户最初通常只给一句话，AI 需要根据任务类型和模板做初始推断。`meta` 保存原始意图、领域、任务类型和 AI 假设，避免后续节点失去来源。

它支撑工作台中的“概览页”，也支撑 AI 后续判断：

```
这是什么类型的轻应用
当前有哪些默认假设
哪些内容来自用户
哪些内容来自 AI 推断
```

## 3. Nodes：需求事实节点

统一节点结构：

```
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

```
type NodeStatus =
  | 'ai_assumption'
  | 'needs_confirmation'
  | 'confirmed'
  | 'conflict'
  | 'deferred'
  | 'excluded'

type ScopeStatus =
  | 'in_scope'
  | 'out_of_scope'
  | 'external_dependency'
  | 'deferred'
```

设计原因：

需求空间探索中，节点经常处于“AI 推断、待确认、已确认、有冲突、暂缓、排除”等状态。状态必须进入 IR，否则前端只能展示静态需求，无法表达 Human AI 协作过程。

### 3.1 目标节点

```
type GoalNode = BaseNode & {
  kind: 'goal'
  successCriteria?: string[]
}

type CapabilityNode = BaseNode & {
  kind: 'capability'
  priority?: 'high' | 'medium' | 'low'
  acceptanceNotes?: string[]
}
```

为什么需要：

目标视角要表达“为什么做”和“本版本形成哪些能力”。能力节点承接目标和具体功能，是目标化能力树的主体。

它支撑目标投影：

```
Goal
  Capability
    AcceptanceNotes
    ScopeStatus
```

### 3.2 角色节点

```
type ActorNode = BaseNode & {
  kind: 'actor'
  roleType: 'primary_user' | 'operator' | 'approver' | 'admin' | 'external'
  responsibilities: string[]
  permissions?: string[]
}
```

为什么需要：

角色是需求空间中的责任边界。流程、数据、UI 都要挂到角色上。角色节点可以生成角色责任矩阵，也可以控制 UI 角色视角原型。

它支撑角色投影：

```
Actor
  Responsibilities
  Permissions
  RelatedTasks
  RelatedScreens
```

### 3.3 系统流程节点

```
type TaskNode = BaseNode & {
  kind: 'task'
  actorId?: NodeId
  capabilityId?: NodeId
  outcome?: string
}

type FlowNode = BaseNode & {
  kind: 'flow'
  trigger?: string
  mainObjectId?: NodeId
}

type FlowStepNode = BaseNode & {
  kind: 'flow_step'
  flowId: NodeId
  stepType:
    | 'user_action'
    | 'system_action'
    | 'decision'
    | 'notification'
    | 'state_transition'
    | 'external_call'
    | 'manual_operation'
  actorId?: NodeId
  inputObjectIds?: NodeId[]
  outputObjectIds?: NodeId[]
  ruleIds?: NodeId[]
}
```

为什么需要：

系统视角要表达“需求如何运作”。单个 FlowStep 是局部修改的最小作用域，适合 AI 在某一步生成候选、补异常、加规则、加通知。

它支撑情境泳道流程图：

```
Actor lane
  FlowStep
    Rule
    Object IO
    StateTransition
```

### 3.4 规则节点

```
type RuleNode = BaseNode & {
  kind: 'rule'
  ruleType:
    | 'condition'
    | 'validation'
    | 'permission'
    | 'business_policy'
    | 'calculation'
  expression?: string
  naturalLanguage: string
}
```

为什么需要：

规则很重要，但无需成为独立投影。规则应挂在流程判断、对象状态迁移、字段校验、权限操作上。这样能保留表达能力，同时控制模型数量。

### 3.5 数据节点

```
type BusinessObjectNode = BaseNode & {
  kind: 'business_object'
  ownerActorId?: NodeId
  fieldIds: NodeId[]
  stateMachineId?: NodeId
}

type FieldNode = BaseNode & {
  kind: 'field'
  objectId: NodeId
  fieldType: 'text' | 'number' | 'date' | 'boolean' | 'enum' | 'file' | 'reference'
  required?: boolean
  source?: 'user_input' | 'system_generated' | 'external'
}

type StateMachineNode = BaseNode & {
  kind: 'state_machine'
  objectId: NodeId
  stateIds: NodeId[]
  transitionIds: NodeId[]
}

type ObjectStateNode = BaseNode & {
  kind: 'object_state'
  objectId: NodeId
}

type StateTransitionNode = BaseNode & {
  kind: 'state_transition'
  fromStateId: NodeId
  toStateId: NodeId
  triggerStepId?: NodeId
  ruleIds?: NodeId[]
}
```

为什么需要：

数据视角要同时表达对象、字段、关系、状态。轻应用需求中，很多问题来自状态流转不清，例如提交、审批、退回、撤回、归档。单纯概念 ER 图表达对象关系，生命周期表达状态变化，IR 中合并为业务对象状态模型更简洁。

### 3.6 UI 节点

```
type ScreenNode = BaseNode & {
  kind: 'screen'
  actorIds: NodeId[]
  purpose?: string
  route?: string
  rootComponentId?: NodeId
}

type UIComponentNode = BaseNode & {
  kind: 'ui_component'
  componentType:
    | 'form'
    | 'table'
    | 'detail'
    | 'list'
    | 'button'
    | 'field'
    | 'status_badge'
    | 'dialog'
    | 'navigation'
  childIds?: NodeId[]
  dataBindingIds?: NodeId[]
  actionBindingIds?: NodeId[]
}
```

为什么需要：

UI 视角要采用组件树。低保真原型只是组件树的渲染结果。组件树能够局部展开、局部替换、局部绑定字段和动作，和 SQUIRE 的组件实例嵌套树保持同构。SQUIRE 中组件定义由模板、组件名、描述、slot 定义组成，组件实例通过 slot 替换形成嵌套结构，这正是 UI 投影最适合借鉴的部分。

## 4. Links：跨视角语义关系

```
type RequirementLink = {
  id: string
  sourceId: NodeId
  targetId: NodeId
  type: LinkType
  status: 'active' | 'suspected' | 'invalid'
  source: SourceRecord
}
```

```
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
  | 'displayed_on'
  | 'triggered_by'
  | 'depends_on'
  | 'diagnoses'
```

为什么需要：

五个投影能合并为一个完整需求空间，关键在 Link。

示例：

```
Capability realizes Goal
Task supports Capability
Actor performs FlowStep
Rule guards FlowStep
FlowStep writes BusinessObject
FlowStep changes_state StateTransition
Screen displayed_on Actor
UIComponent reads Field
UIComponent triggered_by FlowStep
Issue diagnoses Node
```

没有 Links，五个投影会变成五份并列材料。加上 Links 后，系统可以回答：

```
这个页面服务哪个流程
这个流程改变哪个对象状态
这个状态变化由哪个角色触发
这个能力对应哪个目标
这个问题影响哪些视角
```

## 5. Slots：待展开空洞

```
type RequirementSlot = {
  id: SlotId
  ownerNodeId: NodeId
  name: string
  description: string

  expectedKinds: NodeKind[]
  arity: 'one' | 'many'

  status: 'empty' | 'expanding' | 'filled' | 'deferred'
  choiceGroupId?: ChoiceGroupId

  context: {
    projectionHints: ProjectionKind[]
    relatedNodeIds: NodeId[]
  }
}
```

为什么需要：

Slot 是 Human AI 协作探索的入口。它表示“这里需要补充，但当前还没确定”。

例子：

```
流程步骤：经理审批
Slot：退回后如何处理
expectedKinds：rule、flow_step、state_transition、ui_component
```

SQUIRE 用 null operator 表达尚未实例化的位置，并由 slot expansion 生成候选；需求空间 IR 需要同类机制。

## 6. ChoiceGroups：候选分支

```
type ChoiceGroup = {
  id: ChoiceGroupId
  slotId: SlotId
  choices: Choice[]
  selectedChoiceId?: string
  selectionMode: 'single' | 'multiple'
  status: 'open' | 'selected' | 'dismissed'
}

type Choice = {
  id: string
  title: string
  rationale: string
  proposedNodeIds: NodeId[]
  proposedLinkIds: string[]
  impactPreview: ImpactPreview
  status: 'candidate' | 'selected' | 'rejected' | 'archived'
}
```

```
type ImpactPreview = {
  affectedGoals: NodeId[]
  affectedActors: NodeId[]
  affectedFlows: NodeId[]
  affectedObjects: NodeId[]
  affectedScreens: NodeId[]
  newIssues?: IssueId[]
  resolvedIssues?: IssueId[]
}
```

为什么需要：

AI 一次给多个可能方案，用户作为决策函数选择。ChoiceGroup 保留候选分支，支持比较、回看、替换和影响预览。SQUIRE 的 choice operator 可在同一个 IR 中表达多个兼容替代组件，并且选择某个候选后得到具体实例；需求 IR 中的 ChoiceGroup 承担同样职责。

## 7. Proposals：AI 建议单元

```
type Proposal = {
  id: ProposalId
  targetSlotId?: SlotId
  targetNodeId?: NodeId

  intent: string
  proposedNodeIds: NodeId[]
  proposedLinkIds: string[]
  rationale: string

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

为什么需要：

Choice 是分支选择结构，Proposal 是 AI 生成动作的记录。用户可能直接采纳，也可能改写。Proposal 记录“AI 提了什么、为什么这样提、用户如何处理”。

这对解释性和可控性很关键。

## 8. Issues：诊断覆盖层

```
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

为什么需要：

Issue 用于表达 AI 对需求空间的检查结果。它不改变需求事实，只覆盖在节点和链接之上。

典型诊断：

```
流程中存在审批退回，但业务对象缺少“已退回”状态
页面中有提交按钮，但流程中缺少对应 FlowStep
角色可以查看申请单，但权限说明缺失
能力已列入本期范围，但没有任何流程支撑
```

Issue 是页面 05 预览与验证的核心数据来源。

## 9. ProjectionState：投影状态

```
type ProjectionKind = 'goal' | 'role' | 'system' | 'data' | 'ui'

type ProjectionState = {
  goal: {
    rootGoalIds: NodeId[]
    expandedNodeIds: NodeId[]
    layout?: unknown
  }

  role: {
    actorIds: NodeId[]
    visibleColumns: string[]
    layout?: unknown
  }

  system: {
    flowIds: NodeId[]
    swimlaneBy: 'actor' | 'system'
    highlightedNodeIds: NodeId[]
    layout?: unknown
  }

  data: {
    objectIds: NodeId[]
    showFields: boolean
    showStates: boolean
    layout?: unknown
  }

  ui: {
    screenIds: NodeId[]
    activeActorId?: NodeId
    activeScreenId?: NodeId
    layout?: unknown
  }
}
```

为什么需要：

ProjectionState 只保存“怎么看”，不保存“事实是什么”。

五个投影分别对应：

```
goal：目标化能力树
role：角色责任矩阵
system：情境泳道流程图
data：业务对象状态模型
ui：角色视角交互组件树
```

前端五页也应从 ProjectionState 和 Nodes 查询数据：

```
概览页：读取成熟度、Issue、Slot、Choice
要做什么：读取 goal、role
怎么运作：读取 system
范围与交付：读取所有节点的 scopeStatus
预览与验证：读取 system、data、ui、issues
```

投影和页面保持分离，前端交互流程可以变化，IR 的语义结构不受影响。

## 10. Audit：来源与操作痕迹

```
type AuditInfo = {
  createdAt: string
  updatedAt: string
  sourceSummary: SourceRecord[]
  operationLog?: OperationRecord[]
}

type SourceRecord = {
  type: 'user' | 'ai' | 'template' | 'imported'
  text?: string
  confidence?: number
}

type OperationRecord = {
  id: string
  actionType:
    | 'create_node'
    | 'update_node'
    | 'delete_node'
    | 'create_link'
    | 'select_choice'
    | 'resolve_issue'
  targetIds: string[]
  actor: 'user' | 'ai'
  timestamp: string
}
```

为什么需要：

你们当前先不处理版本管理，但单版本内部仍然需要来源和操作痕迹。Audit 不承担版本变迁表达，只承担解释和信任功能。

它回答：

```
这个节点来自用户输入还是 AI 假设
这个候选何时生成
用户选择了哪个方案
哪个问题被忽略或修复
```