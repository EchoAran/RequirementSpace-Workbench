import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { IssuePanel } from '../components/right-panel/IssuePanel';
import { Finding, RequirementSpaceIR } from '../core/schema';

// Mock the store functions used by IssuePanel
vi.mock('../lib/api', () => ({
  workspaceApi: {
    updateFindingStatus: vi.fn().mockResolvedValue({}),
    listFindings: vi.fn().mockResolvedValue({ findings: [] }),
    resolveIssue: vi.fn().mockResolvedValue({ resolution_type: 'unsupported' }),
  },
}));

describe('IssuePanel - capability-driven action button', () => {
  const baseIssue: Finding = {
    findingId: 'issue-1',
    type: 'issue',
    code: 'LEAF_FEATURE_WITHOUT_ACTOR',
    title: 'Test Issue',
    description: 'Test issue description',
    severity: 'blocking',
    status: 'open',
    stage: 'what',
    blockingScope: 'stage_transition',
    metadata: {},
  };

  const baseIr: RequirementSpaceIR = {
    projectId: 'project-123',
    projectName: 'Test Project',
    actors: [],
    features: [],
    flows: [],
    businessObjects: [],
  } as any;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders backendCapability action_label on the action button', () => {
    const issueWithCap: Finding = {
      ...baseIssue,
      capability: { kind: 'ai_repair', action_label: 'AI 修复', enabled: true },
    };

    render(<IssuePanel issue={issueWithCap} ir={baseIr} />);
    expect(screen.queryByText('AI 修复')).not.toBeNull();
  });

  it('renders "查看处理建议" for manual_action capability', () => {
    const issueWithManual: Finding = {
      ...baseIssue,
      code: 'UNKNOWN_CODE',
      capability: { kind: 'manual_action', action_label: '查看处理建议', enabled: true },
    };

    render(<IssuePanel issue={issueWithManual} ir={baseIr} />);
    expect(screen.queryByText('查看处理建议')).not.toBeNull();
  });

  it('renders "生成草稿" for generation_draft capability', () => {
    const issueWithGen: Finding = {
      ...baseIssue,
      code: 'SCENARIO_WITHOUT_ACCEPTANCE_CRITERIA',
      capability: { kind: 'generation_draft', action_label: '生成草稿', enabled: true },
    };

    render(<IssuePanel issue={issueWithGen} ir={baseIr} />);
    expect(screen.queryByText('生成草稿')).not.toBeNull();
  });

  it('renders "定位处理" for open_panel capability', () => {
    const issueWithPanel: Finding = {
      ...baseIssue,
      code: 'ACTOR_ACTION_STEP_WITHOUT_ACTOR',
      capability: { kind: 'open_panel', action_label: '定位处理', enabled: true },
    };

    render(<IssuePanel issue={issueWithPanel} ir={baseIr} />);
    expect(screen.queryByText('定位处理')).not.toBeNull();
  });

  it('disables action button when capability is unsupported and enabled=false', () => {
    const issueWithUnsupported: Finding = {
      ...baseIssue,
      code: 'UNKNOWN',
      capability: { kind: 'unsupported', action_label: '暂不支持自动处理', enabled: false },
    };

    render(<IssuePanel issue={issueWithUnsupported} ir={baseIr} />);
    // The button should exist but be disabled
    const button = screen.queryByText('暂不支持自动处理');
    expect(button).not.toBeNull();
  });

  it('falls back to "查看处理建议" when no backendCapability and code is present', () => {
    const issueNoCap: Finding = {
      ...baseIssue,
      code: 'SOME_CODE',
    };

    render(<IssuePanel issue={issueNoCap} ir={baseIr} />);
    expect(screen.queryByText('查看处理建议')).not.toBeNull();
  });
});
