import { beforeEach, describe, expect, it, vi } from 'vitest';
import { workspaceApi } from '../lib/api';
import { useWorkspaceStore } from '../store/useWorkspaceStore';

vi.mock('../lib/api', () => ({
  workspaceApi: {
    createBlankProject: vi.fn(),
    createKnowledgeWorkspace: vi.fn(),
    getKnowledgeConfig: vi.fn().mockResolvedValue({ enabled: true }),
    getById: vi.fn(),
    listFindings: vi.fn(),
    listChoiceGroups: vi.fn().mockResolvedValue([]),
    listAuditLogs: vi.fn().mockResolvedValue([]),
    getStageProgress: vi.fn().mockResolvedValue({ stages: [] }),
  },
}));

const nextAction = (projectId: string) => ({
  findingId: `what:GENERATE_SCENARIOS:${projectId}`,
  type: 'next_suggestion',
  stage: 'what',
  code: 'GENERATE_SCENARIOS',
  severity: 'info',
  title: '生成典型场景',
  description: '继续补充典型场景',
  blockingScope: 'none',
  metadata: { action: { kind: 'create_draft', draft_type: 'scenario_generation' } },
});

describe('project creation hydration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(workspaceApi.getKnowledgeConfig).mockResolvedValue({ enabled: true } as any);
    vi.mocked(workspaceApi.listChoiceGroups).mockResolvedValue([] as any);
    vi.mocked(workspaceApi.listAuditLogs).mockResolvedValue([] as any);
    vi.mocked(workspaceApi.getStageProgress).mockResolvedValue({ stages: [] } as any);
    vi.mocked(workspaceApi.getById).mockImplementation(async (projectId) => ({
      projectId,
      projectName: projectId,
      statusCode: 'in_progress',
      status: '进行中',
      issueCount: 0,
      unlockedStages: 'what',
      actors: [{ actorId: 1, name: '用户' }],
      features: [{ featureId: 1, featureName: '功能' }],
      flows: [],
      businessObjects: [],
    } as any));
    vi.mocked(workspaceApi.listFindings).mockImplementation(async (projectId, params) => ({
      findings: params.view === 'next_action' ? [nextAction(projectId)] : [],
    } as any));
    useWorkspaceStore.setState({
      sessionVersion: 0,
      ir: null,
      creationWorkspaceId: null,
      creationDocuments: [],
      knowledgeBaseEnabled: true,
      backendFindings: [],
      backendFindingsLoaded: false,
      findingsByView: { issues: [], next_action: [], gate: [], health: [] },
      stageProgress: null,
      error: null,
      isLoading: false,
    });
  });

  it('uses a fresh knowledge workspace for each consecutive project and hydrates suggestions immediately', async () => {
    vi.mocked(workspaceApi.createKnowledgeWorkspace)
      .mockResolvedValueOnce({ public_id: 'workspace-1' } as any)
      .mockResolvedValueOnce({ public_id: 'workspace-2' } as any);
    vi.mocked(workspaceApi.createBlankProject)
      .mockResolvedValueOnce({ project_id: 'project-1' } as any)
      .mockResolvedValueOnce({ project_id: 'project-2' } as any);

    await useWorkspaceStore.getState().initCreationWorkspace();
    expect(useWorkspaceStore.getState().creationWorkspaceId).toBe('workspace-1');
    expect(await useWorkspaceStore.getState().createBlankWorkspace('项目一', '', '需求一')).toBe('project-1');
    expect(useWorkspaceStore.getState().creationWorkspaceId).toBeNull();
    expect(useWorkspaceStore.getState().findingsByView.next_action[0].code).toBe('GENERATE_SCENARIOS');

    await useWorkspaceStore.getState().initCreationWorkspace();
    expect(useWorkspaceStore.getState().creationWorkspaceId).toBe('workspace-2');
    expect(await useWorkspaceStore.getState().createBlankWorkspace('项目二', '', '需求二')).toBe('project-2');

    expect(workspaceApi.createBlankProject).toHaveBeenNthCalledWith(1, expect.objectContaining({ knowledge_workspace_id: 'workspace-1' }));
    expect(workspaceApi.createBlankProject).toHaveBeenNthCalledWith(2, expect.objectContaining({ knowledge_workspace_id: 'workspace-2' }));
    expect(useWorkspaceStore.getState().ir?.projectId).toBe('project-2');
    expect(useWorkspaceStore.getState().backendFindingsLoaded).toBe(true);
    expect(useWorkspaceStore.getState().findingsByView.next_action[0].findingId).toContain('project-2');
  });

  it('returns no project id and keeps the current project when creation fails', async () => {
    useWorkspaceStore.setState({
      ir: { projectId: 'existing-project', projectName: 'Existing' } as any,
      creationWorkspaceId: 'inactive-workspace',
    });
    vi.mocked(workspaceApi.createBlankProject).mockRejectedValueOnce(new Error('workspace_inactive'));

    const result = await useWorkspaceStore.getState().createBlankWorkspace('失败项目', '', '需求');

    expect(result).toBeNull();
    expect(useWorkspaceStore.getState().ir?.projectId).toBe('existing-project');
    expect(workspaceApi.getById).not.toHaveBeenCalled();
  });
});
