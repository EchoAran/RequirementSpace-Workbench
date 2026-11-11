import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { domainRuleApi } from '../lib/api';
import { useWorkspaceStore } from '../store/useWorkspaceStore';

const action = useWorkspaceStore.getState().replaceTargetRules;
const refresh = vi.fn().mockResolvedValue(undefined);
beforeEach(() => {
  vi.clearAllMocks();
  useWorkspaceStore.setState({ ir: { projectId: 'project-1' } as any, branchRef: 'codex/rules',
    sessionVersion: 1, workspaceCanWrite: () => true, replaceTargetRules: action, refreshWorkspace: refresh });
});
afterEach(() => vi.restoreAllMocks());

describe('Target rule association save', () => {
  it.each(['flow', 'flow_step'] as const)('refreshes after saving %s with an empty JSON 204 response', async targetKind => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, {
      status: 204, headers: { 'Content-Type': 'application/json' },
    }));
    await expect(action(targetKind, 'target-1', [1])).resolves.toBeUndefined();
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it('saves the target in the active branch and refreshes once', async () => {
    const save = vi.spyOn(domainRuleApi, 'replaceTargetRules').mockResolvedValue(undefined);
    await action('flow_step', 'step-1', [1, 2]);
    expect(save).toHaveBeenCalledWith('project-1', {
      targetKind: 'flow_step', targetLogicalUuid: 'step-1', ruleIds: [1, 2],
    }, 'codex/rules');
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it('propagates a failed save without refreshing as if it succeeded', async () => {
    vi.spyOn(domainRuleApi, 'replaceTargetRules').mockRejectedValue(new Error('save failed'));
    await expect(action('flow', 'flow-1', [])).rejects.toThrow('save failed');
    expect(refresh).not.toHaveBeenCalled();
  });

  it('does not write in read-only mode', async () => {
    const save = vi.spyOn(domainRuleApi, 'replaceTargetRules').mockResolvedValue(undefined);
    useWorkspaceStore.setState({ workspaceCanWrite: () => false });
    await expect(action('flow', 'flow-1', [])).rejects.toThrow('versionControl.readOnlyToast');
    expect(save).not.toHaveBeenCalled();
  });

  it('does not refresh another session after a branch switch', async () => {
    vi.spyOn(domainRuleApi, 'replaceTargetRules').mockImplementation(async () => {
      useWorkspaceStore.setState({ sessionVersion: 2 });
    });
    await action('flow', 'flow-1', []);
    expect(refresh).not.toHaveBeenCalled();
  });

  it('uses one PUT request with an explicit branch and a clearable rule list', async () => {
    const fetchMock = vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 204 }));
    await domainRuleApi.replaceTargetRules('project-1', {
      targetKind: 'flow', targetLogicalUuid: 'flow-1', ruleIds: [],
    }, 'codex/rules');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(String(url)).toContain('/projects/project-1/rules/associations?branch=codex%2Frules');
    expect(options?.method).toBe('PUT');
    expect(JSON.parse(String(options?.body))).toEqual({ targetKind: 'flow', targetLogicalUuid: 'flow-1', ruleIds: [] });
  });
});
