import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RightObjectPanel } from '../components/shared/RightObjectPanel';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { useAuthStore } from '../store/useAuthStore';
import { workspaceApi } from '../lib/api';

const originalLoadProjectTasks = useWorkspaceStore.getState().loadProjectTasks;

describe('RightObjectPanel actor task history', () => {
  beforeEach(() => {
    vi.spyOn(workspaceApi, 'listProjectMembers').mockResolvedValue([]);
    useAuthStore.setState({
      user: { id: 7, email: 'reviewer@example.com', role: 'user' } as any,
      isAuthenticated: true,
    });
    useWorkspaceStore.setState({
      ir: {
        projectId: 'project-1',
        projectName: 'Panel Test',
        actors: [],
        features: [],
        businessObjects: [],
        flows: [],
      } as any,
      selectedObject: {
        id: 'actor-1',
        kind: 'actor',
        actorId: 1,
        actorName: 'Product Owner',
        actorDescription: 'Owns the backlog',
        confirmationStatus: 'confirmed',
      },
      tasks: [{
        id: 10,
        title: 'Historical confirmation',
        taskType: 'confirm_node',
        targetType: 'actor',
        targetId: '1',
        status: 'done',
        assignedToUserId: 7,
        assigneeEmail: 'reviewer@example.com',
      }],
      loadProjectTasks: vi.fn(),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    useWorkspaceStore.setState({
      ir: null,
      selectedObject: null,
      tasks: [],
      loadProjectTasks: originalLoadProjectTasks,
    });
  });

  it('renders a participant with historical tasks without entering the panel error boundary', () => {
    render(<RightObjectPanel />);

    expect(screen.queryByText('审查面板渲染发生错误')).toBeNull();
    expect(screen.getByText('历史审批与驳回记录')).toBeDefined();
    expect(screen.getByText('Historical confirmation')).toBeDefined();
  });
});
