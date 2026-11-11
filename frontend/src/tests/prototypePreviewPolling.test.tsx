import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { workspaceApi } from '../lib/api';
import { Preview } from '../pages/Preview';

vi.mock('../store/useWorkspaceStore', () => {
  const state = {
    setSelectedObject: vi.fn(),
    ir: {
      projectId: 'project-1',
      projectName: 'Polling project',
      actors: [
        { actorId: 1, actorName: 'Analyst' },
        { actorId: 2, actorName: 'Manager' },
      ],
      features: [{ featureId: 1, featureName: 'Feature', actorIds: [1, 2], scope: { scopeStatus: 'current' } }],
      flows: [{ flowId: 1, flowName: 'Flow', flowSteps: [] }],
      businessObjects: [{ businessObjectId: 1, businessObjectName: 'Object' }],
      findings: [],
    },
    auditLogs: [],
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
    generatePrototypePreview: vi.fn(),
  },
}));

describe('prototype preview polling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('preserves generated scripts while assembling a self-contained iframe', async () => {
    const javascript = "(() => { const $ = (s) => document.querySelector(s); const $$ = (s) => [...document.querySelectorAll(s)]; $('#add').addEventListener('click', () => $$('#add')); })();";
    vi.mocked(workspaceApi.getLatestPrototypePreview).mockResolvedValue({
      prototypeId: 9,
      projectId: 'project-1',
      html: `<!doctype html><html><head>
        <link href="https://fonts.googleapis.com/css2?family=Example" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.example.com/theme.css">
        <link rel="preconnect" href="https://fonts.gstatic.com">
        <link rel="dns-prefetch" href="https://fonts.googleapis.com">
        <link rel="icon" href="data:image/svg+xml,icon">
        <link rel="stylesheet" href="style.css">
      </head><body><button id="add">Add</button><script src="script.js"></script></body></html>`,
      javascript,
      css: 'button { color: green; }',
      pages: [],
      source: 'role_feature_pages',
      status: 'ready',
    });

    render(<MemoryRouter><Preview /></MemoryRouter>);

    const frame = await screen.findByTitle(/prototype/i);
    const srcDoc = frame.getAttribute('srcdoc') || '';
    expect(srcDoc).not.toContain('fonts.googleapis.com');
    expect(srcDoc).not.toContain('cdn.example.com');
    expect(srcDoc).not.toContain('fonts.gstatic.com');
    expect(srcDoc).toContain('<link rel="icon" href="data:image/svg+xml,icon">');
    expect(srcDoc).toContain('<style>button { color: green; }</style>');
    expect(srcDoc).toContain(`<script>${javascript}</script>`);
    expect(srcDoc).not.toContain('src="script.js"');
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

  it('switches the iframe document when the active role changes', async () => {
    vi.mocked(workspaceApi.getLatestPrototypePreview).mockResolvedValue({
      prototypeId: 8,
      projectId: 'project-1',
      html: '<main>Analyst preview</main>',
      javascript: '',
      css: '',
      pages: [
        {
          pageId: 'role-1-feature-1',
          roleId: 1,
          roleName: 'Analyst',
          featureId: 1,
          featureName: 'Review bid',
          html: '<main>Analyst preview</main>',
          javascript: '',
          css: '',
          source: 'role_feature_pages',
          status: 'ready',
        },
        {
          pageId: 'role-2-feature-1',
          roleId: 2,
          roleName: 'Manager',
          featureId: 1,
          featureName: 'Approve bid',
          html: '<main>Manager preview</main>',
          javascript: '',
          css: '',
          source: 'role_feature_pages',
          status: 'ready',
        },
      ],
      source: 'role_feature_pages',
      status: 'ready',
    });

    render(<MemoryRouter><Preview /></MemoryRouter>);

    const analystFrame = await screen.findByTitle('Analyst prototype');
    expect(analystFrame.getAttribute('srcdoc')).toContain('Analyst preview');

    fireEvent.click(screen.getByRole('button', { name: /Manager/ }));

    await waitFor(() => {
      const managerFrame = screen.getByTitle('Manager prototype');
      expect(managerFrame.getAttribute('srcdoc')).toContain('Manager preview');
    });
  });

  it('shows an explicit empty state instead of another role\'s first page', async () => {
    vi.mocked(workspaceApi.getLatestPrototypePreview).mockResolvedValue({
      prototypeId: 9,
      projectId: 'project-1',
      html: '<main>Analyst preview</main>',
      javascript: '',
      css: '',
      pages: [
        {
          pageId: 'role-1-feature-1',
          roleId: 1,
          roleName: 'Analyst',
          featureId: 1,
          featureName: 'Review bid',
          html: '<main>Analyst preview</main>',
          javascript: '',
          css: '',
          source: 'role_feature_pages',
          status: 'ready',
        },
      ],
      source: 'role_feature_pages',
      status: 'ready',
    });

    render(<MemoryRouter><Preview /></MemoryRouter>);

    await screen.findByTitle('Analyst prototype');
    fireEvent.click(screen.getByRole('button', { name: /Manager/ }));

    expect(await screen.findByText('该参与者暂无生成预览')).toBeDefined();
    expect(screen.queryByTitle('Manager prototype')).toBeNull();
  });
});


describe('prototype preview failures', () => {
  it('shows a persisted failure even when no compiled panel exists', async () => {
    vi.mocked(workspaceApi.getLatestPrototypePreview).mockResolvedValue({
      prototypeId: 10, status: 'failed', errorMessage: 'provider unavailable',
      html: '', javascript: '', css: '', pages: [],
    });
    render(<MemoryRouter><Preview /></MemoryRouter>);
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'provider unavailable');
  });

  it('keeps the real generation failure visible without reporting success', async () => {
    vi.mocked(workspaceApi.getLatestPrototypePreview).mockResolvedValue({
      message: 'prototype_preview_not_found',
    });
    vi.mocked(workspaceApi.generatePrototypePreview).mockRejectedValue(new Error('generation rejected'));
    render(<MemoryRouter><Preview /></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button', { name: /一键编译生成交互式原型/ }));
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'generation rejected');
    await waitFor(() => expect(screen.getByText('generation rejected', { selector: 'div.p-4' })).toBeDefined());
    expect(screen.queryByText('生成成功')).toBeNull();
  });
});
