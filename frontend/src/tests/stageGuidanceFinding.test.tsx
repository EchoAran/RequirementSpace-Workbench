import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
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
    });
  });

  it('should render the clean green banner when there are no findings', () => {
    render(<StageGuidanceBanner stage="what" />);
    expect(screen.queryByText('当前阶段暂未发现待处理问题，模型结构健康。', { exact: false })).not.toBeNull();
    expect(screen.queryByText('重新诊断')).not.toBeNull();
  });

  it('should render Next Actions, Issues, and Health Hints in their respective tiers', () => {
    const nextActionFinding: Finding = {
      findingId: 'what:GENERATE_SCENARIOS:feature:1',
      type: 'next_suggestion',
      stage: 'what',
      code: 'GENERATE_SCENARIOS',
      severity: 'info',
      title: '建议补齐系统角色',
      description: '建模需要至少一个核心角色。',
      blockingScope: 'none',
      metadata: {}
    };

    const issueFinding: Finding = {
      findingId: 'what:LEAF_FEATURE_WITHOUT_ACTOR:feature:5',
      type: 'issue',
      stage: 'what',
      code: 'LEAF_FEATURE_WITHOUT_ACTOR',
      severity: 'blocking',
      title: '功能未关联角色',
      description: '叶子功能缺少关联的执行主体。',
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
      description: '部分典型场景名称存在冗余词汇。',
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

    render(<StageGuidanceBanner stage="what" />);

    // 1. Next Actions section
    expect(screen.queryByText('下一步建议')).not.toBeNull();
    expect(screen.queryByText('建议补齐系统角色')).not.toBeNull();
    expect(screen.queryByText('生成场景草稿')).not.toBeNull();
    expect(screen.queryByText('开始处理 (AI)')).toBeNull();

    // 2. Issues count header
    expect(screen.queryByText('仍有 1 个待处理问题')).not.toBeNull();
    expect(screen.queryByText('叶子功能缺少关联的执行主体。')).toBeNull(); // folded by default

    // Expand Issues
    fireEvent.click(screen.getByText('仍有 1 个待处理问题'));
    expect(screen.queryByText('功能未关联角色')).not.toBeNull();
    expect(screen.queryByText('叶子功能缺少关联的执行主体。')).not.toBeNull();
    expect(screen.queryByText('AI 修复')).not.toBeNull();
    expect(screen.queryByText('定位')).not.toBeNull();

    // 3. Health Hints count header
    expect(screen.queryByText('空间健康：1 条可优化建议')).not.toBeNull();
    expect(screen.queryByText('部分典型场景名称存在冗余词汇。')).toBeNull(); // folded by default

    // Expand Health Hints
    fireEvent.click(screen.getByText('空间健康：1 条可优化建议'));
    expect(screen.queryByText('冗余场景名称提示')).not.toBeNull();
    expect(screen.queryByText('部分典型场景名称存在冗余词汇。')).not.toBeNull();
  });

  it('should call startFindingSuggestion when clicking Next Action button', async () => {
    const nextActionFinding: Finding = {
      findingId: 'what:ENTER_HOW:feature:1',
      type: 'next_suggestion',
      stage: 'what',
      code: 'ENTER_HOW',
      severity: 'info',
      title: '建议补齐系统角色',
      description: '建模需要至少一个核心角色。',
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

    render(<StageGuidanceBanner stage="what" />);

    const handleButton = screen.getByText('进入 How 阶段');
    expect(screen.queryByText('开始处理 (AI)')).toBeNull();
    act(() => {
      fireEvent.click(handleButton);
    });

    await vi.waitFor(() => !useWorkspaceStore.getState().isLoading);

    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith(nextActionFinding);
  });

  it('should call updateIssueAttributes when ignoring a health hint', async () => {
    const healthFinding: Finding = {
      findingId: 'what:HEALTH_TEST:feature:3',
      type: 'quality_hint',
      stage: 'what',
      code: 'HEALTH_TEST',
      severity: 'info',
      title: '冗余场景名称提示',
      description: '部分典型场景名称存在冗余词汇。',
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

    render(<StageGuidanceBanner stage="what" />);

    // Expand Health Hints
    fireEvent.click(screen.getByText('空间健康：1 条可优化建议'));
    
    // Find the ignore button (which is the button with title "忽略")
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
      title: '生成场景',
      description: '当前项目还没有场景，建议为功能与参与者生成场景。',
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

    render(<StageGuidanceBanner stage="what" />);

    const handleButton = screen.getByText('生成场景草稿');
    expect(screen.queryByText('开始处理 (AI)')).toBeNull();
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
      description: '缺少系统角色建议。',
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

    render(<StageGuidanceBanner stage="what" />);
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
      description: '角色感知诊断失败。',
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

    render(<StageGuidanceBanner stage="what" />);
    expect(screen.queryByText('重新诊断')).not.toBeNull();
  });

  it('should render "完善流程步骤" for COMPLETE_FLOW_STEPS with open_panel/flow_editor action', () => {
    const completeFlowFinding: Finding = {
      findingId: 'how:COMPLETE_FLOW_STEPS:flow:1',
      type: 'next_suggestion',
      stage: 'how',
      code: 'COMPLETE_FLOW_STEPS',
      severity: 'info',
      title: '完善流程步骤',
      description: '当前流程尚未包含可执行步骤，建议先补充流程步骤。',
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

    render(<StageGuidanceBanner stage="how" />);
    // Verify presentation shows correct label despite action.kind=open_panel
    const buttons = screen.queryAllByText('完善流程步骤');
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });

  it('should render "执行建议" for unknown code fallback', () => {
    const unknownFinding: Finding = {
      findingId: 'what:SOME_UNKNOWN_CODE:feature:1',
      type: 'next_suggestion',
      stage: 'what',
      code: 'SOME_UNKNOWN_CODE',
      severity: 'info',
      title: '未知建议',
      description: '未知的系统建议。',
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

    render(<StageGuidanceBanner stage="what" />);
    expect(screen.queryByText('执行建议')).not.toBeNull();
  });
});
