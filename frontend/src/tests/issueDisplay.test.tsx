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

const spaceWith = (findings: Finding[]): RequirementSpace => ({
  kind: 'requirement_space',
  projectId: 'project-123',
  projectName: 'Test Project',
  projectDescription: '',
  userRequirements: '',
  perceptionSlot: null,
  actors: [],
  features: [],
  flows: [],
  businessObjects: [],
  findings,
});

describe('canonical Finding issue display', () => {
  it('counts normal issue findings and excludes hints', () => {
    expect(isCountableFinding(finding({}))).toBe(true);
    expect(isCountableFinding(finding({ type: 'quality_hint' }))).toBe(false);
    expect(isCountableFinding(finding({ severity: 'info' }))).toBe(false);
  });

  it('returns issue findings for the requested stage', () => {
    const space = spaceWith([
      finding({ findingId: 'what-finding' }),
      finding({ findingId: 'how-finding', stage: 'how', code: 'FLOW_WITHOUT_STEPS' }),
    ]);

    expect(getStageIssues(space, 'what').map((item) => item.findingId)).toEqual(['what-finding']);
    expect(getStageIssues(space, 'how').map((item) => item.findingId)).toEqual(['how-finding']);
  });
});
