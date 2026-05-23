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
  Proposal,
  GoalNode,
  CapabilityNode,
  TaskNode,
  NodeStatus,
  GraphPatch,
  FlowStepType,
  BaseNode,
} from '@/core/schema';
import { workspaceApi } from '@/lib/api';
import { buildPageHealth } from '@/core/selectors';

export type WorkspacePage = '/' | '/what' | '/flow' | '/scope' | '/preview' | '/overview';

export interface WorkspaceListItem {
  id: string;
  name: string;
  idea: string;
  updatedAt: string;
  status: string;
  issueCount: number;
  nodeCount: number;
}

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
export const normalizeRequirementSpace = (space: RequirementSpace | null): RequirementSpace | null => {
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
  const issuesList = detectIssues({
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
    choiceGroups: space.choiceGroups || {},
    proposals: space.proposals || {},
    
    // Stable Selector Cache Fields
    actorsCompatible,
    flowStepsCompatible,
    issuesCompatible: issuesList,
    linksCompatible: linksList,
    goalsCompatible,
    capabilitiesCompatible,
    tasksCompatible,
    scopeItemsCompatible
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

  // Onboarding On-demand Creation
  startAIOnboarding: (prompt: string, name?: string, description?: string) => Promise<void>;
  confirmAIOnboarding: () => Promise<void>;
  regenerateAIOnboarding: () => Promise<void>;
  discardAIOnboarding: () => Promise<void>;
  createBlankWorkspace: (name: string, description: string, prompt: string) => Promise<void>;

  // AI Generators per phase
  generateActors: () => Promise<void>;
  confirmActors: () => Promise<void>;
  
  generateFeatures: () => Promise<void>;
  confirmFeatures: () => Promise<void>;
  
  generateFlowsAndObjects: () => Promise<void>;
  confirmFlowsAndObjects: () => Promise<void>;
  
  generateScenarios: (featureId?: number) => Promise<void>;
  confirmScenarios: (generateAc: boolean) => Promise<void>;
  
  generateAcceptanceCriteria: (scenarioIds?: number[]) => Promise<void>;
  confirmAcceptanceCriteria: () => Promise<void>;
  
  generateScope: () => Promise<void>;
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

  // Legacy Dummy Actions
  applyPatch: (patch: GraphPatch) => Promise<void>;
  openSlot: (slotId: string) => void;
  expandSlot: (slotId: string) => Promise<void>;
  acceptChoice: (choiceId: string) => Promise<void>;
  rejectChoice: (choiceId: string) => Promise<void>;
  createSlotFromIssue: (issueId: string) => Promise<string | null>;
  setNodeStatus: (nodeId: string, status: NodeStatus) => Promise<void>;
  setScopeStatus: (nodeId: string, scopeStatus: ScopeStatus) => Promise<void>;
  runDiagnosis: (scope: any) => Promise<void>;
  rewrite: (scope: any, instruction: string) => Promise<void>;
  explainImpact: (scope: any, patch?: GraphPatch, choiceId?: string) => Promise<void>;
  updateNodeAttributes: (nodeId: string, updates: Partial<BaseNode> & Record<string, any>) => Promise<void>;
  createIssue: (payload: any) => Promise<void>;
  updateIssueAttributes: (issueId: string, updates: any) => Promise<void>;
  updateChoiceAttributes: (choiceId: string, updates: any) => Promise<void>;
  addChoiceToGroup: (choiceGroupId: string, payload: any) => Promise<void>;
  acceptProposal: (proposalId: string) => Promise<void>;
  rejectProposal: (proposalId: string) => Promise<void>;
  convertProposalToChoice: (proposalId: string) => Promise<void>;
}

const findSelectedObjectInIr = (ir: RequirementSpace | null, selectedId: string | number | null): any => {
  if (!ir || !selectedId) return null;
  const numId = typeof selectedId === 'string' ? parseInt(selectedId, 10) : selectedId;

  // Search Slots
  if (ir.slots && ir.slots[selectedId.toString()]) {
    return ir.slots[selectedId.toString()];
  }

  // Search Actor
  const actor = ir.actors.find(a => a.actorId === numId);
  if (actor) return actor;

  // Search Features
  const feature = ir.features.find(f => f.featureId === numId);
  if (feature) return feature;

  // Search Scenario/AC inside features
  for (const feat of ir.features) {
    const scenario = feat.scenarios.find(s => s.scenarioId === numId);
    if (scenario) return scenario;
    for (const s of feat.scenarios) {
      const ac = s.acceptanceCriteria.find(a => a.criterionId === numId);
      if (ac) return ac;
    }
  }

  // Search Business Objects
  const bo = ir.businessObjects.find(b => b.businessObjectId === numId);
  if (bo) return bo;
  for (const b of ir.businessObjects) {
    const attr = b.businessObjectAttributes.find(a => a.businessObjectAttributeId === numId);
    if (attr) return attr;
  }

  // Search Flows & steps
  const flow = ir.flows.find(f => f.flowId === numId);
  if (flow) return flow;
  for (const f of ir.flows) {
    const step = f.flowSteps.find(s => s.stepId === numId);
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
          next.ir = normalizeRequirementSpace(next.ir);
        }
        return next;
      }, replace);
    } else {
      if (update && 'ir' in update && update.ir !== undefined) {
        update.ir = normalizeRequirementSpace(update.ir);
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
      set({
        currentSystemView: 'workspace',
        initialPrompt: space.userRequirements,
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
      set((s) => ({
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

  // Onboarding On-demand Creation
  startAIOnboarding: async (prompt, name, description) => {
    set({ isGenerating: true, error: null });
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
      set({ error: err instanceof Error ? err.message : '确认草稿失败', isLoading: false });
    }
  },

  regenerateAIOnboarding: async () => {
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isGenerating: true, error: null });
    try {
      const updated = await workspaceApi.regenerateProjectCreationDraft(draft.draft_id);
      set({ activeDraft: updated, isGenerating: false, lastActionMessage: '已根据意见重新生成项目草稿。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '重新生成失败', isGenerating: false });
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
    set({ isGenerating: true, error: null });
    try {
      const draft = await workspaceApi.createActorGenerationDraft(pId);
      set({ activeDraft: draft, activeDraftType: 'actor', isGenerating: false });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '生成角色失败', isGenerating: false });
    }
  },

  confirmActors: async () => {
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.confirmActorGenerationDraft(draft.draft_id);
      await get().refreshWorkspace();
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: '已合并 AI 生成的角色列表。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '确认角色失败', isLoading: false });
    }
  },

  generateFeatures: async () => {
    const pId = withWorkspaceId(get());
    set({ isGenerating: true, error: null });
    try {
      const draft = await workspaceApi.createFeatureGenerationDraft(pId);
      set({ activeDraft: draft, activeDraftType: 'feature', isGenerating: false });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '生成功能树失败', isGenerating: false });
    }
  },

  confirmFeatures: async () => {
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.confirmFeatureGenerationDraft(draft.draft_id);
      await get().refreshWorkspace();
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: '已将功能叶子节点合并到功能树。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '确认功能失败', isLoading: false });
    }
  },

  generateFlowsAndObjects: async () => {
    const pId = withWorkspaceId(get());
    set({ isGenerating: true, error: null });
    try {
      const draft = await workspaceApi.createFlowGenerationDraft(pId);
      set({ activeDraft: draft, activeDraftType: 'flow', isGenerating: false });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '生成流程失败', isGenerating: false });
    }
  },

  confirmFlowsAndObjects: async () => {
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.confirmFlowGenerationDraft(draft.draft_id);
      await get().refreshWorkspace();
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: '业务对象与泳道步骤合并落库成功。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '确认失败', isLoading: false });
    }
  },

  generateScenarios: async (featureId) => {
    const pId = withWorkspaceId(get());
    set({ isGenerating: true, error: null });
    try {
      const draft = await workspaceApi.createScenarioGenerationDraft(pId, featureId);
      set({ activeDraft: draft, activeDraftType: 'scenario', isGenerating: false });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '生成成功场景失败', isGenerating: false });
    }
  },

  confirmScenarios: async (generateAc) => {
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.confirmScenarioGenerationDraft(draft.draft_id, { generate_acceptance_criteria: generateAc });
      await get().refreshWorkspace();
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: '成功场景与关联验收标准已应用。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '确认场景失败', isLoading: false });
    }
  },

  generateAcceptanceCriteria: async (scenarioIds) => {
    const pId = withWorkspaceId(get());
    set({ isGenerating: true, error: null });
    try {
      const draft = await workspaceApi.createAcceptanceCriteriaGenerationDraft(pId, scenarioIds);
      set({ activeDraft: draft, activeDraftType: 'ac', isGenerating: false });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '生成验收标准失败', isGenerating: false });
    }
  },

  confirmAcceptanceCriteria: async () => {
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.confirmAcceptanceCriteriaGenerationDraft(draft.draft_id);
      await get().refreshWorkspace();
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: '成功标准已精细化补充并落库。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '确认失败', isLoading: false });
    }
  },

  generateScope: async () => {
    const pId = withWorkspaceId(get());
    set({ isGenerating: true, error: null });
    try {
      const draft = await workspaceApi.createScopeGenerationDraft(pId);
      set({ activeDraft: draft, activeDraftType: 'scope', isGenerating: false });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '生成范围分析失败', isGenerating: false });
    }
  },

  confirmScope: async () => {
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.confirmScopeGenerationDraft(draft.draft_id);
      await get().refreshWorkspace();
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: 'Kano 功能发布计划与正反方观点已确认。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '确认失败', isLoading: false });
    }
  },

  discardDraft: async () => {
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    try {
      await workspaceApi.discardDraft(draft.draft_id);
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
    const space = get().ir;
    if (!space) return;
    const newActor: ActorNode = {
      kind: 'actor',
      actorId: makeIntId(),
      actorName: name,
      actorDescription: description
    };
    const updated = {
      ...space,
      actors: [...space.actors, newActor]
    };
    set({ ir: updated, lastActionMessage: `已添加参与者角色：${name}` });
    await workspaceApi.save(updated);
  },

  updateActor: async (actorId, updates) => {
    const space = get().ir;
    if (!space) return;
    const updated = {
      ...space,
      actors: space.actors.map(a => a.actorId === actorId ? { ...a, ...updates } : a)
    };
    set((s) => ({
      ir: updated,
      selectedObject: findSelectedObjectInIr(updated, s.selectedObjectId),
      lastActionMessage: '参与者角色属性更新成功。'
    }));
    await workspaceApi.save(updated);
  },

  deleteActor: async (actorId) => {
    const space = get().ir;
    if (!space) return;
    // Filter features unlinking actor
    const updatedFeatures = space.features.map(f => ({
      ...f,
      actorIds: f.actorIds.filter(id => id !== actorId)
    }));
    const updated = {
      ...space,
      actors: space.actors.filter(a => a.actorId !== actorId),
      features: updatedFeatures
    };
    set({
      ir: updated,
      selectedObjectId: null,
      selectedObject: null,
      lastActionMessage: '参与者角色已被成功移除，对应功能绑定已解除。'
    });
    await workspaceApi.save(updated);
  },

  // Features Tree CRUD
  addFeature: async (name, description, parentId) => {
    const space = get().ir;
    if (!space) return;
    const featId = makeIntId();
    const newFeature: FeatureNode = {
      kind: 'feature',
      featureId: featId,
      featureName: name,
      featureDescription: description,
      actorIds: [],
      parentId,
      childrenIds: [],
      scenarios: [],
      scope: {
        kind: 'scope',
        scopeId: makeIntId(),
        scopeStatus: '本期',
        reason: '手动创建节点，默认列入本期。',
        positiveSummary: '提供基础的业务支持。',
        negativeSummary: null,
        positivePictureBase64: null,
        negativePictureBase64: null
      }
    };

    let updatedFeatures = [...space.features, newFeature];
    if (parentId !== null) {
      updatedFeatures = updatedFeatures.map(f => f.featureId === parentId ? {
        ...f,
        childrenIds: [...f.childrenIds, featId]
      } : f);
    }

    const updated = { ...space, features: updatedFeatures };
    set({ ir: updated, lastActionMessage: `已创建功能节点：${name}` });
    await workspaceApi.save(updated);
  },

  updateFeature: async (featureId, updates) => {
    const space = get().ir;
    if (!space) return;
    const updated = {
      ...space,
      features: space.features.map(f => f.featureId === featureId ? { ...f, ...updates } : f)
    };
    set((s) => ({
      ir: updated,
      selectedObject: findSelectedObjectInIr(updated, s.selectedObjectId),
      lastActionMessage: '功能节点属性更新成功。'
    }));
    await workspaceApi.save(updated);
  },

  deleteFeature: async (featureId) => {
    const space = get().ir;
    if (!space) return;

    // Recursive helper to gather all node IDs to delete
    const getChildIds = (id: number): number[] => {
      const feat = space.features.find(f => f.featureId === id);
      if (!feat) return [];
      return [id, ...feat.childrenIds.flatMap(cid => getChildIds(cid))];
    };

    const idsToDelete = getChildIds(featureId);
    const target = space.features.find(f => f.featureId === featureId);

    let updatedFeatures = space.features.filter(f => !idsToDelete.includes(f.featureId));
    // Remove from parent's childrenIds
    if (target && target.parentId !== null) {
      updatedFeatures = updatedFeatures.map(f => f.featureId === target.parentId ? {
        ...f,
        childrenIds: f.childrenIds.filter(cid => cid !== featureId)
      } : f);
    }

    const updated = { ...space, features: updatedFeatures };
    set({
      ir: updated,
      selectedObjectId: null,
      selectedObject: null,
      lastActionMessage: '选定功能节点及其子分支已全部移除。'
    });
    await workspaceApi.save(updated);
  },

  // Scenarios CRUD
  addScenario: async (featureId, actorId, name, content) => {
    const space = get().ir;
    if (!space) return;
    const newScenario: ScenarioNode = {
      kind: 'scenario',
      scenarioId: makeIntId(),
      scenarioName: name,
      scenarioContent: content,
      featureId,
      actorId,
      acceptanceCriteria: []
    };

    const updated = {
      ...space,
      features: space.features.map(f => f.featureId === featureId ? {
        ...f,
        scenarios: [...f.scenarios, newScenario]
      } : f)
    };

    set({ ir: updated, lastActionMessage: `已为功能添加新场景：${name}` });
    await workspaceApi.save(updated);
  },

  updateScenario: async (featureId, scenarioId, updates) => {
    const space = get().ir;
    if (!space) return;
    const updated = {
      ...space,
      features: space.features.map(f => f.featureId === featureId ? {
        ...f,
        scenarios: f.scenarios.map(s => s.scenarioId === scenarioId ? { ...s, ...updates } : s)
      } : f)
    };
    set((s) => ({
      ir: updated,
      selectedObject: findSelectedObjectInIr(updated, s.selectedObjectId),
      lastActionMessage: '成功场景已更新。'
    }));
    await workspaceApi.save(updated);
  },

  deleteScenario: async (featureId, scenarioId) => {
    const space = get().ir;
    if (!space) return;
    const updated = {
      ...space,
      features: space.features.map(f => f.featureId === featureId ? {
        ...f,
        scenarios: f.scenarios.filter(s => s.scenarioId !== scenarioId)
      } : f)
    };
    set({
      ir: updated,
      selectedObjectId: null,
      selectedObject: null,
      lastActionMessage: '场景已删除。'
    });
    await workspaceApi.save(updated);
  },

  // Acceptance Criteria CRUD
  addAcceptanceCriterion: async (featureId, scenarioId, content) => {
    const space = get().ir;
    if (!space) return;
    const newAc: AcceptanceCriterionNode = {
      kind: 'acceptance_criterion',
      criterionId: makeIntId(),
      criterionContent: content
    };

    const updated = {
      ...space,
      features: space.features.map(f => f.featureId === featureId ? {
        ...f,
        scenarios: f.scenarios.map(s => s.scenarioId === scenarioId ? {
          ...s,
          acceptanceCriteria: [...s.acceptanceCriteria, newAc]
        } : s)
      } : f)
    };

    set({ ir: updated, lastActionMessage: '成功验收标准添加成功！' });
    await workspaceApi.save(updated);
  },

  updateAcceptanceCriterion: async (featureId, scenarioId, criterionId, content) => {
    const space = get().ir;
    if (!space) return;
    const updated = {
      ...space,
      features: space.features.map(f => f.featureId === featureId ? {
        ...f,
        scenarios: f.scenarios.map(s => s.scenarioId === scenarioId ? {
          ...s,
          acceptanceCriteria: s.acceptanceCriteria.map(a => a.criterionId === criterionId ? { ...a, criterionContent: content } : a)
        } : s)
      } : f)
    };
    set((s) => ({
      ir: updated,
      selectedObject: findSelectedObjectInIr(updated, s.selectedObjectId),
      lastActionMessage: '验收标准已修改。'
    }));
    await workspaceApi.save(updated);
  },

  deleteAcceptanceCriterion: async (featureId, scenarioId, criterionId) => {
    const space = get().ir;
    if (!space) return;
    const updated = {
      ...space,
      features: space.features.map(f => f.featureId === featureId ? {
        ...f,
        scenarios: f.scenarios.map(s => s.scenarioId === scenarioId ? {
          ...s,
          acceptanceCriteria: s.acceptanceCriteria.filter(a => a.criterionId !== criterionId)
        } : s)
      } : f)
    };
    set({
      ir: updated,
      selectedObjectId: null,
      selectedObject: null,
      lastActionMessage: '验收标准已删除。'
    });
    await workspaceApi.save(updated);
  },

  // Business Objects CRUD
  addBusinessObject: async (name, description) => {
    const space = get().ir;
    if (!space) return;
    const newBo: BusinessObjectNode = {
      kind: 'business_object',
      businessObjectId: makeIntId(),
      businessObjectName: name,
      businessObjectDescription: description,
      businessObjectAttributes: []
    };
    const updated = {
      ...space,
      businessObjects: [...space.businessObjects, newBo]
    };
    set({ ir: updated, lastActionMessage: `已创建业务对象：${name}` });
    await workspaceApi.save(updated);
  },

  updateBusinessObject: async (id, name, description) => {
    const space = get().ir;
    if (!space) return;
    const updated = {
      ...space,
      businessObjects: space.businessObjects.map(b => b.businessObjectId === id ? {
        ...b,
        businessObjectName: name,
        businessObjectDescription: description
      } : b)
    };
    set((s) => ({
      ir: updated,
      selectedObject: findSelectedObjectInIr(updated, s.selectedObjectId),
      lastActionMessage: '业务对象定义已更新。'
    }));
    await workspaceApi.save(updated);
  },

  deleteBusinessObject: async (id) => {
    const space = get().ir;
    if (!space) return;
    // Also remove this BO from flow steps inputs/outputs
    const updatedFlows = space.flows.map(f => ({
      ...f,
      flowSteps: f.flowSteps.map(step => ({
        ...step,
        inputBusinessObjectIds: step.inputBusinessObjectIds.filter(x => x !== id),
        outputBusinessObjectIds: step.outputBusinessObjectIds.filter(x => x !== id)
      }))
    }));

    const updated = {
      ...space,
      businessObjects: space.businessObjects.filter(b => b.businessObjectId !== id),
      flows: updatedFlows
    };
    set({
      ir: updated,
      selectedObjectId: null,
      selectedObject: null,
      lastActionMessage: '业务数据对象已被完全抹除。'
    });
    await workspaceApi.save(updated);
  },

  addBusinessObjectAttribute: async (boId, name, description, type, example) => {
    const space = get().ir;
    if (!space) return;
    const newAttr: BusinessObjectAttributeNode = {
      kind: 'business_object_attribute',
      businessObjectAttributeId: makeIntId(),
      businessObjectAttributeName: name,
      businessObjectAttributeDescription: description,
      businessObjectAttributeType: type,
      businessObjectAttributeExample: example
    };

    const updated = {
      ...space,
      businessObjects: space.businessObjects.map(b => b.businessObjectId === boId ? {
        ...b,
        businessObjectAttributes: [...b.businessObjectAttributes, newAttr]
      } : b)
    };

    set({ ir: updated, lastActionMessage: `已为对象添加字段属性：${name}` });
    await workspaceApi.save(updated);
  },

  updateBusinessObjectAttribute: async (boId, attrId, updates) => {
    const space = get().ir;
    if (!space) return;
    const updated = {
      ...space,
      businessObjects: space.businessObjects.map(b => b.businessObjectId === boId ? {
        ...b,
        businessObjectAttributes: b.businessObjectAttributes.map(a => a.businessObjectAttributeId === attrId ? { ...a, ...updates } : a)
      } : b)
    };
    set((s) => ({
      ir: updated,
      selectedObject: findSelectedObjectInIr(updated, s.selectedObjectId),
      lastActionMessage: '字段属性详情修改完毕。'
    }));
    await workspaceApi.save(updated);
  },

  deleteBusinessObjectAttribute: async (boId, attrId) => {
    const space = get().ir;
    if (!space) return;
    const updated = {
      ...space,
      businessObjects: space.businessObjects.map(b => b.businessObjectId === boId ? {
        ...b,
        businessObjectAttributes: b.businessObjectAttributes.filter(a => a.businessObjectAttributeId !== attrId)
      } : b)
    };
    set({
      ir: updated,
      selectedObjectId: null,
      selectedObject: null,
      lastActionMessage: '已移除字段属性。'
    });
    await workspaceApi.save(updated);
  },

  // Flows CRUD
  addFlow: async (name, description, featureIds) => {
    const space = get().ir;
    if (!space) return;
    const newFlow: FlowNode = {
      kind: 'flow',
      flowId: makeIntId(),
      flowName: name,
      flowDescription: description,
      featureIds,
      flowSteps: []
    };
    const updated = {
      ...space,
      flows: [...space.flows, newFlow]
    };
    set({ ir: updated, lastActionMessage: `已组建业务流程：${name}` });
    await workspaceApi.save(updated);
  },

  updateFlow: async (flowId, updates) => {
    const space = get().ir;
    if (!space) return;
    const updated = {
      ...space,
      flows: space.flows.map(f => f.flowId === flowId ? { ...f, ...updates } : f)
    };
    set((s) => ({
      ir: updated,
      selectedObject: findSelectedObjectInIr(updated, s.selectedObjectId),
      lastActionMessage: '流程信息已更新。'
    }));
    await workspaceApi.save(updated);
  },

  deleteFlow: async (flowId) => {
    const space = get().ir;
    if (!space) return;
    const updated = {
      ...space,
      flows: space.flows.filter(f => f.flowId !== flowId)
    };
    set({
      ir: updated,
      selectedObjectId: null,
      selectedObject: null,
      lastActionMessage: '流程已被连根剔除。'
    });
    await workspaceApi.save(updated);
  },

  addFlowStep: async (flowId, step) => {
    const space = get().ir;
    if (!space) return;
    const newStepId = makeIntId();
    const flow = space.flows.find(f => f.flowId === flowId);
    if (!flow) return;

    const newStep: FlowStepNode = {
      kind: 'flow_step',
      stepId: newStepId,
      position: flow.flowSteps.length + 1,
      stepName: step.stepName,
      stepDescription: step.stepDescription,
      stepType: step.stepType,
      actorIds: step.actorIds,
      inputBusinessObjectIds: step.inputBusinessObjectIds,
      outputBusinessObjectIds: step.outputBusinessObjectIds,
      nextStepIds: []
    };

    // Sequential binding for nextStepIds from previous step
    let updatedSteps = [...flow.flowSteps, newStep];
    if (updatedSteps.length > 1) {
      updatedSteps[updatedSteps.length - 2].nextStepIds = [newStepId];
    }

    const updated = {
      ...space,
      flows: space.flows.map(f => f.flowId === flowId ? { ...f, flowSteps: updatedSteps } : f)
    };

    set({ ir: updated, lastActionMessage: `流程步骤 "${step.stepName}" 已载入。` });
    await workspaceApi.save(updated);
  },

  updateFlowStep: async (flowId, stepId, updates) => {
    const space = get().ir;
    if (!space) return;
    const updated = {
      ...space,
      flows: space.flows.map(f => f.flowId === flowId ? {
        ...f,
        flowSteps: f.flowSteps.map(s => s.stepId === stepId ? { ...s, ...updates } : s)
      } : f)
    };
    set((s) => ({
      ir: updated,
      selectedObject: findSelectedObjectInIr(updated, s.selectedObjectId),
      lastActionMessage: '流程步骤细项修改成功。'
    }));
    await workspaceApi.save(updated);
  },

  deleteFlowStep: async (flowId, stepId) => {
    const space = get().ir;
    if (!space) return;
    const flow = space.flows.find(f => f.flowId === flowId);
    if (!flow) return;

    let filteredSteps = flow.flowSteps.filter(s => s.stepId !== stepId);
    // Relink references
    filteredSteps = filteredSteps.map(s => ({
      ...s,
      nextStepIds: s.nextStepIds.filter(x => x !== stepId)
    }));

    // Reorder step positions
    filteredSteps = filteredSteps.map((s, idx) => ({
      ...s,
      position: idx + 1
    }));

    const updated = {
      ...space,
      flows: space.flows.map(f => f.flowId === flowId ? { ...f, flowSteps: filteredSteps } : f)
    };

    set({
      ir: updated,
      selectedObjectId: null,
      selectedObject: null,
      lastActionMessage: '选定步骤已移除，拓扑链路已完成自动流转适配。'
    });
    await workspaceApi.save(updated);
  },

  // Scope (Kano) CRUD
  updateScope: async (featureId, updates) => {
    const space = get().ir;
    if (!space) return;
    const feature = space.features.find(f => f.featureId === featureId);
    if (!feature) return;

    const baseScope: ScopeNode = feature.scope || {
      kind: 'scope',
      scopeId: makeIntId(),
      scopeStatus: '本期',
      reason: '',
      positiveSummary: '',
      negativeSummary: null,
      positivePictureBase64: null,
      negativePictureBase64: null
    };

    const mergedScope = {
      ...baseScope,
      ...updates
    };

    const updated = {
      ...space,
      features: space.features.map(f => f.featureId === featureId ? { ...f, scope: mergedScope } : f)
    };

    set((s) => ({
      ir: updated,
      selectedObject: findSelectedObjectInIr(updated, s.selectedObjectId),
      lastActionMessage: '功能优先级发布范围及理由更新成功。'
    }));
    await workspaceApi.save(updated);
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
    await workspaceApi.save(updated);
  },

  // -------------------------------------------------------------
  // Legacy Dummy Actions
  // -------------------------------------------------------------
  applyPatch: async () => {},
  openSlot: (slotId) => {
    const numId = parseInt(slotId, 10);
    const space = get().ir;
    if (space?.perceptionSlot?.perceptionSlotId === numId) {
      set({ selectedSlotId: numId, selectedObject: space.perceptionSlot, selectedObjectId: numId });
    }
  },
  expandSlot: async () => {},
  acceptChoice: async () => {},
  rejectChoice: async () => {},
  createSlotFromIssue: async () => null,
  setNodeStatus: async () => {},
  setScopeStatus: async (nodeId, scopeStatus) => {
    // Redirects to updateScope if it matches a feature
    const featId = parseInt(nodeId, 10);
    if (!isNaN(featId)) {
      await get().updateScope(featId, { scopeStatus });
    }
  },
  runDiagnosis: async () => {
    set({ lastActionMessage: '静态检查就绪：已根据建模规则同步更新诊断问题。' });
  },
  rewrite: async () => {},
  explainImpact: async () => {},
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
  acceptProposal: async () => {},
  rejectProposal: async () => {},
  convertProposalToChoice: async () => {},
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

export const selectChoices = () => emptyArray as Choice[];
export const selectProposals = () => emptyArray as Proposal[];

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
