import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { FocusFlowCanvasModal } from '../components/shared/FocusFlowCanvasModal';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { FlowNode, ActorNode, BusinessObjectNode } from '../core/schema';

vi.mock('gsap', () => ({
  default: {
    fromTo: vi.fn(),
  },
}));

vi.mock('react-i18next', () => ({
  initReactI18next: {
    type: '3rdParty',
    init: vi.fn(),
  },
  useTranslation: () => ({
    t: (key: string, defaultVal?: any) => {
      if (typeof defaultVal === 'string') return defaultVal;
      if (defaultVal && typeof defaultVal === 'object' && defaultVal.defaultValue) return defaultVal.defaultValue;
      return key;
    },
    i18n: {
      changeLanguage: vi.fn().mockResolvedValue(true),
      language: 'zh-CN',
    },
  }),
}));

describe('FocusFlowCanvasModal Component', () => {
  const mockOnUpdateStep = vi.fn().mockResolvedValue(undefined);
  const mockOnAddStep = vi.fn().mockResolvedValue(undefined);
  const mockOnDeleteStep = vi.fn().mockResolvedValue(undefined);
  const mockOnUpdateTransition = vi.fn().mockResolvedValue(undefined);
  const mockOnDeleteTransition = vi.fn().mockResolvedValue(undefined);
  const mockOnClose = vi.fn();

  const sampleFlow: FlowNode = {
    kind: 'flow',
    flowId: 101,
    flowName: 'Order Processing Flow',
    flowDescription: 'Standard order checkout flow',
    featureIds: [],
    flowSteps: [
      {
        kind: 'flow_step',
        stepId: 1,
        stepName: 'Submit Order',
        stepDescription: 'User submits shopping cart order',
        stepType: 'actorAction',
        actorIds: [1],
        inputBusinessObjectIds: [],
        outputBusinessObjectIds: [],
      },
      {
        kind: 'flow_step',
        stepId: 2,
        stepName: 'Review Payment',
        stepDescription: 'System verifies payment status',
        stepType: 'systemAction',
        actorIds: [],
        inputBusinessObjectIds: [],
        outputBusinessObjectIds: [],
      },
    ],
    transitions: [
      {
        transitionId: 201,
        flowId: 101,
        sourceStepId: 1,
        targetStepId: 2,
        label: 'Pay Success',
        conditionText: 'payment.status == "SUCCESS"',
        isDefault: false,
        semanticTags: ['happy_path'],
        confirmationStatus: 'confirmed',
        ruleIds: [10],
      },
    ],
  };

  const sampleActors: ActorNode[] = [
    { kind: 'actor', actorId: 1, actorName: 'Customer', actorDescription: '' },
  ];

  const sampleBusinessObjects: BusinessObjectNode[] = [];

  const sampleDomainRules = [
    {
      id: 10,
      title: 'Payment Verification Rule',
      statement: 'Every payment must have a valid gateway token',
      origin: 'system',
      confirmationStatus: 'confirmed',
    },
    {
      id: 20,
      title: 'Amount Limit Rule',
      statement: 'Single transaction cannot exceed $50000',
      origin: 'system',
      confirmationStatus: 'confirmed',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    useWorkspaceStore.setState({
      ir: {
        domainRules: sampleDomainRules,
      } as any,
      workspaceCanWrite: () => true,
    } as any);
  });

  it('renders transition details and linked rules when transition is selected', () => {
    render(
      <FocusFlowCanvasModal
        flow={sampleFlow}
        isOpen={true}
        onClose={mockOnClose}
        actors={sampleActors}
        businessObjects={sampleBusinessObjects}
        onUpdateStep={mockOnUpdateStep}
        onAddStep={mockOnAddStep}
        onDeleteStep={mockOnDeleteStep}
        onUpdateTransition={mockOnUpdateTransition}
        onDeleteTransition={mockOnDeleteTransition}
      />
    );

    // Select the transition via its hitarea
    const transitionHit = screen.getByTestId('transition-hitarea-201');
    fireEvent.click(transitionHit);

    // Transition inspector elements should be visible
    const labelInput = screen.getByTestId('transition-label-input') as HTMLInputElement;
    const conditionInput = screen.getByTestId('transition-condition-input') as HTMLTextAreaElement;
    const defaultCheckbox = screen.getByTestId('transition-default-checkbox') as HTMLInputElement;
    const tagsInput = screen.getByTestId('transition-tags-input') as HTMLInputElement;

    expect(labelInput.value).toBe('Pay Success');
    expect(conditionInput.value).toBe('payment.status == "SUCCESS"');
    expect(defaultCheckbox.checked).toBe(false);
    expect(tagsInput.value).toBe('happy_path');

    // Rule 10 should be checked, Rule 20 should be unchecked
    const rule10 = screen.getByTestId('rule-checkbox-10') as HTMLInputElement;
    const rule20 = screen.getByTestId('rule-checkbox-20') as HTMLInputElement;
    expect(rule10.checked).toBe(true);
    expect(rule20.checked).toBe(false);
  });

  it('updates transition fields, toggles linked rules, and calls onUpdateTransition with ruleIds on save', async () => {
    render(
      <FocusFlowCanvasModal
        flow={sampleFlow}
        isOpen={true}
        onClose={mockOnClose}
        actors={sampleActors}
        businessObjects={sampleBusinessObjects}
        onUpdateStep={mockOnUpdateStep}
        onAddStep={mockOnAddStep}
        onDeleteStep={mockOnDeleteStep}
        onUpdateTransition={mockOnUpdateTransition}
        onDeleteTransition={mockOnDeleteTransition}
      />
    );

    // Select transition
    act(() => {
      fireEvent.click(screen.getByTestId('transition-hitarea-201'));
    });

    // Edit label and condition
    const labelInput = screen.getByTestId('transition-label-input');
    act(() => {
      fireEvent.change(labelInput, { target: { value: 'Verified & Paid' } });
    });

    const conditionInput = screen.getByTestId('transition-condition-input');
    act(() => {
      fireEvent.change(conditionInput, { target: { value: 'status == "PAID"' } });
    });

    // Toggle default branch
    const defaultCheckbox = screen.getByTestId('transition-default-checkbox');
    act(() => {
      fireEvent.click(defaultCheckbox);
    });

    // Toggle rule 20 on (so both 10 and 20 are selected)
    const rule20 = screen.getByTestId('rule-checkbox-20');
    act(() => {
      fireEvent.click(rule20);
    });

    // Click save
    const saveBtn = screen.getByTestId('save-transition-button');
    await act(async () => {
      fireEvent.click(saveBtn);
    });

    expect(mockOnUpdateTransition).toHaveBeenCalledTimes(1);
    expect(mockOnUpdateTransition).toHaveBeenCalledWith(101, 201, {
      label: 'Verified & Paid',
      conditionText: 'status == "PAID"',
      isDefault: true,
      semanticTags: ['happy_path'],
      confirmationStatus: 'confirmed',
      ruleIds: [10, 20],
    });
  });

  it('enforces read-only mode when readOnly={true}', () => {
    render(
      <FocusFlowCanvasModal
        flow={sampleFlow}
        isOpen={true}
        onClose={mockOnClose}
        actors={sampleActors}
        businessObjects={sampleBusinessObjects}
        onUpdateStep={mockOnUpdateStep}
        onAddStep={mockOnAddStep}
        onDeleteStep={mockOnDeleteStep}
        onUpdateTransition={mockOnUpdateTransition}
        onDeleteTransition={mockOnDeleteTransition}
        readOnly={true}
      />
    );

    // Read only badge should appear
    expect(screen.getByText('只读模式')).toBeDefined();

    // "添加步骤" button should be hidden
    expect(screen.queryByText('添加步骤')).toBeNull();

    // Port handle should be hidden
    expect(document.querySelector('.port-handle.bg-indigo-600')).toBeNull();

    // Select transition
    fireEvent.click(screen.getByTestId('transition-hitarea-201'));

    // Form inputs should be disabled
    const labelInput = screen.getByTestId('transition-label-input') as HTMLInputElement;
    const conditionInput = screen.getByTestId('transition-condition-input') as HTMLTextAreaElement;
    const defaultCheckbox = screen.getByTestId('transition-default-checkbox') as HTMLInputElement;
    const tagsInput = screen.getByTestId('transition-tags-input') as HTMLInputElement;
    const rule10 = screen.getByTestId('rule-checkbox-10') as HTMLInputElement;

    expect(labelInput.disabled).toBe(true);
    expect(conditionInput.disabled).toBe(true);
    expect(defaultCheckbox.disabled).toBe(true);
    expect(tagsInput.disabled).toBe(true);
    expect(rule10.disabled).toBe(true);

    // Save and Delete transition buttons should not be rendered
    expect(screen.queryByTestId('save-transition-button')).toBeNull();
    expect(screen.queryByTestId('delete-transition-button')).toBeNull();
  });

  it('enforces effectiveReadOnly when workspaceCanWrite returns false even without readOnly prop', () => {
    useWorkspaceStore.setState({
      workspaceCanWrite: () => false,
    } as any);

    render(
      <FocusFlowCanvasModal
        flow={sampleFlow}
        isOpen={true}
        onClose={mockOnClose}
        actors={sampleActors}
        businessObjects={sampleBusinessObjects}
        onUpdateStep={mockOnUpdateStep}
        onAddStep={mockOnAddStep}
        onDeleteStep={mockOnDeleteStep}
        onUpdateTransition={mockOnUpdateTransition}
        onDeleteTransition={mockOnDeleteTransition}
      />
    );

    expect(screen.getByText('只读模式')).toBeDefined();
    expect(screen.queryByText('添加步骤')).toBeNull();
  });

  it('renders flow refinement overlay steps, candidate transitions, and rule badges when choice group is open', () => {
    useWorkspaceStore.setState({
      backendChoiceGroups: {
        'group-1': {
          groupId: 'group-1',
          generationType: 'flow_refinement',
          status: 'open',
          target: { flow_id: 101 },
          choices: [
            {
              choiceId: 'choice-1',
              preview: {
                steps_added: [
                  {
                    temp_id: 'temp_step_1',
                    name: 'Verify Cart Items',
                    description: 'Check item stock and discount',
                    step_type: 'systemAction',
                  },
                ],
                transitions_added: [
                  {
                    temp_id: 'temp_trans_1',
                    source_step_ref: 1,
                    target_step_ref: 'temp_step_1',
                    label: 'Items Valid',
                    condition_text: 'cart.valid == true',
                  },
                ],
                rules_added: [
                  {
                    temp_id: 'temp_rule_1',
                    title: 'Stock Lock Rule',
                    statement: 'Stock must be locked during checkout',
                    parent_rule_ref: 'temp_step_1',
                  },
                ],
              },
            },
          ],
        },
      } as any,
    } as any);

    render(
      <FocusFlowCanvasModal
        flow={sampleFlow}
        isOpen={true}
        onClose={mockOnClose}
        actors={sampleActors}
        businessObjects={sampleBusinessObjects}
        onUpdateStep={mockOnUpdateStep}
        onAddStep={mockOnAddStep}
        onDeleteStep={mockOnDeleteStep}
        onUpdateTransition={mockOnUpdateTransition}
        onDeleteTransition={mockOnDeleteTransition}
      />
    );

    // Overlay header badge should be displayed
    const badge = screen.getByTestId('refinement-overlay-badge');
    expect(badge).toBeDefined();
    expect(badge.textContent).toContain('细化候选待处理');
    expect(badge.textContent).toContain('+1步骤');
    expect(badge.textContent).toContain('+1转移');
    expect(badge.textContent).toContain('+1规则');

    // Candidate step should be rendered
    const candStep = screen.getByTestId('candidate-step-temp_step_1');
    expect(candStep).toBeDefined();
    expect(candStep.textContent).toContain('Verify Cart Items');
    expect(candStep.textContent).toContain('Check item stock and discount');

    // Candidate rule badge should be rendered
    const ruleBadge = screen.getByTestId('candidate-rule-badge-temp_rule_1');
    expect(ruleBadge).toBeDefined();
    expect(ruleBadge.textContent).toContain('Stock Lock Rule');
    expect(ruleBadge.textContent).toContain('Stock must be locked during checkout');

    // Candidate transition edge should be rendered in SVG
    const transEdge = screen.getByTestId('candidate-transition-edge-temp_trans_1');
    expect(transEdge).toBeDefined();
  });
});
