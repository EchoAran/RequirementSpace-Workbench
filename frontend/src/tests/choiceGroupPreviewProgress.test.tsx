import { act, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ChoiceGroupPreviewModal } from '../components/shared/ChoiceGroupPreviewModal';

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
});
