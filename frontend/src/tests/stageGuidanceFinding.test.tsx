import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act, within } from '@testing-library/react';
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
      backendFindingsLoaded: true,
      stageProgress: null,
    });
  });

  it('should render the clean green banner when there are no findings', () => {
    useWorkspaceStore.setState({
      ir: {
        ...useWorkspaceStore.getState().ir,
        actors: [{ actorId: 1 }],
        features: [{ featureId: 1, scenarios: [{ scenarioId: 1, acceptanceCriteria: [{ criterionId: 1 }] }] }],
      } as any,
      stageProgress: {
        stages: [{ stage: 'what', statusCode: 'ready', failedChecks: [], blockingFindings: [] }],
      },
    });
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
      title: '生成场景',
      description: '请为项目功能和参与者生成场景。',
      blockingScope: 'none',
      metadata: {}
    };

    const issueFinding: Finding = {
      findingId: 'what:LEAF_FEATURE_WITHOUT_ACTOR:feature:5',
      type: 'issue',
      stage: 'what',
      code: 'LEAF_FEATURE_WITHOUT_ACTOR',
      severity: 'blocking',
      title: '叶子功能缺少参与者',
      description: '该叶子功能尚未关联参与者。',
      blockingScope: 'stage_transition',
      metadata: {},
      capability: { kind: 'manual_action', action_label: '生成处理建议', enabled: true },
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
    expect(screen.getByRole('heading', { name: '生成场景' })).not.toBeNull();
    expect(screen.getByRole('button', { name: '生成场景草稿' })).not.toBeNull();
    expect(screen.queryByText('开始处理(AI)')).toBeNull();

    // 2. Issues count header
    const issuesHeader = screen.getByRole('button', { name: /待处理问题 1/ });
    expect(within(issuesHeader).getByText('1')).not.toBeNull();
    expect(screen.queryByText('叶子功能缺少参与者')).toBeNull();
    expect(within(issuesHeader).getByText('该叶子功能尚未关联参与者。')).not.toBeNull();

    // Expand Issues
    fireEvent.click(issuesHeader);
    expect(screen.queryByText('叶子功能缺少参与者')).not.toBeNull();
    expect(screen.queryByText('该叶子功能尚未关联参与者。')).not.toBeNull();
    expect(screen.getByRole('button', { name: '生成处理建议' })).not.toBeNull();

    // 3. Health Hints count header
    const healthHeader = screen.getByRole('button', { name: /空间健康 1/ });
    expect(within(healthHeader).getByText('1')).not.toBeNull();
    expect(screen.queryByText('冗余场景名称提示')).toBeNull();
    expect(within(healthHeader).getByText('Scenario name can be improved.')).not.toBeNull();

    // Expand Health Hints
    fireEvent.click(healthHeader);
    expect(screen.queryByText('冗余场景名称提示')).not.toBeNull();
    expect(screen.queryByText('Scenario name can be improved.')).not.toBeNull();
  });

  it('should use stage progress for the stage transition action', async () => {
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

    const transitionSpy = vi.spyOn(useWorkspaceStore.getState(), 'requestStageTransition').mockResolvedValue(undefined);

    useWorkspaceStore.setState({
      findingsByView: {
        next_action: [nextActionFinding],
        issues: [],
        gate: [],
        health: []
      },
      stageProgress: {
        stages: [{
          stage: 'what',
          statusCode: 'ready_to_advance',
          failedChecks: [],
          blockingFindings: [],
          nextAction: { kind: 'stage_transition', transitionAction: 'enter_how' },
        }],
      },
    });

    render(<MemoryRouter><StageGuidanceBanner stage="what" /></MemoryRouter>);

    const handleButton = screen.getByRole('button', { name: '进入 How 阶段' });
    expect(screen.queryByText('开始处理(AI)')).toBeNull();
    act(() => {
      fireEvent.click(handleButton);
    });

    await vi.waitFor(() => !useWorkspaceStore.getState().isLoading);

    expect(transitionSpy).toHaveBeenCalledTimes(1);
    expect(transitionSpy).toHaveBeenCalledWith('enter_how', expect.objectContaining({ navigate: expect.any(Function) }));
    transitionSpy.mockRestore();
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
      },
      branchLoading: false,
      currentBranch: { name: 'feature/test', is_protected: false, is_default: false, permissions: { can_write: true } } as any,
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
      }),
      'main',
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

  it('hides diagnosis for failed perception when stage content is empty', () => {
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
    expect(screen.queryByRole('button', { name: /诊断/ })).toBeNull();
  });

  it.each(['完善流程步骤', 'Complete Flow Steps'])(
    'preserves the backend COMPLETE_FLOW_STEPS title %s with an open_panel action', (title) => {
    const completeFlowFinding: Finding = {
      findingId: 'how:COMPLETE_FLOW_STEPS:flow:1',
      type: 'next_suggestion',
      stage: 'how',
      code: 'COMPLETE_FLOW_STEPS',
      severity: 'info',
      title,
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
    expect(screen.getByRole('heading', { name: title })).not.toBeNull();
    expect(screen.getByRole('button', { name: '完善流程步骤' })).not.toBeNull();
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

  it('shows stage transition and a non-blocking perception suggestion together', () => {
    const slotFinding: Finding = {
      findingId: 'what:FEATURE_SLOT:project:1',
      type: 'next_suggestion',
      stage: 'what',
      code: 'FEATURE_SLOT',
      severity: 'info',
      title: '补充建议',
      description: '补充一个可选功能模块。',
      blockingScope: 'none',
      metadata: {
        source_type: 'perception_slot',
        action: { kind: 'open_panel', panel: 'perception_slot' },
      },
    };
    useWorkspaceStore.setState({
      findingsByView: { issues: [], next_action: [slotFinding], gate: [], health: [] },
      stageProgress: {
        stages: [{
          stage: 'what',
          statusCode: 'ready_to_advance',
          failedChecks: [],
          blockingFindings: [],
          nextAction: { kind: 'stage_transition', transitionAction: 'enter_how' },
        }],
      },
    });

    render(<MemoryRouter><StageGuidanceBanner stage="what" /></MemoryRouter>);

    expect(screen.queryByRole('button', { name: '进入 How 阶段' })).not.toBeNull();
    expect(screen.queryByText('补充一个可选功能模块。')).not.toBeNull();
  });

  it.each([
    ['how', 'enter_scope', '进入 Scope 阶段'],
    ['scope', 'enter_preview', '进入预览阶段'],
  ] as const)('uses the same ready-to-advance rule for the %s stage', (stage, transitionAction, buttonLabel) => {
    useWorkspaceStore.setState({
      stageProgress: {
        stages: [{
          stage,
          statusCode: 'ready_to_advance',
          failedChecks: [],
          blockingFindings: [],
          nextAction: { kind: 'stage_transition', transitionAction },
        }],
      },
    });

    render(<MemoryRouter><StageGuidanceBanner stage={stage} /></MemoryRouter>);

    expect(screen.queryByRole('button', { name: buttonLabel })).not.toBeNull();
  });

  it('does not show a stage transition when the current stage is blocked', () => {
    const issue: Finding = {
      findingId: 'what:LEAF_FEATURE_WITHOUT_SCENARIO:feature:1',
      type: 'issue',
      stage: 'what',
      code: 'LEAF_FEATURE_WITHOUT_SCENARIO',
      severity: 'blocking',
      title: '叶子功能缺少场景',
      description: '该叶子功能没有对应场景。',
      blockingScope: 'stage_transition',
      metadata: {},
    };
    useWorkspaceStore.setState({
      findingsByView: { issues: [issue], next_action: [], gate: [], health: [] },
      stageProgress: {
        stages: [{
          stage: 'what',
          statusCode: 'blocked',
          failedChecks: [{ code: 'leaf_feature_without_scenario' }],
          blockingFindings: [issue],
          nextAction: { kind: 'stage_transition', transitionAction: 'enter_how' },
        }],
      },
    });

    render(<MemoryRouter><StageGuidanceBanner stage="what" /></MemoryRouter>);

    expect(screen.queryByRole('button', { name: '进入 How 阶段' })).toBeNull();
    expect(screen.queryByText('当前阶段尚未完成')).not.toBeNull();
  });

  it('does not report a healthy stage when stage progress still has failed checks', () => {
    useWorkspaceStore.setState({
      stageProgress: {
        stages: [{
          stage: 'how',
          statusCode: 'unlocked_not_started',
          failedChecks: [{ code: 'missing_flows' }],
          blockingFindings: [],
          nextAction: { kind: 'navigate' },
        }],
      },
    });

    render(<MemoryRouter><StageGuidanceBanner stage="how" /></MemoryRouter>);

    expect(screen.queryByText('当前阶段尚未完成')).not.toBeNull();
    expect(screen.queryByText(/模型结构健康/)).toBeNull();
  });

  it('executes rule generation from the How next suggestion', async () => {
    vi.mocked(workspaceApi.createGenerationChoiceGroup).mockResolvedValueOnce({
      id: 1001,
      status: 'open',
      generation_type: 'rule',
      choices: [],
    } as any);
    useWorkspaceStore.setState({
      findingsByView: {
        issues: [],
        gate: [],
        health: [],
        next_action: [{
          findingId: 'how:GENERATE_RULES:suggest',
          type: 'next_suggestion',
          stage: 'how',
          code: 'GENERATE_RULES',
          severity: 'info',
          title: '生成领域规则',
          description: '先生成规则。',
          blockingScope: 'none',
          metadata: { action: { kind: 'create_draft', draft_type: 'rule_generation' } },
        } as Finding],
      },
      stageProgress: {
        stages: [{ stage: 'how', statusCode: 'unlocked_not_started', failedChecks: [{ code: 'missing_flows' }] }],
      },
      branchLoading: false,
      currentBranch: { name: 'feature/test', is_protected: false, is_default: false, permissions: { can_write: true } } as any,
    });

    render(<MemoryRouter><StageGuidanceBanner stage="how" /></MemoryRouter>);
    await act(async () => fireEvent.click(screen.getByRole('button', { name: '生成领域规则草稿' })));

    expect(workspaceApi.createGenerationChoiceGroup).toHaveBeenCalledWith(
      expect.objectContaining({ generation_type: 'rule' }),
      'main',
    );
  });
});
