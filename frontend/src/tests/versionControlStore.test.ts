import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { getRequestBranch, setRequestBranch } from '../lib/http';

vi.mock('../lib/api', () => ({
  workspaceApi: {
    getWorkspaceHydration: vi.fn().mockResolvedValue({
      backendFindings: [],
      findingsByView: { issues: [], nextAction: [], gate: [], health: [] },
      choiceGroups: [],
      stageProgress: { stages: [] },
    }),
    getById: vi.fn().mockResolvedValue({ projectId: 'project-123', projectName: 'P', userRequirements: '' }),
    listFindings: vi.fn().mockResolvedValue({ findings: [], total: 0 }),
    listChoiceGroups: vi.fn().mockResolvedValue([]),
    listAuditLogs: vi.fn().mockResolvedValue([]),
    getStageProgress: vi.fn().mockResolvedValue({ stages: [] }),
    listBranches: vi.fn().mockResolvedValue([
      { id: 1, public_id: 'main-1', name: 'main', is_protected: true, is_default: true, permissions: { can_write: false }, workspace_dirty: { is_dirty: false, modified_entities_count: 0 } },
      { id: 2, public_id: 'feature-a', name: 'feature/探索', is_protected: false, is_default: false, head_commit_public_id: 'abc123', permissions: { can_write: true }, workspace_dirty: { is_dirty: true, modified_entities_count: 2 } },
    ]),
    listCommits: vi.fn().mockResolvedValue({ commits: [], total: 0, limit: 100, offset: 0 }),
    createCommit: vi.fn().mockResolvedValue({}),
  },
}));

import { workspaceApi } from '../lib/api';

describe('Version Control Store Branch Actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setRequestBranch(undefined);
    useWorkspaceStore.setState({
      sessionVersion: 0,
      branchRef: 'main',
      branches: null,
      currentBranch: null,
      commits: null,
      branchLoading: false,
      commitLoading: false,
      commitError: null,
      ir: null,
      stageProgress: null,
      backendFindingsLoaded: false,
    });
  });

  it('openWorkspace 携带分支 ref 并加载分支与提交', async () => {
    const ok = await useWorkspaceStore.getState().openWorkspace('project-123', 'feature-a');
    expect(ok).toBe(true);
    expect(getRequestBranch()).toBe('feature-a');
    expect(workspaceApi.getById).toHaveBeenCalledWith('project-123', 'feature-a');
    expect(workspaceApi.getWorkspaceHydration).toHaveBeenCalledWith('project-123', 'feature-a');
    expect(workspaceApi.listFindings).not.toHaveBeenCalled();
    expect(workspaceApi.listBranches).toHaveBeenCalledWith('project-123');
    expect(workspaceApi.listCommits).toHaveBeenCalledWith('project-123', { all: true, limit: 50, offset: 0 });
    const state = useWorkspaceStore.getState();
    expect(state.branchRef).toBe('feature-a');
    expect(state.currentBranch?.name).toBe('feature/探索');
    expect(state.commits).not.toBeNull();
  });

  it('switchBranch 更新请求上下文与当前分支', async () => {
    useWorkspaceStore.setState({ ir: { projectId: 'project-123', projectName: 'P', userRequirements: '' } as any });
    const ok = await useWorkspaceStore.getState().switchBranch('feature-a');
    expect(ok).toBe(true);
    expect(getRequestBranch()).toBe('feature-a');
    expect(useWorkspaceStore.getState().branchRef).toBe('feature-a');
    expect(useWorkspaceStore.getState().currentBranch?.public_id).toBe('feature-a');
  });

  it('createCommit 409 冲突写入 commitError', async () => {
    useWorkspaceStore.setState({ ir: { projectId: 'project-123', projectName: 'P', userRequirements: '' } as any, branchRef: 'feature-a', sessionVersion: 1 });
    (workspaceApi.createCommit as ReturnType<typeof vi.fn>).mockRejectedValueOnce({ status: 409 });
    const ok = await useWorkspaceStore.getState().createCommit('msg', 'abc123');
    expect(ok).toBe(false);
    expect(useWorkspaceStore.getState().commitError).toBe('versionControl.commitConflict');
    expect(workspaceApi.createCommit).toHaveBeenCalledWith('project-123', {
      message: 'msg',
      expected_head_commit_public_id: 'abc123',
    });
  });

  it('executeSuggestion navigate 动作在 feature 分支下导航保留分支参数', async () => {
    useWorkspaceStore.setState({
      ir: { projectId: 'project-123', projectName: 'P', userRequirements: '' } as any,
      branchRef: 'feature/scope-preview',
      sessionVersion: 1,
      currentBranch: { id: 2, public_id: 'br-feature-123', name: 'feature/scope-preview', permissions: { can_write: true } } as any,
    });

    const navigateMock = vi.fn();
    const suggestionFinding = {
      findingId: 'scope:ENTER_PREVIEW:project:123',
      type: 'next_suggestion' as const,
      stage: 'scope' as const,
      code: 'ENTER_PREVIEW',
      severity: 'info' as const,
      title: '进入预览阶段',
      description: '进入最终产物确认',
      blockingScope: 'none' as const,
      metadata: {
        action: {
          kind: 'navigate',
          route: '/preview',
          label: '进入交付物预览',
        },
      },
    };

    const result = await useWorkspaceStore.getState().startFindingSuggestion(suggestionFinding as any, { navigate: navigateMock });
    expect(result).toEqual({
      type: 'navigation',
      route: '/projects/project-123/preview?branch=feature%2Fscope-preview',
    });
    expect(navigateMock).toHaveBeenCalledWith('/projects/project-123/preview?branch=feature%2Fscope-preview');
  });
});
