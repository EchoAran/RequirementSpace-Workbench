import { create } from 'zustand';
import {
  RequirementSpace,
  ActorNode,
  FeatureNode,
  ScenarioNode,
  AcceptanceCriterionNode,
  ScopeNode,
  BusinessObjectNode,
  BusinessObjectAttributeNode,
  FlowNode,
  FlowStepNode,
  PerceptionSlot,
  ScopeStatus,
  Issue,
  Choice,
  ChoiceGroup,
  GoalNode,
  CapabilityNode,
  TaskNode,
  NodeStatus,
  GraphPatch,
  FlowStepType,
  BaseNode,
  WorkspaceListItem,
} from '@/core/schema';
import { workspaceApi } from '@/lib/api';
import { buildPageHealth } from '@/core/selectors';

export type WorkspacePage = '/' | '/what' | '/flow' | '/scope' | '/preview' | '/overview';

// -------------------------------------------------------------
// Dynamic Static-Analysis Rules-based Issue Detector
// -------------------------------------------------------------
export const detectIssues = (space: RequirementSpace | null): Issue[] => {
  if (!space) return [];
  const issues: Issue[] = [];

  const actors = space.actors || [];
  const features = space.features || [];
  const businessObjects = space.businessObjects || [];
  const flows = space.flows || [];

  // 1. Roles without features
  for (const actor of actors) {
    const isUsed = features.some((f) => (f.actorIds || []).includes(actor.actorId));
    if (!isUsed) {
      issues.push({
        id: `rule_actor_unlinked_${actor.actorId}`,
        title: `参与者角色未关联任何功能`,
        description: `参与者 "${actor.actorName}" 目前在系统架构中没有被任何功能节点引用，请为其添加相应功能，或删除该闲置角色。`,
        severity: 'medium',
        status: 'open',
        relatedNodeIds: [actor.actorId.toString()],
        suggestedProjection: 'role',
        category: 'rule_gap',
      });
    }
  }

  // 2. Features without roles
  for (const feature of features) {
    if ((feature.actorIds || []).length === 0) {
      issues.push({
        id: `rule_feature_no_actor_${feature.featureId}`,
        title: `功能节点未关联任何角色`,
        description: `功能 "${feature.featureName}" 目前未指定任何参与者（执行人），请在该功能的右侧面板中绑定执行角色。`,
        severity: 'high',
        status: 'open',
        relatedNodeIds: [feature.featureId.toString()],
        suggestedProjection: 'goal',
        category: 'rule_gap',
      });
    }

    // 3. Leaf features with empty scenarios
    const isLeaf = (feature.childrenIds || []).length === 0;
    if (isLeaf && (feature.scenarios || []).length === 0) {
      issues.push({
        id: `rule_feature_no_scenarios_${feature.featureId}`,
        title: `叶子功能未定义验收场景`,
        description: `功能节点 "${feature.featureName}" 作为叶子业务节点，尚未描述任何典型成功场景（User Story），可能导致需求不够具象化。`,
        severity: 'medium',
        status: 'open',
        relatedNodeIds: [feature.featureId.toString()],
        suggestedProjection: 'goal',
        category: 'rule_gap',
      });
    }

    // 4. Scenarios without AC
    for (const sc of feature.scenarios || []) {
      if ((sc.acceptanceCriteria || []).length === 0) {
        issues.push({
          id: `rule_scenario_no_ac_${sc.scenarioId}`,
          title: `成功场景缺少验收标准`,
          description: `功能 "${feature.featureName}" 下的场景 "${sc.scenarioName}" 缺少对应的成功标准 (AC)，开发与测试人员将无法验证功能终态。`,
          severity: 'high',
          status: 'open',
          relatedNodeIds: [feature.featureId.toString()],
          suggestedProjection: 'goal',
          category: 'rule_gap',
        });
      }
    }
  }

  // 5. Business objects without attributes
  for (const bo of businessObjects) {
    if ((bo.businessObjectAttributes || []).length === 0) {
      issues.push({
        id: `rule_bo_no_attrs_${bo.businessObjectId}`,
        title: `业务对象缺少字段属性定义`,
        description: `数据实体 "${bo.businessObjectName}" 没有包含任何具体字段属性，建议在其下添加代表业务字段的属性（如 ID、名称、状态等）。`,
        severity: 'medium',
        status: 'open',
        relatedNodeIds: [bo.businessObjectId.toString()],
        suggestedProjection: 'data',
        category: 'rule_gap',
      });
    }
  }

  // 6. Flows without steps
  for (const flow of flows) {
    if ((flow.flowSteps || []).length === 0) {
      issues.push({
        id: `rule_flow_no_steps_${flow.flowId}`,
        title: `业务流程未定义任何步骤`,
        description: `业务流 "${flow.flowName}" 属于空壳流程，没有任何流转的执行步骤，请为其配置用户/系统步骤。`,
        severity: 'high',
        status: 'open',
        relatedNodeIds: [flow.flowId.toString()],
        suggestedProjection: 'system',
      });
    }
  }

  return issues;
};

// -------------------------------------------------------------
// Unified Normalization Helper for Backend Data Synchronization
// -------------------------------------------------------------
const mapBackendIssueToCompatible = (issue: any): Issue => {
  let suggestedProjection: 'goal' | 'role' | 'system' | 'data' | 'ui' = 'goal';
  const stage = issue.stage || '';
  if (stage === 'what') {
    suggestedProjection = 'role';
  } else if (stage === 'how') {
    suggestedProjection = 'system';
  } else if (stage === 'scope') {
    suggestedProjection = 'goal';
  }

  const relatedNodeIds: string[] = [];
  if (issue.target && issue.target.targetId) {
    relatedNodeIds.push(issue.target.targetId.toString());
  }

  return {
    id: issue.issueId || issue.id,
    title: issue.title,
    description: issue.description,
    severity: (issue.severity?.toLowerCase() === 'high' ? 'high' : issue.severity?.toLowerCase() === 'medium' ? 'medium' : 'low') as any,
    status: 'open',
    relatedNodeIds,
    suggestedProjection,
    category: issue.code,
    backendIssueCode: issue.code,
    backendTarget: issue.target,
    backendMetadata: issue.metadata
  };
};

const mapBackendChoiceGroupToCompatible = (cg: any): ChoiceGroup => {
  return {
    id: cg.id.toString(),
    slotId: cg.slotId ? cg.slotId.toString() : '',
    status: cg.status as any,
    selectionMode: cg.selectionMode as any,
    choices: (cg.choices || []).map((c: any) => ({
      id: c.id.toString(),
      title: c.title,
      rationale: c.rationale,
      status: c.status as any,
      patch: c.patch,
      impactPreview: c.impactPreview
    }))
  };
};

const mapResolutionDraftType = (draftType?: string): 'project' | 'actor' | 'feature' | 'flow' | 'scenario' | 'ac' | 'scope' => {
  if (draftType === 'scenario_generation' || draftType === 'scenario') return 'scenario';
  if (draftType === 'acceptance_criteria_generation' || draftType === 'acceptance_criteria' || draftType === 'ac') return 'ac';
  if (draftType === 'scope_generation' || draftType === 'scope') return 'scope';
  if (draftType === 'actor_generation' || draftType === 'actor') return 'actor';
  if (draftType === 'feature_generation' || draftType === 'feature') return 'feature';
  if (draftType === 'flow_generation' || draftType === 'flow') return 'flow';
  if (draftType === 'project_generation' || draftType === 'project') return 'project';
  return 'actor';
};

const getFriendlyErrorMessage = (rawError: string): string => {
  switch (rawError) {
    case 'leaf_feature_without_actor':
      return '⚠️ 当前选择的（或项目内）叶子功能节点未关联任何业务角色！请先在“核心能力特征树”中为该功能模块勾选绑定至少一个角色，然后再发起场景推演。';
    case 'feature_is_not_leaf':
      return '⚠️ 该功能节点不是叶子节点！AI 智能场景推演仅支持针对最底层的“叶子功能节点”进行，请先选择具体的叶子功能节点。';
    case 'empty_leaf_features':
      return '⚠️ 找不到任何可用于生成的叶子功能节点，请先在 What 页面的能力树中创建最底层的叶子功能。';
    case 'project_not_found':
      return '⚠️ 未找到对应的项目空间。';
    case 'empty_actors':
      return '⚠️ 项目中暂无业务角色！请先在 What 页的角色定义中创建至少一个角色。';
    case 'empty_features':
      return '⚠️ 项目中暂无功能节点！请先在 What 页的功能特征树中创建能力模块。';
    case 'feature_not_found':
      return '⚠️ 未找到指定的功能节点。';
    case 'actor_not_found':
      return '⚠️ 未找到指定的业务角色。';
    case 'draft_not_found':
      return '⚠️ AI 推演草稿已失效或过期，请尝试重新点击“AI 智能推演”。';
    default:
      return rawError;
  }
};

const loadBackendIssues = async (projectId: number): Promise<Issue[]> => {
  const stages = ['what', 'how', 'scope', 'preview'];
  const results = await Promise.allSettled(
    stages.map(stage => workspaceApi.listIssues(projectId, stage))
  );

  const allIssues: Issue[] = [];
  results.forEach((res, idx) => {
    if (res.status === 'fulfilled' && res.value && Array.isArray(res.value.issues)) {
      res.value.issues.forEach((bi: any) => {
        allIssues.push(mapBackendIssueToCompatible(bi));
      });
    } else {
      console.warn(`Failed to fetch issues for stage ${stages[idx]}:`, res.status === 'rejected' ? res.reason : 'unknown');
    }
  });
  return allIssues;
};

export const normalizeRequirementSpace = (
  space: RequirementSpace | null,
  backendIssues?: Issue[],
  backendChoiceGroups?: Record<string, ChoiceGroup>
): RequirementSpace | null => {
  console.log('normalizeRequirementSpace called with space:', space?.projectName, 'has_space:', !!space);
  if (!space) return null;

  // 1. Ensure arrays exist
  const actors = space.actors || [];
  const features = space.features || [];
  const businessObjects = space.businessObjects || [];
  const flows = space.flows || [];
  const perceptionSlot = space.perceptionSlot || null;

  // 2. Prepare nodes dictionary
  const nodes: Record<string, any> = {};

  // Actors
  actors.forEach(a => {
    const id = a.actorId.toString();
    nodes[id] = {
      ...a,
      id,
      title: a.actorName,
      description: a.actorDescription,
      status: 'confirmed',
      scopeStatus: 'in_scope'
    };
  });

  // Features (goals/capabilities/tasks)
  features.forEach(f => {
    const id = f.featureId.toString();
    nodes[id] = {
      ...f,
      id,
      title: f.featureName,
      description: f.featureDescription,
      status: 'confirmed',
      scopeStatus: f.scope?.scopeStatus || 'in_scope'
    };
    
    // Scenarios under features
    (f.scenarios || []).forEach(s => {
      const sid = s.scenarioId.toString();
      nodes[sid] = {
        ...s,
        id: sid,
        title: s.scenarioName,
        description: s.scenarioContent,
        status: 'confirmed',
        scopeStatus: 'in_scope'
      };
      
      // Acceptance criteria
      (s.acceptanceCriteria || []).forEach(ac => {
        const acid = ac.criterionId.toString();
        nodes[acid] = {
          ...ac,
          id: acid,
          title: '验收标准',
          description: ac.criterionContent,
          status: 'confirmed',
          scopeStatus: 'in_scope'
        };
      });
    });
  });

  // Business Objects
  businessObjects.forEach(b => {
    const id = b.businessObjectId.toString();
    nodes[id] = {
      ...b,
      id,
      title: b.businessObjectName,
      description: b.businessObjectDescription,
      status: 'confirmed',
      scopeStatus: 'in_scope'
    };
    
    // Attributes
    (b.businessObjectAttributes || []).forEach(attr => {
      const attrId = attr.businessObjectAttributeId.toString();
      nodes[attrId] = {
        ...attr,
        id: attrId,
        title: attr.businessObjectAttributeName,
        description: attr.businessObjectAttributeDescription,
        status: 'confirmed',
        scopeStatus: 'in_scope'
      };
    });
  });

  // Flows and FlowSteps
  flows.forEach(fl => {
    const id = fl.flowId.toString();
    nodes[id] = {
      ...fl,
      id,
      title: fl.flowName,
      description: fl.flowDescription,
      status: 'confirmed',
      scopeStatus: 'in_scope'
    };
    
    // Flow Steps
    (fl.flowSteps || []).forEach(st => {
      const stepId = st.stepId.toString();
      nodes[stepId] = {
        ...st,
        id: stepId,
        title: st.stepName,
        description: st.stepDescription,
        status: 'confirmed',
        scopeStatus: 'in_scope'
      };
    });
  });

  // 3. Synthesized Screens as nodes for layout compatibility
  actors.forEach(actor => {
    businessObjects.forEach(bo => {
      const screenId = `screen_${bo.businessObjectId}`;
      if (!nodes[screenId]) {
        nodes[screenId] = {
          kind: 'screen',
          id: screenId,
          title: `${bo.businessObjectName} 档案看板`,
          description: `提供给 ${actor.actorName} 用于操作 ${bo.businessObjectName} 的控制台及细分账面明细。`,
          status: 'confirmed',
          scopeStatus: 'in_scope'
        };
      }
    });
  });

  // 4. Synthesized Links
  const linksList: any[] = [];
  
  // Accessible_by links: from screen to actor
  actors.forEach(actor => {
    businessObjects.forEach(bo => {
      const screenId = `screen_${bo.businessObjectId}`;
      linksList.push({
        id: `link_accessible_${screenId}_${actor.actorId}`,
        sourceId: screenId,
        targetId: actor.actorId.toString(),
        type: 'accessible_by'
      });
    });
  });

  // Triggers links: from screen to flow step
  flows.forEach(fl => {
    (fl.flowSteps || []).forEach(st => {
      const boIds = [...(st.inputBusinessObjectIds || []), ...(st.outputBusinessObjectIds || [])];
      boIds.forEach(boId => {
        const screenId = `screen_${boId}`;
        linksList.push({
          id: `link_triggers_${screenId}_${st.stepId}`,
          sourceId: screenId,
          targetId: st.stepId.toString(),
          type: 'triggers'
        });
      });
    });
  });

  // 5. Detect and index issues
  const issuesList = backendIssues && backendIssues.length > 0
    ? backendIssues
    : detectIssues({
        ...space,
        actors,
        features,
        businessObjects,
        flows,
        perceptionSlot
      });
  const issuesRecord: Record<string, any> = {};
  issuesList.forEach(i => {
    issuesRecord[i.id] = i;
  });

  // 6. Slots (Perception Slot)
  const slotsRecord: Record<string, any> = {};
  if (perceptionSlot) {
    slotsRecord[perceptionSlot.perceptionSlotId.toString()] = {
      ...perceptionSlot,
      id: perceptionSlot.perceptionSlotId.toString(),
      title: perceptionSlot.perceptionKind,
      description: perceptionSlot.perceptionDescription,
      status: 'empty'
    };
  }

  // 7. Pre-cached compatible arrays for stable select references
  const actorsCompatible = actors.map(a => ({
    ...a,
    id: a.actorId.toString(),
    title: a.actorName,
    description: a.actorDescription,
    status: 'confirmed',
    scopeStatus: 'in_scope'
  }));

  const flowStepsCompatible = flows.flatMap(f => (f.flowSteps || []).map((step, idx) => ({
    ...step,
    id: step.stepId.toString(),
    title: step.stepName,
    description: step.stepDescription,
    status: 'confirmed',
    position: idx + 1
  })));

  const goalsCompatible = features.map(f => ({
    kind: 'feature',
    featureId: f.featureId,
    featureName: f.featureName,
    featureDescription: f.featureDescription
  }));

  const capabilitiesCompatible = goalsCompatible;
  const tasksCompatible = goalsCompatible;
  const scopeItemsCompatible = features.filter(f => f.scope !== null);

  const choiceGroupsRecord = backendChoiceGroups || space.choiceGroups || {};
  const choicesCompatible: Choice[] = [];
  Object.values(choiceGroupsRecord).forEach((cg: any) => {
    if (cg.choices) {
      choicesCompatible.push(...cg.choices);
    }
  });

  return {
    ...space,
    actors,
    features,
    businessObjects,
    flows,
    perceptionSlot,
    nodes,
    links: linksList,
    issues: issuesRecord,
    slots: slotsRecord,
    choiceGroups: choiceGroupsRecord,
    // Stable Selector Cache Fields
    actorsCompatible,
    flowStepsCompatible,
    issuesCompatible: issuesList,
    linksCompatible: linksList,
    goalsCompatible,
    capabilitiesCompatible,
    tasksCompatible,
    scopeItemsCompatible,
    choicesCompatible
  } as any;
};

// Helper for generating IDs
const makeIntId = () => Math.floor(1000 + Math.random() * 9000);

export interface WorkspaceState {
  currentSystemView: 'home' | 'onboarding' | 'workspace';
  setSystemView: (view: 'home' | 'onboarding' | 'workspace') => void;
  initialPrompt: string;

  activePage: WorkspacePage;
  setActivePage: (page: WorkspacePage) => void;

  selectedObjectId: string | number | null;
  selectedObject: any | null;
  setSelectedObject: (obj: any | null) => void;
  selectedNodeId: string | number | null;
  selectedSlotId: string | number | null;
  highlightedNodeIds: string[];

  ir: RequirementSpace | null; // Unified project space matching state.ir for backwards compatibility
  backendIssues: Issue[];
  backendChoiceGroups: Record<string, ChoiceGroup>;
  isDiagnosing: boolean;
  nextSuggestions: Record<string, any>;

  // Draft Generative States
  activeDraft: any | null;
  activeDraftType: 'project' | 'actor' | 'feature' | 'flow' | 'scenario' | 'ac' | 'scope' | null;
  isGenerating: boolean;

  highlightTarget: string | null;
  setHighlightTarget: (id: string | null) => void;
  isLoading: boolean;
  error: string | null;
  lastActionMessage: string | null;
  workspaces: WorkspaceListItem[];

  // Project Lifecycles
  loadWorkspaces: () => Promise<void>;
  openExistingProject: () => Promise<void>;
  openWorkspace: (workspaceId: string) => Promise<void>;
  refreshWorkspace: () => Promise<void>;
  exitWorkspace: () => void;
  updateProject: (projectId: number, name: string, description: string) => Promise<void>;
  deleteProject: (projectId: number) => Promise<void>;

  // Onboarding On-demand Creation
  startAIOnboarding: (prompt: string, name?: string, description?: string) => Promise<void>;
  confirmAIOnboarding: () => Promise<void>;
  regenerateAIOnboarding: (feedback?: string) => Promise<void>;
  discardAIOnboarding: () => Promise<void>;
  createBlankWorkspace: (name: string, description: string, prompt: string) => Promise<void>;

  // AI Generators per phase
  generateActors: () => Promise<void>;
  regenerateActors: (feedback?: string) => Promise<void>;
  confirmActors: () => Promise<void>;
  
  generateFeatures: () => Promise<void>;
  regenerateFeatures: (feedback?: string) => Promise<void>;
  confirmFeatures: () => Promise<void>;
  
  generateFlowsAndObjects: () => Promise<void>;
  regenerateFlowsAndObjects: (feedback?: string) => Promise<void>;
  confirmFlowsAndObjects: () => Promise<void>;
  
  generateScenarios: (featureIds?: number[] | number) => Promise<void>;
  regenerateScenarios: (feedback?: string) => Promise<void>;
  confirmScenarios: (generateAc: boolean) => Promise<void>;
  
  generateAcceptanceCriteria: (scenarioIds?: number[]) => Promise<void>;
  regenerateAcceptanceCriteria: (feedback?: string) => Promise<void>;
  confirmAcceptanceCriteria: () => Promise<void>;
  
  generateScope: () => Promise<void>;
  regenerateScope: (feedback?: string) => Promise<void>;
  confirmScope: () => Promise<void>;
  
  discardDraft: () => Promise<void>;

  // Manual CRUD Actions
  // Actors
  addActor: (name: string, description: string) => Promise<void>;
  updateActor: (actorId: number, updates: Partial<ActorNode>) => Promise<void>;
  deleteActor: (actorId: number) => Promise<void>;

  // Features
  addFeature: (name: string, description: string, parentId: number | null) => Promise<void>;
  updateFeature: (featureId: number, updates: Partial<FeatureNode>) => Promise<void>;
  deleteFeature: (featureId: number) => Promise<void>;

  // Scenarios & ACs
  addScenario: (featureId: number, actorId: number, name: string, content: string) => Promise<void>;
  updateScenario: (featureId: number, scenarioId: number, updates: Partial<ScenarioNode>) => Promise<void>;
  deleteScenario: (featureId: number, scenarioId: number) => Promise<void>;
  
  addAcceptanceCriterion: (featureId: number, scenarioId: number, content: string) => Promise<void>;
  updateAcceptanceCriterion: (featureId: number, scenarioId: number, criterionId: number, content: string) => Promise<void>;
  deleteAcceptanceCriterion: (featureId: number, scenarioId: number, criterionId: number) => Promise<void>;

  // Business Objects
  addBusinessObject: (name: string, description: string) => Promise<void>;
  updateBusinessObject: (id: number, name: string, description: string) => Promise<void>;
  deleteBusinessObject: (id: number) => Promise<void>;
  addBusinessObjectAttribute: (boId: number, name: string, description: string, type: string, example: string) => Promise<void>;
  updateBusinessObjectAttribute: (boId: number, attrId: number, updates: Partial<BusinessObjectAttributeNode>) => Promise<void>;
  deleteBusinessObjectAttribute: (boId: number, attrId: number) => Promise<void>;

  // Flows
  addFlow: (name: string, description: string, featureIds: number[]) => Promise<void>;
  updateFlow: (flowId: number, updates: Partial<FlowNode>) => Promise<void>;
  deleteFlow: (flowId: number) => Promise<void>;
  addFlowStep: (flowId: number, step: {
    stepName: string;
    stepDescription: string;
    stepType: FlowStepType;
    actorIds: number[];
    inputBusinessObjectIds: number[];
    outputBusinessObjectIds: number[];
  }) => Promise<void>;
  updateFlowStep: (flowId: number, stepId: number, updates: Partial<FlowStepNode>) => Promise<void>;
  deleteFlowStep: (flowId: number, stepId: number) => Promise<void>;

  // Scope
  updateScope: (featureId: number, updates: Partial<ScopeNode>) => Promise<void>;
  
  // PerceptionSlot
  clearPerceptionSlot: () => Promise<void>;

  openSlot: (slotId: string) => void;
  expandSlot: (slotId: string) => Promise<void>;
  acceptChoice: (choiceId: string) => Promise<void>;
  rejectChoice: (choiceId: string) => Promise<void>;
  createSlotFromIssue: (issueId: string) => Promise<string | null>;
  setNodeStatus: (nodeId: string, status: NodeStatus) => Promise<void>;
  setScopeStatus: (nodeId: string, scopeStatus: ScopeStatus) => Promise<void>;
  runDiagnosis: (scope: any) => Promise<void>;
  executeNextSuggestion: (stage: string) => Promise<void>;
  rewrite: (scope: any, instruction: string) => Promise<void>;
  explainImpact: (scope: any, patch?: GraphPatch, choiceId?: string) => Promise<void>;
  updateNodeAttributes: (nodeId: string, updates: Partial<BaseNode> & Record<string, any>) => Promise<void>;
  createIssue: (payload: any) => Promise<void>;
  updateIssueAttributes: (issueId: string, updates: any) => Promise<void>;
  updateChoiceAttributes: (choiceId: string, updates: any) => Promise<void>;

  // P5 Audit and Impact
  auditLogs: any[];
  lastImpactPreview: any | null;
  loadAuditLogs: (projectId: number) => Promise<void>;
  getImpactPreview: (featureId: number, nextStatus: string) => Promise<any>;
  addChoiceToGroup: (choiceGroupId: string, payload: any) => Promise<void>;
}

const findSelectedObjectInIr = (ir: RequirementSpace | null, selectedId: string | number | null): any => {
  if (!ir || !selectedId) return null;
  const numId = typeof selectedId === 'string' ? parseInt(selectedId, 10) : selectedId;

  // Search Slots
  if (ir.slots && ir.slots[selectedId.toString()]) {
    return ir.slots[selectedId.toString()];
  }

  // Search Actor
  const actor = ir.actors?.find(a => a.actorId === numId);
  if (actor) return actor;

  // Search Features
  const feature = ir.features?.find(f => f.featureId === numId);
  if (feature) return feature;

  // Search Scenario/AC inside features
  for (const feat of ir.features || []) {
    const scenario = feat.scenarios?.find(s => s.scenarioId === numId);
    if (scenario) return scenario;
    for (const s of feat.scenarios || []) {
      const ac = s.acceptanceCriteria?.find(a => a.criterionId === numId);
      if (ac) return ac;
    }
  }

  // Search Business Objects
  const bo = ir.businessObjects?.find(b => b.businessObjectId === numId);
  if (bo) return bo;
  for (const b of ir.businessObjects || []) {
    const attr = b.businessObjectAttributes?.find(a => a.businessObjectAttributeId === numId);
    if (attr) return attr;
  }

  // Search Flows & steps
  const flow = ir.flows?.find(f => f.flowId === numId);
  if (flow) return flow;
  for (const f of ir.flows || []) {
    const step = f.flowSteps?.find(s => s.stepId === numId);
    if (step) return step;
  }

  // Search dynamic issues
  const issues = detectIssues(ir);
  const matchedIssue = issues.find(i => i.id === selectedId);
  if (matchedIssue) return matchedIssue;

  return null;
};

const withWorkspaceId = (state: WorkspaceState): number => {
  if (!state.ir?.projectId) {
    throw new Error('当前工作区尚未初始化');
  }
  return state.ir.projectId;
};

export const useWorkspaceStore = create<WorkspaceState>((rawSet, get) => {
  const set = (update: any, replace?: boolean) => {
    console.log('Store set called. Update type:', typeof update, 'keys:', typeof update === 'object' && update !== null ? Object.keys(update) : 'function');
    if (typeof update === 'function') {
      (rawSet as any)((state: WorkspaceState) => {
        const next = update(state);
        if (next && 'ir' in next && next.ir !== undefined) {
          const issuesToUse = next.backendIssues || state.backendIssues || [];
          const choiceGroupsToUse = next.backendChoiceGroups || state.backendChoiceGroups || {};
          next.ir = normalizeRequirementSpace(next.ir, issuesToUse, choiceGroupsToUse);
        }
        return next;
      }, replace);
    } else {
      if (update && 'ir' in update && update.ir !== undefined) {
        const issuesToUse = update.backendIssues || get()?.backendIssues || [];
        const choiceGroupsToUse = update.backendChoiceGroups || get()?.backendChoiceGroups || {};
        update.ir = normalizeRequirementSpace(update.ir, issuesToUse, choiceGroupsToUse);
      }
      (rawSet as any)(update, replace);
    }
  };

  return {
    currentSystemView: 'home',
  setSystemView: (view) => set({ currentSystemView: view }),
  initialPrompt: '',

  activePage: '/',
  setActivePage: (page) => set({ activePage: page }),

  selectedObjectId: null,
  selectedObject: null,
  setSelectedObject: (obj) => {
    if (!obj) {
      set({ selectedObjectId: null, selectedObject: null, selectedNodeId: null });
      return;
    }
    const id = obj.actorId || obj.featureId || obj.scenarioId || obj.criterionId || obj.businessObjectId || obj.businessObjectAttributeId || obj.flowId || obj.stepId || obj.id;
    set({
      selectedObjectId: id || null,
      selectedObject: obj,
      selectedNodeId: id || null
    });
  },

  selectedNodeId: null,
  selectedSlotId: null,
  highlightedNodeIds: [],

  ir: null,
  backendIssues: [],
  backendChoiceGroups: {},
  auditLogs: [],
  lastImpactPreview: null,
  isDiagnosing: false,
  nextSuggestions: {},

  // Draft Generative States
  activeDraft: null,
  activeDraftType: null,
  isGenerating: false,

  highlightTarget: null,
  setHighlightTarget: (id) => set({ highlightTarget: id }),
  isLoading: false,
  error: null,
  lastActionMessage: null,
  workspaces: [],

  loadWorkspaces: async () => {
    set({ isLoading: true, error: null });
    try {
      const workspaces = await workspaceApi.list();
      set({ workspaces, isLoading: false });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '加载工作区失败', isLoading: false });
    }
  },

  openExistingProject: async () => {
    set({ isLoading: true, error: null });
    try {
      const list = await workspaceApi.list();
      if (list.length > 0) {
        const space = await workspaceApi.getById(list[0].id);
        set({
          currentSystemView: 'workspace',
          initialPrompt: space.userRequirements,
          ir: space,
          isLoading: false
        });
      } else {
        set({ currentSystemView: 'onboarding', isLoading: false });
      }
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '打开已有项目失败', isLoading: false });
    }
  },

  openWorkspace: async (workspaceId) => {
    set({ isLoading: true, error: null });
    try {
      const space = await workspaceApi.getById(workspaceId);
      const projectId = space.projectId;
      
      let issues: Issue[] = [];
      let choiceGroupsRecord: Record<string, ChoiceGroup> = {};
      
      issues = await loadBackendIssues(projectId);
      try {
        const groups = await workspaceApi.listChoiceGroups(projectId, 'open');
        groups.forEach((cg: any) => {
          const compatible = mapBackendChoiceGroupToCompatible(cg);
          choiceGroupsRecord[compatible.id] = compatible;
        });
      } catch (cgErr) {
        console.warn('Failed to load choice groups:', cgErr);
      }
      await get().loadAuditLogs(projectId);

      set({
        currentSystemView: 'workspace',
        initialPrompt: space.userRequirements,
        backendIssues: issues,
        backendChoiceGroups: choiceGroupsRecord,
        ir: space,
        isLoading: false
      });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '打开工作区失败', isLoading: false });
    }
  },

  refreshWorkspace: async () => {
    const id = get().ir?.projectId;
    if (!id) return;
    try {
      const space = await workspaceApi.getById(id);
      
      let issues: Issue[] = [];
      let choiceGroupsRecord: Record<string, ChoiceGroup> = {};
      
      issues = await loadBackendIssues(id);
      try {
        const groups = await workspaceApi.listChoiceGroups(id, 'open');
        groups.forEach((cg: any) => {
          const compatible = mapBackendChoiceGroupToCompatible(cg);
          choiceGroupsRecord[compatible.id] = compatible;
        });
      } catch (cgErr) {
        console.warn('Failed to load choice groups in refresh:', cgErr);
      }
      await get().loadAuditLogs(id);

      set((s) => ({
        backendIssues: issues,
        backendChoiceGroups: choiceGroupsRecord,
        ir: space,
        selectedObject: findSelectedObjectInIr(space, s.selectedObjectId)
      }));
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '同步数据失败' });
    }
  },

  exitWorkspace: () => {
    set({
      currentSystemView: 'home',
      ir: null,
      selectedObject: null,
      selectedObjectId: null,
      activeDraft: null,
      activeDraftType: null,
      error: null,
      lastActionMessage: null
    });
  },

  updateProject: async (projectId: number, name: string, description: string) => {
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.updateProject(projectId, { name, description });
      await get().loadWorkspaces();
      if (get().ir && get().ir?.projectId === projectId) {
        // If we are currently in this workspace, refresh it to show updated details
        await get().refreshWorkspace();
      }
      set({ isLoading: false, lastActionMessage: '项目基本信息更新成功。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '更新项目失败', isLoading: false });
    }
  },

  deleteProject: async (projectId: number) => {
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.delete(projectId);
      await get().loadWorkspaces();
      if (get().ir && get().ir?.projectId === projectId) {
        // If we are currently in this deleted workspace, exit it
        get().exitWorkspace();
      }
      set({ isLoading: false, lastActionMessage: '项目已成功删除。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '删除项目失败', isLoading: false });
    }
  },

  loadAuditLogs: async (projectId) => {
    try {
      const logs = await workspaceApi.listAuditLogs(projectId);
      const mapped = (logs || []).map((log: any) => ({
        id: (log.id || 1).toString(),
        timestamp: log.createdAt || log.created_at || new Date().toISOString(),
        actionType: log.actionType || log.action_type || '应用变更',
        summary: log.summary || '应用建模变更',
        targetIds: log.targetId || log.target_id ? [log.targetId || log.target_id] : []
      }));
      set({ auditLogs: mapped });
    } catch (err) {
      console.warn('Failed to load audit logs:', err);
    }
  },

  getImpactPreview: async (featureId, nextStatus) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return null;
    try {
      const res = await workspaceApi.impactPreview(projectId, featureId, nextStatus);
      set({ lastImpactPreview: res });
      return res;
    } catch (err) {
      console.warn('Failed to preview impact:', err);
      return null;
    }
  },

  // Onboarding On-demand Creation
  startAIOnboarding: async (prompt, name, description) => {
    set({ isGenerating: true, error: null, lastActionMessage: 'AI 正在生成项目初始草稿，请稍候...' });
    try {
      const draft = await workspaceApi.createProjectCreationDraft({
        user_requirements: prompt,
        project_name: name,
        project_description: description
      });
      set({
        activeDraft: draft,
        activeDraftType: 'project',
        isGenerating: false,
        currentSystemView: 'onboarding'
      });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '生成草稿失败', isGenerating: false });
    }
  },

  confirmAIOnboarding: async () => {
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isLoading: true, error: null });
    try {
      const res = await workspaceApi.confirmProjectCreationDraft(draft.draft_id);
      const space = await workspaceApi.getById(res.project_id);
      set({
        ir: space,
        activeDraft: null,
        activeDraftType: null,
        currentSystemView: 'workspace',
        isLoading: false,
        lastActionMessage: '项目 AI 建模框架已确认，祝您建模愉快！'
      });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '确认草稿失败';
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: '草稿已失效，请重新生成项目草稿', isLoading: false });
      } else {
        set({ error: errMsg, isLoading: false });
      }
    }
  },

  regenerateAIOnboarding: async (feedback) => {
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isGenerating: true, error: null, lastActionMessage: 'AI 正在根据您的意见重新生成项目草稿，请稍候...' });
    try {
      const updated = await workspaceApi.regenerateProjectCreationDraft(draft.draft_id, feedback);
      set({ activeDraft: updated, isGenerating: false, lastActionMessage: '已根据意见重新生成项目草稿。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '重新生成失败';
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: '草稿已失效，请重新配置并生成', isGenerating: false });
      } else {
        set({ error: errMsg, isGenerating: false });
      }
    }
  },

  discardAIOnboarding: async () => {
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    try {
      await workspaceApi.discardProjectCreationDraft(draft.draft_id);
      set({ activeDraft: null, activeDraftType: null, currentSystemView: 'home' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '舍弃草稿失败' });
    }
  },

  createBlankWorkspace: async (name, description, prompt) => {
    set({ isLoading: true, error: null });
    try {
      const res = await workspaceApi.createBlankProject({
        user_requirements: prompt,
        project_name: name,
        project_description: description
      });
      const space = await workspaceApi.getById(res.project_id);
      set({
        ir: space,
        currentSystemView: 'workspace',
        isLoading: false,
        lastActionMessage: '已初始化空白工作区，开始您的敏捷设计吧！'
      });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '创建空白项目失败', isLoading: false });
    }
  },

  // AI Generators per phase
  generateActors: async () => {
    const pId = withWorkspaceId(get());
    set({ isGenerating: true, error: null, lastActionMessage: '🤖 AI 正在根据项目需求精炼并生成核心角色列表，请稍候...' });
    try {
      const draft = await workspaceApi.createActorGenerationDraft(pId);
      set({ activeDraft: draft, activeDraftType: 'actor', isGenerating: false, lastActionMessage: '🤖 AI 推荐的角色列表已生成！已展示在顶部推荐 Banner 中，您可按需调整或一键采纳。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '生成角色失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
    }
  },

  regenerateActors: async (feedback) => {
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isGenerating: true, error: null, lastActionMessage: '🤖 AI 正在根据您的最新意见调整重构角色列表，请稍候...' });
    try {
      let updated;
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        updated = await workspaceApi.regenerateSlotFillingDraft(draftId, feedback);
      } else {
        updated = await workspaceApi.regenerateActorGenerationDraft(draftId, feedback);
      }
      set({ activeDraft: updated, isGenerating: false, lastActionMessage: '已根据意见重新生成角色草稿。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '重新生成角色草稿失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      } else {
        set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmActors: async () => {
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isLoading: true, error: null, lastActionMessage: '💾 正在确认采纳 AI 推荐角色并合入数据库，请稍候...' });
    try {
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        await workspaceApi.confirmSlotFillingDraft(draftId);
      } else {
        await workspaceApi.confirmActorGenerationDraft(draftId);
      }
      await get().refreshWorkspace();
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: '已合并 AI 生成的角色列表。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '确认角色失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: friendlyMsg, lastActionMessage: friendlyMsg, isLoading: false });
      } else {
        set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isLoading: false });
      }
    }
  },

  generateFeatures: async () => {
    const pId = withWorkspaceId(get());
    set({ isGenerating: true, error: null, lastActionMessage: '🤖 AI 正在根据项目原始需求推演并分解核心功能特征树，请稍候...' });
    try {
      const draft = await workspaceApi.createFeatureGenerationDraft(pId);
      set({ activeDraft: draft, activeDraftType: 'feature', isGenerating: false, lastActionMessage: '🤖 AI 推荐的核心功能架构树已生成！已展示在顶部推荐 Banner 中，可调整节点后合并。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '生成功能树失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
    }
  },

  regenerateFeatures: async (feedback) => {
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isGenerating: true, error: null, lastActionMessage: '🤖 AI 正在根据您的反馈意见重新调整分解功能树，请稍候...' });
    try {
      let updated;
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        updated = await workspaceApi.regenerateSlotFillingDraft(draftId, feedback);
      } else {
        updated = await workspaceApi.regenerateFeatureGenerationDraft(draftId, feedback);
      }
      set({ activeDraft: updated, isGenerating: false, lastActionMessage: '已根据意见重新生成功能草稿。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '重新生成功能草稿失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      } else {
        set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmFeatures: async () => {
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isLoading: true, error: null, lastActionMessage: '💾 正在确认采纳功能架构分解并合入正式功能特征树，请稍候...' });
    try {
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        await workspaceApi.confirmSlotFillingDraft(draftId);
      } else {
        await workspaceApi.confirmFeatureGenerationDraft(draftId);
      }
      await get().refreshWorkspace();
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: '已将功能叶子节点合并到功能树。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '确认功能失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: friendlyMsg, lastActionMessage: friendlyMsg, isLoading: false });
      } else {
        set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isLoading: false });
      }
    }
  },

  generateFlowsAndObjects: async () => {
    const pId = withWorkspaceId(get());
    set({ isGenerating: true, error: null, lastActionMessage: '🤖 AI 正在智能推演核心业务流程、泳道步骤及数据实体属性模型，请稍候...' });
    try {
      const draft = await workspaceApi.createFlowGenerationDraft(pId);
      set({ activeDraft: draft, activeDraftType: 'flow', isGenerating: false, lastActionMessage: '🤖 AI 推荐的核心泳道步骤与核心数据对象已生成！已在顶部提供详细列表预览。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '生成流程失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
    }
  },

  regenerateFlowsAndObjects: async (feedback) => {
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isGenerating: true, error: null, lastActionMessage: '🤖 AI 正在根据您的意见重新推演流程与业务对象，请稍候...' });
    try {
      const updated = await workspaceApi.regenerateFlowGenerationDraft(draftId, feedback);
      set({ activeDraft: updated, activeDraftType: 'flow', isGenerating: false, lastActionMessage: '已根据意见重新生成流程与业务对象草稿。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '重新生成流程失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      } else {
        set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmFlowsAndObjects: async () => {
    const draft = get().activeDraft;
    if (!draft) return;
    const draftId = draft.draftId || draft.draft_id;
    if (!draftId) return;
    set({ isLoading: true, error: null, lastActionMessage: '💾 正在确认采纳流程与业务对象草稿，请稍候...' });
    try {
      await workspaceApi.confirmFlowGenerationDraft(draftId);
      await get().refreshWorkspace();
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: '业务流程与业务对象已应用。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '确认流程失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: friendlyMsg, lastActionMessage: friendlyMsg, isLoading: false });
      } else {
        set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isLoading: false });
      }
    }
  },

  generateScenarios: async (featureIds) => {
    const pId = withWorkspaceId(get());
    set({ isGenerating: true, error: null, lastActionMessage: '🤖 AI 正在智能推演具体功能节点在业务场景下的典型成功场景与验收标准 (AC)，此过程调用深层业务逻辑，可能需要一些时间，请稍候...' });
    try {
      if (Array.isArray(featureIds)) {
        if (featureIds.length === 0) {
          const draft = await workspaceApi.createScenarioGenerationDraft(pId);
          set({ activeDraft: draft, activeDraftType: 'scenario', isGenerating: false, lastActionMessage: '🤖 AI 智能场景推演成功！已在上方提供完整场景列表，可查看其详细交互和AC验收条件。' });
        } else if (featureIds.length === 1) {
          const draft = await workspaceApi.createScenarioGenerationDraft(pId, featureIds[0]);
          set({ activeDraft: draft, activeDraftType: 'scenario', isGenerating: false, lastActionMessage: '🤖 AI 智能场景推演成功！已在上方提供完整场景列表，可查看其详细交互和AC验收条件。' });
        } else {
          // Batch concurrent requests
          const drafts = await Promise.all(
            featureIds.map(fId => workspaceApi.createScenarioGenerationDraft(pId, fId))
          );
          const combinedScenarios = drafts.flatMap(d => d.scenarios || []);
          const draftIds = drafts.map(d => d.draftId || d.draft_id);
          const combinedDraft = {
            project_id: pId,
            generation_mode: 'batch',
            draftIds,
            scenarios: combinedScenarios,
            draft_id: draftIds[0], // fallback compatibility
          };
          set({ activeDraft: combinedDraft, activeDraftType: 'scenario', isGenerating: false, lastActionMessage: `🤖 AI 智能场景推演成功！针对选定的 ${featureIds.length} 个功能模块共生成了 ${combinedScenarios.length} 个场景，已在上方提供预览。` });
        }
      } else {
        const draft = await workspaceApi.createScenarioGenerationDraft(pId, featureIds);
        set({ activeDraft: draft, activeDraftType: 'scenario', isGenerating: false, lastActionMessage: '🤖 AI 智能场景推演成功！已在上方提供完整场景列表，可查看其详细交互和AC验收条件。' });
      }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '生成成功场景失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
    }
  },

  regenerateScenarios: async (feedback) => {
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isGenerating: true, error: null, lastActionMessage: '🤖 AI 正在根据您的具体修改反馈，重新演练场景详情，请稍候...' });
    try {
      let updated;
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        updated = await workspaceApi.regenerateSlotFillingDraft(draftId, feedback);
      } else {
        updated = await workspaceApi.regenerateScenarioGenerationDraft(draftId, feedback);
      }
      set({ activeDraft: updated, isGenerating: false, lastActionMessage: '已根据意见重新生成成功场景草稿。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '重新生成场景失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      } else {
        set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmScenarios: async (generateAc) => {
    const draft = get().activeDraft;
    if (!draft) return;
    set({ isLoading: true, error: null, lastActionMessage: '💾 正在确认采纳成功场景设计并正式落库，请稍候...' });
    try {
      if (draft.draftIds && draft.draftIds.length > 0) {
        await Promise.all(
          draft.draftIds.map((id: string) =>
            workspaceApi.confirmScenarioGenerationDraft(id, { generate_acceptance_criteria: generateAc })
          )
        );
      } else {
        const draftId = draft.draftId || draft.draft_id;
        if (!draftId) return;
        if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
          await workspaceApi.confirmSlotFillingDraft(draftId);
        } else {
          await workspaceApi.confirmScenarioGenerationDraft(draftId, { generate_acceptance_criteria: generateAc });
        }
      }
      await get().refreshWorkspace();
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: '成功场景与关联验收标准已应用。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '确认场景失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: friendlyMsg, lastActionMessage: friendlyMsg, isLoading: false });
      } else {
        set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isLoading: false });
      }
    }
  },

  generateAcceptanceCriteria: async (scenarioIds) => {
    const pId = withWorkspaceId(get());
    set({ isGenerating: true, error: null, lastActionMessage: '🤖 AI 正在智能推演该场景的具体验收标准 (Acceptance Criteria - AC) 条目，请稍候...' });
    try {
      const draft = await workspaceApi.createAcceptanceCriteriaGenerationDraft(pId, scenarioIds);
      set({ activeDraft: draft, activeDraftType: 'ac', isGenerating: false, lastActionMessage: '🤖 AI 推荐的验收标准 (AC) 已精细推演成功！已在上方提供完整验收检查清单列表。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '生成验收标准失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
    }
  },

  regenerateAcceptanceCriteria: async (feedback) => {
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isGenerating: true, error: null, lastActionMessage: '🤖 AI 正在根据调整意见重新演练优化验收标准 (AC) 检查项，请稍候...' });
    try {
      let updated;
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        updated = await workspaceApi.regenerateSlotFillingDraft(draftId, feedback);
      } else {
        updated = await workspaceApi.regenerateAcceptanceCriteriaGenerationDraft(draftId, feedback);
      }
      set({ activeDraft: updated, isGenerating: false, lastActionMessage: '已根据意见重新生成验收标准草稿。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '重新生成验收标准失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      } else {
        set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmAcceptanceCriteria: async () => {
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isLoading: true, error: null, lastActionMessage: '💾 正在确认采纳验收条件 (AC) 并正式关联落库，请稍候...' });
    try {
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        await workspaceApi.confirmSlotFillingDraft(draftId);
      } else {
        await workspaceApi.confirmAcceptanceCriteriaGenerationDraft(draftId);
      }
      await get().refreshWorkspace();
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: '成功标准已精细化补充并落库。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '确认失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: friendlyMsg, lastActionMessage: friendlyMsg, isLoading: false });
      } else {
        set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isLoading: false });
      }
    }
  },

  generateScope: async () => {
    const pId = withWorkspaceId(get());
    set({ isGenerating: true, error: null, lastActionMessage: '🤖 AI 正在对项目中的所有功能节点进行深层的 Kano 模型范围归类与推荐分析，请稍候...' });
    try {
      const draft = await workspaceApi.createScopeGenerationDraft(pId);
      set({ activeDraft: draft, activeDraftType: 'scope', isGenerating: false, lastActionMessage: '🤖 AI Kano 范围与发布优先级分析推演成功！已在上方提供完整功能卡片范围归档预览。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '生成范围分析失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
    }
  },

  regenerateScope: async (feedback) => {
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isGenerating: true, error: null, lastActionMessage: '🤖 AI 正在根据您的最新指导意见，重新推算评估功能卡片优先级与 Kano 归属，请稍候...' });
    try {
      const updated = await workspaceApi.regenerateScopeGenerationDraft(draft.draft_id, feedback);
      set({ activeDraft: updated, isGenerating: false, lastActionMessage: '已根据意见重新生成范围分析草稿。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '重新生成范围分析失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      } else {
        set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmScope: async () => {
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isLoading: true, error: null, lastActionMessage: '💾 正在确认采纳发布计划安排并落库保存，请稍候...' });
    try {
      await workspaceApi.confirmScopeGenerationDraft(draft.draft_id);
      await get().refreshWorkspace();
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: 'Kano 功能发布计划与正反方观点已确认。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '确认失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: friendlyMsg, lastActionMessage: friendlyMsg, isLoading: false });
      } else {
        set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isLoading: false });
      }
    }
  },

  discardDraft: async () => {
    const draft = get().activeDraft;
    if (!draft) return;
    try {
      if (draft.draftIds && draft.draftIds.length > 0) {
        await Promise.all(
          draft.draftIds.map((id: string) => workspaceApi.discardDraft(id, get().activeDraftType))
        );
      } else {
        const draftId = draft.draftId || draft.draft_id;
        if (!draftId) return;
        if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
          await workspaceApi.discardSlotFillingDraft(draftId);
        } else {
          await workspaceApi.discardDraft(draftId, get().activeDraftType);
        }
      }
      set({ activeDraft: null, activeDraftType: null, lastActionMessage: '已舍弃未保存的 AI 推荐草案。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '取消草稿失败' });
    }
  },

  // -------------------------------------------------------------
  // Manual CRUD Actions
  // -------------------------------------------------------------

  // Actors
  addActor: async (name, description) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.createActor(pId, { name, description });
      await get().refreshWorkspace();
      set({ lastActionMessage: `已添加参与者角色：${name}` });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '添加参与者角色失败' });
    }
  },

  updateActor: async (actorId, updates) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.updateActor(pId, actorId, {
        name: updates.actorName,
        description: updates.actorDescription
      });
      await get().refreshWorkspace();
      set({ lastActionMessage: '参与者角色属性更新成功。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '更新参与者角色属性失败' });
    }
  },

  deleteActor: async (actorId) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.deleteActor(pId, actorId);
      await get().refreshWorkspace();
      set((s) => {
        const isSelected = s.selectedObjectId === actorId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessage: '参与者角色已被成功移除，对应功能绑定已解除。'
        };
      });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '删除参与者角色失败' });
    }
  },

  // Features Tree CRUD
  addFeature: async (name, description, parentId) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.createFeature(pId, {
        name,
        description,
        parent_id: parentId
      });
      await get().refreshWorkspace();
      set({ lastActionMessage: `已创建功能节点：${name}` });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '创建功能节点失败' });
    }
  },

  updateFeature: async (featureId, updates) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.updateFeature(pId, featureId, {
        name: updates.featureName,
        description: updates.featureDescription,
        actor_ids: updates.actorIds
      });
      await get().refreshWorkspace();
      set({ lastActionMessage: '功能节点属性更新成功。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '更新功能节点属性失败' });
    }
  },

  deleteFeature: async (featureId) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.deleteFeature(pId, featureId);
      await get().refreshWorkspace();
      set((s) => {
        const isSelected = s.selectedObjectId === featureId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessage: '选定功能节点及其子分支已全部移除。'
        };
      });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '删除功能节点失败' });
    }
  },

  // Scenarios CRUD
  addScenario: async (featureId, actorId, name, content) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.createScenario(pId, {
        feature_id: featureId,
        actor_id: actorId,
        name,
        content
      });
      await get().refreshWorkspace();
      set({ lastActionMessage: `已为功能添加新场景：${name}` });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '添加场景失败' });
    }
  },

  updateScenario: async (featureId, scenarioId, updates) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.updateScenario(pId, scenarioId, {
        name: updates.scenarioName,
        content: updates.scenarioContent
      });
      await get().refreshWorkspace();
      set({ lastActionMessage: '成功场景已更新。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '更新场景失败' });
    }
  },

  deleteScenario: async (featureId, scenarioId) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.deleteScenario(pId, scenarioId);
      await get().refreshWorkspace();
      set((s) => {
        const isSelected = s.selectedObjectId === scenarioId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessage: '场景已删除。'
        };
      });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '删除场景失败' });
    }
  },

  // Acceptance Criteria CRUD
  addAcceptanceCriterion: async (featureId, scenarioId, content) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.createAcceptanceCriterion(pId, scenarioId, { content });
      await get().refreshWorkspace();
      set({ lastActionMessage: '成功验收标准添加成功！' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '添加验收标准失败' });
    }
  },

  updateAcceptanceCriterion: async (featureId, scenarioId, criterionId, content) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.updateAcceptanceCriterion(pId, scenarioId, criterionId, { content });
      await get().refreshWorkspace();
      set({ lastActionMessage: '验收标准已修改。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '更新验收标准失败' });
    }
  },

  deleteAcceptanceCriterion: async (featureId, scenarioId, criterionId) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.deleteAcceptanceCriterion(pId, scenarioId, criterionId);
      await get().refreshWorkspace();
      set((s) => {
        const isSelected = s.selectedObjectId === criterionId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessage: '验收标准已删除。'
        };
      });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '删除验收标准失败' });
    }
  },

  // Business Objects CRUD
  addBusinessObject: async (name, description) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.createBusinessObject(pId, { name, description });
      await get().refreshWorkspace();
      set({ lastActionMessage: `已创建业务对象：${name}` });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '创建业务对象失败' });
    }
  },

  updateBusinessObject: async (id, name, description) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.updateBusinessObject(pId, id, { name, description });
      await get().refreshWorkspace();
      set({ lastActionMessage: '业务对象定义已更新。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '更新业务对象定义失败' });
    }
  },

  deleteBusinessObject: async (id) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.deleteBusinessObject(pId, id);
      await get().refreshWorkspace();
      set((s) => {
        const isSelected = s.selectedObjectId === id;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessage: '业务数据对象已被完全抹除。'
        };
      });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '删除业务数据对象失败' });
    }
  },

  addBusinessObjectAttribute: async (boId, name, description, type, example) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.createBusinessObjectAttribute(pId, boId, {
        name,
        description,
        data_type: type,
        example
      });
      await get().refreshWorkspace();
      set({ lastActionMessage: `已为对象添加字段属性：${name}` });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '添加字段属性失败' });
    }
  },

  updateBusinessObjectAttribute: async (boId, attrId, updates) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.updateBusinessObjectAttribute(pId, boId, attrId, {
        name: updates.businessObjectAttributeName,
        description: updates.businessObjectAttributeDescription,
        data_type: updates.businessObjectAttributeType,
        example: updates.businessObjectAttributeExample
      });
      await get().refreshWorkspace();
      set({ lastActionMessage: '字段属性详情修改完毕。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '更新字段属性详情失败' });
    }
  },

  deleteBusinessObjectAttribute: async (boId, attrId) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.deleteBusinessObjectAttribute(pId, boId, attrId);
      await get().refreshWorkspace();
      set((s) => {
        const isSelected = s.selectedObjectId === attrId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessage: '已移除字段属性。'
        };
      });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '移除字段属性失败' });
    }
  },

  // Flows CRUD
  addFlow: async (name, description, featureIds) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.createFlow(pId, {
        name,
        description,
        feature_ids: featureIds
      });
      await get().refreshWorkspace();
      set({ lastActionMessage: `已组建业务流程：${name}` });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '组建业务流程失败' });
    }
  },

  updateFlow: async (flowId, updates) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.updateFlow(pId, flowId, {
        name: updates.flowName,
        description: updates.flowDescription,
        feature_ids: updates.featureIds
      });
      await get().refreshWorkspace();
      set({ lastActionMessage: '流程信息已更新。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '更新流程信息失败' });
    }
  },

  deleteFlow: async (flowId) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.deleteFlow(pId, flowId);
      await get().refreshWorkspace();
      set((s) => {
        const isSelected = s.selectedObjectId === flowId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessage: '流程已被连根剔除。'
        };
      });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '删除流程失败' });
    }
  },

  addFlowStep: async (flowId, step) => {
    const pId = withWorkspaceId(get());
    try {
      // 1. Create the new flow step
      const newStep = await workspaceApi.createFlowStep(pId, flowId, {
        name: step.stepName,
        description: step.stepDescription,
        step_type: step.stepType,
        actor_ids: step.actorIds,
        input_business_object_ids: step.inputBusinessObjectIds,
        output_business_object_ids: step.outputBusinessObjectIds,
        next_step_ids: []
      });

      // 2. Sequential binding for nextStepIds from previous step
      const flow = get().ir?.flows.find(f => f.flowId === flowId);
      if (flow && flow.flowSteps.length > 0) {
        const prevStep = flow.flowSteps[flow.flowSteps.length - 1];
        const newStepId = newStep.step_id || newStep.stepId;
        await workspaceApi.updateFlowStep(pId, flowId, prevStep.stepId, {
          next_step_ids: [newStepId]
        });
      }

      await get().refreshWorkspace();
      set({ lastActionMessage: `流程步骤 "${step.stepName}" 已载入。` });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '载入流程步骤失败' });
    }
  },

  updateFlowStep: async (flowId, stepId, updates) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.updateFlowStep(pId, flowId, stepId, {
        name: updates.stepName,
        description: updates.stepDescription,
        step_type: updates.stepType,
        actor_ids: updates.actorIds,
        input_business_object_ids: updates.inputBusinessObjectIds,
        output_business_object_ids: updates.outputBusinessObjectIds,
        next_step_ids: updates.nextStepIds
      });
      await get().refreshWorkspace();
      set({ lastActionMessage: '流程步骤细项修改成功。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '修改流程步骤细项失败' });
    }
  },

  deleteFlowStep: async (flowId, stepId) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.deleteFlowStep(pId, flowId, stepId);
      await get().refreshWorkspace();
      set((s) => {
        const isSelected = s.selectedObjectId === stepId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessage: '选定步骤已移除，拓扑链路已完成自动流转适配。'
        };
      });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '移除步骤失败' });
    }
  },

  // Scope (Kano) CRUD
  updateScope: async (featureId, updates) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.updateScope(pId, featureId, {
        status: updates.scopeStatus,
        reason: updates.reason,
        positive_summary: updates.positiveSummary,
        negative_summary: updates.negativeSummary
      });
      await get().refreshWorkspace();
      set({ lastActionMessage: '功能优先级发布范围及理由更新成功。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '更新功能优先级发布范围及理由失败' });
    }
  },

  // PerceptionSlot
  clearPerceptionSlot: async () => {
    const space = get().ir;
    if (!space) return;
    const updated = {
      ...space,
      perceptionSlot: null
    };
    set({ ir: updated, lastActionMessage: '已忽略/隐藏当前 AI 感知引导。' });
  },

  openSlot: (slotId) => {
    const numId = parseInt(slotId, 10);
    const space = get().ir;
    if (space?.perceptionSlot?.perceptionSlotId === numId) {
      set({ selectedSlotId: numId, selectedObject: space.perceptionSlot, selectedObjectId: numId });
    }
  },
  expandSlot: async (slotId) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    const numId = parseInt(slotId, 10);
    const slot = get().ir?.perceptionSlot;
    if (!slot || slot.perceptionSlotId !== numId) return;

    set({ isGenerating: true, error: null, lastActionMessage: 'AI 正在展开感知槽并生成补全草稿，请稍候...' });
    try {
      let fillerKind: 'actor' | 'feature' | 'flow' | 'scenario' | 'ac' | null = null;
      const kindText = slot.perceptionKind;
      if (kindText === '角色结点') fillerKind = 'actor';
      else if (kindText === '功能模块结点' || kindText === '功能叶子结点') fillerKind = 'feature';
      else if (kindText === '流程主结点') fillerKind = 'flow';
      else if (kindText === '场景结点') fillerKind = 'scenario';
      else if (kindText === '成功标准结点') fillerKind = 'ac';

      if (!fillerKind) {
        throw new Error('未知的槽感知类型，无法展开。');
      }

      const draft = await workspaceApi.createSlotFillingDraft(projectId, numId, fillerKind);
      set({
        activeDraft: draft,
        activeDraftType: fillerKind,
        isGenerating: false,
        lastActionMessage: 'AI 感知槽开始填充，生成草稿预览。'
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : '槽填充生成失败',
        isGenerating: false
      });
    }
  },
  acceptChoice: async (choiceId) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    const choiceIdNum = parseInt(choiceId, 10);
    if (isNaN(choiceIdNum)) return;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.acceptChoice(projectId, choiceIdNum);
      await get().refreshWorkspace();
      set({ selectedObject: null, selectedObjectId: null, isLoading: false, lastActionMessage: '已成功采纳并应用该设计决策提案。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '采纳决策失败', isLoading: false });
    }
  },
  rejectChoice: async (choiceId) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    const choiceIdNum = parseInt(choiceId, 10);
    if (isNaN(choiceIdNum)) return;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.rejectChoice(projectId, choiceIdNum);
      await get().refreshWorkspace();
      set({ selectedObject: null, selectedObjectId: null, isLoading: false, lastActionMessage: '已拒绝该设计决策提案。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '拒绝决策失败', isLoading: false });
    }
  },
  createSlotFromIssue: async (issueId) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return null;
    const issue = get().ir?.issuesCompatible?.find(i => i.id === issueId);
    if (!issue) return null;

    set({ isLoading: true, error: null });
    try {
      const res = await workspaceApi.resolveIssue(projectId, {
        issue_code: issue.backendIssueCode || issue.category || '',
        target: issue.backendTarget || null,
        metadata: issue.backendMetadata || {}
      });

      await get().refreshWorkspace();

      if (res.draftId || res.draft_id) {
        set({
          activeDraft: res.draft,
          activeDraftType: mapResolutionDraftType(res.action?.draftType || res.action?.draft_type),
          lastActionMessage: `已触发处理：${res.title}`
        });
      }

      set({ isLoading: false });
      
      if (res.action?.payload?.perception_job_id) {
        return res.action.payload.perception_job_id.toString();
      }
      const slot = get().ir?.perceptionSlot;
      return slot ? slot.perceptionSlotId.toString() : null;
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '处理 Issue 失败', isLoading: false });
      return null;
    }
  },
  setNodeStatus: async () => {},
  setScopeStatus: async (nodeId, scopeStatus) => {
    const featId = parseInt(nodeId, 10);
    if (!isNaN(featId)) {
      await get().updateScope(featId, { scopeStatus });
    }
  },
  runDiagnosis: async () => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    
    let stage = 'what';
    const activePage = get().activePage;
    if (activePage === '/flow') stage = 'how';
    else if (activePage === '/scope') stage = 'scope';
    else if (activePage === '/preview') stage = 'preview';

    set({ isDiagnosing: true, error: null });
    try {
      let res = await workspaceApi.getNextSuggestion(projectId, stage);
      set((s) => ({
        nextSuggestions: {
          ...s.nextSuggestions,
          [stage]: res.suggestion
        },
        lastActionMessage: `AI 智能分析中：“${res.suggestion?.title || '正在分析中'}”...`
      }));

      // If the suggestion is in 'running' state, poll until it's finished or failed
      if (res.suggestion && res.suggestion.status === 'running') {
        const maxAttempts = 15; // Max 30 seconds
        let attempts = 0;
        
        while (attempts < maxAttempts) {
          // Wait 2 seconds before polling again
          await new Promise((resolve) => setTimeout(resolve, 2000));
          
          // Poll next suggestion
          res = await workspaceApi.getNextSuggestion(projectId, stage);
          
          set((s) => ({
            nextSuggestions: {
              ...s.nextSuggestions,
              [stage]: res.suggestion
            }
          }));

          // Break loop if suggestion is ready, failed, or null
          if (!res.suggestion || res.suggestion.status !== 'running') {
            break;
          }
          
          attempts++;
        }
      }

      set({
        isDiagnosing: false,
        lastActionMessage: res.suggestion 
          ? `诊断完成！最新建议：“${res.suggestion.title}”。` 
          : '诊断完成！当前模块设计非常规范，暂无建议。'
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : '诊断失败',
        isDiagnosing: false
      });
    }
  },
  executeNextSuggestion: async (stage: string) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    const suggestion = get().nextSuggestions[stage];
    if (!suggestion) return;

    set({ isLoading: true, error: null });
    try {
      const res = await workspaceApi.startNextSuggestion(projectId, {
        stage,
        suggestion_code: suggestion.code,
        target: suggestion.target || null,
        query: null
      });

      await get().refreshWorkspace();

      const action = res.action;
      if (action) {
        if (action.kind === 'open_panel') {
          if (action.panel === 'perception_slot') {
            const perceptionJobId = action.payload?.perception_job_id;
            if (perceptionJobId) {
              await get().expandSlot(perceptionJobId.toString());
            }
          }
        }
      }
      set({ isLoading: false, lastActionMessage: `已执行“${suggestion.title}”建议。` });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '执行建议失败', isLoading: false });
    }
  },
  rewrite: async (scope, instruction) => {
    set({ isLoading: true, error: null });
    try {
      const projectId = withWorkspaceId(get());
      
      const res = await workspaceApi.refineUserRequirements(projectId, instruction);
      
      // Update local ir user requirements
      const space = get().ir;
      if (space) {
        set({
          ir: {
            ...space,
            userRequirements: res.userRequirements,
          }
        });
      }
      
      set({
        isLoading: false,
        lastActionMessage: '📝 AI 智能自动建模成功：已根据您的建模指令精炼并更新了项目原始用户需求。您可在各 Tab 重新发起 AI 推演或补全草稿。'
      });
    } catch (err) {
      set({
        isLoading: false,
        lastActionMessage: `⚠️ 建模失败: ${err instanceof Error ? err.message : '未知异常'}`
      });
    }
  },
  explainImpact: async (scope, patch, choiceId) => {
    set({ isLoading: true, error: null });
    try {
      const projectId = withWorkspaceId(get());

      let targetFeatureId: number | null = null;
      let featureName = '';

      // 1. Try to get feature ID from scope
      if (scope?.kind === 'node' && scope.nodeId) {
        const numId = parseInt(scope.nodeId, 10);
        if (!isNaN(numId)) {
          const feat = get().ir?.features.find(f => f.featureId === numId);
          if (feat) {
            targetFeatureId = numId;
            featureName = feat.featureName;
          }
        }
      }

      // 2. If not found in scope, try current selectedObject if it's a feature
      if (!targetFeatureId) {
        const selObj = get().selectedObject;
        if (selObj && (selObj as any).featureId) {
          targetFeatureId = (selObj as any).featureId;
          featureName = (selObj as any).featureName || '';
        }
      }

      if (!targetFeatureId) {
        set({
          isLoading: false,
          lastActionMessage: '⚠️ 链路联动分析目前支持针对“功能模块”进行分析，请在左侧或 What 页选中一个功能模块节点。'
        });
        return;
      }

      const res = await workspaceApi.impactPreview(projectId, targetFeatureId, '暂缓');
      
      const scenarioCount = res.affectedScenarios?.length || 0;
      const flowCount = res.affectedFlows?.length || 0;
      const boCount = res.affectedBusinessObjects?.length || 0;

      set({
        isLoading: false,
        lastActionMessage: `📊 【${featureName}】变更影响评估：关联受影响场景 ${scenarioCount} 个，业务流 ${flowCount} 个，数据实体 ${boCount} 个。详细分析可在 Scope 页面进行决策评估。`
      });
    } catch (err) {
      set({
        isLoading: false,
        lastActionMessage: `⚠️ 评估失败: ${err instanceof Error ? err.message : '未知异常'}`
      });
    }
  },
  updateNodeAttributes: async (nodeId, updates) => {
    const numId = parseInt(nodeId, 10);
    if (isNaN(numId)) return;
    const space = get().ir;
    if (!space) return;
    // Map updates
    const actor = space.actors.find(a => a.actorId === numId);
    if (actor) {
      await get().updateActor(numId, {
        actorName: updates.title || actor.actorName,
        actorDescription: updates.description || actor.actorDescription
      });
      return;
    }
    const feat = space.features.find(f => f.featureId === numId);
    if (feat) {
      await get().updateFeature(numId, {
        featureName: updates.title || feat.featureName,
        featureDescription: updates.description || feat.featureDescription
      });
      return;
    }
  },
  createIssue: async () => {},
  updateIssueAttributes: async () => {},
  updateChoiceAttributes: async () => {},
  addChoiceToGroup: async () => {},
  };
});

// Backward compatibility selectors for components
const emptyArray: any[] = [];

export const selectGoals = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray as GoalNode[];
  return (state.ir as any).goalsCompatible || emptyArray;
};

export const selectCapabilities = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray as CapabilityNode[];
  return (state.ir as any).capabilitiesCompatible || emptyArray;
};

export const selectTasks = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray as TaskNode[];
  return (state.ir as any).tasksCompatible || emptyArray;
};

export const selectActors = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray as ActorNode[];
  return (state.ir as any).actorsCompatible || emptyArray;
};

export const selectFlowSteps = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray as FlowStepNode[];
  return (state.ir as any).flowStepsCompatible || emptyArray;
};

export const selectIssues = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray as Issue[];
  return (state.ir as any).issuesCompatible || emptyArray;
};

export const selectChoices = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray as Choice[];
  return (state.ir as any).choicesCompatible || emptyArray;
};

export const selectScopeItems = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray;
  return (state.ir as any).scopeItemsCompatible || emptyArray;
};

export const selectLinks = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray;
  return (state.ir as any).linksCompatible || emptyArray;
};

export const selectSelectedObject = (state: WorkspaceState) => {
  if (state.selectedObject) return state.selectedObject;
  return findSelectedObjectInIr(state.ir, state.selectedObjectId);
};

export const selectCurrentPage = (state: WorkspaceState) => state.activePage;

export const selectPageHealth = (state: WorkspaceState, path: string) => {
  return buildPageHealth(state.ir, path);
};
