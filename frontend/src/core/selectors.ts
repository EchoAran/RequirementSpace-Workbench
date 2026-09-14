import type {
  RequirementSpace,
  FeatureNode,
  FlowStepNode,
  Finding,
  NodeStatus,
  Stage,
  FlowNode,
  FlowTransition,
  DomainRule,
} from '@/core/schema';
import {
  findingProjection,
  findingStage,
  isCountableFinding,
} from '@/core/findingPresentation';
import i18n from '@/i18n';

const getConfirmationStatus = (value: unknown): NodeStatus => {
  return value === 'confirmed' || value === 'needs_confirmation' || value === 'ai_assumption'
    ? value
    : 'ai_assumption';
};
const selectAllIssues = (space: RequirementSpace | null): Finding[] => {
  if (!space) return [];
  return space.findings || [];
};

// Readiness summary calculation
type ReadinessDimension = {
  kind: 'goal' | 'role' | 'system' | 'data' | 'ui';
  title: string;
  score: number;
  checked: boolean;
};

export type ReadinessSummary = {
  overallScore: number;
  dimensions: ReadinessDimension[];
};

export const buildReadiness = (space: RequirementSpace | null, stageProgress?: any): ReadinessSummary => {
  if (!space) return { overallScore: 0, dimensions: [] };

  const features = space.features || [];
  const actors = space.actors || [];
  const flows = space.flows || [];
  const businessObjects = space.businessObjects || [];

  const howStage = stageProgress?.stages?.find((s: any) => s.stage === 'how');
  const isHowUnlocked = howStage ? Boolean(howStage.unlocked) : true;

  // Calculate scores for each dimension
  // 1. Goal (Features) - ratio of features with defined descriptions/names
  const goalScore = features.length > 0 ? 100 : 0;

  // 2. Role - ratio of actors referenced by features
  const linkedActorIds = new Set(features.flatMap(f => f.actorIds || []));
  const actorScore = actors.length > 0 
    ? Math.floor((actors.filter(a => linkedActorIds.has(a.actorId)).length / actors.length) * 100)
    : 0;

  // 3. System - ratio of leaf features with flows
  const leafFeatures = features.filter(f => f.parentId !== null && (f.childrenIds || []).length === 0);
  const flowsLinkedFeatures = new Set(flows.flatMap(f => f.featureIds || []));
  const systemScore = !isHowUnlocked
    ? 0
    : leafFeatures.length > 0
    ? Math.floor((leafFeatures.filter(f => flowsLinkedFeatures.has(f.featureId)).length / leafFeatures.length) * 100)
    : 0;

  // 4. Data - Business object attribute completeness
  const totalBOs = businessObjects.length;
  const completeBOs = businessObjects.filter(b => (b.businessObjectAttributes || []).length > 0).length;
  const dataScore = !isHowUnlocked
    ? 0
    : totalBOs > 0
    ? Math.floor((completeBOs / totalBOs) * 100)
    : 0;

  // 5. UI / Acceptance - scenarios with acceptance criteria ratio
  const totalScenarios = features.flatMap(f => f.scenarios || []);
  const completeScenarios = totalScenarios.filter(s => (s.acceptanceCriteria || []).length > 0).length;
  const uiScore = totalScenarios.length > 0 ? Math.floor((completeScenarios / totalScenarios.length) * 100) : 0;

  const dims: ReadinessDimension[] = [
    { kind: 'goal', title: i18n.t('selectors.readiness.goal'), score: goalScore, checked: goalScore >= 80 },
    { kind: 'role', title: i18n.t('selectors.readiness.role'), score: actorScore, checked: actorScore >= 80 },
    { kind: 'system', title: i18n.t('selectors.readiness.system'), score: systemScore, checked: systemScore >= 80 },
    { kind: 'data', title: i18n.t('selectors.readiness.data'), score: dataScore, checked: dataScore >= 80 },
    { kind: 'ui', title: i18n.t('selectors.readiness.ui'), score: uiScore, checked: uiScore >= 80 },
  ];

  const overallScore = Math.floor(dims.reduce((sum, d) => sum + d.score, 0) / dims.length);

  return { overallScore, dimensions: dims };
};

export const getStageIssues = (space: RequirementSpace | null, stage: Stage): Finding[] => {
  if (!space) return [];
  return (space.findings || []).filter(
    (finding) => isCountableFinding(finding) && findingStage(finding) === stage
  );
};

export type OverviewModel = {
  readiness: ReadinessSummary;
  openIssues: Finding[];
  highRiskIssues: Finding[];
  decisionQueue: Array<{
    id: string;
    kind: 'choiceGroup';
    titleKey: string;
    titleParams?: Record<string, string | number>;
    descriptionKey?: string;
    descriptionParams?: Record<string, string | number>;
    original: any;
  }>;
  recentChoices: any[];
  openChoiceGroupsCount: number;
  openSlotsCount: number;

  aiAssumptionLedger: any[];
  recentAuditOperations: any[];
};

const choiceGroupTypeLabelMap: Record<string, string> = {
  actor: 'overview.decisionQueue.types.actor',
  scenario: 'overview.decisionQueue.types.scenario',
  feature: 'overview.decisionQueue.types.feature',
  flow: 'overview.decisionQueue.types.flow',
  scope: 'overview.decisionQueue.types.scope',
  acceptance_criteria: 'overview.decisionQueue.types.acceptanceCriteria',
  project_creation: 'overview.decisionQueue.types.projectCreation',
};

const getChoiceGroupDecisionLabel = (choiceGroup: any) => {
  const rawType = choiceGroup.generationType || choiceGroup.generation_type || choiceGroup.sourceType || choiceGroup.source_type;
  return choiceGroupTypeLabelMap[rawType] || null;
};

const getChoiceGroupDecisionDescription = (choiceGroup: any) => {
  const label = getChoiceGroupDecisionLabel(choiceGroup);
  const candidateCount = (choiceGroup.choices || []).filter((choice: any) => choice.status === 'candidate').length
    || choiceGroup.successCount
    || choiceGroup.success_count
    || choiceGroup.candidateCount
    || choiceGroup.candidate_count
    || choiceGroup.choices?.length
    || 0;

  if (label) {
    return {
      descriptionKey: 'overview.decisionQueue.descriptionWithType',
      descriptionParams: { count: candidateCount, typeKey: label },
    };
  }

  return {
    descriptionKey: 'overview.decisionQueue.description',
    descriptionParams: { count: candidateCount },
  };
};

export const buildOverviewModel = (
  space: RequirementSpace | null,
  auditLogs: any[] = [],
  stageProgress?: any,
  backendFindings: Finding[] = [],
): OverviewModel => {
  const readiness = buildReadiness(space, stageProgress);
  if (!space) {
    return {
      readiness,
      openIssues: [],
      highRiskIssues: [],
      decisionQueue: [],
      recentChoices: [],
      openChoiceGroupsCount: 0,
      openSlotsCount: 0,

      aiAssumptionLedger: [],
      recentAuditOperations: [],
    };
  }

  const allIssues = backendFindings.length > 0 ? backendFindings : selectAllIssues(space);
  const openIssues = allIssues.filter((finding) => (finding.status || 'open') === 'open' && isCountableFinding(finding));
  const highRiskIssues = openIssues.filter((finding) => finding.severity === 'blocking');

  const dq: any[] = [];

  // 1. 抉择项：ChoiceGroups (处于 open 状态)
  if (space.choiceGroups) {
    Object.values(space.choiceGroups).forEach((cg: any) => {
      if (cg.status === 'open') {
        const label = getChoiceGroupDecisionLabel(cg);
        const decisionDescription = getChoiceGroupDecisionDescription(cg);
        dq.push({
          id: cg.id,
          kind: 'choiceGroup' as const,
          titleKey: label ? 'overview.decisionQueue.titleWithType' : 'overview.decisionQueue.title',
          titleParams: label ? { typeKey: label } : { id: cg.id },
          ...decisionDescription,
          original: cg,
        });
      }
    });
  }

  // 构建 AI 推测账本：扫描所有实体，收集 confirmationStatus === 'ai_assumption' 的节点
  const ledger: any[] = [];
  const pushLedger = (kind: string, id: number, title: string, source: string, status: string) => {
    if (status === 'ai_assumption') {
      ledger.push({
        kind,
        id: `${kind}-${id}`,
        nodeId: id,
        title,
        source,
        status,
      });
    }
  };
  (space.actors || []).forEach((a: any) =>
    pushLedger('actor', a.actorId, a.actorName, a.actorDescription, a.confirmationStatus)
  );
  (space.features || []).forEach((f: any) => {
    pushLedger('feature', f.featureId, f.featureName, f.featureDescription, f.confirmationStatus);
    if (f.scope?.scopeId) {
      pushLedger(
        'scope',
        f.scope.scopeId,
        f.featureName,
        f.scope.reason || f.featureDescription || i18n.t('selectors.scope.pendingDecision'),
        f.scope.confirmationStatus,
      );
    }
    (f.scenarios || []).forEach((s: any) => {
      pushLedger('scenario', s.scenarioId, s.scenarioName, s.scenarioContent, s.confirmationStatus);
      (s.acceptanceCriteria || []).forEach((ac: any) => {
        pushLedger('acceptance_criterion', ac.criterionId, ac.criterionContent?.slice(0, 80), ac.criterionContent, ac.confirmationStatus);
      });
    });
  });
  (space.businessObjects || []).forEach((b: any) => {
    pushLedger('business_object', b.businessObjectId, b.businessObjectName, b.businessObjectDescription, b.confirmationStatus);
    (b.businessObjectAttributes || []).forEach((attr: any) => {
      pushLedger(
        'business_object_attribute',
        attr.businessObjectAttributeId,
        attr.businessObjectAttributeName,
        attr.businessObjectAttributeDescription,
        attr.confirmationStatus,
      );
    });
  });
  (space.flows || []).forEach((fl: any) => {
    pushLedger('flow', fl.flowId, fl.flowName, fl.flowDescription, fl.confirmationStatus);
    (fl.flowSteps || []).forEach((step: any) => {
      pushLedger(
        'flow_step',
        step.stepId,
        step.stepName,
        step.stepDescription,
        step.confirmationStatus,
      );
    });
  });

  const choices = Object.values(space.choiceGroups || {}).flatMap(group => group.choices || []);
  const recentChoices = choices.filter((c: any) => c.status === 'candidate').slice(0, 3);
  const openChoiceGroupsCount = Object.values(space.choiceGroups || {}).filter((cg: any) => cg.status === 'open').length;

  const openSlotsCount = (stageProgress?.stages || []).filter(
    (stage: any) => stage.statusCode === 'blocked',
  ).length;

  return {
    readiness,
    openIssues,
    highRiskIssues,
    decisionQueue: dq.slice(0, 5),
    recentChoices,
    openChoiceGroupsCount,
    openSlotsCount,

    aiAssumptionLedger: ledger,
    recentAuditOperations: auditLogs.slice(0, 5),
  };
};

export const projectionPath = (projection: string) => {
  if (projection === 'system') return '/flow';
  if (projection === 'data') return '/scope';
  if (projection === 'ui') return '/preview';
  return '/what';
};

export type WorkspaceRoutePage = '/overview' | '/what' | '/flow' | '/scope' | '/preview' | '/knowledge' | '/repo';

export const buildProjectRoute = (
  projectId: string | null | undefined,
  page: WorkspaceRoutePage
): string => {
  if (projectId === null || projectId === undefined || projectId === '') return page;
  return `/projects/${projectId}${page}`;
};

/** 分支感知路由：非 main 分支时附加 ?branch=，保证导航后仍停留在同一分支。 */
export const buildProjectRouteWithBranch = (
  projectId: string | null | undefined,
  page: WorkspaceRoutePage,
  branchRef?: string
): string => {
  const base = buildProjectRoute(projectId, page);
  if (branchRef && branchRef !== 'main') {
    return `${base}?branch=${encodeURIComponent(branchRef)}`;
  }
  return base;
};

export const extractWorkspacePage = (
  pathname: string
): WorkspaceRoutePage | null => {
  const match = pathname.match(/\/projects\/[^/]+(\/overview|\/what|\/flow|\/scope|\/preview|\/knowledge|\/repo)$/);
  if (match) {
    return match[1] as WorkspaceRoutePage;
  }

  if (
    pathname === '/overview' ||
    pathname === '/what' ||
    pathname === '/flow' ||
    pathname === '/scope' ||
    pathname === '/preview' ||
    pathname === '/knowledge' ||
    pathname === '/repo'
  ) {
    return pathname;
  }

  return null;
};

export const normalizeFindingTarget = (target: any): { targetType: string; targetId?: number | string; targetLogicalUuid?: string } | null => {
  if (!target) return null;
  const targetType = (
    target.targetType ||
    target.target_type ||
    target.targetKind ||
    target.target_kind ||
    target.type ||
    ''
  ).toString().toLowerCase();

  const rawId = target.targetId !== undefined
    ? target.targetId
    : target.target_id !== undefined
    ? target.target_id
    : target.id;

  const targetLogicalUuid = (
    target.targetLogicalUuid ||
    target.target_logical_uuid ||
    target.logicalUuid ||
    target.logical_uuid ||
    ''
  ).toString();

  return {
    targetType,
    targetId: rawId,
    targetLogicalUuid: targetLogicalUuid || undefined,
  };
};

export const selectFindingsForStep = (
  step: FlowStepNode | null | undefined,
  findings: Finding[] = []
): Finding[] => {
  if (!step || !Array.isArray(findings)) return [];
  const stepIdStr = String(step.stepId);
  const stepUuid = step.logicalUuid;

  return findings.filter((f) => {
    const meta = normalizeFindingTarget(f.target || f.metadata?.target);
    if (!meta) return false;
    const isStepType = meta.targetType === 'flow_step' || meta.targetType === 'step';
    if (!isStepType) return false;

    if (meta.targetId !== undefined && String(meta.targetId) === stepIdStr) return true;
    if (stepUuid && meta.targetLogicalUuid === stepUuid) return true;
    return false;
  });
};

export const selectFindingsForTransition = (
  transition: FlowTransition | null | undefined,
  findings: Finding[] = []
): Finding[] => {
  if (!transition || !Array.isArray(findings)) return [];
  const transId = transition.transitionId || transition.id;
  const transIdStr = transId !== undefined ? String(transId) : undefined;
  const transUuid = transition.logicalUuid;

  return findings.filter((f) => {
    const meta = normalizeFindingTarget(f.target || f.metadata?.target);
    if (!meta) return false;
    const isTransType = meta.targetType === 'flow_transition' || meta.targetType === 'transition';
    if (!isTransType) return false;

    if (transIdStr !== undefined && meta.targetId !== undefined && String(meta.targetId) === transIdStr) return true;
    if (transUuid && meta.targetLogicalUuid === transUuid) return true;
    return false;
  });
};

export const selectFindingsForFlow = (
  flow: FlowNode | null | undefined,
  findings: Finding[] = []
): Finding[] => {
  if (!flow || !Array.isArray(findings)) return [];
  const flowIdStr = String(flow.flowId);
  const flowUuid = flow.logicalUuid;
  const steps = flow.flowSteps || [];
  const transitions = flow.transitions || [];

  const stepIds = new Set(steps.map((s) => String(s.stepId)));
  const stepUuids = new Set(steps.map((s) => s.logicalUuid).filter(Boolean));

  const transIds = new Set(transitions.map((t) => String(t.transitionId || t.id)).filter(Boolean));
  const transUuids = new Set(transitions.map((t) => t.logicalUuid).filter(Boolean));

  return findings.filter((f) => {
    const meta = normalizeFindingTarget(f.target || f.metadata?.target);
    if (!meta) return false;

    // Direct Flow match
    if (meta.targetType === 'flow') {
      if (meta.targetId !== undefined && String(meta.targetId) === flowIdStr) return true;
      if (flowUuid && meta.targetLogicalUuid === flowUuid) return true;
      return false;
    }

    // Step match
    if (meta.targetType === 'flow_step' || meta.targetType === 'step') {
      if (meta.targetId !== undefined && stepIds.has(String(meta.targetId))) return true;
      if (meta.targetLogicalUuid && stepUuids.has(meta.targetLogicalUuid)) return true;
      return false;
    }

    // Transition match
    if (meta.targetType === 'flow_transition' || meta.targetType === 'transition') {
      if (meta.targetId !== undefined && transIds.has(String(meta.targetId))) return true;
      if (meta.targetLogicalUuid && transUuids.has(meta.targetLogicalUuid)) return true;
      return false;
    }

    return false;
  });
};

// Flow step topology detail
export type StepDetail = {
  inputs: string[];
  outputs: string[];
  rules: string[];
  stateChanges: string[];
  relatedIssueIds: string[];
  relatedChoiceIds: string[];
};

export const buildStepDetail = (space: RequirementSpace | null, stepId: string | number): StepDetail => {
  const emptyDetail: StepDetail = { inputs: [], outputs: [], rules: [], stateChanges: [], relatedIssueIds: [], relatedChoiceIds: [] };
  if (!space) return emptyDetail;
  const numId = typeof stepId === 'string' ? parseInt(stepId, 10) : stepId;

  // Find step
  let targetStep: FlowStepNode | null = null;
  for (const flow of space.flows || []) {
    const s = (flow.flowSteps || []).find(st => st.stepId === numId);
    if (s) {
      targetStep = s;
      break;
    }
  }

  if (!targetStep) return emptyDetail;

  const inputs = (targetStep.inputBusinessObjectIds || [])
    .map(id => (space.businessObjects || []).find(b => b.businessObjectId === id)?.businessObjectName)
    .filter(Boolean) as string[];

  const outputs = (targetStep.outputBusinessObjectIds || [])
    .map(id => (space.businessObjects || []).find(b => b.businessObjectId === id)?.businessObjectName)
    .filter(Boolean) as string[];

  const stepLogicalUuid = targetStep.logicalUuid;
  const linkedRules = (space.domainRules || [])
    .filter(r => (r.links || []).some(l => l.targetKind === 'flow_step' && Boolean(stepLogicalUuid) && l.targetLogicalUuid === stepLogicalUuid))
    .map(r => r.title);

  // Extract real findings targeting this step
  const relatedFindings = selectFindingsForStep(targetStep, space.findings || []);
  const relatedIssueIds = relatedFindings.map(f => f.findingId);

  return {
    inputs,
    outputs,
    rules: linkedRules,
    stateChanges: outputs.map(o => i18n.t('selectors.stepDetail.stateChange', { name: o })),
    relatedIssueIds,
    relatedChoiceIds: [],
  };
};

export type SystemProjection = {
  swimlanes: string[];
  abnormalIssues: Finding[];
  getStepsBySwimlane: (lane: string) => FlowStepNode[];
  getOutgoingStepTitles: (stepId: string) => string[];
  getExceptionStepTitles: (stepId: string) => string[];
  getStepSlots: (stepId: string) => any[];
  businessObjects: any[];
  getRelatedStepsForObject: (objectId: string | number) => any[];
};

export const SYSTEM_SWIMLANE_ID = '__system__';

export const buildSystemProjection = (space: RequirementSpace | null): SystemProjection => {
  const baseLanes = space ? (space.actors || []).map(a => a.actorName) : [];
  const swimlanes = baseLanes.includes(SYSTEM_SWIMLANE_ID) ? baseLanes : [...baseLanes, SYSTEM_SWIMLANE_ID];

  const empty = {
    swimlanes,
    abnormalIssues: [],
    getStepsBySwimlane: () => [],
    getOutgoingStepTitles: () => [],
    getExceptionStepTitles: () => [],
    getStepSlots: () => [],
    businessObjects: [],
    getRelatedStepsForObject: () => [],
  };

  if (!space) return empty;

  const abnormalIssues = (space.findings || []).filter(
    (finding) => findingProjection(finding) === 'system',
  );

  const allSteps = (space.flows || []).flatMap(f => f.flowSteps || []);

  const getStepsBySwimlane = (lane: string) => {
    return allSteps
      .filter(step => {
        if (lane === SYSTEM_SWIMLANE_ID) {
          return (step.actorIds || []).length === 0;
        }
        const performerId = (step.actorIds || [])[0];
        const performer = (space.actors || []).find(a => a.actorId === performerId);
        return performer ? performer.actorName === lane : false;
      })
      .map((step, idx) => ({
        ...step,
        id: step.stepId.toString(),
        title: step.stepName,
        description: step.stepDescription,
        status: 'confirmed',
        position: idx + 1
      })) as any[];
  };

  const allTransitions = (space.flows || []).flatMap(f => (f as any).transitions || []);

  const getOutgoingStepTitles = (stepId: string | number) => {
    const numId = typeof stepId === 'string' ? parseInt(stepId, 10) : stepId;
    return allTransitions
      .filter(t => t.sourceStepId === numId)
      .map(t => allSteps.find(s => s.stepId === t.targetStepId)?.stepName)
      .filter(Boolean) as string[];
  };

  const getExceptionStepTitles = (stepId: string | number) => {
    const numId = typeof stepId === 'string' ? parseInt(stepId, 10) : stepId;
    return allTransitions
      .filter(t => t.sourceStepId === numId && (
        (t.semanticTags || []).some((tag: string) => tag.toLowerCase().includes('exception') || tag.toLowerCase().includes('error')) ||
        (t.label || '').toLowerCase().includes('异常') ||
        (t.label || '').toLowerCase().includes('失败')
      ))
      .map(t => allSteps.find(s => s.stepId === t.targetStepId)?.stepName)
      .filter(Boolean) as string[];
  };

  const getRelatedStepsForObject = (objectId: string | number) => {
    const numId = typeof objectId === 'string' ? parseInt(objectId, 10) : objectId;
    return allSteps
      .filter(s => (s.inputBusinessObjectIds || []).includes(numId) || (s.outputBusinessObjectIds || []).includes(numId))
      .map(step => ({
        ...step,
        id: step.stepId.toString(),
        title: step.stepName,
        description: step.stepDescription,
        status: 'confirmed',
        kind: 'flow_step'
      }));
  };

  return {
    swimlanes,
    abnormalIssues,
    getStepsBySwimlane,
    getOutgoingStepTitles,
    getExceptionStepTitles,
    getStepSlots: () => [],
    businessObjects: (space.businessObjects || []).map(b => ({
      ...b,
      id: b.businessObjectId.toString(),
      title: b.businessObjectName,
      description: b.businessObjectDescription,
      status: getConfirmationStatus((b as any).confirmationStatus),
    })),
    getRelatedStepsForObject,
  };
};

export const normalizeScopeStatus = (status: string | undefined | null): 'current' | 'postponed' | 'exclude' => {
  if (!status) return 'current';
  const s = status.toLowerCase();
  if (s === 'current' || s === 'in_scope' || s === '本期') return 'current';
  if (s === 'postponed' || s === 'deferred' || s === '暂缓') return 'postponed';
  if (s === 'exclude' || s === 'excluded' || s === '排除') return 'exclude';
  return 'current';
};

// Tree-hierarchy feature selectors
export const getRootCapabilities = (space: RequirementSpace | null): any[] => {
  if (!space) return [];
  const features = space.features || [];
  const dbRoot = features.find(f => f.parentId === null);
  if (!dbRoot) return [];
  
  return features
    .filter(f => f.parentId === dbRoot.featureId)
    .map(f => ({
      ...f,
      id: f.featureId.toString(),
      title: f.featureName,
      description: f.featureDescription,
      status: getConfirmationStatus((f as any).confirmationStatus),
      scopeStatus: normalizeScopeStatus(f.scope?.scopeStatus),
      kind: 'feature'
    }));
};

export const getChildCapabilities = (space: RequirementSpace | null, capId: string | number): any[] => {
  if (!space) return [];
  const numId = typeof capId === 'string' ? parseInt(capId, 10) : capId;
  return (space.features || [])
    .filter(f => f.parentId === numId)
    .map(f => ({
      ...f,
      id: f.featureId.toString(),
      title: f.featureName,
      description: f.featureDescription,
      status: getConfirmationStatus((f as any).confirmationStatus),
      scopeStatus: normalizeScopeStatus(f.scope?.scopeStatus),
      kind: 'feature'
    }));
};

export const groupScopeItems = (space: RequirementSpace | null) => {
  const empty = { inScope: [], deferred: [], dependencies: [], outOfScope: [], excluded: [], undecided: [] };
  if (!space) return empty;

  // Filter leaf capabilities only
  const leafFeatures = (space.features || []).filter(f => {
    const isParent = (space.features || []).some(child => child.parentId === f.featureId);
    return f.parentId !== null && !isParent;
  });

  const mapToNode = (f: FeatureNode) => {
    const parentModule = (space.features || []).find(p => p.featureId === f.parentId);
    const scopeStatus = f.scope?.scopeStatus;
    const hasScope = !!scopeStatus;
    const normStatus = scopeStatus ? normalizeScopeStatus(scopeStatus) : undefined;
    const isDecisionMissing = !hasScope;
    const scopeConfirmationStatus = (f.scope as any)?.confirmationStatus;

    return {
      kind: 'scope' as const,
      id: f.featureId.toString(),
      featureId: f.featureId,
      featureName: f.featureName,
      featureDescription: f.featureDescription,
      title: f.featureName,
      description: f.featureDescription,
      status: scopeConfirmationStatus,
      confirmationStatus: scopeConfirmationStatus,
      scopeStatus: normStatus,
      isDecisionMissing,
      parentModuleName: parentModule ? parentModule.featureName : i18n.t('selectors.ungroupedModule'),
      scope: f.scope ? {
        ...f.scope,
        confirmationStatus: scopeConfirmationStatus,
        scopeStatus: normStatus
      } : {
        kind: 'scope' as const,
        scopeId: undefined as any,
        scopeStatus: normStatus as any,
        reason: '',
        confirmationStatus: undefined,
        positiveSummary: null,
        negativeSummary: null,
        positivePictureBase64: null,
        negativePictureBase64: null,
        kanoCategory: null,
        kanoCategoryName: null
      }
    };
  };

  const mapped = leafFeatures.map(mapToNode);

  return {
    inScope: mapped.filter(f => f.scopeStatus === 'current'),
    deferred: mapped.filter(f => f.scopeStatus === 'postponed'),
    dependencies: [],
    outOfScope: [],
    excluded: mapped.filter(f => f.scopeStatus === 'exclude'),
    undecided: mapped.filter(f => f.isDecisionMissing),
  };
};

export const buildRolePages = (space: RequirementSpace | null, actorId: string | null): any[] => {
  if (!space || !actorId) return [];
  const numId = typeof actorId === 'string' ? parseInt(actorId, 10) : actorId;
  const actor = (space.actors || []).find(a => a.actorId === numId);
  if (!actor) return [];

  // Filter leaf capabilities only associated with this actor
  const leafFeatures = (space.features || []).filter(f => {
    const isParent = (space.features || []).some(child => child.parentId === f.featureId);
    return f.parentId !== null && !isParent && (f.actorIds || []).includes(numId);
  });

  return leafFeatures.map(f => {
    // Find steps in flows associated with this feature and this actor
    const relatedSteps = (space.flows || [])
      .filter(flow => (flow.featureIds || []).includes(f.featureId))
      .flatMap(flow => flow.flowSteps || [])
      .filter(step => (step.actorIds || []).includes(numId))
      .map(step => step.stepName);

    return {
      id: `screen_feat_${f.featureId}`,
      name: i18n.t('selectors.rolePage.name', { featureName: f.featureName }),
      desc: f.featureDescription || i18n.t('selectors.rolePage.description', { actorName: actor.actorName, featureName: f.featureName }),
      featureName: f.featureName,
      scenarios: f.scenarios || [],
      relatedSteps: relatedSteps.length > 0 ? relatedSteps : [i18n.t('selectors.rolePage.fallbackStep', { featureName: f.featureName })],
      actions: (f.scenarios || []).map(s => s.scenarioName)
    };
  });
};

export const selectRulesForTarget = (
  space: RequirementSpace | null,
  targetKind: 'flow' | 'flow_step' | 'flow_transition',
  targetLogicalUuid?: string
): DomainRule[] => {
  if (!space?.domainRules || !targetLogicalUuid) return [];
  return space.domainRules.filter(r => {
    return (r.links || []).some(l => {
      return l.targetKind === targetKind && l.targetLogicalUuid === targetLogicalUuid;
    });
  });
};

export const selectTransitionLabel = (
  transition?: Partial<FlowTransition> | null
): {
  text: string;
  isFallback: boolean;
  isConditionFallback: boolean;
  isUnspecified: boolean;
  isDefault: boolean;
  status: 'specified' | 'condition_fallback' | 'unspecified';
} => {
  const isDefault = Boolean(transition?.isDefault);
  if (!transition) {
    return {
      text: i18n.t('how.transitionLabel.unspecified', '未说明流转条件'),
      isFallback: true,
      isConditionFallback: false,
      isUnspecified: true,
      isDefault: false,
      status: 'unspecified',
    };
  }
  const label = (transition.label || '').trim();
  if (label) {
    return {
      text: label,
      isFallback: false,
      isConditionFallback: false,
      isUnspecified: false,
      isDefault,
      status: 'specified',
    };
  }
    const cond = (transition.conditionText || '').trim();
  if (cond) {
    return {
      text: cond,
      isFallback: true,
      isConditionFallback: true,
      isUnspecified: false,
      isDefault,
      status: 'condition_fallback',
    };
  }
  return {
    text: i18n.t('how.transitionLabel.unspecified', '未说明流转条件'),
    isFallback: true,
    isConditionFallback: false,
    isUnspecified: true,
    isDefault,
    status: 'unspecified',
  };
};


export const selectFlowSummary = (
  flow: FlowNode | null,
  domainRules: DomainRule[] = [],
  findings: Finding[] = []
): {
  stepCount: number;
  transitionCount: number;
  ruleCount: number;
  boCount: number;
  blockingFindingsCount: number;
  warningFindingsCount: number;
} => {
  if (!flow) {
    return { stepCount: 0, transitionCount: 0, ruleCount: 0, boCount: 0, blockingFindingsCount: 0, warningFindingsCount: 0 };
  }
  const steps = flow.flowSteps || [];
  const transitions = flow.transitions || [];
  const stepUuids = new Set(steps.map(s => s.logicalUuid).filter(Boolean));
  const transUuids = new Set(transitions.map(t => t.logicalUuid).filter(Boolean));

  // Linked rules to flow, its steps or transitions
  const linkedRuleIds = new Set<number>();
  domainRules.forEach(r => {
    (r.links || []).forEach(link => {
      if (
        (link.targetKind === 'flow' && link.targetLogicalUuid === flow.logicalUuid) ||
        (link.targetKind === 'flow_step' && link.targetLogicalUuid && stepUuids.has(link.targetLogicalUuid)) ||
        (link.targetKind === 'flow_transition' && link.targetLogicalUuid && transUuids.has(link.targetLogicalUuid))
      ) {
        linkedRuleIds.add(r.id);
      }
    });
  });

  // Involved BOs
  const boIds = new Set<number>();
  steps.forEach(s => {
    (s.inputBusinessObjectIds || []).forEach(id => boIds.add(id));
    (s.outputBusinessObjectIds || []).forEach(id => boIds.add(id));
  });

  // Findings targeting this flow or its steps/transitions
  const relevantFindings = selectFindingsForFlow(flow, findings);
  let blockingCount = 0;
  let warningCount = 0;

  relevantFindings.forEach(f => {
    const isBlocking = (f.severity as string) === 'error' || (f.severity as string) === 'blocking' || (f.blockingScope && f.blockingScope !== 'none');
    if (isBlocking) {
      blockingCount++;
    } else if (f.severity === 'warning') {
      warningCount++;
    }
  });

  return {
    stepCount: steps.length,
    transitionCount: transitions.length,
    ruleCount: linkedRuleIds.size,
    boCount: boIds.size,
    blockingFindingsCount: blockingCount,
    warningFindingsCount: warningCount,
  };
};
