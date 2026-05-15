export type NodeKind =
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
  | 'ui_component';

export type NodeStatus =
  | 'ai_assumption'
  | 'needs_confirmation'
  | 'confirmed'
  | 'conflict'
  | 'deferred'
  | 'excluded';

export type ScopeStatus =
  | 'in_scope'
  | 'out_of_scope'
  | 'deferred'
  | 'external_dependency';

export type SourceRecord = {
  type: 'user' | 'ai' | 'system' | 'template' | 'imported';
  text?: string | null;
  refId?: string | null;
  confidence?: number | null;
};

export type BaseNode = {
  id: string;
  kind: NodeKind;
  title: string;
  description: string;
  status: NodeStatus;
  confidence?: number | null;
  scopeStatus: ScopeStatus | null;
  source: SourceRecord;
  tags: string[];
};

export interface GoalNode extends BaseNode {
  kind: 'goal';
  successCriteria?: string[];
}
export interface CapabilityNode extends BaseNode {
  kind: 'capability';
  priority?: 'high' | 'medium' | 'low';
  acceptanceNotes?: string[];
}
export interface ActorNode extends BaseNode {
  kind: 'actor';
  roleType?: 'primary_user' | 'operator' | 'approver' | 'admin' | 'external';
  responsibilities?: string[];
  permissions?: string[];
}
export interface TaskNode extends BaseNode {
  kind: 'task';
  outcome?: string | null;
}
export interface FlowNode extends BaseNode {
  kind: 'flow';
  trigger?: string | null;
}
export interface FlowStepNode extends BaseNode {
  kind: 'flow_step';
  stepType?:
    | 'user_action'
    | 'system_action'
    | 'decision'
    | 'notification'
    | 'state_transition'
    | 'external_call'
    | 'manual_operation';
}
export interface RuleNode extends BaseNode {
  kind: 'rule';
  ruleType?: 'condition' | 'validation' | 'permission' | 'business_policy' | 'calculation' | null;
  expression?: string | null;
  naturalLanguage?: string | null;
}
export interface BusinessObjectNode extends BaseNode {
  kind: 'business_object';
}
export interface FieldNode extends BaseNode {
  kind: 'field';
  fieldType?: 'text' | 'number' | 'date' | 'boolean' | 'enum' | 'file' | 'reference' | null;
  required?: boolean | null;
  valueSource?: 'user_input' | 'system_generated' | 'external' | null;
}
export interface StateMachineNode extends BaseNode {
  kind: 'state_machine';
}
export interface ObjectStateNode extends BaseNode {
  kind: 'object_state';
}
export interface StateTransitionNode extends BaseNode {
  kind: 'state_transition';
}
export interface ScreenNode extends BaseNode {
  kind: 'screen';
  purpose?: string | null;
  route?: string | null;
}
export interface UIComponentNode extends BaseNode {
  kind: 'ui_component';
  componentType?:
    | 'form'
    | 'table'
    | 'detail'
    | 'list'
    | 'button'
    | 'field'
    | 'status_badge'
    | 'dialog'
    | 'navigation'
    | null;
}

export type RequirementNode =
  | GoalNode
  | CapabilityNode
  | ActorNode
  | TaskNode
  | FlowNode
  | FlowStepNode
  | RuleNode
  | BusinessObjectNode
  | FieldNode
  | StateMachineNode
  | ObjectStateNode
  | StateTransitionNode
  | ScreenNode
  | UIComponentNode;

export type LinkType =
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
  ;

export type RequirementLink = {
  id: string;
  sourceId: string;
  targetId: string;
  type: LinkType;
  label?: string | null;
  status: 'active' | 'suspected' | 'invalid';
  source: SourceRecord;
};

export type ProjectionKind = 'goal' | 'role' | 'system' | 'data' | 'ui';

export type SlotStatus = 'empty' | 'expanding' | 'candidate_ready' | 'filled' | 'deferred';

export type RequirementSlot = {
  id: string;
  ownerNodeId: string;
  ownerProjection: ProjectionKind;
  name: string;
  description?: string;
  expectedKinds: NodeKind[];
  arity: 'one' | 'many';
  status: SlotStatus;
  context: {
    projectionHints: ProjectionKind[];
    relatedNodeIds: string[];
    promptHints: string[];
  };
};

export type ImpactPreview = {
  affectedGoals: string[];
  affectedActors: string[];
  affectedFlows: string[];
  affectedObjects: string[];
  affectedScreens: string[];
  newIssues?: string[];
  resolvedIssues?: string[];
};

export type ChoiceGroupStatus = 'open' | 'selected' | 'dismissed';

export type IssueCategory =
  | 'missing'
  | 'conflict'
  | 'ambiguity'
  | 'scope_risk'
  | 'flow_gap'
  | 'data_gap'
  | 'ui_gap'
  | 'rule_gap';

export type Issue = {
  id: string;
  title: string;
  description: string;
  severity: 'low' | 'medium' | 'high';
  category: IssueCategory;
  relatedNodeIds: string[];
  suggestedProjection: ProjectionKind;
  suggestedAction: string;
  status: 'open' | 'resolved' | 'ignored';
  source: SourceRecord;
};

export type GraphPatch = {
  addNodes?: RequirementNode[];
  updateNodes?: ({ id: string } & Partial<RequirementNode>)[];
  removeNodeIds?: string[];
  addLinks?: RequirementLink[];
  updateLinks?: ({ id: string } & Partial<RequirementLink>)[];
  removeLinkIds?: string[];
  addSlots?: RequirementSlot[];
  updateSlots?: ({ id: string } & Partial<RequirementSlot>)[];
  removeSlotIds?: string[];
  addIssues?: Issue[];
  updateIssues?: ({ id: string } & Partial<Issue>)[];
  resolveIssueIds?: string[];
  addChoiceGroups?: ChoiceGroup[];
  updateChoiceGroups?: ({ id: string } & Partial<ChoiceGroup>)[];
};

export type Choice = {
  id: string;
  choiceGroupId: string;
  title: string;
  rationale: string;
  patch: GraphPatch;
  impactPreview: ImpactPreview;
  status: 'candidate' | 'selected' | 'rejected' | 'archived';
};

export type ChoiceGroup = {
  id: string;
  slotId: string;
  choices: Choice[];
  selectedChoiceIds: string[];
  selectionMode: 'single' | 'multiple';
  status: ChoiceGroupStatus;
};

export type Proposal = {
  id: string;
  workspaceId: string;
  title: string;
  summary: string;
  scope: Record<string, unknown>;
  patch: GraphPatch;
  impactPreview: ImpactPreview;
  status: 'draft' | 'candidate' | 'accepted' | 'rejected' | 'archived';
  createdAt: string;
  source: SourceRecord;
};

export type ProjectionState = {
  goal: { expandedNodeIds: string[]; filters: Record<string, string | number | boolean | null>; layout: Record<string, string | number | boolean | null> };
  role: { activeActorId: string | null; filters: Record<string, string | number | boolean | null>; layout: Record<string, string | number | boolean | null> };
  system: { swimlaneBy: 'actor' | 'system'; highlightedNodeIds: string[]; filters: Record<string, string | number | boolean | null>; layout: Record<string, string | number | boolean | null> };
  data: { showStates: boolean; showFields: boolean; filters: Record<string, string | number | boolean | null>; layout: Record<string, string | number | boolean | null> };
  ui: { activeActorId: string | null; activeScreenId: string | null; filters: Record<string, string | number | boolean | null>; layout: Record<string, string | number | boolean | null> };
};

export type Assumption = {
  id: string;
  description: string;
};

export type ProjectMeta = {
  domain?: string | null;
  taskType?: string | null;
  templateId?: string | null;
  inputPrompt?: string | null;
  assumptions: Assumption[];
};

export type AuditInfo = {
  createdAt: string;
  updatedAt: string;
  sourceSummary: SourceRecord[];
  operationLog: OperationRecord[];
};

export type OperationActor = {
  type: SourceRecord['type'];
  refId?: string | null;
};

export type OperationRecord = {
  id: string;
  actionType: string;
  targetIds: string[];
  actor: OperationActor;
  summary: string;
  details: Record<string, unknown>;
  timestamp: string;
};

export type RequirementSpaceIR = {
  id: string;
  name: string;
  idea: string;
  meta: ProjectMeta;
  nodes: Record<string, RequirementNode>;
  links: RequirementLink[];
  slots: Record<string, RequirementSlot>;
  choiceGroups: Record<string, ChoiceGroup>;
  proposals: Record<string, Proposal>;
  issues: Record<string, Issue>;
  projections: ProjectionState;
  audit: AuditInfo;
};

export const NodeStatusToText: Record<NodeStatus, string> = {
  confirmed: '已确认',
  ai_assumption: 'AI 假设',
  needs_confirmation: '待确认',
  conflict: '有冲突',
  deferred: '暂缓',
  excluded: '已排除',
};

export const ScopeStatusToText: Record<ScopeStatus, string> = {
  in_scope: '范围内',
  out_of_scope: '范围外',
  deferred: '延期处理',
  external_dependency: '外部依赖',
};

export const NodeKindToText: Record<string, string> = {
  goal: '目标',
  capability: '能力',
  actor: '角色/系统',
  task: '任务',
  flow: '流程',
  flow_step: '流程步骤',
  rule: '业务规则',
  business_object: '数据对象',
  field: '字段',
  state_machine: '状态机',
  object_state: '状态',
  state_transition: '状态流转',
  screen: '页面/视图',
  ui_component: '界面组件',
};

export const SourceTypeToText: Record<string, string> = {
  user: '用户提供',
  ai: 'AI 推演',
  system: '系统生成',
};
