import { describe, expect, it } from 'vitest';
import { getStageIssues } from '../core/selectors';
import { isCountableFinding } from '../core/findingPresentation';
import type { Finding, RequirementSpace } from '../core/schema';

const finding = (overrides: Partial<Finding>): Finding => ({
  findingId: 'finding-1',
  type: 'issue',
  stage: 'what',
  code: 'LEAF_FEATURE_WITHOUT_ACTOR',
  severity: 'blocking',
  title: 'Finding',
  description: 'Finding description',
  blockingScope: 'stage_transition',
  metadata: {},
  ...overrides,
});

describe('findingDisplay - canonical Finding selectors', () => {
  it('filters non-countable codes without a legacy Issue projection', () => {
    const space = {
      projectId: 'project-123',
      projectName: 'Test Project',
      actors: [],
      features: [],
      flows: [],
      businessObjects: [],
      findings: [
        finding({ findingId: 'countable' }),
        finding({
          findingId: 'quality',
          code: 'ACTOR_WITHOUT_FEATURE',
          severity: 'warning',
          blockingScope: 'none',
        }),
      ],
    } as RequirementSpace;

    expect(getStageIssues(space, 'what').map((item) => item.findingId)).toEqual(['countable']);
  });

  it('classifies quality-only codes as non-countable', () => {
    expect(isCountableFinding(finding({ code: 'ACTOR_WITHOUT_FEATURE' }))).toBe(false);
    expect(isCountableFinding(finding({ code: 'DUPLICATE_SCENARIO_NAME' }))).toBe(false);
  });
});
