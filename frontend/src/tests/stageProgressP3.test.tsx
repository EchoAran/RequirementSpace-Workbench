import { renderWithEffects as render } from './renderWithEffects';
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, screen, fireEvent, waitFor } from '@testing-library/react';
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
    getProjectConfiguration: vi.fn().mockResolvedValue(null),
    getLatestPrototypePreview: vi.fn().mockResolvedValue(null),
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
      branchLoading: false,
      currentBranch: { name: 'feature/test', is_protected: false, is_default: false, permissions: { can_write: true } } as any,
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

    await render(
      <MemoryRouter>
        <LeftNav />
      </MemoryRouter>
    );

    // Find and click the Flow page link ("怎么运作")
    const flowLink = screen.getByText('怎么运作');
    await act(async () => fireEvent.click(flowLink));

    // LeftNav onClick reads stageProgress, detects that 'how' is locked, and reads What stage failedChecks.
    expect(useWorkspaceStore.getState().error).toBe('项目尚未有参与者。');
  });

  it('should render the backend next_action finding in Overview and trigger it when clicked', async () => {
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

    useWorkspaceStore.setState({
      stageProgress: mockProgress as any,
      backendFindingsLoaded: true,
      findingsByView: {
        issues: [],
        gate: [],
        health: [],
        next_action: [{
          findingId: 'what:ENTER_HOW:suggest',
          type: 'next_suggestion',
          stage: 'what',
          code: 'ENTER_HOW',
          severity: 'info',
          title: '进入 How 阶段',
          description: '推进到 How 阶段',
          blockingScope: 'none',
          metadata: { action: { kind: 'stage_transition', transition_action: 'enter_how' } },
        } as any]
      }
    });
    vi.mocked(workspaceApi.stageTransition).mockResolvedValue({
      status: 'unlocked',
      unlocked_stage: 'what',
      unlocked_stages: ['what'],
      blocking_findings: []
    });

    const refreshSpy = vi.fn().mockResolvedValue(undefined);
    useWorkspaceStore.setState({ refreshWorkspace: refreshSpy });

    await render(
      <MemoryRouter>
        <Overview />
      </MemoryRouter>
    );

    // Verify it renders the canonical finding returned by the backend.
    const suggestBtn = screen.getByText('进入 How 阶段');
    expect(suggestBtn).toBeDefined();

    await act(async () => fireEvent.click(suggestBtn));

    await waitFor(() => {
      expect(workspaceApi.stageTransition).toHaveBeenCalledWith('project-123', { action: 'enter_how', force: false });
    });
  });

  it('keeps the next suggestion area empty when the backend returns no next_action', async () => {
    useWorkspaceStore.setState({
      backendFindingsLoaded: true,
      findingsByView: { issues: [], next_action: [], gate: [], health: [] },
    });

    await render(
      <MemoryRouter>
        <Overview />
      </MemoryRouter>
    );

    expect(screen.queryByText(/stageGuidanceSlots\./)).toBeNull();
    expect(screen.queryByText(/^(暂无建议|No suggestions)$/)).toBeNull();
  });

  it('shows a stage transition and keeps perception guidance inside the existing pending issues section', async () => {
    const slotFinding = {
      findingId: 'what:FEATURE_SLOT:suggest',
      type: 'next_suggestion',
      stage: 'what',
      code: 'FEATURE_SLOT',
      severity: 'info',
      title: '补充功能建议',
      description: '可以补充一个非阻塞功能。',
      blockingScope: 'none',
      metadata: {
        source_type: 'perception_slot',
        action: { kind: 'open_panel', panel: 'perception_slot' },
      },
    };
    useWorkspaceStore.setState({
      ir: {
        ...useWorkspaceStore.getState().ir,
        statusCode: 'needs_attention',
        issueCount: 0,
        perceptionSlot: {
          id: '17',
          stage: 'what',
          perceptionKind: '功能模块结点',
          perceptionDescription: '可以补充一个非阻塞功能。',
        },
      } as any,
      backendFindingsLoaded: true,
      findingsByView: { issues: [], next_action: [slotFinding as any], gate: [], health: [] },
      stageProgress: {
        stages: [{
          stage: 'what',
          statusCode: 'ready_to_advance',
          blockingFindings: [],
          nextAction: { kind: 'stage_transition', transitionAction: 'enter_how' },
        }],
      },
    });

    await render(<MemoryRouter><Overview /></MemoryRouter>);

    await waitFor(() => expect(screen.queryByText('进入 How 阶段')).not.toBeNull());
    const issuesTitle = screen.getAllByText('待处理问题').find((element) => element.tagName === 'H3');
    const issuesSection = issuesTitle?.closest('section');
    expect(issuesSection?.textContent).toContain('待完善建议');
    expect(issuesSection?.textContent).toContain('补充功能建议');
  });
});
