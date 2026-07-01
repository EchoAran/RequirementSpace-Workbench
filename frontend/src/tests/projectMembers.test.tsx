import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import ProjectMembersModal from '../components/project/ProjectMembersModal';
import { workspaceApi } from '../lib/api';
import { ProjectMember } from '../core/schema';

// Mock the workspaceApi
vi.mock('../lib/api', () => ({
  workspaceApi: {
    listProjectMembers: vi.fn(),
    addProjectMember: vi.fn(),
    updateProjectMember: vi.fn(),
    removeProjectMember: vi.fn(),
  },
}));

const mockMembers: ProjectMember[] = [
  {
    memberId: 101,
    userId: 1,
    email: 'owner@perm.test',
    role: 'owner',
    status: 'active',
    joinedAt: '2026-06-27T03:00:00Z',
    createdAt: '2026-06-27T03:00:00Z',
    updatedAt: '2026-06-27T03:00:00Z',
  },
  {
    memberId: 102,
    userId: 2,
    email: 'editor@perm.test',
    role: 'editor',
    status: 'active',
    joinedAt: '2026-06-27T03:05:00Z',
    createdAt: '2026-06-27T03:05:00Z',
    updatedAt: '2026-06-27T03:05:00Z',
  },
  {
    memberId: 103,
    userId: 3,
    email: 'viewer@perm.test',
    role: 'viewer',
    status: 'active',
    joinedAt: '2026-06-27T03:10:00Z',
    createdAt: '2026-06-27T03:10:00Z',
    updatedAt: '2026-06-27T03:10:00Z',
  },
];

describe('ProjectMembersModal - Collaborative UI & Permissions', () => {
  it('renders list of members correctly', async () => {
    vi.mocked(workspaceApi.listProjectMembers).mockResolvedValue(mockMembers);

    render(
      <ProjectMembersModal
        projectId="test-proj-id"
        currentUserId={1}
        onClose={() => {}}
      />
    );

    // Should display loading first, then members
    expect(screen.getByText(/正在加载成员/i)).toBeDefined();

    await waitFor(() => {
      expect(screen.queryByText(/正在加载成员/i)).toBeNull();
    });

    expect(screen.getByText('owner@perm.test')).toBeDefined();
    expect(screen.getByText('editor@perm.test')).toBeDefined();
    expect(screen.getByText('viewer@perm.test')).toBeDefined();
  });

  it('renders management form and action buttons for Owner/Admin', async () => {
    vi.mocked(workspaceApi.listProjectMembers).mockResolvedValue(mockMembers);

    render(
      <ProjectMembersModal
        projectId="test-proj-id"
        currentUserId={1} // User 1 is Owner
        onClose={() => {}}
      />
    );

    await waitFor(() => {
      expect(screen.queryByText(/正在加载成员/i)).toBeNull();
    });

    // Owner should see the invitation form
    expect(screen.getByText(/邀请新成员/i)).toBeDefined();

    // Owner should see the role selector for other members
    const roleSelectors = screen.getAllByRole('combobox');
    // invitation select + other members (editor and viewer)
    expect(roleSelectors.length).toBe(3); 
  });

  it('hides management features for Editors and Viewers (Read-only View)', async () => {
    vi.mocked(workspaceApi.listProjectMembers).mockResolvedValue(mockMembers);

    render(
      <ProjectMembersModal
        projectId="test-proj-id"
        currentUserId={3} // User 3 is Viewer
        onClose={() => {}}
      />
    );

    await waitFor(() => {
      expect(screen.queryByText(/正在加载成员/i)).toBeNull();
    });

    // Viewer should NOT see the invitation form
    expect(screen.queryByText(/邀请新成员/i)).toBeNull();

    // Viewer should NOT see role selectors or trash icons
    const roleSelectors = screen.queryAllByRole('combobox');
    expect(roleSelectors.length).toBe(0);

    // Other roles are displayed as static text labels
    expect(screen.getByText('OWNER')).toBeDefined();
    expect(screen.getByText('EDITOR')).toBeDefined();
  });
});
