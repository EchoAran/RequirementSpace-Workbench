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
  type: 'user' | 'ai' | 'system';
  text?: string;
  refId?: string;
};

export type BaseNode = {
  id: string;
  kind: NodeKind;
  title: string;
  description?: string;
  status: NodeStatus;
  confidence?: number;
  scopeStatus?: ScopeStatus;
  source: SourceRecord;
  slots?: string[];
  tags?: string[];
};

export interface GoalNode extends BaseNode {
  kind: 'goal';
  value?: string;
  note?: string;
  successCriteria?: string[];
}
export interface CapabilityNode extends BaseNode {
  kind: 'capability';
  priority?: string;
  parentId?: string;
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
  result?: string;
  actorId?: string;
  capabilityId?: string;
  outcome?: string;
}
export interface FlowNode extends BaseNode {
  kind: 'flow';
  trigger?: string;
  mainObjectId?: string;
}
export interface FlowStepNode extends BaseNode {
  kind: 'flow_step';
  actorId?: string;
  stepType?: string;
  input?: string[];
  output?: string[];
  flowId?: string;
  inputObjectIds?: string[];
  outputObjectIds?: string[];
  ruleIds?: string[];
}
export interface RuleNode extends BaseNode {
  kind: 'rule';
  ruleType?: 'condition' | 'validation' | 'permission' | 'business_policy' | 'calculation';
  expression?: string;
  naturalLanguage?: string;
}
export interface BusinessObjectNode extends BaseNode {
  kind: 'business_object';
  ownerActorId?: string;
  fieldIds?: string[];
  stateMachineId?: string;
}
export interface FieldNode extends BaseNode {
  kind: 'field';
  objectId?: string;
  fieldType?: 'text' | 'number' | 'date' | 'boolean' | 'enum' | 'file' | 'reference';
  required?: boolean;
  valueSource?: 'user_input' | 'system_generated' | 'external';
}
export interface StateMachineNode extends BaseNode {
  kind: 'state_machine';
  objectId?: string;
  stateIds?: string[];
  transitionIds?: string[];
}
export interface ObjectStateNode extends BaseNode {
  kind: 'object_state';
  objectId?: string;
}
export interface StateTransitionNode extends BaseNode {
  kind: 'state_transition';
  fromStateId?: string;
  toStateId?: string;
  triggerStepId?: string;
  ruleIds?: string[];
}
export interface ScreenNode extends BaseNode {
  kind: 'screen';
  actorIds?: string[];
  purpose?: string;
  route?: string;
  rootComponentId?: string;
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
    | 'navigation';
  childIds?: string[];
  dataBindingIds?: string[];
  actionBindingIds?: string[];
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
  | 'contains'
  | 'accessible_by'
  | 'binds_field'
  | 'invokes_step'
  | 'displayed_on'
  | 'triggered_by';

export type RequirementLink = {
  id: string;
  sourceId: string;
  targetId: string;
  type: LinkType;
  label?: string;
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
  choiceGroupId?: string;
  context: {
    projectionHints: ProjectionKind[];
    relatedNodeIds: string[];
    promptHints?: string[];
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
  removeLinkIds?: string[];
  addSlots?: RequirementSlot[];
  updateSlots?: ({ id: string } & Partial<RequirementSlot>)[];
  removeSlotIds?: string[];
  addIssues?: Issue[];
  updateIssues?: ({ id: string } & Partial<Issue>)[];
  resolveIssueIds?: string[];
};

export type Choice = {
  id: string;
  title: string;
  rationale: string;
  patch: GraphPatch;
  impactPreview: ImpactPreview;
  status: 'candidate' | 'selected' | 'rejected' | 'archived';
  proposedNodeIds?: string[];
  proposedLinkIds?: string[];
};

export type ChoiceGroup = {
  id: string;
  slotId: string;
  choices: Choice[];
  selectedChoiceId?: string;
  selectionMode: 'single' | 'multiple';
  status: 'open' | 'selected' | 'dismissed';
};

export type Proposal = {
  id: string;
  title?: string;
  summary?: string;
  patch?: GraphPatch;
  impactPreview?: ImpactPreview;
  createdAt?: string;
  scope?: Record<string, unknown>;
};

export type ProjectionState = {
  goal: { rootGoalIds: string[]; expandedNodeIds: string[]; layout?: unknown };
  role: { actorIds: string[]; visibleColumns: string[]; layout?: unknown };
  system: { flowIds: string[]; swimlaneBy: 'actor' | 'system'; highlightedNodeIds: string[]; layout?: unknown };
  data: { objectIds: string[]; showStates: boolean; showFields: boolean; layout?: unknown };
  ui: { roleViewIds: string[]; activeActorId?: string; activeScreenId?: string; layout?: unknown };
};

export type Assumption = {
  id: string;
  description: string;
};

export type ProjectMeta = {
  domain?: string;
  taskType?: string;
  templateId?: string;
  inputPrompt?: string;
  assumptions: Assumption[];
};

export type AuditInfo = {
  createdAt: string;
  updatedAt: string;
  sourceSummary: SourceRecord[];
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
