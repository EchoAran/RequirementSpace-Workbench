import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { setRequestBranch } from '../lib/http';
import { workspaceApi } from '../lib/api';

vi.mock('../lib/api', () => ({
  workspaceApi: {
    getById: vi.fn().mockResolvedValue({ projectId: 'p', userRequirements: 'detail' }),
    getWorkspaceHydration: vi.fn().mockResolvedValue({
      projectDetail: { projectId: 'p', userRequirements: 'hydrated' },
      backendFindings: [], findingsByView: {}, choiceGroups: [],
    }),
    listFindings: vi.fn().mockResolvedValue({ findings: [] }),
    listChoiceGroups: vi.fn().mockResolvedValue([]),
    listAuditLogs: vi.fn().mockResolvedValue([]),
    getStageProgress: vi.fn().mockResolvedValue({}),
    listBranches: vi.fn().mockResolvedValue([]),
    listCommits: vi.fn().mockResolvedValue({ commits: [] }),
    getProjectConfiguration: vi.fn().mockResolvedValue({ generation_strategy: { candidate_count: 2 } }),
    createGenerationChoiceGroup: vi.fn().mockResolvedValue({ id: 20, status: 'open', choices: [] }),
  },
}));

describe('Branch isolation during loading and generation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setRequestBranch('test');
    useWorkspaceStore.setState({
      sessionVersion: 1, branchRef: 'test', ir: { projectId: 'p' } as any,
      backendChoiceGroups: {}, isGeneratingChoices: false,
      projectConfiguration: null,
      branchLoading: false,
      currentBranch: { name: 'test', is_protected: false, is_default: false, permissions: { can_write: true } } as any,
    });
  });

  it('opens main with main hydration after visiting test', async () => {
    expect(await useWorkspaceStore.getState().openWorkspace('p', 'main')).toBe(true);
    expect(workspaceApi.getById).toHaveBeenCalledWith('p', 'main');
    expect(workspaceApi.getWorkspaceHydration).toHaveBeenCalledWith('p', 'main');
    expect(useWorkspaceStore.getState().ir?.userRequirements).toBe('hydrated');
  });

  it('keeps the fallback choice and finding reads in the requested branch', async () => {
    vi.mocked(workspaceApi.getWorkspaceHydration).mockRejectedValueOnce(new Error('hydrate unavailable'));
    expect(await useWorkspaceStore.getState().openWorkspace('p', 'main')).toBe(true);
    expect(workspaceApi.listChoiceGroups).toHaveBeenCalledWith('p', 'open', 'main');
    expect(workspaceApi.listFindings).toHaveBeenCalledWith('p', { view: 'issues', stage: 'all', branch: 'main' });
  });

  it('does not send generation after a branch switch while loading defaults', async () => {
    let finish!: (value: any) => void;
    vi.mocked(workspaceApi.getProjectConfiguration).mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
    const pending = useWorkspaceStore.getState().createGenerationChoiceGroup({ projectId: 'p', generationType: 'rule' });
    await useWorkspaceStore.getState().switchBranch('main');
    finish({ generation_strategy: { candidate_count: 2 } });
    expect(await pending).toBeNull();
    expect(workspaceApi.createGenerationChoiceGroup).not.toHaveBeenCalled();
    expect(useWorkspaceStore.getState().projectConfiguration).toBeNull();
    expect(useWorkspaceStore.getState().isGeneratingChoices).toBe(false);
  });

  it('clears a foreign choice modal and generation state on branch switch', async () => {
    useWorkspaceStore.setState({ activeChoiceGroup: { id: 6 } as any, isGeneratingChoices: true, generatingChoiceGroupType: 'rule' });
    await useWorkspaceStore.getState().switchBranch('main');
    expect(useWorkspaceStore.getState().activeChoiceGroup).toBeNull();
    expect(useWorkspaceStore.getState().isGeneratingChoices).toBe(false);
    expect(useWorkspaceStore.getState().generatingChoiceGroupType).toBeNull();
  });

  it('passes the originating branch explicitly to generation', async () => {
    await useWorkspaceStore.getState().createGenerationChoiceGroup({ projectId: 'p', generationType: 'rule', candidateCount: 2 });
    expect(workspaceApi.createGenerationChoiceGroup).toHaveBeenCalledWith(expect.objectContaining({ project_id: 'p', generation_type: 'rule' }), 'test');
  });
});
