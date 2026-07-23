import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { StageGuidanceBanner } from '../components/shared/StageGuidanceBanner';
import { Finding } from '../core/schema';
import { workspaceApi } from '../lib/api';

vi.mock('../lib/api', () => ({
  workspaceApi: {
    listFindings: vi.fn().mockResolvedValue({ findings: [] }),
    updateFindingStatus: vi.fn().mockResolvedValue({}),
    createGenerationChoiceGroup: vi.fn(),
  }
}));

describe('StageGuidanceBanner - 4-Tier UX Categorization Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useWorkspaceStore.setState({
      ir: { projectId: 'project-123', projectName: 'Test Project' } as any,
      findingsByView: {
        issues: [],
        next_action: [],
        gate: [],
        health: []
      },
      isLoading: false,
      isGenerating: false,
      isDiagnosing: false,
      stageProgress: null,
    });
  });

  it('should render the clean green banner when there are no findings', () => {
    render(<MemoryRouter><StageGuidanceBanner stage="what" /></MemoryRouter>);
    expect(screen.queryByRole('button')).not.toBeNull();
    expect(screen.queryByRole('button')).not.toBeNull();
  });

  it('should render Next Actions, Issues, and Health Hints in their respective tiers', () => {
    const nextActionFinding: Finding = {
      findingId: 'what:GENERATE_SCENARIOS:feature:1',
      type: 'next_suggestion',
      stage: 'what',
      code: 'GENERATE_SCENARIOS',
      severity: 'info',
      title: '建议补齐系统角色',
      description: 'Need at least one core role.',
      blockingScope: 'none',
      metadata: {}
    };

    const issueFinding: Finding = {
      findingId: 'what:LEAF_FEATURE_WITHOUT_ACTOR:feature:5',
      type: 'issue',
      stage: 'what',
      code: 'LEAF_FEATURE_WITHOUT_ACTOR',
      severity: 'blocking',
      title: 'Feature missing actor',
      description: 'Leaf feature has no actor.',
      blockingScope: 'stage_transition',
      metadata: {},
      capability: { kind: 'ai_repair', action_label: 'AI 修复', enabled: true },
    };

    const healthFinding: Finding = {
      findingId: 'what:HEALTH_TEST:feature:3',
      type: 'quality_hint',
      stage: 'what',
      code: 'HEALTH_TEST',
      severity: 'info',
      title: '冗余场景名称提示',
      description: 'Scenario name can be improved.',
      blockingScope: 'none',
      metadata: {},
      capability: null,
    };

    useWorkspaceStore.setState({
      findingsByView: {
        next_action: [nextActionFinding],
        issues: [issueFinding],
        gate: [],
        health: [healthFinding]
      }
    });

    render(<MemoryRouter><StageGuidanceBanner stage="what" /></MemoryRouter>);

    // 1. Next Actions section
    expect(screen.queryByText('下一步建议')).not.toBeNull();
    expect(screen.queryByText('生成场景')).not.toBeNull();
    expect(screen.queryByText('生成场景草稿')).not.toBeNull();
    expect(screen.queryByText('开始处理(AI)')).toBeNull();

    // 2. Issues count header
    expect(screen.queryByText('仍有 1 个待处理问题')).not.toBeNull();
    expect(screen.queryByText('叶子功能缺少参与者')).not.toBeNull();
    expect(screen.queryByText('Leaf feature has no actor.')).toBeNull(); // folded by default

    // Expand Issues
    fireEvent.click(screen.getByText('仍有 1 个待处理问题'));
    expect(screen.queryByText('叶子功能缺少参与者')).not.toBeNull();
    expect(screen.queryByText('该叶子功能尚未关联参与者。')).not.toBeNull();
    expect(screen.queryByText('定位')).not.toBeNull();
    expect(screen.getAllByRole('button').length).toBeGreaterThan(0);

    // 3. Health Hints count header
    expect(screen.queryByText(/空间健康/)).not.toBeNull();
    expect(screen.queryByText('Scenario name can be improved.')).toBeNull(); // folded by default

    // Expand Health Hints
    fireEvent.click(screen.getByText(/空间健康/));
    expect(screen.queryByText('冗余场景名称提示')).not.toBeNull();
    expect(screen.queryByText('Scenario name can be improved.')).not.toBeNull();
  });

  it('should call startFindingSuggestion when clicking Next Action button', async () => {
    const nextActionFinding: Finding = {
      findingId: 'what:ENTER_HOW:feature:1',
      type: 'next_suggestion',
      stage: 'what',
      code: 'ENTER_HOW',
      severity: 'info',
      title: '建议补齐系统角色',
      description: 'Need at least one core role.',
      blockingScope: 'none',
      metadata: {}
    };

    const spy = vi.spyOn(useWorkspaceStore.getState(), 'startFindingSuggestion');

    useWorkspaceStore.setState({
      findingsByView: {
        next_action: [nextActionFinding],
        issues: [],
        gate: [],
        health: []
      }
    });

    render(<MemoryRouter><StageGuidanceBanner stage="what" /></MemoryRouter>);

    const handleButton = screen.getByRole('button', { name: '进入 How 阶段' });
    expect(screen.queryByText('开始处理(AI)')).toBeNull();
    act(() => {
      fireEvent.click(handleButton);
    });

    await vi.waitFor(() => !useWorkspaceStore.getState().isLoading);

    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith(nextActionFinding, expect.objectContaining({ navigate: expect.any(Function) }));
  });

  it('should call updateIssueAttributes when ignoring a health hint', async () => {
    const healthFinding: Finding = {
      findingId: 'what:HEALTH_TEST:feature:3',
      type: 'quality_hint',
      stage: 'what',
      code: 'HEALTH_TEST',
      severity: 'info',
      title: '冗余场景名称提示',
      description: 'Scenario name can be improved.',
      blockingScope: 'none',
      metadata: {}
    };

    const spy = vi.spyOn(useWorkspaceStore.getState(), 'updateIssueAttributes');

    useWorkspaceStore.setState({
      findingsByView: {
        next_action: [],
        issues: [],
        gate: [],
        health: [healthFinding]
      }
    });

    render(<MemoryRouter><StageGuidanceBanner stage="what" /></MemoryRouter>);

    // Expand Health Hints
    fireEvent.click(screen.getByText(/空间健康/));
    
    // Find the ignore button (which is the button with title "蹇界暐")
    const ignoreButton = screen.getByTitle('忽略');
    act(() => {
      fireEvent.click(ignoreButton);
    });

    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith(healthFinding.findingId, { status: 'ignored' });
  });

  it('should trigger scenario generation flow and set store state when clicking GENERATE_SCENARIOS next action', async () => {
    const nextActionFinding: Finding = {
      findingId: 'what:GENERATE_SCENARIOS:feature:1',
      type: 'next_suggestion',
      stage: 'what',
      code: 'GENERATE_SCENARIOS',
      severity: 'info',
      title: '鐢熸垚鍦烘櫙',
      description: 'Generate scenarios for features and actors.',
      blockingScope: 'none',
      metadata: {
        action: {
          kind: 'create_draft',
          draft_type: 'scenario_generation',
          payload: { project_id: 'project-123' }
        }
      }
    };

    // Mock createGenerationChoiceGroup to return choice group mock
    vi.mocked(workspaceApi.createGenerationChoiceGroup).mockResolvedValueOnce({
      id: 999,
      status: 'open',
      generation_type: 'scenario',
      choices: []
    } as any);

    useWorkspaceStore.setState({
      findingsByView: {
        next_action: [nextActionFinding],
        issues: [],
        gate: [],
        health: []
      }
    });

    render(<MemoryRouter><StageGuidanceBanner stage="what" /></MemoryRouter>);

    const handleButton = screen.getByText('生成场景草稿');
    expect(screen.queryByText('开始处理(AI)')).toBeNull();
    await act(async () => {
      fireEvent.click(handleButton);
    });

    await vi.waitFor(() => !useWorkspaceStore.getState().isLoading);

    expect(workspaceApi.createGenerationChoiceGroup).toHaveBeenCalledWith(
      expect.objectContaining({
        project_id: 'project-123',
        generation_type: 'scenario'
      })
    );
  });

  it('should render "查看建议" for slot findings', () => {
    const slotFinding: Finding = {
      findingId: 'what:ACTOR_SLOT:feature:1',
      type: 'next_suggestion',
      stage: 'what',
      code: 'ACTOR_SLOT',
      severity: 'info',
      title: '缺少系统角色',
      description: 'Missing role suggestion.',
      blockingScope: 'none',
      metadata: {}
    };

    useWorkspaceStore.setState({
      findingsByView: {
        next_action: [slotFinding],
        issues: [],
        gate: [],
        health: []
      }
    });

    render(<MemoryRouter><StageGuidanceBanner stage="what" /></MemoryRouter>);
    expect(screen.queryByText('查看建议')).not.toBeNull();
  });

  it('should render "重新诊断" for failed perception findings', () => {
    const failedFinding: Finding = {
      findingId: 'what:ACTOR_PERCEPTION_FAILED:feature:1',
      type: 'next_suggestion',
      stage: 'what',
      code: 'ACTOR_PERCEPTION_FAILED',
      severity: 'info',
      title: '角色感知失败',
      description: 'Actor perception failed.',
      blockingScope: 'none',
      metadata: {}
    };

    useWorkspaceStore.setState({
      findingsByView: {
        next_action: [failedFinding],
        issues: [],
        gate: [],
        health: []
      }
    });

    render(<MemoryRouter><StageGuidanceBanner stage="what" /></MemoryRouter>);
    expect(screen.queryByText('重新诊断')).not.toBeNull();
  });

  it('should render the localized COMPLETE_FLOW_STEPS title with open_panel/flow_editor action', () => {
    const completeFlowFinding: Finding = {
      findingId: 'how:COMPLETE_FLOW_STEPS:flow:1',
      type: 'next_suggestion',
      stage: 'how',
      code: 'COMPLETE_FLOW_STEPS',
      severity: 'info',
      title: '完善流程步骤',
      description: 'Complete flow steps before entering Scope.',
      blockingScope: 'none',
      metadata: {
        action: {
          kind: 'open_panel',
          panel: 'flow_editor',
          route: '/projects/test/how',
          payload: { flow_id: 1 },
        },
      },
    };

    useWorkspaceStore.setState({
      findingsByView: {
        next_action: [completeFlowFinding],
        issues: [],
        gate: [],
        health: [],
      },
    });

    render(<MemoryRouter><StageGuidanceBanner stage="how" /></MemoryRouter>);
    // Verify presentation shows correct label despite action.kind=open_panel
    expect(screen.queryByText('补全流程步骤')).not.toBeNull();
  });

  it('should render "执行建议" for unknown code fallback', () => {
    const unknownFinding: Finding = {
      findingId: 'what:SOME_UNKNOWN_CODE:feature:1',
      type: 'next_suggestion',
      stage: 'what',
      code: 'SOME_UNKNOWN_CODE',
      severity: 'info',
      title: '未知建议',
      description: 'Unknown suggestion.',
      blockingScope: 'none',
      metadata: {}
    };

    useWorkspaceStore.setState({
      findingsByView: {
        next_action: [unknownFinding],
        issues: [],
        gate: [],
        health: []
      }
    });

    render(<MemoryRouter><StageGuidanceBanner stage="what" /></MemoryRouter>);
    expect(screen.queryByText('执行建议')).not.toBeNull();
  });

  it('should hide stale next action after the stage has already advanced', () => {
    const nextActionFinding: Finding = {
      findingId: 'what:ENTER_HOW:project:1',
      type: 'next_suggestion',
      stage: 'what',
      code: 'ENTER_HOW',
      severity: 'info',
      title: '进入 How 阶段',
      description: 'What 已完成',
      blockingScope: 'none',
      metadata: {}
    };

    useWorkspaceStore.setState({
      findingsByView: {
        next_action: [nextActionFinding],
        issues: [],
        gate: [],
        health: []
      },
      stageProgress: {
        stages: [
          { stage: 'what', statusCode: 'ready' },
          { stage: 'how', statusCode: 'unlocked_not_started' },
          { stage: 'scope', statusCode: 'locked' }
        ]
      }
    });

    render(<MemoryRouter><StageGuidanceBanner stage="what" /></MemoryRouter>);
    expect(screen.queryByText('进入 How 阶段')).toBeNull();
  });

  it('should keep an active perception slot visible after the stage has advanced', () => {
    const slotFinding: Finding = {
      findingId: 'what:FEATURE_SLOT:project:1',
      type: 'next_suggestion',
      stage: 'what',
      code: 'FEATURE_SLOT',
      severity: 'info',
      title: '补充建议',
      description: '发现一个需要补充的功能模块。',
      blockingScope: 'none',
      metadata: {
        source_type: 'perception_slot',
        action: { kind: 'open_panel', panel: 'perception_slot' },
      },
    };

    useWorkspaceStore.setState({
      findingsByView: {
        next_action: [slotFinding],
        issues: [],
        gate: [],
        health: [],
      },
      stageProgress: {
        stages: [{ stage: 'what', statusCode: 'ready' }],
      },
    });

    render(<MemoryRouter><StageGuidanceBanner stage="what" /></MemoryRouter>);
    expect(screen.queryByText('发现一个需要补充的功能模块。')).not.toBeNull();
  });
});
