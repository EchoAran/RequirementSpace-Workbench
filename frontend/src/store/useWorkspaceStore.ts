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
  KnowledgeWorkspace,
  KnowledgeDocument,
} from '@/core/schema';
import { workspaceApi } from '@/lib/api';
import i18n from '@/i18n';
import { getNextSuggestionPresentation } from '@/core/nextSuggestionPresentation';
import { getGenerationStrategyPresentation } from '@/core/generationStrategyPresentation';
import type { MessageInterpolation } from '@/core/localizedMessage';

const getConfirmationStatus = (value: unknown): NodeStatus => {
  return value === 'confirmed' || value === 'needs_confirmation' || value === 'ai_assumption'
    ? value
    : 'ai_assumption';
};


export type WorkspacePage = '/what' | '/flow' | '/scope' | '/preview' | '/overview' | '/knowledge';



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
      strategyId: c.strategyId ?? c.strategy_id,
      strategyLabel: c.strategyLabel ?? c.strategy_label,
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
 * 从 Finding 对象获取处理能力，优先使用后端返回的 capability。
 *
 * 任何时候都优先信任后端 capability 字段；缺失时使用安全回退（manual_action），
 * 不由前端 code 推导 AI capability。
 */
export function getFindingCapability(finding: { code: string; capability?: any; type?: string }): {
  kind: string;
  actionLabel: string;
  enabled: boolean;
} {
  // 1. 优先使用后端返回的 capability
  if (finding.capability) {
    return {
      kind: finding.capability.kind || 'manual_action',
      actionLabel: finding.capability.action_label || i18n.t('store.finding.viewSuggestion'),
      enabled: finding.capability.enabled !== false,
    };
  }

  // 2. 当 capability 缺失（旧缓存或旧响应）时，使用安全回退
  //    禁止用 code 推导 AI capability，统一降级为 manual_action
  console.warn(
    `getFindingCapability: Finding ${finding.code} (${finding.type}) missing backend capability. ` +
    'Using safe fallback manual_action. Check if backend returned capability field.',
  );
  return {
    kind: 'manual_action',
    actionLabel: i18n.t('store.finding.viewSuggestion'),
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
    return 'store.errors.timeout';
  }
  if (
    normalizedError.includes('quota') ||
    normalizedError.includes('rate limit') ||
    normalizedError.includes('429')
  ) {
    return 'store.errors.quota';
  }
  if (
    normalizedError.includes('invalid api key') ||
    normalizedError.includes('unauthorized') ||
    normalizedError.includes('401')
  ) {
    return 'store.errors.unauthorized';
  }

  switch (rawError) {
    case 'llm_config_required':
      return 'store.errors.llm_config_required';
    case 'server_llm_config_not_configured':
      return 'store.errors.server_llm_config_not_configured';
    case 'llm_content_locale_mismatch':
      return 'store.errors.llm_content_locale_mismatch';
    case 'leaf_feature_without_actor':
      return 'store.errors.leaf_feature_without_actor';
    case 'feature_is_not_leaf':
      return 'store.errors.feature_is_not_leaf';
    case 'empty_leaf_features':
      return 'store.errors.empty_leaf_features';
    case 'project_not_found':
      return 'store.errors.project_not_found';
    case 'empty_actors':
      return 'store.errors.empty_actors';
    case 'empty_features':
      return 'store.errors.empty_features';
    case 'feature_not_found':
      return 'store.errors.feature_not_found';
    case 'actor_not_found':
      return 'store.errors.actor_not_found';
    case 'draft_not_found':
      return 'store.errors.draft_not_found';
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
          title: i18n.t('confirmationWorkspace.nodeKindLabels.acceptance_criterion'),
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
          title: `${bo.businessObjectName} ${i18n.t('rightPanel.coreFeatureNode')}`,
          description: `${i18n.t('store.bo.boardDesc')}`,
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
    slotsRecord[perceptionSlot.id] = {
      ...perceptionSlot,
      id: perceptionSlot.id,
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
  actor: 'confirmationWorkspace.nodeKindLabels.actor',
  feature: 'confirmationWorkspace.nodeKindLabels.feature',
  flow: 'confirmationWorkspace.nodeKindLabels.flow',
  scenario: 'confirmationWorkspace.nodeKindLabels.scenario',
  acceptance_criteria: 'confirmationWorkspace.nodeKindLabels.acceptance_criterion',
  scope: 'confirmationWorkspace.nodeKindLabels.scope',
  project_creation: 'store.project.draft',
};

const getGenerationTypeLabel = (generationType?: string) => (
  generationTypeLabelMap[generationType || ''] || generationType || 'choiceGroupPreview.candidateFallback'
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

const buildInitialChoiceProgress = (candidateCount?: number, candidateLabels: string[] = []) => {
  const totalCandidates = candidateCount || 2;
  return {
    totalCandidates,
    candidateLabels,
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
  stageTransitionInFlight: boolean;
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
  lastActionMessageToken: string | null;
  lastActionMessageTokenInterpolation: MessageInterpolation | null;
  lastIssueResolution: any | null;
  workspaces: WorkspaceListItem[];
  stageProgress: any | null;
  loadStageProgress: (projectId?: string) => Promise<void>;

  // Project Lifecycles
  loadWorkspaces: () => Promise<void>;
  openExistingProject: () => Promise<void>;
  openWorkspace: (workspaceId: string) => Promise<boolean>;
  refreshWorkspace: () => Promise<void>;
  exitWorkspace: () => void;
  updateProject: (projectId: string, name: string, description: string) => Promise<void>;
  deleteProject: (projectId: string) => Promise<void>;

  // Onboarding On-demand Creation
  startAIOnboarding: (prompt: string, name?: string, description?: string) => Promise<void>;
  confirmAIOnboarding: () => Promise<string | null>;
  regenerateAIOnboarding: (feedback?: string) => Promise<void>;
  discardAIOnboarding: () => Promise<void>;
  createBlankWorkspace: (name: string, description: string, prompt: string) => Promise<string | null>;

  // Knowledge Base Workspace / Onboarding
  creationWorkspaceId: string | null;
  creationDocuments: KnowledgeDocument[];
  initCreationWorkspace: () => Promise<void>;
  loadCreationDocuments: () => Promise<void>;
  uploadCreationDocument: (file: File) => Promise<void>;
  deleteCreationDocument: (docId: string) => Promise<void>;
  retryCreationDocument: (docId: string) => Promise<void>;

  // Project-level Knowledge Base
  projectDocuments: KnowledgeDocument[];
  isUploadingDocument: boolean;
  projectConfiguration: any | null;
  isLoadingProjectConfiguration: boolean;
  isSavingGenerationStrategies: boolean;
  loadProjectDocuments: () => Promise<void>;
  uploadProjectDocument: (file: File) => Promise<void>;
  deleteProjectDocument: (docId: string) => Promise<void>;
  retryProjectDocument: (docId: string) => Promise<void>;
  toggleDocumentAI: (docId: string, enabled: boolean) => Promise<void>;
  fetchProjectConfiguration: (projectId: string) => Promise<void>;
  updateProjectGenerationStrategies: (projectId: string, payload: any) => Promise<void>;
  deleteProjectGenerationStrategies: (projectId: string) => Promise<void>;
  updateProjectKnowledgeConfig: (projectId: string, payload: { enabled: boolean }) => Promise<void>;
  updateProjectConfiguration: (projectId: string, payload: { content_locale: string | null }) => Promise<void>;

  // Feature Flag
  knowledgeBaseEnabled: boolean;
  loadKnowledgeConfig: () => Promise<void>;

  activeChoiceGroup: any | null;
  choiceGroupGenerationProgress: {
    totalCandidates: number;
    candidateLabels: string[];
    completedCandidates: number;
    candidateStatuses: Record<number, 'pending' | 'generating' | 'complete' | 'failed'>;
  } | null;
  isGeneratingChoices: boolean;
  generatingChoiceGroupType?: string | null;
  openOnboardingChoiceGroups: any[];
  pendingGenerationConflict: PendingGenerationConflict | null;
  createOnboardingChoiceGroup: (userRequirements: string, candidateCount?: number) => Promise<void>;
  acceptOnboardingChoice: (choiceId: string) => Promise<string | null>;
  discardOnboardingChoiceGroup: () => Promise<void>;
  deferOnboardingChoiceGroup: () => Promise<string | null>;
  loadOpenOnboardingChoiceGroups: () => Promise<void>;
  recoverOnboardingChoiceGroup: (groupId: string) => Promise<void>;
  dismissPendingGenerationConflict: () => void;
  confirmPendingGenerationConflict: () => Promise<void>;

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
  runDiagnosis: (stage?: 'what' | 'how' | 'scope') => Promise<void>;
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
  requestStageTransition: (
    action: 'enter_how' | 'enter_scope' | 'enter_preview',
    options?: { navigate?: (path: string) => void; force?: boolean }
  ) => Promise<void>;

  activeGateCheck: {
    action: string;
    findings: Finding[];
    onPass: () => void;
    onCancel: () => void;
  } | null;
  snoozedGateFindingIds: Record<string, string>; // Maps key to context hash
  triggerGateCheck: (action: string, onPass: () => void, onCancel?: () => void) => Promise<void>;
  snoozeGateFinding: (action: string, finding: Finding) => void;
  startFindingSuggestion: (
    finding: Finding,
    options?: { navigate?: (path: string) => void }
  ) => Promise<any>;
  executeGateFindingAction: (finding: Finding) => Promise<void>;

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
    throw new Error('store.errors.loadWorkspaceFailed');
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
    version: number,
    options?: { navigate?: (path: string) => void }
  ) => {
    if (!action) return null;

    const kind = action.kind;

    if (kind === 'stage_transition') {
      const transitionAction = action.transition_action || action.transitionAction;
      if (transitionAction) {
        if (options?.navigate) {
          await get().requestStageTransition(transitionAction, { navigate: options.navigate });
        }
        return {
          type: 'stage_transition',
          action: transitionAction,
        };
      }
      return null;
    }

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
      return {
        type: 'business_action',
        kind,
        action,
      };
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

      const projectId = get().ir?.projectId;
      if (projectId && route) {
        let resolvedRoute = route;
        if (page) {
          resolvedRoute = `/projects/${projectId}${page}`;
        }
        if (options?.navigate) {
          options.navigate(resolvedRoute);
        } else if (page) {
          get().setActivePage(page);
        }
        return {
          type: 'navigation',
          route: resolvedRoute,
        };
      }
      return null;
    } else if (kind === 'wait') {
      const stage = (action.stage || context.stage || 'what') as 'what' | 'how' | 'scope';
      const projectId = get().ir?.projectId;
      
      set({ lastActionMessageToken: 'store.actions.refreshingAnalysis' });
      
      if (!projectId) {
        return {
          type: 'wait',
          jobId: action.job_id || action.jobId,
          stage,
          message: 'store.errors.projectIdMissing',
          status: 'failed',
        };
      }

      let res = await workspaceApi.getNextSuggestion(projectId, stage);
      if (get().sessionVersion !== version) return;
      let currentSug = res.suggestion;

      if (currentSug && currentSug.status === 'running') {
        const maxAttempts = 4;
        let attempts = 0;
        
        while (attempts < maxAttempts) {
          set({ lastActionMessageToken: 'store.actions.runningDiagnosis' });
          await new Promise((resolve) => setTimeout(resolve, 2000));
          if (get().sessionVersion !== version) return;
          
          res = await workspaceApi.getNextSuggestion(projectId, stage);
          if (get().sessionVersion !== version) return;
          currentSug = res.suggestion;
          
          if (!currentSug || currentSug.status !== 'running') {
            break;
          }
          attempts++;
        }
      }

      // Update in store
      set((s: WorkspaceState) => ({
        nextSuggestions: {
          ...s.nextSuggestions,
          [stage]: currentSug
        }
      }));

      await get().refreshWorkspace();

      let status = 'idle';
      let message = 'store.finding.diagnosisComplete';

      if (currentSug) {
        if (currentSug.status === 'running') {
          status = 'running';
          message = 'store.finding.aiAnalyzing';
        } else if (currentSug.status === 'failed') {
          status = 'failed';
          message = 'store.finding.reDiagnose';
          set({
            lastActionMessageTokenInterpolation: {
              key: message,
              values: { desc: currentSug.description || i18n.t('store.errors.analysisError') },
            },
          });
        } else if (
          currentSug.code === 'ENTER_HOW' ||
          currentSug.code === 'ENTER_SCOPE' ||
          currentSug.metadata?.action?.kind === 'stage_transition'
        ) {
          status = 'ready_to_advance';
          message = 'store.finding.stageTransitionAvailable';
        } else {
          status = 'suggestion_changed';
          message = 'store.finding.fixSuggestionsRegenerated';
        }
      }

      set({ lastActionMessageToken: message });

      return {
        type: 'wait',
        jobId: action.job_id || action.jobId,
        stage,
        message,
        status,
      };
    } else if (kind === 'open_gate_findings') {
      const stage = (context.stage || 'what') as 'what' | 'how' | 'scope';
      const actionMap: Record<string, string> = {
        'what': 'enter_how',
        'how': 'enter_scope',
        'scope': 'enter_preview'
      };
      const gateAction = actionMap[stage] || 'enter_how';
      await get().triggerGateCheck(gateAction, () => {
        if (options?.navigate) {
          get().requestStageTransition(gateAction as any, { navigate: options.navigate });
        }
      });
      return {
        type: 'open_gate_findings',
        stage,
      };
    } else if (kind === 'retry') {
      const stage = (context.stage || 'what') as 'what' | 'how' | 'scope';
      const projectId = get().ir?.projectId;
      if (projectId) {
        await workspaceApi.rediagnoseNextSuggestion(projectId, stage);
        await get().runDiagnosis(stage);
      }
      return {
        type: 'retry',
        stage,
      };
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
          if (options?.navigate) {
            options.navigate(`/projects/${get().ir?.projectId}/flow`);
          } else {
            get().setActivePage('/flow');
          }
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
            if (options?.navigate) {
              options.navigate(`/projects/${get().ir?.projectId}${page}`);
            } else {
              get().setActivePage(page);
            }
            routed = true;
            set({ lastActionMessageToken: 'store.actions.navigatedToPage' });
          }
        }
        if (!routed) {
          set({ lastActionMessageToken: 'store.actions.unableToLocate' });
        }
      }
      return {
        type: 'open_panel',
        panel,
        payload,
      };
    }
    return null;
  };

  const executeIssueResolution = async (res: any, issue: any, version: number) => {
    const type = resolutionType(res);

    if (type === 'already_resolved') {
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ isLoading: false, lastActionMessageToken: 'store.actions.issueResolved' });
      return;
    }

    if (type === 'open_panel') {
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      if (res.action) {
        await executeProcessorAction(res.action, { stage: issue.stage, target: issue.target }, version);
      }
        set({ isLoading: false, lastActionMessageToken: 'store.actions.panelOpened', lastIssueResolution: res });
      return;
    }

    if (type === 'manual_action') {
        set({ isLoading: false, lastActionMessageToken: 'store.actions.manualActionRequired', lastIssueResolution: res });
      return;
    }

    if (type === 'unsupported') {
        set({ isLoading: false, lastActionMessageToken: 'store.actions.autoFixUnsupported', lastIssueResolution: res });
      return;
    }

    if (type === 'repair_draft') {
      set({
        activeDraft: res.draft || res,
        activeDraftType: 'repair',
        lastActionMessageToken: 'store.actions.fixSuggestionsGenerated',
        isLoading: false
      });
      return;
    }

    if (type === 'choice_group') {
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ isLoading: false, lastActionMessageToken: 'store.actions.addedToDecisionQueue' });
      return;
    }

    // Default / standard path
    await get().refreshWorkspace();
    if (get().sessionVersion !== version) return;
    if (res.draftId || res.draft_id) {
      set({
        activeDraft: res.draft,
        activeDraftType: mapResolutionDraftType(res.action?.draftType || res.action?.draft_type),
        lastActionMessageToken: 'store.actions.actionTriggered'
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

    creationWorkspaceId: null,
    creationDocuments: [],
    projectDocuments: [],
    isUploadingDocument: false,
    projectConfiguration: null,
    isLoadingProjectConfiguration: false,
    isSavingGenerationStrategies: false,
    knowledgeBaseEnabled: true,

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
  stageTransitionInFlight: false,
  nextSuggestions: {},

  // Draft Generative States
  activeDraft: null,
  activeDraftType: null,
  isGenerating: false,

  activeChoiceGroup: null,
  choiceGroupGenerationProgress: null,
  isGeneratingChoices: false,
  openOnboardingChoiceGroups: [],
  pendingGenerationConflict: null,
  activeStaleChoice: null,

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
  lastActionMessageToken: null,
  lastActionMessageTokenInterpolation: null,
  lastIssueResolution: null,
  workspaces: [],
  stageProgress: null,

  loadWorkspaces: async () => {
    const version = get().sessionVersion;
    set({ isLoading: true, error: null });
    try {
      const workspaces = await workspaceApi.list();
      if (get().sessionVersion !== version) return;
      set({ workspaces, isLoading: false });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.errors.loadWorkspaceFailed', isLoading: false });
    }
  },

  openExistingProject: async () => {
    const version = get().sessionVersion + 1;
    set({ sessionVersion: version, stageProgress: null, isLoading: true, error: null });
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
        await get().loadStageProgress(projectId);
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
      set({ error: err instanceof Error ? err.message : 'store.project.openFailed', isLoading: false });
    }
  },

  openWorkspace: async (workspaceId) => {
    const version = get().sessionVersion + 1;
    set({ sessionVersion: version, stageProgress: null, isLoading: true, error: null });
    try {
      const space = await workspaceApi.getById(workspaceId);
      if (get().sessionVersion !== version) return false;
      const projectId = space.projectId;
      
      let choiceGroupsRecord: Record<string, ChoiceGroup> = {};
      
        const findingsData = await loadBackendFindingsAndViews(projectId);
        if (get().sessionVersion !== version) return false;
        try {
          const groups = await workspaceApi.listChoiceGroups(projectId, 'open');
          if (get().sessionVersion !== version) return false;
          groups.forEach((cg: any) => {
            const compatible = mapBackendChoiceGroupToCompatible(cg);
            choiceGroupsRecord[compatible.id] = compatible;
          });
        } catch (cgErr) {
          console.warn('Failed to load choice groups:', cgErr);
        }
        await get().loadAuditLogs(projectId);
        if (get().sessionVersion !== version) return false;
        await get().loadStageProgress(projectId);
        if (get().sessionVersion !== version) return false;

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
        return true;
    } catch (err) {
      if (get().sessionVersion !== version) return false;
      set({ error: err instanceof Error ? err.message : 'store.errors.openWorkspaceFailed', isLoading: false });
      return false;
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
      await get().loadStageProgress(id);
      if (get().sessionVersion !== version) return;

      set((s: WorkspaceState) => ({
        ...findingsData,
        backendFindingsLoaded: true,
        backendChoiceGroups: choiceGroupsRecord,
        ir: space,
        selectedObject: findSelectedObjectInIr(space, s.selectedObjectId, s.selectedObject)
      }));
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.errors.syncDataFailed' });
    }
  },
  loadStageProgress: async (projectId?: string) => {
    const version = get().sessionVersion;
    const id = projectId || get().ir?.projectId;
    if (!id) return;
    try {
      const progress = await workspaceApi.getStageProgress(id);
      if (get().sessionVersion !== version) return;
      set({ stageProgress: progress });
    } catch (err) {
      console.error('Failed to load stage progress:', err);
    }
  },

  requestStageTransition: async (
    action: 'enter_how' | 'enter_scope' | 'enter_preview',
    options?: { navigate?: (path: string) => void; force?: boolean }
  ) => {
    if (get().stageTransitionInFlight) {
      console.warn('Stage transition already in flight, ignoring request.');
      return;
    }
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;

    let targetRoute = '';
    if (action === 'enter_how') {
      targetRoute = `/projects/${projectId}/flow`;
    } else if (action === 'enter_scope') {
      targetRoute = `/projects/${projectId}/scope`;
    } else if (action === 'enter_preview') {
      targetRoute = `/projects/${projectId}/preview`;
    } else {
      return;
    }

    set({ stageTransitionInFlight: true, isLoading: true, error: null });

    try {
      const response = await workspaceApi.stageTransition(projectId, {
        action,
        force: options?.force || false,
      });

      if (get().sessionVersion !== version) {
        set({ stageTransitionInFlight: false });
        return;
      }

      if (response.status === 'blocked') {
        // Pop the gate check modal
        set({
          activeGateCheck: {
            action: action === 'enter_preview' ? 'generate_preview' : action,
            findings: response.blockingFindings || [],
            onPass: () => {
              set({ activeGateCheck: null });
              get().requestStageTransition(action, { ...options, force: true });
            },
            onCancel: () => {
              set({ activeGateCheck: null });
            },
          },
          isLoading: false,
          stageTransitionInFlight: false,
        });
        return;
      }

      // Transition succeeded, refresh workspace and navigate
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) {
        set({ stageTransitionInFlight: false });
        return;
      }

      set({ isLoading: false, stageTransitionInFlight: false });

      if (options?.navigate) {
        options.navigate(targetRoute);
      }
    } catch (err) {
      if (get().sessionVersion !== version) {
        set({ stageTransitionInFlight: false });
        return;
      }
      set({ error: err instanceof Error ? err.message : 'store.errors.stageTransitionFailed', isLoading: false, stageTransitionInFlight: false });
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
      set({ error: err instanceof Error ? err.message : 'store.errors.gateCheckFailed', isLoading: false });
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

  startFindingSuggestion: async (finding: Finding, options?: { navigate?: (path: string) => void }) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;

    const presentation = getNextSuggestionPresentation(finding);
    const isGlobalLoading = presentation.icon === 'generate' || presentation.icon === 'retry' || presentation.icon === 'wait';

    set({
      isLoading: true,
      error: null,
      ...(isGlobalLoading ? { isGenerating: true, lastActionMessageToken: presentation.loadingLabel } : {})
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
        const result = await executeProcessorAction(action, { stage: finding.stage, findingCode: finding.code, target }, version, options);
        set({ isLoading: false, isGenerating: false });
        return result;
      } else {
        throw new Error(`${i18n.t('store.finding.nextActionText')}「${finding.code}」${i18n.t('store.finding.missingActionText')}`);
      }
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.errors.startSuggestionFailed', isLoading: false, isGenerating: false });
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
      const msg = err instanceof Error ? err.message : 'store.errors.autoFixFailed';
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
      stageProgress: null,
      auditLogs: [],
      error: null,
      boDeletionError: null,
      lastActionMessageToken: null,
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
      set({ isLoading: false, lastActionMessageToken: 'store.project.updateSuccess' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.project.updateFailed', isLoading: false });
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
      set({ isLoading: false, lastActionMessageToken: 'store.project.deleteSuccess' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.project.deleteFailed', isLoading: false });
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
        actionType: log.actionType || log.action_type || 'store.actions.actionTriggered',
        summary: log.summary || 'store.actions.actionTriggered',
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
    set({ isGenerating: true, error: null, lastActionMessageToken: 'store.project.generatingInitialDraft' });
    try {
      const draft = await workspaceApi.createProjectCreationDraft({
        user_requirements: prompt,
        project_name: name,
        project_description: description,
        knowledge_workspace_id: get().creationWorkspaceId || undefined,
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
      set({ error: err instanceof Error ? err.message : 'store.errors.generateDraftFailed', isGenerating: false });
    }
  },

  confirmAIOnboarding: async () => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return null;
    set({ isLoading: true, error: null });
    try {
      const res = await workspaceApi.confirmProjectCreationDraft(draft.draft_id);
      if (get().sessionVersion !== version) return null;
      const projectId = res.project_id;
      set({
        activeDraft: null,
        activeDraftType: null,
        creationWorkspaceId: null,
        creationDocuments: [],
      });
      const opened = await get().openWorkspace(projectId);
      if (!opened) return null;
      set({ lastActionMessageToken: 'store.project.modelFrameworkConfirmed' });
      return projectId;
    } catch (err) {
      if (get().sessionVersion !== version) return null;
      const errMsg = err instanceof Error ? err.message : 'store.errors.confirmDraftFailed';
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: 'store.errors.draftExpired', isLoading: false });
      } else {
        set({ error: errMsg, isLoading: false });
      }
      return null;
    }
  },

  regenerateAIOnboarding: async (feedback) => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isGenerating: true, error: null, lastActionMessageToken: 'store.project.regeneratingDraft' });
    try {
      const updated = await workspaceApi.regenerateProjectCreationDraft(draft.draft_id, feedback);
      if (get().sessionVersion !== version) return;
      set({ activeDraft: updated, isGenerating: false, lastActionMessageToken: 'store.project.draftRegenerated' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.errors.regenerateFailed';
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: 'store.errors.draftExpired', isGenerating: false });
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
      set({ error: err instanceof Error ? err.message : 'store.errors.discardDraftFailed' });
    }
  },

  createOnboardingChoiceGroup: async (userRequirements, candidateCount) => {
    const version = get().sessionVersion;
    set({
      isGeneratingChoices: true,
      error: null,
      lastActionMessageToken: 'store.project.generatingPlans',
      choiceGroupGenerationProgress: null,
    });
    try {
      const group = await workspaceApi.createProjectCreationChoiceGroup({
        user_requirements: userRequirements,
        candidate_count: candidateCount || 2,
        knowledge_workspace_id: get().creationWorkspaceId || undefined,
      });
      if (get().sessionVersion !== version) return;
      set({
        activeChoiceGroup: group,
        isGeneratingChoices: false,
        choiceGroupGenerationProgress: null,
        activeDraft: null,
        activeDraftType: null,
        lastActionMessageToken: group.status === 'failed'
          ? 'store.errors.generatingPlansFailed'
          : 'store.project.plansGeneratedCount',
        lastActionMessageTokenInterpolation: group.status === 'failed'
          ? null
          : {
              key: 'store.project.plansGeneratedCount',
              values: { count: group.successCount || 0 },
            },
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({
        error: err instanceof Error ? err.message : 'store.project.generatingPlansFailed',
        isGeneratingChoices: false,
        choiceGroupGenerationProgress: null,
      });
    }
  },

  acceptOnboardingChoice: async (choiceId) => {
    const version = get().sessionVersion;
    const group = get().activeChoiceGroup;
    if (!group) return null;
    set({ isLoading: true, error: null });
    try {
      const res = await workspaceApi.acceptProjectCreationChoice(group.id, choiceId);
      if (get().sessionVersion !== version) return null;
      const projectId = res.projectId ?? res.project_id;
      if (!projectId) {
        throw new Error('project_id_missing');
      }
      set({
        activeChoiceGroup: null,
        activeDraft: null,
        activeDraftType: null,
        creationWorkspaceId: null,
        creationDocuments: [],
      });
      const opened = await get().openWorkspace(String(projectId));
      if (!opened) return null;
      set({ lastActionMessageToken: 'store.project.createdSuccess' });
      // Reload open groups since this one is resolved
      void get().loadOpenOnboardingChoiceGroups();
      return String(projectId);
    } catch (err) {
      if (get().sessionVersion !== version) return null;
      set({ error: err instanceof Error ? err.message : 'store.project.adoptPlanFailed', isLoading: false });
      return null;
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
          lastActionMessageToken: 'store.project.candidateClosed',
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
      const opened = await get().openWorkspace(String(projectId));
      if (!opened) return null;
      set({
        activeChoiceGroup: null,
        isLoading: false,
        lastActionMessageToken: 'store.project.blankProjectCreated',
      });
      void get().loadOpenOnboardingChoiceGroups();
      return String(projectId);
    } catch (err) {
      if (get().sessionVersion !== version) return null;
      set({
        error: err instanceof Error ? err.message : 'store.project.deferFailed',
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
      // Silently fail because this is a background refresh.
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
      set({ error: 'store.project.restoreDraftFailed' });
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
        lastActionMessageToken: 'store.project.existingCandidatesOpened',
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

    let effectiveCandidateCount = candidateCount;
    let candidateLabels: string[] = [];

    if (effectiveCandidateCount === undefined) {
      try {
        const projectConfiguration = await workspaceApi.getProjectConfiguration(projectId);
        const strategyConfig = projectConfiguration?.generation_strategy;
        effectiveCandidateCount = strategyConfig?.candidate_count;
        candidateLabels = (strategyConfig?.strategies || [])
          .filter((strategy: any) => strategy.enabled)
          .slice(0, effectiveCandidateCount)
          .map((strategy: any) => getGenerationStrategyPresentation(strategy, i18n.t).label);
        set({ projectConfiguration });
      } catch {
        // Keep generation available when the configuration summary cannot be loaded.
      }
    }

    const version = get().sessionVersion;
    set({
      isGeneratingChoices: true,
      error: null,
      choiceGroupGenerationProgress: buildInitialChoiceProgress(effectiveCandidateCount, candidateLabels),
      lastActionMessageToken: 'store.project.generatingCandidates',
    });

    try {
      if (conflictingGroup && forceReplace) {
        await workspaceApi.discardChoiceGroup(projectId, Number(conflictingGroup.id));
        if (get().sessionVersion !== version) return null;
        set((state: WorkspaceState) => ({
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
        candidate_count: candidateCount,
        user_feedback: userFeedback || null,
      });
      if (get().sessionVersion !== version) return null;
      set((state: WorkspaceState) => ({
        ...syncChoiceGroupToWorkspace(group, state),
        isGeneratingChoices: false,
        activeDraft: null,
        activeDraftType: null,
        pendingGenerationConflict: null,
        choiceGroupGenerationProgress: null,
        lastActionMessageToken: 'store.project.candidatesGenerated',
      }));
      return group;
    } catch (err) {
      if (get().sessionVersion !== version) return null;
      if (err instanceof Error && err.message === GENERATION_CONFLICT_PENDING_ERROR) {
        set({ isGeneratingChoices: false, choiceGroupGenerationProgress: null });
        return null;
      }
      set({
        error: err instanceof Error ? err.message : 'store.project.generatingCandidatesFailed',
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
        project_description: description,
        knowledge_workspace_id: get().creationWorkspaceId || undefined,
      });
      if (get().sessionVersion !== version) return null;
      const projectId = res.projectId ?? res.project_id;
      if (!projectId) {
        throw new Error('project_id_missing');
      }
      set({
        creationWorkspaceId: null,
        creationDocuments: [],
      });
      const opened = await get().openWorkspace(String(projectId));
      if (!opened) return null;
      set({ lastActionMessageToken: 'store.project.blankWorkspaceInitialized' });
      return String(projectId);
    } catch (err) {
      if (get().sessionVersion !== version) return null;
      set({ error: err instanceof Error ? err.message : 'store.project.createBlankFailed', isLoading: false });
      return null;
    }
  },

  initCreationWorkspace: async () => {
    await get().loadKnowledgeConfig();
    if (!get().knowledgeBaseEnabled) return;
    if (get().creationWorkspaceId) return;
    try {
      const ws = await workspaceApi.createKnowledgeWorkspace();
      set({ creationWorkspaceId: ws.public_id || (ws as any).publicId, creationDocuments: [] });
    } catch (err) {
      console.error('Failed to initialize creation knowledge workspace', err);
    }
  },

  loadKnowledgeConfig: async () => {
    try {
      const config = await workspaceApi.getKnowledgeConfig();
      set({ knowledgeBaseEnabled: config.enabled });
    } catch (err) {
      console.error('Failed to load knowledge base configuration', err);
    }
  },

  loadCreationDocuments: async () => {
    const wsId = get().creationWorkspaceId;
    if (!wsId) return;
    try {
      const docs = await workspaceApi.listWorkspaceDocuments(wsId);
      set({ creationDocuments: docs });
    } catch (err) {
      console.error('Failed to load creation documents', err);
    }
  },

  uploadCreationDocument: async (file: File) => {
    const wsId = get().creationWorkspaceId;
    if (!wsId) return;
    set({ isUploadingDocument: true, error: null });
    try {
      await workspaceApi.uploadWorkspaceDocument(wsId, file);
      await get().loadCreationDocuments();
      set({ isUploadingDocument: false });
    } catch (err) {
      set({ 
        isUploadingDocument: false,
        error: err instanceof Error ? err.message : 'store.knowledge.uploadFailed'
      });
    }
  },

  deleteCreationDocument: async (docId: string) => {
    const wsId = get().creationWorkspaceId;
    if (!wsId) return;
    set({ error: null });
    try {
      await workspaceApi.deleteWorkspaceDocument(wsId, docId);
      await get().loadCreationDocuments();
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'store.knowledge.deleteFailed' });
    }
  },

  retryCreationDocument: async (docId: string) => {
    const wsId = get().creationWorkspaceId;
    if (!wsId) return;
    set({ error: null });
    try {
      await workspaceApi.retryWorkspaceDocument(wsId, docId);
      await get().loadCreationDocuments();
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'store.knowledge.retryParseFailed' });
    }
  },

  loadProjectDocuments: async () => {
    await get().loadKnowledgeConfig();
    if (!get().knowledgeBaseEnabled) return;
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    try {
      const docs = await workspaceApi.listProjectDocuments(projectId);
      set({ projectDocuments: docs });
    } catch (err) {
      console.error('Failed to load project documents', err);
    }
  },

  uploadProjectDocument: async (file: File) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ isUploadingDocument: true, error: null });
    try {
      await workspaceApi.uploadProjectDocument(projectId, file);
      await get().loadProjectDocuments();
      set({ isUploadingDocument: false, lastActionMessageToken: 'store.knowledge.uploadSuccess' });
    } catch (err) {
      set({ 
        isUploadingDocument: false,
        error: err instanceof Error ? err.message : 'store.knowledge.uploadFailed'
      });
    }
  },

  deleteProjectDocument: async (docId: string) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ error: null });
    try {
      await workspaceApi.deleteProjectDocument(projectId, docId);
      await get().loadProjectDocuments();
      set({ lastActionMessageToken: 'store.knowledge.deleteSuccess' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'store.knowledge.deleteFailed' });
    }
  },

  retryProjectDocument: async (docId: string) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ error: null });
    try {
      await workspaceApi.retryProjectDocument(projectId, docId);
      await get().loadProjectDocuments();
      set({ lastActionMessageToken: 'store.knowledge.reparseTriggered' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'store.knowledge.retryParseFailed' });
    }
  },

  toggleDocumentAI: async (docId: string, enabled: boolean) => {
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ error: null });
    try {
      await workspaceApi.patchProjectDocument(projectId, docId, { ai_enabled: enabled });
      await get().loadProjectDocuments();
      set({ lastActionMessageToken: enabled ? 'store.knowledge.aiSearchEnabled' : 'store.knowledge.aiSearchDisabled' });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'store.knowledge.toggleAIFailed' });
    }
  },

  fetchProjectConfiguration: async (projectId: string) => {
    set({ isLoadingProjectConfiguration: true, error: null });
    try {
      const config = await workspaceApi.getProjectConfiguration(projectId);
      set({ projectConfiguration: config, isLoadingProjectConfiguration: false });
    } catch (err) {
      set({
        isLoadingProjectConfiguration: false,
        error: err instanceof Error ? err.message : 'store.strategies.loadFailed',
      });
    }
  },

  updateProjectGenerationStrategies: async (projectId: string, payload: any) => {
    set({ isSavingGenerationStrategies: true, error: null });
    try {
      await workspaceApi.updateProjectGenerationStrategies(projectId, payload);
      const config = await workspaceApi.getProjectConfiguration(projectId);
      set({
        projectConfiguration: config,
        isSavingGenerationStrategies: false,
        lastActionMessageToken: 'store.strategies.saveSuccess',
      });
    } catch (err) {
      set({ isSavingGenerationStrategies: false });
      throw err;
    }
  },

  deleteProjectGenerationStrategies: async (projectId: string) => {
    set({ isSavingGenerationStrategies: true, error: null });
    try {
      await workspaceApi.deleteProjectGenerationStrategies(projectId);
      const config = await workspaceApi.getProjectConfiguration(projectId);
      set({
        projectConfiguration: config,
        isSavingGenerationStrategies: false,
        lastActionMessageToken: 'store.strategies.resetSuccess',
      });
    } catch (err) {
      set({ isSavingGenerationStrategies: false });
      throw err;
    }
  },

  updateProjectKnowledgeConfig: async (projectId: string, payload: { enabled: boolean }) => {
    set({ error: null });
    try {
      await workspaceApi.updateProjectKnowledgeConfig(projectId, payload);
      const config = await workspaceApi.getProjectConfiguration(projectId);
      set({ projectConfiguration: config });
    } catch (err) {
      throw err;
    }
  },

  updateProjectConfiguration: async (projectId: string, payload: { content_locale: string | null }) => {
    set({ error: null });
    try {
      const config = await workspaceApi.updateProjectConfiguration(projectId, payload);
      set({ projectConfiguration: config });
    } catch (err) {
      throw err;
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
      set({ activeDraft: draft, activeDraftType: 'actor', isGeneratingChoices: false, isGenerating: false, lastActionMessageToken: 'store.actor.listGenerated' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.actor.generateFailed';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
    }
  },

  regenerateActors: async (feedback) => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isGenerating: true, error: null, lastActionMessageToken: 'store.actor.regeneratingList' });
    try {
      let updated;
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        updated = await workspaceApi.regenerateSlotFillingDraft(draftId, feedback);
      } else {
        updated = await workspaceApi.regenerateActorGenerationDraft(draftId, feedback);
      }
      if (get().sessionVersion !== version) return;
      set({ activeDraft: updated, isGenerating: false, lastActionMessageToken: 'store.actor.draftRegenerated' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.actor.regenerateFailed';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessageToken: friendlyMsg, isGenerating: false });
      } else {
        set({ error: errMsg, lastActionMessageToken: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmActors: async () => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isLoading: true, error: null, lastActionMessageToken: 'store.actor.applyingDraft' });
    try {
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        await workspaceApi.confirmSlotFillingDraft(draftId);
      } else {
        await workspaceApi.confirmActorGenerationDraft(draftId);
      }
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessageToken: 'store.actor.draftApplied' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.actor.confirmFailed';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessageToken: friendlyMsg, isLoading: false });
      } else {
        set({ error: errMsg, lastActionMessageToken: friendlyMsg, isLoading: false });
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
        lastActionMessageToken: 'store.feature.treeGenerated',
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.feature.generateFailed';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
    }
  },

  regenerateFeatures: async (feedback) => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isGenerating: true, error: null, lastActionMessageToken: 'store.feature.regeneratingTree' });
    try {
      let updated;
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        updated = await workspaceApi.regenerateSlotFillingDraft(draftId, feedback);
      } else {
        updated = await workspaceApi.regenerateFeatureGenerationDraft(draftId, feedback);
      }
      if (get().sessionVersion !== version) return;
      set({ activeDraft: updated, isGenerating: false, lastActionMessageToken: 'store.feature.draftRegenerated' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.feature.regenerateFailed';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessageToken: friendlyMsg, isGenerating: false });
      } else {
        set({ error: errMsg, lastActionMessageToken: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmFeatures: async () => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isLoading: true, error: null, lastActionMessageToken: 'store.feature.applyingTree' });
    try {
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        await workspaceApi.confirmSlotFillingDraft(draftId);
      } else {
        await workspaceApi.confirmFeatureGenerationDraft(draftId);
      }
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessageToken: 'store.feature.treeApplied' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.feature.confirmFailed';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessageToken: friendlyMsg, isLoading: false });
      } else {
        set({ error: errMsg, lastActionMessageToken: friendlyMsg, isLoading: false });
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
        lastActionMessageToken: 'store.flow.flowAndObjectsGenerated',
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.flow.generateFailed';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
    }
  },

  regenerateFlowsAndObjects: async (feedback) => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isGenerating: true, error: null, lastActionMessageToken: 'store.flow.regeneratingFlow' });
    try {
      const updated = isSlotFillingDraft(draft)
        ? await workspaceApi.regenerateSlotFillingDraft(draftId, feedback)
        : await workspaceApi.regenerateFlowGenerationDraft(draftId, feedback);
      if (get().sessionVersion !== version) return;
      set({ activeDraft: updated, activeDraftType: 'flow', isGenerating: false, lastActionMessageToken: 'store.flow.draftRegenerated' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.flow.regenerateFailed';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessageToken: friendlyMsg, isGenerating: false });
      } else {
        set({ error: errMsg, lastActionMessageToken: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmFlowsAndObjects: async () => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft) return;
    const draftId = draft.draftId || draft.draft_id;
    if (!draftId) return;
    set({ isLoading: true, error: null, lastActionMessageToken: 'store.flow.applyingFlow' });
    try {
      if (isSlotFillingDraft(draft)) {
        await workspaceApi.confirmSlotFillingDraft(draftId);
      } else {
        await workspaceApi.confirmFlowGenerationDraft(draftId);
      }
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessageToken: 'store.flow.flowApplied' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.flow.confirmFailed';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessageToken: friendlyMsg, isLoading: false });
      } else {
        set({ error: errMsg, lastActionMessageToken: friendlyMsg, isLoading: false });
      }
    }
  },

  generateScenarios: async (featureIds, forceReplace = false) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    const isSingleTarget = featureIds !== undefined && featureIds !== null && (
      !Array.isArray(featureIds) || featureIds.length === 1
    );
    const targetFeatureId = isSingleTarget
      ? (Array.isArray(featureIds) ? featureIds[0] : featureIds)
      : null;
    const targetFeatureIds = Array.isArray(featureIds) ? featureIds : (featureIds ? [featureIds] : []);
    const generationTarget = isSingleTarget
      ? { generation_mode: 'single', feature_id: targetFeatureId }
      : targetFeatureIds.length > 0
        ? { generation_mode: 'batch', feature_ids: targetFeatureIds }
        : { generation_mode: 'full' };

    try {
      const group = await get().createGenerationChoiceGroup({
        projectId: pId,
        generationType: 'scenario',
        target: generationTarget,
        candidateCount: targetFeatureIds.length > 25 ? 1 : undefined,
        forceReplace,
        conflictAction: 'generateScenarios',
        conflictArgs: { featureIds },
      });
      if (get().sessionVersion !== version) return;
      if (group || get().pendingGenerationConflict) return;
      if (get().error) return;
    } catch (err) {
      if (get().sessionVersion !== version) return;
      if (get().pendingGenerationConflict) return;
      if (!(err instanceof Error) || err.message !== 'choice_group_disabled') {
        set({ error: err instanceof Error ? err.message : 'store.project.generatingCandidatesFailed' });
        return;
      }
    }

    // Use the legacy draft path only when choice groups are explicitly disabled.
    set({ isGenerating: true, error: null, lastActionMessageToken: 'store.scenario.generatingDraft' });
    try {
      if (Array.isArray(featureIds)) {
        if (featureIds.length === 0) {
          const draft = await workspaceApi.createScenarioGenerationDraft(pId);
          if (get().sessionVersion !== version) return;
          set({ activeDraft: draft, activeDraftType: 'scenario', isGenerating: false, lastActionMessageToken: 'store.scenario.draftGenerated' });
        } else if (featureIds.length === 1) {
          const draft = await workspaceApi.createScenarioGenerationDraft(pId, featureIds[0]);
          if (get().sessionVersion !== version) return;
          set({ activeDraft: draft, activeDraftType: 'scenario', isGenerating: false, lastActionMessageToken: 'store.scenario.draftGenerated' });
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
          set({ activeDraft: combinedDraft, activeDraftType: 'scenario', isGenerating: false, lastActionMessageToken: 'store.scenario.combinedDraftGenerated' });
        }
      } else {
        const draft = await workspaceApi.createScenarioGenerationDraft(pId, featureIds);
        if (get().sessionVersion !== version) return;
        set({ activeDraft: draft, activeDraftType: 'scenario', isGenerating: false, lastActionMessageToken: 'store.scenario.draftGenerated' });
      }
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.finding.generateFailed';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
    }
  },

  regenerateScenarios: async (feedback) => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isGenerating: true, error: null, lastActionMessageToken: 'store.finding.generatingScenario' });
    try {
      let updated;
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        updated = await workspaceApi.regenerateSlotFillingDraft(draftId, feedback);
      } else {
        updated = await workspaceApi.regenerateScenarioGenerationDraft(draftId, feedback);
      }
      if (get().sessionVersion !== version) return;
      set({ activeDraft: updated, isGenerating: false, lastActionMessageToken: 'store.finding.draftScenarioRegenerated' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.finding.regenerateFailed';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessageToken: friendlyMsg, isGenerating: false });
      } else {
        set({ error: errMsg, lastActionMessageToken: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmScenarios: async (generateAc) => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft) return;
    set({ isLoading: true, error: null, lastActionMessageToken: 'store.finding.applyingScenario' });
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
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessageToken: 'store.finding.scenarioApplied' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.finding.updateFailed';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessageToken: friendlyMsg, isLoading: false });
      } else {
        set({ error: errMsg, lastActionMessageToken: friendlyMsg, isLoading: false });
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
        lastActionMessageToken: 'store.finding.scenarioACGenerated',
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.finding.generateFailed';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
    }
  },

  regenerateAcceptanceCriteria: async (feedback) => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isGenerating: true, error: null, lastActionMessageToken: 'store.finding.generatingAC' });
    try {
      let updated;
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        updated = await workspaceApi.regenerateSlotFillingDraft(draftId, feedback);
      } else {
        updated = await workspaceApi.regenerateAcceptanceCriteriaGenerationDraft(draftId, feedback);
      }
      if (get().sessionVersion !== version) return;
      set({ activeDraft: updated, isGenerating: false, lastActionMessageToken: 'store.finding.acDraftRegenerated' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.finding.regenerateFailed';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessageToken: friendlyMsg, isGenerating: false });
      } else {
        set({ error: errMsg, lastActionMessageToken: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmAcceptanceCriteria: async () => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || (!draft.draft_id && !draft.draftId)) return;
    const draftId = draft.draftId || draft.draft_id;
    set({ isLoading: true, error: null, lastActionMessageToken: 'store.finding.applyingAC' });
    try {
      if (draft.perceptionJobId !== undefined || draft.perception_job_id !== undefined) {
        await workspaceApi.confirmSlotFillingDraft(draftId);
      } else {
        await workspaceApi.confirmAcceptanceCriteriaGenerationDraft(draftId);
      }
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessageToken: 'store.finding.acApplied' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.finding.updateFailed';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessageToken: friendlyMsg, isLoading: false });
      } else {
        set({ error: errMsg, lastActionMessageToken: friendlyMsg, isLoading: false });
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
        lastActionMessageToken: 'store.finding.kanoGenerated',
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.finding.generateFailed';
      set({ error: errMsg, isGenerating: false, isGeneratingChoices: false });
    }
  },

  regenerateScope: async (feedback) => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isGenerating: true, error: null, lastActionMessageToken: 'store.finding.generatingKano' });
    try {
      const updated = await workspaceApi.regenerateScopeGenerationDraft(draft.draft_id, feedback);
      if (get().sessionVersion !== version) return;
      set({ activeDraft: updated, isGenerating: false, lastActionMessageToken: 'store.finding.kanoDraftRegenerated' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.finding.regenerateFailed';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessageToken: friendlyMsg, isGenerating: false });
      } else {
        set({ error: errMsg, lastActionMessageToken: friendlyMsg, isGenerating: false });
      }
    }
  },

  confirmScope: async () => {
    const version = get().sessionVersion;
    const draft = get().activeDraft;
    if (!draft || !draft.draft_id) return;
    set({ isLoading: true, error: null, lastActionMessageToken: 'store.finding.applyingKano' });
    try {
      await workspaceApi.confirmScopeGenerationDraft(draft.draft_id);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ activeDraft: null, activeDraftType: null, isLoading: false, lastActionMessageToken: 'store.finding.kanoApplied' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.finding.updateFailed';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      if (errMsg === 'draft_not_found') {
        set({ activeDraft: null, activeDraftType: null, error: errMsg, lastActionMessageToken: friendlyMsg, isLoading: false });
      } else {
        set({ error: errMsg, lastActionMessageToken: friendlyMsg, isLoading: false });
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
      set({ activeDraft: null, activeDraftType: null, lastActionMessageToken: 'store.finding.discardDraftSuccess' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.finding.discardFailed' });
    }
  },

  skipKano: async () => {
    const version = get().sessionVersion;
    const ir = get().ir;
    if (!ir || !ir.projectId) return;
    set({ isLoading: true, error: null, lastActionMessageToken: 'store.finding.skippingKano' });
    try {
      await workspaceApi.skipKano(ir.projectId);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ isLoading: false, lastActionMessageToken: 'store.finding.kanoSkipped' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.finding.updateFailed';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      set({ error: errMsg, lastActionMessageToken: friendlyMsg, isLoading: false });
    }
  },

  resetKano: async () => {
    const version = get().sessionVersion;
    const ir = get().ir;
    if (!ir || !ir.projectId) return;
    set({ isLoading: true, error: null, lastActionMessageToken: 'store.finding.resettingKano' });
    try {
      await workspaceApi.resetKano(ir.projectId);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ isLoading: false, lastActionMessageToken: 'store.finding.kanoReset' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.finding.updateFailed';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      set({ error: errMsg, lastActionMessageToken: friendlyMsg, isLoading: false });
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
      set({
        lastActionMessageToken: 'store.actor.createSuccess',
        lastActionMessageTokenInterpolation: { key: 'store.actor.createSuccess', values: { name } },
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.actor.updateFailed' });
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
      set({ lastActionMessageToken: 'store.actor.updateSuccess' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: 'store.actor.parallelConflict' });
      } else {
        set({ error: err instanceof Error ? err.message : 'store.actor.updateFailed' });
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
      set((s: WorkspaceState) => {
        const isSelected = s.selectedObjectId === actorId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessageToken: 'store.actor.deleteSuccess'
        };
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.actor.deleteFailed' });
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
      set({
        lastActionMessageToken: 'store.feature.createSuccessWithName',
        lastActionMessageTokenInterpolation: { key: 'store.feature.createSuccessWithName', values: { name } },
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.feature.updateFailed' });
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
      set({ lastActionMessageToken: 'store.feature.updateSuccess' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: 'store.feature.parallelConflict' });
      } else {
        set({ error: err instanceof Error ? err.message : 'store.feature.updateFailed' });
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
      set((s: WorkspaceState) => {
        const isSelected = s.selectedObjectId === featureId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessageToken: 'store.feature.deleteSubtreeSuccess'
        };
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.feature.updateFailed' });
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
      set({
        lastActionMessageToken: 'store.scenario.createSuccess',
        lastActionMessageTokenInterpolation: { key: 'store.scenario.createSuccess', values: { name } },
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.finding.generateFailed' });
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
      set({ lastActionMessageToken: 'store.scenario.updateSuccess' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: 'store.scenario.parallelConflict' });
      } else {
        set({ error: err instanceof Error ? err.message : 'store.finding.updateFailed' });
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
      set((s: WorkspaceState) => {
        const isSelected = s.selectedObjectId === scenarioId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessageToken: 'store.finding.deleteSuccess'
        };
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.finding.deleteFailed' });
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
      set({ lastActionMessageToken: 'store.ac.createSuccess' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.finding.generateFailed' });
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
      set({ lastActionMessageToken: 'store.ac.updateSuccess' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: 'store.ac.parallelConflict' });
      } else {
        set({ error: err instanceof Error ? err.message : 'store.finding.updateFailed' });
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
      set((s: WorkspaceState) => {
        const isSelected = s.selectedObjectId === criterionId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessageToken: 'store.ac.deleteSuccess'
        };
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.finding.deleteFailed' });
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
    set({ lastActionMessageToken: 'store.bo.createSuccess' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.finding.generateFailed' });
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
      set({ lastActionMessageToken: 'store.bo.updateSuccess' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: 'store.bo.parallelConflict' });
      } else {
        set({ error: err instanceof Error ? err.message : 'store.finding.updateFailed' });
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
      set({ boDeletionError: 'store.bo.deletionRefError' });
      return;
    }

    try {
      await workspaceApi.deleteBusinessObject(pId, id);
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set((s: WorkspaceState) => {
        const isSelected = s.selectedObjectId === id;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessageToken: 'store.bo.deleteSuccess',
          boDeletionError: null
        };
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : '';
      if (errMsg.includes('business_object_in_use')) {
        set({ boDeletionError: 'store.bo.deletionRefError' });
      } else {
        set({ error: errMsg || 'store.finding.deleteFailed' });
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
      set({
        lastActionMessageToken: 'store.bo.addFieldSuccessWithName',
        lastActionMessageTokenInterpolation: { key: 'store.bo.addFieldSuccessWithName', values: { name } },
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.bo.addFieldFailed' });
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
      set({ lastActionMessageToken: 'store.bo.updateFieldSuccess' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: 'store.bo.fieldParallelConflict' });
      } else {
        set({ error: err instanceof Error ? err.message : 'store.bo.updateFieldFailed' });
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
      set((s: WorkspaceState) => {
        const isSelected = s.selectedObjectId === attrId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessageToken: 'store.bo.deleteFieldSuccess'
        };
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.bo.deleteFieldFailed' });
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
      set({
        lastActionMessageToken: 'store.flow.createSuccessWithName',
        lastActionMessageTokenInterpolation: { key: 'store.flow.createSuccessWithName', values: { name } },
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
    set({ error: err instanceof Error ? err.message : 'store.flow.createFailed' });
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
      set({ lastActionMessageToken: 'store.flow.updateSuccess' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: 'store.flow.parallelConflict' });
      } else {
    set({ error: err instanceof Error ? err.message : 'store.flow.updateFailed' });
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
      set((s: WorkspaceState) => {
        const isSelected = s.selectedObjectId === flowId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessageToken: 'store.flow.deleteSuccess'
        };
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
    set({ error: err instanceof Error ? err.message : 'store.flow.deleteFailed' });
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
      set({ lastActionMessageToken: 'store.flowStep.loadSuccess' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.flowStep.loadFailed' });
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
      set({ lastActionMessageToken: 'store.flowStep.updateSuccess' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: 'store.flowStep.parallelConflict' });
      } else {
        set({ error: err instanceof Error ? err.message : 'store.flowStep.updateFailed' });
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
      set((s: WorkspaceState) => {
        const isSelected = s.selectedObjectId === stepId;
        return {
          selectedObjectId: isSelected ? null : s.selectedObjectId,
          selectedObject: isSelected ? null : s.selectedObject,
          lastActionMessageToken: 'store.flowStep.deleteSuccess'
        };
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.flowStep.deleteFailed' });
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
      set({ lastActionMessageToken: 'store.flowStep.sortSuccess' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.flowStep.sortFailed' });
    }
  },

  // Scope (Kano) CRUD
  updateScope: async (featureId, updates) => {
    const version = get().sessionVersion;
    const pId = withWorkspaceId(get());
    const feature = (get().ir?.features || []).find((x: any) => x.featureId === featureId);
    try {
      await workspaceApi.updateScope(pId, featureId, {
        status: updates.scopeStatus || feature?.scope?.scopeStatus || 'current',
        reason: updates.reason ?? feature?.scope?.reason ?? '',
        positive_summary: updates.positiveSummary,
        negative_summary: updates.negativeSummary,
        last_seen_updated_at: feature?.scope?.updatedAt
      });
      if (get().sessionVersion !== version) return;
      await get().refreshWorkspace();
      if (get().sessionVersion !== version) return;
      set({ lastActionMessageToken: 'store.scope.updateSuccess' });
    } catch (err: any) {
      if (get().sessionVersion !== version) return;
      if (err?.status === 409) {
        set({ error: 'store.scope.parallelConflict' });
      } else {
        set({ error: err instanceof Error ? err.message : 'store.scope.updateFailed' });
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
      set((s: WorkspaceState) => ({
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
        lastActionMessageToken: 'store.finding.deleteSuccess'
      }));
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const errMsg = err instanceof Error ? err.message : 'store.finding.deleteFailed';
      const friendlyMsg = getFriendlyErrorMessage(errMsg);
      set({ error: errMsg, lastActionMessageToken: friendlyMsg, isLoading: false });
    }
  },

  openSlot: (slotId) => {
    const numId = parseInt(slotId, 10);
    const space = get().ir;
    if (space?.perceptionSlot?.id === slotId) {
      set({ selectedSlotId: numId, selectedObject: space.perceptionSlot, selectedObjectId: numId });
    }
  },
  expandSlot: async (slotId) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    const numId = parseInt(slotId, 10);
    const slot = get().ir?.perceptionSlot;
    if (!slot || slot.id !== slotId) return;

    set({ isGenerating: true, error: null, lastActionMessageToken: 'store.finding.slotFilling' });
    try {
      let fillerKind: 'actor' | 'feature' | 'flow' | 'scenario' | 'ac' | null = null;
      const kindText = slot.perceptionKind ? slot.perceptionKind.toUpperCase() : '';
      if (kindText === '角色结点' || kindText === 'ACTOR') fillerKind = 'actor';
      else if (kindText === '功能模块结点' || kindText === '功能叶子结点' || kindText === 'FEATURE') fillerKind = 'feature';
      else if (kindText === '流程主结点' || kindText === '流程主节点' || kindText === 'FLOW') fillerKind = 'flow';
      else if (kindText === '场景结点' || kindText === 'SCENARIO') fillerKind = 'scenario';
      else if (kindText === '成功标准结点' || kindText === 'ACCEPTANCE_CRITERION' || kindText === 'AC' || kindText === 'ac') fillerKind = 'ac';

      if (!fillerKind) {
        throw new Error('store.finding.unknownKind');
      }

      const draft = await workspaceApi.createSlotFillingDraft(projectId, numId, fillerKind);
      if (get().sessionVersion !== version) return;
      set({
        activeDraft: draft,
        activeDraftType: fillerKind,
        isGenerating: false,
        lastActionMessageToken: 'store.finding.slotFilled'
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({
        error: err instanceof Error ? err.message : 'store.finding.slotFillFailed',
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
        lastActionMessageToken: 'store.finding.adoptSuccess',
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.finding.adoptFailed', isLoading: false });
    }
  },
  regenerateChoiceGroup: async (groupId, feedback) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ isGeneratingChoices: true, error: null, lastActionMessageToken: 'store.finding.regeneratingPlan' });
    try {
      const newGroup = await workspaceApi.regenerateChoiceGroup(projectId, groupId, feedback);
      if (get().sessionVersion !== version) return;
      set({ activeChoiceGroup: newGroup, isGeneratingChoices: false, activeDraft: null, activeDraftType: null,
        lastActionMessageToken: 'store.finding.planGroupRegenerated',
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.finding.regenerateFailed', isGeneratingChoices: false });
    }
  },
  regenerateChoice: async (choiceId, feedback) => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    set({ isGeneratingChoices: true, error: null, lastActionMessageToken: 'store.finding.regeneratingPlan' });
    try {
      const updatedGroup = await workspaceApi.regenerateChoice(projectId, choiceId, feedback);
      if (get().sessionVersion !== version) return;
      set({ activeChoiceGroup: updatedGroup, isGeneratingChoices: false,
        lastActionMessageToken: 'store.finding.planRegenerated',
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.finding.regenerateFailed', isGeneratingChoices: false });
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
      set({ selectedObject: null, selectedObjectId: null, isLoading: false, lastActionMessageToken: 'store.finding.rejectSuccess' });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.finding.rejectFailed', isLoading: false });
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
        set({ activeChoiceGroup: null, isLoading: false, lastActionMessageToken: 'store.finding.discardSuccess' });
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
        set({ error: 'store.finding.issueNotFound', lastActionMessageToken: 'store.finding.issueNotFound', isLoading: false });
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
      return slot ? slot.id : null;
    } catch (err) {
      if (get().sessionVersion !== version) return null;
      const msg = (err as any)?.detail || (err instanceof Error ? err.message : 'store.finding.processIssueFailed');
      set({ error: msg, lastActionMessageToken: msg, isLoading: false });
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
          const msg = res.status === 'stale' ? 'store.finding.draftExpired' : 'store.finding.draftInvalid';
        set({ isLoading: false, lastActionMessageToken: msg, error: msg });
        return res;
      }
      set({
        isLoading: false,
        lastActionMessageToken: 'store.finding.fixApplied',
        activeDraft: null,
        activeDraftType: null,
      });
      const rIds = res.resolvedIssueIds || res.resolved_issue_ids;
      if (res && rIds && rIds.length > 0) {
        set({ lastActionMessageToken: 'store.finding.issuesResolved' });
      }
      return res;
    } catch (err) {
      if (get().sessionVersion !== version) return null;
      const msg = (err as any)?.response?.data?.detail || (err instanceof Error ? err.message : 'store.finding.applyFixFailed');
      set({ error: msg, lastActionMessageToken: msg, isLoading: false });
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
      set({ isLoading: false, lastActionMessageToken: 'store.finding.discardDraftSuccess', activeDraft: null, activeDraftType: null });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      const msg = (err as any)?.response?.data?.detail || (err instanceof Error ? err.message : 'store.finding.discardFixFailed');
      set({ error: msg, lastActionMessageToken: msg, isLoading: false });
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
        lastActionMessageToken: 'store.finding.fixSuggestionsRegenerated',
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({ error: err instanceof Error ? err.message : 'store.finding.regenerateFailed', isLoading: false });
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
      set({ error: err instanceof Error ? err.message : 'store.finding.updateNodeStatusFailed' });
    }
  },
  setScopeStatus: async (nodeId, scopeStatus) => {
    const featId = parseInt(nodeId, 10);
    if (!isNaN(featId)) {
      await get().updateScope(featId, { scopeStatus });
    }
  },
  runDiagnosis: async (stage?: 'what' | 'how' | 'scope') => {
    const version = get().sessionVersion;
    const projectId = get().ir?.projectId;
    if (!projectId) return;
    
    let targetStage: string = stage || 'what';
    if (!stage) {
      const activePage = get().activePage;
      if (activePage === '/flow') targetStage = 'how';
      else if (activePage === '/scope') targetStage = 'scope';
      else if (activePage === '/preview') targetStage = 'scope';
      else targetStage = 'what';
    }

    set({ isDiagnosing: true, error: null });
    try {
      let res = await workspaceApi.rediagnoseNextSuggestion(projectId, targetStage);
      if (get().sessionVersion !== version) return;
      set((s: WorkspaceState) => ({
        nextSuggestions: {
          ...s.nextSuggestions,
          [targetStage]: res.suggestion
        },
        lastActionMessageToken: 'store.finding.slotFilling'
      }));

      // If the suggestion is in 'running' state, poll until it's finished or failed
      if (res.suggestion && res.suggestion.status === 'running') {
        while (res.suggestion?.status === 'running') {
          // Wait 2 seconds before polling again
          await new Promise((resolve) => setTimeout(resolve, 2000));
          if (get().sessionVersion !== version) return;
          
          // Poll the rediagnosis chain so the next perceptron starts after an empty result.
          res = await workspaceApi.getRediagnoseStatus(projectId, targetStage);
          if (get().sessionVersion !== version) return;
          
          set((s: WorkspaceState) => ({
            nextSuggestions: {
              ...s.nextSuggestions,
              [targetStage]: res.suggestion
            }
          }));

          // Break loop if suggestion is ready, failed, or null
          if (!res.suggestion || res.suggestion.status !== 'running') {
            break;
          }
        }
      }

      if (get().sessionVersion !== version) return;
      if (res.suggestion?.status === 'failed') {
        throw new Error(res.suggestion.description || 'store.finding.diagnosisFailed');
      }
      set({
        isDiagnosing: false,
        lastActionMessageToken: res.suggestion?.sourceType === 'perception_slot'
          ? 'store.finding.fixSuggestionsRegenerated'
          : 'store.finding.noSuggestions'
      });
      await get().refreshWorkspace();
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({
        error: err instanceof Error ? err.message : 'store.finding.diagnosisFailed',
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
        lastActionMessageToken: 'store.finding.autoModelingSuccess'
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({
        isLoading: false,
        lastActionMessageToken: 'store.finding.generateFailed'
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
          lastActionMessageToken: 'store.finding.selectModuleForImpact'
        });
        return;
      }

      const res = await workspaceApi.impactPreview(projectId, targetFeatureId, 'postponed');
      if (get().sessionVersion !== version) return;
      
      const scenarioCount = res.affectedScenarios?.length || 0;
      const flowCount = res.affectedFlows?.length || 0;
      const boCount = res.affectedBusinessObjects?.length || 0;

      set({
        isLoading: false,
        lastActionMessageToken: 'store.finding.impactEvaluated'
      });
    } catch (err) {
      if (get().sessionVersion !== version) return;
      set({
        isLoading: false,
        lastActionMessageToken: 'store.finding.updateFailed'
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
          error: err instanceof Error ? err.message : 'store.finding.updateFailed',
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
      lastActionMessageToken:
        updates?.status === 'ignored'
          ? 'store.finding.issueIgnored'
          : updates?.status === 'resolved'
            ? 'store.finding.issueStatusUpdated'
            : 'store.finding.issueUpdated'
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
