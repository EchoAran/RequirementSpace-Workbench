import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { workspaceApi } from '../lib/api';
import { WorkspaceListItem } from '../core/schema';

// Mock workspaceApi
vi.mock('../lib/api', () => ({
  workspaceApi: {
    list: vi.fn(),
    listFindings: vi.fn().mockResolvedValue([]),
    listChoiceGroups: vi.fn().mockResolvedValue([]),
  },
}));

describe('useWorkspaceStore - Project List Membership Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useWorkspaceStore.setState({
      workspaces: [],
    });
  });

  it('successfully loads project list with membership metadata', async () => {
    const mockWorkspaces: WorkspaceListItem[] = [
      {
        id: 'p-1',
        name: 'Project A',
        idea: 'Idea A',
        description: 'Description A',
        updatedAt: '2026-06-27T03:00:00Z',
        status: 'active',
        issueCount: 0,
        nodeCount: 5,
        membershipRole: 'owner',
        ownerUserId: 1,
        memberCount: 2,
      },
      {
        id: 'p-2',
        name: 'Project B',
        idea: 'Idea B',
        description: 'Description B',
        updatedAt: '2026-06-27T03:10:00Z',
        status: 'active',
        issueCount: 3,
        nodeCount: 12,
        membershipRole: 'editor',
        ownerUserId: 2,
        memberCount: 4,
      },
    ];

    vi.mocked(workspaceApi.list).mockResolvedValue(mockWorkspaces);

    // Call store method
    await useWorkspaceStore.getState().loadWorkspaces();

    // Verify state updates
    const state = useWorkspaceStore.getState();
    expect(state.workspaces.length).toBe(2);

    // Assert that collaborative fields are preserved in the store state
    const first = state.workspaces[0];
    expect(first.id).toBe('p-1');
    expect(first.membershipRole).toBe('owner');
    expect(first.ownerUserId).toBe(1);
    expect(first.memberCount).toBe(2);

    const second = state.workspaces[1];
    expect(second.id).toBe('p-2');
    expect(second.membershipRole).toBe('editor');
    expect(second.ownerUserId).toBe(2);
    expect(second.memberCount).toBe(4);
  });
});
