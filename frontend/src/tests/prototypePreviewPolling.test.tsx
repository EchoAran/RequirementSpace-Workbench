import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { workspaceApi } from '../lib/api';
import { Preview } from '../pages/Preview';

vi.mock('../store/useWorkspaceStore', () => {
  const state = {
    setSelectedObject: vi.fn(),
    setHighlightTarget: vi.fn(),
    highlightTarget: null,
    ir: {
      projectId: 'project-1',
      projectName: 'Polling project',
      actors: [{ actorId: 1, actorName: 'User' }],
      features: [{ featureId: 1, featureName: 'Feature', scope: { scopeStatus: 'current' } }],
      flows: [{ flowId: 1, flowName: 'Flow', flowSteps: [] }],
      businessObjects: [{ businessObjectId: 1, businessObjectName: 'Object' }],
      findings: [],
    },
    auditLogs: [],
    selectedObject: null,
    activeShadowDraft: null,
    getActiveShadowDraft: vi.fn().mockResolvedValue(null),
    prepareShadowDraft: vi.fn(),
    getShadowDraft: vi.fn(),
    discardShadowDraft: vi.fn(),
    commitShadowDraft: vi.fn(),
    regenerateShadowDraft: vi.fn(),
    triggerGateCheck: vi.fn((_gate, action) => action()),
  };
  const useWorkspaceStore = vi.fn((selector) =>
    typeof selector === 'function' ? selector(state) : state
  );
  Object.assign(useWorkspaceStore, { setState: vi.fn() });
  return {
    useWorkspaceStore,
    selectSelectedObject: () => null,
  };
});

vi.mock('../lib/api', () => ({
  workspaceApi: {
    getLatestPrototypePreview: vi.fn(),
  },
}));

describe('prototype preview polling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('resumes a persisted generating preview after refresh', async () => {
    vi.mocked(workspaceApi.getLatestPrototypePreview)
      .mockResolvedValueOnce({
        prototypeId: 7,
        projectId: 'project-1',
        html: '',
        javascript: '',
        css: '',
        pages: [],
        source: 'role_feature_pages',
        status: 'generating',
      })
      .mockResolvedValue({
        prototypeId: 7,
        projectId: 'project-1',
        html: '<main>Generated preview</main>',
        javascript: '',
        css: '',
        pages: [],
        source: 'role_feature_pages',
        status: 'ready',
      });

    render(<MemoryRouter><Preview /></MemoryRouter>);

    await waitFor(
      () => expect(workspaceApi.getLatestPrototypePreview).toHaveBeenCalledTimes(2),
      { timeout: 3000 },
    );
    expect(await screen.findByTitle(/prototype/i)).toBeDefined();
  });
});
