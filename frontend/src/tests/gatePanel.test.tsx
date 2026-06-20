import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import GateCheckModal from '../components/shared/GateCheckModal';
import { Finding } from '../core/schema';

vi.mock('../lib/api', () => ({
  workspaceApi: {
    listFindings: vi.fn().mockResolvedValue({ findings: [] }),
    updateFindingStatus: vi.fn().mockResolvedValue({}),
  }
}));

describe('GateCheckModal - UI and Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useWorkspaceStore.setState({
      activeGateCheck: null,
      snoozedGateFindingIds: {},
      ir: { projectId: 'project-123', projectName: 'Test Project' } as any,
    });
  });

  const mockFindings: Finding[] = [
    {
      findingId: 'what:FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO:aggregate',
      type: 'gate_condition',
      stage: 'what',
      code: 'FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO',
      severity: 'blocking',
      title: '缺少典型场景',
      description: '角色和功能未关联典型场景',
      blockingScope: 'stage_transition',
      metadata: {
        missing_pairs: [{ feature_id: 1, actor_id: 2 }]
      },
      capability: { kind: 'ai_repair', action_label: 'AI 修复', enabled: true },
    },
    {
      findingId: 'how:LEAF_FEATURE_WITHOUT_FLOW:feature:2',
      type: 'gate_condition',
      stage: 'how',
      code: 'LEAF_FEATURE_WITHOUT_FLOW',
      severity: 'blocking',
      title: '未关联业务流程',
      description: '叶子功能缺少对应的流程或步骤描述',
      blockingScope: 'stage_transition',
      metadata: {},
      capability: { kind: 'ai_repair', action_label: 'AI 修复', enabled: true },
    }
  ];

  it('should render nothing when activeGateCheck is null', () => {
    render(<GateCheckModal />);
    expect(screen.queryByText('模型就绪度检查未通过')).toBeNull();
  });

  it('should render findings, titles, descriptions, and AI action buttons when activeGateCheck is populated', () => {
    const onPass = vi.fn();
    const onCancel = vi.fn();

    useWorkspaceStore.setState({
      activeGateCheck: {
        action: 'enter_how',
        findings: mockFindings,
        onPass,
        onCancel,
      }
    });

    render(<GateCheckModal />);

    expect(screen.queryByText('模型就绪度检查未通过')).not.toBeNull();
    expect(screen.queryByText('缺少典型场景')).not.toBeNull();
    expect(screen.queryByText('角色和功能未关联典型场景')).not.toBeNull();
    expect(screen.queryAllByText('AI 修复').length).toBe(2);
  });

  it('should trigger onCancel when clicking Cancel button', () => {
    const onPass = vi.fn();
    const onCancel = vi.fn();

    useWorkspaceStore.setState({
      activeGateCheck: {
        action: 'enter_how',
        findings: mockFindings,
        onPass,
        onCancel,
      }
    });

    render(<GateCheckModal />);

    const cancelButton = screen.getByText('暂不处理 (Cancel)');
    fireEvent.click(cancelButton);

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onPass).not.toHaveBeenCalled();
  });

  it('should snooze all findings and call onPass when clicking Continue anyway', () => {
    const onPass = vi.fn();
    const onCancel = vi.fn();

    const snoozeSpy = vi.spyOn(useWorkspaceStore.getState(), 'snoozeGateFinding');

    useWorkspaceStore.setState({
      activeGateCheck: {
        action: 'enter_how',
        findings: mockFindings,
        onPass,
        onCancel,
      }
    });

    render(<GateCheckModal />);

    const continueButton = screen.getByText('继续进入 (Continue anyway)');
    fireEvent.click(continueButton);

    // Assert snoozeGateFinding was called for both findings
    expect(snoozeSpy).toHaveBeenCalledTimes(2);
    expect(snoozeSpy).toHaveBeenNthCalledWith(1, 'enter_how', mockFindings[0]);
    expect(snoozeSpy).toHaveBeenNthCalledWith(2, 'enter_how', mockFindings[1]);

    expect(onPass).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();
  });

  it('should call executeGateFindingAction when clicking AI action button', async () => {
    const onPass = vi.fn();
    const onCancel = vi.fn();

    const executeGateFindingActionSpy = vi.spyOn(useWorkspaceStore.getState(), 'executeGateFindingAction').mockResolvedValue(undefined);

    useWorkspaceStore.setState({
      activeGateCheck: {
        action: 'enter_how',
        findings: [mockFindings[0]],
        onPass,
        onCancel,
      }
    });

    render(<GateCheckModal />);

    const aiButton = screen.getByText('AI 修复');
    fireEvent.click(aiButton);

    expect(executeGateFindingActionSpy).toHaveBeenCalledTimes(1);
    expect(executeGateFindingActionSpy).toHaveBeenCalledWith(mockFindings[0]);
  });

  it('should display capability-specific error message when AI action fails', async () => {
    const onPass = vi.fn();
    const onCancel = vi.fn();

    vi.spyOn(useWorkspaceStore.getState(), 'executeGateFindingAction').mockRejectedValue(new Error('AI generation timed out'));

    useWorkspaceStore.setState({
      activeGateCheck: {
        action: 'enter_how',
        findings: [mockFindings[0]],
        onPass,
        onCancel,
      }
    });

    render(<GateCheckModal />);

    const aiButton = screen.getByText('AI 修复');
    await act(async () => {
      fireEvent.click(aiButton);
    });

    // capability kind = ai_repair → 显示区分化产品文案
    expect(screen.queryByText('AI 修复失败，请稍后重试或手动处理。')).not.toBeNull();
    expect(onCancel).not.toHaveBeenCalled();
  });

  it('should render "查看处理建议" for manual_action capability', () => {
    const manualFinding: Finding = {
      findingId: 'what:SCOPE_WITHOUT_REASON:scope:5',
      type: 'gate_condition',
      stage: 'what',
      code: 'SCOPE_WITHOUT_REASON',
      severity: 'blocking',
      title: '范围缺少理由',
      description: '范围结论缺少说明理由',
      blockingScope: 'stage_transition',
      metadata: {},
      capability: { kind: 'manual_action', action_label: '查看处理建议', enabled: true },
    };

    const onPass = vi.fn();
    const onCancel = vi.fn();

    useWorkspaceStore.setState({
      activeGateCheck: {
        action: 'enter_scope',
        findings: [manualFinding],
        onPass,
        onCancel,
      },
    });

    render(<GateCheckModal />);
    expect(screen.queryByText('查看处理建议')).not.toBeNull();
  });

  it('should show manual action text when capability is unsupported', () => {
    const unsupportedFinding: Finding = {
      findingId: 'how:UNSUPPORTED_CODE:step:5',
      type: 'gate_condition',
      stage: 'how',
      code: 'UNSUPPORTED_CODE',
      severity: 'blocking',
      title: '不支持的检测项',
      description: '此类型暂不支持自动处理',
      blockingScope: 'stage_transition',
      metadata: {},
      capability: { kind: 'unsupported', action_label: '暂不支持自动处理', enabled: false },
    };

    const onPass = vi.fn();
    const onCancel = vi.fn();

    useWorkspaceStore.setState({
      activeGateCheck: {
        action: 'enter_how',
        findings: [unsupportedFinding],
        onPass,
        onCancel,
      }
    });

    render(<GateCheckModal />);

    // unsupported capability → 不显示按钮，显示手动修补提示
    expect(screen.queryByText('请返回对应步骤手动修补')).not.toBeNull();
    expect(screen.queryByText('暂不支持自动处理')).toBeNull();
  });

  it('should render capability-specific button labels for different finding types', () => {
    const allCapFindings: Finding[] = [
      {
        findingId: 'what:SCOPE_WITHOUT_REASON:scope:1',
        type: 'gate_condition',
        stage: 'what',
        code: 'SCOPE_WITHOUT_REASON',
        severity: 'blocking',
        title: '范围缺少理由',
        description: '范围结论缺少说明理由',
        blockingScope: 'stage_transition',
        metadata: {},
        capability: { kind: 'ai_repair', action_label: 'AI 修复', enabled: true },
      },
      {
        findingId: 'what:LEAF_FEATURE_WITHOUT_SCOPE:feature:2',
        type: 'gate_condition',
        stage: 'what',
        code: 'LEAF_FEATURE_WITHOUT_SCOPE',
        severity: 'blocking',
        title: '功能缺少范围',
        description: '叶子功能缺少范围结论',
        blockingScope: 'stage_transition',
        metadata: {},
        capability: { kind: 'generation_draft', action_label: '生成草稿', enabled: true },
      },
      {
        findingId: 'how:ACTOR_ACTION_STEP_WITHOUT_ACTOR:step:3',
        type: 'gate_condition',
        stage: 'how',
        code: 'ACTOR_ACTION_STEP_WITHOUT_ACTOR',
        severity: 'blocking',
        title: '步骤缺少参与者',
        description: '用户动作步骤缺少关联参与者',
        blockingScope: 'stage_transition',
        metadata: {},
        capability: { kind: 'open_panel', action_label: '定位处理', enabled: true },
      },
      {
        findingId: 'how:BUSINESS_OBJECT_WITHOUT_USAGE:bo:4',
        type: 'gate_condition',
        stage: 'how',
        code: 'BUSINESS_OBJECT_WITHOUT_USAGE',
        severity: 'blocking',
        title: '业务对象未被使用',
        description: '业务对象未被流程步骤使用',
        blockingScope: 'stage_transition',
        metadata: {},
        capability: { kind: 'ai_repair', action_label: 'AI 修复', enabled: true },
      },
    ];

    const onPass = vi.fn();
    const onCancel = vi.fn();

    useWorkspaceStore.setState({
      activeGateCheck: {
        action: 'enter_how',
        findings: allCapFindings,
        onPass,
        onCancel,
      }
    });

    render(<GateCheckModal />);

    // 验证多类 capability 按钮文案（AI 修复出现 2 次）
    expect(screen.queryAllByText('AI 修复').length).toBe(2);
    expect(screen.queryByText('生成草稿')).not.toBeNull();
    expect(screen.queryByText('定位处理')).not.toBeNull();
  });

  it('should not close modal when pendingGenerationConflict is set', async () => {
    const onPass = vi.fn();
    const onCancel = vi.fn();

    vi.spyOn(useWorkspaceStore.getState(), 'executeGateFindingAction').mockImplementation(async () => {
      useWorkspaceStore.setState({
        pendingGenerationConflict: {
          action: 'generateFeatures',
          generationType: 'feature',
          existingGroupId: 456,
          existingGroupLabel: '功能模块',
        } as any
      });
    });

    useWorkspaceStore.setState({
      activeGateCheck: {
        action: 'enter_how',
        findings: [mockFindings[0]],
        onPass,
        onCancel,
      }
    });

    render(<GateCheckModal />);

    const aiButton = screen.getByText('AI 修复');
    await act(async () => {
      fireEvent.click(aiButton);
    });

    expect(onCancel).not.toHaveBeenCalled();
  });
});
