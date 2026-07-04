import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor, act } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { Preview } from '../pages/Preview';
import { workspaceApi } from '../lib/api';

// Mock sub-components
vi.mock('../components/shared/ChoiceGroupPreviewModal', () => ({
  ChoiceGroupPreviewModal: () => <div data-testid="choice-group-preview-modal" />
}));

vi.mock('../store/useWorkspaceStore', () => {
  const mockState = {
    setSelectedObject: vi.fn(),
    setHighlightTarget: vi.fn(),
    highlightTarget: null,
    ir: {
      projectId: 'proj_123',
      projectName: 'Test Space',
      actors: [{ actorId: 1, actorName: 'Actor' }],
      features: [{ featureId: 1, featureName: 'Feature', scope: 'current' }],
      flows: [{ flowId: 1, flowName: 'Flow' }],
      businessObjects: [{ businessObjectId: 1, businessObjectName: 'BO' }],
      findings: [],
    },
    auditLogs: [],
    selectedObject: null,
    activeShadowDraft: null,
    getActiveShadowDraft: vi.fn().mockResolvedValue(null),
    prepareShadowDraft: vi.fn().mockResolvedValue(null),
    getShadowDraft: vi.fn().mockResolvedValue(null),
    discardShadowDraft: vi.fn().mockResolvedValue(null),
    commitShadowDraft: vi.fn().mockResolvedValue(null),
    regenerateShadowDraft: vi.fn().mockResolvedValue(null),
    triggerGateCheck: vi.fn((gate, action) => action()),
  };

  const mockUseStore = vi.fn((selector) => {
    if (typeof selector === 'function') {
      return selector(mockState);
    }
    return mockState;
  });

  Object.assign(mockUseStore, {
    setState: vi.fn(),
  });

  return {
    useWorkspaceStore: mockUseStore,
    selectSelectedObject: () => null,
  };
});

vi.mock('../lib/api', () => ({
  workspaceApi: {
    exportMarkdown: vi.fn(),
    exportJson: vi.fn(),
    exportSplSyntax: vi.fn(),
    exportSplSemantic: vi.fn(),
    getLatestPrototypePreview: vi.fn().mockResolvedValue({
      projectId: 'proj_123',
      projectName: 'Test Space',
      rolePrototypePages: [],
    }),
  },
}));

describe('SPL Export Frontend UI Preview Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders SPL export buttons in the menu and triggers syntax download', async () => {
    render(
      <MemoryRouter>
        <Preview />
      </MemoryRouter>
    );

    // 1. Click "导出资产" to open dropdown menu after loading completes
    const exportBtn = await screen.findByText('导出资产');
    act(() => {
      fireEvent.click(exportBtn);
    });

    // 2. Assert syntax and semantic export items are in the DOM
    expect(screen.getByText('导出 SPL 语法规格')).toBeDefined();
    expect(screen.getByText('导出 SPL 语义规格')).toBeDefined();

    // Mock API resolutions
    vi.mocked(workspaceApi.exportSplSyntax).mockResolvedValue('Syntax SPL text');

    // Mock global downloadFile or URL creation to verify downloads
    const originalCreateObjectURL = window.URL.createObjectURL;
    const originalRevokeObjectURL = window.URL.revokeObjectURL;
    window.URL.createObjectURL = vi.fn(() => 'mock-blob-url');
    window.URL.revokeObjectURL = vi.fn();

    // 3. Trigger Syntax Export Click
    act(() => {
      fireEvent.click(screen.getByText('导出 SPL 语法规格'));
    });
    await waitFor(() => {
      expect(workspaceApi.exportSplSyntax).toHaveBeenCalledWith('proj_123');
    });

    // Restore original window methods
    window.URL.createObjectURL = originalCreateObjectURL;
    window.URL.revokeObjectURL = originalRevokeObjectURL;
  });

  it('renders SPL export buttons in the menu and triggers semantic download', async () => {
    render(
      <MemoryRouter>
        <Preview />
      </MemoryRouter>
    );

    // 1. Click "导出资产" to open dropdown menu after loading completes
    const exportBtn = await screen.findByText('导出资产');
    act(() => {
      fireEvent.click(exportBtn);
    });

    // 2. Assert syntax and semantic export items are in the DOM
    expect(screen.getByText('导出 SPL 语法规格')).toBeDefined();
    expect(screen.getByText('导出 SPL 语义规格')).toBeDefined();

    // Mock API resolutions
    vi.mocked(workspaceApi.exportSplSemantic).mockResolvedValue('Semantic SPL text');

    // Mock global downloadFile or URL creation to verify downloads
    const originalCreateObjectURL = window.URL.createObjectURL;
    const originalRevokeObjectURL = window.URL.revokeObjectURL;
    window.URL.createObjectURL = vi.fn(() => 'mock-blob-url');
    window.URL.revokeObjectURL = vi.fn();

    // 3. Trigger Semantic Export Click
    act(() => {
      fireEvent.click(screen.getByText('导出 SPL 语义规格'));
    });
    await waitFor(() => {
      expect(workspaceApi.exportSplSemantic).toHaveBeenCalledWith('proj_123');
    });

    // Restore original window methods
    window.URL.createObjectURL = originalCreateObjectURL;
    window.URL.revokeObjectURL = originalRevokeObjectURL;
  });

  it('displays correct error toast message on API failure', async () => {
    render(
      <MemoryRouter>
        <Preview />
      </MemoryRouter>
    );

    // Open menu after loading completes
    const exportBtn = await screen.findByText('导出资产');
    act(() => {
      fireEvent.click(exportBtn);
    });

    // Mock API failure with 'spl_export_skill_unavailable'
    vi.mocked(workspaceApi.exportSplSyntax).mockRejectedValue(new Error('spl_export_skill_unavailable'));

    // Trigger Syntax Export Click
    act(() => {
      fireEvent.click(screen.getByText('导出 SPL 语法规格'));
    });

    // Verify correct toast alert message is shown in the UI
    await waitFor(() => {
      expect(screen.getByText('当前 SPL 导出能力不可用，可先导出 Markdown 需求规格说明书。')).toBeDefined();
    });
  });

  it('displays correct error toast message when semantic export is disabled', async () => {
    render(
      <MemoryRouter>
        <Preview />
      </MemoryRouter>
    );

    // Open menu after loading completes
    const exportBtn = await screen.findByText('导出资产');
    act(() => {
      fireEvent.click(exportBtn);
    });

    // Mock API failure with 'spl_export_semantic_disabled'
    vi.mocked(workspaceApi.exportSplSemantic).mockRejectedValue(new Error('spl_export_semantic_disabled'));

    // Trigger Semantic Export Click
    act(() => {
      fireEvent.click(screen.getByText('导出 SPL 语义规格'));
    });

    // Verify correct toast alert message is shown in the UI
    await waitFor(() => {
      expect(screen.getByText('SPL 语义导出功能已被禁用，请先导出 SPL 语法规格。')).toBeDefined();
    });
  });
});
