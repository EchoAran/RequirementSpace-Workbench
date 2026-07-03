import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { buildPageHealth, buildStageGate } from '../core/selectors';
import { LeftNav } from '../components/layout/LeftNav';
import { Overview } from '../pages/Overview';

// Mock sub-components of Overview to avoid deep imports breaking rendering
vi.mock('../components/shared/RightObjectPanel', () => ({
  RightObjectPanel: () => <div data-testid="right-object-panel" />
}));
vi.mock('../components/shared/ChoiceGroupPreviewModal', () => ({
  ChoiceGroupPreviewModal: () => <div data-testid="choice-group-preview-modal" />
}));
vi.mock('../components/shared/StaleChoiceDialog', () => ({
  StaleChoiceDialog: () => <div data-testid="stale-choice-dialog" />
}));
vi.mock('../components/collaboration/ConfirmationWorkspace', () => ({
  ConfirmationWorkspace: () => <div data-testid="confirmation-workspace" />
}));

vi.mock('../lib/api', () => ({
  workspaceApi: {
    listFindings: vi.fn(),
    unlockStage: vi.fn().mockResolvedValue({ message: 'stage_unlocked' }),
    stageTransition: vi.fn().mockResolvedValue({ status: 'unlocked', unlocked_stage: 'what', unlocked_stages: ['what'], blocking_findings: [] }),
    getById: vi.fn().mockResolvedValue({}),
    listChoiceGroups: vi.fn().mockResolvedValue([]),
    listAuditLogs: vi.fn().mockResolvedValue([]),
  }
}));

import { workspaceApi } from '../lib/api';

describe('Stage Transition Phase 1 Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useWorkspaceStore.setState({
      ir: {
        projectId: 'project-123',
        projectName: 'Test Project',
        unlockedStages: '',
        actors: [{ actorId: 1, name: 'User' }],
        features: [
          { featureId: 10, featureName: 'Parent', parentId: null },
          { featureId: 11, featureName: 'Leaf', parentId: 10, actorIds: [1] }
        ],
        flows: [],
        businessObjects: [],
        findings: []
      } as any,
      findingsByView: {
        issues: [],
        next_action: [],
        gate: [],
        health: []
      },
      auditLogs: [],
      sessionVersion: 1,
      isLoading: false,
      error: null,
      activeGateCheck: null,
      stageTransitionInFlight: false,
      stageProgress: null
    });
  });

  it('should evaluate whatGate as passed:true even when transition confirm slot exists', () => {
    const ir = useWorkspaceStore.getState().ir;
    
    // Add scenario & AC to satisfy static mandatory checks for what stage
    ir!.features = [
      { featureId: 10, featureName: 'Parent', parentId: null },
      { 
        featureId: 11, 
        featureName: 'Leaf', 
        parentId: 10, 
        actorIds: [1],
        scenarios: [
          { 
            scenarioId: 1, 
            title: 'Scenario', 
            acceptanceCriteria: [{ id: 1, title: 'AC' }] 
          }
        ]
      } as any
    ];

    // Under this setup, evaluateMandatoryChecks('what') is true.
    // unlockedStages does not contain 'what', so it will generate a transition confirm slot.
    const whatGate = buildStageGate(ir, 'what');
    expect(whatGate.mandatoryChecksPassed).toBe(true);
    expect(whatGate.passed).toBe(true); // Excluded from blocking slot!
    expect(whatGate.blockingSlot).toBeUndefined();
    expect(whatGate.activeSlot?.kind).toBe('stage_gate_transition_confirm');

    const whatHealth = buildPageHealth(ir, '/what');
    expect(whatHealth.statusCode).toBe('ready_to_advance');
    expect(whatHealth.statusLabel).toBe('可进入下一阶段');
  });

  it('should call stageTransition with force:false on requestStageTransition (enter_how)', async () => {
    vi.mocked(workspaceApi.stageTransition).mockResolvedValue({
      status: 'unlocked',
      unlocked_stage: 'what',
      unlocked_stages: ['what'],
      blocking_findings: []
    });

    const refreshSpy = vi.fn().mockResolvedValue(undefined);
    useWorkspaceStore.setState({
      refreshWorkspace: refreshSpy,
      stageProgress: {
        stages: [
          {
            stage: 'what',
            statusCode: 'ready_to_advance',
            nextAction: { kind: 'stage_transition', label: '申请进入下一阶段', transitionAction: 'enter_how' },
            failedChecks: [],
            blockingFindings: []
          },
          { stage: 'how', statusCode: 'locked', nextAction: { kind: 'none', label: '' }, failedChecks: [], blockingFindings: [] },
          { stage: 'scope', statusCode: 'locked', nextAction: { kind: 'none', label: '' }, failedChecks: [], blockingFindings: [] }
        ]
      }
    });

    const navigateSpy = vi.fn();

    await useWorkspaceStore.getState().requestStageTransition('enter_how', { navigate: navigateSpy });

    expect(workspaceApi.stageTransition).toHaveBeenCalledWith('project-123', { action: 'enter_how', force: false });
    expect(refreshSpy).toHaveBeenCalled();
    expect(navigateSpy).toHaveBeenCalledWith('/projects/project-123/flow');
  });

  it('should call stageTransition with force:false on requestStageTransition (enter_scope)', async () => {
    vi.mocked(workspaceApi.stageTransition).mockResolvedValue({
      status: 'unlocked',
      unlocked_stage: 'how',
      unlocked_stages: ['how'],
      blocking_findings: []
    });

    const refreshSpy = vi.fn().mockResolvedValue(undefined);
    useWorkspaceStore.setState({
      refreshWorkspace: refreshSpy,
      stageProgress: {
        stages: [
          {
            stage: 'what',
            statusCode: 'ready_to_advance',
            nextAction: { kind: 'stage_transition', label: '申请进入下一阶段', transitionAction: 'enter_how' },
            failedChecks: [],
            blockingFindings: []
          },
          { stage: 'how', statusCode: 'locked', nextAction: { kind: 'none', label: '' }, failedChecks: [], blockingFindings: [] },
          { stage: 'scope', statusCode: 'locked', nextAction: { kind: 'none', label: '' }, failedChecks: [], blockingFindings: [] }
        ]
      }
    });

    const navigateSpy = vi.fn();

    await useWorkspaceStore.getState().requestStageTransition('enter_scope', { navigate: navigateSpy });

    expect(workspaceApi.stageTransition).toHaveBeenCalledWith('project-123', { action: 'enter_scope', force: false });
    expect(refreshSpy).toHaveBeenCalled();
    expect(navigateSpy).toHaveBeenCalledWith('/projects/project-123/scope');
  });

  it('should prevent duplicate transition calls when stageTransitionInFlight is true', async () => {
    let resolveTransition: any;
    const transitionPromise = new Promise<any>((resolve) => {
      resolveTransition = resolve;
    });
    vi.mocked(workspaceApi.stageTransition).mockReturnValue(transitionPromise);

    const refreshSpy = vi.fn().mockResolvedValue(undefined);
    useWorkspaceStore.setState({ refreshWorkspace: refreshSpy });

    const navigateSpy = vi.fn();

    // Trigger first transition
    const p1 = useWorkspaceStore.getState().requestStageTransition('enter_how', { navigate: navigateSpy });

    // Expect state to be in flight
    expect(useWorkspaceStore.getState().stageTransitionInFlight).toBe(true);

    // Trigger second transition
    await useWorkspaceStore.getState().requestStageTransition('enter_scope', { navigate: navigateSpy });

    // The second call should be ignored, so stageTransition is only called once
    expect(workspaceApi.stageTransition).toHaveBeenCalledTimes(1);

    // Resolve the first transition call
    resolveTransition({
      status: 'unlocked',
      unlocked_stage: 'what',
      unlocked_stages: ['what'],
      blocking_findings: []
    });
    await p1;

    // After completion, it should be false
    expect(useWorkspaceStore.getState().stageTransitionInFlight).toBe(false);
  });

  it('should trigger requestStageTransition when clicking on locked Flow page link in LeftNav if pre-requisite is ready to advance', async () => {
    // Setup What stage as ready_to_advance
    const ir = useWorkspaceStore.getState().ir;
    ir!.features = [
      { featureId: 10, featureName: 'Parent', parentId: null },
      { 
        featureId: 11, 
        featureName: 'Leaf', 
        parentId: 10, 
        actorIds: [1],
        scenarios: [
          { 
            scenarioId: 1, 
            title: 'Scenario', 
            acceptanceCriteria: [{ id: 1, title: 'AC' }] 
          }
        ]
      } as any
    ];

    // Mock API
    vi.mocked(workspaceApi.stageTransition).mockResolvedValue({
      status: 'unlocked',
      unlocked_stage: 'what',
      unlocked_stages: ['what'],
      blocking_findings: []
    });
    const refreshSpy = vi.fn().mockResolvedValue(undefined);
    useWorkspaceStore.setState({ refreshWorkspace: refreshSpy });

    render(
      <MemoryRouter>
        <LeftNav />
      </MemoryRouter>
    );

    // Find and click the Flow page link ("怎么运作")
    const flowLink = screen.getByText('怎么运作');
    fireEvent.click(flowLink);

    // Verify it intercepts the click and executes requestStageTransition -> stageTransition
    await waitFor(() => {
      expect(workspaceApi.stageTransition).toHaveBeenCalledWith('project-123', { action: 'enter_how', force: false });
    });
  });

  it('should show error toast and prevent navigation when clicking locked Flow link in LeftNav if pre-requisite is NOT ready', async () => {
    // What stage is NOT ready (no scenarios or AC)
    // Mock API
    vi.mocked(workspaceApi.stageTransition).mockResolvedValue({
      status: 'unlocked',
      unlocked_stage: 'what',
      unlocked_stages: ['what'],
      blocking_findings: []
    });

    render(
      <MemoryRouter>
        <LeftNav />
      </MemoryRouter>
    );

    const flowLink = screen.getByText('怎么运作');
    fireEvent.click(flowLink);

    // Since it's not ready, it should not trigger stageTransition
    expect(workspaceApi.stageTransition).not.toHaveBeenCalled();

    // Verify error toast was set in the store
    expect(useWorkspaceStore.getState().error).toContain('需先补齐 What 阶段');
  });


  it('should keep Preview navigation available for shadow preview before Scope is unlocked', () => {
    useWorkspaceStore.setState({
      stageProgress: {
        stages: [
          { stage: 'what', unlocked: true, statusCode: 'ready', statusLabel: '已完成', blockingFindings: [] },
          { stage: 'how', unlocked: true, statusCode: 'ready', statusLabel: '已完成', blockingFindings: [] },
          { stage: 'scope', unlocked: false, statusCode: 'locked', statusLabel: '尚未解锁', blockingFindings: [] },
        ]
      }
    });

    render(
      <MemoryRouter>
        <LeftNav />
      </MemoryRouter>
    );

    const previewLink = screen.getByText('方案预览').closest('a');
    expect(previewLink?.getAttribute('href')).toBe('/projects/project-123/preview');
    expect(previewLink?.className).not.toContain('cursor-not-allowed');
  });
  it('should trigger requestStageTransition when clicking on next suggestion button in Overview', async () => {
    // Setup What stage as ready_to_advance
    const ir = useWorkspaceStore.getState().ir;
    ir!.features = [
      { featureId: 10, featureName: 'Parent', parentId: null },
      { 
        featureId: 11, 
        featureName: 'Leaf', 
        parentId: 10, 
        actorIds: [1],
        scenarios: [
          { 
            scenarioId: 1, 
            title: 'Scenario', 
            acceptanceCriteria: [{ id: 1, title: 'AC' }] 
          }
        ]
      } as any
    ];

    vi.mocked(workspaceApi.stageTransition).mockResolvedValue({
      status: 'unlocked',
      unlocked_stage: 'what',
      unlocked_stages: ['what'],
      blocking_findings: []
    });
    const refreshSpy = vi.fn().mockResolvedValue(undefined);
    useWorkspaceStore.setState({
      refreshWorkspace: refreshSpy,
      stageProgress: {
        stages: [
          {
            stage: 'what',
            statusCode: 'ready_to_advance',
            nextAction: { kind: 'stage_transition', label: '申请进入下一阶段', transitionAction: 'enter_how' },
            failedChecks: [],
            blockingFindings: []
          },
          { stage: 'how', statusCode: 'locked', nextAction: { kind: 'none', label: '' }, failedChecks: [], blockingFindings: [] },
          { stage: 'scope', statusCode: 'locked', nextAction: { kind: 'none', label: '' }, failedChecks: [], blockingFindings: [] }
        ]
      }
    });

    render(
      <MemoryRouter>
        <Overview />
      </MemoryRouter>
    );

    const suggestBtn = screen.getByText('申请进入下一阶段');
    fireEvent.click(suggestBtn);

    // Verify it triggers requestStageTransition
    await waitFor(() => {
      expect(workspaceApi.stageTransition).toHaveBeenCalledWith('project-123', { action: 'enter_how', force: false });
    });
  });
});
