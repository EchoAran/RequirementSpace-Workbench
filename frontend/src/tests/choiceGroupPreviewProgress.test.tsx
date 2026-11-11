import { act, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ChoiceGroupPreviewModal } from '../components/shared/ChoiceGroupPreviewModal';
import { useWorkspaceStore } from '../store/useWorkspaceStore';

describe('ChoiceGroupPreviewModal generation progress', () => {
  it('uses simulated progress when backend progress is only an initial pending placeholder', () => {
    vi.useFakeTimers();

    try {
      render(
        <ChoiceGroupPreviewModal
          group={null}
          isWorking={true}
          isGeneratingChoices={true}
          generationProgress={{
            totalCandidates: 2,
            candidateLabels: ['均衡版', '全面版'],
            completedCandidates: 0,
            candidateStatuses: {
              0: 'pending',
              1: 'pending',
            },
          }}
          onAccept={vi.fn()}
          onDiscard={vi.fn()}
          onDefer={vi.fn()}
          onRegenerate={vi.fn()}
        />
      );

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(screen.getByText(/% \(0\/2\)/).textContent).not.toContain('0%');
      expect(screen.getByText('推演中')).toBeTruthy();
      expect(screen.getAllByText('排队中')).toHaveLength(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it('renders configured strategy labels for every candidate', () => {
    render(
      <ChoiceGroupPreviewModal
        group={null}
        isWorking={true}
        isGeneratingChoices={true}
        generationProgress={{
          totalCandidates: 3,
          candidateLabels: ['均衡版', '风险规避版', '流程优先版'],
          completedCandidates: 0,
          candidateStatuses: { 0: 'pending', 1: 'pending', 2: 'pending' },
        }}
        onAccept={vi.fn()}
        onDiscard={vi.fn()}
        onDefer={vi.fn()}
        onRegenerate={vi.fn()}
      />
    );

    expect(screen.getByText('风险规避版')).toBeTruthy();
    expect(screen.getByText('流程优先版')).toBeTruthy();
  });

  it('displays flow-specific loading title and subtasks when generating flows', () => {
    useWorkspaceStore.setState({
      generatingChoiceGroupType: 'flow',
      lastActionMessageToken: 'store.project.generatingCandidates',
    });

    render(
      <ChoiceGroupPreviewModal
        group={null}
        isWorking={true}
        isGeneratingChoices={true}
        generationProgress={null}
        onAccept={vi.fn()}
        onDiscard={vi.fn()}
        onDefer={vi.fn()}
        onRegenerate={vi.fn()}
      />
    );

    expect(screen.getByText('正在生成与重构业务流程与对象方案...')).toBeTruthy();
    expect(screen.queryByText('正在为您规划与推演初始项目草稿方案...')).toBeNull();
  });

  it('displays appropriate loading title when group.generationType is specified', () => {
    useWorkspaceStore.setState({
      generatingChoiceGroupType: null,
      lastActionMessageToken: 'store.project.generatingCandidates',
    });

    render(
      <ChoiceGroupPreviewModal
        group={{ generationType: 'actor', choices: [] }}
        isWorking={true}
        isGeneratingChoices={true}
        generationProgress={null}
        onAccept={vi.fn()}
        onDiscard={vi.fn()}
        onDefer={vi.fn()}
        onRegenerate={vi.fn()}
      />
    );

    expect(screen.getByText('正在推演与精炼参与者角色方案...')).toBeTruthy();
    expect(screen.queryByText('正在为您规划与推演初始项目草稿方案...')).toBeNull();
  });
});
