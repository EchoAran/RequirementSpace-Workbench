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
  Finding,
  FindingType,
  BlockingScope,
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
  PendingManualAction,
} from '@/core/schema';
import { workspaceApi } from '@/lib/api';
import { buildPageHealth } from '@/core/selectors';
import { getNextSuggestionPresentation } from '@/core/nextSuggestionPresentation';

const getConfirmationStatus = (value: unknown): NodeStatus => {
  return value === 'confirmed' || value === 'needs_confirmation' || value === 'ai_assumption'
    ? value
    : 'ai_assumption';
};


export type WorkspacePage = '/what' | '/flow' | '/scope' | '/preview' | '/overview';



// -------------------------------------------------------------
// Unified Normalization Helper for Backend Data Synchronization
// -------------------------------------------------------------
const mapBackendChoiceGroupToCompatible = (cg: any): ChoiceGroup => {
  return {
    id: cg.id.toString(),
    slotId: (cg.slotId ?? cg.slot_id) ? String(cg.slotId ?? cg.slot_id) : '',
    status: cg.status as any,
    selectionMode: (cg.selectionMode ?? cg.selection_mode) as any,
    sourceType: cg.sourceType ?? cg.source_type,
    issueCode: cg.issueCode ?? cg.issue_code,
    issueId: cg.issueId ?? cg.issue_id,
    generationType: cg.generationType ?? cg.generation_type,
    target: cg.target,
    candidateCount: cg.candidateCount ?? cg.candidate_count,
    successCount: cg.successCount ?? cg.success_count,
    failureCount: cg.failureCount ?? cg.failure_count,
    statusDetail: cg.statusDetail ?? cg.status_detail,
    choices: (cg.choices || []).map((c: any) => ({
      id: c.id.toString(),
      choiceGroupId: String(c.choiceGroupId ?? c.choice_group_id ?? cg.id),
      title: c.title,
      rationale: c.rationale,
      status: c.status as any,
      patch: c.patch,
      impactPreview: c.impactPreview ?? c.impact_preview,
      payload: c.payload,
      draftType: c.draftType ?? c.draft_type,
      applyMode: c.applyMode ?? c.apply_mode,
      preview: c.preview,
      comparisonSummary: c.comparisonSummary ?? c.comparison_summary,
      score: c.score,
      error: c.error,
    }))
  };
};

const resolutionType = (res: any): string | undefined => res.resolutionType || res.resolution_type;
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

/**
 * 浠?Finding 瀵硅薄鑾峰彇澶勭悊鑳藉姏锛堜紭鍏堜娇鐢ㄥ悗绔繑鍥炵殑 capability锛夈€?
 *
 * 浠讳綍鏃跺€欎紭鍏堜俊浠诲悗绔?capability 瀛楁锛涚己澶辨椂浣跨敤瀹夊叏鍥為€€锛坢anual_action锛夛紝
 * 涓嶇敱鍓嶇 code 鎺ㄥ AI capability銆?
 */
export function getFindingCapability(finding: { code: string; capability?: any; type?: string }): {
  kind: string;
  actionLabel: string;
  enabled: boolean;
} {
  // 1. 浼樺厛浣跨敤鍚庣杩斿洖鐨?capability
  if (finding.capability) {
    return {
      kind: finding.capability.kind || 'manual_action',
      actionLabel: finding.capability.action_label || '查看处理建议',
      enabled: finding.capability.enabled !== false,
    };
  }

  // 2. 鏃?capability 鏃讹紙鏃х紦瀛?鏃у搷搴旓級锛屼娇鐢ㄥ畨鍏ㄥ洖閫€
  //    绂佹鐢?code 鎺ㄥ AI capability锛岀粺涓€闄嶇骇涓?manual_action
  console.warn(
    `getFindingCapability: Finding ${finding.code} (${finding.type}) missing backend capability. ` +
    'Using safe fallback manual_action. Check if backend returned capability field.',
  );
  return {
    kind: 'manual_action',
    actionLabel: '查看处理建议',
    enabled: true,
  };
}

export const getFriendlyErrorMessage = (rawError: string): string => {
  const normalizedError = (rawError || '').toLowerCase();
  if (
    normalizedError.includes('timeout') ||
    normalizedError.includes('timed out') ||
    normalizedError.includes('request timed out')
  ) {
    return 'AI 服务响应超时，请稍后重试；如果持续出现，请检查模型服务连接状态。';
  }
  if (
    normalizedError.includes('quota') ||
    normalizedError.includes('rate limit') ||
    normalizedError.includes('429')
  ) {
    return 'AI 服务调用额度或频率受限，请稍后重试或检查 API 配额。';
  }
  if (
    normalizedError.includes('invalid api key') ||
    normalizedError.includes('unauthorized') ||
    normalizedError.includes('401')
  ) {
    return 'AI 服务鉴权失败，请检查账户设置中的 API 密钥是否有效。';
  }

  switch (rawError) {
    case 'llm_config_required':
      return '尚未配置大语言模型连接信息，请前往账户设置填写 API 密钥后再启用 AI 推演。';
    case 'server_llm_config_not_configured':
      return '服务端尚未配置共享 API 密钥与模型。普通用户请联系管理员，管理员请检查服务端 .env 配置。';
    case 'leaf_feature_without_actor':
      return '当前叶子功能节点未关联业务角色，请先为该功能模块绑定至少一个角色，再发起场景推演。';
    case 'feature_is_not_leaf':
      return '该功能节点不是叶子节点。AI 场景推演仅支持最底层叶子功能节点。';
    case 'empty_leaf_features':
      return '找不到可用于生成的叶子功能节点，请先在 What 页面创建最底层功能。';
    case 'project_not_found':
      return '未找到对应的项目空间。';
    case 'empty_actors':
      return '项目中暂无业务角色，请先在 What 页创建至少一个角色。';
    case 'empty_features':
      return '项目中暂无功能节点，请先在 What 页创建能力模块。';
    case 'feature_not_found':
      return '未找到指定的功能节点。';
    case 'actor_not_found':
      return '未找到指定的业务角色。';
    case 'draft_not_found':
      return 'AI 推演草稿已失效或过期，请重新发起 AI 推演。';
    default:
      return rawError;
  }
};
const getVisibleIssueStages = (unlockedStages?: string[]): Array<'what' | 'how' | 'scope'> => {
  const unlocked = new Set(unlockedStages || []);
  const stages: Array<'what' | 'how' | 'scope'> = ['what'];

  if (unlocked.has('what')) {
    stages.push('how');
  }
  if (unlocked.has('how')) {
    stages.push('scope');
  }

  return stages;
};

const loadBackendFindingsAndViews = async (
  projectId: string
): Promise<{
  backendFindings: Finding[];
  findingsByView: {
    issues: Finding[];
    next_action: Finding[];
    gate: Finding[];
    health: Finding[];
  };
}> => {
  try {
    const [issuesRes, nextRes, gateRes, healthRes] = await Promise.all([
      workspaceApi.listFindings(projectId, { view: 'issues', stage: 'all' }),
      workspaceApi.listFindings(projectId, { view: 'next_action', stage: 'all' }),
      workspaceApi.listFindings(projectId, { view: 'gate', stage: 'all' }),
      workspaceApi.listFindings(projectId, { view: 'health', stage: 'all' })
    ]);

    const findings_issues = issuesRes?.findings || [];
    const findings_next = nextRes?.findings || [];
    const findings_gate = gateRes?.findings || [];
    const findings_health = healthRes?.findings || [];

    const allFindings = [...findings_issues, ...findings_next, ...findings_gate, ...findings_health];

    return {
      backendFindings: allFindings,
      findingsByView: {
        issues: findings_issues,
        next_action: findings_next,
        gate: findings_gate,
        health: findings_health
      }
    };
  } catch (err) {
    console.error('Failed to load findings in loadBackendFindingsAndViews:', err);
    return {
      backendFindings: [],
      findingsByView: { issues: [], next_action: [], gate: [], health: [] }
    };
  }
};

export const normalizeRequirementSpace = (
  space: RequirementSpace | null,
  issueFindings?: Finding[] | null,
  backendChoiceGroups?: Record<string, ChoiceGroup>,
  backendFindingsLoaded?: boolean
): RequirementSpace | null => {
  console.log('normalizeRequirementSpace called with space:', space?.projectName, 'has_space:', !!space);
  if (!space) return null;

  // 1. Ensure arrays exist
  const actors = space.actors || [];
  const features = space.features || [];
  const businessObjects = space.businessObjects || [];
  const flows = space.flows || [];
  const perceptionSlot = space.perceptionSlot || null;
  const visibleIssueStages = new Set(getVisibleIssueStages(space.unlockedStages));

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
      status: getConfirmationStatus((a as any).confirmationStatus),
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
      status: getConfirmationStatus((f as any).confirmationStatus),
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
        status: getConfirmationStatus((s as any).confirmationStatus),
        scopeStatus: 'in_scope'
      };
      
      // Acceptance criteria
      (s.acceptanceCriteria || []).forEach(ac => {
        const acid = ac.criterionId.toString();
        nodes[acid] = {
          ...ac,
          id: acid,
          title: '楠屾敹鏍囧噯',
          description: ac.criterionContent,
          status: getConfirmationStatus((ac as any).confirmationStatus),
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
      status: getConfirmationStatus((b as any).confirmationStatus),
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
      status: getConfirmationStatus((fl as any).confirmationStatus),
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
          title: `${bo.businessObjectName} 看板`,
          description: `提供给 ${actor.actorName} 用于操作 ${bo.businessObjectName} 的控制台及明细页面。`,
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
      const boIds = [...new Set([...(st.inputBusinessObjectIds || []), ...(st.outputBusinessObjectIds || [])])];
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

  const dedupedLinksList = Array.from(
    new Map(linksList.map((link) => [link.id, link])).values()
  );

  // 5. Detect and index issues
  const normalizedSpaceForRules = {
    ...space,
    actors,
    features,
    businessObjects,
    flows,
    perceptionSlot
  };
  const issuesList = backendFindingsLoaded && issueFindings
    ? issueFindings.filter((finding) => finding.type === 'issue' && visibleIssueStages.has(finding.stage as any))
    : [];
  const issuesRecord: Record<string, any> = {};
  issuesList.forEach((finding) => {
    issuesRecord[finding.findingId] = finding;
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
    status: getConfirmationStatus((a as any).confirmationStatus),
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
    links: dedupedLinksList,
    issues: issuesRecord,
    slots: slotsRecord,
    choiceGroups: choiceGroupsRecord,
    findings: issuesList,
    // Stable Selector Cache Fields
    actorsCompatible,
    flowStepsCompatible,
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

const isSlotFillingDraft = (draft: any | null | undefined) => (
  draft?.perceptionJobId !== undefined || draft?.perception_job_id !== undefined
);

const generationTypeLabelMap: Record<string, string> = {
  actor: '参与者',
  feature: '功能树',
  flow: '流程与对象',
  scenario: '场景',
  acceptance_criteria: '验收标准',
  scope: '范围分析',
  project_creation: '项目草稿',
};

const getGenerationTypeLabel = (generationType?: string) => (
  generationTypeLabelMap[generationType || ''] || generationType || '候选方案'
);

const normalizeConflictTarget = (target?: any) => {
  if (!target || typeof target !== 'object') return null;
  const entries = Object.entries(target)
    .filter(([, value]) => value !== undefined && value !== null)
    .map(([key, value]): [string, string | string[]] => {
      if (Array.isArray(value)) {
        return [key, [...value].map(item => String(item)).sort()];
      }
      return [key, String(value)];
    })
    .sort(([a], [b]) => a.localeCompare(b));

  return JSON.stringify(Object.fromEntries(entries));
};

const isGenerationTargetMatch = (existingTarget?: any, requestedTarget?: any) => {
  if (!requestedTarget) return true;
  return normalizeConflictTarget(existingTarget) === normalizeConflictTarget(requestedTarget);
};

const findConflictingChoiceGroup = (
  choiceGroups: Record<string, ChoiceGroup>,
  generationType: string,
  target?: any,
) => {
  return Object.values(choiceGroups).find((group) => {
    if (!group) return false;
    if (group.status !== 'open' && group.status !== 'stale') return false;
    if ((group.generationType || '') !== generationType) return false;
    return isGenerationTargetMatch(group.target, target);
  }) || null;
};

const GENERATION_CONFLICT_PENDING_ERROR = 'generation_choice_conflict_pending';

const buildInitialChoiceProgress = (candidateCount?: number) => {
  const totalCandidates = candidateCount || 2;
  return {
    totalCandidates,
    completedCandidates: 0,
    candidateStatuses: Object.fromEntries(
      Array.from({ length: totalCandidates }, (_, index) => [index, 'pending'])
    ) as Record<number, 'pending' | 'generating' | 'complete' | 'failed'>,
  };
};

type PendingGenerationConflict =
  | {
      action: 'generateActors';
      generationType: 'actor';
      existingGroupId: string;
      existingGroupLabel: string;
    }
  | {
      action: 'generateFeatures';
      generationType: 'feature';
      existingGroupId: string;
      existingGroupLabel: string;
    }
  | {
      action: 'generateFlowsAndObjects';
      generationType: 'flow';
      existingGroupId: string;
      existingGroupLabel: string;
    }
  | {
      action: 'generateScope';
      generationType: 'scope';
      existingGroupId: string;
      existingGroupLabel: string;
    }
  | {
      action: 'generateScenarios';
      generationType: 'scenario';
      existingGroupId: string;
      existingGroupLabel: string;
      featureIds?: number[] | number;
    }
  | {
      action: 'generateAcceptanceCriteria';
      generationType: 'acceptance_criteria';
      existingGroupId: string;
      existingGroupLabel: string;
      scenarioIds?: number[];
    };

export interface WorkspaceState {
  sessionVersion: number;
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
  backendFindings: Finding[];
  backendFindingsLoaded: boolean;
  findingsByView: {
    issues: Finding[];
    next_action: Finding[];
    gate: Finding[];
    health: Finding[];
  };
  backendChoiceGroups: Record<string, ChoiceGroup>;
  isDiagnosing: boolean;
  /** @deprecated Legacy cache used only by runDiagnosis polling. UI should read findingsByView.next_action instead. */
  nextSuggestions: Record<string, any>;

  // Draft Generative States
  activeDraft: any | null;
  activeDraftType: 'project' | 'actor' | 'feature' | 'flow' | 'scenario' | 'ac' | 'scope' | 'repair' | null;
  isGenerating: boolean;

  highlightTarget: string | null;
  setHighlightTarget: (id: string | null) => void;
  pendingManualAction: PendingManualAction | null;
  setPendingManualAction: (action: PendingManualAction | null) => void;
  isLoading: boolean;
  error: string | null;
  setError: (error: string | null) => void;
  boDeletionError: string | null;
  setBoDeletionError: (error: string | null) => void;
  lastActionMessage: string | null;
  lastIssueResolution: any | null;
  workspaces: WorkspaceListItem[];

  // Project Lifecycles
  loadWorkspaces: () => Promise<void>;
  openExistingProject: () => Promise<void>;
  openWorkspace: (workspaceId: string) => Promise<void>;
  refreshWorkspace: () => Promise<void>;
  exitWorkspace: () => void;
  updateProject: (projectId: string, name: string, description: string) => Promise<void>;
  deleteProject: (projectId: string) => Promise<void>;

  // Onboarding On-demand Creation
  startAIOnboarding: (prompt: string, name?: string, description?: string) => Promise<void>;
  confirmAIOnboarding: () => Promise<void>;
  regenerateAIOnboarding: (feedback?: string) => Promise<void>;
  discardAIOnboarding: () => Promise<void>;
  createBlankWorkspace: (name: string, description: string, prompt: string) => Promise<void>;

  // Phase 2: Choice Group Onboarding
  activeChoiceGroup: any | null;
  choiceGroupGenerationProgress: {
    totalCandidates: number;
    completedCandidates: number;
    candidateStatuses: Record<number, 'pending' | 'generating' | 'complete' | 'failed'>;
  } | null;
  isGeneratingChoices: boolean;
  generatingChoiceGroupType?: string | null;
  openOnboardingChoiceGroups: any[];
  pendingGenerationConflict: PendingGenerationConflict | null;
  createOnboardingChoiceGroup: (userRequirements: string, candidateCount?: number) => Promise<void>;
  acceptOnboardingChoice: (choiceId: string) => Promise<void>;
  discardOnboardingChoiceGroup: () => Promise<void>;
  deferOnboardingChoiceGroup: () => Promise<string | null>;
  loadOpenOnboardingChoiceGroups: () => Promise<void>;
  recoverOnboardingChoiceGroup: (groupId: string) => Promise<void>;
  dismissPendingGenerationConflict: () => void;
  confirmPendingGenerationConflict: () => Promise<void>;

  // Phase 3: In-project Generation Choice Group (actor, scenario, etc.)
  createGenerationChoiceGroup: (params: {
    projectId: string;
    generationType: string;
    target?: any;
    candidateCount?: number;
    userFeedback?: string;
    forceReplace?: boolean;
    conflictAction?: PendingGenerationConflict['action'];
    conflictArgs?: Record<string, any>;
  }) => Promise<any>;

  // AI Generators per phase
  generateActors: (forceReplace?: boolean) => Promise<void>;
  regenerateActors: (feedback?: string) => Promise<void>;
  confirmActors: () => Promise<void>;
  
  generateFeatures: (forceReplace?: boolean) => Promise<void>;
  regenerateFeatures: (feedback?: string) => Promise<void>;
  confirmFeatures: () => Promise<void>;
  
  generateFlowsAndObjects: (forceReplace?: boolean) => Promise<void>;
  regenerateFlowsAndObjects: (feedback?: string) => Promise<void>;
  confirmFlowsAndObjects: () => Promise<void>;
  
  generateScenarios: (featureIds?: number[] | number, forceReplace?: boolean) => Promise<void>;
  regenerateScenarios: (feedback?: string) => Promise<void>;
  confirmScenarios: (generateAc: boolean) => Promise<void>;
  
  generateAcceptanceCriteria: (scenarioIds?: number[], forceReplace?: boolean) => Promise<void>;
  regenerateAcceptanceCriteria: (feedback?: string) => Promise<void>;
  confirmAcceptanceCriteria: () => Promise<void>;
  
  generateScope: (forceReplace?: boolean) => Promise<void>;
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
  reorderFlowSteps: (flowId: number, stepIds: number[]) => Promise<void>;

  // Scope
  updateScope: (featureId: number, updates: Partial<ScopeNode>) => Promise<void>;
  skipKano: () => Promise<void>;
  resetKano: () => Promise<void>;
  
  // PerceptionSlot
  clearPerceptionSlot: () => Promise<void>;

  openSlot: (slotId: string) => void;
  expandSlot: (slotId: string) => Promise<void>;
  acceptChoice: (choiceId: string, force?: boolean) => Promise<void>;
  rejectChoice: (choiceId: string) => Promise<void>;
  discardChoiceGroup: (groupId: number) => Promise<void>;
  activeStaleChoice: { projectId: string; choiceId: number; staleReason: string } | null;
  clearStaleChoice: () => void;
  regenerateChoiceGroup: (groupId: number, feedback?: string) => Promise<void>;
  regenerateChoice: (choiceId: number, feedback?: string) => Promise<void>;
  executeFindingIssueResolution: (issueId: string) => Promise<string | null>;
  confirmRepairDraft: (draftId: string) => Promise<any>;
  discardRepairDraft: (draftId: string) => Promise<void>;
  regenerateRepairDraft: (draftId: string) => Promise<void>;
  setNodeStatus: (nodeId: string, nodeKind: string, status: NodeStatus) => Promise<void>;
  setScopeStatus: (nodeId: string, scopeStatus: ScopeStatus) => Promise<void>;
  runDiagnosis: (scope?: any) => Promise<void>;
  rewrite: (scope: any, instruction: string) => Promise<void>;
  explainImpact: (scope: any, patch?: GraphPatch, choiceId?: string) => Promise<void>;
  updateNodeAttributes: (nodeId: string, updates: Partial<BaseNode> & Record<string, any>) => Promise<void>;
  createIssue: (payload: any) => Promise<void>;
  updateIssueAttributes: (issueId: string, updates: any) => Promise<void>;
  updateChoiceAttributes: (choiceId: string, updates: any) => Promise<void>;

  // P5 Audit and Impact
  auditLogs: any[];
  lastImpactPreview: any | null;
  loadAuditLogs: (projectId: string) => Promise<void>;
  getImpactPreview: (featureId: number, nextStatus: string) => Promise<any>;
  addChoiceToGroup: (choiceGroupId: string, payload: any) => Promise<void>;

  // P5 Shadow Preview Draft Actions
  activeShadowDraft: any | null;
  getActiveShadowDraft: () => Promise<any>;
  prepareShadowDraft: () => Promise<any>;
  getShadowDraft: (draftId: string) => Promise<any>;
  discardShadowDraft: (draftId: string) => Promise<void>;
  commitShadowDraft: (draftId: string) => Promise<void>;
  regenerateShadowDraft: (draftId: string, feedback?: string) => Promise<any>;
  unlockStageGate: (stage: string) => Promise<void>;

  // Phase 3: Gate and Suggestion Convergence
  activeGateCheck: {
    action: string;
    findings: Finding[];
    onPass: () => void;
    onCancel: () => void;
  } | null;
  snoozedGateFindingIds: Record<string, string>; // Maps key to context hash
  triggerGateCheck: (action: string, onPass: () => void, onCancel?: () => void) => Promise<void>;
  snoozeGateFinding: (action: string, finding: Finding) => void;
  startFindingSuggestion: (finding: Finding) => Promise<void>;
  executeGateFindingAction: (finding: Finding) => Promise<void>;

  // Phase 3 & 4: Collaboration Tasks
  tasks: any[];
  userTasks: any[];
  confirmationSummary: any | null;
  loadProjectTasks: (projectId: string, params?: any) => Promise<void>;
  loadMyTasks: (params?: any) => Promise<void>;
  loadConfirmationSummary: (projectId: string) => Promise<any>;
  createConfirmationTask: (
    projectId: string,
    payload: {
      nodeKind: string;
      nodeId: number;
      assignedToUserId: number;
      title?: string;
      description?: string;
      priority?: string;
      dueAt?: string;
    }
  ) => Promise<any>;
  createBatchConfirmTask: (
    projectId: string,
    payload: {
      targets: Array<{ nodeKind: string; nodeId: number }>;
      assignedToUserId: number;
      title?: string;
      description?: string;
      priority?: string;
      dueAt?: string;
    }
  ) => Promise<any>;
  decideTask: (
    projectId: string,
    taskId: number,
    payload: {
      decision: string;
      decisionNote?: string;
    }
  ) => Promise<any>;
  cancelTask: (projectId: string, taskId: number) => Promise<any>;
}

const buildSelectedScopeObject = (feature: any) => {
  if (!feature) return null;
  return {
    kind: 'scope' as const,
    id: feature.featureId?.toString?.() || null,
    featureId: feature.featureId,
    featureName: feature.featureName || '',
    featureDescription: feature.featureDescription || '',
    parentId: feature.parentId ?? null,
    scopeId: feature.scope?.scopeId,
    title: feature.featureName || '',
    description: feature.featureDescription || '',
    status: feature.scope?.confirmationStatus,
    confirmationStatus: feature.scope?.confirmationStatus,
    scopeStatus: feature.scope?.scopeStatus,
    scope: feature.scope || null,
  };
};

const findSelectedObjectInIr = (
  ir: RequirementSpace | null,
  selectedId: string | number | null,
  previousSelectedObject?: any | null,
): any => {
  if (!ir || !selectedId) return null;
  const numId = typeof selectedId === 'string' ? parseInt(selectedId, 10) : selectedId;

  if (previousSelectedObject?.kind === 'scope') {
    const scopeFeature = ir.features?.find(
      (feature: any) =>
        feature.scope?.scopeId === numId ||
        feature.featureId === previousSelectedObject.featureId,
    );
    if (scopeFeature) {
      return buildSelectedScopeObject(scopeFeature);
    }
  }

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

  const matchedIssue = (ir.findings || []).find((finding) => finding.findingId === selectedId);
  if (matchedIssue) return matchedIssue;

  return null;
};

const withWorkspaceId = (state: WorkspaceState): string => {
  if (!state.ir?.projectId) {
    throw new Error('褰撳墠宸ヤ綔鍖哄皻鏈垵濮嬪寲');
  }
  return state.ir.projectId;
};

const getGateFindingContextHash = (finding: any): string => {
  if (!finding || !finding.metadata) return '';

  if (finding.metadata.missing_pairs) {
    const pairs = [...finding.metadata.missing_pairs];
    pairs.sort((a: any, b: any) => {
      const keyA = `${a.feature_id}:${a.actor_id}`;
      const keyB = `${b.feature_id}:${b.actor_id}`;
      return keyA.localeCompare(keyB);
    });
    return JSON.stringify(pairs);
  }

  if (finding.metadata.missing_features) {
    const features = [...finding.metadata.missing_features];
    features.sort((a: any, b: any) => (a.feature_id || 0) - (b.feature_id || 0));
    return JSON.stringify(features);
  }

  return '';
};

const loadSnoozedGatesFromSession = (): Record<string, string> => {
  if (typeof window === 'undefined') return {};
  try {
    const data = sessionStorage.getItem('rs_workbench_snoozed_gates');
    return data ? JSON.parse(data) : {};
  } catch {
    return {};
  }
};

function buildAggregateTarget(finding: Finding): any {
  const meta = finding.metadata || {};
  if (finding.code === 'FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO') {
    const pairs = meta.missing_pairs || [];
    if (pairs.length > 0) {
      return {
        target_type: 'feature_actor_pair',
        target_id: `${pairs[0].feature_id}:${pairs[0].actor_id}`,
      };
    }
  }
  if (finding.code === 'LEAF_FEATURE_WITHOUT_FLOW' || finding.code === 'LEAF_FEATURE_WITHOUT_SCOPE') {
    const features = meta.missing_features || [];
    if (features.length > 0) {
      return { target_type: 'feature', target_id: features[0].feature_id };
    }
  }
  return finding.target || null;
}
export const useWorkspaceStore = create<WorkspaceState>((rawSet, get) => {
  const set = (update: any, replace?: boolean) => {
    console.log('Store set called. Update type:', typeof update, 'keys:', typeof update === 'object' && update !== null ? Object.keys(update) : 'function');
    if (typeof update === 'function') {
      (rawSet as any)((state: WorkspaceState) => {
        const next = update(state);
        if (next && 'ir' in next && next.ir !== undefined) {
          const findingsToUse = next.findingsByView?.issues || state.findingsByView.issues || [];
          const choiceGroupsToUse = next.backendChoiceGroups || state.backendChoiceGroups || {};
          const loadedToUse = next.backendFindingsLoaded !== undefined ? next.backendFindingsLoaded : state.backendFindingsLoaded;
          next.ir = normalizeRequirementSpace(next.ir, findingsToUse, choiceGroupsToUse, loadedToUse);
        }
        return next;
      }, replace);
    } else {
      if (update && 'ir' in update && update.ir !== undefined) {
        const findingsToUse = update.findingsByView?.issues || get()?.findingsByView.issues || [];
        const choiceGroupsToUse = update.backendChoiceGroups || get()?.backendChoiceGroups || {};
        const loadedToUse = update.backendFindingsLoaded !== undefined ? update.backendFindingsLoaded : get()?.backendFindingsLoaded;
        update.ir = normalizeRequirementSpace(update.ir, findingsToUse, choiceGroupsToUse, loadedToUse);
      }
      (rawSet as any)(update, replace);
    }
  };

  const executeProcessorAction = async (
    action: any,
    context: { stage?: string; findingCode?: string; target?: any },
    version: number
  ) => {
    if (!action) return;

    const kind = action.kind;

    if (kind === 'create_draft') {
      const draftType = action.draft_type || action.draftType;
      const code = context.findingCode || '';

      if (code === 'GENERATE_ACTORS' || draftType === 'actor_generation') {
        await get().generateActors(false);
      } else if (code === 'GENERATE_FEATURES' || draftType === 'feature_generation') {
        await get().generateFeatures(false);
      } else if (code === 'GENERATE_SCENARIOS' || draftType === 'scenario_generation') {
        let featureIds: any = undefined;
        if (action.payload?.feature_id) {
          featureIds = [action.payload.feature_id];
        } else if (action.payload?.feature_ids) {
          featureIds = action.payload.feature_ids;
        } else if (context.target && (context.target.type === 'feature' || context.target.targetType === 'feature')) {
          const id = context.target.id || context.target.targetId;
          if (id) {
            featureIds = [parseInt(id.toString(), 10)];
          }
        }
        await get().generateScenarios(featureIds, false);
      } else if (code === 'GENERATE_ACCEPTANCE_CRITERIA' || draftType === 'acceptance_criteria_generation') {
        let scenarioIds: any = undefined;
        if (action.payload?.scenario_ids) {
          scenarioIds = action.payload.scenario_ids;
        }
        await get().generateAcceptanceCriteria(scenarioIds, false);
      } else if (code === 'GENERATE_FLOWS_AND_BUSINESS_OBJECTS' || draftType === 'flow_generation' || draftType === 'flows_and_business_objects_generation') {
        await get().generateFlowsAndObjects(false);
      } else if (code === 'GENERATE_SCOPE' || draftType === 'scope_generation') {
        await get().generateScope(false);
      }
    } else if (kind === 'navigate') {
      const route = action.route || '';
      let page: any = null;
      if (route.endsWith('/what') || route === 'what' || route.endsWith('/projects/what')) {
        page = '/what';
      } else if (
        route.endsWith('/how') ||
        route.endsWith('/flow') ||
        route === 'how' ||
        route === 'flow' ||
        route.endsWith('/projects/how') ||
        route.endsWith('/projects/flow')
      ) {
        page = '/flow';
      } else if (route.endsWith('/scope') || route === 'scope' || route.endsWith('/projects/scope')) {
        page = '/scope';
      } else if (route.endsWith('/preview') || route === 'preview' || route.endsWith('/projects/preview')) {
        page = '/preview';
      }

      if (page) {
        get().setActivePage(page);
      }
    } else if (kind === 'wait') {
      set({ lastActionMessage: '后台分析正在运行，请稍后刷新或重新诊断。' });
      await get().refreshWorkspace();
    } else if (kind === 'retry') {
      const stage = context.stage || 'what';
      const projectId = get().ir?.projectId;
      if (projectId) {
        await workspaceApi.rediagnoseNextSuggestion(projectId, stage);
        await get().runDiagnosis(stage);
      }
    } else if (kind === 'open_panel') {
      const panel = action.panel;
      const payload = action.payload || {};
      let found = false;

      if (panel === 'perception_slot') {
        const jobId = payload.perception_job_id || payload.perceptionJobId;
        if (jobId) {
          await get().expandSlot(jobId.toString());
          found = true;
        }
      } else if (panel === 'feature') {
        const featId = (payload.feature_id || payload.featureId)?.toString();
        if (featId) {
          const featObj = get().ir?.features?.find((f: any) => f.featureId.toString() === featId);
          if (featObj) {
            get().setSelectedObject({ ...featObj, kind: 'feature' });
            found = true;
          }
        }
      } else if (panel === 'actor') {
        const actorId = (payload.actor_id || payload.actorId)?.toString();
        if (actorId) {
          const actObj = get().ir?.actors?.find((a: any) => a.actorId.toString() === actorId);
          if (actObj) {
            get().setSelectedObject({ ...actObj, kind: 'actor' });
            found = true;
          }
        }
      } else if (panel === 'scenario') {
        const scenarioId = (payload.scenario_id || payload.scenarioId)?.toString();
        if (scenarioId) {
          let scenarioObj: any = null;
          get().ir?.features?.forEach((f: any) => {
            const s = f.scenarios?.find((sc: any) => sc.scenarioId.toString() === scenarioId);
            if (s) scenarioObj = s;
          });
          if (scenarioObj) {
            get().setSelectedObject({ ...scenarioObj, kind: 'scenario' });
            found = true;
          }
        }
      } else if (panel === 'flow' || panel === 'flow_editor') {
        const flowId = (payload.flow_id || payload.flowId)?.toString();
        if (flowId) {
          const flowObj = get().ir?.flows?.find((fl: any) => fl.flowId.toString() === flowId);
          if (flowObj) {
            get().setSelectedObject({ ...flowObj, kind: 'flow' });
            found = true;
          }
        }
        if (!found) {
          // Navigate to How page as fallback
          get().setActivePage('/flow');
          found = true;
        }
      } else if (panel === 'business_object') {
        const boId = (payload.business_object_id || payload.businessObjectId)?.toString();
        if (boId) {
          const boObj = get().ir?.businessObjects?.find((bo: any) => bo.businessObjectId.toString() === boId);
          if (boObj) {
            get().setSelectedObject({ ...boObj, kind: 'business_object' });
            found = true;
          }
        }
      } else if (panel === 'scope') {
        const featId = (payload.feature_id || payload.featureId || payload.scopeId || payload.scope_id)?.toString();
        if (featId) {
          const featObj = get().ir?.features?.find((f: any) => f.featureId.toString() === featId);
          if (featObj) {
            get().setSelectedObject({ ...featObj, kind: 'scope' });
            found = true;
          }
        }
      }

      if (!found) {
        // Fallback: Check action.route
        let routed = false;
        if (action.route) {
          const route = action.route;
          let page: any = null;
          if (route.endsWith('/what') || route === 'what' || route.endsWith('/projects/what')) page = '/what';
          else if (
            route.endsWith('/how') ||
            route.endsWith('/flow') ||
            route === 'how' ||
            route === 'flow' ||
            route.endsWith('/projects/how') ||
            route.endsWith('/projects/flow')
          )
            page = '/flow';
          else if (route.endsWith('/scope') || route === 'scope' || route.endsWith('/projects/scope')) page = '/scope';
          else if (route.endsWith('/preview') || route === 'preview' || route.endsWith('/projects/preview')) page = '/preview';

          if (page) {
            get().setActivePage(page);
            routed = true;
            set({ lastActionMessage: `无法定位目标对象，已导航到对应页面：${page}` });
          }
        }
        if (!routed) {
          set({ lastActionMessage: '无法定位目标对象，请重新诊断或手动定位。' });
        }
      }
    }
  };

  const executeIssueResolution = async (res: any, issue: any, version: number) => {
    const type = resolutionType(res);

    if (type === 'already_resolved') {
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ isLoading: false, lastActionMessage: '该问题已解决。' });
      return;
    }

    if (type === 'open_panel') {
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      if (res.action) {
        await executeProcessorAction(res.action, { stage: issue.stage, target: issue.target }, version);
      }
      set({ isLoading: false, lastActionMessage: res.title || '已打开对应操作面板。', lastIssueResolution: res });
      return;
    }

    if (type === 'manual_action') {
      set({ isLoading: false, lastActionMessage: res.title || '请手动处理该问题。', lastIssueResolution: res });
      return;
    }

    if (type === 'unsupported') {
      set({ isLoading: false, lastActionMessage: res.title || '暂不支持自动修复。', lastIssueResolution: res });
      return;
    }

    if (type === 'repair_draft') {
      set({
        activeDraft: res.draft || res,
        activeDraftType: 'repair',
        lastActionMessage: `已生成修复建议：${res.title}`,
        isLoading: false
      });
      return;
    }

    if (type === 'choice_group') {
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ isLoading: false, lastActionMessage: '已加入方案决策队列，请选择处理方案。' });
      return;
    }

    // Default / standard path
    await get().refreshWorkspace();
    if (get().sessionVersion !== version) return;
    if (res.draftId || res.draft_id) {
      set({
        activeDraft: res.draft,
        activeDraftType: mapResolutionDraftType(res.action?.draftType || res.action?.draft_type),
        lastActionMessage: `已触发处理：${res.title}`
      });
    }
    set({ isLoading: false });
  };

  const syncChoiceGroupToWorkspace = (group: any, state: WorkspaceState) => {
    const compatible = mapBackendChoiceGroupToCompatible(group);
    const nextChoiceGroups = {
      ...state.backendChoiceGroups,
      [compatible.id]: compatible,
    };

    return {
      backendChoiceGroups: nextChoiceGroups,
      ir: state.ir,
      activeChoiceGroup: group,
    };
  };

  const removeChoiceGroupFromWorkspace = (groupId: string, state: WorkspaceState) => {
    const nextChoiceGroups = { ...state.backendChoiceGroups };
    delete nextChoiceGroups[groupId];
    return {
      backendChoiceGroups: nextChoiceGroups,
      ir: state.ir,
    };
  };

  return {
    sessionVersion: 0,
    currentSystemView: 'home',
  setSystemView: (view) => set({ currentSystemView: view, activePage: view === 'workspace' ? get().activePage : '/overview' }),
  initialPrompt: '',

  activePage: '/overview',
  setActivePage: (page) => set({ activePage: page }),

  selectedObjectId: null,
  selectedObject: null,
  setSelectedObject: (obj) => {
    if (!obj) {
      set({ selectedObjectId: null, selectedObject: null, selectedNodeId: null });
      return;
    }
    const id =
      (obj.kind === 'scope' ? (obj.scopeId || obj.id || obj.featureId) : undefined) ||
      obj.actorId ||
      obj.featureId ||
      obj.scenarioId ||
      obj.criterionId ||
      obj.businessObjectId ||
      obj.businessObjectAttributeId ||
      obj.flowId ||
      obj.stepId ||
      obj.id;
    set({
      selectedObjectId: id || null,
      selectedObject: obj,
      selectedNodeId: id || null
    });
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('workspace:selected-object', { detail: { id } }));
    }
  },

  selectedNodeId: null,
  selectedSlotId: null,
  highlightedNodeIds: [],

  ir: null,
  backendFindings: [],
  backendFindingsLoaded: false,
  findingsByView: {
    issues: [],
    next_action: [],
    gate: [],
    health: []
  },
  backendChoiceGroups: {},
  auditLogs: [],
  tasks: [],
  userTasks: [],
  confirmationSummary: null,
  lastImpactPreview: null,
  isDiagnosing: false,
  nextSuggestions: {},

  // Draft Generative States
  activeDraft: null,
  activeDraftType: null,
  isGenerating: false,

  // Phase 2: Choice Group Onboarding
  activeChoiceGroup: null,
  choiceGroupGenerationProgress: null,
  isGeneratingChoices: false,
  openOnboardingChoiceGroups: [],
  pendingGenerationConflict: null,
  activeStaleChoice: null,

  // Phase 3: Gate and Suggestion Convergence
  activeGateCheck: null,
  snoozedGateFindingIds: loadSnoozedGatesFromSession(),

  highlightTarget: null,
  setHighlightTarget: (id) => set({ highlightTarget: id }),
  pendingManualAction: null,
  setPendingManualAction: (action) => set({ pendingManualAction: action }),
  isLoading: false,
  error: null,
  setError: (err) => set({ error: err }),
  boDeletionError: null,
  setBoDeletionError: (err) => set({ boDeletionError: err }),
  lastActionMessage: null,
  lastIssueResolution: null,
  workspaces: [],

  loadWorkspaces: async () => {
    const version = get().sessionVersion;
    set({ isLoading: true, error: null });
    try {
      const workspaces = await workspaceApi.list();
      if (get().sessionVersion !== version) return;
      set({ workspaces, isLoading: false });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '加载工作区失败', isLoading: false });
    }
  },

  openExistingProject: async () => {
    const version = get().sessionVersion;
    set({ isLoading: true, error: null });
    try {
      const list = await workspaceApi.list();
      if (get().sessionVersion !== version) return;
      if (list.length > 0) {
        const space = await workspaceApi.getById(list[0].id);
        if (get().sessionVersion !== version) return;
        const projectId = space.projectId;

        let choiceGroupsRecord: Record<string, ChoiceGroup> = {};

        const findingsData = await loadBackendFindingsAndViews(projectId);
        if (get().sessionVersion !== version) return;
        try {
          const groups = await workspaceApi.listChoiceGroups(projectId, 'open');
          if (get().sessionVersion !== version) return;
          groups.forEach((cg: any) => {
            const compatible = mapBackendChoiceGroupToCompatible(cg);
            choiceGroupsRecord[compatible.id] = compatible;
          });
        } catch (cgErr) {
          console.warn('Failed to load choice groups in openExistingProject:', cgErr);
        }
        await get().loadAuditLogs(projectId);
        if (get().sessionVersion !== version) return;

        set({
          currentSystemView: 'workspace',
          activePage: '/overview',
          initialPrompt: space.userRequirements,
          ...findingsData,
          backendFindingsLoaded: true,
          backendChoiceGroups: choiceGroupsRecord,
          ir: space,
          selectedObject: null,
          selectedObjectId: null,
          selectedNodeId: null,
          selectedSlotId: null,
          highlightTarget: null,
          pendingManualAction: null,
          isLoading: false
        });
      } else {
        set({ currentSystemView: 'onboarding', isLoading: false });
      }
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '鎵撳紑宸叉湁椤圭洰澶辫触', isLoading: false });
    }
  },

  openWorkspace: async (workspaceId) => {
    const version = get().sessionVersion;
    set({ isLoading: true, error: null });
    try {
      const space = await workspaceApi.getById(workspaceId);
      if (get().sessionVersion !== version) return;
      const projectId = space.projectId;
      
      let choiceGroupsRecord: Record<string, ChoiceGroup> = {};
      
        const findingsData = await loadBackendFindingsAndViews(projectId);
        if (get().sessionVersion !== version) return;
        try {
          const groups = await workspaceApi.listChoiceGroups(projectId, 'open');
          if (get().sessionVersion !== version) return;
          groups.forEach((cg: any) => {
            const compatible = mapBackendChoiceGroupToCompatible(cg);
            choiceGroupsRecord[compatible.id] = compatible;
          });
        } catch (cgErr) {
          console.warn('Failed to load choice groups:', cgErr);
        }
        await get().loadAuditLogs(projectId);
        if (get().sessionVersion !== version) return;

        set({
          currentSystemView: 'workspace',
          activePage: '/overview',
          initialPrompt: space.userRequirements,
          ...findingsData,
          backendFindingsLoaded: true,
          backendChoiceGroups: choiceGroupsRecord,
          ir: space,
          selectedObject: null,
          selectedObjectId: null,
          selectedNodeId: null,
          selectedSlotId: null,
          highlightTarget: null,
          pendingManualAction: null,
          isLoading: false
        });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '打开工作区失败', isLoading: false });
    }
  },

  refreshWorkspace: async () => {
    const version = get().sessionVersion;
    const id = get().ir?.projectId;
    if (!id) return;
    try {
      const space = await workspaceApi.getById(id);
      if (get().sessionVersion !== version) return;
      
      let choiceGroupsRecord: Record<string, ChoiceGroup> = {};
      
      const findingsData = await loadBackendFindingsAndViews(id);
      if (get().sessionVersion !== version) return;
      try {
        const groups = await workspaceApi.listChoiceGroups(id, 'open');
        if (get().sessionVersion !== version) return;
        groups.forEach((cg: any) => {
          const compatible = mapBackendChoiceGroupToCompatible(cg);
          choiceGroupsRecord[compatible.id] = compatible;
        });
      } catch (cgErr) {
        console.warn('Failed to load choice groups in refresh:', cgErr);
      }
      await get().loadAuditLogs(id);
      if (get().sessionVersion !== version) return;

      set((s) => ({
        ...findingsData,
        backendFindingsLoaded: true,
        backendChoiceGroups: choiceGroupsRecord,
        ir: space,
        selectedObject: findSelectedObjectInIr(space, s.selectedObjectId, s.selectedObject)
      }));
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '鍚屾鏁版嵁澶辫触' });
    }
  },

  unlockStageGate: async (stage: string) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.unlockStage(projectId, stage);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ isLoading: false });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '瑙ｉ攣闃舵澶辫触', isLoading: false });
    }
  },

  triggerGateCheck: async (action: string, onPass: () => void, onCancel?: () => void) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) {
      onPass();
      return;
    }
    set({ isLoading: true, error: null });
    try {
      const res = await workspaceApi.listFindings(projectId, { view: 'gate', action });
      const findings = Array.isArray(res) ? res : (res?.findings || []);
      if (get().sessionVersion !== version) return;
      set({ isLoading: false });

      const snoozed = get().snoozedGateFindingIds || {};
      const activeFindings = findings.filter((finding: Finding) => {
        const key = `${projectId}:${action}:${finding.findingId}`;
        const storedHash = snoozed[key];
        if (!storedHash) return true;
        const currentHash = getGateFindingContextHash(finding);
        return storedHash !== currentHash;
      });

      if (activeFindings.length > 0) {
        set({
          activeGateCheck: {
            action,
            findings: activeFindings,
            onPass: () => {
              set({ activeGateCheck: null });
              onPass();
            },
            onCancel: () => {
              set({ activeGateCheck: null });
              if (onCancel) onCancel();
            }
          }
        });
      } else {
        onPass();
      }
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '检查门禁失败', isLoading: false });
    }
  },

  snoozeGateFinding: (action: string, finding: Finding) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    const hash = getGateFindingContextHash(finding);
    const key = `${projectId}:${action}:${finding.findingId}`;
    const nextSnoozed = {
      ...get().snoozedGateFindingIds,
      [key]: hash,
    };
    set({ snoozedGateFindingIds: nextSnoozed });
    if (typeof window !== 'undefined') {
      try {
        sessionStorage.setItem('rs_workbench_snoozed_gates', JSON.stringify(nextSnoozed));
      } catch (e) {
        console.error('Failed to save snoozed gates to sessionStorage', e);
      }
    }
  },

  startFindingSuggestion: async (finding: Finding) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;

    const presentation = getNextSuggestionPresentation(finding);
    const isGlobalLoading = presentation.icon === 'generate' || presentation.icon === 'retry';

    set({
      isLoading: true,
      error: null,
      ...(isGlobalLoading ? { isGenerating: true, lastActionMessage: presentation.loadingLabel } : {})
    });
    try {
      const target =
        finding.metadata?.target ||
        (finding.target
          ? {
              type: finding.target.targetType || finding.target.type,
              id: finding.target.targetId || finding.target.id,
              parentType: finding.target.parentType,
              parentId: finding.target.parentId,
            }
          : null);

      const action = finding.metadata?.action;
      if (action) {
        await executeProcessorAction(action, { stage: finding.stage, findingCode: finding.code, target }, version);
      } else {
        throw new Error(`涓嬩竴姝ュ缓璁€?{finding.code}銆嶇己灏戝彲鎵ц action`);
      }
      set({ isLoading: false, isGenerating: false });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '鍚姩寤鸿澶辫触', isLoading: false, isGenerating: false });
    }
  },

/** Build a target from aggregate gate metadata for the resolve API. */

  executeGateFindingAction: async (finding: Finding) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;

    set({ isLoading: true, error: null });
    try {
      // Gate aggregate findings lack individual targets. Build one from
      // metadata so the backend IssueRepairService can dispatch correctly.
      const gateTarget = buildAggregateTarget(finding);

      const res = await workspaceApi.resolveIssue(projectId, {
        issue_id: finding.findingId,
        issue_code: finding.code,
        stage: finding.stage,
        target: gateTarget,
        metadata: finding.metadata || {}
      });
      if (get().sessionVersion !== version) return;

      // Pass the finding directly as the context for executeIssueResolution
      await executeIssueResolution(res, finding, version);

      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const msg = err instanceof Error ? err.message : '自动处理缺陷失败';
      set({ error: msg, isLoading: false });
      throw err;
    }
  },

  exitWorkspace: () => {
    set((state: any) => ({
      sessionVersion: state.sessionVersion + 1,
      currentSystemView: 'home',
      activePage: '/overview',
      ir: null,
      selectedObject: null,
      selectedObjectId: null,
      selectedNodeId: null,
      selectedSlotId: null,
      highlightedNodeIds: [],
      highlightTarget: null,
      pendingManualAction: null,
      activeDraft: null,
      activeDraftType: null,
      isGenerating: false,
      isGeneratingChoices: false,
      generatingChoiceGroupType: null,
      choiceGroupGenerationProgress: null,
      activeGateCheck: null,
      pendingGenerationConflict: null,
      activeChoiceGroup: null,
      activeStaleChoice: null,
      activeShadowDraft: null,
      backendFindings: [],
      backendFindingsLoaded: false,
      findingsByView: { issues: [], next_action: [], gate: [], health: [] },
      backendChoiceGroups: {},
      isDiagnosing: false,
      nextSuggestions: {},
      auditLogs: [],
      error: null,
      boDeletionError: null,
      lastActionMessage: null,
      lastIssueResolution: null,
      lastImpactPreview: null,
      isLoading: false
    }));
  },

  updateProject: async (projectId: string, name: string, description: string) => {
    const version = get().sessionVersion;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.updateProject(projectId, { name, description });
      if (get().sessionVersion !== version) return;
      await get().loadWorkspaces();
      if (get().sessionVersion !== version) return;
      if (get().ir && get().ir?.projectId === projectId) {
        // If we are currently in this workspace, refresh it to show updated details
        await get().refreshWorkspace();
        if (get().sessionVersion !== version) return;
      }
      set({ isLoading: false, lastActionMessage: '项目基本信息更新成功。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '鏇存柊椤圭洰澶辫触', isLoading: false });
    }
  },

  deleteProject: async (projectId: string) => {
    const version = get().sessionVersion;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.delete(projectId);
      if (get().sessionVersion !== version) return;
      await get().loadWorkspaces();
      if (get().sessionVersion !== version) return;
      if (get().ir && get().ir?.projectId === projectId) {
        // If we are currently in this deleted workspace, exit it
        get().exitWorkspace();
      }
      set({ isLoading: false, lastActionMessage: '项目已成功删除。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '鍒犻櫎椤圭洰澶辫触', isLoading: false });
    }
  },

  loadAuditLogs: async (projectId) => {
    const version = get().sessionVersion;
    try {
      const logs = await workspaceApi.listAuditLogs(projectId);
      if (get().sessionVersion !== version) return;
      const mapped = (logs || []).map((log: any) => ({
        id: (log.id || 1).toString(),
        timestamp: log.createdAt || log.created_at || new Date().toISOString(),
        actionType: log.actionType || log.action_type || '搴旂敤鍙樻洿',
        summary: log.summary || '搴旂敤寤烘ā鍙樻洿',
        targetIds: log.targetId || log.target_id ? [log.targetId || log.target_id] : [],
        actorUserId: log.actorUserId !== undefined ? log.actorUserId : log.actor_user_id,
        actorType: log.actorType !== undefined ? log.actorType : (log.actor_type || 'system'),
        actorEmail: log.actorEmail !== undefined ? log.actorEmail : log.actor_email,
        diff: log.diff !== undefined ? log.diff : null,
        requestId: log.requestId !== undefined ? log.requestId : log.request_id,
        taskId: log.taskId !== undefined ? log.taskId : log.task_id
      }));
      set({ auditLogs: mapped });
    } catch (err) {
      console.warn('Failed to load audit logs:', err);
    }
  },

  getImpactPreview: async (featureId, nextStatus) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return null;
    try {
      const res = await workspaceApi.impactPreview(projectId, featureId, nextStatus);
      if (get().sessionVersion !== version) return null;
      set({ lastImpactPreview: res });
      return res;
    } catch (err) {
      console.warn('Failed to preview impact:', err);
      return null;
    }
  },

  // Onboarding On-demand Creation
  startAIOnboarding: async (prompt, name, description) => {
    const version = get().sessionVersion;
    set({ isGenerating: true, error: null, lastActionMessage: 'AI 姝ｅ湪鐢熸垚椤圭洰鍒濆鑽夌锛岃绋嶅€?..' });
    try {
      const draft = await workspaceApi.createProjectCreationDraft({
        user_requirements: prompt,
        project_name: name,
        project_description: description
      });
      if (get().sessionVersion !== version) return;
      set({
        activeDraft: draft,
        activeDraftType: 'project',
        isGenerating: false,
        currentSystemView: 'onboarding'
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '鐢熸垚鑽夌澶辫触', isGenerating: false });
    }
  },

  confirmAIOnboarding: async () => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isLoading: true, error: null });
    try {
      const res = await workspaceApi.confirmProjectCreationDraft(draft.draft_id);
      if (get().sessionVersion !== version) return;
      const space = await workspaceApi.getById(res.project_id);
      if (get().sessionVersion !== version) return;
      set({
        ir: space,
        activeDraft: null,
        activeDraftType: null,
        currentSystemView: 'workspace',
        activePage: '/overview',
        selectedObject: null,
        selectedObjectId: null,
        selectedNodeId: null,
        selectedSlotId: null,
        highlightTarget: null,
        pendingManualAction: null,
        isLoading: false,
        lastActionMessage: '项目 AI 建模框架已确认，祝您建模愉快！'
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '纭鑽夌澶辫触';
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: '草稿已失效，请重新生成项目草稿。', isLoading: false });
      } else {
        set({ error: errMsg, isLoading: false });
      }
    }
  },

  regenerateAIOnboarding: async (feedback) => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isGenerating: true, error: null, lastActionMessage: 'AI 姝ｅ湪鏍规嵁鎮ㄧ殑鎰忚閲嶆柊鐢熸垚椤圭洰鑽夌锛岃绋嶅€?..' });
    try {
      const updated = await workspaceApi.regenerateProjectCreationDraft(draft.draft_id, feedback);
      if (get().sessionVersion !== version) return;
      set({ activeDraft: updated, isGenerating: false, lastActionMessage: '已根据意见重新生成项目草稿。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '閲嶆柊鐢熸垚澶辫触';
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: '鑽夌宸插け鏁堬紝璇烽噸鏂伴厤缃苟鐢熸垚', isGenerating: false });
      } else {
        set({ error: errMsg, isGenerating: false });
      }
    }
  },

  discardAIOnboarding: async () => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    try {
      await workspaceApi.discardProjectCreationDraft(draft.draft_id);
      if (get().sessionVersion !== version) return;
      set({ activeDraft: null, activeDraftType: null, currentSystemView: 'home' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '鑸嶅純鑽夌澶辫触' });
    }
  },

  // 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲
  // Phase 2: Choice Group Onboarding Actions
  // 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲

  createOnboardingChoiceGroup: async (userRequirements, candidateCount) => {
    const version = get().sessionVersion;
    set({
      isGeneratingChoices: true,
      error: null,
      lastActionMessage: 'AI 正在为您生成多套项目方案...',
      choiceGroupGenerationProgress: null,
    });
    try {
      // Simulate progress polling while the backend generates
      const group = await workspaceApi.createProjectCreationChoiceGroup({
        user_requirements: userRequirements,
        candidate_count: candidateCount || 2,
      });
      if (get().sessionVersion !== version) return;
      set({
        activeChoiceGroup: group,
        isGeneratingChoices: false,
        choiceGroupGenerationProgress: null,
        activeDraft: null,
        activeDraftType: null,
        lastActionMessage: group.status === 'failed'
          ? '方案生成失败，请重试'
          : `已生成 ${group.successCount || 0} 套完整项目方案`,
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({
        error: err instanceof Error ? err.message : '生成项目方案失败',
        isGeneratingChoices: false,
        choiceGroupGenerationProgress: null,
      });
    }
  },

  acceptOnboardingChoice: async (choiceId) => {
    const version = get().sessionVersion;
    const group = get().activeChoiceGroup;
    if (!group) return;
    set({ isLoading: true, error: null });
    try {
      const res = await workspaceApi.acceptProjectCreationChoice(group.id, choiceId);
      if (get().sessionVersion !== version) return;
      const projectId = res.projectId ?? res.project_id;
      if (!projectId) {
        throw new Error('project_id_missing');
      }
      const space = await workspaceApi.getById(projectId);
      if (get().sessionVersion !== version) return;
      set({
        ir: space,
        activeChoiceGroup: null,
        activeDraft: null,
        activeDraftType: null,
        currentSystemView: 'workspace',
        activePage: '/overview',
        selectedObject: null,
        selectedObjectId: null,
        selectedNodeId: null,
        isLoading: false,
        lastActionMessage: '项目已创建，祝您建模愉快！',
      });
      // Reload open groups since this one is resolved
      get().loadOpenOnboardingChoiceGroups();
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '閲囩撼鏂规澶辫触', isLoading: false });
    }
  },

  discardOnboardingChoiceGroup: async () => {
    const version = get().sessionVersion;
    const group = get().activeChoiceGroup;
    if (!group) {
      set({ activeChoiceGroup: null });
      return;
    }
    try {
      await workspaceApi.discardProjectCreationChoiceGroup(group.id);
      if (get().sessionVersion !== version) return;
    } catch (err) {
      console.warn('Failed to discard onboarding choice group on backend:', err);
    } finally {
      if (get().sessionVersion === version) {
        set({
          activeChoiceGroup: null,
          isGeneratingChoices: false,
          generatingChoiceGroupType: null,
          currentSystemView: 'onboarding',
          lastActionMessage: '宸插叧闂€欓€夋柟妗堝苟杩斿洖鍒涘缓椤甸潰',
        });
        void get().loadOpenOnboardingChoiceGroups();
      }
    }
  },

  deferOnboardingChoiceGroup: async () => {
    const version = get().sessionVersion;
    const group = get().activeChoiceGroup;
    if (!group) return null;
    set({ isLoading: true, error: null });
    try {
      const res = await workspaceApi.deferProjectCreationChoiceGroup(group.id);
      if (get().sessionVersion !== version) return null;
      const projectId = res.projectId ?? res.project_id;
      if (!projectId) {
        throw new Error('project_id_missing');
      }
      await get().openWorkspace(String(projectId));
      if (get().sessionVersion !== version) return null;
      set({
        activeChoiceGroup: null,
        isLoading: false,
        lastActionMessage: '已创建空白项目，并保留待采纳的项目草稿方案。',
      });
      void get().loadOpenOnboardingChoiceGroups();
      return String(projectId);
    } catch (err) {
      if (get().sessionVersion !== version) return null;
      set({
        error: err instanceof Error ? err.message : '绋嶅悗澶勭悊澶辫触',
        isLoading: false,
      });
      return null;
    }
  },

  loadOpenOnboardingChoiceGroups: async () => {
    const version = get().sessionVersion;
    try {
      const groups = await workspaceApi.listOpenProjectCreationChoiceGroups();
      if (get().sessionVersion !== version) return;
      set({ openOnboardingChoiceGroups: groups });
    } catch {
      // Silently fail 鈥?this is a background refresh
    }
  },

  recoverOnboardingChoiceGroup: async (groupId) => {
    const version = get().sessionVersion;
    try {
      const group = await workspaceApi.getProjectCreationChoiceGroup(groupId);
      if (get().sessionVersion !== version) return;
      if (group && group.status === 'open') {
        set({ activeChoiceGroup: group, currentSystemView: 'onboarding' });
      }
    } catch {
      if (get().sessionVersion !== version) return;
      set({ error: '无法恢复项目草稿，它可能已失效。' });
    }
  },

  dismissPendingGenerationConflict: () => {
    set({ pendingGenerationConflict: null });
  },

  confirmPendingGenerationConflict: async () => {
    const conflict = get().pendingGenerationConflict;
    if (!conflict) return;

    set({ pendingGenerationConflict: null });

    if (conflict.action === 'generateActors') {
      await get().generateActors(true);
      return;
    }
    if (conflict.action === 'generateFeatures') {
      await get().generateFeatures(true);
      return;
    }
    if (conflict.action === 'generateFlowsAndObjects') {
      await get().generateFlowsAndObjects(true);
      return;
    }
    if (conflict.action === 'generateScope') {
      await get().generateScope(true);
      return;
    }
    if (conflict.action === 'generateScenarios') {
      await get().generateScenarios(conflict.featureIds, true);
      return;
    }
    if (conflict.action === 'generateAcceptanceCriteria') {
      await get().generateAcceptanceCriteria(conflict.scenarioIds, true);
    }
  },

  // Phase 3: In-project Generation Choice Group
  createGenerationChoiceGroup: async (params) => {
    const {
      projectId,
      generationType,
      target,
      candidateCount,
      userFeedback,
      forceReplace,
      conflictAction,
      conflictArgs,
    } = params;
    if (import.meta.env.VITE_GENERATION_CHOICE_GROUP_ENABLED === 'false') {
      set({ isGeneratingChoices: false, isGenerating: false });
      throw new Error('choice_group_disabled');
    }

    const conflictingGroup = findConflictingChoiceGroup(get().backendChoiceGroups, generationType, target);
    if (conflictingGroup && !forceReplace && !userFeedback) {
      set({
        activeChoiceGroup: conflictingGroup,
        activeDraft: null,
        activeDraftType: null,
        pendingGenerationConflict: null,
        choiceGroupGenerationProgress: null,
        error: null,
        isGeneratingChoices: false,
        isGenerating: false,
        lastActionMessage: `已打开现有${getGenerationTypeLabel(generationType)}候选方案，可继续选择或重新生成。`,
      });
      return conflictingGroup;
    }

    if (conflictingGroup && !forceReplace && userFeedback) {
      set({
        pendingGenerationConflict: {
          action: conflictAction || 'generateFeatures',
          generationType: generationType as PendingGenerationConflict['generationType'],
          existingGroupId: conflictingGroup.id,
          existingGroupLabel: getGenerationTypeLabel(generationType),
          ...(conflictArgs || {}),
        } as PendingGenerationConflict,
        error: null,
      });
      throw new Error(GENERATION_CONFLICT_PENDING_ERROR);
    }

    const version = get().sessionVersion;
    set({
      isGeneratingChoices: true,
      error: null,
      choiceGroupGenerationProgress: buildInitialChoiceProgress(candidateCount),
      lastActionMessage: `正在生成 ${generationType} 候选方案...`,
    });

    try {
      if (conflictingGroup && forceReplace) {
        await workspaceApi.discardChoiceGroup(projectId, Number(conflictingGroup.id));
        if (get().sessionVersion !== version) return null;
        set((state) => ({
          ...removeChoiceGroupFromWorkspace(conflictingGroup.id, state),
          pendingGenerationConflict: null,
          activeChoiceGroup:
            state.activeChoiceGroup && String(state.activeChoiceGroup.id) === conflictingGroup.id
              ? null
          : state.activeChoiceGroup,
        }));
      }

      const group = await workspaceApi.createGenerationChoiceGroup({
        project_id: projectId,
        generation_type: generationType,
        target: target || null,
        candidate_count: candidateCount || 2,
        user_feedback: userFeedback || null,
      });
      if (get().sessionVersion !== version) return null;
      set((state) => ({
        ...syncChoiceGroupToWorkspace(group, state),
        isGeneratingChoices: false,
        activeDraft: null,
        activeDraftType: null,
        pendingGenerationConflict: null,
        choiceGroupGenerationProgress: null,
        lastActionMessage: `已生成 ${group.successCount || group.success_count || 0} 套候选方案`,
      }));
      return group;
    } catch (err) {
      if (get().sessionVersion !== version) return null;
      if (err instanceof Error && err.message === GENERATION_CONFLICT_PENDING_ERROR) {
        set({ isGeneratingChoices: false, choiceGroupGenerationProgress: null });
        return null;
      }
      set({
        error: err instanceof Error ? err.message : '生成候选方案失败',
        isGeneratingChoices: false,
        choiceGroupGenerationProgress: null,
      });
      return null;
    }
  },

  createBlankWorkspace: async (name, description, prompt) => {
    const version = get().sessionVersion;
    set({ isLoading: true, error: null });
    try {
      const res = await workspaceApi.createBlankProject({
        user_requirements: prompt,
        project_name: name,
        project_description: description
      });
      if (get().sessionVersion !== version) return;
      const projectId = res.projectId ?? res.project_id;
      if (!projectId) {
        throw new Error('project_id_missing');
      }
      const space = await workspaceApi.getById(projectId);
      if (get().sessionVersion !== version) return;
      set({
        ir: space,
        currentSystemView: 'workspace',
        activePage: '/overview',
        selectedObject: null,
        selectedObjectId: null,
        selectedNodeId: null,
        selectedSlotId: null,
        highlightTarget: null,
        pendingManualAction: null,
        isLoading: false,
        lastActionMessage: '已初始化空白工作区，开始您的敏捷设计吧！'
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '鍒涘缓绌虹櫧椤圭洰澶辫触', isLoading: false });
    }
  },

  // AI Generators per phase
  generateActors: async (forceReplace = false) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      const group = await get().createGenerationChoiceGroup({
        projectId: pId,
        generationType: 'actor',
        candidateCount: 2,
        forceReplace,
        conflictAction: 'generateActors',
      });
      if (get().sessionVersion !== version) return;
      if (group || get().pendingGenerationConflict) return;
    } catch (_err) {
      if (get().sessionVersion !== version) return;
      if (get().pendingGenerationConflict) return;
    }
    try {
      // Fallback: old single-draft flow
      const draft = await workspaceApi.createActorGenerationDraft(pId);
      if (get().sessionVersion !== version) return;
      set({ activeDraft: draft, activeDraftType: 'actor', isGeneratingChoices: false, isGenerating: false, lastActionMessage: '角色列表已生成。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '鐢熸垚瑙掕壊澶辫触';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
    }
  },

  regenerateActors: async (feedback) => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isGenerating: true, error: null, lastActionMessage: '姝ｅ湪鏍规嵁鎰忚璋冩暣閲嶆瀯瑙掕壊鍒楄〃锛岃绋嶅€?..' });
    try {
      let updated;
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        updated = await workspaceApi.regenerateSlotFillingDraft(draftId, feedback);
      } else {
        updated = await workspaceApi.regenerateActorGenerationDraft(draftId, feedback);
      }
      if (get().sessionVersion !== version) return;
      set({ activeDraft: updated, isGenerating: false, lastActionMessage: '已根据意见重新生成角色草稿。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '閲嶆柊鐢熸垚瑙掕壊鑽夌澶辫触';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      } else {
        set({ error: errMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmActors: async () => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isLoading: true, error: null, lastActionMessage: '馃捑 姝ｅ湪纭閲囩撼 AI 鎺ㄨ崘瑙掕壊骞跺悎鍏ユ暟鎹簱锛岃绋嶅€?..' });
    try {
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        await workspaceApi.confirmSlotFillingDraft(draftId);
      } else {
        await workspaceApi.confirmActorGenerationDraft(draftId);
      }
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: '已合并 AI 生成的角色列表。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '纭瑙掕壊澶辫触';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessage: friendlyMsg, isLoading: false });
      } else {
        set({ error: errMsg, lastActionMessage: friendlyMsg, isLoading: false });
      }
    }
  },

  generateFeatures: async (forceReplace = false) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      const group = await get().createGenerationChoiceGroup({
        projectId: pId,
        generationType: 'feature',
        candidateCount: 2,
        forceReplace,
        conflictAction: 'generateFeatures',
      });
      if (get().sessionVersion !== version) return;
      if (group || get().pendingGenerationConflict) return;
    } catch (_err) {
      if (get().sessionVersion !== version) return;
      if (get().pendingGenerationConflict) return;
    }
    try {
      const draft = await workspaceApi.createFeatureGenerationDraft(pId);
      if (get().sessionVersion !== version) return;
      set({ activeDraft: draft, activeDraftType: 'feature', isGenerating: false, isGeneratingChoices: false,
        lastActionMessage: '核心功能架构树已生成。',
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '生成功能树失败';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
    }
  },

  regenerateFeatures: async (feedback) => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isGenerating: true, error: null, lastActionMessage: '姝ｅ湪鏍规嵁鎰忚閲嶆柊璋冩暣鍔熻兘鍒嗚В鏍戯紝璇风◢鍊?..' });
    try {
      let updated;
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        updated = await workspaceApi.regenerateSlotFillingDraft(draftId, feedback);
      } else {
        updated = await workspaceApi.regenerateFeatureGenerationDraft(draftId, feedback);
      }
      if (get().sessionVersion !== version) return;
      set({ activeDraft: updated, isGenerating: false, lastActionMessage: '已根据意见重新生成功能草稿。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '閲嶆柊鐢熸垚鍔熻兘鑽夌澶辫触';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      } else {
        set({ error: errMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmFeatures: async () => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isLoading: true, error: null, lastActionMessage: '馃捑 姝ｅ湪纭閲囩撼鍔熻兘鏋舵瀯鍒嗚В骞跺悎鍏ユ寮忓姛鑳界壒寰佹爲锛岃绋嶅€?..' });
    try {
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        await workspaceApi.confirmSlotFillingDraft(draftId);
      } else {
        await workspaceApi.confirmFeatureGenerationDraft(draftId);
      }
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: '已将功能叶子节点合并到功能树。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '纭鍔熻兘澶辫触';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessage: friendlyMsg, isLoading: false });
      } else {
        set({ error: errMsg, lastActionMessage: friendlyMsg, isLoading: false });
      }
    }
  },

  generateFlowsAndObjects: async (forceReplace = false) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      const group = await get().createGenerationChoiceGroup({
        projectId: pId,
        generationType: 'flow',
        candidateCount: 2,
        forceReplace,
        conflictAction: 'generateFlowsAndObjects',
      });
      if (get().sessionVersion !== version) return;
      if (group || get().pendingGenerationConflict) return;
    } catch (_err) {
      if (get().sessionVersion !== version) return;
      if (get().pendingGenerationConflict) return;
    }
    try {
      const draft = await workspaceApi.createFlowGenerationDraft(pId);
      if (get().sessionVersion !== version) return;
      set({ activeDraft: draft, activeDraftType: 'flow', isGenerating: false, isGeneratingChoices: false,
        lastActionMessage: '核心泳道步骤与核心数据对象已生成。',
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '鐢熸垚娴佺▼澶辫触';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
    }
  },

  regenerateFlowsAndObjects: async (feedback) => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isGenerating: true, error: null, lastActionMessage: '姝ｅ湪鏍规嵁鎰忚閲嶆柊鎺ㄦ紨娴佺▼涓庝笟鍔″璞★紝璇风◢鍊?..' });
    try {
      const updated = isSlotFillingDraft(draft)
        ? await workspaceApi.regenerateSlotFillingDraft(draftId, feedback)
        : await workspaceApi.regenerateFlowGenerationDraft(draftId, feedback);
      if (get().sessionVersion !== version) return;
      set({ activeDraft: updated, activeDraftType: 'flow', isGenerating: false, lastActionMessage: '已根据意见重新生成流程与业务对象草稿。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '閲嶆柊鐢熸垚娴佺▼澶辫触';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      } else {
        set({ error: errMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmFlowsAndObjects: async () => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft) return;
    const draftId = draft.draftId || draft.draft_id;
    if (!draftId) return;
    set({ isLoading: true, error: null, lastActionMessage: '馃捑 姝ｅ湪纭閲囩撼娴佺▼涓庝笟鍔″璞¤崏绋匡紝璇风◢鍊?..' });
    try {
      if (isSlotFillingDraft(draft)) {
        await workspaceApi.confirmSlotFillingDraft(draftId);
      } else {
        await workspaceApi.confirmFlowGenerationDraft(draftId);
      }
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: '业务流程与业务对象已应用。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '纭娴佺▼澶辫触';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessage: friendlyMsg, isLoading: false });
      } else {
        set({ error: errMsg, lastActionMessage: friendlyMsg, isLoading: false });
      }
    }
  },

  generateScenarios: async (featureIds, forceReplace = false) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    const isSingleTarget = !Array.isArray(featureIds) ||
      (Array.isArray(featureIds) && featureIds.length === 1);
    const targetFeatureId = isSingleTarget
      ? (Array.isArray(featureIds) ? featureIds[0] : featureIds)
      : null;
    const targetFeatureIds = Array.isArray(featureIds) ? featureIds : (featureIds ? [featureIds] : []);

    try {
      const group = await get().createGenerationChoiceGroup({
        projectId: pId,
        generationType: 'scenario',
        target: isSingleTarget
          ? { generation_mode: 'single', feature_id: targetFeatureId }
          : { generation_mode: 'batch', feature_ids: targetFeatureIds },
        candidateCount: 2,
        forceReplace,
        conflictAction: 'generateScenarios',
        conflictArgs: { featureIds },
      });
      if (get().sessionVersion !== version) return;
      if (group || get().pendingGenerationConflict) return;
    } catch (_err) {
      if (get().sessionVersion !== version) return;
      if (get().pendingGenerationConflict) return;
      // Fall through to draft fallback
    }

    // 鈹€鈹€ Fallback / full / batch: old draft path 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    set({ isGenerating: true, error: null, lastActionMessage: '正在生成场景草稿，请稍候...' });
    try {
      if (Array.isArray(featureIds)) {
        if (featureIds.length === 0) {
          const draft = await workspaceApi.createScenarioGenerationDraft(pId);
          if (get().sessionVersion !== version) return;
          set({ activeDraft: draft, activeDraftType: 'scenario', isGenerating: false, lastActionMessage: '场景草稿生成成功，已在上方提供完整场景列表。' });
        } else if (featureIds.length === 1) {
          const draft = await workspaceApi.createScenarioGenerationDraft(pId, featureIds[0]);
          if (get().sessionVersion !== version) return;
          set({ activeDraft: draft, activeDraftType: 'scenario', isGenerating: false, lastActionMessage: '场景草稿生成成功，已在上方提供完整场景列表。' });
        } else {
          const drafts = await Promise.all(
            featureIds.map(fId => workspaceApi.createScenarioGenerationDraft(pId, fId))
          );
          if (get().sessionVersion !== version) return;
          const combinedScenarios = drafts.flatMap(d => d.scenarios || []);
          const draftIds = drafts.map(d => d.draftId || d.draft_id);
          const combinedDraft = {
            project_id: pId,
            generation_mode: 'batch',
            draftIds,
            scenarios: combinedScenarios,
            draft_id: draftIds[0],
          };
          set({ activeDraft: combinedDraft, activeDraftType: 'scenario', isGenerating: false, lastActionMessage: `场景草稿生成成功，针对选定的 ${featureIds.length} 个功能模块共生成了 ${combinedScenarios.length} 个场景，已在上方提供预览。` });
        }
      } else {
        const draft = await workspaceApi.createScenarioGenerationDraft(pId, featureIds);
        if (get().sessionVersion !== version) return;
        set({ activeDraft: draft, activeDraftType: 'scenario', isGenerating: false, lastActionMessage: '场景草稿生成成功，已在上方提供完整场景列表。' });
      }
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '生成场景失败';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
    }
  },

  regenerateScenarios: async (feedback) => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isGenerating: true, error: null, lastActionMessage: '正在根据反馈重新生成场景详情，请稍候...' });
    try {
      let updated;
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        updated = await workspaceApi.regenerateSlotFillingDraft(draftId, feedback);
      } else {
        updated = await workspaceApi.regenerateScenarioGenerationDraft(draftId, feedback);
      }
      if (get().sessionVersion !== version) return;
      set({ activeDraft: updated, isGenerating: false, lastActionMessage: '已根据意见重新生成成功场景草稿。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '閲嶆柊鐢熸垚鍦烘櫙澶辫触';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      } else {
        set({ error: errMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmScenarios: async (generateAc) => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft) return;
    set({ isLoading: true, error: null, lastActionMessage: '馃捑 姝ｅ湪纭閲囩撼鎴愬姛鍦烘櫙璁捐骞舵寮忚惤搴擄紝璇风◢鍊?..' });
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
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: '成功场景与关联验收标准已应用。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '纭鍦烘櫙澶辫触';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessage: friendlyMsg, isLoading: false });
      } else {
        set({ error: errMsg, lastActionMessage: friendlyMsg, isLoading: false });
      }
    }
  },

  generateAcceptanceCriteria: async (scenarioIds, forceReplace = false) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    const isSingleTarget = Array.isArray(scenarioIds) && scenarioIds.length === 1;
    if (isSingleTarget) {
      try {
        const group = await get().createGenerationChoiceGroup({
          projectId: pId,
          generationType: 'acceptance_criteria',
          target: { generation_mode: 'single', scenario_ids: scenarioIds },
          candidateCount: 2,
          forceReplace,
          conflictAction: 'generateAcceptanceCriteria',
          conflictArgs: { scenarioIds },
        });
        if (get().sessionVersion !== version) return;
        if (group || get().pendingGenerationConflict) return;
      } catch (_err) {
        if (get().sessionVersion !== version) return;
        if (get().pendingGenerationConflict) return;
        /* fall through */
      }
    }
    try {
      const draft = await workspaceApi.createAcceptanceCriteriaGenerationDraft(pId, scenarioIds);
      if (get().sessionVersion !== version) return;
      set({ activeDraft: draft, activeDraftType: 'ac', isGenerating: false, isGeneratingChoices: false,
        lastActionMessage: '成功标准 (AC) 已生成。',
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '鐢熸垚楠屾敹鏍囧噯澶辫触';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
    }
  },

  regenerateAcceptanceCriteria: async (feedback) => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isGenerating: true, error: null, lastActionMessage: '姝ｅ湪鏍规嵁璋冩暣鎰忚閲嶆柊婕旂粌浼樺寲鎴愬姛鏍囧噯 (AC) 妫€鏌ラ」锛岃绋嶅€?..' });
    try {
      let updated;
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        updated = await workspaceApi.regenerateSlotFillingDraft(draftId, feedback);
      } else {
        updated = await workspaceApi.regenerateAcceptanceCriteriaGenerationDraft(draftId, feedback);
      }
      if (get().sessionVersion !== version) return;
      set({ activeDraft: updated, isGenerating: false, lastActionMessage: '已根据意见重新生成验收标准草稿。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '閲嶆柊鐢熸垚楠屾敹鏍囧噯澶辫触';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      } else {
        set({ error: errMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmAcceptanceCriteria: async () => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isLoading: true, error: null, lastActionMessage: '馃捑 姝ｅ湪纭閲囩撼楠屾敹鏉′欢 (AC) 骞舵寮忓叧鑱旇惤搴擄紝璇风◢鍊?..' });
    try {
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        await workspaceApi.confirmSlotFillingDraft(draftId);
      } else {
        await workspaceApi.confirmAcceptanceCriteriaGenerationDraft(draftId);
      }
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: '成功标准已补充并落库。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '纭澶辫触';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessage: friendlyMsg, isLoading: false });
      } else {
        set({ error: errMsg, lastActionMessage: friendlyMsg, isLoading: false });
      }
    }
  },

  generateScope: async (forceReplace = false) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      const group = await get().createGenerationChoiceGroup({
        projectId: pId,
        generationType: 'scope',
        candidateCount: 2,
        forceReplace,
        conflictAction: 'generateScope',
      });
      if (get().sessionVersion !== version) return;
      if (group || get().pendingGenerationConflict) return;
    } catch (_err) {
      if (get().sessionVersion !== version) return;
      if (get().pendingGenerationConflict) return;
    }
    try {
      const draft = await workspaceApi.createScopeGenerationDraft(pId);
      if (get().sessionVersion !== version) return;
      set({ activeDraft: draft, activeDraftType: 'scope', isGenerating: false, isGeneratingChoices: false,
        lastActionMessage: 'Kano 范围与发布优先级分析已成功。',
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '鐢熸垚鑼冨洿鍒嗘瀽澶辫触';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
    }
  },

  regenerateScope: async (feedback) => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isGenerating: true, error: null, lastActionMessage: '姝ｅ湪鏍规嵁鎰忚閲嶆柊璇勪及鍔熻兘鍗＄墖浼樺厛绾т笌 Kano 褰掑睘锛岃绋嶅€?..' });
    try {
      const updated = await workspaceApi.regenerateScopeGenerationDraft(draft.draft_id, feedback);
      if (get().sessionVersion !== version) return;
      set({ activeDraft: updated, isGenerating: false, lastActionMessage: '已根据意见重新生成范围分析草稿。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '閲嶆柊鐢熸垚鑼冨洿鍒嗘瀽澶辫触';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      } else {
        set({ error: errMsg, lastActionMessage: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmScope: async () => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isLoading: true, error: null, lastActionMessage: '馃捑 姝ｅ湪纭閲囩撼鍙戝竷璁″垝瀹夋帓骞惰惤搴撲繚瀛橈紝璇风◢鍊?..' });
    try {
      await workspaceApi.confirmScopeGenerationDraft(draft.draft_id);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessage: 'Kano 功能发布计划与正反方观点已确认。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '纭澶辫触';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessage: friendlyMsg, isLoading: false });
      } else {
        set({ error: errMsg, lastActionMessage: friendlyMsg, isLoading: false });
      }
    }
  },

  discardDraft: async () => {
    const version = get().sessionVersion;
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
      if (get().sessionVersion !== version) return;
      set({ activeDraft: null, activeDraftType: null, lastActionMessage: '已舍弃未保存的 AI 推荐草案。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '鍙栨秷鑽夌澶辫触' });
    }
  },

  skipKano: async () => {
    const version = get().sessionVersion;
    const ir = get().ir;
    if (!ir || !ir.projectId) return;
    set({ isLoading: true, error: null, lastActionMessage: '姝ｅ湪璺宠繃 Kano 鍒嗘瀽骞惰В閿佸鑸?..' });
    try {
      await workspaceApi.skipKano(ir.projectId);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ isLoading: false, lastActionMessage: '已跳过 Kano 分析，阶段导航已解锁。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '璺宠繃 Kano 鍒嗘瀽澶辫触';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      set({ error: errMsg, lastActionMessage: friendlyMsg, isLoading: false });
    }
  },

  resetKano: async () => {
    const version = get().sessionVersion;
    const ir = get().ir;
    if (!ir || !ir.projectId) return;
    set({ isLoading: true, error: null, lastActionMessage: '姝ｅ湪閲嶇疆 Kano 鍒嗘瀽锛屾竻鐞?AI 寤鸿...' });
    try {
      await workspaceApi.resetKano(ir.projectId);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ isLoading: false, lastActionMessage: 'Kano 分析已重置，手工交付决策已保留。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '閲嶇疆 Kano 鍒嗘瀽澶辫触';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      set({ error: errMsg, lastActionMessage: friendlyMsg, isLoading: false });
    }
  },

  // -------------------------------------------------------------
  // Manual CRUD Actions
  // -------------------------------------------------------------

  // Actors
  addActor: async (name, description) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.createActor(pId, { name, description });
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: `宸叉坊鍔犲弬涓庤€呰鑹诧細${name}` });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '添加参与者角色失败' });
    }
  },

  updateActor: async (actorId, updates) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    const actor = (get().ir?.actors || []).find((x: any) => x.actorId === actorId);
    try {
      await workspaceApi.updateActor(pId, actorId, {
        name: updates.actorName,
        description: updates.actorDescription,
        last_seen_updated_at: actor?.updatedAt
      });
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: '参与者角色属性更新成功。' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: '更新失败：检测到并行的冲突编辑。该参与者已被其他成员修改，请刷新页面以加载最新版本。' });
      } else {
        set({ error: err instanceof Error ? err.message : '更新参与者角色属性失败' });
      }
    }
  },

  deleteActor: async (actorId) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.deleteActor(pId, actorId);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set((s) => {
        const isSelected = s.selectedObjectId === actorId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessage: '参与者角色已被成功移除，对应功能绑定已解除。'
        };
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '删除参与者角色失败' });
    }
  },

  // Features Tree CRUD
  addFeature: async (name, description, parentId) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    let finalParentId = parentId;
    if (parentId === null) {
      const dbRoot = get().ir?.features?.find((f: any) => f.parentId === null);
      if (dbRoot) {
        finalParentId = dbRoot.featureId;
      }
    }
    try {
      await workspaceApi.createFeature(pId, {
        name,
        description,
        parent_id: finalParentId
      });
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: `宸插垱寤哄姛鑳借妭鐐癸細${name}` });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '鍒涘缓鍔熻兘鑺傜偣澶辫触' });
    }
  },

  updateFeature: async (featureId, updates) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    const original = get().ir?.features?.find((f: any) => f.featureId === featureId);
    try {
      await workspaceApi.updateFeature(pId, featureId, {
        name: updates.featureName !== undefined ? updates.featureName : original?.featureName,
        description: updates.featureDescription !== undefined ? updates.featureDescription : original?.featureDescription,
        actor_ids: updates.actorIds !== undefined ? updates.actorIds : original?.actorIds,
        last_seen_updated_at: original?.updatedAt
      });
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: '功能节点属性更新成功。' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: '更新失败：检测到并行的冲突编辑。该功能节点已被其他成员修改，请刷新页面以加载最新版本。' });
      } else {
        set({ error: err instanceof Error ? err.message : '更新功能节点属性失败' });
      }
    }
  },

  deleteFeature: async (featureId) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.deleteFeature(pId, featureId);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set((s) => {
        const isSelected = s.selectedObjectId === featureId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessage: '选定功能节点及其子分支已全部移除。'
        };
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '鍒犻櫎鍔熻兘鑺傜偣澶辫触' });
    }
  },

  // Scenarios CRUD
  addScenario: async (featureId, actorId, name, content) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.createScenario(pId, {
        feature_id: featureId,
        actor_id: actorId,
        name,
        content
      });
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: `宸蹭负鍔熻兘娣诲姞鏂板満鏅細${name}` });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '娣诲姞鍦烘櫙澶辫触' });
    }
  },

  updateScenario: async (featureId, scenarioId, updates) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    let originalScenario: any = null;
    for (const f of (get().ir?.features || [])) {
      const found = (f.scenarios || []).find((s: any) => s.scenarioId === scenarioId);
      if (found) {
        originalScenario = found;
        break;
      }
    }
    try {
      await workspaceApi.updateScenario(pId, scenarioId, {
        name: updates.scenarioName,
        content: updates.scenarioContent,
        last_seen_updated_at: originalScenario?.updatedAt
      });
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: '成功场景已更新。' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: '更新失败：检测到并行的冲突编辑。该场景/用户故事已被其他成员修改，请刷新页面以加载最新版本。' });
      } else {
        set({ error: err instanceof Error ? err.message : '鏇存柊鍦烘櫙澶辫触' });
      }
    }
  },

  deleteScenario: async (featureId, scenarioId) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.deleteScenario(pId, scenarioId);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set((s) => {
        const isSelected = s.selectedObjectId === scenarioId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessage: '场景已删除。'
        };
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '鍒犻櫎鍦烘櫙澶辫触' });
    }
  },

  // Acceptance Criteria CRUD
  addAcceptanceCriterion: async (featureId, scenarioId, content) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.createAcceptanceCriterion(pId, scenarioId, { content });
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: '成功验收标准添加成功！' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '娣诲姞楠屾敹鏍囧噯澶辫触' });
    }
  },

  updateAcceptanceCriterion: async (featureId, scenarioId, criterionId, content) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    let originalAc: any = null;
    for (const f of (get().ir?.features || [])) {
      for (const s of (f.scenarios || [])) {
        const found = (s.acceptanceCriteria || []).find((a: any) => a.criterionId === criterionId);
        if (found) {
          originalAc = found;
          break;
        }
      }
    }
    try {
      await workspaceApi.updateAcceptanceCriterion(pId, scenarioId, criterionId, {
        content,
        last_seen_updated_at: originalAc?.updatedAt
      });
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: '验收标准已修改。' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: '更新失败：检测到并行的冲突编辑。该验收标准已被其他成员修改，请刷新页面以加载最新版本。' });
      } else {
        set({ error: err instanceof Error ? err.message : '鏇存柊楠屾敹鏍囧噯澶辫触' });
      }
    }
  },

  deleteAcceptanceCriterion: async (featureId, scenarioId, criterionId) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.deleteAcceptanceCriterion(pId, scenarioId, criterionId);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set((s) => {
        const isSelected = s.selectedObjectId === criterionId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessage: '验收标准已删除。'
        };
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '鍒犻櫎楠屾敹鏍囧噯澶辫触' });
    }
  },

  // Business Objects CRUD
  addBusinessObject: async (name, description) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.createBusinessObject(pId, { name, description });
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: `宸插垱寤轰笟鍔″璞★細${name}` });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '鍒涘缓涓氬姟瀵硅薄澶辫触' });
    }
  },

  updateBusinessObject: async (id, name, description) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    const bo = (get().ir?.businessObjects || []).find((x: any) => x.businessObjectId === id);
    try {
      await workspaceApi.updateBusinessObject(pId, id, {
        name,
        description,
        last_seen_updated_at: bo?.updatedAt
      });
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: '业务对象定义已更新。' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: '更新失败：检测到并行的冲突编辑。该业务对象已被其他成员修改，请刷新页面以加载最新版本。' });
      } else {
        set({ error: err instanceof Error ? err.message : '鏇存柊涓氬姟瀵硅薄瀹氫箟澶辫触' });
      }
    }
  },

  deleteBusinessObject: async (id) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    const ir = get().ir;
    const flows = ir?.flows || [];
    const isReferenced = flows.some(flow =>
      (flow.flowSteps || []).some(step =>
        (step.inputBusinessObjectIds || []).includes(id) ||
        (step.outputBusinessObjectIds || []).includes(id)
      )
    );
    if (isReferenced) {
      set({ boDeletionError: '无法删除该数据实体：某些流程步骤正在将其作为输入或输出实体引用。请先取消关联。' });
      return;
    }

    try {
      await workspaceApi.deleteBusinessObject(pId, id);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set((s) => {
        const isSelected = s.selectedObjectId === id;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessage: '业务数据对象已被完全移除。',
          boDeletionError: null
        };
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '';
      if (errMsg.includes('business_object_in_use')) {
        set({ boDeletionError: '无法删除该数据实体：该数据实体正被某些流程步骤作为输入或输出对象引用。请先取消关联后再删除。' });
      } else {
        set({ error: errMsg || '鍒犻櫎涓氬姟鏁版嵁瀵硅薄澶辫触' });
      }
    }
  },

  addBusinessObjectAttribute: async (boId, name, description, type, example) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.createBusinessObjectAttribute(pId, boId, {
        name,
        description,
        data_type: type,
        example
      });
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: `宸蹭负瀵硅薄娣诲姞瀛楁灞炴€э細${name}` });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '添加字段属性失败' });
    }
  },

  updateBusinessObjectAttribute: async (boId, attrId, updates) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    let originalAttr: any = null;
    for (const bo of (get().ir?.businessObjects || [])) {
      const found = (bo.businessObjectAttributes || []).find((a: any) => a.businessObjectAttributeId === attrId);
      if (found) {
        originalAttr = found;
        break;
      }
    }
    try {
      await workspaceApi.updateBusinessObjectAttribute(pId, boId, attrId, {
        name: updates.businessObjectAttributeName,
        description: updates.businessObjectAttributeDescription,
        data_type: updates.businessObjectAttributeType,
        example: updates.businessObjectAttributeExample,
        last_seen_updated_at: originalAttr?.updatedAt
      });
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: '字段属性详情修改完毕。' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: '更新失败：检测到并行的冲突编辑。该字段属性已被其他成员修改，请刷新页面以加载最新版本。' });
      } else {
        set({ error: err instanceof Error ? err.message : '更新字段属性详情失败' });
      }
    }
  },

  deleteBusinessObjectAttribute: async (boId, attrId) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.deleteBusinessObjectAttribute(pId, boId, attrId);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set((s) => {
        const isSelected = s.selectedObjectId === attrId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessage: '已移除字段属性。'
        };
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '移除字段属性失败' });
    }
  },

  // Flows CRUD
  addFlow: async (name, description, featureIds) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.createFlow(pId, {
        name,
        description,
        feature_ids: featureIds
      });
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: `宸茬粍寤轰笟鍔℃祦绋嬶細${name}` });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '缁勫缓涓氬姟娴佺▼澶辫触' });
    }
  },

  updateFlow: async (flowId, updates) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    const flow = (get().ir?.flows || []).find((x: any) => x.flowId === flowId);
    try {
      await workspaceApi.updateFlow(pId, flowId, {
        name: updates.flowName,
        description: updates.flowDescription,
        feature_ids: updates.featureIds,
        last_seen_updated_at: flow?.updatedAt
      });
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: '流程信息已更新。' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: '更新失败：检测到并行的冲突编辑。该流程已被其他成员修改，请刷新页面以加载最新版本。' });
      } else {
        set({ error: err instanceof Error ? err.message : '鏇存柊娴佺▼淇℃伅澶辫触' });
      }
    }
  },

  deleteFlow: async (flowId) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.deleteFlow(pId, flowId);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set((s) => {
        const isSelected = s.selectedObjectId === flowId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessage: '流程已删除。'
        };
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '鍒犻櫎娴佺▼澶辫触' });
    }
  },

  addFlowStep: async (flowId, step) => {
    const version = get().sessionVersion;
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
      if (get().sessionVersion !== version) return;

      // 2. Sequential binding for nextStepIds from previous step
      const flow = get().ir?.flows.find(f => f.flowId === flowId);
      if (flow && flow.flowSteps.length > 0) {
        const prevStep = flow.flowSteps[flow.flowSteps.length - 1];
        const newStepId = newStep.step_id || newStep.stepId;
        await workspaceApi.updateFlowStep(pId, flowId, prevStep.stepId, {
          next_step_ids: [newStepId]
        });
        if (get().sessionVersion !== version) return;
      }

      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: `流程步骤 "${step.stepName}" 已载入。` });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '杞藉叆娴佺▼姝ラ澶辫触' });
    }
  },

  updateFlowStep: async (flowId, stepId, updates) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    let originalStep: any = null;
    for (const flow of (get().ir?.flows || [])) {
      const found = (flow.flowSteps || []).find((s: any) => s.stepId === stepId);
      if (found) {
        originalStep = found;
        break;
      }
    }
    try {
      await workspaceApi.updateFlowStep(pId, flowId, stepId, {
        name: updates.stepName,
        description: updates.stepDescription,
        step_type: updates.stepType,
        actor_ids: updates.actorIds,
        input_business_object_ids: updates.inputBusinessObjectIds,
        output_business_object_ids: updates.outputBusinessObjectIds,
        next_step_ids: updates.nextStepIds,
        last_seen_updated_at: originalStep?.updatedAt
      });
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: '流程步骤细项修改成功。' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: '更新失败：检测到并行的冲突编辑。该流程步骤已被其他成员修改，请刷新页面以加载最新版本。' });
      } else {
        set({ error: err instanceof Error ? err.message : '淇敼娴佺▼姝ラ缁嗛」澶辫触' });
      }
    }
  },

  deleteFlowStep: async (flowId, stepId) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.deleteFlowStep(pId, flowId, stepId);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set((s) => {
        const isSelected = s.selectedObjectId === stepId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessage: '选定步骤已移除，拓扑链路已完成自动流转适配。'
        };
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '绉婚櫎姝ラ澶辫触' });
    }
  },

  reorderFlowSteps: async (flowId, stepIds) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.reorderFlowSteps(pId, flowId, stepIds);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: '线性步骤排序及拓扑链路同步成功。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '閲嶆柊鎺掑垪姝ラ椤哄簭澶辫触' });
    }
  },

  // Scope (Kano) CRUD
  updateScope: async (featureId, updates) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    const feature = (get().ir?.features || []).find((x: any) => x.featureId === featureId);
    try {
      await workspaceApi.updateScope(pId, featureId, {
        status: updates.scopeStatus,
        reason: updates.reason,
        positive_summary: updates.positiveSummary,
        negative_summary: updates.negativeSummary,
        last_seen_updated_at: feature?.scope?.updatedAt
      });
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessage: '功能优先级发布范围及理由更新成功。' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: '更新失败：检测到并行的冲突编辑。该范围划分已被其他成员修改，请刷新页面以加载最新版本。' });
      } else {
        set({ error: err instanceof Error ? err.message : '鏇存柊鍔熻兘浼樺厛绾у彂甯冭寖鍥村強鐞嗙敱澶辫触' });
      }
    }
  },

  // PerceptionSlot
  clearPerceptionSlot: async () => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.deletePerceptionSlot(projectId);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set((s) => ({
        isLoading: false,
        selectedSlotId: null,
        selectedObjectId:
          s.selectedObject?.kind === 'perception_slot' || s.selectedObject?.perceptionSlotId
            ? null
            : s.selectedObjectId,
        selectedObject:
          s.selectedObject?.kind === 'perception_slot' || s.selectedObject?.perceptionSlotId
            ? null
            : s.selectedObject,
        lastActionMessage: '已忽略并删除当前待处理卡点。'
      }));
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '删除待处理卡点失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      set({ error: errMsg, lastActionMessage: friendlyMsg, isLoading: false });
    }
  },

  openSlot: (slotId) => {
    const numId = parseInt(slotId, 10);
    const space = get().ir;
    if (space?.perceptionSlot?.perceptionSlotId === numId) {
      set({ selectedSlotId: numId, selectedObject: space.perceptionSlot, selectedObjectId: numId });
    }
  },
  expandSlot: async (slotId) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    const numId = parseInt(slotId, 10);
    const slot = get().ir?.perceptionSlot;
    if (!slot || slot.perceptionSlotId !== numId) return;

    set({ isGenerating: true, error: null, lastActionMessage: 'AI 姝ｅ湪灞曞紑鎰熺煡妲藉苟鐢熸垚琛ュ叏鑽夌锛岃绋嶅€?..' });
    try {
      let fillerKind: 'actor' | 'feature' | 'flow' | 'scenario' | 'ac' | null = null;
      const kindText = slot.perceptionKind ? slot.perceptionKind.toUpperCase() : '';
      if (kindText === '瑙掕壊缁撶偣' || kindText === 'ACTOR') fillerKind = 'actor';
      else if (kindText === '鍔熻兘妯″潡缁撶偣' || kindText === '鍔熻兘鍙跺瓙缁撶偣' || kindText === 'FEATURE') fillerKind = 'feature';
      else if (kindText === '流程主节点' || kindText === 'FLOW') fillerKind = 'flow';
      else if (kindText === '鍦烘櫙缁撶偣' || kindText === 'SCENARIO') fillerKind = 'scenario';
      else if (kindText === '鎴愬姛鏍囧噯缁撶偣' || kindText === 'ACCEPTANCE_CRITERION' || kindText === 'AC' || kindText === 'ac') fillerKind = 'ac';

      if (!fillerKind) {
        throw new Error('未知的感知类型，无法展开。');
      }

      const draft = await workspaceApi.createSlotFillingDraft(projectId, numId, fillerKind);
      if (get().sessionVersion !== version) return;
      set({
        activeDraft: draft,
        activeDraftType: fillerKind,
        isGenerating: false,
        lastActionMessage: 'AI 感知槽开始填充，生成草稿预览。'
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({
        error: err instanceof Error ? err.message : '槽填充生成失败',
        isGenerating: false
      });
    }
  },
  acceptChoice: async (choiceId, force) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    const choiceIdNum = parseInt(choiceId, 10);
    if (isNaN(choiceIdNum)) return;
    set({ isLoading: true, error: null });
    try {
      const result = await workspaceApi.acceptChoice(projectId, choiceIdNum, force || false);
      if (get().sessionVersion !== version) return;
      // Handle stale response (UX-5)
      if (result?.is_stale) {
        set({ activeStaleChoice: { projectId, choiceId: choiceIdNum, staleReason: result.stale_reason }, isLoading: false });
        return;
      }
      // Accept succeeded → refresh workspace & close modal
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({
        activeChoiceGroup: null,
        activeStaleChoice: null,
        selectedObject: null,
        selectedObjectId: null,
        isLoading: false,
        lastActionMessage: '已成功采纳并应用该设计决策提案。',
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '采纳决策失败', isLoading: false });
    }
  },
  regenerateChoiceGroup: async (groupId, feedback) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ isGeneratingChoices: true, error: null, lastActionMessage: '正在重新生成候选方案...' });
    try {
      const newGroup = await workspaceApi.regenerateChoiceGroup(projectId, groupId, feedback);
      if (get().sessionVersion !== version) return;
      set({ activeChoiceGroup: newGroup, isGeneratingChoices: false, activeDraft: null, activeDraftType: null,
        lastActionMessage: '已重新生成候选方案组',
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '重新生成失败', isGeneratingChoices: false });
    }
  },
  regenerateChoice: async (choiceId, feedback) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ isGeneratingChoices: true, error: null, lastActionMessage: '正在重新生成候选方案...' });
    try {
      const updatedGroup = await workspaceApi.regenerateChoice(projectId, choiceId, feedback);
      if (get().sessionVersion !== version) return;
      set({ activeChoiceGroup: updatedGroup, isGeneratingChoices: false,
        lastActionMessage: '已重新生成候选方案',
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '重新生成失败', isGeneratingChoices: false });
    }
  },
  clearStaleChoice: () => {
    set({ activeStaleChoice: null });
  },
  rejectChoice: async (choiceId) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    const choiceIdNum = parseInt(choiceId, 10);
    if (isNaN(choiceIdNum)) return;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.rejectChoice(projectId, choiceIdNum);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ selectedObject: null, selectedObjectId: null, isLoading: false, lastActionMessage: '已拒绝该设计决策提案。' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '鎷掔粷鍐崇瓥澶辫触', isLoading: false });
    }
  },

  discardChoiceGroup: async (groupId) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) {
      set({ activeChoiceGroup: null });
      return;
    }
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.discardChoiceGroup(projectId, groupId);
      if (get().sessionVersion !== version) return;
    } catch (err) {
      console.warn('Failed to discard choice group on backend:', err);
    } finally {
      if (get().sessionVersion === version) {
        set({ activeChoiceGroup: null, isLoading: false, lastActionMessage: '已丢弃候选方案组。' });
        await get().refreshWorkspace();
      }
    }
  },

  executeFindingIssueResolution: async (issueId) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return null;
    const issue = get().findingsByView.issues.find((finding) => finding.findingId === issueId);
    if (!issue) {
        set({ error: '找不到对应问题，请重新诊断后再试。', lastActionMessage: '找不到对应问题，请重新诊断后再试。', isLoading: false });
      return null;
    }

    set({ isLoading: true, error: null });
    try {
      const res = await workspaceApi.resolveIssue(projectId, {
        issue_id: issue.findingId,
        issue_code: issue.code,
        stage: issue.stage,
        target: issue.target || null,
        metadata: issue.metadata || {}
      });
      if (get().sessionVersion !== version) return null;

      await executeIssueResolution(res, issue, version);

      if (res.action?.payload?.perception_job_id) {
        return res.action.payload.perception_job_id.toString();
      }
      const slot = get().ir?.perceptionSlot;
      return slot ? slot.perceptionSlotId.toString() : null;
    } catch (err) {
      if (get().sessionVersion !== version) return null;
      const msg = (err as any)?.detail || (err instanceof Error ? err.message : '澶勭悊 Issue 澶辫触');
      set({ error: msg, lastActionMessage: msg, isLoading: false });
      return null;
    }
  },
  confirmRepairDraft: async (draftId) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ isLoading: true, error: null });
    try {
      const res: any = await workspaceApi.confirmRepairDraft(projectId, draftId);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      if (res && (res.status === 'stale' || res.status === 'invalid')) {
          const msg = res.status === 'stale' ? '修复草稿已过期，请重新生成。' : '修复草稿已失效，数据已变化。';
        set({ isLoading: false, lastActionMessage: msg, error: msg });
        return res;
      }
      set({
        isLoading: false,
        lastActionMessage: '修复已应用。',
        activeDraft: null,
        activeDraftType: null,
      });
      const rIds = res.resolvedIssueIds || res.resolved_issue_ids;
      if (res && rIds && rIds.length > 0) {
        set({ lastActionMessage: `已解决 ${rIds.length} 个问题。` });
      }
      return res;
    } catch (err) {
      if (get().sessionVersion !== version) return null;
      const msg = (err as any)?.response?.data?.detail || (err instanceof Error ? err.message : '搴旂敤淇澶辫触');
      set({ error: msg, lastActionMessage: msg, isLoading: false });
      return null;
    }
  },
  discardRepairDraft: async (draftId) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.discardRepairDraft(projectId, draftId);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ isLoading: false, lastActionMessage: '已丢弃修复草稿。', activeDraft: null, activeDraftType: null });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const msg = (err as any)?.response?.data?.detail || (err instanceof Error ? err.message : '涓㈠純淇澶辫触');
      set({ error: msg, lastActionMessage: msg, isLoading: false });
    }
  },
  regenerateRepairDraft: async (draftId) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ isLoading: true, error: null });
    try {
      const res = await workspaceApi.regenerateRepairDraft(projectId, draftId);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({
        isLoading: false,
        activeDraft: res,
        activeDraftType: 'repair',
        lastActionMessage: '已重新生成修复建议。',
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '閲嶆柊鐢熸垚淇澶辫触', isLoading: false });
    }
  },
  setNodeStatus: async (nodeId: string, nodeKind: string, status: NodeStatus) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    try {
      await workspaceApi.updateNodeConfirmationStatus(projectId, nodeKind, parseInt(nodeId, 10), status);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : '更新节点状态失败' });
    }
  },
  setScopeStatus: async (nodeId, scopeStatus) => {
    const featId = parseInt(nodeId, 10);
    if (!isNaN(featId)) {
      await get().updateScope(featId, { scopeStatus });
    }
  },
  runDiagnosis: async () => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    
    let stage = 'what';
    const activePage = get().activePage;
    if (activePage === '/flow') stage = 'how';
    else if (activePage === '/scope') stage = 'scope';
    else if (activePage === '/preview') stage = 'preview';

    set({ isDiagnosing: true, error: null });
    try {
      let res = await workspaceApi.rediagnoseNextSuggestion(projectId, stage);
      if (get().sessionVersion !== version) return;
      set((s) => ({
        nextSuggestions: {
          ...s.nextSuggestions,
          [stage]: res.suggestion
        },
        lastActionMessage: `AI 智能分析中：${res.suggestion?.title || '正在分析中'}...`
      }));

      // If the suggestion is in 'running' state, poll until it's finished or failed
      if (res.suggestion && res.suggestion.status === 'running') {
        const maxAttempts = 15; // Max 30 seconds
        let attempts = 0;
        
        while (attempts < maxAttempts) {
          // Wait 2 seconds before polling again
          await new Promise((resolve) => setTimeout(resolve, 2000));
          if (get().sessionVersion !== version) return;
          
          // Poll next suggestion
          res = await workspaceApi.getNextSuggestion(projectId, stage);
          if (get().sessionVersion !== version) return;
          
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

      if (get().sessionVersion !== version) return;
      set({
        isDiagnosing: false,
        lastActionMessage: res.suggestion 
          ? `诊断完成！最新建议：${res.suggestion.title}`
          : '诊断完成！当前模块设计非常规范，暂无建议。'
      });
      await get().refreshWorkspace();
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({
        error: err instanceof Error ? err.message : '璇婃柇澶辫触',
        isDiagnosing: false
      });
    }
  },
  rewrite: async (scope, instruction) => {
    const version = get().sessionVersion;
    set({ isLoading: true, error: null });
    try {
      const projectId = withWorkspaceId(get());
      
      const res = await workspaceApi.refineUserRequirements(projectId, instruction);
      if (get().sessionVersion !== version) return;
      
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
        lastActionMessage: 'AI 智能自动建模成功：已根据您的建模指令精炼并更新了项目原始用户需求。您可在各 Tab 重新发起 AI 推演或补全草稿。'
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({
        isLoading: false,
        lastActionMessage: `鈿狅笍 寤烘ā澶辫触: ${err instanceof Error ? err.message : '鏈煡寮傚父'}`
      });
    }
  },
  explainImpact: async (scope, patch, choiceId) => {
    const version = get().sessionVersion;
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
          lastActionMessage: '链路联动分析目前支持针对“功能模块”进行分析，请在左侧或 What 页面选中一个功能模块节点。'
        });
        return;
      }

      const res = await workspaceApi.impactPreview(projectId, targetFeatureId, '鏆傜紦');
      if (get().sessionVersion !== version) return;
      
      const scenarioCount = res.affectedScenarios?.length || 0;
      const flowCount = res.affectedFlows?.length || 0;
      const boCount = res.affectedBusinessObjects?.length || 0;

      set({
        isLoading: false,
        lastActionMessage: `【${featureName}】变更影响评估：关联受影响场景 ${scenarioCount} 个，业务流 ${flowCount} 个，数据实体 ${boCount} 个。详细分析可在 Scope 页面进行决策评估。`
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({
        isLoading: false,
        lastActionMessage: `鈿狅笍 璇勪及澶辫触: ${err instanceof Error ? err.message : '鏈煡寮傚父'}`
      });
    }
  },
  updateNodeAttributes: async (nodeId, updates) => {
    const version = get().sessionVersion;
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
      if (get().sessionVersion !== version) return;
      return;
    }
    const feat = space.features.find(f => f.featureId === numId);
    if (feat) {
      await get().updateFeature(numId, {
        featureName: updates.title || feat.featureName,
        featureDescription: updates.description || feat.featureDescription
      });
      if (get().sessionVersion !== version) return;
      return;
    }
  },
  createIssue: async () => {},
  updateIssueAttributes: async (issueId, updates) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;

    if (projectId && updates?.status && ['open', 'ignored', 'resolved'].includes(updates.status)) {
      try {
        await workspaceApi.updateFindingStatus(projectId, issueId, updates.status);
        if (get().sessionVersion !== version) return;
      } catch (err) {
        if (get().sessionVersion !== version) return;
        set({
          error: err instanceof Error ? err.message : '更新 Finding 状态失败',
        });
        throw err;
      }
    }

    if (get().sessionVersion !== version) return;

    const currentFindings = get().backendFindings || [];
    const nextFindings = currentFindings.map((finding) =>
      finding.findingId === issueId ? { ...finding, ...updates } : finding
    );

    const nextFindingsByView = {
      issues: get().findingsByView.issues.map((f) => f.findingId === issueId ? { ...f, ...updates } : f),
      next_action: get().findingsByView.next_action.map((f) => f.findingId === issueId ? { ...f, ...updates } : f),
      gate: get().findingsByView.gate.map((f) => f.findingId === issueId ? { ...f, ...updates } : f),
      health: get().findingsByView.health.map((f) => f.findingId === issueId ? { ...f, ...updates } : f),
    };

    const currentSelectedObject = get().selectedObject;
    const nextSelectedObject =
      currentSelectedObject && (currentSelectedObject as any).id === issueId
        ? { ...(currentSelectedObject as any), ...updates }
        : currentSelectedObject;

    set({
      backendFindings: nextFindings,
      backendFindingsLoaded: get().backendFindingsLoaded,
      findingsByView: nextFindingsByView,
      ir: get().ir,
      selectedObject: nextSelectedObject,
      lastActionMessage:
        updates?.status === 'ignored'
          ? '已忽略该 Issue。'
          : updates?.status === 'resolved'
            ? '已更新该 Issue 状态。'
            : '已更新 Issue 属性。'
    });
  },
  updateChoiceAttributes: async () => {},
  addChoiceToGroup: async () => {},

  // P5 Shadow Preview Draft Actions
  activeShadowDraft: null,

  getActiveShadowDraft: async () => {
    const version = get().sessionVersion;
    const projectId = withWorkspaceId(get());
    try {
      const res = await workspaceApi.getActiveShadowDraft(projectId);
      if (get().sessionVersion !== version) return null;
      if (res && res.status !== 'idle') {
        set({ activeShadowDraft: res });
      } else {
        set({ activeShadowDraft: null });
      }
      return res;
    } catch (err) {
      if (get().sessionVersion !== version) return null;
      console.warn('Failed to fetch active shadow draft:', err);
      set({ activeShadowDraft: null });
      throw err;
    }
  },

  prepareShadowDraft: async () => {
    const version = get().sessionVersion;
    const projectId = withWorkspaceId(get());
    set({ isLoading: true });
    try {
      const res = await workspaceApi.prepareShadowDraft(projectId);
      if (get().sessionVersion !== version) return null;
      set({ activeShadowDraft: res, isLoading: false });
      return res;
    } catch (err) {
      if (get().sessionVersion !== version) return null;
      set({ isLoading: false });
      throw err;
    }
  },

  getShadowDraft: async (draftId: string) => {
    const version = get().sessionVersion;
    const projectId = withWorkspaceId(get());
    try {
      const res = await workspaceApi.getShadowDraft(projectId, draftId);
      if (get().sessionVersion !== version) return null;
      set({ activeShadowDraft: res });
      return res;
    } catch (err) {
      if (get().sessionVersion !== version) return null;
      console.warn('Failed to fetch shadow draft:', err);
      throw err;
    }
  },

  discardShadowDraft: async (draftId: string) => {
    const version = get().sessionVersion;
    const projectId = withWorkspaceId(get());
    set({ isLoading: true });
    try {
      await workspaceApi.discardShadowDraft(projectId, draftId);
      if (get().sessionVersion !== version) return;
      set({ activeShadowDraft: null, isLoading: false });
      await get().refreshWorkspace();
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ isLoading: false });
      throw err;
    }
  },

  commitShadowDraft: async (draftId: string) => {
    const version = get().sessionVersion;
    const projectId = withWorkspaceId(get());
    set({ isLoading: true });
    try {
      await workspaceApi.commitShadowDraft(projectId, draftId);
      if (get().sessionVersion !== version) return;
      set({ activeShadowDraft: null, isLoading: false });
      await get().refreshWorkspace();
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ isLoading: false });
      throw err;
    }
  },

  regenerateShadowDraft: async (draftId: string, feedback?: string) => {
    const version = get().sessionVersion;
    const projectId = withWorkspaceId(get());
    set({ isLoading: true });
    try {
      const res = await workspaceApi.regenerateShadowDraft(projectId, draftId, feedback);
      if (get().sessionVersion !== version) return null;
      set({ activeShadowDraft: res, isLoading: false });
      return res;
    } catch (err) {
      if (get().sessionVersion !== version) return null;
      set({ isLoading: false });
      throw err;
    }
  },

  loadProjectTasks: async (projectId: string, params?: any) => {
    const version = get().sessionVersion;
    try {
      const res = await workspaceApi.listProjectTasks(projectId, params);
      if (get().sessionVersion !== version) return;
      set({ tasks: res });
    } catch (err) {
      console.error('Failed to load project tasks:', err);
    }
  },

  loadMyTasks: async (params?: any) => {
    const version = get().sessionVersion;
    try {
      const res = await workspaceApi.listMyTasks(params);
      if (get().sessionVersion !== version) return;
      set({ userTasks: res });
    } catch (err) {
      console.error('Failed to load user tasks:', err);
    }
  },

  loadConfirmationSummary: async (projectId: string) => {
    const version = get().sessionVersion;
    try {
      const res = await workspaceApi.getProjectConfirmationSummary(projectId);
      if (get().sessionVersion !== version) return res;
      set({ confirmationSummary: res });
      return res;
    } catch (err) {
      console.error('Failed to load project confirmation summary:', err);
      throw err;
    }
  },

  createConfirmationTask: async (projectId: string, payload: any) => {
    const version = get().sessionVersion;
    set({ isLoading: true });
    try {
      const res = await workspaceApi.createConfirmationTask(projectId, payload);
      if (get().sessionVersion !== version) return res;
      set({ isLoading: false });
      await get().loadProjectTasks(projectId);
      await get().loadConfirmationSummary(projectId);
      await get().refreshWorkspace();
      return res;
    } catch (err) {
      if (get().sessionVersion !== version) throw err;
      set({ isLoading: false });
      throw err;
    }
  },

  createBatchConfirmTask: async (projectId: string, payload: any) => {
    const version = get().sessionVersion;
    set({ isLoading: true });
    try {
      const res = await workspaceApi.createBatchConfirmTask(projectId, payload);
      if (get().sessionVersion !== version) return res;
      set({ isLoading: false });
      await get().loadProjectTasks(projectId);
      await get().loadConfirmationSummary(projectId);
      await get().refreshWorkspace();
      return res;
    } catch (err) {
      if (get().sessionVersion !== version) throw err;
      set({ isLoading: false });
      throw err;
    }
  },

  decideTask: async (projectId: string, taskId: number, payload: any) => {
    const version = get().sessionVersion;
    set({ isLoading: true });
    try {
      const res = await workspaceApi.decideTask(projectId, taskId, payload);
      if (get().sessionVersion !== version) return res;
      set({ isLoading: false });
      await get().loadProjectTasks(projectId);
      await get().loadConfirmationSummary(projectId);
      await get().refreshWorkspace();
      return res;
    } catch (err) {
      if (get().sessionVersion !== version) throw err;
      set({ isLoading: false });
      throw err;
    }
  },

  cancelTask: async (projectId: string, taskId: number) => {
    const version = get().sessionVersion;
    set({ isLoading: true });
    try {
      const res = await workspaceApi.cancelTask(projectId, taskId);
      if (get().sessionVersion !== version) return res;
      set({ isLoading: false });
      await get().loadProjectTasks(projectId);
      await get().loadConfirmationSummary(projectId);
      await get().refreshWorkspace();
      return res;
    } catch (err) {
      if (get().sessionVersion !== version) throw err;
      set({ isLoading: false });
      throw err;
    }
  },
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
  return state.findingsByView.issues || emptyArray;
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
