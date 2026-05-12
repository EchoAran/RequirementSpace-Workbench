export type NodeKind = 
  | 'goal' | 'capability' | 'actor' | 'task' | 'flow' | 'flow_step' 
  | 'rule' | 'business_object' | 'field' | 'state_machine' 
  | 'object_state' | 'state_transition' | 'screen' | 'ui_component';

export type NodeStatus = 
  | 'ai_assumption' 
  | 'needs_confirmation' 
  | 'confirmed' 
  | 'conflict' 
  | 'deferred' 
  | 'excluded';

export type ScopeStatus = 'in_scope' | 'out_of_scope' | 'deferred' | 'dependency' | 'excluded';

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
  confidence: number;
  scopeStatus?: ScopeStatus;
  source: SourceRecord;
  slots?: string[];
  tags?: string[];
};

export interface GoalNode extends BaseNode { kind: 'goal'; value?: string; note?: string; }
export interface CapabilityNode extends BaseNode { kind: 'capability'; priority?: string; parentId?: string; }
export interface ActorNode extends BaseNode { kind: 'actor'; }
export interface TaskNode extends BaseNode { kind: 'task'; owner?: string; result?: string; }
export interface FlowNode extends BaseNode { kind: 'flow'; trigger?: string; }
export interface FlowStepNode extends BaseNode {
  kind: 'flow_step';
  actor?: string;
  stepType?: string;
  swimlane?: string;
  input?: string[];
  output?: string[];
}
export interface RuleNode extends BaseNode { kind: 'rule'; }
export interface BusinessObjectNode extends BaseNode { kind: 'business_object'; }
export interface FieldNode extends BaseNode { kind: 'field'; }
export interface StateMachineNode extends BaseNode { kind: 'state_machine'; }
export interface ObjectStateNode extends BaseNode { kind: 'object_state'; }
export interface StateTransitionNode extends BaseNode { kind: 'state_transition'; }
export interface ScreenNode extends BaseNode { kind: 'screen'; }
export interface UIComponentNode extends BaseNode { kind: 'ui_component'; }

export type RequirementNode =
  | GoalNode | CapabilityNode | ActorNode | TaskNode | FlowNode | FlowStepNode
  | RuleNode | BusinessObjectNode | FieldNode | StateMachineNode
  | ObjectStateNode | StateTransitionNode | ScreenNode | UIComponentNode;

export type LinkType = 
  | 'realizes' | 'supports' | 'performed_by' | 'owns' | 'precedes' 
  | 'branches_to' | 'guards' | 'reads' | 'writes' | 'changes_state' 
  | 'displayed_on' | 'triggered_by' | 'depends_on' | 'diagnoses';

export type RequirementLink = {
  id: string;
  sourceId: string;
  targetId: string;
  type: LinkType;
  label?: string;
  status: 'active' | 'suspected' | 'invalid';
  source: SourceRecord;
};

export type RequirementSlot = {
  id: string;
  ownerNodeId: string;
  name: string;
  description?: string;
  expectedKinds: NodeKind[];
  arity: 'one' | 'many';
  status: 'empty' | 'expanding' | 'filled' | 'deferred';
  choiceGroupId?: string;
  context: {
    projectionHints: ProjectionKind[];
    relatedNodeIds: string[];
  };
};

export type ChoiceGroup = {
  id: string;
  slotId: string;
  choices: Choice[];
  selectedChoiceId?: string;
  selectionMode: 'single' | 'multiple';
  status: 'open' | 'selected' | 'dismissed';
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

export type Choice = {
  id: string;
  title: string;
  rationale: string;
  proposedNodeIds: string[];
  proposedLinkIds: string[];
  impactPreview: ImpactPreview;
  status: 'candidate' | 'selected' | 'rejected' | 'archived';
};

export type Proposal = {
  id: string;
  // ... extra fields for higher level proposal if needed
};

export type IssueCategory = 
  | 'missing' | 'conflict' | 'ambiguity' | 'scope_risk' 
  | 'flow_gap' | 'data_gap' | 'ui_gap' | 'rule_gap';

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

export type ProjectionKind = 'goal' | 'role' | 'system' | 'data' | 'ui';

export type ProjectionState = {
  goal: { rootGoalIds: string[]; expandedNodeIds: string[]; layout?: any };
  role: { actorIds: string[]; visibleColumns: string[]; layout?: any };
  system: { flowIds: string[]; swimlaneBy: 'actor' | 'system'; highlightedNodeIds: string[]; layout?: any };
  data: { objectIds: string[]; showStates: boolean; showFields: boolean; layout?: any };
  ui: { roleViewIds: string[]; activeActorId?: string; activeScreenId?: string; layout?: any };
};

export type Assumption = {
  id: string;
  description: string;
};

export type RequirementSpaceIR = {
  id: string;
  name: string;
  idea: string;
  domain: {
    taskType?: string;
    templateId?: string;
    assumptions: Assumption[];
  };
  nodes: Record<string, RequirementNode>;
  links: RequirementLink[];
  slots: Record<string, RequirementSlot>;
  choiceGroups: Record<string, ChoiceGroup>;
  proposals: Record<string, Proposal>;
  issues: Record<string, Issue>;
  projections: ProjectionState;
  audit: {
    createdAt: string;
    updatedAt: string;
    sourceSummary: SourceRecord[];
  };
};

export type GraphPatch = {
  addNodes?: RequirementNode[];
  updateNodes?: Partial<RequirementNode>[]; // Needs careful handling for ID
  removeNodeIds?: string[];
  addLinks?: RequirementLink[];
  removeLinkIds?: string[];
  updateSlots?: Partial<RequirementSlot>[];
  resolveIssueIds?: string[];
  createIssueIds?: string[];
};

// Map old type statuses to new for compatibility or UI rendering
export const NodeStatusToText: Record<NodeStatus, string> = {
  'confirmed': '已确认',
  'ai_assumption': 'AI 假设',
  'needs_confirmation': '待确认',
  'conflict': '有冲突',
  'deferred': '暂缓',
  'excluded': '已排除'
};

export const NodeKindToText: Record<string, string> = {
  'goal': '目标',
  'capability': '能力',
  'actor': '角色/系统',
  'task': '任务',
  'flow': '流程',
  'flow_step': '流程步骤',
  'rule': '业务规则',
  'business_object': '数据对象',
  'field': '字段',
  'state_machine': '状态机',
  'object_state': '状态',
  'state_transition': '状态流转',
  'screen': '页面/视图',
  'ui_component': 'UI 组件'
};

export const SourceTypeToText: Record<string, string> = {
  'user': '用户提供',
  'ai': 'AI 推演',
  'system': '系统生成'
};
