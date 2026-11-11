import { afterEach, describe, expect, it, vi } from 'vitest';
import { workspaceApi } from '../lib/api';
import { setRequestBranch } from '../lib/http';

describe('Explicit branch query propagation', () => {
  afterEach(() => { vi.unstubAllGlobals(); setRequestBranch(undefined); });

  it('keeps explicit main hydration when the implicit branch is test', async () => {
    setRequestBranch('test');
    const fetchMock = vi.fn().mockImplementation(async () => new Response('{}', { headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    await workspaceApi.getWorkspaceHydration('p', 'main');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/projects/p/hydrate?branch=main');
  });

  it('keeps generation and detail requests in an explicitly chosen test branch', async () => {
    setRequestBranch('main');
    const fetchMock = vi.fn().mockImplementation(async () => new Response('{}', { headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    await workspaceApi.createGenerationChoiceGroup({ project_id: 'p', generation_type: 'rule' }, 'test');
    await workspaceApi.getById('p', 'test');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/generation_choice_groups?branch=test');
    expect(fetchMock.mock.calls[1][0]).toBe('/api/projects/p?branch=test');
  });
});
