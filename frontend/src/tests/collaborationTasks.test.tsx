import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { TaskDecisionModal } from '../components/shared/TaskDecisionModal';
import { useWorkspaceStore } from '../store/useWorkspaceStore';

vi.mock('../store/useWorkspaceStore', () => ({
  useWorkspaceStore: vi.fn((selector) => {
    const mockState = {
      decideTask: vi.fn(),
      loadProjectTasks: vi.fn(),
      refreshWorkspace: vi.fn(),
    };
    if (typeof selector === 'function') {
      return selector(mockState);
    }
    return mockState;
  }),
}));

const mockTask = {
  id: 42,
  title: 'Confirm New Payment Actor',
  description: 'Review details for the payment actor.',
  status: 'open',
  creatorEmail: 'editor@tasks.test',
  assigneeEmail: 'reviewer@tasks.test',
  assignedToUserId: 3,
  contentSnapshot: {
    name: 'Payment Actor',
    description: 'Responsible for paying',
  },
  contentChanged: false,
};

describe('TaskDecisionModal', () => {
  it('renders task details and readable content record correctly', () => {
    render(
      <TaskDecisionModal
        task={mockTask}
        projectId="proj-1"
        onClose={() => {}}
        onDecided={() => {}}
      />
    );

    expect(screen.getByText('Confirm New Payment Actor')).toBeDefined();
    expect(screen.getByText('Review details for the payment actor.')).toBeDefined();
    expect(screen.getByText('发起确认时的内容记录')).toBeDefined();
    expect(screen.getByText('Payment Actor')).toBeDefined();
    expect(screen.getByText('reviewer@tasks.test')).toBeDefined();
  });

  it('renders content changed warning when contentChanged is true', () => {
    const taskWithChange = { ...mockTask, contentChanged: true };
    render(
      <TaskDecisionModal
        task={taskWithChange}
        projectId="proj-1"
        onClose={() => {}}
        onDecided={() => {}}
      />
    );

    expect(screen.getByText('内容已经发生变化')).toBeDefined();
  });

  it('renders batch target snapshots instead of an empty top-level snapshot', () => {
    const batchTask = {
      ...mockTask,
      contentSnapshot: undefined,
      targets: [
        {
          node_kind: 'actor',
          node_id: 2,
          snapshot: {
            name: 'Project Draft Participant',
            description: 'Reviews the initial project draft',
          },
        },
      ],
    };

    render(
      <TaskDecisionModal
        task={batchTask}
        projectId="proj-1"
        onClose={() => {}}
        onDecided={() => {}}
      />
    );

    expect(screen.getByText('Project Draft Participant')).toBeDefined();
    expect(screen.getByText(/Reviews the initial project draft/)).toBeDefined();
  });

  it('calls decideTask when approve button is clicked', async () => {
    const mockDecide = vi.fn().mockResolvedValue({});
    vi.mocked(useWorkspaceStore).mockImplementation((selector: any) => {
      const state = {
        decideTask: mockDecide,
      };
      return selector(state);
    });

    const onDecidedMock = vi.fn();

    render(
      <TaskDecisionModal
        task={mockTask}
        projectId="proj-1"
        onClose={() => {}}
        onDecided={onDecidedMock}
      />
    );

    fireEvent.click(screen.getByText('通过'));

    await waitFor(() => {
      expect(mockDecide).toHaveBeenCalledWith('proj-1', 42, {
        decision: 'approve',
        decisionNote: undefined,
      });
      expect(onDecidedMock).toHaveBeenCalled();
    });
  });
});
