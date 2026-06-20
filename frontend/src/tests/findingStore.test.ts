import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getFriendlyErrorMessage, getFindingCapability, useWorkspaceStore } from '../store/useWorkspaceStore';
import { workspaceApi } from '../lib/api';
import { Finding } from '../core/schema';

// Mock workspaceApi
vi.mock('../lib/api', () => ({
  workspaceApi: {
    listFindings: vi.fn(),
    updateFindingStatus: vi.fn(),
    rediagnoseNextSuggestion: vi.fn(),
    getNextSuggestion: vi.fn(),
    list: vi.fn().mockResolvedValue([]),
    getById: vi.fn(),
    listChoiceGroups: vi.fn().mockResolvedValue([]),
    createGenerationChoiceGroup: vi.fn(),
    discardChoiceGroup: vi.fn(),
    resolveIssue: vi.fn(),
  }
}));

describe('useWorkspaceStore - Finding Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Clear workspace store state
    useWorkspaceStore.setState({
      backendFindings: [],
      backendFindingsLoaded: false,
      findingsByView: {
        issues: [],
        next_action: [],
        gate: [],
        health: []
      },
      ir: null
    });
  });

  it('1. loadBackendFindingsAndViews - Loads canonical findings from API', async () => {
    const mockFindingsIssues: Finding[] = [
      {
        findingId: 'what:LEAF_FEATURE_WITHOUT_ACTOR:feature:10',
        type: 'issue',
        stage: 'what',
        code: 'LEAF_FEATURE_WITHOUT_ACTOR',
        severity: 'blocking',
        title: 'Feature lacks actor',
        description: 'Leaf feature lacks actor binding',
        target: { targetType: 'feature', targetId: 10 },
        blockingScope: 'stage_transition',
        actionCode: 'open_panel',
        metadata: {}
      }
    ];
    const mockFindingsHealth: Finding[] = [
      {
        findingId: 'what:ACTOR_WITHOUT_FEATURE:actor:5',
        type: 'quality_hint',
        stage: 'what',
        code: 'ACTOR_WITHOUT_FEATURE',
        severity: 'warning',
        title: 'Actor lacks feature',
        description: 'Actor has no associated feature',
        target: { targetType: 'actor', targetId: 5 },
        blockingScope: 'none',
        actionCode: 'open_panel',
        metadata: {}
      }
    ];

    vi.mocked(workspaceApi.listFindings).mockImplementation(async (projectId, params) => {
      if (params.view === 'issues') return { findings: mockFindingsIssues } as any;
      if (params.view === 'health') return { findings: mockFindingsHealth } as any;
      return { findings: [] } as any;
    });

    // Mock getById to return project metadata
    vi.mocked(workspaceApi.getById).mockResolvedValueOnce({
      projectId: 'project-123',
      projectName: 'Test Space',
      unlockedStages: 'what',
      actors: [],
      features: [],
      flows: []
    } as any);

    // Call openWorkspace (which triggers loadBackendFindingsAndViews internally)
    await useWorkspaceStore.getState().openWorkspace('project-123');

    // Verify findings are set
    const state = useWorkspaceStore.getState();
    expect(state.backendFindings.length).toBe(2);
    expect(state.findingsByView.issues).toEqual(mockFindingsIssues);
    expect(state.findingsByView.health).toEqual(mockFindingsHealth);

    expect(state.ir?.findings).toEqual(mockFindingsIssues);
  });

  it('2. updateIssueAttributes - Delegates status update to updateFindingStatus and refreshes state', async () => {
    const mockIssues: Finding[] = [
      {
        findingId: 'what:LEAF_FEATURE_WITHOUT_ACTOR:feature:10',
        type: 'issue',
        stage: 'what',
        code: 'LEAF_FEATURE_WITHOUT_ACTOR',
        severity: 'blocking',
        title: 'Feature lacks actor',
        description: 'Leaf feature lacks actor binding',
        target: { targetType: 'feature', targetId: 10 },
        blockingScope: 'stage_transition',
        actionCode: 'open_panel',
        metadata: {}
      }
    ];
    
    // Set initial store state (with ir.projectId seeded)
    useWorkspaceStore.setState({
      ir: { projectId: 'project-123' } as any,
      backendFindings: mockIssues,
      findingsByView: {
        issues: mockIssues,
        next_action: [],
        gate: [],
        health: []
      }
    });

    vi.mocked(workspaceApi.updateFindingStatus).mockResolvedValueOnce({
      projectId: 'project-123',
      findingId: 'what:LEAF_FEATURE_WITHOUT_ACTOR:feature:10',
      status: 'ignored'
    } as any);

    vi.mocked(workspaceApi.listFindings).mockResolvedValue({ findings: [] } as any);

    // Call updateIssueAttributes (which delegates to updateFindingStatus)
    await useWorkspaceStore.getState().updateIssueAttributes('what:LEAF_FEATURE_WITHOUT_ACTOR:feature:10', { status: 'ignored' });

    // Verify updateFindingStatus called correctly
    expect(workspaceApi.updateFindingStatus).toHaveBeenCalledWith('project-123', 'what:LEAF_FEATURE_WITHOUT_ACTOR:feature:10', 'ignored');
  });

  it('3. triggerGateCheck - Correctly unpacks listFindings response and handles gate activation', async () => {
    const mockGateFindings: Finding[] = [
      {
        findingId: 'what:FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO:aggregate',
        type: 'gate_condition',
        stage: 'what',
        code: 'FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO',
        severity: 'blocking',
        title: '缺少典型场景',
        description: '角色和功能未关联典型场景',
        blockingScope: 'stage_transition',
        metadata: {
          missing_pairs: [{ feature_id: 1, actor_id: 2 }]
        }
      }
    ];

    useWorkspaceStore.setState({
      ir: { projectId: 'project-123' } as any,
      activeGateCheck: null,
      snoozedGateFindingIds: {}
    });

    // Case 1: listFindings returns `{ findings: [...] }`
    vi.mocked(workspaceApi.listFindings).mockResolvedValueOnce({ findings: mockGateFindings } as any);

    const onPass = vi.fn();
    const onCancel = vi.fn();

    await useWorkspaceStore.getState().triggerGateCheck('enter_how', onPass, onCancel);

    // Verify activeGateCheck is populated
    let state = useWorkspaceStore.getState();
    expect(state.activeGateCheck).not.toBeNull();
    expect(state.activeGateCheck?.findings).toEqual(mockGateFindings);
    expect(onPass).not.toHaveBeenCalled();

    // Case 2: listFindings returns `[]` (compatible fallback)
    useWorkspaceStore.setState({ activeGateCheck: null });
    vi.mocked(workspaceApi.listFindings).mockResolvedValueOnce([] as any);

    const onPass2 = vi.fn();
    await useWorkspaceStore.getState().triggerGateCheck('enter_how', onPass2);

    state = useWorkspaceStore.getState();
    expect(state.activeGateCheck).toBeNull();
    expect(onPass2).toHaveBeenCalledTimes(1);
  });

  it('4. startFindingSuggestion - executes the action embedded in Finding metadata', async () => {
    const finding: Finding = {
      findingId: 'what:BIND_ACTORS_TO_FEATURE:suggest',
      type: 'next_suggestion',
      stage: 'what',
      code: 'BIND_ACTORS_TO_FEATURE',
      severity: 'info',
      title: '绑定角色',
      description: '绑定角色',
      target: { targetType: 'feature', targetId: 42 },
      blockingScope: 'none',
      metadata: {
        target: { type: 'feature', id: 42 },
        action: {
          kind: 'open_panel',
          panel: 'feature',
          payload: { feature_id: 42 },
        },
      }
    };

    useWorkspaceStore.setState({
      ir: {
        projectId: 'project-123',
        features: [{ featureId: 42, featureName: 'Feature 42' }],
      } as any,
      selectedObject: null,
    });

    await useWorkspaceStore.getState().startFindingSuggestion(finding);

    expect(useWorkspaceStore.getState().selectedObject?.featureId).toBe(42);
  });

  it('5. runDiagnosis - Performs rediagnosis, updates workspace state, and refreshes findings', async () => {
    useWorkspaceStore.setState({
      ir: { projectId: 'project-123' } as any,
      activePage: '/what',
      isDiagnosing: false,
      findingsByView: {
        issues: [],
        next_action: [],
        gate: [],
        health: []
      }
    });

    const mockRediagnoseRes = {
      project_id: 'project-123',
      stage: 'what',
      suggestion: {
        code: 'GENERATE_SCENARIOS',
        title: '生成典型场景',
        description: '生成典型场景',
        status: 'ready',
        action: { kind: 'create_draft' }
      }
    };

    const rediagnoseSpy = vi.spyOn(workspaceApi, 'rediagnoseNextSuggestion').mockResolvedValueOnce(mockRediagnoseRes as any);
    const refreshSpy = vi.spyOn(useWorkspaceStore.getState(), 'refreshWorkspace').mockImplementationOnce(async () => {
      // Mock refreshWorkspace behavior: load new next_action finding
      useWorkspaceStore.setState({
        findingsByView: {
          issues: [],
          next_action: [
            {
              findingId: 'what:GENERATE_SCENARIOS:suggest',
              type: 'next_suggestion',
              stage: 'what',
              code: 'GENERATE_SCENARIOS',
              severity: 'info',
              title: '生成典型场景',
              description: '生成典型场景',
              blockingScope: 'none',
              metadata: {
                action: { kind: 'create_draft' }
              }
            }
          ],
          gate: [],
          health: []
        }
      });
    });

    await useWorkspaceStore.getState().runDiagnosis();

    expect(rediagnoseSpy).toHaveBeenCalledWith('project-123', 'what');
    expect(refreshSpy).toHaveBeenCalledTimes(1);
    
    const state = useWorkspaceStore.getState();
    expect(state.findingsByView.next_action.length).toBe(1);
    expect(state.findingsByView.next_action[0].code).toBe('GENERATE_SCENARIOS');
  });

  it('6. startFindingSuggestion - handles kind=create_draft actions and delegates to store generators', async () => {
    useWorkspaceStore.setState({
      ir: { projectId: 'project-123' } as any
    });

    const store = useWorkspaceStore.getState();
    const generateActorsSpy = vi.spyOn(store, 'generateActors').mockResolvedValue(undefined);
    const generateFeaturesSpy = vi.spyOn(store, 'generateFeatures').mockResolvedValue(undefined);
    const generateScenariosSpy = vi.spyOn(store, 'generateScenarios').mockResolvedValue(undefined);
    const generateACSRpy = vi.spyOn(store, 'generateAcceptanceCriteria').mockResolvedValue(undefined);
    const generateFlowsAndObjectsSpy = vi.spyOn(store, 'generateFlowsAndObjects').mockResolvedValue(undefined);
    const generateScopeSpy = vi.spyOn(store, 'generateScope').mockResolvedValue(undefined);
    vi.spyOn(store, 'refreshWorkspace').mockResolvedValue(undefined);

    const finding: Finding = {
      findingId: 'what:GENERATE_SCENARIOS:suggest',
      type: 'next_suggestion',
      stage: 'what',
      code: 'GENERATE_SCENARIOS',
      severity: 'info',
      title: '生成场景',
      description: '生成典型场景',
      blockingScope: 'none',
      metadata: {},
    };

    // Case GENERATE_SCENARIOS
    finding.code = 'GENERATE_SCENARIOS';
    finding.metadata = { action: { kind: 'create_draft', draft_type: 'scenario_generation' } };
    await useWorkspaceStore.getState().startFindingSuggestion(finding);
    expect(generateScenariosSpy).toHaveBeenCalledWith(undefined, false);

    // Case GENERATE_ACTORS
    finding.code = 'GENERATE_ACTORS';
    finding.metadata = { action: { kind: 'create_draft', draft_type: 'actor_generation' } };
    await useWorkspaceStore.getState().startFindingSuggestion(finding);
    expect(generateActorsSpy).toHaveBeenCalledWith(false);

    // Case GENERATE_FEATURES
    finding.code = 'GENERATE_FEATURES';
    finding.metadata = { action: { kind: 'create_draft', draft_type: 'feature_generation' } };
    await useWorkspaceStore.getState().startFindingSuggestion(finding);
    expect(generateFeaturesSpy).toHaveBeenCalledWith(false);

    // Case GENERATE_ACCEPTANCE_CRITERIA
    finding.code = 'GENERATE_ACCEPTANCE_CRITERIA';
    finding.metadata = { action: { kind: 'create_draft', draft_type: 'acceptance_criteria_generation' } };
    await useWorkspaceStore.getState().startFindingSuggestion(finding);
    expect(generateACSRpy).toHaveBeenCalledWith(undefined, false);

    // Case GENERATE_FLOWS_AND_BUSINESS_OBJECTS
    finding.code = 'GENERATE_FLOWS_AND_BUSINESS_OBJECTS';
    finding.metadata = { action: { kind: 'create_draft', draft_type: 'flow_generation' } };
    await useWorkspaceStore.getState().startFindingSuggestion(finding);
    expect(generateFlowsAndObjectsSpy).toHaveBeenCalledWith(false);

    // Case GENERATE_SCOPE
    finding.code = 'GENERATE_SCOPE';
    finding.metadata = { action: { kind: 'create_draft', draft_type: 'scope_generation' } };
    await useWorkspaceStore.getState().startFindingSuggestion(finding);
    expect(generateScopeSpy).toHaveBeenCalledWith(false);
  });

  it('7. startFindingSuggestion - handles navigate route actions', async () => {
    useWorkspaceStore.setState({
      ir: { projectId: 'project-123' } as any,
      activePage: '/what'
    });

    const store = useWorkspaceStore.getState();
    vi.spyOn(store, 'refreshWorkspace').mockResolvedValue(undefined);

    const finding: Finding = {
      findingId: 'what:ENTER_HOW:suggest',
      type: 'next_suggestion',
      stage: 'what',
      code: 'ENTER_HOW',
      severity: 'info',
      title: '进入下一阶段',
      description: '进入下一阶段',
      blockingScope: 'none',
      metadata: { action: { kind: 'navigate', route: '/projects/project-123/how' } },
    };

    await useWorkspaceStore.getState().startFindingSuggestion(finding);

    expect(useWorkspaceStore.getState().activePage).toBe('/flow');
  });

  it('8. startFindingSuggestion - handles wait actions', async () => {
    useWorkspaceStore.setState({
      ir: { projectId: 'project-123' } as any,
      lastActionMessage: null
    });

    const store = useWorkspaceStore.getState();
    vi.spyOn(store, 'refreshWorkspace').mockResolvedValue(undefined);

    const finding: Finding = {
      findingId: 'what:WAIT:suggest',
      type: 'next_suggestion',
      stage: 'what',
      code: 'WAIT',
      severity: 'info',
      title: '等待',
      description: '等待',
      blockingScope: 'none',
      metadata: { action: { kind: 'wait' } },
    };

    await useWorkspaceStore.getState().startFindingSuggestion(finding);

    expect(useWorkspaceStore.getState().lastActionMessage).toBe('后台分析正在运行，请稍后刷新或重新诊断。');
  });

  it('9. startFindingSuggestion - handles retry actions', async () => {
    useWorkspaceStore.setState({
      ir: { projectId: 'project-123' } as any
    });

    const store = useWorkspaceStore.getState();
    vi.spyOn(store, 'refreshWorkspace').mockResolvedValue(undefined);

    const finding: Finding = {
      findingId: 'what:RETRY:suggest',
      type: 'next_suggestion',
      stage: 'what',
      code: 'RETRY',
      severity: 'info',
      title: '重试',
      description: '重试',
      blockingScope: 'none',
      metadata: { action: { kind: 'retry' } },
    };

    const rediagnoseSpy = vi.spyOn(workspaceApi, 'rediagnoseNextSuggestion').mockResolvedValueOnce({} as any);
    const runDiagnosisSpy = vi.spyOn(useWorkspaceStore.getState(), 'runDiagnosis').mockResolvedValueOnce(undefined);

    await useWorkspaceStore.getState().startFindingSuggestion(finding);

    expect(rediagnoseSpy).toHaveBeenCalledWith('project-123', 'what');
    expect(runDiagnosisSpy).toHaveBeenCalledWith('what');
  });

  it('10. executeFindingIssueResolution - handles open_panel and delegates to executeProcessorAction', async () => {
    const issueId = 'issue-123';
    const mockIssue: Finding = {
      findingId: issueId,
      type: 'issue',
      code: 'ISSUE_CODE',
      stage: 'what',
      severity: 'blocking',
      title: 'Issue',
      description: 'Issue',
      target: { targetType: 'feature', targetId: 10 },
      blockingScope: 'stage_transition',
    };

    useWorkspaceStore.setState({
      ir: {
        projectId: 'project-123',
        features: [
          { featureId: 10, featureName: 'Feature 10' }
        ]
      } as any,
      findingsByView: { issues: [mockIssue], next_action: [], gate: [], health: [] },
      selectedObject: null
    });

    const store = useWorkspaceStore.getState();
    vi.spyOn(store, 'refreshWorkspace').mockResolvedValue(undefined);

    vi.spyOn(workspaceApi, 'resolveIssue').mockResolvedValueOnce({
      resolution_type: 'open_panel',
      title: '打开功能面板',
      action: {
        kind: 'open_panel',
        panel: 'feature',
        payload: { feature_id: 10 }
      }
    } as any);

    await useWorkspaceStore.getState().executeFindingIssueResolution(issueId);

    const selected = useWorkspaceStore.getState().selectedObject;
    expect(selected).not.toBeNull();
    expect(selected.featureId).toBe(10);
    expect(selected.kind).toBe('feature');
  });

  it('startFindingSuggestion - handles open_panel actions', async () => {
    useWorkspaceStore.setState({
      ir: {
        projectId: 'project-123',
        features: [
          { featureId: 10, featureName: 'Feature 10' }
        ]
      } as any,
      selectedObject: null
    });

    const store = useWorkspaceStore.getState();
    vi.spyOn(store, 'refreshWorkspace').mockResolvedValue(undefined);

    const finding: Finding = {
      findingId: 'what:BIND_ACTORS_TO_FEATURE:suggest',
      type: 'next_suggestion',
      stage: 'what',
      code: 'BIND_ACTORS_TO_FEATURE',
      severity: 'info',
      title: '建议绑定角色',
      description: '建议绑定角色',
      blockingScope: 'none'
      ,
      metadata: {
        action: {
          kind: 'open_panel',
          panel: 'feature',
          payload: { feature_id: 10 },
        },
      },
    };

    await useWorkspaceStore.getState().startFindingSuggestion(finding);

    const selected = useWorkspaceStore.getState().selectedObject;
    expect(selected).not.toBeNull();
    expect(selected.featureId).toBe(10);
  });

  it('11. executeFindingIssueResolution - handles repair_draft resolution type', async () => {
    const issueId = 'issue-123';
    const mockIssue: Finding = {
      findingId: issueId,
      type: 'issue',
      code: 'ISSUE_CODE',
      stage: 'what',
      severity: 'blocking',
      title: 'Issue',
      description: 'Issue',
      blockingScope: 'stage_transition',
    };

    useWorkspaceStore.setState({
      ir: {
        projectId: 'project-123',
      } as any,
      findingsByView: { issues: [mockIssue], next_action: [], gate: [], health: [] },
      activeDraft: null,
      activeDraftType: null
    });

    const store = useWorkspaceStore.getState();
    vi.spyOn(store, 'refreshWorkspace').mockResolvedValue(undefined);

    const mockDraft = { draft_id: 'draft-999', patch: {} };
    vi.spyOn(workspaceApi, 'resolveIssue').mockResolvedValueOnce({
      resolution_type: 'repair_draft',
      title: '修复草稿标题',
      draft: mockDraft
    } as any);

    await useWorkspaceStore.getState().executeFindingIssueResolution(issueId);

    const state = useWorkspaceStore.getState();
    expect(state.activeDraft).toEqual(mockDraft);
    expect(state.activeDraftType).toBe('repair');
    expect(state.lastActionMessage).toBe('已生成修复建议：修复草稿标题');
  });

  it('12. executeFindingIssueResolution - handles unsupported resolution type', async () => {
    const issueId = 'issue-123';
    const mockIssue: Finding = {
      findingId: issueId,
      type: 'issue',
      code: 'ISSUE_CODE',
      stage: 'what',
      severity: 'blocking',
      title: 'Issue',
      description: 'Issue',
      blockingScope: 'stage_transition',
    };

    useWorkspaceStore.setState({
      ir: {
        projectId: 'project-123',
      } as any,
      findingsByView: { issues: [mockIssue], next_action: [], gate: [], health: [] },
      lastIssueResolution: null
    });

    const store = useWorkspaceStore.getState();
    vi.spyOn(store, 'refreshWorkspace').mockResolvedValue(undefined);

    vi.spyOn(workspaceApi, 'resolveIssue').mockResolvedValueOnce({
      resolution_type: 'unsupported',
      title: '暂不支持自动修复'
    } as any);

    await useWorkspaceStore.getState().executeFindingIssueResolution(issueId);

    const state = useWorkspaceStore.getState();
    expect(state.lastIssueResolution.resolution_type).toBe('unsupported');
    expect(state.lastActionMessage).toBe('暂不支持自动修复');
  });

  it('13. executeFindingIssueResolution - handles issue not found (sets error)', async () => {
    useWorkspaceStore.setState({
      ir: {
        projectId: 'project-123',
      } as any,
      findingsByView: { issues: [], next_action: [], gate: [], health: [] },
      error: null
    });

    await useWorkspaceStore.getState().executeFindingIssueResolution('non-existent-issue');

    const state = useWorkspaceStore.getState();
    expect(state.error).toBe('找不到对应问题，请重新诊断后再试。');
    expect(state.lastActionMessage).toBe('找不到对应问题，请重新诊断后再试。');
  });

  it('14. executeProcessorAction - handles open_panel payload not found fallback to route navigation', async () => {
    useWorkspaceStore.setState({
      ir: {
        projectId: 'project-123',
        features: [] // Empty features -> target not found!
      } as any,
      activePage: '/what'
    });

    const store = useWorkspaceStore.getState();
    vi.spyOn(store, 'refreshWorkspace').mockResolvedValue(undefined);

    const finding: Finding = {
      findingId: 'what:GENERATE_SCENARIOS:suggest',
      type: 'next_suggestion',
      stage: 'what',
      code: 'GENERATE_SCENARIOS',
      severity: 'info',
      title: '生成场景',
      description: '生成典型场景',
      blockingScope: 'none',
      metadata: {
        action: {
          kind: 'open_panel',
          panel: 'feature',
          payload: { feature_id: 9999 },
          route: '/projects/project-123/how',
        },
      },
    };

    await useWorkspaceStore.getState().startFindingSuggestion(finding);

    const state = useWorkspaceStore.getState();
    expect(state.activePage).toBe('/flow');
    expect(state.lastActionMessage).toBe('无法定位目标对象，已导航到对应页面：/flow');
  });

  it('15. executeGateFindingAction - runs via unified resolveIssue API for known gate code', async () => {
    useWorkspaceStore.setState({
      ir: { projectId: 'project-123' } as any
    });

    const store = useWorkspaceStore.getState();
    vi.spyOn(store, 'refreshWorkspace').mockResolvedValue(undefined);

    const resolveSpy = vi.mocked(workspaceApi.resolveIssue).mockResolvedValueOnce({
      resolution_type: 'choice_group',
      title: '选择处理方案',
      issue_code: 'FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO',
      action: { kind: 'open_choice_group', choice_group_id: '99' }
    } as any);

    const finding: Finding = {
      findingId: 'what:FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO:aggregate',
      type: 'gate_condition',
      stage: 'what',
      code: 'FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO',
      severity: 'blocking',
      title: '缺少典型场景',
      description: '缺少典型场景',
      blockingScope: 'stage_transition',
      metadata: {
        missing_pairs: [{ feature_id: 10, actor_id: 20 }]
      }
    };

    await useWorkspaceStore.getState().executeGateFindingAction(finding);

    // Must use the unified resolve API, not hardcoded generator dispatch
    expect(resolveSpy).toHaveBeenCalledWith('project-123', {
      issue_id: 'what:FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO:aggregate',
      issue_code: 'FEATURE_ACTOR_PAIR_WITHOUT_SCENARIO',
      stage: 'what',
      target: { target_type: "feature_actor_pair", target_id: "10:20" },
      metadata: { missing_pairs: [{ feature_id: 10, actor_id: 20 }] },
    });
  });

  it('16. executeGateFindingAction - fails and sets error for unknown gate code', async () => {
    useWorkspaceStore.setState({
      ir: { projectId: 'project-123' } as any,
      error: null
    });

    vi.mocked(workspaceApi.resolveIssue).mockRejectedValueOnce({
      detail: 'unsupported_issue_code',
    });

    const finding: Finding = {
      findingId: 'what:UNKNOWN_GATE_CODE:aggregate',
      type: 'gate_condition',
      stage: 'what',
      code: 'UNKNOWN_GATE_CODE',
      severity: 'blocking',
      title: '未知门禁',
      description: '未知门禁',
      blockingScope: 'stage_transition'
    };

    await expect(useWorkspaceStore.getState().executeGateFindingAction(finding)).rejects.toThrow();

    const state = useWorkspaceStore.getState();
    expect(state.error).toBe('自动处理缺陷失败');
  });

  it('17. createGenerationChoiceGroup - reuses an identical open group without conflict prompt', async () => {
    const existingGroup = {
      id: '88',
      status: 'open',
      generationType: 'scenario',
      target: { generation_mode: 'single', feature_id: 10 },
      choices: []
    } as any;

    useWorkspaceStore.setState({
      ir: { projectId: 'project-123' } as any,
      backendChoiceGroups: { '88': existingGroup },
      pendingGenerationConflict: null,
      activeChoiceGroup: null,
    });

    const group = await useWorkspaceStore.getState().createGenerationChoiceGroup({
      projectId: 'project-123',
      generationType: 'scenario',
      target: { generation_mode: 'single', feature_id: 10 },
      conflictAction: 'generateScenarios',
      conflictArgs: { featureIds: [10] },
    });

    expect(group).toBe(existingGroup);
    expect(workspaceApi.createGenerationChoiceGroup).not.toHaveBeenCalled();
    expect(useWorkspaceStore.getState().pendingGenerationConflict).toBeNull();
    expect(useWorkspaceStore.getState().activeChoiceGroup).toBe(existingGroup);
  });

  it('18. createGenerationChoiceGroup - exposes generation progress while request is pending', async () => {
    let resolveRequest: (value: any) => void = () => {};
    vi.mocked(workspaceApi.createGenerationChoiceGroup).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveRequest = resolve;
      }) as any
    );

    useWorkspaceStore.setState({
      ir: { projectId: 'project-123' } as any,
      backendChoiceGroups: {},
      choiceGroupGenerationProgress: null,
    });

    const pending = useWorkspaceStore.getState().createGenerationChoiceGroup({
      projectId: 'project-123',
      generationType: 'scenario',
      candidateCount: 3,
    });

    expect(useWorkspaceStore.getState().choiceGroupGenerationProgress).toMatchObject({
      totalCandidates: 3,
      completedCandidates: 0,
    });

    resolveRequest({
      id: '99',
      status: 'open',
      generationType: 'scenario',
      successCount: 2,
      choices: []
    });
    await pending;

    expect(useWorkspaceStore.getState().choiceGroupGenerationProgress).toBeNull();
  });

  it('19. getFriendlyErrorMessage - normalizes common LLM provider failures', () => {
    expect(getFriendlyErrorMessage('Request timed out after 100s')).toContain('AI 服务响应超时');
    expect(getFriendlyErrorMessage('429 rate limit exceeded')).toContain('API 配额');
    expect(getFriendlyErrorMessage('401 invalid api key')).toContain('API 密钥');
  });

  it('20. getFindingCapability - uses backend capability when present', () => {
    const finding: Finding = {
      findingId: 'test:1',
      type: 'issue',
      stage: 'what',
      code: 'SCOPE_WITHOUT_REASON',
      severity: 'blocking',
      title: 'Test',
      description: 'Test',
      blockingScope: 'stage_transition',
      capability: { kind: 'ai_repair', action_label: 'AI 修复', enabled: true },
    };
    const cap = getFindingCapability(finding);
    expect(cap.kind).toBe('ai_repair');
    expect(cap.actionLabel).toBe('AI 修复');
    expect(cap.enabled).toBe(true);
  });

  it('21. getFindingCapability - falls back to manual_action when capability is missing', () => {
    const finding: Finding = {
      findingId: 'test:2',
      type: 'issue',
      stage: 'what',
      code: 'LEAF_FEATURE_WITHOUT_ACTOR',
      severity: 'blocking',
      title: 'Test',
      description: 'Test',
      blockingScope: 'stage_transition',
      // no capability field
    };
    const cap = getFindingCapability(finding);
    expect(cap.kind).toBe('manual_action');
    expect(cap.actionLabel).toBe('查看处理建议');
    expect(cap.enabled).toBe(true);
  });

  it('22. getFindingCapability - respects all five capability kinds', () => {
    const labels: Record<string, string> = {
      ai_repair: 'AI 修复',
      generation_draft: '生成草稿',
      open_panel: '定位处理',
      manual_action: '查看处理建议',
      unsupported: '暂不支持自动处理',
    };

    for (const [kind, expectedLabel] of Object.entries(labels)) {
      const finding: Finding = {
        findingId: `test:${kind}`,
        type: 'issue',
        stage: 'what',
        code: 'TEST_CODE',
        severity: 'blocking',
        title: 'Test',
        description: 'Test',
        blockingScope: 'stage_transition',
        capability: { kind: kind as any, action_label: expectedLabel, enabled: kind !== 'unsupported' },
      };
      const cap = getFindingCapability(finding);
      expect(cap.kind).toBe(kind);
      expect(cap.actionLabel).toBe(expectedLabel);
      expect(cap.enabled).toBe(kind !== 'unsupported');
    }
  });

  it('23. loadBackendFindingsAndViews - preserves capability on canonical Finding', async () => {
    const mockCap = { kind: 'ai_repair' as const, action_label: 'AI 修复', enabled: true };
    const mockFindingsIssues: Finding[] = [
      {
        findingId: 'what:LEAF_FEATURE_WITHOUT_ACTOR:feature:10',
        type: 'issue',
        stage: 'what',
        code: 'LEAF_FEATURE_WITHOUT_ACTOR',
        severity: 'blocking',
        title: 'Feature lacks actor',
        description: 'Leaf feature lacks actor binding',
        target: { targetType: 'feature', targetId: 10 },
        blockingScope: 'stage_transition',
        actionCode: 'open_panel',
        metadata: {},
        capability: mockCap,
      },
    ];

    vi.mocked(workspaceApi.listFindings).mockImplementation(async (projectId, params) => {
      if (params.view === 'issues') return { findings: mockFindingsIssues } as any;
      return { findings: [] } as any;
    });
    vi.mocked(workspaceApi.getById).mockResolvedValueOnce({
      projectId: 'project-123',
      projectName: 'Test Space',
      unlockedStages: 'what',
      actors: [],
      features: [],
      flows: [],
    } as any);

    await useWorkspaceStore.getState().openWorkspace('project-123');
    const state = useWorkspaceStore.getState();

    expect(state.findingsByView.issues.length).toBe(1);
    expect(state.findingsByView.issues[0].capability).toEqual(mockCap);
  });
});
