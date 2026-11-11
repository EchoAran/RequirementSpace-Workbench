import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { workspaceApi } from '../lib/api';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { getRequestBranch, setRequestBranch } from '../lib/http';

const detail = (branch: string) => ({ projectId: 'audit-project', projectName: 'Audit', userRequirements: `REQUIREMENTS_${branch}` });
beforeEach(() => {
  useWorkspaceStore.setState(useWorkspaceStore.getInitialState(), true);
  useWorkspaceStore.setState({ sessionVersion: 1, ir: detail('A') as any, branchRef: 'work/a',
    currentBranch: { name: 'work/a', is_protected: false, is_default: false, permissions: { can_write: true } } as any });
  setRequestBranch('work/a');
  vi.spyOn(workspaceApi, 'getById').mockResolvedValue(detail('B') as any);
  vi.spyOn(workspaceApi, 'getWorkspaceHydration').mockResolvedValue({ projectDetail: detail('B'),
    findingsByView: {}, backendFindings: [], choiceGroups: [] } as any);
  vi.spyOn(workspaceApi, 'listAuditLogs').mockResolvedValue([]);
  vi.spyOn(workspaceApi, 'listBranches').mockResolvedValue([
    { public_id: 'work/b', name: 'work/b', permissions: { can_write: true }, is_default: false, is_protected: false },
  ] as any);
  vi.spyOn(workspaceApi, 'listCommits').mockResolvedValue({ commits: [] } as any);
});
afterEach(() => vi.restoreAllMocks());

it('switching branch discards old drafts and releases generation state', async () => {
  useWorkspaceStore.setState({ activeDraft: { draftId: 'DRAFT_CREATED_ON_A' }, activeDraftType: 'scenario' });
  let finish!: (value: any) => void;
  vi.spyOn(workspaceApi, 'regenerateScenarioGenerationDraft').mockReturnValue(new Promise(resolve => { finish = resolve; }));
  const generating = useWorkspaceStore.getState().regenerateScenarios('audit feedback');
  expect(useWorkspaceStore.getState().isGenerating).toBe(true);
  expect(useWorkspaceStore.getState().requestBranchSwitch('work/b')).toBe(false);
  useWorkspaceStore.getState().discardPendingEdits();
  expect(await useWorkspaceStore.getState().switchBranch('work/b')).toBe(true);
  finish({ draftId: 'DRAFT_CREATED_ON_A' });
  await generating;
  const state = useWorkspaceStore.getState();
  expect(state.branchRef).toBe('work/b');
  expect(state.ir?.userRequirements).toBe('REQUIREMENTS_B');
  expect(state.activeDraft).toBeNull();
  expect(state.activeDraftType).toBeNull();
  expect(state.isGenerating).toBe(false);
});

it('a failed branch switch preserves the previous data and request context', async () => {
  vi.mocked(workspaceApi.getById).mockRejectedValueOnce(new Error('audit simulated network error'));
  expect(await useWorkspaceStore.getState().switchBranch('work/b')).toBe(false);
  const state = useWorkspaceStore.getState();
  expect(state.ir?.userRequirements).toBe('REQUIREMENTS_A');
  expect(state.branchRef).toBe('work/a');
  expect(getRequestBranch()).toBe('work/a');
  expect(state.currentBranch?.name).toBe('work/a');
  expect(state.branchLoading).toBe(false);
});

it('keeps branch data unchanged when target hydration fails', async () => {
  vi.mocked(workspaceApi.getWorkspaceHydration).mockRejectedValueOnce(new Error('hydration failed'));
  expect(await useWorkspaceStore.getState().switchBranch('work/b')).toBe(false);
  expect(workspaceApi.getWorkspaceHydration).toHaveBeenCalledWith('audit-project', 'work/b');
  const state = useWorkspaceStore.getState();
  expect(state.ir?.userRequirements).toBe('REQUIREMENTS_A');
  expect(state.branchRef).toBe('work/a');
  expect(getRequestBranch()).toBe('work/a');
  expect(state.currentBranch?.name).toBe('work/a');
});

it('ignores a completed branch load after a newer switch has started', async () => {
  let finish!: (value: any) => void;
  vi.mocked(workspaceApi.getById).mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
  const oldSwitch = useWorkspaceStore.getState().switchBranch('work/old');
  expect(getRequestBranch()).toBe('work/a');
  expect(await useWorkspaceStore.getState().switchBranch('work/b')).toBe(true);
  finish(detail('OLD'));
  expect(await oldSwitch).toBe(false);
  expect(useWorkspaceStore.getState().ir?.userRequirements).toBe('REQUIREMENTS_B');
  expect(getRequestBranch()).toBe('work/b');
});

it('keeps the active request branch when reopening a workspace fails', async () => {
  vi.mocked(workspaceApi.getById).mockRejectedValueOnce(new Error('load failed'));
  expect(await useWorkspaceStore.getState().openWorkspace('other-project', 'work/b')).toBe(false);
  expect(useWorkspaceStore.getState().ir?.userRequirements).toBe('REQUIREMENTS_A');
  expect(useWorkspaceStore.getState().branchRef).toBe('work/a');
  expect(getRequestBranch()).toBe('work/a');
});
