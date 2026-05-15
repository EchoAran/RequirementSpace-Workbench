import type {
  Choice,
  ChoiceGroup,
  ImpactPreview,
  Issue,
  FlowStepNode,
  OperationRecord,
  Proposal,
  ProjectionKind,
  RequirementLink,
  RequirementNode,
  RequirementSlot,
  RequirementSpaceIR,
  ScopeStatus,
} from '@/types';

const emptyArray: any[] = [];

const irCache = new WeakMap<object, Record<string, any>>();

const getCache = <T extends object>(ir: T, key: string, build: () => any) => {
  if (!irCache.has(ir)) irCache.set(ir, {});
  const map = irCache.get(ir)!;
  if (!(key in map)) map[key] = build();
  return map[key];
};

export const selectAllNodes = (ir: RequirementSpaceIR | null) => {
  if (!ir) return emptyArray as RequirementNode[];
  return getCache(ir as any, 'allNodes', () => Object.values(ir.nodes || {})) as RequirementNode[];
};

export const selectAllIssues = (ir: RequirementSpaceIR | null) => {
  if (!ir) return emptyArray as Issue[];
  return getCache(ir as any, 'allIssues', () => Object.values(ir.issues || {})) as Issue[];
};

export const selectAllLinks = (ir: RequirementSpaceIR | null) => {
  if (!ir) return emptyArray as RequirementLink[];
  return ir.links || (emptyArray as RequirementLink[]);
};

export const selectAllSlots = (ir: RequirementSpaceIR | null) => {
  if (!ir) return emptyArray as RequirementSlot[];
  return getCache(ir as any, 'allSlots', () => Object.values(ir.slots || {})) as RequirementSlot[];
};

export const selectAllChoiceGroups = (ir: RequirementSpaceIR | null) => {
  if (!ir) return emptyArray as ChoiceGroup[];
  return getCache(ir as any, 'allChoiceGroups', () => Object.values(ir.choiceGroups || {})) as ChoiceGroup[];
};

export const selectAllChoices = (ir: RequirementSpaceIR | null) => {
  if (!ir) return emptyArray as Choice[];
  return getCache(ir as any, 'allChoices', () => {
    const groups = Object.values(ir.choiceGroups || {});
    return groups.flatMap((g) => g.choices || []);
  }) as Choice[];
};

export const selectAllProposals = (ir: RequirementSpaceIR | null) => {
  if (!ir) return emptyArray as Proposal[];
  return getCache(ir as any, 'allProposals', () => Object.values(ir.proposals || {})) as Proposal[];
};

export const selectAllAuditOperations = (ir: RequirementSpaceIR | null) => {
  if (!ir) return emptyArray as OperationRecord[];
  return getCache(ir as any, 'allAuditOperations', () =>
    [...(ir.audit?.operationLog || [])].sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1)),
  ) as OperationRecord[];
};

export const selectAiAssumptionNodes = (ir: RequirementSpaceIR | null) => {
  if (!ir) return emptyArray as RequirementNode[];
  return getCache(ir as any, 'aiAssumptionNodes', () =>
    selectAllNodes(ir).filter((node) => node.status === 'ai_assumption'),
  ) as RequirementNode[];
};

export const selectNodesByKind = (ir: RequirementSpaceIR | null, kind: RequirementNode['kind']) => {
  if (!ir) return emptyArray as RequirementNode[];
  return getCache(ir as any, `nodesByKind:${kind}`, () =>
    Object.values(ir.nodes || {}).filter((n) => n.kind === kind)
  ) as RequirementNode[];
};

export const selectPerformerActorIds = (ir: RequirementSpaceIR | null, nodeId: string) => {
  if (!ir) return emptyArray as string[];
  const links = selectAllLinks(ir);
  return links
    .filter((l) => l.sourceId === nodeId && l.type === 'performed_by')
    .map((l) => l.targetId)
    .filter((id) => ir.nodes[id]?.kind === 'actor');
};

export const selectPerformerTitle = (ir: RequirementSpaceIR | null, nodeId: string) => {
  if (!ir) return null as string | null;
  const ids = selectPerformerActorIds(ir, nodeId);
  if (!ids.length) return null;
  return ir.nodes[ids[0]]?.title || ids[0];
};

export const calculateCoverage = (nodes: { status: string }[]) => {
  if (!nodes.length) return 0;
  const confirmed = nodes.filter((n) => n.status === 'confirmed').length;
  return Math.floor((confirmed / nodes.length) * 100);
};

export type ReadinessDimension = {
  kind: ProjectionKind;
  title: string;
  score: number;
  checked: boolean;
};

export type ReadinessSummary = {
  overallScore: number;
  dimensions: ReadinessDimension[];
};

export const buildReadiness = (ir: RequirementSpaceIR | null): ReadinessSummary => {
  if (!ir) return { overallScore: 0, dimensions: [] };

  const goals = selectNodesByKind(ir, 'goal');
  const actors = selectNodesByKind(ir, 'actor');
  const flowSteps = selectNodesByKind(ir, 'flow_step');
  const screens = selectNodesByKind(ir, 'screen');
  const dataObjects = selectNodesByKind(ir, 'business_object');

  const dims: ReadinessDimension[] = [
    { kind: 'goal', title: '目标覆盖度', score: calculateCoverage(goals), checked: calculateCoverage(goals) >= 80 },
    { kind: 'role', title: '角色闭环', score: calculateCoverage(actors), checked: calculateCoverage(actors) >= 80 },
    { kind: 'system', title: '流程闭环', score: calculateCoverage(flowSteps), checked: calculateCoverage(flowSteps) >= 80 },
    { kind: 'data', title: '数据映射', score: calculateCoverage(dataObjects), checked: calculateCoverage(dataObjects) >= 80 },
    { kind: 'ui', title: '界面交互', score: calculateCoverage(screens), checked: calculateCoverage(screens) >= 80 },
  ];
  const overallScore = Math.floor(dims.reduce((sum, d) => sum + d.score, 0) / dims.length);
  return { overallScore, dimensions: dims };
};

export type DecisionQueueItem =
  | { kind: 'issue'; issue: Issue; ownerProjection: ProjectionKind; severity: Issue['severity'] }
  | { kind: 'slot'; slot: RequirementSlot; ownerProjection: ProjectionKind }
  | { kind: 'choiceGroup'; choiceGroup: ChoiceGroup; ownerProjection: ProjectionKind }
  | { kind: 'proposal'; proposal: Proposal; ownerProjection: ProjectionKind };

export const buildDecisionQueue = (ir: RequirementSpaceIR | null): DecisionQueueItem[] => {
  if (!ir) return [];
  const issues = selectAllIssues(ir).filter((i) => i.status === 'open');
  const slots = selectAllSlots(ir).filter((s) => s.status === 'empty');
  const groups = selectAllChoiceGroups(ir).filter((g) => g.status === 'open');
  const proposals = selectAllProposals(ir).filter((p) => p.status === 'candidate');

  const items: DecisionQueueItem[] = [];

  for (const issue of issues) {
    items.push({ kind: 'issue', issue, ownerProjection: issue.suggestedProjection, severity: issue.severity });
  }
  for (const slot of slots) {
    items.push({ kind: 'slot', slot, ownerProjection: slot.ownerProjection });
  }
  for (const choiceGroup of groups) {
    const slot = ir.slots?.[choiceGroup.slotId];
    items.push({ kind: 'choiceGroup', choiceGroup, ownerProjection: slot?.ownerProjection || 'goal' });
  }
  for (const proposal of proposals) {
    const slotId = typeof proposal.scope?.slotId === 'string' ? String(proposal.scope.slotId) : null;
    const slot = slotId ? ir.slots?.[slotId] : null;
    items.push({ kind: 'proposal', proposal, ownerProjection: slot?.ownerProjection || 'goal' });
  }

  const severityRank: Record<string, number> = { high: 0, medium: 1, low: 2 };
  const itemRank = (item: DecisionQueueItem) => {
    if (item.kind === 'issue' && item.severity === 'high') return 0;
    if (item.kind === 'choiceGroup') return 1;
    if (item.kind === 'slot' && item.slot.status === 'empty') return 2;
    if (item.kind === 'proposal' && item.proposal.status === 'candidate') return 3;
    if (item.kind === 'issue') return 4;
    return 5;
  };
  return items.sort((a, b) => {
    const ak = itemRank(a) - itemRank(b);
    if (ak !== 0) return ak;
    const as = a.kind === 'issue' ? severityRank[a.severity] : 3;
    const bs = b.kind === 'issue' ? severityRank[b.severity] : 3;
    return as - bs;
  });
};

export type PageHealth = {
  status: '阻塞' | '待决策' | '可预览' | '已收敛' | '不可用' | '未开始';
  issueCount: number;
  todoCount: number;
  hasRisk: boolean;
  disabled: boolean;
};

export const buildPageHealth = (ir: RequirementSpaceIR | null, path: string): PageHealth => {
  if (!ir) return { status: '未开始', issueCount: 0, todoCount: 0, hasRisk: false, disabled: false };

  const nodes = selectAllNodes(ir);
  const issues = selectAllIssues(ir);
  const flowSteps = nodes.filter((n) => n.kind === 'flow_step');
  const actors = nodes.filter((n) => n.kind === 'actor');
  const scopeItems = nodes.filter((n) => (n as any).scopeStatus) as RequirementNode[];

  const goals = nodes.filter((n) => n.kind === 'goal');
  const capabilities = nodes.filter((n) => n.kind === 'capability');
  const tasks = nodes.filter((n) => n.kind === 'task');

  let items: any[] = [];
  let relatedIssues: Issue[] = [];
  let isPreview = false;

  if (path === '/') {
    items = [...goals, ...capabilities, ...tasks, ...actors, ...flowSteps, ...scopeItems];
    relatedIssues = issues;
  } else if (path === '/what') {
    items = [...goals, ...capabilities, ...tasks, ...actors];
    relatedIssues = issues.filter((g) => g.relatedNodeIds.some((id) => items.some((i) => i.id === id)));
  } else if (path === '/flow') {
    items = flowSteps;
    relatedIssues = issues.filter((g) => g.relatedNodeIds.some((id) => items.some((i) => i.id === id)));
  } else if (path === '/scope') {
    items = scopeItems;
    relatedIssues = issues.filter((g) => g.relatedNodeIds.some((id) => items.some((i) => i.id === id)));
  } else if (path === '/preview') {
    isPreview = true;
    items = [...goals, ...capabilities, ...tasks, ...actors, ...flowSteps, ...scopeItems];
    relatedIssues = issues;
  }

  const isAvailable = flowSteps.length > 0 && actors.length > 0;
  if (isPreview && !isAvailable) {
    return { status: '不可用', issueCount: 0, todoCount: 0, hasRisk: false, disabled: true };
  }

  const todoCount = items.filter(
    (i) => i.status === 'needs_confirmation' || i.status === 'ai_assumption'
  ).length;
  const issueCount = relatedIssues.filter((g) => g.status === 'open').length;
  const blockingCount = relatedIssues.filter((g) => g.severity === 'high' && g.status === 'open').length;
  const hasRisk = blockingCount > 0;

  let status: PageHealth['status'] = '未开始';
  if (items.length > 0) {
    if (hasRisk) status = '阻塞';
    else if (todoCount > 0 || issueCount > 0) status = '待决策';
    else if (isPreview) status = '可预览';
    else status = '已收敛';
  }

  return { status, issueCount, todoCount, hasRisk, disabled: isPreview ? !isAvailable : false };
};

export type OverviewModel = {
  readiness: ReadinessSummary;
  highRiskIssues: Issue[];
  decisionQueue: Array<{ id: string; kind: 'issue' | 'slot' | 'choiceGroup' | 'proposal'; title: string; description: string; original: any }>;
  recentChoices: Choice[];
  openChoiceGroupsCount: number;
  openSlotsCount: number;
  pendingProposalCount: number;
  aiAssumptionLedger: Array<{ id: string; title: string; kind: string; source: string }>;
  recentAuditOperations: OperationRecord[];
};

export const buildOverviewModel = (ir: RequirementSpaceIR | null): OverviewModel => {
  const readiness = buildReadiness(ir);
  if (!ir) {
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

  const issues = selectAllIssues(ir);
  const highRiskIssues = issues.filter((g) => g.severity === 'high' && g.status === 'open');

  const groups = selectAllChoiceGroups(ir);
  const openChoiceGroupsCount = groups.filter((cg) => cg.status === 'open').length;

  const slots = selectAllSlots(ir);
  const openSlotsCount = slots.filter((s) => s.status === 'empty' || s.status === 'candidate_ready').length;

  const pendingProposalCount = selectAllProposals(ir).filter((proposal) => proposal.status === 'candidate').length;
  const aiAssumptionLedger = selectAiAssumptionNodes(ir)
    .slice(0, 6)
    .map((node) => ({
      id: node.id,
      title: node.title,
      kind: node.kind,
      source: node.source?.text || 'AI 自动生成',
    }));
  const recentAuditOperations = selectAllAuditOperations(ir).slice(0, 6);

  const dq = buildDecisionQueue(ir)
    .slice(0, 5)
    .map((item) => {
      if (item.kind === 'issue') {
        return {
          id: item.issue.id,
          kind: 'issue' as const,
          title: item.issue.title,
          description: item.issue.description,
          original: item.issue,
        };
      }
      if (item.kind === 'slot') {
        return {
          id: item.slot.id,
          kind: 'slot' as const,
          title: item.slot.name,
          description: item.slot.description || '等待补充 Choice',
          original: item.slot,
        };
      }
      if (item.kind === 'proposal') {
        return {
          id: item.proposal.id,
          kind: 'proposal' as const,
          title: item.proposal.title,
          description: item.proposal.summary || '等待审阅的局部改写提案',
          original: item.proposal,
        };
      }
      const slot = ir.slots?.[item.choiceGroup.slotId];
      return {
        id: item.choiceGroup.id,
        kind: 'choiceGroup' as const,
        title: slot?.name || `槽位：${item.choiceGroup.slotId}`,
        description: `有 ${(item.choiceGroup.choices || []).length} 个 Choice 待确认`,
        original: item.choiceGroup,
      };
    });

  const recentChoices = selectAllChoices(ir).filter((c) => c.status === 'candidate').slice(0, 3);
  return {
    readiness,
    highRiskIssues,
    decisionQueue: dq,
    recentChoices,
    openChoiceGroupsCount,
    openSlotsCount,
    pendingProposalCount,
    aiAssumptionLedger,
    recentAuditOperations,
  };
};

export const projectionPath = (projection: ProjectionKind) => {
  if (projection === 'system') return '/flow';
  if (projection === 'data') return '/scope';
  if (projection === 'ui') return '/preview';
  return '/what';
};

export const formatImpactPreview = (ir: RequirementSpaceIR, impact: ImpactPreview | null | undefined) => {
  if (!impact) return { goals: [], actors: [], flows: [], objects: [], screens: [] };
  const toTitle = (id: string) => ir.nodes[id]?.title || id;
  return {
    goals: (impact.affectedGoals || []).map(toTitle),
    actors: (impact.affectedActors || []).map(toTitle),
    flows: (impact.affectedFlows || []).map(toTitle),
    objects: (impact.affectedObjects || []).map(toTitle),
    screens: (impact.affectedScreens || []).map(toTitle),
  };
};

export const groupScopeItems = (ir: RequirementSpaceIR | null) => {
  if (!ir) {
    return { inScope: [], deferred: [], dependencies: [], outOfScope: [], excluded: [] } as Record<
      'inScope' | 'deferred' | 'dependencies' | 'outOfScope' | 'excluded',
      RequirementNode[]
    >;
  }
  const nodes = selectAllNodes(ir);
  const deliveryKinds = new Set(['capability', 'task', 'flow', 'screen', 'business_object']);
  const scopeItems = nodes.filter(
    (n) => deliveryKinds.has(n.kind) && (n as any).scopeStatus,
  ) as (RequirementNode & { scopeStatus: ScopeStatus })[];
  const excluded = nodes.filter((n) => n.status === 'excluded');
  return {
    inScope: scopeItems.filter((i) => i.scopeStatus === 'in_scope'),
    deferred: scopeItems.filter((i) => i.scopeStatus === 'deferred'),
    dependencies: scopeItems.filter((i) => i.scopeStatus === 'external_dependency'),
    outOfScope: scopeItems.filter((i) => i.scopeStatus === 'out_of_scope'),
    excluded,
  };
};

export const getTasksForCapability = (ir: RequirementSpaceIR | null, capId: string) => {
  if (!ir) return emptyArray as RequirementNode[];
  const links = selectAllLinks(ir);
  const taskIds = new Set(
    links
      .filter((l) => l.targetId === capId && l.type === 'supports')
      .map((l) => l.sourceId)
  );
  return Array.from(taskIds)
    .map((id) => ir.nodes[id])
    .filter((n) => n && n.kind === 'task');
};

export const getChildCapabilities = (ir: RequirementSpaceIR | null, capId: string) => {
  if (!ir) return emptyArray as RequirementNode[];
  return selectAllLinks(ir)
    .filter((l) => l.type === 'contains' && l.sourceId === capId && ir.nodes[l.targetId]?.kind === 'capability')
    .map((l) => ir.nodes[l.targetId])
    .filter(Boolean);
};

export const getRootCapabilities = (ir: RequirementSpaceIR | null) => {
  if (!ir) return emptyArray as RequirementNode[];
  const capabilities = selectNodesByKind(ir, 'capability');
  const childIds = new Set(
    selectAllLinks(ir)
      .filter((l) => l.type === 'contains' && ir.nodes[l.sourceId]?.kind === 'capability' && ir.nodes[l.targetId]?.kind === 'capability')
      .map((l) => l.targetId)
  );
  return capabilities.filter((cap) => !childIds.has(cap.id));
};

export type TaskFootprint = {
  flowStepCount: number;
  screenCount: number;
  objectCount: number;
};

export type StepDetail = {
  inputs: string[];
  outputs: string[];
  rules: string[];
  stateChanges: string[];
  relatedPages: string[];
  relatedIssueIds: string[];
  relatedChoiceIds: string[];
};

export const buildStepDetail = (ir: RequirementSpaceIR | null, stepId: string): StepDetail => {
  if (!ir) return { inputs: [], outputs: [], rules: [], stateChanges: [], relatedPages: [], relatedIssueIds: [], relatedChoiceIds: [] };
  const links = selectAllLinks(ir);
  const titlesFor = (ids: string[]) => ids.map((id) => ir.nodes[id]?.title || id).filter(Boolean);

  const inputIds = links.filter((l) => l.sourceId === stepId && l.type === 'reads').map((l) => l.targetId);
  const outputIds = links.filter((l) => l.sourceId === stepId && l.type === 'writes').map((l) => l.targetId);
  const ruleIds = links.filter((l) => l.targetId === stepId && l.type === 'guards').map((l) => l.sourceId);
  const transitionIds = links.filter((l) => l.sourceId === stepId && l.type === 'changes_state').map((l) => l.targetId);

  const componentIds = links.filter((l) => l.type === 'invokes_step' && l.targetId === stepId).map((l) => l.sourceId);
  const screenIds = links
    .filter((l) => l.type === 'contains' && componentIds.includes(l.targetId) && ir.nodes[l.sourceId]?.kind === 'screen')
    .map((l) => l.sourceId);
  const relatedSlotIds = selectAllSlots(ir)
    .filter((slot) => (slot.context?.relatedNodeIds || []).includes(stepId))
    .map((slot) => slot.id);
  const relatedChoiceIds = selectAllChoiceGroups(ir)
    .filter((group) => relatedSlotIds.includes(group.slotId))
    .flatMap((group) => group.choices.map((choice) => choice.id));
  const relatedIssueIds = selectAllIssues(ir)
    .filter((issue) => issue.relatedNodeIds.includes(stepId))
    .map((issue) => issue.id);

  return {
    inputs: titlesFor([...new Set(inputIds)]),
    outputs: titlesFor([...new Set(outputIds)]),
    rules: titlesFor([...new Set(ruleIds)]),
    stateChanges: titlesFor([...new Set(transitionIds)]),
    relatedPages: titlesFor([...new Set(screenIds)]),
    relatedIssueIds: [...new Set(relatedIssueIds)],
    relatedChoiceIds: [...new Set(relatedChoiceIds)],
  };
};

const buildPrecedesTopology = (ir: RequirementSpaceIR): string[] => {
  const flowSteps = selectNodesByKind(ir, 'flow_step');
  const stepIds = flowSteps.map((step) => step.id);
  const stepIdSet = new Set(stepIds);
  const precedes = selectAllLinks(ir).filter(
    (link) => link.type === 'precedes' && stepIdSet.has(link.sourceId) && stepIdSet.has(link.targetId),
  );
  const indegree = new Map<string, number>(stepIds.map((id) => [id, 0]));
  const adjacency = new Map<string, string[]>(stepIds.map((id) => [id, []]));

  for (const link of precedes) {
    indegree.set(link.targetId, (indegree.get(link.targetId) || 0) + 1);
    adjacency.get(link.sourceId)?.push(link.targetId);
  }

  const queue = stepIds
    .filter((id) => (indegree.get(id) || 0) === 0)
    .sort((a, b) => String(ir.nodes[a]?.title || a).localeCompare(String(ir.nodes[b]?.title || b)));
  const ordered: string[] = [];

  while (queue.length > 0) {
    const current = queue.shift()!;
    ordered.push(current);
    for (const next of adjacency.get(current) || []) {
      indegree.set(next, (indegree.get(next) || 0) - 1);
      if ((indegree.get(next) || 0) === 0) {
        queue.push(next);
        queue.sort((a, b) => String(ir.nodes[a]?.title || a).localeCompare(String(ir.nodes[b]?.title || b)));
      }
    }
  }

  for (const id of stepIds) {
    if (!ordered.includes(id)) ordered.push(id);
  }
  return ordered;
};

export const buildTaskFootprint = (ir: RequirementSpaceIR | null, taskId: string): TaskFootprint => {
  if (!ir) return { flowStepCount: 0, screenCount: 0, objectCount: 0 };
  const links = selectAllLinks(ir);

  const stepIds = links
    .filter((l) => l.targetId === taskId && l.type === 'supports')
    .map((l) => l.sourceId)
    .filter((id) => ir.nodes[id]?.kind === 'flow_step');

  const uniqStepIds = [...new Set(stepIds)];

  const actionComponentIds = links
    .filter((l) => uniqStepIds.includes(l.targetId) && l.type === 'invokes_step')
    .map((l) => l.sourceId)
    .filter((id) => ir.nodes[id]?.kind === 'ui_component');

  const screenIds = links
    .filter((l) => l.type === 'contains' && actionComponentIds.includes(l.targetId))
    .map((l) => l.sourceId)
    .filter((id) => ir.nodes[id]?.kind === 'screen');

  const objectIds = links
    .filter(
      (l) =>
        (uniqStepIds.includes(l.sourceId) || uniqStepIds.includes(l.targetId)) &&
        (l.type === 'reads' || l.type === 'writes' || l.type === 'changes_state')
    )
    .map((l) => (uniqStepIds.includes(l.sourceId) ? l.targetId : l.sourceId))
    .filter((id) => ir.nodes[id]?.kind === 'business_object');

  return {
    flowStepCount: uniqStepIds.length,
    screenCount: [...new Set(screenIds)].length,
    objectCount: [...new Set(objectIds)].length,
  };
};

export type SystemProjection = {
  swimlanes: string[];
  abnormalIssues: Issue[];
  getStepsBySwimlane: (lane: string) => FlowStepNode[];
  getNextStepTitles: (stepId: string) => string[];
  getExceptionStepTitles: (stepId: string) => string[];
  getStepSlots: (stepId: string) => Array<{ id: string; title: string; choiceCount: number; status: RequirementSlot['status'] }>;
  businessObjects: RequirementNode[];
  getRelatedStepsForObject: (objectId: string) => RequirementNode[];
};

export const buildSystemProjection = (ir: RequirementSpaceIR | null): SystemProjection => {
  const swimlanes = (() => {
    if (!ir) return ['系统'];
    const actors = selectNodesByKind(ir, 'actor') as any[];
    const titles = actors.map((a) => a.title).filter(Boolean);
    const hasSystem = titles.includes('系统');
    const lanes = [...titles];
    if (!hasSystem) lanes.push('系统');
    if (!lanes.length) return ['系统'];
    return lanes;
  })();

  const empty = {
    swimlanes,
    abnormalIssues: [],
    getStepsBySwimlane: () => [],
    getNextStepTitles: () => [],
    getExceptionStepTitles: () => [],
    getStepSlots: () => [],
    businessObjects: [],
    getRelatedStepsForObject: () => [],
  } satisfies SystemProjection;
  if (!ir) return empty;

  const flowSteps = selectNodesByKind(ir, 'flow_step');
  const links = selectAllLinks(ir);
  const slots = selectAllSlots(ir);
  const issues = selectAllIssues(ir);
  const abnormalIssues = issues.filter((g) => g.category === 'flow_gap' || g.category === 'rule_gap');
  const businessObjects = selectNodesByKind(ir, 'business_object');
  const topology = buildPrecedesTopology(ir);
  const topologyIndex = new Map(topology.map((id, index) => [id, index]));

  const getStepsBySwimlane = (lane: string) =>
    (flowSteps
      .filter((s: any) => selectPerformerTitle(ir, s.id) === lane)
      .sort((a: any, b: any) => (topologyIndex.get(a.id) || 0) - (topologyIndex.get(b.id) || 0)) as unknown as FlowStepNode[]);

  const getNextStepTitles = (stepId: string) =>
    links
      .filter((l) => l.sourceId === stepId && l.type === 'precedes')
      .map((l) => ir.nodes[l.targetId]?.title)
      .filter(Boolean) as string[];

  const getExceptionStepTitles = (stepId: string) =>
    links
      .filter((l) => l.sourceId === stepId && l.type === 'branches_to')
      .map((l) => ir.nodes[l.targetId]?.title)
      .filter(Boolean) as string[];

  const getStepSlots = (stepId: string) =>
    slots
      .filter((s) => (s.context?.relatedNodeIds || []).includes(stepId))
      .map((s) => {
        const group = Object.values(ir.choiceGroups || {}).find((cg) => cg.slotId === s.id);
        const groupCount = group?.choices?.length || 0;
        return { id: s.id, title: s.name, choiceCount: groupCount, status: s.status };
      });

  const getRelatedStepsForObject = (objectId: string) => {
    const relatedStepIds = links
      .filter(
        (l) =>
          (l.sourceId === objectId || l.targetId === objectId) &&
          (l.type === 'reads' || l.type === 'writes' || l.type === 'changes_state')
      )
      .map((l) => (l.sourceId === objectId ? l.targetId : l.sourceId))
      .filter((id: string) => ir.nodes?.[id]?.kind === 'flow_step');

    const uniq = [...new Set(relatedStepIds)];
    return uniq.map((id) => ir.nodes[id]).filter(Boolean);
  };

  return {
    swimlanes,
    abnormalIssues,
    getStepsBySwimlane,
    getNextStepTitles,
    getExceptionStepTitles,
    getStepSlots,
    businessObjects,
    getRelatedStepsForObject,
  };
};

export type RolePageModel = {
  id: string;
  name: string;
  desc: string;
  actions: string[];
  relatedSteps: string[];
  relatedIssues: string[];
};

export type GoalBranchItem =
  | { kind: 'issue'; issue: Issue; projection: ProjectionKind }
  | { kind: 'slot'; slot: RequirementSlot; projection: ProjectionKind }
  | { kind: 'choiceGroup'; choiceGroup: ChoiceGroup; projection: ProjectionKind };

export const buildGoalBranchItems = (ir: RequirementSpaceIR | null): GoalBranchItem[] => {
  if (!ir) return [];
  const goalNodeIds = new Set(
    selectAllNodes(ir)
      .filter((node) => ['goal', 'capability', 'task', 'actor'].includes(node.kind))
      .map((node) => node.id),
  );

  const issueItems = selectAllIssues(ir)
    .filter(
      (issue) =>
        issue.status === 'open' &&
        (issue.suggestedProjection === 'goal' ||
          issue.suggestedProjection === 'role' ||
          issue.relatedNodeIds.some((id) => goalNodeIds.has(id))),
    )
    .map((issue) => ({ kind: 'issue' as const, issue, projection: issue.suggestedProjection }));

  const slotItems = selectAllSlots(ir)
    .filter(
      (slot) =>
        slot.ownerProjection === 'goal' ||
        slot.ownerProjection === 'role' ||
        goalNodeIds.has(slot.ownerNodeId) ||
        (slot.context?.relatedNodeIds || []).some((id) => goalNodeIds.has(id)),
    )
    .map((slot) => ({ kind: 'slot' as const, slot, projection: slot.ownerProjection }));

  const choiceGroupItems = selectAllChoiceGroups(ir)
    .filter((choiceGroup) => {
      const slot = ir.slots[choiceGroup.slotId];
      if (!slot) return false;
      return (
        choiceGroup.status === 'open' &&
        (slot.ownerProjection === 'goal' ||
          slot.ownerProjection === 'role' ||
          goalNodeIds.has(slot.ownerNodeId) ||
          (slot.context?.relatedNodeIds || []).some((id) => goalNodeIds.has(id)))
      );
    })
    .map((choiceGroup) => {
      const slot = ir.slots[choiceGroup.slotId];
      return { kind: 'choiceGroup' as const, choiceGroup, projection: slot?.ownerProjection || 'goal' };
    });

  return [...issueItems, ...choiceGroupItems, ...slotItems];
};

export type PreviewCheckpoint = {
  id: 'initial' | 'structure' | 'flow' | 'delivery';
  title: string;
  projection: ProjectionKind;
  passed: boolean;
  checks: Array<{ label: string; passed: boolean }>;
};

export const buildPreviewCheckpoints = (ir: RequirementSpaceIR | null): PreviewCheckpoint[] => {
  if (!ir) {
    return [
      { id: 'initial', title: '初始输入', projection: 'goal', passed: false, checks: [] },
      { id: 'structure', title: '结构成型', projection: 'goal', passed: false, checks: [] },
      { id: 'flow', title: '流程闭环', projection: 'system', passed: false, checks: [] },
      { id: 'delivery', title: '交付确认', projection: 'ui', passed: false, checks: [] },
    ];
  }

  const goals = selectNodesByKind(ir, 'goal');
  const capabilities = selectNodesByKind(ir, 'capability');
  const tasks = selectNodesByKind(ir, 'task');
  const actors = selectNodesByKind(ir, 'actor');
  const flowSteps = selectNodesByKind(ir, 'flow_step');
  const screens = selectNodesByKind(ir, 'screen');
  const issues = selectAllIssues(ir).filter((issue) => issue.status === 'open');
  const slots = selectAllSlots(ir).filter((slot) => slot.status === 'empty' || slot.status === 'candidate_ready');
  const proposals = selectAllProposals(ir).filter((proposal) => proposal.status === 'candidate' || proposal.status === 'draft');

  const checkpoints: PreviewCheckpoint[] = [
    {
      id: 'initial',
      title: '初始输入',
      projection: 'goal',
      checks: [
        { label: '存在核心目标', passed: goals.length > 0 },
        { label: '存在主要角色', passed: actors.length > 0 },
      ],
      passed: false,
    },
    {
      id: 'structure',
      title: '结构成型',
      projection: 'goal',
      checks: [
        { label: '存在能力定义', passed: capabilities.length > 0 },
        { label: '存在关键任务', passed: tasks.length > 0 },
      ],
      passed: false,
    },
    {
      id: 'flow',
      title: '流程闭环',
      projection: 'system',
      checks: [
        { label: '存在流程步骤', passed: flowSteps.length > 0 },
        { label: '无高风险流程 Issue', passed: !issues.some((issue) => issue.category === 'flow_gap' && issue.severity === 'high') },
      ],
      passed: false,
    },
    {
      id: 'delivery',
      title: '交付确认',
      projection: 'ui',
      checks: [
        { label: '存在界面与组件树', passed: screens.length > 0 },
        { label: '无待决策 Slot', passed: slots.length === 0 },
        { label: '无待审阅 Proposal', passed: proposals.length === 0 },
      ],
      passed: false,
    },
  ];

  return checkpoints.map((checkpoint) => ({
    ...checkpoint,
    passed: checkpoint.checks.every((check) => check.passed),
  }));
};

export const buildPlaybackForActor = (ir: RequirementSpaceIR | null, actorId: string | null) => {
  if (!ir || !actorId) return [];
  const rolePages = buildRolePages(ir, actorId);
  const topology = buildPrecedesTopology(ir);
  const links = selectAllLinks(ir);

  return rolePages.map((page) => {
    const screenId = page.id;
    const componentIds = links
      .filter((link) => link.type === 'contains' && link.sourceId === screenId && ir.nodes[link.targetId]?.kind === 'ui_component')
      .map((link) => link.targetId);
    const invokedSteps = links
      .filter((link) => link.type === 'invokes_step' && componentIds.includes(link.sourceId))
      .map((link) => link.targetId)
      .filter((stepId) => ir.nodes[stepId]?.kind === 'flow_step');

    const sortedStepIds = [...new Set(invokedSteps)].sort((a, b) => topology.indexOf(a) - topology.indexOf(b));

    return {
      screenId,
      screenTitle: page.name,
      stepIds: sortedStepIds,
      stepTitles: sortedStepIds.map((id) => ir.nodes[id]?.title || id),
    };
  });
};

export const buildRolePages = (ir: RequirementSpaceIR | null, actorId: string | null): RolePageModel[] => {
  if (!ir || !actorId) return [];
  const links = selectAllLinks(ir);
  const issues = selectAllIssues(ir);

  const accessibleScreenLinks = links.filter((l) => l.targetId === actorId && l.type === 'accessible_by');
  const screenIds = accessibleScreenLinks.map((l) => l.sourceId).filter((id) => ir.nodes[id]?.kind === 'screen');

  return screenIds
    .map((id) => {
      const screenNode: any = ir.nodes[id];
      if (!screenNode) return null;

      const childIds = links
        .filter((l) => l.type === 'contains' && l.sourceId === id)
        .map((l) => l.targetId)
        .filter((cid) => ir.nodes[cid]?.kind === 'ui_component');

      const actions = childIds.filter((cid) => {
        const n: any = ir.nodes[cid];
        const ct = String(n?.componentType || '');
        const title = String(n?.title || '');
        return ct === 'button' || title.includes('Button') || title.includes('Action') || title.includes('按钮');
      });

      const relatedStepLinks = childIds.flatMap((cid) =>
        links.filter((l) => l.sourceId === cid && l.type === 'invokes_step')
      );
      const relatedStepIds = [...new Set(relatedStepLinks.map((l) => l.targetId))];

      const relatedIssuesForScreen = issues.filter(
        (issue) => issue.relatedNodeIds.includes(id) || childIds.some((cid) => issue.relatedNodeIds.includes(cid))
      );

      return {
        id,
        name: screenNode.title,
        desc: screenNode.description || '无描述',
        actions: actions.map((a) => ir.nodes[a]?.title || a),
        relatedSteps: relatedStepIds.map((s) => ir.nodes[s]?.title || s),
        relatedIssues: relatedIssuesForScreen.map((issue) => issue.title),
      } as RolePageModel;
    })
    .filter(Boolean) as RolePageModel[];
};
