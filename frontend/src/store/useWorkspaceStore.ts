import { create } from 'zustand';
import {
  RequirementSpaceIR,
  RequirementNode,
  BaseNode,
  Issue,
  Choice,
  ChoiceGroup,
  Proposal,
  GoalNode,
  CapabilityNode,
  TaskNode,
  ActorNode,
  FlowStepNode,
  NodeStatus,
  ScopeStatus,
  GraphPatch,
} from '@/types';
import { workspaceApi } from '@/lib/api';
import { buildPageHealth } from '@/domain/ir/selectors';

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

interface WorkspaceState {
  currentSystemView: 'home' | 'onboarding' | 'workspace';
  setSystemView: (view: 'home' | 'onboarding' | 'workspace') => void;
  initialPrompt: string;

  activePage: WorkspacePage;
  setActivePage: (page: WorkspacePage) => void;

  selectedObjectId: string | null;
  selectedObject: any | null;
  setSelectedObject: (obj: BaseNode | { id: string } | null) => void;
  selectedNodeId: string | null;
  selectedSlotId: string | null;
  activeChoiceGroupId: string | null;
  highlightedNodeIds: string[];

  ir: RequirementSpaceIR | null;

  highlightTarget: string | null;
  setHighlightTarget: (id: string | null) => void;
  isLoading: boolean;
  error: string | null;
  lastActionMessage: string | null;
  workspaces: WorkspaceListItem[];

  // Actions
  initializeWorkspace: (prompt: string) => Promise<void>;
  openExistingProject: () => Promise<void>;
  openWorkspace: (workspaceId: string) => Promise<void>;
  refreshWorkspace: () => Promise<void>;
  loadWorkspaces: () => Promise<void>;
  exitWorkspace: () => void;
  
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
  createIssue: (payload: {
    title: string;
    description?: string;
    severity?: 'low' | 'medium' | 'high';
    category?: string;
    relatedNodeIds?: string[];
    suggestedProjection?: string;
    suggestedAction?: string;
  }) => Promise<void>;
  updateIssueAttributes: (issueId: string, updates: Partial<Issue> & Record<string, any>) => Promise<void>;
  updateChoiceAttributes: (choiceId: string, updates: Partial<Choice> & Record<string, any>) => Promise<void>;
  addChoiceToGroup: (choiceGroupId: string, payload: { title: string; rationale?: string }) => Promise<void>;
  acceptProposal: (proposalId: string) => Promise<void>;
  rejectProposal: (proposalId: string) => Promise<void>;
  convertProposalToChoice: (proposalId: string) => Promise<void>;
}

const findSelectedObjectInIr = (ir: RequirementSpaceIR | null, selectedId: string | null) => {
  if (!ir || !selectedId) return null;
  if (ir.nodes[selectedId]) return ir.nodes[selectedId];
  if (ir.issues[selectedId]) return ir.issues[selectedId];
  if (ir.slots[selectedId]) return ir.slots[selectedId];
  if (ir.choiceGroups[selectedId]) return ir.choiceGroups[selectedId];
  if (ir.proposals[selectedId]) return ir.proposals[selectedId];
  for (const group of Object.values(ir.choiceGroups || {})) {
    if (!group?.choices) continue;
    const choice = group.choices.find((c) => c.id === selectedId);
    if (choice) return choice;
  }
  return null;
};

const findChoiceGroupBySlotId = (ir: RequirementSpaceIR | null, slotId: string | null): ChoiceGroup | null => {
  if (!ir || !slotId) return null;
  return Object.values(ir.choiceGroups || {}).find((group) => group.slotId === slotId) || null;
};

const findChoiceGroupByChoiceId = (ir: RequirementSpaceIR | null, choiceId: string | null): ChoiceGroup | null => {
  if (!ir || !choiceId) return null;
  return (
    Object.values(ir.choiceGroups || {}).find((group) =>
      (group.choices || []).some((choice) => choice.id === choiceId)
    ) || null
  );
};

const withWorkspaceId = (state: WorkspaceState): string => {
  if (!state.ir?.id) {
    throw new Error('当前工作区尚未初始化');
  }
  return state.ir.id;
};

const setError = (set: any, err: unknown) => {
  set({ error: err instanceof Error ? err.message : '操作失败' });
};

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  currentSystemView: 'home',
  setSystemView: (view) => set({ currentSystemView: view }),
  initialPrompt: '',

  activePage: '/',
  setActivePage: (page) => set({ activePage: page }),

  selectedObjectId: null,
  selectedObject: null,
  setSelectedObject: (obj) => set({ 
    selectedObjectId: obj ? obj.id : null,
    selectedObject: obj,
    selectedNodeId: obj ? obj.id : null 
  }),
  
  selectedNodeId: null,
  selectedSlotId: null,
  activeChoiceGroupId: null,
  highlightedNodeIds: [],

  ir: null,

  highlightTarget: null,
  setHighlightTarget: (id) => set({ highlightTarget: id }),
  isLoading: false,
  error: null,
  lastActionMessage: null,
  workspaces: [],

  initializeWorkspace: async (prompt) => {
    set({ isLoading: true, error: null, lastActionMessage: null });
    try {
      const ir = await workspaceApi.bootstrap(prompt);
      set({
        currentSystemView: 'workspace',
        initialPrompt: prompt,
        ir,
        isLoading: false,
        selectedObject: null,
        selectedObjectId: null,
      });
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  openExistingProject: async () => {
    set({ isLoading: true, error: null, lastActionMessage: null });
    try {
      const ir = await workspaceApi.getDefault();
      set({
        currentSystemView: 'workspace',
        initialPrompt: ir.idea || '',
        ir,
        isLoading: false,
        selectedObject: null,
        selectedObjectId: null,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (message.includes('没有 workspace') || message.includes('404')) {
        set({
          currentSystemView: 'onboarding',
          ir: null,
          isLoading: false,
          error: null,
          lastActionMessage: '当前没有已有项目，请先创建一个新工作区。',
        });
        return;
      }
      setError(set, err);
      set({ isLoading: false });
    }
  },

  openWorkspace: async (workspaceId) => {
    set({ isLoading: true, error: null, lastActionMessage: null });
    try {
      const ir = await workspaceApi.getById(workspaceId);
      set({
        currentSystemView: 'workspace',
        initialPrompt: ir.idea || '',
        ir,
        isLoading: false,
        selectedObject: null,
        selectedObjectId: null,
      });
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  refreshWorkspace: async () => {
    const state = get();
    if (!state.ir?.id) return;
    set({ isLoading: true, error: null });
    try {
      const ir = await workspaceApi.getById(state.ir.id);
      set((s) => ({
        ir,
        isLoading: false,
        selectedObject: findSelectedObjectInIr(ir, s.selectedObjectId),
        lastActionMessage: '已同步最新数据。',
      }));
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  loadWorkspaces: async () => {
    set({ isLoading: true, error: null });
    try {
      const workspaces = await workspaceApi.list();
      set({ workspaces, isLoading: false });
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  exitWorkspace: () => set({
    currentSystemView: 'home',
    ir: null,
    selectedObject: null,
    selectedObjectId: null,
    error: null,
    lastActionMessage: null,
  }),

  applyPatch: async (patch) => {
    set({ isLoading: true, error: null });
    try {
      const workspaceId = withWorkspaceId(get());
      const resp = await workspaceApi.applyPatch(workspaceId, patch as any);
      const ir = resp.workspace;
      set((state) => ({
        ir,
        isLoading: false,
        selectedObject: findSelectedObjectInIr(ir, state.selectedObjectId),
        lastActionMessage: '已应用变更。',
      }));
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },
  
  openSlot: (slotId) => {
    const state = get();
    const slot = state.ir?.slots?.[slotId];
    const choiceGroup = findChoiceGroupBySlotId(state.ir, slotId);
    const choiceGroupId = choiceGroup?.id || null;
    set({
      selectedSlotId: slotId,
      activeChoiceGroupId: choiceGroupId,
      selectedObject: choiceGroup || slot || null,
      selectedObjectId: choiceGroupId || slotId,
    });
    if (!choiceGroup && slot?.status === 'empty') {
      void get().expandSlot(slotId);
    }
  },

  createSlotFromIssue: async (issueId) => {
    const state = get();
    if (!state.ir?.id) return null;
    set({ isLoading: true, error: null });
    try {
      const resp = await workspaceApi.createSlotForIssue(state.ir.id, issueId);
      const ir = resp.workspace;
      set({
        ir,
        isLoading: false,
        selectedSlotId: resp.slotId,
        activeChoiceGroupId: null,
        selectedObjectId: resp.slotId,
        selectedObject: ir.slots[resp.slotId] || null,
        lastActionMessage: '已从 Issue 创建 Slot。',
      });
      return resp.slotId;
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
      return null;
    }
  },

  expandSlot: async (slotId) => {
    const state = get();
    if (!state.ir?.id) return;
    const existingGroup = findChoiceGroupBySlotId(state.ir, slotId);
    if (existingGroup) {
      set({
        selectedSlotId: slotId,
        activeChoiceGroupId: existingGroup.id,
        selectedObjectId: existingGroup.id,
        selectedObject: existingGroup,
        lastActionMessage: '已打开现有 ChoiceGroup。',
      });
      return;
    }
    set({ isLoading: true, error: null });
    try {
      const resp = await workspaceApi.expandSlot(state.ir.id, slotId);
      const ir = resp.workspace;
      set({
        ir,
        isLoading: false,
        selectedSlotId: slotId,
        activeChoiceGroupId: resp.choiceGroupId,
        selectedObjectId: resp.choiceGroupId,
        selectedObject: ir.choiceGroups[resp.choiceGroupId],
        lastActionMessage: '已展开 Slot 并生成 ChoiceGroup。',
      });
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  acceptChoice: async (choiceId) => {
    set({ isLoading: true, error: null });
    try {
      const workspaceId = withWorkspaceId(get());
      const ir = await workspaceApi.acceptChoice(workspaceId, choiceId);
      const selected = findSelectedObjectInIr(ir, choiceId);
      set({
        ir,
        isLoading: false,
        selectedObjectId: selected?.id || null,
        selectedObject: selected,
        lastActionMessage: 'Choice 已采纳并应用。',
      });
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },
  
  rejectChoice: async (choiceId) => {
    set({ isLoading: true, error: null });
    try {
      const workspaceId = withWorkspaceId(get());
      const ir = await workspaceApi.rejectChoice(workspaceId, choiceId);
      set({
        ir,
        isLoading: false,
        selectedObjectId: null,
        selectedObject: null,
        lastActionMessage: 'Choice 已拒绝。',
      });
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  setNodeStatus: async (nodeId, status) => {
    set({ isLoading: true, error: null });
    try {
      const workspaceId = withWorkspaceId(get());
      const ir = await workspaceApi.patchNodeStatus(workspaceId, nodeId, status);
      set((state) => ({
        ir,
        isLoading: false,
        selectedObject: findSelectedObjectInIr(ir, state.selectedObjectId),
        lastActionMessage: '已更新节点状态。',
      }));
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  setScopeStatus: async (nodeId, scopeStatus) => {
    set({ isLoading: true, error: null });
    try {
      const workspaceId = withWorkspaceId(get());
      const ir = await workspaceApi.patchNodeScope(workspaceId, nodeId, scopeStatus);
      set((state) => ({
        ir,
        isLoading: false,
        selectedObject: findSelectedObjectInIr(ir, state.selectedObjectId),
        lastActionMessage: '已更新范围状态。',
      }));
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },
  
  runDiagnosis: async (scope) => {
    set({ isLoading: true, error: null });
    try {
      const workspaceId = withWorkspaceId(get());
      const resp = await workspaceApi.diagnose(workspaceId, scope);
      const ir = resp.workspace;
      set((state) => ({
        ir,
        isLoading: false,
        selectedObject: findSelectedObjectInIr(ir, state.selectedObjectId),
        lastActionMessage:
          (resp.result?.createdIssueIds as string[] | undefined)?.length
            ? '已完成诊断并新增 Issue。'
            : '已完成诊断，未发现新增 Issue。',
      }));
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  rewrite: async (scope, instruction) => {
    set({ isLoading: true, error: null });
    try {
      const workspaceId = withWorkspaceId(get());
      const resp = await workspaceApi.rewrite(workspaceId, { scope, instruction });
      const ir = resp.workspace;
      const proposalId = (resp.result?.proposalId as string | undefined) || null;
      set((state) => ({
        ir,
        isLoading: false,
        selectedObjectId: proposalId || state.selectedObjectId,
        selectedObject: findSelectedObjectInIr(ir, proposalId || state.selectedObjectId),
        lastActionMessage: '已生成局部改写提案（未自动应用）。',
      }));
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  explainImpact: async (scope, patch, choiceId) => {
    set({ isLoading: true, error: null });
    try {
      const workspaceId = withWorkspaceId(get());
      if (!patch && !choiceId) {
        set({
          isLoading: false,
          lastActionMessage: '请选择 Choice 或 Proposal 后再解释影响。',
        });
        return;
      }
      const resp = await workspaceApi.impactPreview(workspaceId, {
        patch: patch || null,
        choiceId: choiceId || null,
      });
      const impact = resp.impactPreview;
      const count =
        (impact.affectedGoals?.length || 0) +
        (impact.affectedActors?.length || 0) +
        (impact.affectedFlows?.length || 0) +
        (impact.affectedObjects?.length || 0) +
        (impact.affectedScreens?.length || 0);
      set({
        isLoading: false,
        lastActionMessage: `影响预览：涉及 ${count} 个节点（按投影汇总）。`,
      });
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  updateNodeAttributes: async (nodeId, updates) => {
    set({ isLoading: true, error: null });
    try {
      const workspaceId = withWorkspaceId(get());
      const resp = await workspaceApi.applyPatch(workspaceId, {
        updateNodes: [{ id: nodeId, ...updates }],
      } as any);
      const ir = resp.workspace;
      set((state) => ({
        ir,
        isLoading: false,
        selectedObject: findSelectedObjectInIr(ir, state.selectedObjectId),
        lastActionMessage: '已保存修改。',
      }));
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  createIssue: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      const workspaceId = withWorkspaceId(get());
      const resp = await workspaceApi.createIssue(workspaceId, payload as any);
      const ir = resp.workspace;
      set({
        ir,
        isLoading: false,
        selectedObjectId: resp.issueId,
        selectedObject: ir.issues[resp.issueId],
        lastActionMessage: '已创建待处理项。',
      });
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  updateIssueAttributes: async (issueId, updates) => {
    set({ isLoading: true, error: null });
    try {
      const workspaceId = withWorkspaceId(get());
      const ir = await workspaceApi.patchIssueDetails(workspaceId, issueId, updates as any);
      set((state) => ({
        ir,
        isLoading: false,
        selectedObject: findSelectedObjectInIr(ir, state.selectedObjectId),
        lastActionMessage: '已更新 Issue。',
      }));
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  updateChoiceAttributes: async (choiceId, updates) => {
    set({ isLoading: true, error: null });
    try {
      const workspaceId = withWorkspaceId(get());
      const ir = await workspaceApi.patchChoice(workspaceId, choiceId, updates as any);
      set((state) => ({
        ir,
        isLoading: false,
        selectedObject: findSelectedObjectInIr(ir, state.selectedObjectId),
        lastActionMessage: '已更新 Choice。',
      }));
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  addChoiceToGroup: async (choiceGroupId, payload) => {
    set({ isLoading: true, error: null });
    try {
      const workspaceId = withWorkspaceId(get());
      const resp = await workspaceApi.addChoiceToGroup(workspaceId, choiceGroupId, {
        title: payload.title,
        rationale: payload.rationale || '',
        patch: {},
        impactPreview: {
          affectedGoals: [],
          affectedActors: [],
          affectedFlows: [],
          affectedObjects: [],
          affectedScreens: [],
        },
      });
      const ir = resp.workspace;
      set({
        ir,
        isLoading: false,
        selectedObjectId: choiceGroupId,
        selectedObject: ir.choiceGroups[choiceGroupId],
        lastActionMessage: '已补充 Choice。',
      });
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  acceptProposal: async (proposalId) => {
    set({ isLoading: true, error: null });
    try {
      const workspaceId = withWorkspaceId(get());
      const resp = await workspaceApi.acceptProposal(workspaceId, proposalId);
      const ir = resp.workspace;
      set({
        ir,
        isLoading: false,
        selectedObjectId: null,
        selectedObject: null,
        lastActionMessage: '提案已采纳并应用到 IR。',
      });
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  rejectProposal: async (proposalId) => {
    set({ isLoading: true, error: null });
    try {
      const workspaceId = withWorkspaceId(get());
      const resp = await workspaceApi.rejectProposal(workspaceId, proposalId);
      const ir = resp.workspace;
      set({
        ir,
        isLoading: false,
        selectedObjectId: proposalId,
        selectedObject: ir.proposals[proposalId] || null,
        lastActionMessage: '提案已拒绝。',
      });
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  convertProposalToChoice: async (proposalId) => {
    set({ isLoading: true, error: null });
    try {
      const workspaceId = withWorkspaceId(get());
      const resp = await workspaceApi.convertProposalToChoice(workspaceId, proposalId);
      const ir = resp.workspace;
      set({
        ir,
        isLoading: false,
        selectedSlotId: ir.choiceGroups[resp.choiceGroupId]?.slotId || null,
        activeChoiceGroupId: resp.choiceGroupId,
        selectedObjectId: resp.choiceGroupId,
        selectedObject: ir.choiceGroups[resp.choiceGroupId] || null,
        lastActionMessage: '提案已转为 Choice。',
      });
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

}));

const selectNodesByKindCache = new WeakMap<any, Record<string, any[]>>();
const getNodesByKind = (nodes: any, kind: string) => {
  if (!selectNodesByKindCache.has(nodes)) {
    selectNodesByKindCache.set(nodes, {});
  }
  const cacheMap = selectNodesByKindCache.get(nodes)!;
  if (!cacheMap[kind]) {
    cacheMap[kind] = Object.values(nodes).filter((n: any) => n.kind === kind);
  }
  return cacheMap[kind];
};

const issuesCache = new WeakMap<any, any[]>();
const getIssues = (issues: any) => {
  if (!issuesCache.has(issues || {})) {
    issuesCache.set(issues || {}, Object.values(issues || {}));
  }
  return issuesCache.get(issues || {})!;
};

const choicesCache = new WeakMap<any, Choice[]>();
const getChoices = (choiceGroups: any) => {
  const safeChoiceGroups = choiceGroups || {};
  if (!choicesCache.has(safeChoiceGroups)) {
    let choices: Choice[] = [];
    Object.values(safeChoiceGroups).forEach((cg: any) => {
      if (cg && cg.choices) {
        choices = [...choices, ...cg.choices];
      }
    });
    choicesCache.set(safeChoiceGroups, choices);
  }
  return choicesCache.get(safeChoiceGroups)!;
};

export const selectProposals = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray;
  return Object.values(state.ir.proposals || {}) as Proposal[];
};

const scopeItemsCache = new WeakMap<any, RequirementNode[]>();
const getScopeItems = (nodes: any) => {
  if (!scopeItemsCache.has(nodes)) {
    scopeItemsCache.set(nodes, Object.values(nodes).filter((n: any) => n.scopeStatus) as RequirementNode[]);
  }
  return scopeItemsCache.get(nodes)!;
};

const emptyArray: any[] = [];

// Selectors mimicking the old flat arrays for the UI to transition smoothly

export const selectGoals = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray as GoalNode[];
  return getNodesByKind(state.ir.nodes, 'goal') as GoalNode[];
};

export const selectCapabilities = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray as CapabilityNode[];
  return getNodesByKind(state.ir.nodes, 'capability') as CapabilityNode[];
};

export const selectTasks = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray as TaskNode[];
  return getNodesByKind(state.ir.nodes, 'task') as TaskNode[];
};

export const selectActors = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray as ActorNode[];
  return getNodesByKind(state.ir.nodes, 'actor') as ActorNode[];
};

export const selectFlowSteps = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray as FlowStepNode[];
  return getNodesByKind(state.ir.nodes, 'flow_step') as FlowStepNode[];
};

export const selectIssues = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray;
  return getIssues(state.ir.issues);
};

export const selectChoices = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray;
  return getChoices(state.ir.choiceGroups);
};

export const selectScopeItems = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray;
  return getScopeItems(state.ir.nodes);
};

export const selectLinks = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray;
  return state.ir.links || emptyArray;
};

export const selectSelectedObject = (state: WorkspaceState) => {
  if (state.selectedObject) return state.selectedObject;
  return findSelectedObjectInIr(state.ir, state.selectedObjectId);
};

export const selectCurrentPage = (state: WorkspaceState) => state.activePage;

export interface PageHealth {
  status: '阻塞' | '待决策' | '可预览' | '已收敛' | '不可用' | '未开始';
  issueCount: number;
  todoCount: number;
  hasRisk: boolean;
  disabled: boolean;
}

export const selectPageHealth = (state: WorkspaceState, path: string): PageHealth => {
  return buildPageHealth(state.ir, path);
};
