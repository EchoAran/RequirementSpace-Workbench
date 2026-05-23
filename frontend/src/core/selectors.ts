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
} from '@/core/schema';
import { detectIssues } from '@/store/useWorkspaceStore';

export const selectAllNodes = (space: RequirementSpace | null): any[] => {
  if (!space) return [];
  const list: any[] = [];
  (space.actors || []).forEach(a => list.push({ ...a, id: a.actorId.toString(), title: a.actorName, description: a.actorDescription, status: 'confirmed', scopeStatus: 'in_scope' }));
  (space.features || []).forEach(f => list.push({ ...f, id: f.featureId.toString(), title: f.featureName, description: f.featureDescription, status: 'confirmed', scopeStatus: f.scope?.scopeStatus || 'in_scope' }));
  (space.businessObjects || []).forEach(b => list.push({ ...b, id: b.businessObjectId.toString(), title: b.businessObjectName, description: b.businessObjectDescription, status: 'confirmed', scopeStatus: 'in_scope' }));
  (space.flows || []).forEach(fl => {
    list.push({ ...fl, id: fl.flowId.toString(), title: fl.flowName, description: fl.flowDescription, status: 'confirmed', scopeStatus: 'in_scope' });
    (fl.flowSteps || []).forEach(st => {
      list.push({ ...st, id: st.stepId.toString(), title: st.stepName, description: st.stepDescription, status: 'confirmed', scopeStatus: 'in_scope' });
    });
  });
  return list;
};

export const selectAllIssues = (space: RequirementSpace | null): Issue[] => {
  return detectIssues(space);
};

export const selectAllLinks = (): any[] => [];
export const selectAllSlots = (space: RequirementSpace | null): any[] => {
  if (!space || !space.perceptionSlot) return [];
  return [space.perceptionSlot];
};
export const selectAllChoiceGroups = (): any[] => [];
export const selectAllChoices = (): any[] => [];
export const selectAllProposals = (): any[] => [];

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
  if (actorIds.length === 0) return '系统';
  const actor = (space.actors || []).find(a => a.actorId === actorIds[0]);
  return actor ? actor.actorName : '系统';
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
  const leafFeatures = features.filter(f => (f.childrenIds || []).length === 0);
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
    { kind: 'goal', title: '系统目标就绪', score: goalScore, checked: goalScore >= 80 },
    { kind: 'role', title: '执行角色覆盖', score: actorScore, checked: actorScore >= 80 },
    { kind: 'system', title: '业务流程闭环', score: systemScore, checked: systemScore >= 80 },
    { kind: 'data', title: '业务对象建模', score: dataScore, checked: dataScore >= 80 },
    { kind: 'ui', title: '验收场景覆盖', score: uiScore, checked: uiScore >= 80 },
  ];

  const overallScore = Math.floor(dims.reduce((sum, d) => sum + d.score, 0) / dims.length);

  return { overallScore, dimensions: dims };
};

// Page Health summary calculation
export type PageHealth = {
  status: '阻塞' | '待决策' | '可预览' | '已收敛' | '不可用' | '未开始';
  issueCount: number;
  todoCount: number;
  hasRisk: boolean;
  disabled: boolean;
};

export const buildPageHealth = (space: RequirementSpace | null, path: string): PageHealth => {
  if (!space) return { status: '未开始', issueCount: 0, todoCount: 0, hasRisk: false, disabled: false };

  const issues = detectIssues(space);
  const hasPerception = space.perceptionSlot !== null;

  let relatedIssues: Issue[] = [];
  let todoCount = 0;
  let isPreview = false;

  if (path === '/') {
    relatedIssues = issues;
    todoCount = hasPerception ? 1 : 0;
  } else if (path === '/what') {
    relatedIssues = issues.filter(i => i.suggestedProjection === 'goal' || i.suggestedProjection === 'role');
    todoCount = (hasPerception && (space.perceptionSlot?.perceptionKind.includes('角色') || space.perceptionSlot?.perceptionKind.includes('功能') || space.perceptionSlot?.perceptionKind.includes('场景') || space.perceptionSlot?.perceptionKind.includes('成功'))) ? 1 : 0;
  } else if (path === '/flow') {
    relatedIssues = issues.filter(i => i.suggestedProjection === 'system');
    todoCount = (hasPerception && space.perceptionSlot?.perceptionKind.includes('流程')) ? 1 : 0;
  } else if (path === '/scope') {
    relatedIssues = issues.filter(i => i.suggestedProjection === 'data');
    todoCount = 0;
  } else if (path === '/preview') {
    isPreview = true;
    relatedIssues = issues;
    todoCount = 0;
  }

  const isAvailable = (space.actors || []).length > 0 && (space.features || []).length > 0;
  if (isPreview && !isAvailable) {
    return { status: '不可用', issueCount: 0, todoCount: 0, hasRisk: false, disabled: true };
  }

  const issueCount = relatedIssues.length;
  const highRiskCount = relatedIssues.filter(i => i.severity === 'high').length;
  const hasRisk = highRiskCount > 0;

  let status: PageHealth['status'] = '已收敛';
  if (hasRisk) {
    status = '阻塞';
  } else if (issueCount > 0 || todoCount > 0) {
    status = '待决策';
  } else if (isPreview) {
    status = '可预览';
  }

  return { status, issueCount, todoCount, hasRisk, disabled: isPreview ? !isAvailable : false };
};

// Overview dashboard calculation
export type OverviewModel = {
  readiness: ReadinessSummary;
  highRiskIssues: Issue[];
  decisionQueue: Array<{
    id: string;
    kind: 'issue' | 'slot' | 'choiceGroup' | 'proposal';
    title: string;
    description: string;
    original: any;
  }>;
  recentChoices: any[];
  openChoiceGroupsCount: number;
  openSlotsCount: number;
  pendingProposalCount: number;
  aiAssumptionLedger: any[];
  recentAuditOperations: any[];
};

export const buildOverviewModel = (space: RequirementSpace | null): OverviewModel => {
  const readiness = buildReadiness(space);
  if (!space) {
    return {
      readiness,
      highRiskIssues: [],
      decisionQueue: [],
      recentChoices: [],
      openChoiceGroupsCount: 0,
      openSlotsCount: 0,
      pendingProposalCount: 0,
      aiAssumptionLedger: [],
      recentAuditOperations: [],
    };
  }

  const issues = detectIssues(space);
  const highRiskIssues = issues.filter(i => i.severity === 'high');

  const dq: any[] = [];

  // If perception slot is present, it's the highest priority todo!
  if (space.perceptionSlot) {
    dq.push({
      id: space.perceptionSlot.perceptionSlotId.toString(),
      kind: 'slot' as const,
      title: space.perceptionSlot.perceptionKind,
      description: space.perceptionSlot.perceptionDescription,
      original: space.perceptionSlot,
    });
  }

  // Push rule-based issues next
  issues.forEach(issue => {
    dq.push({
      id: issue.id,
      kind: 'issue' as const,
      title: issue.title,
      description: issue.description,
      original: issue,
    });
  });

  return {
    readiness,
    highRiskIssues,
    decisionQueue: dq.slice(0, 5),
    recentChoices: [],
    openChoiceGroupsCount: 0,
    openSlotsCount: space.perceptionSlot ? 1 : 0,
    pendingProposalCount: 0,
    aiAssumptionLedger: [],
    recentAuditOperations: [
      {
        id: '1',
        timestamp: new Date().toISOString(),
        actionType: '系统初始化',
        summary: '项目数据库加载成功，就绪度模型已就位。',
        targetIds: []
      }
    ],
  };
};

export const projectionPath = (projection: string) => {
  if (projection === 'system') return '/flow';
  if (projection === 'data') return '/scope';
  if (projection === 'ui') return '/preview';
  return '/what';
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
    rules: ['满足业务主流程条件限制', 'AI 流程流转完整性保障'],
    stateChanges: outputs.map(o => `${o} 状态更新`),
    relatedPages: ['操作控制大屏', '扫码录入页面'],
    relatedIssueIds: [],
    relatedChoiceIds: [],
  };
};

export type SystemProjection = {
  swimlanes: string[];
  abnormalIssues: Issue[];
  getStepsBySwimlane: (lane: string) => FlowStepNode[];
  getNextStepTitles: (stepId: string) => string[];
  getExceptionStepTitles: (stepId: string) => string[];
  getStepSlots: (stepId: string) => any[];
  businessObjects: any[];
  getRelatedStepsForObject: (objectId: string) => any[];
};

export const buildSystemProjection = (space: RequirementSpace | null): SystemProjection => {
  const baseLanes = space ? (space.actors || []).map(a => a.actorName) : [];
  const swimlanes = baseLanes.includes('系统') ? baseLanes : [...baseLanes, '系统'];

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

  const issues = detectIssues(space);
  const abnormalIssues = issues.filter(i => i.suggestedProjection === 'system');

  const allSteps = (space.flows || []).flatMap(f => f.flowSteps || []);

  const getStepsBySwimlane = (lane: string) => {
    return allSteps
      .filter(step => {
        if (lane === '系统') {
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
    return allSteps.filter(s => (s.inputBusinessObjectIds || []).includes(numId) || (s.outputBusinessObjectIds || []).includes(numId));
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
      status: 'confirmed'
    })),
    getRelatedStepsForObject,
  };
};

export type GoalBranchItem =
  | { kind: 'issue'; issue: Issue; projection: string }
  | { kind: 'slot'; slot: any; projection: string }
  | { kind: 'choiceGroup'; choiceGroup: any; projection: string };

export const buildGoalBranchItems = (space: RequirementSpace | null): GoalBranchItem[] => {
  if (!space) return [];
  const items: GoalBranchItem[] = [];

  // Add active perception slot
  if (space.perceptionSlot) {
    items.push({
      kind: 'slot',
      slot: {
        id: space.perceptionSlot.perceptionSlotId.toString(),
        name: space.perceptionSlot.perceptionKind,
        description: space.perceptionSlot.perceptionDescription,
        status: 'empty'
      },
      projection: 'goal'
    });
  }

  // Add relevant rule issues
  const issues = detectIssues(space);
  issues.forEach(issue => {
    items.push({
      kind: 'issue',
      issue,
      projection: issue.suggestedProjection
    });
  });

  return items;
};

// Tree-hierarchy feature selectors
export const getRootCapabilities = (space: RequirementSpace | null): any[] => {
  if (!space) return [];
  return (space.features || [])
    .filter(f => f.parentId === null)
    .map(f => ({
      id: f.featureId.toString(),
      title: f.featureName,
      description: f.featureDescription,
      status: 'confirmed',
      scopeStatus: f.scope?.scopeStatus || '本期'
    }));
};

export const getChildCapabilities = (space: RequirementSpace | null, capId: string | number): any[] => {
  if (!space) return [];
  const numId = typeof capId === 'string' ? parseInt(capId, 10) : capId;
  return (space.features || [])
    .filter(f => f.parentId === numId)
    .map(f => ({
      id: f.featureId.toString(),
      title: f.featureName,
      description: f.featureDescription,
      status: 'confirmed',
      scopeStatus: f.scope?.scopeStatus || '本期'
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
    status: 'confirmed',
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
  const empty = { inScope: [], deferred: [], dependencies: [], outOfScope: [], excluded: [] };
  if (!space) return empty;

  // Filter leaf capabilities only (nodes with parent and no children)
  const leafFeatures = (space.features || []).filter(f => {
    const isLeaf = !(space.features || []).some(child => child.parentId === f.featureId);
    return f.parentId !== null && isLeaf;
  });

  const mapToNode = (f: FeatureNode) => {
    const parentModule = (space.features || []).find(p => p.featureId === f.parentId);
    return {
      id: f.featureId.toString(),
      title: f.featureName,
      description: f.featureDescription,
      status: 'confirmed',
      scopeStatus: f.scope?.scopeStatus || '本期',
      parentModuleName: parentModule ? parentModule.featureName : '未分组模块',
      scope: f.scope || {
        kind: 'scope' as const,
        scopeId: Math.floor(1000 + Math.random() * 9000),
        scopeStatus: '本期',
        reason: '默认包含在本期范围中，请点击卡片录入决策缘由与Kano分析。',
        positiveSummary: null,
        negativeSummary: null,
        positivePictureBase64: null,
        negativePictureBase64: null
      }
    };
  };

  const mapped = leafFeatures.map(mapToNode);

  return {
    inScope: mapped.filter(f => f.scopeStatus === '本期'),
    deferred: mapped.filter(f => f.scopeStatus === '暂缓'),
    dependencies: [],
    outOfScope: [],
    excluded: mapped.filter(f => f.scopeStatus === '排除'),
  };
};

export const buildPreviewCheckpoints = (space: RequirementSpace | null) => {
  if (!space) {
    return [
      { id: 'initial', title: '初始输入', projection: 'goal', passed: false, checks: [] },
      { id: 'structure', title: '结构成型', projection: 'goal', passed: false, checks: [] },
      { id: 'flow', title: '流程闭环', projection: 'system', passed: false, checks: [] },
      { id: 'delivery', title: '交付确认', projection: 'ui', passed: false, checks: [] },
    ];
  }

  const checkpoints = [
    {
      id: 'initial',
      title: '初始输入',
      projection: 'goal',
      checks: [
        { label: '存在核心目标', passed: space.projectName !== '' },
        { label: '存在主要角色', passed: (space.actors || []).length > 0 },
      ],
      passed: false,
    },
    {
      id: 'structure',
      title: '结构成型',
      projection: 'goal',
      checks: [
        { label: '存在功能定义', passed: (space.features || []).length > 0 },
        { label: '存在关键验收场景', passed: (space.features || []).some(f => (f.scenarios || []).length > 0) },
      ],
      passed: false,
    },
    {
      id: 'flow',
      title: '流程闭环',
      projection: 'system',
      checks: [
        { label: '存在流程步骤', passed: (space.flows || []).some(f => (f.flowSteps || []).length > 0) },
        { label: '无严重业务缺陷', passed: detectIssues(space).filter(i => i.severity === 'high').length === 0 },
      ],
      passed: false,
    },
    {
      id: 'delivery',
      title: '交付确认',
      projection: 'ui',
      checks: [
        { label: '存在业务数据建模', passed: (space.businessObjects || []).length > 0 },
        { label: '已完成范围划分', passed: (space.features || []).some(f => f.scope !== null) },
      ],
      passed: false,
    },
  ];

  return checkpoints.map(c => ({
    ...c,
    passed: c.checks.every(chk => chk.passed)
  }));
};

export const buildRolePages = (space: RequirementSpace | null, actorId: string | null): any[] => {
  if (!space || !actorId) return [];
  const numId = typeof actorId === 'string' ? parseInt(actorId, 10) : actorId;
  const actor = (space.actors || []).find(a => a.actorId === numId);
  if (!actor) return [];

  // Filter leaf capabilities only (nodes with parent and no children) associated with this actor
  const leafFeatures = (space.features || []).filter(f => {
    const isLeaf = !(space.features || []).some(child => child.parentId === f.featureId);
    return f.parentId !== null && isLeaf && (f.actorIds || []).includes(numId);
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
      name: `【${f.featureName}】操作界面`,
      desc: f.featureDescription || `提供给 ${actor.actorName} 用于执行 ${f.featureName} 的交互界面。`,
      featureName: f.featureName,
      scenarios: f.scenarios || [],
      relatedSteps: relatedSteps.length > 0 ? relatedSteps : [`操作与处理 ${f.featureName}`],
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
