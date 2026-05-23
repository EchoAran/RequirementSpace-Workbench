export type NodeKind =
  | 'actor'
  | 'feature'
  | 'scenario'
  | 'acceptance_criterion'
  | 'scope'
  | 'business_object'
  | 'business_object_attribute'
  | 'flow'
  | 'flow_step'
  | 'perception_slot'
  | 'requirement_space'
  | 'task'
  | 'state_transition'
  | 'field'
  | 'state_machine'
  | 'screen'
  | 'goal'
  | 'capability';

export type ScopeStatus = '本期' | '暂缓' | '排除';

export type FlowStepType = 'actorAction' | 'systemAction' | 'judgment';

export type PerceptionKindType =
  | '角色结点'
  | '功能模块结点'
  | '功能叶子结点'
  | '场景结点'
  | '成功标准结点'
  | '流程主结点'
  | '流程步骤结点';

// 角色结点
export interface ActorNode {
  kind: 'actor';
  actorId: number;
  actorName: string;
  actorDescription: string;
  
  // Compatibility properties for legacy components
  id?: string;
  title?: string;
  description?: string;
  status?: NodeStatus;
  scopeStatus?: ScopeStatus | 'in_scope' | 'out_of_scope' | 'external_dependency' | 'deferred';
}

// 成功标准
export interface AcceptanceCriterionNode {
  kind: 'acceptance_criterion';
  criterionId: number;
  criterionContent: string;

  // Compatibility properties for legacy components
  id?: string;
  title?: string;
  description?: string;
  status?: NodeStatus;
}

// 场景/用户故事
export interface ScenarioNode {
  kind: 'scenario';
  scenarioId: number;
  scenarioName: string;
  scenarioContent: string; // 场景描述 / 用户故事
  featureId: number;
  actorId: number;
  acceptanceCriteria: AcceptanceCriterionNode[];

  // Compatibility properties for legacy components
  id?: string;
  title?: string;
  description?: string;
  status?: NodeStatus;
}

// 功能范围 (Kano)
export interface ScopeNode {
  kind: 'scope';
  scopeId: number;
  scopeStatus: ScopeStatus;
  reason: string;
  positiveSummary: string | null;
  negativeSummary: string | null;
  positivePictureBase64: string | null;
  negativePictureBase64: string | null;

  // Compatibility properties for legacy components
  id?: string;
  title?: string;
  description?: string;
  status?: NodeStatus;
}

// 功能结点 (组成特征树)
export interface FeatureNode {
  kind: 'feature';
  featureId: number;
  featureName: string;
  featureDescription: string;
  actorIds: number[];
  parentId: number | null;
  childrenIds: number[];
  scenarios: ScenarioNode[];
  scope: ScopeNode | null;

  // Compatibility properties for legacy components
  id?: string;
  title?: string;
  description?: string;
  status?: NodeStatus;
}

// 业务对象属性
export interface BusinessObjectAttributeNode {
  kind: 'business_object_attribute';
  businessObjectAttributeId: number;
  businessObjectAttributeName: string;
  businessObjectAttributeDescription: string;
  businessObjectAttributeType: string;
  businessObjectAttributeExample: string;

  // Compatibility properties for legacy components
  id?: string;
  title?: string;
  description?: string;
  status?: NodeStatus;
}

// 业务对象主结点
export interface BusinessObjectNode {
  kind: 'business_object';
  businessObjectId: number;
  businessObjectName: string;
  businessObjectDescription: string;
  businessObjectAttributes: BusinessObjectAttributeNode[];

  // Compatibility properties for legacy components
  id?: string;
  title?: string;
  description?: string;
  status?: NodeStatus;
}

// 流程步骤结点
export interface FlowStepNode {
  kind: 'flow_step';
  stepId: number;
  stepName: string;
  stepDescription: string;
  stepType: FlowStepType;
  actorIds: number[];
  inputBusinessObjectIds: number[];
  outputBusinessObjectIds: number[];
  nextStepIds: number[];
  
  // Compatibility properties for legacy components
  id?: string;
  title?: string;
  description?: string;
  status?: NodeStatus;
  position?: number;
}

// 流程主结点
export interface FlowNode {
  kind: 'flow';
  flowId: number;
  flowName: string;
  flowDescription: string;
  featureIds: number[];
  flowSteps: FlowStepNode[];

  // Compatibility properties for legacy components
  id?: string;
  title?: string;
  description?: string;
  status?: NodeStatus;
}

// 感知槽建议
export interface PerceptionSlot {
  kind: 'perception_slot';
  perceptionSlotId: number;
  perceptionKind: PerceptionKindType;
  perceptionDescription: string;
}

// 整个项目空间
export interface RequirementSpace {
  kind: 'requirement_space';
  projectId: number;
  projectName: string;
  projectDescription: string;
  userRequirements: string;
  perceptionSlot: PerceptionSlot | null;
  actors: ActorNode[];
  features: FeatureNode[];
  businessObjects: BusinessObjectNode[];
  flows: FlowNode[];

  // Legacy properties for compatibility
  id?: string;
  name?: string;
  nodes?: Record<string, any>;
  links?: Record<string, any>;
  issues?: Record<string, any>;
  slots?: Record<string, any>;
  choiceGroups?: Record<string, any>;
  proposals?: Record<string, any>;
}

// -------------------------------------------------------------
// UI 映射字典与文案定义
// -------------------------------------------------------------

export const NodeKindToText: Record<NodeKind, string> = {
  actor: '系统参与者',
  feature: '功能节点',
  scenario: '成功场景 (User Story)',
  acceptance_criterion: '成功标准 (AC)',
  scope: '范围分析',
  business_object: '业务对象',
  business_object_attribute: '对象属性',
  flow: '业务流',
  flow_step: '步骤',
  perception_slot: 'AI 槽感知建议',
  requirement_space: '需求空间主座',
  task: '开发任务',
  state_transition: '状态流转',
  field: '字段',
  state_machine: '状态机',
  screen: '页面/屏幕',
  goal: '目标',
  capability: '能力',
};

export const FlowStepTypeToText: Record<FlowStepType, string> = {
  actorAction: '用户动作',
  systemAction: '系统动作',
  judgment: '条件分支/判断',
};

export const PerceptionKindToText: Record<PerceptionKindType, string> = {
  '角色结点': '检测到缺少参与者',
  '功能模块结点': '检测到缺少功能模块',
  '功能叶子结点': '检测到缺少功能叶子节点',
  '场景结点': '检测到缺少典型场景 (User Story)',
  '成功标准结点': '检测到场景缺少成功标准',
  '流程主结点': '检测到功能缺少系统流程',
  '流程步骤结点': '检测到流程步骤不完整',
};

// -------------------------------------------------------------
// Compatibility Types for existing codebases
// -------------------------------------------------------------
export interface Issue {
  id: string;
  title: string;
  description: string;
  severity: 'high' | 'medium' | 'low';
  status: 'open' | 'ignored' | 'resolved';
  relatedNodeIds: string[];
  suggestedProjection: 'goal' | 'role' | 'system' | 'data' | 'ui';
  category?: string;
}

export type RequirementNode =
  | ActorNode
  | FeatureNode
  | ScenarioNode
  | AcceptanceCriterionNode
  | ScopeNode
  | BusinessObjectNode
  | FlowNode
  | FlowStepNode;

export interface BaseNode {
  id: string;
  kind: NodeKind;
  title: string;
  description: string;
  status: 'confirmed' | 'needs_confirmation' | 'ai_assumption';
}

export interface Choice {
  id: string;
  title: string;
  rationale: string;
  status: 'candidate' | 'accepted' | 'rejected';

  // Compatibility properties for legacy components
  patch?: GraphPatch;
  impactPreview?: any;
}

export interface ChoiceGroup {
  id: string;
  slotId: string;
  status: 'open' | 'resolved';
  choices: Choice[];

  // Compatibility properties for legacy components
  selectionMode?: 'single' | 'multiple';
}

export interface Proposal {
  id: string;
  title: string;
  summary: string;
  status: 'candidate' | 'accepted' | 'rejected';
  scope: any;

  // Compatibility properties for legacy components
  patch?: GraphPatch;
  impactPreview?: any;
}

export type NodeStatus = 'confirmed' | 'needs_confirmation' | 'ai_assumption';

export interface GraphPatch {
  updateNodes?: any[];
  deleteNodes?: string[];
  addNodes?: any[];
  addLinks?: any[];
  removeLinkIds?: string[];
  updateSlots?: any[];
  addSlots?: any[];
  addIssues?: any[];
}

export type RequirementLink = any;
export type RequirementSlot = any;
export type ProjectionKind = string;
export type LinkType = string;

export const NodeStatusToText: Record<string, string> = {
  confirmed: '已确认',
  needs_confirmation: '待确认',
  ai_assumption: 'AI 推测',
  excluded: '已排除',
};

export const ScopeStatusToText: Record<string, string> = {
  in_scope: '本期包含',
  deferred: '暂缓处理',
  external_dependency: '外部依赖',
  out_of_scope: '范围外',
  excluded: '已排除',
};

export type ImpactPreview = any;

export type RequirementSpaceIR = RequirementSpace;

export interface GoalNode {
  kind: 'feature';
  featureId: number;
  featureName: string;
  featureDescription: string;
}
export interface CapabilityNode {
  kind: 'feature';
  featureId: number;
  featureName: string;
  featureDescription: string;
}
export interface TaskNode {
  kind: 'feature';
  featureId: number;
  featureName: string;
  featureDescription: string;
}

