import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useTranslation } from 'react-i18next';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { Preview } from '../pages/Preview';

const mocks = vi.hoisted(() => ({
  state: {} as any,
}));

vi.mock('../store/useWorkspaceStore', () => {
  const useWorkspaceStore = vi.fn((selector) =>
    typeof selector === 'function' ? selector(mocks.state) : mocks.state
  );
  Object.assign(useWorkspaceStore, { setState: vi.fn() });
  return { useWorkspaceStore, selectSelectedObject: () => null };
});

describe('shadow preview progress locale', () => {
  beforeEach(async () => {
    await useTranslation().i18n.changeLanguage('en-US');
    mocks.state = {
      setSelectedObject: vi.fn(),
      setHighlightTarget: vi.fn(),
      highlightTarget: null,
      ir: {
        projectId: 'project-1',
        projectName: 'Shadow project',
        actors: [],
        features: [],
        flows: [],
        businessObjects: [],
        findings: [],
      },
      auditLogs: [],
      selectedObject: null,
      activeShadowDraft: null,
      getActiveShadowDraft: vi.fn().mockResolvedValue(null),
      prepareShadowDraft: vi.fn(() => {
        mocks.state.activeShadowDraft = {
          source: 'shadow_project',
          status: 'generating',
          draftId: 'draft-1',
          unreadyGates: ['what', 'how', 'scope'],
          currentProgress: 15,
          currentStepLabel: 'preview.full.progressWhat',
        };
        return Promise.resolve(mocks.state.activeShadowDraft);
      }),
      getShadowDraft: vi.fn().mockResolvedValue(mocks.state.activeShadowDraft),
      discardShadowDraft: vi.fn(),
      commitShadowDraft: vi.fn(),
      regenerateShadowDraft: vi.fn(),
      triggerGateCheck: vi.fn((_gate, action) => action()),
    };
  });

  it('translates backend progress keys using the selected UI language', async () => {
    render(<MemoryRouter><Preview /></MemoryRouter>);

    fireEvent.click(await screen.findByText('Generate and Preview Shadow Prototype'));

    expect(await screen.findByText(/AI is completing What-stage assets/)).toBeDefined();
    await waitFor(() => expect(mocks.state.prepareShadowDraft).toHaveBeenCalledOnce());
  });
});
