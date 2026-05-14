import { create } from 'zustand';
import {
  RequirementSpaceIR,
  RequirementNode,
  BaseNode,
  Issue,
  Choice,
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
  generateChoices: (slotId: string) => Promise<void>;
  selectChoice: (choiceId: string) => Promise<void>;
  rejectChoice: (choiceId: string) => Promise<void>;
  markNodeStatus: (nodeId: string, status: NodeStatus) => Promise<void>;
  setNodeScope: (nodeId: string, scopeStatus: ScopeStatus) => Promise<void>;
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

  // Legacy actions for compatibility with older UI parts during transition
  acceptCandidate: (candidateId: string) => Promise<void>;
  generateGap: (targetId?: string) => Promise<void>;
  deferObject: (objId: string) => Promise<void>;
  excludeObject: (objId: string) => Promise<void>;
  generateCandidate: (gapId: string) => Promise<void>;
  moveScopeItem: (itemId: string, newColumn: string) => Promise<void>;
}

const findSelectedObjectInIr = (ir: RequirementSpaceIR | null, selectedId: string | null) => {
  if (!ir || !selectedId) return null;
  if (ir.nodes[selectedId]) return ir.nodes[selectedId];
  if (ir.issues[selectedId]) return ir.issues[selectedId];
  for (const group of Object.values(ir.choiceGroups || {})) {
    if (!group?.choices) continue;
    const choice = group.choices.find((c) => c.id === selectedId);
    if (choice) return choice;
  }
  return null;
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
      const ir = await workspaceApi.applyPatch(workspaceId, patch as any);
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
    const choiceGroupId = slot?.choiceGroupId || null;
    set({
      selectedSlotId: slotId,
      activeChoiceGroupId: choiceGroupId,
      selectedObject: choiceGroupId && state.ir ? state.ir.choiceGroups[choiceGroupId] : slot || null,
      selectedObjectId: choiceGroupId || slotId,
    });
  },
  
  generateChoices: async (slotId) => {
    const state = get();
    if (!state.ir?.id) return;
    const slot = state.ir.slots[slotId];
    if (slot?.choiceGroupId) {
      set({
        selectedObjectId: slot.choiceGroupId,
        selectedObject: state.ir.choiceGroups[slot.choiceGroupId],
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
        lastActionMessage: '已展开 Slot 并生成候选方案。',
      });
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },
  
  selectChoice: async (choiceId) => {
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
        lastActionMessage: '候选方案已采纳并应用。',
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
        lastActionMessage: '候选方案已拒绝。',
      });
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },
  
  markNodeStatus: async (nodeId, status) => {
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
  
  setNodeScope: async (nodeId, scopeStatus) => {
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
            ? '已完成诊断并新增缺口项。'
            : '已完成诊断，未发现新增缺口。',
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
      set((state) => ({
        ir,
        isLoading: false,
        selectedObject: findSelectedObjectInIr(ir, state.selectedObjectId),
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
          lastActionMessage: '请选择一个候选方案后再解释影响。',
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
      const knownKeys = ['title', 'description', 'status', 'scopeStatus', 'confidence', 'source'];
      const body: Record<string, any> = {};
      const extra: Record<string, any> = {};

      Object.entries(updates || {}).forEach(([key, value]) => {
        if (knownKeys.includes(key)) {
          body[key] = value;
        } else {
          extra[key] = value;
        }
      });

      if (Object.keys(extra).length > 0) {
        body.extra = extra;
      }

      const ir = await workspaceApi.patchNode(workspaceId, nodeId, body);
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
        lastActionMessage: '已更新缺口信息。',
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
        lastActionMessage: '已更新候选方案。',
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
        proposedNodeIds: [],
        proposedLinkIds: [],
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
        lastActionMessage: '已补充新候选方案。',
      });
    } catch (err) {
      setError(set, err);
      set({ isLoading: false });
    }
  },

  // Legacy mappings
  acceptCandidate: async (candidateId) => {
    await get().selectChoice(candidateId);
  },

  deferObject: async (objId) => {
    const state = get();
    const issue = state.ir?.issues?.[objId];
    if (issue) {
      try {
        const workspaceId = withWorkspaceId(state);
        const ir = await workspaceApi.patchIssueStatus(workspaceId, objId, 'ignored');
        set({
          ir,
          selectedObject: null,
          selectedObjectId: null,
          lastActionMessage: '缺口已暂缓。',
        });
      } catch (err) {
        setError(set, err);
      }
      return;
    }
    await get().markNodeStatus(objId, 'deferred');
  },

  excludeObject: async (objId) => {
    const state = get();
    const choice = Object.values(state.ir?.choiceGroups || {})
      .flatMap((group) => group.choices || [])
      .find((c) => c.id === objId);
    if (choice) {
      await get().rejectChoice(objId);
      return;
    }
    await get().markNodeStatus(objId, 'excluded');
  },

  generateCandidate: async (gapId) => {
    const state = get();
    if (!state.ir?.id) return;
    if (state.ir.issues[gapId]) {
      set({ isLoading: true, error: null });
      try {
        const resp = await workspaceApi.createSlotForIssue(state.ir.id, gapId);
        const ir = resp.workspace;
        const slot = ir.slots?.[resp.slotId];
        set({
          ir,
          isLoading: false,
          selectedSlotId: resp.slotId,
          activeChoiceGroupId: slot?.choiceGroupId || null,
          selectedObjectId: resp.slotId,
          selectedObject: slot || null,
          lastActionMessage: '已创建修复 Slot，等待展开候选。',
        });
      } catch (err) {
        setError(set, err);
        set({ isLoading: false });
      }
      return;
    }

    await get().runDiagnosis({ targetId: gapId });
  },

  generateGap: async () => {
    await get().runDiagnosis({ trigger: 'manual' });
  },

  moveScopeItem: async (itemId, newColumn) => {
    const ir = get().ir;
    const node = ir?.nodes?.[itemId];
    const isExcludedTarget = newColumn === '已排除' || newColumn === '明确排除';
    if (isExcludedTarget) {
      await get().markNodeStatus(itemId, 'excluded');
      return;
    }

    if (node?.status === 'excluded') {
      await get().markNodeStatus(itemId, 'needs_confirmation');
    }

    let scopeStatus: ScopeStatus = 'in_scope';
    if (newColumn === '本期暂不处理' || newColumn === '暂缓处理') scopeStatus = 'deferred';
    else if (newColumn === '外部依赖') scopeStatus = 'external_dependency';
    else if (newColumn === '范围外') scopeStatus = 'out_of_scope';
    await get().setNodeScope(itemId, scopeStatus);
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

const candidatesCache = new WeakMap<any, Choice[]>();
const getCandidates = (choiceGroups: any) => {
  const safeChoiceGroups = choiceGroups || {};
  if (!candidatesCache.has(safeChoiceGroups)) {
    let choices: Choice[] = [];
    Object.values(safeChoiceGroups).forEach((cg: any) => {
      if (cg && cg.choices) {
        choices = [...choices, ...cg.choices];
      }
    });
    candidatesCache.set(safeChoiceGroups, choices);
  }
  return candidatesCache.get(safeChoiceGroups)!;
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

export const selectCandidates = (state: WorkspaceState) => {
  if (!state.ir) return emptyArray;
  return getCandidates(state.ir.choiceGroups);
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
  gapCount: number;
  todoCount: number;
  hasRisk: boolean;
  disabled: boolean;
}

export const selectPageHealth = (state: WorkspaceState, path: string): PageHealth => {
  return buildPageHealth(state.ir, path);
};
