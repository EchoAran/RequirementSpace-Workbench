import type {
  Choice,
  ChoiceGroup,
  ImpactPreview,
  Issue,
  FlowStepNode,
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
  | { kind: 'choiceGroup'; choiceGroup: ChoiceGroup; ownerProjection: ProjectionKind };

export const buildDecisionQueue = (ir: RequirementSpaceIR | null): DecisionQueueItem[] => {
  if (!ir) return [];
  const issues = selectAllIssues(ir).filter((i) => i.status === 'open');
  const slots = selectAllSlots(ir).filter((s) => s.status === 'candidate_ready' || s.status === 'empty');
  const groups = selectAllChoiceGroups(ir).filter((g) => g.status === 'open');

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

  const severityRank: Record<string, number> = { high: 0, medium: 1, low: 2 };
  const kindRank: Record<DecisionQueueItem['kind'], number> = { issue: 0, slot: 1, choiceGroup: 2 };
  return items.sort((a, b) => {
    const ak = kindRank[a.kind] - kindRank[b.kind];
    if (ak !== 0) return ak;
    const as = a.kind === 'issue' ? severityRank[a.severity] : 3;
    const bs = b.kind === 'issue' ? severityRank[b.severity] : 3;
    return as - bs;
  });
};

export type PageHealth = {
  status: '阻塞' | '待决策' | '可预览' | '已收敛' | '不可用' | '未开始';
  gapCount: number;
  todoCount: number;
  hasRisk: boolean;
  disabled: boolean;
};

export const buildPageHealth = (ir: RequirementSpaceIR | null, path: string): PageHealth => {
  if (!ir) return { status: '未开始', gapCount: 0, todoCount: 0, hasRisk: false, disabled: false };

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
    return { status: '不可用', gapCount: 0, todoCount: 0, hasRisk: false, disabled: true };
  }

  const todoCount = items.filter(
    (i) => i.status === 'needs_confirmation' || i.status === 'ai_assumption'
  ).length;
  const gapCount = relatedIssues.filter((g) => g.status === 'open').length;
  const blockingCount = relatedIssues.filter((g) => g.severity === 'high' && g.status === 'open').length;
  const hasRisk = blockingCount > 0;

  let status: PageHealth['status'] = '未开始';
  if (items.length > 0) {
    if (hasRisk) status = '阻塞';
    else if (todoCount > 0 || gapCount > 0) status = '待决策';
    else if (isPreview) status = '可预览';
    else status = '已收敛';
  }

  return { status, gapCount, todoCount, hasRisk, disabled: isPreview ? !isAvailable : false };
};

export type OverviewModel = {
  readiness: ReadinessSummary;
  highRiskIssues: Issue[];
  decisionQueue: Array<{ id: string; kind: 'issue' | 'slot' | 'choiceGroup'; title: string; description: string; original: any }>;
  recentCandidates: Choice[];
  openChoiceGroupsCount: number;
  openSlotsCount: number;
};

export const buildOverviewModel = (ir: RequirementSpaceIR | null): OverviewModel => {
  const readiness = buildReadiness(ir);
  if (!ir) {
    return {
      readiness,
      highRiskIssues: [],
      decisionQueue: [],
      recentCandidates: [],
      openChoiceGroupsCount: 0,
      openSlotsCount: 0,
    };
  }

  const issues = selectAllIssues(ir);
  const highRiskIssues = issues.filter((g) => g.severity === 'high' && g.status === 'open');

  const groups = selectAllChoiceGroups(ir);
  const openChoiceGroupsCount = groups.filter((cg) => cg.status === 'open').length;

  const slots = selectAllSlots(ir);
  const openSlotsCount = slots.filter((s) => s.status === 'candidate_ready' || s.status === 'empty').length;

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
          description: item.slot.description || '等待补充候选方案',
          original: item.slot,
        };
      }
      const slot = ir.slots?.[item.choiceGroup.slotId];
      return {
        id: item.choiceGroup.id,
        kind: 'choiceGroup' as const,
        title: slot?.name || `槽位：${item.choiceGroup.slotId}`,
        description: `有 ${(item.choiceGroup.choices || []).length} 个候选方案待确认`,
        original: item.choiceGroup,
      };
    });

  const recentCandidates = selectAllChoices(ir).filter((c) => c.status === 'candidate').slice(0, 3);
  return { readiness, highRiskIssues, decisionQueue: dq, recentCandidates, openChoiceGroupsCount, openSlotsCount };
};

export const projectionPath = (projection: ProjectionKind) => {
  if (projection === 'system') return '/flow';
  if (projection === 'data') return '/scope';
  if (projection === 'ui') return '/preview';
  return '/what';
};

export type ScopeImpact = { flows: string[]; objects: string[]; screens: string[] };

export const buildScopeImpact = (ir: RequirementSpaceIR | null, nodeId: string | null): ScopeImpact => {
  if (!ir || !nodeId) return { flows: [], objects: [], screens: [] };
  const links = selectAllLinks(ir);
  const relatedLinks = links.filter((l) => l.sourceId === nodeId || l.targetId === nodeId);
  if (!relatedLinks.length) return { flows: [], objects: [], screens: [] };

  const affected = relatedLinks.map((l) => (l.sourceId === nodeId ? l.targetId : l.sourceId));
  const flows = [...new Set(affected.filter((id) => ['flow_step', 'flow'].includes((ir.nodes[id] as any)?.kind)))];
  const objects = [...new Set(affected.filter((id) => (ir.nodes[id] as any)?.kind === 'business_object'))];
  const screens = [...new Set(affected.filter((id) => (ir.nodes[id] as any)?.kind === 'screen'))];
  return { flows, objects, screens };
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
  const scopeItems = nodes.filter((n) => (n as any).scopeStatus) as (RequirementNode & { scopeStatus: ScopeStatus })[];
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
      .filter((l) => l.targetId === capId && (l.type === 'supports' || l.type === 'realizes'))
      .map((l) => l.sourceId)
  );
  return Array.from(taskIds)
    .map((id) => ir.nodes[id])
    .filter((n) => n && n.kind === 'task');
};

export type TaskFootprint = {
  flowStepCount: number;
  screenCount: number;
  objectCount: number;
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
    .filter((l) => uniqStepIds.includes(l.targetId) && (l.type === 'triggered_by' || l.type === 'invokes_step'))
    .map((l) => l.sourceId)
    .filter((id) => ir.nodes[id]?.kind === 'ui_component');

  const screenIds = links
    .filter(
      (l) =>
        (l.type === 'displayed_on' && actionComponentIds.includes(l.sourceId)) ||
        (l.type === 'contains' && actionComponentIds.includes(l.targetId))
    )
    .map((l) => (l.type === 'displayed_on' ? l.targetId : l.sourceId))
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
  getStepSlots: (stepId: string) => Array<{ id: string; title: string; candidatesCount: number }>;
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

  const getStepsBySwimlane = (lane: string) =>
    (flowSteps.filter((s: any) => selectPerformerTitle(ir, s.id) === lane) as unknown as FlowStepNode[]);

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
        const groupCount = s.choiceGroupId ? ir.choiceGroups[s.choiceGroupId]?.choices?.length || 0 : 0;
        return { id: s.id, title: s.name, candidatesCount: groupCount };
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
  relatedGaps: string[];
};

export const buildRolePages = (ir: RequirementSpaceIR | null, actorId: string | null): RolePageModel[] => {
  if (!ir || !actorId) return [];
  const links = selectAllLinks(ir);
  const gaps = selectAllIssues(ir);

  const screenLinks = links.filter((l) => l.targetId === actorId && (l.type === 'reads' || l.type === 'accessible_by'));
  const screenIds = screenLinks.map((l) => l.sourceId).filter((id) => ir.nodes[id]?.kind === 'screen');

  return screenIds
    .map((id) => {
      const screenNode: any = ir.nodes[id];
      if (!screenNode) return null;

      const childIds = links
        .filter(
          (l) =>
            (l.type === 'displayed_on' && l.targetId === id) ||
            (l.type === 'contains' && l.sourceId === id)
        )
        .map((l) => (l.type === 'displayed_on' ? l.sourceId : l.targetId))
        .filter((cid) => ir.nodes[cid]?.kind === 'ui_component');

      const actions = childIds.filter((cid) => {
        const n: any = ir.nodes[cid];
        const ct = String(n?.componentType || '');
        const title = String(n?.title || '');
        return ct === 'button' || title.includes('Button') || title.includes('Action') || title.includes('按钮');
      });

      const relatedStepLinks = childIds.flatMap((cid) =>
        links.filter((l) => l.sourceId === cid && (l.type === 'triggered_by' || l.type === 'invokes_step'))
      );
      const relatedStepIds = [...new Set(relatedStepLinks.map((l) => l.targetId))];

      const relatedGapsToScreen = gaps.filter(
        (g) => g.relatedNodeIds.includes(id) || childIds.some((cid) => g.relatedNodeIds.includes(cid))
      );

      return {
        id,
        name: screenNode.title,
        desc: screenNode.description || '无描述',
        actions: actions.map((a) => ir.nodes[a]?.title || a),
        relatedSteps: relatedStepIds.map((s) => ir.nodes[s]?.title || s),
        relatedGaps: relatedGapsToScreen.map((g) => g.title),
      } as RolePageModel;
    })
    .filter(Boolean) as RolePageModel[];
};
