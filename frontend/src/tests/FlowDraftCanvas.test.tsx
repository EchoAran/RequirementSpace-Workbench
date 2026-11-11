import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FlowDraftCanvas } from '../components/how/flow_canvas/FlowDraftCanvas';

describe('FlowDraftCanvas', () => {
  it('renders the generated flow contract as connected canvas nodes', () => {
    render(
      <FlowDraftCanvas
        flow={{
          flow_steps: [
            {
              step_name: '提交订单',
              step_description: '用户提交购物车中的商品',
              step_type: 'actorAction',
              actor_names: ['顾客'],
              output_business_object_names: ['订单'],
            },
            {
              step_name: '校验库存',
              step_description: '系统检查库存是否足够',
              step_type: 'systemAction',
              input_business_object_names: ['订单'],
            },
          ],
          flow_transitions: [
            {
              source_step_name: '提交订单',
              target_step_name: '校验库存',
              label: '提交成功',
              condition_text: '订单完整',
            },
          ],
        }}
      />
    );

    expect(screen.getByTestId('flow-draft-canvas')).toBeDefined();
    expect(screen.getAllByTestId('flow-draft-edge')).toHaveLength(1);
    expect(screen.getByText('提交订单')).toBeDefined();
    expect(screen.getByText('校验库存')).toBeDefined();
    expect(screen.getByText('提交成功 · 订单完整')).toBeDefined();
  });

  it('does not invent sequential edges when the draft has no transitions', () => {
    render(
      <FlowDraftCanvas
        flow={{
          flow_steps: [
            { step_name: '步骤一', step_type: 'actorAction' },
            { step_name: '步骤二', step_type: 'systemAction' },
          ],
          flow_transitions: [],
        }}
      />
    );

    expect(screen.queryAllByTestId('flow-draft-edge')).toHaveLength(0);
  });
});
