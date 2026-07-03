import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { LeftNav } from '../components/layout/LeftNav';
import { Overview } from '../pages/Overview';

// Mock sub-components of Overview to avoid rendering issues
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
    getStageProgress: vi.fn(),
    listFindings: vi.fn(),
    stageTransition: vi.fn(),
  }
}));

import { workspaceApi } from '../lib/api';

describe('Phase 3 StageProgress Unified State Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useWorkspaceStore.setState({
      ir: {
        projectId: 'project-123',
        projectName: 'Test Project',
        unlockedStages: '',
        actors: [],
        features: [],
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
      stageProgress: null,
      sessionVersion: 1,
      isLoading: false,
      error: null,
    });
  });

  it('should successfully loadStageProgress and store it in state', async () => {
    const mockProgress = {
      projectId: 'project-123',
      stages: [
        {
          stage: 'what',
          statusCode: 'in_progress',
          statusLabel: '进行中',
          unlocked: true,
          failedChecks: [{ code: 'missing_actors', message: '缺少参与者', targets: [] }],
          nextAction: { kind: 'navigate', label: '定义参与者', route: '/what' }
        },
        {
          stage: 'how',
          statusCode: 'locked',
          statusLabel: '未解锁',
          unlocked: false,
          failedChecks: [],
          nextAction: { kind: 'none', label: '' }
        },
        {
          stage: 'scope',
          statusCode: 'locked',
          statusLabel: '未解锁',
          unlocked: false,
          failedChecks: [],
          nextAction: { kind: 'none', label: '' }
        }
      ]
    };

    vi.mocked(workspaceApi.getStageProgress).mockResolvedValue(mockProgress);

    await useWorkspaceStore.getState().loadStageProgress();

    expect(workspaceApi.getStageProgress).toHaveBeenCalledWith('project-123');
    expect(useWorkspaceStore.getState().stageProgress).toEqual(mockProgress);
  });

  it('should prevent navigation and show error toast when clicking locked stage in LeftNav using stageProgress failed checks', async () => {
    const mockProgress = {
      projectId: 'project-123',
      stages: [
        {
          stage: 'what',
          statusCode: 'in_progress',
          statusLabel: '进行中',
          unlocked: true,
          failedChecks: [{ code: 'missing_actors', message: '缺少参与者', targets: [] }],
          nextAction: { kind: 'navigate', label: '定义参与者', route: '/what' }
        },
        {
          stage: 'how',
          statusCode: 'locked',
          statusLabel: '未解锁',
          unlocked: false,
          failedChecks: [],
          nextAction: { kind: 'none', label: '' }
        },
        {
          stage: 'scope',
          statusCode: 'locked',
          statusLabel: '未解锁',
          unlocked: false,
          failedChecks: [],
          nextAction: { kind: 'none', label: '' }
        }
      ]
    };

    useWorkspaceStore.setState({ stageProgress: mockProgress as any });

    render(
      <MemoryRouter>
        <LeftNav />
      </MemoryRouter>
    );

    // Find and click the Flow page link ("怎么运作")
    const flowLink = screen.getByText('怎么运作');
    fireEvent.click(flowLink);

    // LeftNav onClick reads stageProgress, detects that 'how' is locked, and reads What stage failedChecks.
    expect(useWorkspaceStore.getState().error).toBe('缺少参与者');
  });

  it('should render nextAction from active stage in Overview and trigger startFindingSuggestion when clicked', async () => {
    const mockProgress = {
      projectId: 'project-123',
      stages: [
        {
          stage: 'what',
          statusCode: 'ready_to_advance',
          statusLabel: '可进入下一阶段',
          unlocked: true,
          failedChecks: [],
          nextAction: { kind: 'stage_transition', label: '申请进入下一阶段', transitionAction: 'enter_how' }
        },
        {
          stage: 'how',
          statusCode: 'locked',
          statusLabel: '未解锁',
          unlocked: false,
          failedChecks: [],
          nextAction: { kind: 'none', label: '' }
        },
        {
          stage: 'scope',
          statusCode: 'locked',
          statusLabel: '未解锁',
          unlocked: false,
          failedChecks: [],
          nextAction: { kind: 'none', label: '' }
        }
      ]
    };

    useWorkspaceStore.setState({ stageProgress: mockProgress as any });
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
        <Overview />
      </MemoryRouter>
    );

    // Verify it renders progress suggestion action button in Overview
    const suggestBtn = screen.getByText('申请进入下一阶段');
    expect(suggestBtn).toBeDefined();

    fireEvent.click(suggestBtn);

    await waitFor(() => {
      expect(workspaceApi.stageTransition).toHaveBeenCalledWith('project-123', { action: 'enter_how', force: false });
    });
  });
});
