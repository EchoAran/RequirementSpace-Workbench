import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { ConfirmationWorkspace } from '../components/collaboration/ConfirmationWorkspace';
import { useWorkspaceStore } from '../store/useWorkspaceStore';

vi.mock('../store/useWorkspaceStore', () => ({
  useWorkspaceStore: vi.fn((selector) => {
    const mockState = {
      ir: {
        projectId: 'test-proj',
        actors: [
          { actorId: 1, actorName: 'Mock Actor', actorDescription: 'Desc', confirmationStatus: 'ai_assumption' }
        ]
      },
      currentUser: { id: 3, email: 'reviewer@test.com' },
      tasks: [
        {
          id: 101,
          title: 'Verify Actor Task',
          status: 'open',
          assignedToUserId: 3,
          creatorEmail: 'editor@test.com',
          assigneeEmail: 'reviewer@test.com',
          targets: [{ node_kind: 'actor', node_id: 1, snapshot: { name: 'Mock Actor', description: 'Desc' } }]
        }
      ],
      confirmationSummary: {
        aiAssumptionCount: 1,
        openTaskCount: 1,
        assignedToMeCount: 1,
        createdByMeCount: 0,
        rejectedCount: 0,
      },
      loadProjectTasks: vi.fn(),
      loadConfirmationSummary: vi.fn(),
      createBatchConfirmTask: vi.fn(),
      cancelTask: vi.fn(),
    };
    if (typeof selector === 'function') {
      return selector(mockState);
    }
    return mockState;
  }),
}));

vi.mock('@/lib/api', () => ({
  workspaceApi: {
    listProjectMembers: vi.fn().mockResolvedValue([
      { userId: 3, email: 'reviewer@test.com', role: 'editor', status: 'active' }
    ])
  }
}));

describe('ConfirmationWorkspace Component', () => {
  it('renders dashboard counts and tab switcher', () => {
    render(<ConfirmationWorkspace />);
    expect(screen.getByText('AI 假设节点')).toBeDefined();
    expect(screen.getByText('未完结任务')).toBeDefined();
    expect(screen.getByText('指派给我')).toBeDefined();
  });

  it('renders list of assumptions and tab task switcher click', () => {
    render(<ConfirmationWorkspace />);
    // Initial tab is assumptions, so "Mock Actor" should be visible
    expect(screen.getByText('Mock Actor')).toBeDefined();
    
    // Switch to tasks tab
    const tasksTab = screen.getByText('确认任务列表 (1)');
    fireEvent.click(tasksTab);
    expect(screen.getByText('Verify Actor Task')).toBeDefined();
  });
});
