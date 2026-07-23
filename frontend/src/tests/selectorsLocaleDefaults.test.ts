import { afterEach, describe, expect, it } from 'vitest';
import i18n from '@/i18n';
import {
  buildRolePages,
  buildStepDetail,
  buildSystemProjection,
  SYSTEM_SWIMLANE_ID,
} from '@/core/selectors';
import type { RequirementSpace } from '@/core/schema';

const space = {
  actors: [{ actorId: 1, actorName: 'Operator' }],
  features: [{ featureId: 2, featureName: 'Order Review', featureDescription: '', parentId: 1, actorIds: [1], scenarios: [] }],
  businessObjects: [{ businessObjectId: 3, businessObjectName: 'Order' }],
  flows: [{ flowId: 4, featureIds: [2], flowSteps: [{ stepId: 5, stepName: 'Review', actorIds: [], outputBusinessObjectIds: [3] }] }],
} as unknown as RequirementSpace;

describe('selector locale defaults', () => {
  afterEach(async () => {
    await i18n.changeLanguage('zh-CN');
  });

  it('produces English default flow-step and role-page content', async () => {
    await i18n.changeLanguage('en-US');

    expect(buildStepDetail(space, 5)).toMatchObject({
      rules: ['Satisfies the primary workflow constraints', 'Ensures AI workflow continuity'],
      stateChanges: ['Order status updated'],
      relatedPages: ['Operations Console', 'Scan Entry Page'],
    });
    expect(buildRolePages(space, '1')[0]).toMatchObject({
      name: 'Order Review Operations Screen',
      desc: 'An interface for Operator to perform Order Review.',
      relatedSteps: ['Operate and process Order Review'],
    });
  });

  it('uses a stable identifier for the system swimlane', () => {
    const projection = buildSystemProjection(space);

    expect(projection.swimlanes).toContain(SYSTEM_SWIMLANE_ID);
    expect(projection.swimlanes).not.toContain('系统');
    expect(projection.getStepsBySwimlane(SYSTEM_SWIMLANE_ID)).toHaveLength(1);
  });
});
