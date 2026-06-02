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
  PendingManualAction,
} from '@/core/schema';
import { workspaceApi } from '@/lib/api';
import { buildPageHealth, detectIssues, detectStageIssues } from '@/core/selectors';

const getConfirmationStatus = (value: unknown): NodeStatus => {
  return value === 'confirmed' || value === 'needs_confirmation' || value === 'ai_assumption'
    ? value
    : 'ai_assumption';
};


export type WorkspacePage = '/what' | '/flow' | '/scope' | '/preview' | '/overview';



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
    suggestedProjection = 'data';
  }

  const relatedNodeIds: string[] = [];
  if (issue.target && issue.target.targetId) {
    relatedNodeIds.push(issue.target.targetId.toString());
  }

  return {
    id: issue.issueId || issue.id,
    title: issue.title,
    description: issue.description,
    severity: (
      issue.severity?.toLowerCase() === 'high' || issue.severity?.toLowerCase() === 'blocking'
        ? 'high'
        : issue.severity?.toLowerCase() === 'medium' || issue.severity?.toLowerCase() === 'warning'
        ? 'medium'
        : 'low'
    ) as any,
    status: 'open',
    relatedNodeIds,
    suggestedProjection,
    stage,
    domain: issue.domain || issue.metadata?.domain,
    category: issue.code,
    backendIssueCode: issue.code,
    backendTarget: issue.target,
    backendMetadata: issue.metadata
  };
};

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

const loadBackendIssues = async (projectId: number, unlockedStages?: string[]): Promise<Issue[]> => {
  const stages = getVisibleIssueStages(unlockedStages);
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
  backendIssues?: Issue[] | null,
  backendChoiceGroups?: Record<string, ChoiceGroup>,
  backendIssuesLoaded?: boolean
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
          title: '验收标准',
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
  const issuesList = backendIssuesLoaded && backendIssues
    ? backendIssues.filter((issue) => !issue.stage || visibleIssueStages.has(issue.stage as any))
    : getVisibleIssueStages(space.unlockedStages).flatMap((stage) => detectStageIssues(normalizedSpaceForRules, stage));
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
  backendIssuesLoaded: boolean;
  backendChoiceGroups: Record<string, ChoiceGroup>;
  isDiagnosing: boolean;
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
  updateProject: (projectId: number, name: string, description: string) => Promise<void>;
  deleteProject: (projectId: number) => Promise<void>;

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
  deferOnboardingChoiceGroup: () => Promise<number | null>;
  loadOpenOnboardingChoiceGroups: () => Promise<void>;
  recoverOnboardingChoiceGroup: (groupId: string) => Promise<void>;
  dismissPendingGenerationConflict: () => void;
  confirmPendingGenerationConflict: () => Promise<void>;

  // Phase 3: In-project Generation Choice Group (actor, scenario, etc.)
  createGenerationChoiceGroup: (params: {
    projectId: number;
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
  activeStaleChoice: { projectId: number; choiceId: number; staleReason: string } | null;
  clearStaleChoice: () => void;
  regenerateChoiceGroup: (groupId: number, feedback?: string) => Promise<void>;
  regenerateChoice: (choiceId: number, feedback?: string) => Promise<void>;
  createSlotFromIssue: (issueId: string) => Promise<string | null>;
  resolveIssue: (issueId: string) => Promise<string | null>;
  confirmRepairDraft: (draftId: string) => Promise<any>;
  discardRepairDraft: (draftId: string) => Promise<void>;
  regenerateRepairDraft: (draftId: string) => Promise<void>;
  setNodeStatus: (nodeId: string, nodeKind: string, status: NodeStatus) => Promise<void>;
  setScopeStatus: (nodeId: string, scopeStatus: ScopeStatus) => Promise<void>;
  runDiagnosis: (scope?: any) => Promise<void>;
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

  // P5 Shadow Preview Draft Actions
  activeShadowDraft: any | null;
  getActiveShadowDraft: () => Promise<any>;
  prepareShadowDraft: () => Promise<any>;
  getShadowDraft: (draftId: string) => Promise<any>;
  discardShadowDraft: (draftId: string) => Promise<void>;
  commitShadowDraft: (draftId: string) => Promise<void>;
  regenerateShadowDraft: (draftId: string, feedback?: string) => Promise<any>;
  unlockStageGate: (stage: string) => Promise<void>;
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
          const loadedToUse = next.backendIssuesLoaded !== undefined ? next.backendIssuesLoaded : state.backendIssuesLoaded;
          next.ir = normalizeRequirementSpace(next.ir, issuesToUse, choiceGroupsToUse, loadedToUse);
        }
        return next;
      }, replace);
    } else {
      if (update && 'ir' in update && update.ir !== undefined) {
        const issuesToUse = update.backendIssues || get()?.backendIssues || [];
        const choiceGroupsToUse = update.backendChoiceGroups || get()?.backendChoiceGroups || {};
        const loadedToUse = update.backendIssuesLoaded !== undefined ? update.backendIssuesLoaded : get()?.backendIssuesLoaded;
        update.ir = normalizeRequirementSpace(update.ir, issuesToUse, choiceGroupsToUse, loadedToUse);
      }
      (rawSet as any)(update, replace);
    }
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
  backendIssues: [],
  backendIssuesLoaded: false,
  backendChoiceGroups: {},
  auditLogs: [],
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
        const projectId = space.projectId;

        let issues: Issue[] = [];
        let choiceGroupsRecord: Record<string, ChoiceGroup> = {};

        issues = await loadBackendIssues(projectId, space.unlockedStages);
        try {
          const groups = await workspaceApi.listChoiceGroups(projectId, 'open');
          groups.forEach((cg: any) => {
            const compatible = mapBackendChoiceGroupToCompatible(cg);
            choiceGroupsRecord[compatible.id] = compatible;
          });
        } catch (cgErr) {
          console.warn('Failed to load choice groups in openExistingProject:', cgErr);
        }
        await get().loadAuditLogs(projectId);

        set({
          currentSystemView: 'workspace',
          activePage: '/overview',
          initialPrompt: space.userRequirements,
          backendIssues: issues,
          backendIssuesLoaded: true,
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
      
      issues = await loadBackendIssues(projectId, space.unlockedStages);
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
        activePage: '/overview',
        initialPrompt: space.userRequirements,
        backendIssues: issues,
        backendIssuesLoaded: true,
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
      
      issues = await loadBackendIssues(id, space.unlockedStages);
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
        backendIssuesLoaded: true,
        backendChoiceGroups: choiceGroupsRecord,
        ir: space,
        selectedObject: findSelectedObjectInIr(space, s.selectedObjectId, s.selectedObject)
      }));
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '同步数据失败' });
    }
  },

  unlockStageGate: async (stage: string) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.unlockStage(projectId, stage);
      await get().refreshWorkspace();
      set({ isLoading: false });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '解锁阶段失败', isLoading: false });
    }
  },

  exitWorkspace: () => {
    set({
      currentSystemView: 'home',
      activePage: '/overview',
      ir: null,
      selectedObject: null,
      selectedObjectId: null,
      selectedNodeId: null,
      selectedSlotId: null,
      highlightTarget: null,
      pendingManualAction: null,
      activeDraft: null,
      activeDraftType: null,
      backendIssues: [],
      backendIssuesLoaded: false,
      backendChoiceGroups: {},
      auditLogs: [],
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

  // ══════════════════════════════════════════════════════════
  // Phase 2: Choice Group Onboarding Actions
  // ══════════════════════════════════════════════════════════

  createOnboardingChoiceGroup: async (userRequirements, candidateCount) => {
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
      set({
        error: err instanceof Error ? err.message : '生成项目方案失败',
        isGeneratingChoices: false,
        choiceGroupGenerationProgress: null,
      });
    }
  },

  acceptOnboardingChoice: async (choiceId) => {
    const group = get().activeChoiceGroup;
    if (!group) return;
    set({ isLoading: true, error: null });
    try {
      const res = await workspaceApi.acceptProjectCreationChoice(group.id, choiceId);
      const projectId = res.projectId ?? res.project_id;
      if (!projectId) {
        throw new Error('project_id_missing');
      }
      const space = await workspaceApi.getById(projectId);
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
        lastActionMessage: '项目已创建！祝您建模愉快！',
      });
      // Reload open groups since this one is resolved
      get().loadOpenOnboardingChoiceGroups();
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '采纳方案失败', isLoading: false });
    }
  },

  discardOnboardingChoiceGroup: async () => {
    const group = get().activeChoiceGroup;
    if (!group) {
      set({ activeChoiceGroup: null });
      return;
    }
    try {
      await workspaceApi.discardProjectCreationChoiceGroup(group.id);
    } catch (err) {
      console.warn('Failed to discard onboarding choice group on backend:', err);
    } finally {
      set({
        activeChoiceGroup: null,
        isGeneratingChoices: false,
        generatingChoiceGroupType: null,
        currentSystemView: 'onboarding',
        lastActionMessage: '已关闭候选方案并返回创建页面',
      });
      void get().loadOpenOnboardingChoiceGroups();
    }
  },

  deferOnboardingChoiceGroup: async () => {
    const group = get().activeChoiceGroup;
    if (!group) return null;
    set({ isLoading: true, error: null });
    try {
      const res = await workspaceApi.deferProjectCreationChoiceGroup(group.id);
      const projectId = res.projectId ?? res.project_id;
      if (!projectId) {
        throw new Error('project_id_missing');
      }
      await get().openWorkspace(String(projectId));
      set({
        activeChoiceGroup: null,
        isLoading: false,
        lastActionMessage: '已创建空白项目，并保留待采纳的项目草稿方案。',
      });
      void get().loadOpenOnboardingChoiceGroups();
      return Number(projectId);
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : '稍后处理失败',
        isLoading: false,
      });
      return null;
    }
  },

  loadOpenOnboardingChoiceGroups: async () => {
    try {
      const groups = await workspaceApi.listOpenProjectCreationChoiceGroups();
      set({ openOnboardingChoiceGroups: groups });
    } catch {
      // Silently fail — this is a background refresh
    }
  },

  recoverOnboardingChoiceGroup: async (groupId) => {
    try {
      const group = await workspaceApi.getProjectCreationChoiceGroup(groupId);
      if (group && group.status === 'open') {
        set({ activeChoiceGroup: group, currentSystemView: 'onboarding' });
      }
    } catch {
      set({ error: '无法恢复项目草稿，它可能已失效' });
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

  // ══════════════════════════════════════════════════════════
  // Phase 3: In-project Generation Choice Group
  // ══════════════════════════════════════════════════════════

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
    // 前端开关: VITE_GENERATION_CHOICE_GROUP_ENABLED=false 时跳过 choice group
    if (import.meta.env.VITE_GENERATION_CHOICE_GROUP_ENABLED === 'false') {
      set({ isGeneratingChoices: false, isGenerating: false });
      throw new Error('choice_group_disabled');
    }

    const conflictingGroup = findConflictingChoiceGroup(get().backendChoiceGroups, generationType, target);
    if (conflictingGroup && !forceReplace) {
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

    set({
      isGeneratingChoices: true,
      error: null,
      lastActionMessage: `正在生成 ${generationType} 候选方案...`,
    });
    try {
      if (conflictingGroup && forceReplace) {
        await workspaceApi.discardChoiceGroup(projectId, Number(conflictingGroup.id));
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
      set((state) => ({
        ...syncChoiceGroupToWorkspace(group, state),
        isGeneratingChoices: false,
        activeDraft: null,
        activeDraftType: null,
        pendingGenerationConflict: null,
        lastActionMessage: `已生成 ${group.successCount || group.success_count || 0} 套候选方案`,
      }));
      return group;
    } catch (err) {
      if (err instanceof Error && err.message === GENERATION_CONFLICT_PENDING_ERROR) {
        set({ isGeneratingChoices: false });
        return null;
      }
      set({
        error: err instanceof Error ? err.message : '生成候选方案失败',
        isGeneratingChoices: false,
      });
      return null;
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
      const projectId = res.projectId ?? res.project_id;
      if (!projectId) {
        throw new Error('project_id_missing');
      }
      const space = await workspaceApi.getById(projectId);
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
      set({ error: err instanceof Error ? err.message : '创建空白项目失败', isLoading: false });
    }
  },

  // AI Generators per phase
  generateActors: async (forceReplace = false) => {
    const pId = withWorkspaceId(get());
    try {
      const group = await get().createGenerationChoiceGroup({
        projectId: pId,
        generationType: 'actor',
        candidateCount: 2,
        forceReplace,
        conflictAction: 'generateActors',
      });
      if (group || get().pendingGenerationConflict) return;
    } catch (_err) {
      if (get().pendingGenerationConflict) return;
    }
    try {
      // Fallback: old single-draft flow
      const draft = await workspaceApi.createActorGenerationDraft(pId);
      set({ activeDraft: draft, activeDraftType: 'actor', isGeneratingChoices: false, isGenerating: false, lastActionMessage: '🤖 AI 推荐的角色列表已生成！' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '生成角色失败';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
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

  generateFeatures: async (forceReplace = false) => {
    const pId = withWorkspaceId(get());
    try {
      const group = await get().createGenerationChoiceGroup({
        projectId: pId,
        generationType: 'feature',
        candidateCount: 2,
        forceReplace,
        conflictAction: 'generateFeatures',
      });
      if (group || get().pendingGenerationConflict) return;
    } catch (_err) {
      if (get().pendingGenerationConflict) return;
    }
    try {
      const draft = await workspaceApi.createFeatureGenerationDraft(pId);
      set({ activeDraft: draft, activeDraftType: 'feature', isGenerating: false, isGeneratingChoices: false,
        lastActionMessage: '🤖 AI 推荐的核心功能架构树已生成！',
      });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '生成功能树失败';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
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

  generateFlowsAndObjects: async (forceReplace = false) => {
    const pId = withWorkspaceId(get());
    try {
      const group = await get().createGenerationChoiceGroup({
        projectId: pId,
        generationType: 'flow',
        candidateCount: 2,
        forceReplace,
        conflictAction: 'generateFlowsAndObjects',
      });
      if (group || get().pendingGenerationConflict) return;
    } catch (_err) {
      if (get().pendingGenerationConflict) return;
    }
    try {
      const draft = await workspaceApi.createFlowGenerationDraft(pId);
      set({ activeDraft: draft, activeDraftType: 'flow', isGenerating: false, isGeneratingChoices: false,
        lastActionMessage: '🤖 AI 推荐的核心泳道步骤与核心数据对象已生成！',
      });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '生成流程失败';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
    }
  },

  regenerateFlowsAndObjects: async (feedback) => {
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isGenerating: true, error: null, lastActionMessage: '🤖 AI 正在根据您的意见重新推演流程与业务对象，请稍候...' });
    try {
      const updated = isSlotFillingDraft(draft)
        ? await workspaceApi.regenerateSlotFillingDraft(draftId, feedback)
        : await workspaceApi.regenerateFlowGenerationDraft(draftId, feedback);
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
      if (isSlotFillingDraft(draft)) {
        await workspaceApi.confirmSlotFillingDraft(draftId);
      } else {
        await workspaceApi.confirmFlowGenerationDraft(draftId);
      }
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

  generateScenarios: async (featureIds, forceReplace = false) => {
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
      if (group || get().pendingGenerationConflict) return;
    } catch (_err) {
      if (get().pendingGenerationConflict) return;
      // Fall through to draft fallback
    }

    // ── Fallback / full / batch: old draft path ──────────────
    set({ isGenerating: true, error: null, lastActionMessage: '🤖 AI 正在智能推演具体功能节点在业务场景下的典型成功场景...' });
    try {
      if (Array.isArray(featureIds)) {
        if (featureIds.length === 0) {
          const draft = await workspaceApi.createScenarioGenerationDraft(pId);
          set({ activeDraft: draft, activeDraftType: 'scenario', isGenerating: false, lastActionMessage: '🤖 AI 智能场景推演成功！已在上方提供完整场景列表，可查看其详细交互 and AC验收条件。' });
        } else if (featureIds.length === 1) {
          const draft = await workspaceApi.createScenarioGenerationDraft(pId, featureIds[0]);
          set({ activeDraft: draft, activeDraftType: 'scenario', isGenerating: false, lastActionMessage: '🤖 AI 智能场景推演成功！已在上方提供完整场景列表，可查看其详细交互 and AC验收条件。' });
        } else {
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
            draft_id: draftIds[0],
          };
          set({ activeDraft: combinedDraft, activeDraftType: 'scenario', isGenerating: false, lastActionMessage: `🤖 AI 智能场景推演成功！针对选定的 ${featureIds.length} 个功能模块共生成了 ${combinedScenarios.length} 个场景，已在上方提供预览。` });
        }
      } else {
        const draft = await workspaceApi.createScenarioGenerationDraft(pId, featureIds);
        set({ activeDraft: draft, activeDraftType: 'scenario', isGenerating: false, lastActionMessage: '🤖 AI 智能场景推演成功！已在上方提供完整场景列表，可查看其详细交互 and AC验收条件。' });
      }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '生成成功场景失败';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
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

  generateAcceptanceCriteria: async (scenarioIds, forceReplace = false) => {
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
        if (group || get().pendingGenerationConflict) return;
      } catch (_err) {
        if (get().pendingGenerationConflict) return;
        /* fall through */
      }
    }
    try {
      const draft = await workspaceApi.createAcceptanceCriteriaGenerationDraft(pId, scenarioIds);
      set({ activeDraft: draft, activeDraftType: 'ac', isGenerating: false, isGeneratingChoices: false,
        lastActionMessage: '🤖 AI 推荐的验收标准 (AC) 已精细推演成功！',
      });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '生成验收标准失败';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
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

  generateScope: async (forceReplace = false) => {
    const pId = withWorkspaceId(get());
    try {
      const group = await get().createGenerationChoiceGroup({
        projectId: pId,
        generationType: 'scope',
        candidateCount: 2,
        forceReplace,
        conflictAction: 'generateScope',
      });
      if (group || get().pendingGenerationConflict) return;
    } catch (_err) {
      if (get().pendingGenerationConflict) return;
    }
    try {
      const draft = await workspaceApi.createScopeGenerationDraft(pId);
      set({ activeDraft: draft, activeDraftType: 'scope', isGenerating: false, isGeneratingChoices: false,
        lastActionMessage: '🤖 AI Kano 范围与发布优先级分析推演成功！',
      });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '生成范围分析失败';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
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

  skipKano: async () => {
    const ir = get().ir;
    if (!ir || !ir.projectId) return;
    set({ isLoading: true, error: null, lastActionMessage: '正在跳过 Kano 分析并解锁导航...' });
    try {
      await workspaceApi.skipKano(ir.projectId);
      await get().refreshWorkspace();
      set({ isLoading: false, lastActionMessage: '已跳过 Kano 分析，阶段导航已解锁。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '跳过 Kano 分析失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isLoading: false });
    }
  },

  resetKano: async () => {
    const ir = get().ir;
    if (!ir || !ir.projectId) return;
    set({ isLoading: true, error: null, lastActionMessage: '正在重置 Kano 分析，清理 AI 建议...' });
    try {
      await workspaceApi.resetKano(ir.projectId);
      await get().refreshWorkspace();
      set({ isLoading: false, lastActionMessage: 'Kano 分析已重置，手工交付决策已保留。' });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '重置 Kano 分析失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isLoading: false });
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
      await get().refreshWorkspace();
      set({ lastActionMessage: `已创建功能节点：${name}` });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '创建功能节点失败' });
    }
  },

  updateFeature: async (featureId, updates) => {
    const pId = withWorkspaceId(get());
    const original = get().ir?.features?.find((f: any) => f.featureId === featureId);
    try {
      await workspaceApi.updateFeature(pId, featureId, {
        name: updates.featureName !== undefined ? updates.featureName : original?.featureName,
        description: updates.featureDescription !== undefined ? updates.featureDescription : original?.featureDescription,
        actor_ids: updates.actorIds !== undefined ? updates.actorIds : original?.actorIds
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
    const ir = get().ir;
    const flows = ir?.flows || [];
    const isReferenced = flows.some(flow =>
      (flow.flowSteps || []).some(step =>
        (step.inputBusinessObjectIds || []).includes(id) ||
        (step.outputBusinessObjectIds || []).includes(id)
      )
    );
    if (isReferenced) {
      set({ boDeletionError: '无法删除该数据实体：因为某些流程步骤（How阶段）正将其作为输入或输出实体引用。请先在相应的步骤面板中取消勾选关联。' });
      return;
    }

    try {
      await workspaceApi.deleteBusinessObject(pId, id);
      await get().refreshWorkspace();
      set((s) => {
        const isSelected = s.selectedObjectId === id;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessage: '业务数据对象已被完全抹除。',
          boDeletionError: null
        };
      });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : '';
      if (errMsg.includes('business_object_in_use')) {
        set({ boDeletionError: '无法删除该数据实体：该数据实体正被某些流程步骤（How阶段）作为输入或输出对象引用。请先在相应的步骤面板中取消勾选关联，再进行删除。' });
      } else {
        set({ error: errMsg || '删除业务数据对象失败' });
      }
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

  reorderFlowSteps: async (flowId, stepIds) => {
    const pId = withWorkspaceId(get());
    try {
      await workspaceApi.reorderFlowSteps(pId, flowId, stepIds);
      await get().refreshWorkspace();
      set({ lastActionMessage: '线性步骤排序及拓扑链路同步成功。' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '重新排列步骤顺序失败' });
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
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.deletePerceptionSlot(projectId);
      await get().refreshWorkspace();
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
      const errMsg = err instanceof Error ? err.message : '删除待处理卡点失败';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      set({ error: friendlyMsg, lastActionMessage: friendlyMsg, isLoading: false });
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
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    const numId = parseInt(slotId, 10);
    const slot = get().ir?.perceptionSlot;
    if (!slot || slot.perceptionSlotId !== numId) return;

    set({ isGenerating: true, error: null, lastActionMessage: 'AI 正在展开感知槽并生成补全草稿，请稍候...' });
    try {
      let fillerKind: 'actor' | 'feature' | 'flow' | 'scenario' | 'ac' | null = null;
      const kindText = slot.perceptionKind ? slot.perceptionKind.toUpperCase() : '';
      if (kindText === '角色结点' || kindText === 'ACTOR') fillerKind = 'actor';
      else if (kindText === '功能模块结点' || kindText === '功能叶子结点' || kindText === 'FEATURE') fillerKind = 'feature';
      else if (kindText === '流程主结点' || kindText === 'FLOW') fillerKind = 'flow';
      else if (kindText === '场景结点' || kindText === 'SCENARIO') fillerKind = 'scenario';
      else if (kindText === '成功标准结点' || kindText === 'ACCEPTANCE_CRITERION' || kindText === 'AC' || kindText === 'ac') fillerKind = 'ac';

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
  acceptChoice: async (choiceId, force) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    const choiceIdNum = parseInt(choiceId, 10);
    if (isNaN(choiceIdNum)) return;
    set({ isLoading: true, error: null });
    try {
      const result = await workspaceApi.acceptChoice(projectId, choiceIdNum, force || false);
      // Handle stale response (UX-5)
      if (result?.is_stale) {
        set({ activeStaleChoice: { projectId, choiceId: choiceIdNum, staleReason: result.stale_reason }, isLoading: false });
        return;
      }
      // Accept succeeded → refresh workspace & close modal
      await get().refreshWorkspace();
      set({
        activeChoiceGroup: null,
        activeStaleChoice: null,
        selectedObject: null,
        selectedObjectId: null,
        isLoading: false,
        lastActionMessage: '已成功采纳并应用该设计决策提案。',
      });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '采纳决策失败', isLoading: false });
    }
  },
  regenerateChoiceGroup: async (groupId, feedback) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ isGeneratingChoices: true, error: null, lastActionMessage: '正在重新生成候选方案...' });
    try {
      const newGroup = await workspaceApi.regenerateChoiceGroup(projectId, groupId, feedback);
      set({ activeChoiceGroup: newGroup, isGeneratingChoices: false, activeDraft: null, activeDraftType: null,
        lastActionMessage: '已重新生成候选方案组',
      });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '重新生成失败', isGeneratingChoices: false });
    }
  },
  regenerateChoice: async (choiceId, feedback) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ isGeneratingChoices: true, error: null, lastActionMessage: '正在重新生成候选方案...' });
    try {
      const updatedGroup = await workspaceApi.regenerateChoice(projectId, choiceId, feedback);
      set({ activeChoiceGroup: updatedGroup, isGeneratingChoices: false,
        lastActionMessage: '已重新生成候选方案',
      });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '重新生成失败', isGeneratingChoices: false });
    }
  },
  clearStaleChoice: () => {
    set({ activeStaleChoice: null });
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

  discardChoiceGroup: async (groupId) => {
    const projectId = get().ir?.projectId;
    if (!projectId) {
      set({ activeChoiceGroup: null });
      return;
    }
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.discardChoiceGroup(projectId, groupId);
    } catch (err) {
      console.warn('Failed to discard choice group on backend:', err);
    } finally {
      set({ activeChoiceGroup: null, isLoading: false, lastActionMessage: '已丢弃候选方案组。' });
      await get().refreshWorkspace();
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
        issue_id: issue.id,
        issue_code: issue.backendIssueCode || issue.category || '',
        stage: issue.stage,
        target: issue.backendTarget || null,
        metadata: issue.backendMetadata || {}
      });

      if (resolutionType(res) === 'already_resolved') {
        await get().refreshWorkspace();
        set({ isLoading: false, lastActionMessage: '该问题已解决。' });
        return null;
      }

      if (resolutionType(res) === 'open_panel' || resolutionType(res) === 'manual_action' || resolutionType(res) === 'unsupported') {
        set({ isLoading: false, lastActionMessage: res.title || '请手动处理该问题。', lastIssueResolution: res });
        return null;
      }

      if (resolutionType(res) === 'repair_draft') {
        set({ activeDraft: res.draft || res, activeDraftType: 'repair', lastActionMessage: `已生成修复建议：${res.title}`, isLoading: false });
        return null;
      }

      if (resolutionType(res) === 'choice_group') {
        await get().refreshWorkspace();
        set({ isLoading: false, lastActionMessage: '已加入方案决策队列，请选择处理方案。' });
        return null;
      }

      await get().refreshWorkspace();
      if (res.draftId || res.draft_id) {
        set({ activeDraft: res.draft, activeDraftType: mapResolutionDraftType(res.action?.draftType || res.action?.draft_type), lastActionMessage: `已触发处理：${res.title}` });
      }
      set({ isLoading: false });
      if (res.action?.payload?.perception_job_id) {
        return res.action.payload.perception_job_id.toString();
      }
      const slot = get().ir?.perceptionSlot;
      return slot ? slot.perceptionSlotId.toString() : null;
    } catch (err) {
      const msg = (err as any)?.detail || (err instanceof Error ? err.message : '处理 Issue 失败');
      set({ error: msg, lastActionMessage: msg, isLoading: false });
      return null;
    }
  },
  resolveIssue: async (issueId) => {
    return get().createSlotFromIssue(issueId);
  },
  confirmRepairDraft: async (draftId) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ isLoading: true, error: null });
    try {
      const res: any = await workspaceApi.confirmRepairDraft(projectId, draftId);
      await get().refreshWorkspace();
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
      const msg = (err as any)?.response?.data?.detail || (err instanceof Error ? err.message : '应用修复失败');
      set({ error: msg, lastActionMessage: msg, isLoading: false });
      return null;
    }
  },
  discardRepairDraft: async (draftId) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.discardRepairDraft(projectId, draftId);
      await get().refreshWorkspace();
      set({ isLoading: false, lastActionMessage: '已丢弃修复草稿。', activeDraft: null, activeDraftType: null });
    } catch (err) {
      const msg = (err as any)?.response?.data?.detail || (err instanceof Error ? err.message : '丢弃修复失败');
      set({ error: msg, lastActionMessage: msg, isLoading: false });
    }
  },
  regenerateRepairDraft: async (draftId) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ isLoading: true, error: null });
    try {
      const res = await workspaceApi.regenerateRepairDraft(projectId, draftId);
      await get().refreshWorkspace();
      set({
        isLoading: false,
        activeDraft: res,
        activeDraftType: 'repair',
        lastActionMessage: '已重新生成修复建议。',
      });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : '重新生成修复失败', isLoading: false });
    }
  },
  setNodeStatus: async (nodeId: string, nodeKind: string, status: NodeStatus) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    try {
      await workspaceApi.updateNodeConfirmationStatus(projectId, nodeKind, parseInt(nodeId, 10), status);
      await get().refreshWorkspace();
    } catch (err) {
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
      await get().refreshWorkspace();
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
          } else if (action.panel === 'feature' && action.payload?.feature_id) {
            const featId = action.payload.feature_id.toString();
            const featObj = get().ir?.features?.find((f: any) => f.featureId.toString() === featId);
            if (featObj) {
              get().setSelectedObject(featObj);
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
  updateIssueAttributes: async (issueId, updates) => {
    const current = get();
    const projectId = current.ir?.projectId;

    if (projectId && updates?.status && ['open', 'ignored', 'resolved'].includes(updates.status)) {
      try {
        await workspaceApi.updateIssueStatus(projectId, issueId, updates.status);
      } catch (err) {
        set({
          error: err instanceof Error ? err.message : '更新 Issue 状态失败',
        });
        throw err;
      }
    }

    const currentIssues = current.backendIssues || [];
    const nextIssues = currentIssues.map((issue) =>
      issue.id === issueId ? { ...issue, ...updates } : issue
    );

    const nextSelectedObject =
      current.selectedObject && (current.selectedObject as any).id === issueId
        ? { ...(current.selectedObject as any), ...updates }
        : current.selectedObject;

    set({
      backendIssues: nextIssues,
      backendIssuesLoaded: current.backendIssuesLoaded,
      ir: current.ir,
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
    const projectId = withWorkspaceId(get());
    try {
      const res = await workspaceApi.getActiveShadowDraft(projectId);
      if (res && res.status !== 'idle') {
        set({ activeShadowDraft: res });
      } else {
        set({ activeShadowDraft: null });
      }
      return res;
    } catch (err) {
      console.warn('Failed to fetch active shadow draft:', err);
      set({ activeShadowDraft: null });
      throw err;
    }
  },

  prepareShadowDraft: async () => {
    const projectId = withWorkspaceId(get());
    set({ isLoading: true });
    try {
      const res = await workspaceApi.prepareShadowDraft(projectId);
      set({ activeShadowDraft: res, isLoading: false });
      return res;
    } catch (err) {
      set({ isLoading: false });
      throw err;
    }
  },

  getShadowDraft: async (draftId: string) => {
    const projectId = withWorkspaceId(get());
    try {
      const res = await workspaceApi.getShadowDraft(projectId, draftId);
      set({ activeShadowDraft: res });
      return res;
    } catch (err) {
      console.warn('Failed to fetch shadow draft:', err);
      throw err;
    }
  },

  discardShadowDraft: async (draftId: string) => {
    const projectId = withWorkspaceId(get());
    set({ isLoading: true });
    try {
      await workspaceApi.discardShadowDraft(projectId, draftId);
      set({ activeShadowDraft: null, isLoading: false });
      await get().refreshWorkspace();
    } catch (err) {
      set({ isLoading: false });
      throw err;
    }
  },

  commitShadowDraft: async (draftId: string) => {
    const projectId = withWorkspaceId(get());
    set({ isLoading: true });
    try {
      await workspaceApi.commitShadowDraft(projectId, draftId);
      set({ activeShadowDraft: null, isLoading: false });
      await get().refreshWorkspace();
    } catch (err) {
      set({ isLoading: false });
      throw err;
    }
  },

  regenerateShadowDraft: async (draftId: string, feedback?: string) => {
    const projectId = withWorkspaceId(get());
    set({ isLoading: true });
    try {
      const res = await workspaceApi.regenerateShadowDraft(projectId, draftId, feedback);
      set({ activeShadowDraft: res, isLoading: false });
      return res;
    } catch (err) {
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
