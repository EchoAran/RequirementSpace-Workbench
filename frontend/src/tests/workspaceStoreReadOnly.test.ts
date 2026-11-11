import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useWorkspaceStore } from '../store/useWorkspaceStore';

vi.mock('../lib/api', () => ({
  workspaceApi: {
    getById: vi.fn(),
    listBranches: vi.fn(),
    listCommits: vi.fn(),
    deletePerceptionSlot: vi.fn(),
    acceptChoice: vi.fn(),
    rejectChoice: vi.fn(),
    discardChoiceGroup: vi.fn(),
    resolveIssue: vi.fn(),
    confirmRepairDraft: vi.fn(),
    updateNodeConfirmationStatus: vi.fn(),
    updateFindingStatus: vi.fn(),
    commitShadowDraft: vi.fn(),
    createActor: vi.fn(),
    confirmActorGenerationDraft: vi.fn(),
    confirmFeatureGenerationDraft: vi.fn(),
    confirmFlowGenerationDraft: vi.fn(),
    confirmScenarioGenerationDraft: vi.fn(),
    confirmAcceptanceCriteriaGenerationDraft: vi.fn(),
    confirmScopeGenerationDraft: vi.fn(),
    confirmSlotFillingDraft: vi.fn(),
    skipKano: vi.fn(),
    resetKano: vi.fn(),
    rediagnoseNextSuggestion: vi.fn(),
    getRediagnoseStatus: vi.fn(),
    createSlotFillingDraft: vi.fn(),
    createGenerationChoiceGroup: vi.fn(),
    stageTransition: vi.fn(),
    discardRepairDraft: vi.fn(),
    regenerateRepairDraft: vi.fn(),
  },
  setRequestBranch: vi.fn(),
}));

import { workspaceApi } from '../lib/api';

describe('WorkspaceStore Read-Only Barrier & Fail-Closed Logic', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useWorkspaceStore.setState({
      sessionVersion: 1,
      ir: { projectId: 'project-999', projectName: 'Test', userRequirements: '', actors: [], features: [] } as any,
      branches: [],
      currentBranch: null,
      branchLoading: false,
      error: null,
      findingsByView: { issues: [{ findingId: 'issue-1', code: 'WHAT_MISSING', stage: 'what' }], next_action: [], gate: [], health: [] } as any,
    });
  });

  describe('workspaceCanWrite fail-closed rules', () => {
    it('returns false when no project is loaded', () => {
      useWorkspaceStore.setState({ ir: null });
      expect(useWorkspaceStore.getState().workspaceCanWrite()).toBe(false);
    });

    it('returns false when branchLoading is true', () => {
      useWorkspaceStore.setState({ branchLoading: true });
      expect(useWorkspaceStore.getState().workspaceCanWrite()).toBe(false);
    });

    it('returns false when currentBranch is null (not yet resolved)', () => {
      useWorkspaceStore.setState({ currentBranch: null, branchLoading: false });
      expect(useWorkspaceStore.getState().workspaceCanWrite()).toBe(false);
    });

    it('returns false for protected branch or main branch', () => {
      useWorkspaceStore.setState({
        currentBranch: { id: 1, name: 'main', is_protected: true, is_default: true, permissions: { can_write: true } } as any,
      });
      expect(useWorkspaceStore.getState().workspaceCanWrite()).toBe(false);

      useWorkspaceStore.setState({
        currentBranch: { id: 2, name: 'release/v1', is_protected: true, is_default: false, permissions: { can_write: true } } as any,
      });
      expect(useWorkspaceStore.getState().workspaceCanWrite()).toBe(false);
    });

    it('returns false when branch permission can_write is false', () => {
      useWorkspaceStore.setState({
        currentBranch: { id: 3, name: 'feature/read-only', is_protected: false, is_default: false, permissions: { can_write: false } } as any,
      });
      expect(useWorkspaceStore.getState().workspaceCanWrite()).toBe(false);
    });

    it('returns true ONLY when un-protected feature branch has can_write permission', () => {
      useWorkspaceStore.setState({
        currentBranch: { id: 4, name: 'feature/dev', is_protected: false, is_default: false, permissions: { can_write: true } } as any,
      });
      expect(useWorkspaceStore.getState().workspaceCanWrite()).toBe(true);
    });
  });

  describe('mutation actions barrier on read-only / main branch', () => {
    beforeEach(() => {
      // Set to read-only state (main branch)
      useWorkspaceStore.setState({
        currentBranch: { id: 1, name: 'main', is_protected: true, is_default: true, permissions: { can_write: false } } as any,
        error: null,
      });
    });

    it('clearPerceptionSlot is blocked', async () => {
      await useWorkspaceStore.getState().clearPerceptionSlot();
      expect(workspaceApi.deletePerceptionSlot).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('acceptChoice is blocked', async () => {
      await useWorkspaceStore.getState().acceptChoice('123');
      expect(workspaceApi.acceptChoice).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('rejectChoice is blocked', async () => {
      await useWorkspaceStore.getState().rejectChoice('123');
      expect(workspaceApi.rejectChoice).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('discardChoiceGroup is blocked', async () => {
      await useWorkspaceStore.getState().discardChoiceGroup(1);
      expect(workspaceApi.discardChoiceGroup).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('executeFindingIssueResolution is blocked', async () => {
      const res = await useWorkspaceStore.getState().executeFindingIssueResolution('issue-1');
      expect(res).toBeNull();
      expect(workspaceApi.resolveIssue).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('confirmRepairDraft is blocked', async () => {
      const res = await useWorkspaceStore.getState().confirmRepairDraft('draft-1');
      expect(res).toBeNull();
      expect(workspaceApi.confirmRepairDraft).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('setNodeStatus is blocked', async () => {
      await useWorkspaceStore.getState().setNodeStatus('1', 'actor', 'confirmed' as any);
      expect(workspaceApi.updateNodeConfirmationStatus).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('updateIssueAttributes is blocked', async () => {
      await useWorkspaceStore.getState().updateIssueAttributes('issue-1', { status: 'resolved' });
      expect(workspaceApi.updateFindingStatus).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('commitShadowDraft is blocked', async () => {
      await useWorkspaceStore.getState().commitShadowDraft('shadow-1');
      expect(workspaceApi.commitShadowDraft).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('confirmActors is blocked', async () => {
      useWorkspaceStore.setState({ activeDraft: { draftId: 'd-1' } as any });
      await useWorkspaceStore.getState().confirmActors();
      expect(workspaceApi.confirmActorGenerationDraft).not.toHaveBeenCalled();
      expect(workspaceApi.confirmSlotFillingDraft).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('confirmFeatures is blocked', async () => {
      useWorkspaceStore.setState({ activeDraft: { draftId: 'd-2' } as any });
      await useWorkspaceStore.getState().confirmFeatures();
      expect(workspaceApi.confirmFeatureGenerationDraft).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('confirmFlowDraft is blocked', async () => {
      useWorkspaceStore.setState({ activeDraft: { draftId: 'd-3' } as any });
      await useWorkspaceStore.getState().confirmFlowDraft();
      expect(workspaceApi.confirmFlowGenerationDraft).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('confirmScenarios is blocked', async () => {
      useWorkspaceStore.setState({ activeDraft: { draftId: 'd-4' } as any });
      await useWorkspaceStore.getState().confirmScenarios(false);
      expect(workspaceApi.confirmScenarioGenerationDraft).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('confirmAcceptanceCriteria is blocked', async () => {
      useWorkspaceStore.setState({ activeDraft: { draftId: 'd-5' } as any });
      await useWorkspaceStore.getState().confirmAcceptanceCriteria();
      expect(workspaceApi.confirmAcceptanceCriteriaGenerationDraft).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('confirmScope is blocked', async () => {
      useWorkspaceStore.setState({ activeDraft: { draft_id: 'd-6' } as any });
      await useWorkspaceStore.getState().confirmScope();
      expect(workspaceApi.confirmScopeGenerationDraft).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('skipKano is blocked', async () => {
      await useWorkspaceStore.getState().skipKano();
      expect(workspaceApi.skipKano).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('resetKano is blocked', async () => {
      await useWorkspaceStore.getState().resetKano();
      expect(workspaceApi.resetKano).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('runDiagnosis is blocked', async () => {
      await useWorkspaceStore.getState().runDiagnosis('what');
      expect(workspaceApi.rediagnoseNextSuggestion).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('expandSlot is blocked', async () => {
      await useWorkspaceStore.getState().expandSlot('1');
      expect(workspaceApi.createSlotFillingDraft).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('createGenerationChoiceGroup is blocked', async () => {
      const res = await useWorkspaceStore.getState().createGenerationChoiceGroup({ projectId: 'project-999', generationType: 'rule' });
      expect(res).toBeNull();
      expect(workspaceApi.createGenerationChoiceGroup).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('requestStageTransition is blocked', async () => {
      await useWorkspaceStore.getState().requestStageTransition('enter_how');
      expect(workspaceApi.stageTransition).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('discardRepairDraft is blocked', async () => {
      await useWorkspaceStore.getState().discardRepairDraft('draft-1');
      expect(workspaceApi.discardRepairDraft).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });

    it('regenerateRepairDraft is blocked', async () => {
      await useWorkspaceStore.getState().regenerateRepairDraft('draft-1');
      expect(workspaceApi.regenerateRepairDraft).not.toHaveBeenCalled();
      expect(useWorkspaceStore.getState().error).toBe('versionControl.readOnlyToast');
    });
  });
});
