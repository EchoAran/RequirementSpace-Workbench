import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, renderHook, screen } from '@testing-library/react';
import { useTranslation } from 'react-i18next';
import { MemoryRouter } from 'react-router-dom';
import { StageGuidanceBanner } from '../components/shared/StageGuidanceBanner';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import type { Finding } from '../core/schema';

const stages = ['what', 'how'] as const;
const states = ['healthy', 'incomplete', 'blocked', 'transition', 'suggestion', 'health', 'loading', 'failed'] as const;
const fullSpace = () => ({
  projectId: 'project-123',
  projectName: 'Test Project',
  actors: [{ actorId: 1 }],
  features: [{ featureId: 1, scenarios: [{ scenarioId: 1, acceptanceCriteria: [{ criterionId: 1 }] }] }],
  domainRules: [{ ruleId: 1 }],
  flows: [{ flowId: 1 }],
  businessObjects: [{ objectId: 1 }],
  perceptionSlot: null,
});

// States where the banner still surfaces a manual diagnosis trigger:
// compact empty/loading cards, or the Space Health section (health hints present).
const triggerStates = ['healthy', 'health', 'loading'] as const;
// States with actionable content but no health hints: the reworked banner no longer
// renders a standalone diagnosis button there.
const hiddenStates = ['incomplete', 'blocked', 'transition', 'suggestion', 'failed'] as const;

const buildStageFinding = ({ stage, state }: { stage: 'what' | 'how'; state: string }): Finding => {
  return {
    findingId: `${stage}:TEST:project:1`,
    stage,
    code: state === 'failed' ? 'ACTOR_PERCEPTION_FAILED' : 'TEST',
    type: state === 'blocked' ? 'issue' : state === 'health' ? 'quality_hint' : 'next_suggestion',
    severity: state === 'blocked' ? 'blocking' : 'info',
    blockingScope: state === 'blocked' ? 'stage_transition' : 'none',
    title: 'Test finding',
    description: 'Test finding description',
    metadata: state === 'failed'
      ? { source_type: 'perception_slot', status: 'failed', action: { kind: 'retry' } }
      : { action: { kind: 'open_panel', panel: 'perception_slot' } },
  };
};

const applyStageState = ({ stage, state }: { stage: 'what' | 'how'; state: string }) => {
  const finding = buildStageFinding({ stage, state });
  const transitionAction = stage === 'what' ? 'enter_how' : 'enter_scope';
  useWorkspaceStore.setState({
    backendFindingsLoaded: state !== 'loading',
    stageProgress: state === 'loading' ? null : {
      stages: [{
        stage,
        statusCode: state === 'incomplete' ? 'unlocked_not_started'
          : state === 'blocked' ? 'blocked'
            : state === 'transition' ? 'ready_to_advance'
              : state === 'suggestion' ? 'in_progress' : 'ready',
        failedChecks: [],
        blockingFindings: state === 'blocked' ? [finding] : [],
        nextAction: { kind: 'stage_transition', transitionAction },
      }],
    },
    findingsByView: {
      issues: state === 'blocked' ? [finding] : [],
      next_action: state === 'suggestion' || state === 'failed' ? [finding] : [],
      health: state === 'health' ? [finding] : [],
      gate: [],
    },
  });
};

const buildHealthHint = (stage: 'what' | 'how'): Finding => ({
  findingId: `${stage}:TEST:project:1`,
  stage,
  code: 'TEST',
  type: 'quality_hint',
  severity: 'info',
  blockingScope: 'none',
  title: 'Test finding',
  description: 'Test finding description',
  metadata: { action: { kind: 'open_panel', panel: 'perception_slot' } },
});

describe('StageGuidanceBanner manual diagnosis', () => {
  beforeEach(() => {
    useWorkspaceStore.setState({
      ir: fullSpace() as any,
      findingsByView: { issues: [], next_action: [], gate: [], health: [] },
      backendFindingsLoaded: true,
      stageProgress: null,
      isLoading: false,
      isGenerating: false,
      isDiagnosing: false,
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it.each(stages.flatMap((stage) => triggerStates.map((state) => ({ stage, state }))))(
    'keeps manual diagnosis available in $stage / $state',
    ({ stage, state }) => {
      applyStageState({ stage, state });
      const diagnosis = vi.spyOn(useWorkspaceStore.getState(), 'runDiagnosis').mockResolvedValue(undefined);

      render(<MemoryRouter><StageGuidanceBanner stage={stage} /></MemoryRouter>);

      const button = screen.getByRole('button', { name: '诊断需求空间' });
      expect((button as HTMLButtonElement).disabled).toBe(false);
      fireEvent.click(button);
      expect(diagnosis).toHaveBeenCalledExactlyOnceWith(stage);
    },
  );

  it.each(stages.flatMap((stage) => hiddenStates.map((state) => ({ stage, state }))))(
    'hides manual diagnosis when the banner has actionable content in $stage / $state',
    ({ stage, state }) => {
      applyStageState({ stage, state });

      render(<MemoryRouter><StageGuidanceBanner stage={stage} /></MemoryRouter>);

      expect(screen.queryByRole('button', { name: /诊断/ })).toBeNull();
      if (state === 'blocked') {
        expect(screen.queryByRole('button', { name: /进入/ })).toBeNull();
      }
    },
  );

  it.each(['isLoading', 'isGenerating', 'isDiagnosing'] as const)(
    'keeps the button visible but disabled during %s',
    (flag) => {
      useWorkspaceStore.setState({
        [flag]: true,
        stageProgress: { stages: [{ stage: 'how', statusCode: 'in_progress', failedChecks: [], blockingFindings: [] }] },
        findingsByView: { issues: [], next_action: [], gate: [], health: [buildHealthHint('how')] },
      });
      const diagnosis = vi.spyOn(useWorkspaceStore.getState(), 'runDiagnosis').mockResolvedValue(undefined);

      render(<MemoryRouter><StageGuidanceBanner stage="how" /></MemoryRouter>);

      const button = screen.getByRole('button', { name: '诊断需求空间' });
      expect((button as HTMLButtonElement).disabled).toBe(true);
      fireEvent.click(button);
      expect(diagnosis).not.toHaveBeenCalled();
    },
  );

  it.each([
    { stage: 'what', missing: 'actors' },
    { stage: 'what', missing: 'features' },
    { stage: 'what', missing: 'scenarios' },
    { stage: 'what', missing: 'acceptanceCriteria' },
    { stage: 'how', missing: 'domainRules' },
    { stage: 'how', missing: 'flows' },
    { stage: 'how', missing: 'businessObjects' },
  ] as const)('hides manual diagnosis when $stage lacks $missing', ({ stage, missing }) => {
    const space = fullSpace();
    if (missing === 'scenarios') space.features[0].scenarios = [];
    else if (missing === 'acceptanceCriteria') space.features[0].scenarios[0].acceptanceCriteria = [];
    else space[missing] = [];
    useWorkspaceStore.setState({ ir: { ...space, perceptionSlot: { stage } } as any });

    render(<MemoryRouter><StageGuidanceBanner stage={stage} /></MemoryRouter>);

    expect(screen.queryByRole('button', { name: /诊断/ })).toBeNull();
  });

  it.each(states)('hides manual diagnosis in Scope / %s', (state) => {
    useWorkspaceStore.setState({
      stageProgress: state === 'loading' ? null : {
        stages: [{ stage: 'scope', statusCode: state === 'blocked' ? 'blocked' : 'ready', failedChecks: [], blockingFindings: [] }],
      },
      ir: { ...fullSpace(), perceptionSlot: { stage: 'scope' } } as any,
    });

    render(<MemoryRouter><StageGuidanceBanner stage="scope" /></MemoryRouter>);

    expect(screen.queryByRole('button', { name: /诊断/ })).toBeNull();
  });

  it.each(stages)('uses re-diagnose only for a ready perception suggestion in %s', (stage) => {
    const finding = {
      findingId: `${stage}:FEATURE_SLOT:project:1`,
      type: 'next_suggestion',
      stage,
      code: 'FEATURE_SLOT',
      severity: 'info',
      blockingScope: 'none',
      title: 'Supplemental suggestion',
      description: 'Supplemental suggestion description',
      metadata: { source_type: 'perception_slot', status: 'ready', action: { kind: 'open_panel', panel: 'perception_slot' } },
    } as Finding;
    useWorkspaceStore.setState({
      findingsByView: { issues: [], next_action: [finding], health: [buildHealthHint(stage)], gate: [] },
    });

    render(<MemoryRouter><StageGuidanceBanner stage={stage} /></MemoryRouter>);

    expect(screen.queryByRole('button', { name: '重新诊断' })).not.toBeNull();
    expect(screen.queryByRole('button', { name: '诊断需求空间' })).toBeNull();
  });

  it.each(stages)('recognizes the current-stage perception slot in %s', (stage) => {
    useWorkspaceStore.setState({ ir: { ...fullSpace(), perceptionSlot: { stage } } as any });

    render(<MemoryRouter><StageGuidanceBanner stage={stage} /></MemoryRouter>);

    expect(screen.queryByRole('button', { name: '重新诊断' })).not.toBeNull();
  });

  it('does not use another stage\'s perception slot as a reason to re-diagnose', () => {
    useWorkspaceStore.setState({ ir: { ...fullSpace(), perceptionSlot: { stage: 'how' } } as any });

    render(<MemoryRouter><StageGuidanceBanner stage="what" /></MemoryRouter>);

    expect(screen.queryByRole('button', { name: '诊断需求空间' })).not.toBeNull();
    expect(screen.queryByRole('button', { name: '重新诊断' })).toBeNull();
  });

  it.each([false, true])('synchronizes the English diagnosis label when a perception suggestion exists: %s', async (hasSuggestion) => {
    const { result } = renderHook(() => useTranslation());
    await act(async () => { await result.current.i18n.changeLanguage('en-US'); });
    try {
      if (hasSuggestion) {
        useWorkspaceStore.setState({ ir: { ...fullSpace(), perceptionSlot: { stage: 'what' } } as any });
      }

      render(<MemoryRouter><StageGuidanceBanner stage="what" /></MemoryRouter>);

      expect(screen.queryByRole('button', { name: hasSuggestion ? 'Re-diagnose' : 'Diagnose requirements space' })).not.toBeNull();
    } finally {
      await act(async () => { await result.current.i18n.changeLanguage('zh-CN'); });
    }
  });
});
