import { describe, expect, it } from 'vitest';
import { buildOverviewModel } from '../core/selectors';
import type { RequirementSpace } from '../core/schema';

describe('aiHypothesisLedgerBaseline - AI Hypothesis Ledger Scanner', () => {
  it('scans and collects only nodes with ai_assumption status', () => {
    const mockSpace = {
      kind: 'requirement_space',
      projectId: 'p-1',
      projectName: 'Test Project',
      projectDescription: '',
      userRequirements: '',
      actors: [
        {
          kind: 'actor',
          actorId: 1,
          actorName: 'Actor AI',
          actorDescription: 'AI assumption',
          confirmationStatus: 'ai_assumption',
        },
        {
          kind: 'actor',
          actorId: 2,
          actorName: 'Actor Confirmed',
          actorDescription: 'Confirmed',
          confirmationStatus: 'confirmed',
        },
      ],
      features: [
        {
          kind: 'feature',
          featureId: 10,
          featureName: 'Feature AI',
          featureDescription: 'AI Feature',
          actorIds: [],
          parentId: null,
          childrenIds: [],
          scenarios: [],
          scope: null,
          confirmationStatus: 'ai_assumption',
        },
      ],
      businessObjects: [
        {
          kind: 'business_object',
          businessObjectId: 20,
          businessObjectName: 'BO Needs Confirm',
          businessObjectDescription: 'Needs Confirm',
          confirmationStatus: 'needs_confirmation',
          businessObjectAttributes: [],
        },
      ],
      flows: [],
    } as unknown as RequirementSpace;

    const result = buildOverviewModel(mockSpace, []);
    
    // Check that aiAssumptionLedger only includes 'actor-1' and 'feature-10'
    const ledger = result.aiAssumptionLedger;
    expect(ledger).toBeDefined();
    
    const ids = ledger.map(item => item.id);
    expect(ids).toContain('actor-1');
    expect(ids).toContain('feature-10');
    expect(ids).not.toContain('actor-2');
    expect(ids).not.toContain('business_object-20');
    
    // Check fields of the ledger item
    const actorItem = ledger.find(item => item.id === 'actor-1');
    expect(actorItem.kind).toBe('actor');
    expect(actorItem.nodeId).toBe(1);
    expect(actorItem.title).toBe('Actor AI');
    expect(actorItem.source).toBe('AI assumption');
    expect(actorItem.status).toBe('ai_assumption');
  });

  it('returns locale keys and parameters for open decision queue entries', () => {
    const mockSpace = {
      actors: [],
      features: [],
      businessObjects: [],
      flows: [],
      choiceGroups: {
        'choice-group-1': {
          id: 'choice-group-1',
          status: 'open',
          generationType: 'actor',
          statusDetail: { comparisonSummary: '均衡版：2 个参与者候选方案' },
          choices: [{ status: 'candidate' }, { status: 'candidate' }],
        },
      },
    } as unknown as RequirementSpace;

    const entry = buildOverviewModel(mockSpace).decisionQueue[0];
    expect(entry).toEqual(expect.objectContaining({
      titleKey: 'overview.decisionQueue.titleWithType',
      titleParams: { typeKey: 'overview.decisionQueue.types.actor' },
      descriptionKey: 'overview.decisionQueue.descriptionWithType',
      descriptionParams: { count: 2, typeKey: 'overview.decisionQueue.types.actor' },
    }));
    expect(entry).not.toHaveProperty('description');
  });
});
