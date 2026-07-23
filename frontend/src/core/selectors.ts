import type {
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
  Choice,
  ChoiceGroup,
  GoalNode,
  CapabilityNode,
  TaskNode,
  NodeStatus,
  GraphPatch,
  FlowStepType,
  Stage,
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
export const selectAllNodes = (space: RequirementSpace | null): any[] => {
  if (!space) return [];
  const list: any[] = [];
  (space.actors || []).forEach(a => list.push({ ...a, id: a.actorId.toString(), title: a.actorName, description: a.actorDescription, status: getConfirmationStatus((a as any).confirmationStatus), scopeStatus: 'in_scope' }));
  (space.features || []).forEach(f => list.push({ ...f, id: f.featureId.toString(), title: f.featureName, description: f.featureDescription, status: getConfirmationStatus((f as any).confirmationStatus), scopeStatus: f.scope?.scopeStatus || 'in_scope' }));
  (space.businessObjects || []).forEach(b => {
    list.push({ ...b, id: b.businessObjectId.toString(), title: b.businessObjectName, description: b.businessObjectDescription, status: getConfirmationStatus((b as any).confirmationStatus), scopeStatus: 'in_scope' });
    (b.businessObjectAttributes || []).forEach(attr => {
      list.push({
        ...attr,
        id: attr.businessObjectAttributeId.toString(),
        title: attr.businessObjectAttributeName,
        description: attr.businessObjectAttributeDescription,
        status: getConfirmationStatus((attr as any).confirmationStatus),
        scopeStatus: 'in_scope',
      });
    });
  });
  (space.flows || []).forEach(fl => {
    list.push({ ...fl, id: fl.flowId.toString(), title: fl.flowName, description: fl.flowDescription, status: getConfirmationStatus((fl as any).confirmationStatus), scopeStatus: 'in_scope' });
    (fl.flowSteps || []).forEach(st => {
      list.push({ ...st, id: st.stepId.toString(), title: st.stepName, description: st.stepDescription, status: getConfirmationStatus((st as any).confirmationStatus), scopeStatus: 'in_scope' });
    });
  });
  return list;
};

export const selectAllIssues = (space: RequirementSpace | null): Finding[] => {
  if (!space) return [];
  return space.findings || [];
};

export const selectAllLinks = (): any[] => [];
export const selectAllSlots = (space: RequirementSpace | null): any[] => {
  if (!space || !space.perceptionSlot) return [];
  return [space.perceptionSlot];
};
export const selectAllChoiceGroups = (): any[] => [];
export const selectAllChoices = (): any[] => [];

export const selectPerformerActorIds = (space: RequirementSpace | null, taskId: string | number): number[] => {
  if (!space) return [];
  const numId = typeof taskId === 'string' ? parseInt(taskId, 10) : taskId;
  // If it's a scenario/task
  for (const feat of space.features || []) {
    const sc = (feat.scenarios || []).find(s => s.scenarioId === numId);
    if (sc) return [sc.actorId];
  }
  return [];
};

export const selectPerformerTitle = (space: RequirementSpace | null, taskId: string | number): string | null => {
  if (!space) return null;
  const actorIds = selectPerformerActorIds(space, taskId);
  if (actorIds.length === 0) return i18n.t('selectors.system');
  const actor = (space.actors || []).find(a => a.actorId === actorIds[0]);
  return actor ? actor.actorName : i18n.t('selectors.system');
};

// Readiness summary calculation
export type ReadinessDimension = {
  kind: 'goal' | 'role' | 'system' | 'data' | 'ui';
  title: string;
  score: number;
  checked: boolean;
};

export type ReadinessSummary = {
  overallScore: number;
  dimensions: ReadinessDimension[];
};

export const buildReadiness = (space: RequirementSpace | null): ReadinessSummary => {
  if (!space) return { overallScore: 0, dimensions: [] };

  const features = space.features || [];
  const actors = space.actors || [];
  const flows = space.flows || [];
  const businessObjects = space.businessObjects || [];

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
  const systemScore = leafFeatures.length > 0
    ? Math.floor((leafFeatures.filter(f => flowsLinkedFeatures.has(f.featureId)).length / leafFeatures.length) * 100)
    : 0;

  // 4. Data - Business object attribute completeness
  const totalBOs = businessObjects.length;
  const completeBOs = businessObjects.filter(b => (b.businessObjectAttributes || []).length > 0).length;
  const dataScore = totalBOs > 0 ? Math.floor((completeBOs / totalBOs) * 100) : 0;

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

export const inferIssueStage = findingStage;

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
): OverviewModel => {
  const readiness = buildReadiness(space);
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

  const allIssues = selectAllIssues(space);
  const openIssues = allIssues.filter((finding) => (finding.status || 'open') === 'open');
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

  // 构建 AI 假设账本：扫描所有实体，收集 confirmationStatus === 'ai_assumption' 的节点
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

  const choicesCompatible = (space as any).choicesCompatible || [];
  const recentChoices = choicesCompatible.filter((c: any) => c.status === 'candidate').slice(0, 3);
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

export const buildProjectRoute = (
  projectId: string | null | undefined,
  page: '/overview' | '/what' | '/flow' | '/scope' | '/preview' | '/knowledge'
): string => {
  if (projectId === null || projectId === undefined || projectId === '') return page;
  return `/projects/${projectId}${page}`;
};

export const extractWorkspacePage = (
  pathname: string
): '/overview' | '/what' | '/flow' | '/scope' | '/preview' | '/knowledge' | null => {
  const match = pathname.match(/\/projects\/[^/]+(\/overview|\/what|\/flow|\/scope|\/preview|\/knowledge)$/);
  if (match) {
    return match[1] as '/overview' | '/what' | '/flow' | '/scope' | '/preview' | '/knowledge';
  }

  if (
    pathname === '/overview' ||
    pathname === '/what' ||
    pathname === '/flow' ||
    pathname === '/scope' ||
    pathname === '/preview' ||
    pathname === '/knowledge'
  ) {
    return pathname;
  }

  return null;
};

// Flow step topology detail
export type StepDetail = {
  inputs: string[];
  outputs: string[];
  rules: string[];
  stateChanges: string[];
  relatedPages: string[];
  relatedIssueIds: string[];
  relatedChoiceIds: string[];
};

export const buildStepDetail = (space: RequirementSpace | null, stepId: string | number): StepDetail => {
  const emptyDetail = { inputs: [], outputs: [], rules: [], stateChanges: [], relatedPages: [], relatedIssueIds: [], relatedChoiceIds: [] };
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

  return {
    inputs,
    outputs,
    rules: [i18n.t('selectors.stepDetail.businessFlowRule'), i18n.t('selectors.stepDetail.flowIntegrityRule')],
    stateChanges: outputs.map(o => i18n.t('selectors.stepDetail.stateChange', { name: o })),
    relatedPages: [i18n.t('selectors.stepDetail.operationsPage'), i18n.t('selectors.stepDetail.entryPage')],
    relatedIssueIds: [],
    relatedChoiceIds: [],
  };
};

export type SystemProjection = {
  swimlanes: string[];
  abnormalIssues: Finding[];
  getStepsBySwimlane: (lane: string) => FlowStepNode[];
  getNextStepTitles: (stepId: string) => string[];
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
    getNextStepTitles: () => [],
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

  const getNextStepTitles = (stepId: string | number) => {
    const numId = typeof stepId === 'string' ? parseInt(stepId, 10) : stepId;
    const step = allSteps.find(s => s.stepId === numId);
    if (!step) return [];
    return (step.nextStepIds || [])
      .map(nid => allSteps.find(s => s.stepId === nid)?.stepName)
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
    getNextStepTitles,
    getExceptionStepTitles: () => [],
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

export type GoalBranchItem =
  | { kind: 'issue'; issue: Finding; projection: string }
  | { kind: 'slot'; slot: any; projection: string }
  | { kind: 'choiceGroup'; choiceGroup: any; projection: string };

export const buildGoalBranchItems = (space: RequirementSpace | null): GoalBranchItem[] => {
  if (!space) return [];
  const items: GoalBranchItem[] = [];

  // Add active perception slot
  if (space.perceptionSlot) {
    const slotStage = ((space.perceptionSlot as any).stage || 'what') as Stage;
    const projection = slotStage === 'how' ? 'system' : slotStage === 'scope' ? 'data' : 'goal';
    items.push({
      kind: 'slot',
      slot: {
        id: space.perceptionSlot.id,
        name: space.perceptionSlot.perceptionKind,
        description: space.perceptionSlot.perceptionDescription,
        status: 'empty'
      },
      projection
    });
  }

  // Add relevant rule issues
  (space.findings || []).forEach((issue) => {
    items.push({
      kind: 'issue',
      issue,
      projection: findingProjection(issue),
    });
  });

  return items;
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

export const getTasksForCapability = (space: RequirementSpace | null, capId: string | number): any[] => {
  if (!space) return [];
  const numId = typeof capId === 'string' ? parseInt(capId, 10) : capId;
  const feature = (space.features || []).find(f => f.featureId === numId);
  if (!feature) return [];

  // Map scenarios of this feature as tasks
  return (feature.scenarios || []).map(s => ({
    id: s.scenarioId.toString(),
    title: s.scenarioName,
    outcome: s.scenarioContent,
    status: getConfirmationStatus((s as any).confirmationStatus),
    actorId: s.actorId.toString(),
    scopeStatus: 'in_scope'
  }));
};

export const buildTaskFootprint = (space: RequirementSpace | null, taskId: string | number): { flowStepCount: number; screenCount: number; objectCount: number } => {
  if (!space) return { flowStepCount: 0, screenCount: 0, objectCount: 0 };
  const numId = typeof taskId === 'string' ? parseInt(taskId, 10) : taskId;

  // Locate the scenario matching scenarioId
  let targetScenario: ScenarioNode | null = null;
  for (const f of space.features || []) {
    const s = (f.scenarios || []).find(sc => sc.scenarioId === numId);
    if (s) {
      targetScenario = s;
      break;
    }
  }

  if (!targetScenario) return { flowStepCount: 1, screenCount: 1, objectCount: 1 };

  // Calculate realistic footprints
  const flowStepCount = (space.flows || []).flatMap(f => f.flowSteps || []).filter(step => (step.actorIds || []).includes(targetScenario!.actorId)).length || 1;
  const objectCount = (space.businessObjects || []).length || 1;

  return {
    flowStepCount,
    screenCount: 1,
    objectCount
  };
};

export const formatImpactPreview = (space: RequirementSpace | null, impact: any) => {
  if (!impact) return { goals: [], actors: [], flows: [], objects: [], screens: [] };
  return {
    goals: [],
    actors: [],
    flows: [],
    objects: [],
    screens: []
  };
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

export const buildPlaybackForActor = (space: RequirementSpace | null, actorId: string | null) => {
  if (!space || !actorId) return [];
  const pages = buildRolePages(space, actorId);
  return pages.map(page => ({
    screenId: page.id,
    screenTitle: page.name,
    stepIds: page.relatedSteps,
    stepTitles: page.relatedSteps
  }));
};
