import { act, cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { App } from '../App';
import { workspaceApi } from '../lib/api';
import { getRequestBranch, setRequestBranch } from '../lib/http';
import { useWorkspaceStore } from '../store/useWorkspaceStore';

vi.mock('../components/auth/AuthGuard', () => ({ AuthGuard: ({ children }: any) => children }));
vi.mock('../components/layout/Layout', () => ({ Layout: ({ children }: any) => children }));
vi.mock('../components/shared/ScopedAIBar', () => ({ ScopedAIBar: () => null }));
vi.mock('../pages/Overview', () => ({ Overview: () => null }));
vi.mock('../store/useAuthStore', () => ({ useAuthStore: (selector: any) => selector({ checkAuth: vi.fn() }) }));

const detail = (branch: string) => ({ projectId: 'p', userRequirements: branch });

beforeEach(() => {
  window.history.replaceState({}, '', '/projects/p/overview?branch=work%2Fb');
  useWorkspaceStore.setState(useWorkspaceStore.getInitialState(), true);
  useWorkspaceStore.setState({
    ir: detail('A') as any, branchRef: 'work/a', pendingBranchRef: 'work/b',
    currentBranch: { name: 'work/a', permissions: { can_write: true } } as any,
  });
  setRequestBranch('work/a');
  vi.spyOn(workspaceApi, 'getWorkspaceHydration').mockResolvedValue({
    projectDetail: detail('B'), backendFindings: [], findingsByView: {}, choiceGroups: [],
  } as any);
  vi.spyOn(workspaceApi, 'listAuditLogs').mockResolvedValue([]);
  vi.spyOn(workspaceApi, 'listBranches').mockResolvedValue([{ name: 'work/b' }] as any);
  vi.spyOn(workspaceApi, 'listCommits').mockResolvedValue({ commits: [] } as any);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it('starts one switch when clearing a confirmed pending branch rerenders the route', async () => {
  let finish!: (value: any) => void;
  vi.spyOn(workspaceApi, 'getById').mockReturnValue(new Promise(resolve => { finish = resolve; }));
  render(<App />);
  await waitFor(() => expect(workspaceApi.getById).toHaveBeenCalledTimes(1));
  expect(getRequestBranch()).toBe('work/a');
  await act(async () => { finish(detail('B')); });
  await waitFor(() => expect(useWorkspaceStore.getState().branchRef).toBe('work/b'));
  expect(workspaceApi.getById).toHaveBeenCalledTimes(1);
  expect(new URLSearchParams(window.location.search).get('branch')).toBe('work/b');
});

it('restores the URL to the active branch after a failed switch', async () => {
  vi.spyOn(workspaceApi, 'getById').mockRejectedValue(new Error('network failed'));
  render(<App />);
  await waitFor(() => expect(new URLSearchParams(window.location.search).get('branch')).toBe('work/a'));
  expect(useWorkspaceStore.getState().branchRef).toBe('work/a');
  expect(getRequestBranch()).toBe('work/a');
  expect(workspaceApi.getById).toHaveBeenCalledTimes(1);
});

it('does not restore an old branch URL after navigating to a different project', async () => {
  let finishOld!: (value: any) => void;
  let finishNew!: (value: any) => void;
  vi.spyOn(workspaceApi, 'getById')
    .mockReturnValueOnce(new Promise(resolve => { finishOld = resolve; }))
    .mockReturnValueOnce(new Promise(resolve => { finishNew = resolve; }));
  vi.mocked(workspaceApi.getWorkspaceHydration).mockResolvedValue({
    projectDetail: { projectId: 'other', userRequirements: 'C' },
    backendFindings: [], findingsByView: {}, choiceGroups: [],
  } as any);
  render(<App />);
  await waitFor(() => expect(workspaceApi.getById).toHaveBeenCalledTimes(1));
  await act(async () => {
    window.history.pushState({}, '', '/projects/other/overview?branch=work%2Fc');
    window.dispatchEvent(new PopStateEvent('popstate'));
  });
  await waitFor(() => expect(workspaceApi.getById).toHaveBeenCalledTimes(2));
  await act(async () => { finishOld(detail('B')); });
  expect(new URLSearchParams(window.location.search).get('branch')).toBe('work/c');
  await act(async () => { finishNew({ projectId: 'other', userRequirements: 'C' }); });
  await waitFor(() => expect(useWorkspaceStore.getState().ir?.projectId).toBe('other'));
  expect(getRequestBranch()).toBe('work/c');
});
