import { describe, expect, it, vi } from 'vitest';
import { workspaceApi } from '../lib/api';
import { useWorkspaceStore } from '../store/useWorkspaceStore';

// Mock workspaceApi
vi.mock('../lib/api', () => ({
  workspaceApi: {
    listAuditLogs: vi.fn(),
  },
}));

describe('Audit Logs Schema Mapping', () => {
  it('maps raw API audit log objects into store structure with actor details and diffs', async () => {
    const rawLogs = [
      {
        id: 1,
        project_id: 'proj_1',
        action_type: 'update_user_requirements',
        summary: '手动更新用户需求文档',
        target_type: 'project',
        target_id: '1',
        created_at: '2026-06-27T03:00:00.000Z',
        actor_user_id: 1,
        actor_type: 'user',
        actor_email: 'auditor@test.com',
        diff: {
          user_requirements: {
            before: 'Old Reqs',
            after: 'New Reqs',
          },
        },
        request_id: 'req_xyz123',
        task_id: null,
      },
      {
        id: 2,
        project_id: 'proj_1',
        action_type: 'refine_user_requirements',
        summary: '通过LLM精炼优化用户需求文档',
        target_type: 'project',
        target_id: '1',
        created_at: '2026-06-27T03:05:00.000Z',
        actor_user_id: 1,
        actor_type: 'ai',
        actor_email: 'auditor@test.com',
        diff: {
          user_requirements: {
            before: 'New Reqs',
            after: 'Refined Reqs',
          },
        },
        request_id: 'req_abc999',
        task_id: null,
      },
    ];

    vi.mocked(workspaceApi.listAuditLogs).mockResolvedValue(rawLogs);

    // Call store action
    await useWorkspaceStore.getState().loadAuditLogs('proj_1');

    // Retrieve state
    const mappedLogs = useWorkspaceStore.getState().auditLogs;
    expect(mappedLogs.length).toBe(2);

    // First log check (update_user_requirements)
    const log1 = mappedLogs[0];
    expect(log1.id).toBe('1');
    expect(log1.timestamp).toBe('2026-06-27T03:00:00.000Z');
    expect(log1.actionType).toBe('update_user_requirements');
    expect(log1.summary).toBe('手动更新用户需求文档');
    expect(log1.actorUserId).toBe(1);
    expect(log1.actorType).toBe('user');
    expect(log1.actorEmail).toBe('auditor@test.com');
    expect(log1.diff).toEqual({
      user_requirements: {
        before: 'Old Reqs',
        after: 'New Reqs',
      },
    });
    expect(log1.requestId).toBe('req_xyz123');

    // Second log check (refine_user_requirements)
    const log2 = mappedLogs[1];
    expect(log2.id).toBe('2');
    expect(log2.timestamp).toBe('2026-06-27T03:05:00.000Z');
    expect(log2.actionType).toBe('refine_user_requirements');
    expect(log2.actorType).toBe('ai');
    expect(log2.requestId).toBe('req_abc999');
  });
});
