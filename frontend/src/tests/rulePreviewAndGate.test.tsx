import { renderWithEffects as render } from './renderWithEffects';
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ChoicePreviewRenderer } from '../components/shared/ChoicePreviewRenderer';
import { ChoiceGroupPreviewModal } from '../components/shared/ChoiceGroupPreviewModal';
import { HowItWorks } from '../pages/HowItWorks';
import { useWorkspaceStore } from '../store/useWorkspaceStore';

vi.mock('react-i18next', () => ({
  initReactI18next: {
    type: '3rdParty',
    init: vi.fn(),
  },
  useTranslation: () => ({
    t: (key: string, options?: any) => {
      if (options?.count !== undefined) return `${key} (${options.count})`;
      if (options?.status !== undefined) return `${key}: ${options.status}`;
      if (options?.target !== undefined) return `${key}: ${options.target}`;
      if (options?.defaultValue) return options.defaultValue;
      return key;
    },
    i18n: {
      changeLanguage: vi.fn().mockResolvedValue(true),
      language: 'zh-CN',
      t: (key: string, options?: any) => {
        if (options?.target !== undefined) return `${key}: ${options.target}`;
        return key;
      },
    },
  }),
}));

vi.mock('../components/shared/RightObjectPanel', () => ({
  RightObjectPanel: () => <div data-testid="right-object-panel" />
}));
vi.mock('../components/shared/DraftPreviewModal', () => ({
  DraftPreviewModal: () => <div data-testid="draft-preview-modal" />
}));
vi.mock('../components/shared/FocusFlowCanvasModal', () => ({
  FocusFlowCanvasModal: () => <div data-testid="focus-flow-canvas-modal" />
}));
vi.mock('../components/shared/ConfirmTransitionModal', () => ({
  ConfirmTransitionModal: () => <div data-testid="confirm-transition-modal" />
}));
vi.mock('../components/shared/AIAddObjectDialog', () => ({
  AIAddObjectDialog: () => <div data-testid="ai-add-object-dialog" />
}));
vi.mock('../components/how/RuleSection', () => ({
  RuleSection: () => <div data-testid="rule-section" />
}));
vi.mock('../components/shared/StageGuidanceBanner', () => ({
  StageGuidanceBanner: () => <div data-testid="stage-guidance-banner" />
}));

describe('Rule and Flow Preview Contracts', () => {
  it('renders rule preview with statement, confirmation status badges, and source links', async () => {
    const previewData = {
      rule_count: 2,
      rules: [
        {
          temp_id: 'rule-temp-1',
          title: 'Order Refund Policy',
          statement: 'Refund must be initiated within 7 days of delivery.',
          confirmation_status: 'confirmed',
          parent_rule_ref: null,
          source_links: [
            {
              target_kind: 'knowledge',
              context_text: 'chunk-kb-001: Refund FAQ section 2',
            },
          ],
        },
        {
          temp_id: 'rule-temp-2',
          title: 'Partial Refund Rule',
          statement: 'Partial refund requires managerial approval.',
          confirmation_status: 'needs_confirmation',
          parent_rule_ref: 'rule-temp-1',
          source_links: [
            {
              target_kind: 'feature',
              target_logical_uuid: 'feat-uuid-refund',
              context_text: 'Feature: Refund processing',
            },
          ],
        },
      ],
    };

    await render(<ChoicePreviewRenderer draftType="rule" preview={previewData} />);

    expect(screen.getByText('Order Refund Policy')).toBeTruthy();
    expect(screen.getByText('Refund must be initiated within 7 days of delivery.')).toBeTruthy();
    expect(screen.getByText('nodeStatus.confirmed')).toBeTruthy();
    expect(screen.getByText(/knowledge/i)).toBeTruthy();
    expect(screen.getByText(/: chunk-kb-001: Refund FAQ section 2/)).toBeTruthy();

    expect(screen.getByText('Partial Refund Rule')).toBeTruthy();
    expect(screen.getByText('Partial refund requires managerial approval.')).toBeTruthy();
    expect(screen.getByText('nodeStatus.needs_confirmation')).toBeTruthy();
    expect(screen.getByText(/Parent:\s*rule-temp-1/)).toBeTruthy();
    expect(screen.getAllByText(/feature/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/: Feature: Refund processing/)).toBeTruthy();
  });

  it('renders flow transitions with source/target step numbers and rule reference badge', async () => {
    const previewData = {
      flow_count: 1,
      flows: [
        {
          flow_name: 'Checkout Flow',
          flow_description: 'Standard payment checkout sequence',
          steps: [
            { step_number: '1', step_name: 'Submit Order' },
            { step_number: '2', step_name: 'Process Payment' },
          ],
          transitions: [
            {
              transition_temp_id: 'tr-1',
              source_step_number: '1',
              target_step_number: '2',
              label: 'Proceed to Pay',
              condition_text: 'cart.total > 0',
              is_default: true,
              rule_refs: ['rule-uuid-1', 'rule-uuid-2'],
            },
          ],
        },
      ],
    };

    await render(<ChoicePreviewRenderer draftType="flow" preview={previewData} />);

    expect(screen.getByText('Checkout Flow')).toBeTruthy();
    expect(screen.getByText('1')).toBeTruthy();
    expect(screen.getByText('2')).toBeTruthy();
    expect(screen.getByText('[Proceed to Pay]')).toBeTruthy();
    expect(screen.getByText('(cart.total > 0)')).toBeTruthy();
    expect(screen.getByText('Default')).toBeTruthy();
    expect(screen.getByText('2 Rules')).toBeTruthy();
  });

  it('renders flow transitions with fallback to step_ref when step_number is absent', async () => {
    const previewData = {
      flow_count: 1,
      flows: [
        {
          flow_name: 'Approval Flow',
          steps: [
            { step_name: 'Draft' },
            { step_name: 'Approve' },
          ],
          transitions: [
            {
              transition_temp_id: 'tr-ref-1',
              source_step_ref: 'step-ref-start',
              target_step_ref: 'step-ref-end',
              label: 'Sign Off',
              rule_refs: ['rule-uuid-mgr'],
            },
          ],
        },
      ],
    };

    await render(<ChoicePreviewRenderer draftType="flow" preview={previewData} />);

    expect(screen.getByText('step-ref-start')).toBeTruthy();
    expect(screen.getByText('step-ref-end')).toBeTruthy();
    expect(screen.getByText('[Sign Off]')).toBeTruthy();
    expect(screen.getByText('1 Rules')).toBeTruthy();
  });
});

describe('ChoiceGroupPreviewModal Flow Replacement Confirmation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useWorkspaceStore.setState({
      ir: {
        flows: [{ id: 1, flowName: 'Existing Flow' }],
        businessObjects: [],
      } as any,
    });
  });

  it('prompts window.confirm with confirmReplaceFlowSet when accepting flow choice and flows exist', async () => {
    const confirmMock = vi.fn().mockReturnValue(true);
    window.confirm = confirmMock;
    const mockAccept = vi.fn();

    const mockGroup = {
      id: 101,
      generationType: 'flow',
      choices: [
        {
          id: 1,
          status: 'candidate',
          choiceKey: 'choice-1',
          label: 'Candidate 1',
          applyBehavior: 'replace_flow_set',
          preview: { flow_count: 1, flows: [{ flow_name: 'New Flow' }] },
          payload: {},
        },
      ],
    };

    await render(
      <ChoiceGroupPreviewModal
        group={mockGroup as any}
        isWorking={false}
        isGeneratingChoices={false}
        generationProgress={null}
        onAccept={mockAccept}
        onDiscard={vi.fn()}
        onDefer={vi.fn()}
        onRegenerate={vi.fn()}
      />
    );

    const adoptBtn = screen.getByText('choiceGroupPreview.adoptPlanBtn');
    await act(async () => fireEvent.click(adoptBtn));

    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringMatching(/替换当前工作区的所有现有流程|confirmReplaceFlowSet/)
    );
    expect(mockAccept).toHaveBeenCalled();
  });

  it('cancels adoption when user declines window.confirm', async () => {
    const confirmMock = vi.fn().mockReturnValue(false);
    window.confirm = confirmMock;
    const mockAccept = vi.fn();

    const mockGroup = {
      id: 101,
      generationType: 'flow',
      choices: [
        {
          id: 1,
          status: 'candidate',
          choiceKey: 'choice-1',
          label: 'Candidate 1',
          applyBehavior: 'replace_flow_set',
          preview: { flow_count: 1, flows: [{ flow_name: 'New Flow' }] },
          payload: {},
        },
      ],
    };

    await render(
      <ChoiceGroupPreviewModal
        group={mockGroup as any}
        isWorking={false}
        isGeneratingChoices={false}
        generationProgress={null}
        onAccept={mockAccept}
        onDiscard={vi.fn()}
        onDefer={vi.fn()}
        onRegenerate={vi.fn()}
      />
    );

    const adoptBtn = screen.getByText('choiceGroupPreview.adoptPlanBtn');
    await act(async () => fireEvent.click(adoptBtn));

    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringMatching(/替换当前工作区的所有现有流程|confirmReplaceFlowSet/)
    );
    expect(mockAccept).not.toHaveBeenCalled();
  });
});

describe('HowItWorks Flow Generation Gate & Read-Only Permissions', () => {
  const mockGenerateFlows = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    useWorkspaceStore.setState({
      ir: {
        projectId: 1,
        actors: [{ actorId: 1, id: 1, actorName: 'Customer', name: 'Customer' }],
        features: [{ featureId: 1, id: 1, featureName: 'Checkout', name: 'Checkout' }],
        flows: [],
        businessObjects: [],
        domainRules: [],
      } as any,
      generatingChoiceGroupType: null,
      workspaceCanWrite: () => true,
      generateFlows: mockGenerateFlows,
      selectedObjectId: null,
      selectedObjectType: null,
      choiceGroups: [],
    } as any);
  });

  it('disables flow generation button when no domain rule exists', async () => {
    await render(
      <MemoryRouter>
        <HowItWorks />
      </MemoryRouter>
    );

    expect(screen.getAllByTitle('how.domainRules.ruleRequiredForFlow').length).toBeGreaterThan(0);
    const genBtn = screen.getAllByText('how.generateBtn')[0].closest('button');
    expect(genBtn).toBeTruthy();
    expect(genBtn?.disabled).toBe(true);

    await act(async () => fireEvent.click(genBtn!));
    expect(mockGenerateFlows).not.toHaveBeenCalled();
  });

  it('enables flow generation button when a domain rule exists and workspace is writable', async () => {
    useWorkspaceStore.setState({
      ir: {
        projectId: 1,
        actors: [{ actorId: 1, id: 1, actorName: 'Customer', name: 'Customer' }],
        features: [{ featureId: 1, id: 1, featureName: 'Checkout', name: 'Checkout' }],
        flows: [],
        businessObjects: [],
        domainRules: [{ id: 1, logicalUuid: 'rule-1', title: 'Checkout rule', statement: 'Checkout must follow the rule.' }],
      } as any,
    });

    await render(
      <MemoryRouter>
        <HowItWorks />
      </MemoryRouter>
    );

    expect(screen.queryAllByTitle('how.domainRules.ruleRequiredForFlow')).toHaveLength(0);
    const genBtn = screen.getAllByText('how.generateBtn')[0].closest('button');
    expect(genBtn).toBeTruthy();
    expect(genBtn?.disabled).toBe(false);

    await act(async () => fireEvent.click(genBtn!));
    expect(mockGenerateFlows).toHaveBeenCalled();
  });

  it('disables generation and hides modification buttons when workspace is read-only', async () => {
    useWorkspaceStore.setState({
      ir: {
        projectId: 1,
        actors: [{ actorId: 1, id: 1, actorName: 'Customer', name: 'Customer' }],
        features: [{ featureId: 1, id: 1, featureName: 'Checkout', name: 'Checkout' }],
        flows: [
          {
            id: 1,
            flowId: 1,
            flowName: 'Active Order Flow',
            steps: [],
            transitions: [],
          },
        ],
        businessObjects: [],
        domainRules: [{ id: 1, logicalUuid: 'rule-1', title: 'Checkout rule', statement: 'Checkout must follow the rule.' }],
      } as any,
      workspaceCanWrite: () => false,
    });

    await render(
      <MemoryRouter>
        <HowItWorks />
      </MemoryRouter>
    );

    // Generate/regenerate button should be disabled in read-only mode
    const regenBtn = screen.getByText('how.regenerateBtn').closest('button');
    expect(regenBtn).toBeTruthy();
    expect(regenBtn?.disabled).toBe(true);

    // Flow creation / AI buttons should not be rendered
    expect(screen.queryByTitle('how.addFlowTooltip')).toBeNull();
    expect(screen.queryByTitle('how.aiAddFlowTooltip')).toBeNull();

    // Flow action buttons (edit, delete, add step) should not be rendered
    expect(screen.queryByTitle('how.editFlowTooltip')).toBeNull();
    expect(screen.queryByTitle('how.deleteFlowTooltip')).toBeNull();
    expect(screen.queryByTitle('how.addStepTooltip')).toBeNull();
  });
});
