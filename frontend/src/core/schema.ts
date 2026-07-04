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

export type ScopeStatus = 'current' | 'postponed' | 'exclude';

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
  updatedAt?: string;
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
  updatedAt?: string;
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
  updatedAt?: string;
}

// 功能范围 (Kano)
export interface ScopeNode {
  kind: 'scope';
  scopeId: number;
  scopeStatus: ScopeStatus;
  reason: string;
  confirmationStatus?: NodeStatus;
  positiveSummary: string | null;
  negativeSummary: string | null;
  positivePictureBase64: string | null;
  negativePictureBase64: string | null;
  kanoCategory?: string | null;
  kanoCategoryName?: string | null;

  // Compatibility properties for legacy components
  id?: string;
  title?: string;
  description?: string;
  status?: NodeStatus;
  updatedAt?: string;
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
  updatedAt?: string;
}

// 业务对象属性
export interface BusinessObjectAttributeNode {
  kind: 'business_object_attribute';
  businessObjectAttributeId: number;
  businessObjectAttributeName: string;
  businessObjectAttributeDescription: string;
  businessObjectAttributeType: string;
  businessObjectAttributeExample: string;
  confirmationStatus?: NodeStatus;

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
  confirmationStatus?: NodeStatus;
  businessObjectAttributes: BusinessObjectAttributeNode[];

  // Compatibility properties for legacy components
  id?: string;
  title?: string;
  description?: string;
  status?: NodeStatus;
  updatedAt?: string;
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
  confirmationStatus?: NodeStatus;
  
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
  confirmationStatus?: NodeStatus;
  featureIds: number[];
  flowSteps: FlowStepNode[];

  // Compatibility properties for legacy components
  id?: string;
  title?: string;
  description?: string;
  status?: NodeStatus;
  updatedAt?: string;
}

export type Stage = 'what' | 'how' | 'scope';

export interface StageGateResult {
  stage: Stage;
  mandatoryChecksPassed: boolean;
  passed: boolean;
  issues: Finding[];
  activeSlot?: PerceptionSlot;
  blockingSlot?: PerceptionSlot;
  missingKinds: string[];
}

export interface PageHealth {
  statusCode: 'not_started' | 'in_progress' | 'needs_attention' | 'ready' | 'locked' | 'real_ready' | 'shadow_available' | 'ready_to_advance';
  statusLabel: string;
  disabled: boolean;
  disabledReason?: string;
  issueCount: number;
  hasBlockingSlot: boolean;
  nextSlot?: PerceptionSlot;
}

// 感知槽建议
export interface PerceptionSlot {
  id: string;
  stage: Stage;
  blocking: boolean;                  // 是否阻塞当前阶段 Gate (如：暖场建议为 false)
  kind: string;                       // 槽位类型标识 (如：'missing_scenario')
  description: string;                // 行动引导话术
  targetKind?: string;
  targetId?: number;
  actions: {
    manual?: {
      label: string;
      targetRoute?: string;           // 手动跳转的路径
      targetId?: number;              // 聚焦高亮的目标ID
      focusMode?: 'highlight' | 'modal' | 'scroll';
    };
    ai?: {
      label: string;
      endpoint?: string;              // AI 槽填充请求接口
      payload?: Record<string, unknown>;
    };
  };

  // 兼容老版本的字段，避免底层代码或网络请求映射报错
  kind_legacy?: 'perception_slot';
  perceptionSlotId?: number;
  perceptionKind?: PerceptionKindType;
  perceptionDescription?: string;
  perceptionJobId?: number;
}

export interface PendingManualAction {
  kind: string;
  targetRoute?: string;
  targetKind?: string;
  targetId?: number;
  focusMode?: 'highlight' | 'modal' | 'scroll';
}

// 整个项目空间
export interface RequirementSpace {
  kind: 'requirement_space';
  projectId: string;
  projectName: string;
  projectDescription: string;
  userRequirements: string;
  perceptionSlot: PerceptionSlot | null;
  actors: ActorNode[];
  features: FeatureNode[];
  businessObjects: BusinessObjectNode[];
  flows: FlowNode[];
  kanoStatus?: 'missing' | 'generating' | 'draft_ready' | 'generated' | 'skipped' | 'failed';
  unlockedStages?: string[];

  // Legacy properties for compatibility
  id?: string;
  name?: string;
  nodes?: Record<string, any>;
  links?: Record<string, any>;
  issues?: Record<string, any>;
  slots?: Record<string, any>;
  choiceGroups?: Record<string, any>;
  findings?: Finding[];

  // Compatible properties for selector caching
  actorsCompatible?: any[];
  flowStepsCompatible?: any[];
  linksCompatible?: any[];
  goalsCompatible?: any[];
  capabilitiesCompatible?: any[];
  /** @deprecated Use capabilitiesCompatible instead */
  tasksCompatible?: any[];
  scopeItemsCompatible?: any[];
}

// -------------------------------------------------------------
// UI 映射字典与文案定义
// -------------------------------------------------------------

export const NodeKindToText: Record<NodeKind, string> = {
  actor: '系统参与者',
  feature: '功能结点',
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
  '功能叶子结点': '检测到缺少功能叶子结点',
  '场景结点': '检测到缺少典型场景 (User Story)',
  '成功标准结点': '检测到场景缺少成功标准',
  '流程主结点': '检测到功能缺少系统流程',
  '流程步骤结点': '检测到流程步骤不完整',
};

// -------------------------------------------------------------
// Compatibility Types for existing codebases
// -------------------------------------------------------------
export type FindingType = 'issue' | 'next_suggestion' | 'gate_condition' | 'quality_hint';
export type BlockingScope = 'none' | 'stage_transition' | 'preview' | 'export' | 'checkpoint';

export type IssueCapabilityKind =
  | 'ai_repair'
  | 'generation_draft'
  | 'open_panel'
  | 'manual_action'
  | 'unsupported';

export interface IssueCapability {
  kind: IssueCapabilityKind;
  action_label: string;
  enabled: boolean;
}

export interface Finding {
  findingId: string;
  type: FindingType;
  stage: 'what' | 'how' | 'scope' | 'preview' | 'all';
  code: string;
  title: string;
  description: string;
  severity: 'blocking' | 'warning' | 'info';
  target?: any;
  blockingScope: BlockingScope;
  actionCode?: string;
  metadata?: Record<string, any>;
  capability?: IssueCapability | null;
  status?: 'open' | 'ignored' | 'resolved';
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
  choiceGroupId?: string;
  payload?: any;
  draftType?: string;
  applyMode?: string;
  preview?: any;
  comparisonSummary?: string;
  score?: any;
  error?: any;
}

export interface ChoiceGroup {
  id: string;
  slotId: string;
  status: 'open' | 'resolved' | 'stale' | 'discarded' | 'failed';
  choices: Choice[];
  sourceType?: string;
  issueCode?: string;
  issueId?: string;

  // Compatibility properties for legacy components
  selectionMode?: 'single' | 'multiple';
  generationType?: string;
  target?: any;
  candidateCount?: number;
  successCount?: number;
  failureCount?: number;
  statusDetail?: any;
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
  ai_assumption: 'AI 假设',
  excluded: '已排除',
};

/**
 * 节点类型 → 目标页面路由映射，用于概览页假设账本点击导航
 */
export const NodeKindToRoute: Record<string, (projectId: string) => string> = {
  actor: (id) => `/projects/${id}/what`,
  feature: (id) => `/projects/${id}/what`,
  scenario: (id) => `/projects/${id}/what`,
  acceptance_criterion: (id) => `/projects/${id}/what`,
  scope: (id) => `/projects/${id}/scope`,
  business_object: (id) => `/projects/${id}/flow`,
  flow: (id) => `/projects/${id}/flow`,
};

export const ScopeStatusToText: Record<string, string> = {
  current: '本期',
  postponed: '暂缓',
  exclude: '排除',
  in_scope: '本期',
  deferred: '暂缓',
  external_dependency: '外部依赖',
  out_of_scope: '范围外',
  excluded: '排除',
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

export interface WorkspaceListItem {
  id: string;
  name: string;
  idea: string;
  description?: string;
  updatedAt: string;
  statusCode?: 'not_started' | 'needs_attention' | 'has_issues' | 'scope_pending' | 'in_progress' | 'converged';
  status: string;
  issueCount: number;
  nodeCount: number;
  membershipRole?: string;
  ownerUserId?: number;
  memberCount?: number;
}

export interface ProjectCreationDraft {
  draft_id: string;
  user_requirements: string;
  project_preview: {
    project_name: string;
    project_description: string;
  };
  actors: Array<{ actor_name: string; actor_description: string }>;
  features: Array<{
    feature_number?: string | null;
    feature_name: string;
    feature_description: string;
    actor_names: string[];
  }>;
}

export interface ProjectCreationConfirmResponse {
  projectId?: string;
  project_id: string;
  projectName?: string;
  project_name: string;
  projectDescription?: string;
  project_description: string;
  message: string;
}

export interface ProjectCreationDiscardResponse {
  draft_id: string;
  message: string;
}

export interface ProjectCreationChoiceItem {
  id: string;
  title: string;
  rationale: string;
  status: 'candidate' | 'accepted' | 'rejected' | 'failed' | 'discarded';
  draftType: string;
  applyMode: string;
  payload: any;
  preview: {
    project_name?: string;
    project_description?: string;
    actor_count?: number;
    actors?: string[];
    feature_count?: number;
    features?: string[];
  };
  score?: any;
  comparisonSummary?: string;
  error?: { error_type: string; message: string };
}

export interface ProjectCreationChoiceGroup {
  id: string;
  status: 'open' | 'resolved' | 'discarded' | 'failed';
  generationType: string;
  userRequirements: string;
  candidateCount?: number;
  successCount?: number;
  failureCount?: number;
  statusDetail?: any;
  contextHash?: string;
  createdAt?: number;
  updatedAt?: number;
  resolvedProjectId?: string;
  choices: ProjectCreationChoiceItem[];
}

export interface ProjectCreationChoiceGroupDeferResponse {
  projectId?: string;
  project_id?: string;
  projectName?: string;
  project_name?: string;
  projectDescription?: string;
  project_description?: string;
  choiceGroup?: GenerationChoiceGroup;
  choice_group?: GenerationChoiceGroup;
  message: string;
}

export interface GenerationChoiceGroup {
  id: number | string;
  projectId: string;
  status: string;
  generationType?: string;
  target?: any;
  candidateCount?: number;
  successCount?: number;
  failureCount?: number;
  statusDetail?: any;
  choices: GenerationChoiceItem[];
}

export interface GenerationChoiceItem {
  id: number | string;
  title: string;
  rationale: string;
  status: string;
  draftType?: string;
  applyMode?: string;
  payload?: any;
  preview?: any;
  patch?: any;
  comparisonSummary?: string;
  score?: any;
  error?: any;
}

export interface ProjectMember {
  memberId: number;
  userId: number;
  email: string;
  role: string;
  status: string;
  joinedAt?: string;
  createdAt: string;
  updatedAt: string;
}

export interface KnowledgeWorkspace {
  id: number;
  public_id: string;
  publicId?: string;
  scope: string;
  status: string;
  projectId: number | null;
}

export interface KnowledgeDocument {
  id: number;
  public_id: string;
  workspace_id: number | null;
  project_id: number | null;
  owner_user_id: number;
  original_filename: string;
  content_type: string;
  file_size: number;
  status: 'uploaded' | 'converting' | 'ready' | 'failed' | 'deleted';
  ai_enabled: boolean;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

