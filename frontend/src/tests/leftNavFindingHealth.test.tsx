import { renderWithEffects as render } from './renderWithEffects';
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { LeftNav } from '../components/layout/LeftNav';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../lib/api', () => ({
  workspaceApi: {
    listFindings: vi.fn().mockResolvedValue({ findings: [] }),
    updateFindingStatus: vi.fn().mockResolvedValue({}),
    getLatestPrototypePreview: vi.fn().mockResolvedValue({ status: 'completed', preview: null }),
  }
}));

describe('LeftNav backend health status tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useWorkspaceStore.setState({
      ir: {
        projectId: 'project-123',
        projectName: 'Test Project',
        unlockedStages: 'what',
        actors: [{ id: 1, name: 'Admin' }],
        features: [{ featureId: 10, featureName: 'Settings', parentId: null }],
        flows: [],
        businessObjects: [],
        findings: []
      } as any,
      findingsByView: {
        issues: [],
        next_action: [],
        gate: [],
        health: []
      },
      stageProgress: null,
    });
  });

  it('should show Ready (已就绪) status when only next action and health hints exist', async () => {
    // Set next action finding and health hint finding
    useWorkspaceStore.setState({
      stageProgress: {
        stages: [
          { stage: 'what', unlocked: true, statusCode: 'ready', statusLabel: '已就绪', blockingFindings: [] },
          { stage: 'how', unlocked: false, statusCode: 'locked', statusLabel: '未解锁', blockingFindings: [] },
          { stage: 'scope', unlocked: false, statusCode: 'locked', statusLabel: '未解锁', blockingFindings: [] },
        ]
      } as any,
      findingsByView: {
        issues: [], // No countable issues
        next_action: [
          {
            findingId: 'what:NEXT_ACTION_TEST:feature:1',
            type: 'next_suggestion',
            stage: 'what',
            code: 'NEXT_ACTION_TEST',
            severity: 'info',
            title: '建议补齐系统角色',
            description: '建模需要至少一个核心角色。',
            blockingScope: 'none',
            metadata: {}
          }
        ],
        gate: [],
        health: [
          {
            findingId: 'what:HEALTH_TEST:feature:3',
            type: 'quality_hint',
            stage: 'what',
            code: 'HEALTH_TEST',
            severity: 'info',
            title: '冗余场景名称提示',
            description: '部分典型场景名称存在冗余词汇。',
            blockingScope: 'none',
            metadata: {}
          }
        ]
      },
      ir: {
        projectId: 'project-123',
        projectName: 'Test Project',
        unlockedStages: 'what',
        actors: [{ id: 1, name: 'Admin' }],
        features: [{ featureId: 10, featureName: 'Settings', parentId: null }],
        flows: [],
        businessObjects: [],
        findings: [
          {
            findingId: 'what:ACTOR_WITHOUT_FEATURE:actor:5',
            type: 'quality_hint',
            code: 'ACTOR_WITHOUT_FEATURE',
            title: 'Actor not linked',
            description: 'Actor has no associated feature',
            severity: 'warning',
            status: 'open',
            stage: 'what',
            blockingScope: 'none',
            metadata: {},
          }
        ]
      } as any
    });

    await render(
      <MemoryRouter>
        <LeftNav />
      </MemoryRouter>
    );

    // LeftNav should display '已就绪' for '要做什么' (which maps to /what)
    // and should NOT display '待处理' or '1 待处理' since next_action and health (ACTOR_WITHOUT_FEATURE) are not countable
    expect(screen.queryByText('已就绪')).not.toBeNull();
    expect(screen.queryByText('待处理')).toBeNull();
    expect(screen.queryByText('1 待处理')).toBeNull();
  });

  it('should show Needs Attention (待处理) when a real countable issue exists', async () => {
    useWorkspaceStore.setState({
      stageProgress: {
        stages: [
          {
            stage: 'what',
            unlocked: true,
            statusCode: 'blocked',
            statusLabel: '待处理',
            blockingFindings: [{ findingId: 'what:LEAF_FEATURE_WITHOUT_ACTOR:feature:10' }],
          },
          { stage: 'how', unlocked: false, statusCode: 'locked', statusLabel: '未解锁', blockingFindings: [] },
          { stage: 'scope', unlocked: false, statusCode: 'locked', statusLabel: '未解锁', blockingFindings: [] },
        ]
      } as any,
      findingsByView: {
        issues: [
          {
            findingId: 'what:LEAF_FEATURE_WITHOUT_ACTOR:feature:10',
            type: 'issue',
            stage: 'what',
            code: 'LEAF_FEATURE_WITHOUT_ACTOR',
            severity: 'blocking',
            title: 'Feature lacks actor',
            description: 'Leaf feature lacks actor binding',
            blockingScope: 'stage_transition',
            metadata: {}
          }
        ],
        next_action: [],
        gate: [],
        health: []
      },
      ir: {
        projectId: 'project-123',
        projectName: 'Test Project',
        unlockedStages: 'what',
        actors: [{ id: 1, name: 'Admin' }],
        features: [{ featureId: 10, featureName: 'Settings', parentId: null }],
        flows: [],
        businessObjects: [],
        findings: [
          {
            findingId: 'what:LEAF_FEATURE_WITHOUT_ACTOR:feature:10',
            type: 'issue',
            code: 'LEAF_FEATURE_WITHOUT_ACTOR',
            title: 'Feature lacks actor',
            description: 'Leaf feature lacks actor binding',
            severity: 'blocking',
            status: 'open',
            stage: 'what',
            blockingScope: 'stage_transition',
            metadata: {},
          }
        ]
      } as any
    });

    await render(
      <MemoryRouter>
        <LeftNav />
      </MemoryRouter>
    );

    // LeftNav should display the backend issue count and no ready state.
    expect(screen.queryByText(/1 (待处理|pending)/i)).not.toBeNull();
    expect(screen.queryByText(/^(已就绪|ready)$/i)).toBeNull();
  });

  it('labels a non-blocking perception slot as a refinement suggestion', async () => {
    useWorkspaceStore.setState({
      ir: {
        ...useWorkspaceStore.getState().ir,
        statusCode: 'needs_attention',
        issueCount: 0,
        perceptionSlot: {
          id: '9',
          stage: 'what',
          perceptionKind: '功能模块结点',
          perceptionDescription: '可选补充建议',
        },
      } as any,
      stageProgress: {
        stages: [
          { stage: 'what', unlocked: true, statusCode: 'ready_to_advance', blockingFindings: [] },
          { stage: 'how', unlocked: false, statusCode: 'locked', blockingFindings: [] },
          { stage: 'scope', unlocked: false, statusCode: 'locked', blockingFindings: [] },
        ],
      } as any,
    });

    await render(<MemoryRouter><LeftNav /></MemoryRouter>);

    expect(screen.queryByText('有待完善建议')).not.toBeNull();
    expect(screen.queryByText('存在阻塞问题')).toBeNull();
  });
});
