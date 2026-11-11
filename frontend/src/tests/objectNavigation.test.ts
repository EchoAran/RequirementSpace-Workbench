import { describe, it, expect } from 'vitest';
import { jumpTargetForEntity, findIrNodeByUuid } from '../core/objectNavigation';

describe('jumpTargetForEntity', () => {
  it('actor/feature/feature_relation/scenario/acceptance_criterion → /what', () => {
    expect(jumpTargetForEntity('actor')).toBe('/what');
    expect(jumpTargetForEntity('feature')).toBe('/what');
    expect(jumpTargetForEntity('feature_relation')).toBe('/what');
    expect(jumpTargetForEntity('scenario')).toBe('/what');
    expect(jumpTargetForEntity('acceptance_criterion')).toBe('/what');
  });

  it('flow/flow_step/business_object/business_object_attribute → /flow', () => {
    expect(jumpTargetForEntity('flow')).toBe('/flow');
    expect(jumpTargetForEntity('flow_step')).toBe('/flow');
    expect(jumpTargetForEntity('business_object')).toBe('/flow');
    expect(jumpTargetForEntity('business_object_attribute')).toBe('/flow');
  });

  it('scope → /scope；project_metadata → null', () => {
    expect(jumpTargetForEntity('scope')).toBe('/scope');
    expect(jumpTargetForEntity('project_metadata')).toBeNull();
  });
});

describe('findIrNodeByUuid', () => {
  const ir = {
    projectId: 'p1',
    actors: [{ logicalUuid: 'act-1', actorId: 1 }],
    features: [
      { logicalUuid: 'feat-1', featureId: 1, scenarios: [{ logicalUuid: 'scen-1', scenarioId: 10, acceptanceCriteria: [{ logicalUuid: 'ac-1', criterionId: 100 }] }], scope: { logicalUuid: 'scope-1', scopeId: 200 } },
    ],
    businessObjects: [{ logicalUuid: 'bo-1', businessObjectId: 3, businessObjectAttributes: [{ logicalUuid: 'attr-1', businessObjectAttributeId: 30 }] }],
    flows: [{ logicalUuid: 'flow-1', flowId: 4, flowSteps: [{ logicalUuid: 'step-1', stepId: 40 }] }],
  } as any;

  it('顶层实体按 logicalUuid 命中', () => {
    expect(findIrNodeByUuid(ir, 'actor', 'act-1')?.actorId).toBe(1);
    expect(findIrNodeByUuid(ir, 'feature', 'feat-1')?.featureId).toBe(1);
    expect(findIrNodeByUuid(ir, 'business_object', 'bo-1')?.businessObjectId).toBe(3);
    expect(findIrNodeByUuid(ir, 'flow', 'flow-1')?.flowId).toBe(4);
  });

  it('嵌套实体命中', () => {
    expect(findIrNodeByUuid(ir, 'scenario', 'scen-1')?.scenarioId).toBe(10);
    expect(findIrNodeByUuid(ir, 'acceptance_criterion', 'ac-1')?.criterionId).toBe(100);
    expect(findIrNodeByUuid(ir, 'business_object_attribute', 'attr-1')?.businessObjectAttributeId).toBe(30);
    expect(findIrNodeByUuid(ir, 'flow_step', 'step-1')?.stepId).toBe(40);
  });

  it('scope 经 feature.scope 命中', () => {
    expect(findIrNodeByUuid(ir, 'scope', 'scope-1')?.scopeId).toBe(200);
  });

  it('未命中返回 null', () => {
    expect(findIrNodeByUuid(ir, 'feature', 'missing')).toBeNull();
    expect(findIrNodeByUuid(null, 'feature', 'x')).toBeNull();
  });
});
