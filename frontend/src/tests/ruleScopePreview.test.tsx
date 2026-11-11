import { afterEach, expect, it } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import { ChoicePreviewRenderer } from '../components/shared/ChoicePreviewRenderer';

afterEach(cleanup);

it('shows refinement rule text and association scopes using the actual preview contract', () => {
  render(<ChoicePreviewRenderer draftType="flow_refinement" preview={{
    target_flow_name: '订单流程', rules_added: [{ temp_id: 'r-new', title: '报价约束', statement: '毛利率不得低于百分之十五' }],
    rule_links_added: ['flow', 'flow_step', 'flow_transition'].map(kind => ({
      rule_ref: 'r-new', target_kind: kind, target_ref: `${kind}-target`, link_purpose: 'applies_to',
    })),
  }} />);
  expect(screen.getByText('毛利率不得低于百分之十五')).toBeDefined();
  const links = within(screen.getByTestId('refinement-rule-associations'));
  expect(links.getByText('流程级规则 · 订单流程')).toBeDefined();
  expect(links.getByText('本步骤直接关联规则 · flow_step-target')).toBeDefined();
  expect(links.getByText('分支连线规则 · flow_transition-target')).toBeDefined();
  expect(links.getAllByText('报价约束')).toHaveLength(3);
});

it('counts a rule once across flow, step, and transition scopes in a flow candidate', () => {
  render(<ChoicePreviewRenderer draftType="flow" payload={{ flows: [{ flow_name: '报价流程', rule_refs: ['r-1'],
    flow_steps: [{ step_name: '报价', rule_refs: ['r-1', 'r-2'] }],
    transitions: [{ source_step_number: 'S-001', target_step_number: 'S-002', rule_refs: ['r-2'] }],
  }] }} />);
  expect(screen.getByText(/包含 2 条业务规则/)).toBeDefined();
});
