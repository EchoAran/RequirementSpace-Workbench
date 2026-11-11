import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';
import { ChoiceCard } from '../components/shared/ChoiceCard';
import { Choice } from '../core/schema';
import { useWorkspaceStore } from '../store/useWorkspaceStore';

vi.mock('../lib/api', () => ({
  workspaceApi: {},
}));

describe('ChoiceCard', () => {
  it('renders an issue-repair impact preview without legacy impact arrays', () => {
    useWorkspaceStore.setState({ ir: { projectId: 'p1' } as any });
    const choice: Choice = {
      id: '8',
      title: '补充参与者关联',
      rationale: '修复参与者一致性问题',
      status: 'candidate',
      impactPreview: {
        summary: '将补充参与者关联',
        affected_nodes: [],
        affected_relations: [],
        risk_level: 'low',
      },
    };

    expect(() => render(
      <ChoiceCard
        choice={choice}
        onAccept={vi.fn()}
        onRewrite={vi.fn()}
        onReject={vi.fn()}
      />,
    )).not.toThrow();
  });
});
