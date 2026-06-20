import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { IssueCard } from '../components/shared/IssueCard';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { Finding } from '../core/schema';

// Mock the store
vi.mock('../lib/api', () => ({
  workspaceApi: { resolveIssue: vi.fn(), updateFindingStatus: vi.fn(), listFindings: vi.fn() },
}));

describe('IssueCard - capability-driven action button', () => {
  const baseIssue: Finding = {
    findingId: 'issue-1',
    type: 'issue',
    stage: 'what',
    code: 'LEAF_FEATURE_WITHOUT_ACTOR',
    title: 'Test Issue',
    description: 'Test issue description',
    severity: 'blocking',
    status: 'open',
    blockingScope: 'stage_transition',
    metadata: {},
  };

  const mockIr = { nodes: {}, projectId: 'p1' } as any;

  beforeEach(() => {
    vi.clearAllMocks();
    useWorkspaceStore.setState({ ir: mockIr });
  });

  it('renders backendCapability action_label on the action button', () => {
    const issue: Finding = {
      ...baseIssue,
      capability: { kind: 'ai_repair', action_label: 'AI 修复', enabled: true },
    };
    render(<IssueCard issue={issue} onClick={vi.fn()} onCreateSlot={vi.fn()} onIgnore={vi.fn()} />);
    expect(screen.queryByText('AI 修复')).not.toBeNull();
  });

  it('renders "生成草稿" for generation_draft capability', () => {
    const issue: Finding = {
      ...baseIssue,
      capability: { kind: 'generation_draft', action_label: '生成草稿', enabled: true },
    };
    render(<IssueCard issue={issue} onClick={vi.fn()} onCreateSlot={vi.fn()} onIgnore={vi.fn()} />);
    expect(screen.queryByText('生成草稿')).not.toBeNull();
  });

  it('renders "定位处理" for open_panel capability', () => {
    const issue: Finding = {
      ...baseIssue,
      capability: { kind: 'open_panel', action_label: '定位处理', enabled: true },
    };
    render(<IssueCard issue={issue} onClick={vi.fn()} onCreateSlot={vi.fn()} onIgnore={vi.fn()} />);
    expect(screen.queryByText('定位处理')).not.toBeNull();
  });

  it('renders "查看处理建议" for manual_action capability', () => {
    const issue: Finding = {
      ...baseIssue,
      capability: { kind: 'manual_action', action_label: '查看处理建议', enabled: true },
    };
    render(<IssueCard issue={issue} onClick={vi.fn()} onCreateSlot={vi.fn()} onIgnore={vi.fn()} />);
    expect(screen.queryByText('查看处理建议')).not.toBeNull();
  });

  it('renders "暂不支持自动处理" for unsupported capability and disables button', () => {
    const issue: Finding = {
      ...baseIssue,
      capability: { kind: 'unsupported', action_label: '暂不支持自动处理', enabled: false },
    };
    render(<IssueCard issue={issue} onClick={vi.fn()} onCreateSlot={vi.fn()} onIgnore={vi.fn()} />);
    const button = screen.queryByText('暂不支持自动处理');
    expect(button).not.toBeNull();
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it('falls back to "查看处理建议" when no backendCapability', () => {
    const issue: Finding = { ...baseIssue };
    render(<IssueCard issue={issue} onClick={vi.fn()} onCreateSlot={vi.fn()} onIgnore={vi.fn()} />);
    expect(screen.queryByText('查看处理建议')).not.toBeNull();
  });
});
