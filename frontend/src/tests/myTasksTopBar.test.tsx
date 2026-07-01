import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { TopBar } from '../components/layout/TopBar';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { useAuthStore } from '../store/useAuthStore';

// Mock react-router-dom
vi.mock('react-router-dom', () => ({
  useLocation: () => ({ pathname: '/overview' }),
  useNavigate: () => vi.fn(),
}));

vi.mock('../store/useWorkspaceStore', () => ({
  useWorkspaceStore: vi.fn((selector) => {
    const mockState = {
      exitWorkspace: vi.fn(),
      ir: {
        projectId: 'test-proj',
        projectName: 'TopBar Test Project'
      },
      userTasks: [
        {
          task: {
            id: 201,
            title: 'Popover Task Item',
            priority: 'high',
            creatorEmail: 'creator@tasks.test',
            assigneeEmail: 'me@tasks.test',
            dueAt: '2026-12-31',
            createdAt: '2026-06-27T12:00:00Z',
          },
          projectSummary: {
            projectId: 'test-proj',
            projectName: 'TopBar Test Project'
          },
          targetSummary: {
            nodeKind: 'actor',
            nodeId: 1,
            nodeName: 'Test Target Node'
          },
          creatorSummary: {
            userId: 3,
            email: 'creator@tasks.test'
          },
          assigneeSummary: {
            userId: 5,
            email: 'me@tasks.test'
          },
          contentChanged: false
        }
      ],
      loadMyTasks: vi.fn(),
      refreshWorkspace: vi.fn(),
      loadConfirmationSummary: vi.fn(),
    };
    if (typeof selector === 'function') {
      return selector(mockState);
    }
    return mockState;
  }),
}));

vi.mock('../store/useAuthStore', () => ({
  useAuthStore: vi.fn(() => ({
    user: { id: 5, email: 'me@tasks.test', role: 'editor' },
    logout: vi.fn(),
  })),
}));

describe('TopBar - My Tasks Checklist Popover', () => {
  it('renders task count badge in header button', () => {
    render(<TopBar />);
    // Badge has count '1'
    expect(screen.getByText('1')).toBeDefined();
  });

  it('toggles the tasks popover checklist when clicked', () => {
    render(<TopBar />);
    
    // Clicking the trigger button
    const trigger = screen.getByTitle('待我审批确认的任务');
    fireEvent.click(trigger);
    
    // Check if popover shows
    expect(screen.getByText('待办审批确认清单')).toBeDefined();
    expect(screen.getByText('Popover Task Item')).toBeDefined();
  });
});
