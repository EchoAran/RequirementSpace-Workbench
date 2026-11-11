import { renderWithEffects as render } from './renderWithEffects';
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { FocusFlowCanvasModal } from '../components/shared/FocusFlowCanvasModal';
import { HowItWorks } from '../pages/HowItWorks';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import {
  selectTransitionLabel,
  selectFlowSummary,
  selectRulesForTarget,
  buildStepDetail,
} from '../core/selectors';
import { FlowNode, ActorNode, BusinessObjectNode, DomainRule, Finding } from '../core/schema';
import { workspaceApi } from '../lib/api';

vi.mock('../lib/api', () => ({
  workspaceApi: {
    getFlowObjectUsage: vi.fn(),
    generateFlows: vi.fn(),
    confirmFlowDraft: vi.fn(),
    getFlowPaths: vi.fn(),
    listProjectTasks: vi.fn().mockResolvedValue([]),
    listProjectMembers: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock('gsap', () => ({
  default: {
    fromTo: vi.fn(),
  },
}));

describe('P5: HOW Experience, Object Projection & Canvas Transition Enhancement', () => {
  const mockOnUpdateStep = vi.fn().mockResolvedValue(undefined);
  const mockOnAddStep = vi.fn().mockResolvedValue(undefined);
  const mockOnDeleteStep = vi.fn().mockResolvedValue(undefined);
  const mockOnUpdateTransition = vi.fn().mockResolvedValue(undefined);
  const mockOnDeleteTransition = vi.fn().mockResolvedValue(undefined);
  const mockOnClose = vi.fn();

  const sampleFlow: FlowNode = {
    kind: 'flow',
    flowId: 101,
    logicalUuid: 'flow-uuid-101',
    flowName: 'Checkout Flow',
    flowDescription: 'User checkout process',
    featureIds: [],
    flowSteps: [
      {
        kind: 'flow_step',
        stepId: 1,
        logicalUuid: 'step-uuid-1',
        stepName: 'Submit Order',
        stepDescription: 'User clicks place order button',
        stepType: 'actorAction',
        actorIds: [1],
        inputBusinessObjectIds: [501],
        outputBusinessObjectIds: [502],
      },
      {
        kind: 'flow_step',
        stepId: 2,
        logicalUuid: 'step-uuid-2',
        stepName: 'Process Payment',
        stepDescription: 'System interacts with gateway',
        stepType: 'systemAction',
        actorIds: [],
        inputBusinessObjectIds: [502],
        outputBusinessObjectIds: [],
      },
    ],
    transitions: [
      {
        transitionId: 301,
        logicalUuid: 'trans-uuid-301',
        flowId: 101,
        sourceStepId: 1,
        targetStepId: 2,
        label: 'Payment Verified',
        conditionText: 'payment.status == "OK"',
        isDefault: true,
        semanticTags: ['happy_path'],
        confirmationStatus: 'confirmed',
        ruleIds: [1],
      },
    ],
  };

  const sampleFlow2: FlowNode = {
    kind: 'flow',
    flowId: 102,
    logicalUuid: 'flow-uuid-102',
    flowName: 'Refund Flow',
    flowDescription: 'User refund request process',
    featureIds: [],
    flowSteps: [
      {
        kind: 'flow_step',
        stepId: 11,
        logicalUuid: 'step-uuid-11',
        stepName: 'Request Refund',
        stepDescription: 'Request refund on order',
        stepType: 'actorAction',
        actorIds: [1],
        inputBusinessObjectIds: [501], // Shared BO with Flow 101
        outputBusinessObjectIds: [],
      },
    ],
    transitions: [],
  };

  const sampleActors: ActorNode[] = [
    { kind: 'actor', actorId: 1, actorName: 'Buyer', actorDescription: '' },
  ];

  const sampleBusinessObjects: BusinessObjectNode[] = [
    {
      kind: 'business_object',
      businessObjectId: 501,
      logicalUuid: 'bo-uuid-501',
      businessObjectName: 'Order',
      businessObjectDescription: 'Customer order entity',
      businessObjectAttributes: [
        {
          kind: 'business_object_attribute',
          businessObjectAttributeId: 1001,
          businessObjectAttributeName: 'order_id',
          businessObjectAttributeType: 'string',
          businessObjectAttributeDescription: 'Primary order identifier',
          businessObjectAttributeExample: 'ORD-12345',
        },
      ],
      confirmationStatus: 'confirmed',
    },
    {
      kind: 'business_object',
      businessObjectId: 502,
      logicalUuid: 'bo-uuid-502',
      businessObjectName: 'PaymentRecord',
      businessObjectDescription: 'Payment transaction record',
      businessObjectAttributes: [],
      confirmationStatus: 'confirmed',
    },
  ];

  const sampleRules: DomainRule[] = [
    {
      id: 1,
      logicalUuid: 'rule-uuid-1',
      projectId: 1,
      title: 'Order Total Verification Rule',
      statement: 'Order total must match sum of line items',
      origin: 'manual',
      confirmationStatus: 'confirmed',
      links: [
        {
          id: 101,
          logicalUuid: 'link-uuid-101',
          projectId: 1,
          ruleId: 1,
          targetKind: 'flow_step',
          targetLogicalUuid: 'step-uuid-1',
          linkPurpose: 'applies_to',
          contextText: '',
          createdAt: '2026-09-08T00:00:00Z',
          updatedAt: '2026-09-08T00:00:00Z',
        },
      ],
      childRuleIds: [],
      createdAt: '2026-09-08T00:00:00Z',
      updatedAt: '2026-09-08T00:00:00Z',
    },
  ];

  const sampleFeatures = [
    {
      featureId: 1,
      logicalUuid: 'feature-uuid-1',
      featureName: 'Checkout Feature',
      featureDescription: 'User checkout feature',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    useWorkspaceStore.setState({
      workspaceCanWrite: () => true,
      ir: {
        projectId: 'project-101',
        features: sampleFeatures,
        actors: sampleActors,
        businessObjects: sampleBusinessObjects,
        flows: [sampleFlow, sampleFlow2],
        domainRules: sampleRules,
        findings: [],
      } as any,
      flowPathProjections: {
        101: [
          {
            pathId: 'path-1',
            name: 'Standard Happy Path',
            isMain: true,
            status: 'valid',
            stepIds: [1, 2],
            stepLogicalUuids: ['step-uuid-1', 'step-uuid-2'],
            transitionIds: [301],
            transitionLogicalUuids: ['trans-uuid-301'],
            summary: 'Normal checkout completion',
          },
        ],
      },
      flowObjectUsages: {
        101: [
          {
            businessObjectId: 501,
            logicalUuid: 'bo-uuid-501',
            name: 'Order',
            description: 'Customer order entity',
            confirmationStatus: 'confirmed',
            attributes: [
              { id: 1001, name: 'order_id', dataType: 'string', description: 'Primary order identifier', example: 'ORD-12345' }
            ],
            usedByStepIds: [1],
            inputAtStepIds: [1],
            outputAtStepIds: [],
            otherFlowsCount: 1,
            otherFlowNames: ['Refund Flow'],
          },
          {
            businessObjectId: 502,
            logicalUuid: 'bo-uuid-502',
            name: 'PaymentRecord',
            description: 'Payment transaction record',
            confirmationStatus: 'confirmed',
            attributes: [],
            usedByStepIds: [1, 2],
            inputAtStepIds: [2],
            outputAtStepIds: [1],
            otherFlowsCount: 0,
            otherFlowNames: [],
          },
        ] as any,
      },
      flowObjectUsageLoading: {},
      flowObjectUsageErrors: {},
      flowPathLoading: {},
      flowPathErrors: {},
    });

    vi.mocked(workspaceApi.getFlowPaths).mockImplementation(async (_projectId: string, flowId: number) => {
      if (flowId === 101) {
        return {
          paths: [
            {
              pathId: 'path-1',
              name: 'Standard Happy Path',
              isMain: true,
              status: 'valid',
              stepIds: [1, 2],
              summary: 'Normal checkout completion',
            },
          ],
        } as any;
      }
      return { paths: [] } as any;
    });

    vi.mocked(workspaceApi.getFlowObjectUsage).mockImplementation(async (_projectId: string, flowId: number) => {
      if (flowId === 101) {
        return {
          flowId: 101,
          objects: [
            {
              businessObjectId: 501,
              name: 'Order',
              description: 'Customer order entity',
              confirmationStatus: 'confirmed',
              attributes: [
                { attributeId: 1001, name: 'order_id', type: 'string', description: 'Primary order identifier' }
              ],
              inputAtStepIds: [1],
              outputAtStepIds: [],
              otherFlowsCount: 1,
              otherFlowNames: ['Refund Flow'],
            },
            {
              businessObjectId: 502,
              name: 'PaymentRecord',
              description: 'Payment transaction record',
              confirmationStatus: 'confirmed',
              attributes: [],
              inputAtStepIds: [2],
              outputAtStepIds: [1],
              otherFlowsCount: 0,
              otherFlowNames: [],
            },
          ],
        } as any;
      }
      return { flowId, objects: [] } as any;
    });
  });

  describe('1. Selectors & Projection Quality', () => {
    it('selectTransitionLabel prioritizes label over conditionText and detects unspecified condition', () => {
      // Prioritizes label
      const labeled = selectTransitionLabel({ label: 'Approve', conditionText: 'score > 80', isDefault: false });
      expect(labeled.text).toBe('Approve');
      expect(labeled.isConditionFallback).toBe(false);
      expect(labeled.isUnspecified).toBe(false);

      // Fallback to conditionText
      const fallback = selectTransitionLabel({ conditionText: 'score > 80', isDefault: false });
      expect(fallback.text).toBe('score > 80');
      expect(fallback.isConditionFallback).toBe(true);
      expect(fallback.isUnspecified).toBe(false);

      // Unspecified condition
      const unspecified = selectTransitionLabel({ isDefault: false });
      expect(unspecified.isUnspecified).toBe(true);
      expect(unspecified.text).toBe('未说明流转条件');

      // Default transition
      const defaultTrans = selectTransitionLabel({ isDefault: true });
      expect(defaultTrans.isDefault).toBe(true);
    });

    it('buildStepDetail contains no fictitious data and populates real relatedIssueIds', () => {
      const detail = buildStepDetail(useWorkspaceStore.getState().ir, 1);
      expect((detail as any).relatedPages).toBeUndefined();
      expect(detail.inputs.length).toBeGreaterThanOrEqual(1);
      expect(detail.relatedIssueIds).toEqual([]);
    });

    it('selectFlowSummary counts findings matching real FindingTarget contract', () => {
      const findings: Finding[] = [
        {
          findingId: 'f1',
          type: 'issue',
          code: 'UNLINKED_STEP',
          severity: 'blocking',
          title: 'Step blocking issue',
          description: 'Step has error',
          stage: 'how',
          target: { targetType: 'flow_step', targetId: 1 },
          blockingScope: 'stage_transition',
        },
        {
          findingId: 'f2',
          type: 'issue',
          code: 'DEAD_END_TRANSITION',
          severity: 'warning',
          title: 'Transition warning',
          description: 'Transition warning description',
          stage: 'how',
          target: { targetType: 'flow_transition', targetId: 301 },
          blockingScope: 'none',
        },
        {
          findingId: 'f3',
          type: 'issue',
          code: 'FLOW_DISCONNECTED',
          severity: 'warning',
          title: 'Flow warning',
          description: 'Flow warning description',
          stage: 'how',
          target: { targetType: 'flow', targetId: 101 },
          blockingScope: 'none',
        },
      ];

      const summary = selectFlowSummary(sampleFlow, sampleRules, findings);
      expect(summary.blockingFindingsCount).toBe(1);
      expect(summary.warningFindingsCount).toBe(2);
    });

    it('selectFlowSummary calculates accurate metrics for steps, transitions, rules, and BOs', () => {
      const summary = selectFlowSummary(sampleFlow, sampleRules, []);
      expect(summary.stepCount).toBe(2);
      expect(summary.transitionCount).toBe(1);
      expect(summary.ruleCount).toBe(1); // Linked via RuleLink
      expect(summary.boCount).toBe(2); // 501 and 502
      expect(summary.blockingFindingsCount).toBe(0);
    });

    it('loadFlowPaths tracks loading, handles errors cleanly without silent fallback, and provides retry', async () => {
      useWorkspaceStore.setState({
        ir: { ...(useWorkspaceStore.getState().ir || {}), projectId: '1' } as any,
      });
      vi.mocked(workspaceApi.getFlowPaths).mockRejectedValueOnce(new Error('Network error loading paths'));

      await expect(useWorkspaceStore.getState().loadFlowPaths(101)).rejects.toThrow('Network error loading paths');
      expect(useWorkspaceStore.getState().flowPathErrors[101]).toBe('Network error loading paths');
      expect(useWorkspaceStore.getState().flowPathLoading[101]).toBe(false);

      // Now retry with success
      vi.mocked(workspaceApi.getFlowPaths).mockResolvedValueOnce({
        paths: [
          { pathId: 'path-1', name: 'Main Path', isMain: true, status: 'valid', stepIds: [1, 2] },
        ],
      } as any);

      const paths = await useWorkspaceStore.getState().loadFlowPaths(101);
      expect(paths.length).toBe(1);
      expect(useWorkspaceStore.getState().flowPathProjections[101].length).toBe(1);
      expect(useWorkspaceStore.getState().flowPathErrors[101]).toBeNull();
    });

    it('selectRulesForTarget retrieves linked domain rules via RuleLinks', () => {
      const rules = selectRulesForTarget(useWorkspaceStore.getState().ir, 'flow_step', 'step-uuid-1');
      expect(rules.length).toBe(1);
      expect(rules[0].title).toBe('Order Total Verification Rule');
    });
  });

  describe('2. FocusFlowCanvasModal Canvas & Transition Enhancement', () => {
    it('renders interactive edge label pill on the canvas and displays transition attributes', async () => {
      await render(
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

      // Edge label pill should be rendered
      const labelPill = screen.getByTestId('transition-label-301');
      expect(labelPill).toBeDefined();
      expect(labelPill.textContent).toContain('Payment Verified');
      expect(labelPill.textContent).toContain('默认'); // Default badge
    });

    it('renders path projection selector dropdown and highlights steps in selected path', async () => {
      await render(
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

      // Path Projection dropdown should be visible in toolbar
      const pathSelect = await screen.findByTestId('path-projection-select');
      expect(pathSelect).toBeDefined();
      expect(pathSelect.textContent).toContain('Standard Happy Path');

      // Select path
      await act(async () => fireEvent.change(pathSelect, { target: { value: 'path-1' } }));

      // Step cards should display the path badge
      const stepCards = screen.getAllByText('主路径');
      expect(stepCards.length).toBeGreaterThanOrEqual(1);
    });

    it('displays linked DomainRules in the Step Inspector drawer', async () => {
      await render(
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

      // Step 1 is selected by default; verify linked domain rule appears in inspector
      const ruleItem = screen.getByTestId('step-linked-rule-1');
      expect(ruleItem).toBeDefined();
      expect(ruleItem.textContent).toContain('Order Total Verification Rule');
      expect(ruleItem.textContent).toContain('Order total must match sum of line items');
    });

    it('allows clicking an edge to open Transition Inspector and editing attributes', async () => {
      await render(
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

      // Click transition edge
      const hitArea = screen.getByTestId('transition-hitarea-301');
      await act(async () => fireEvent.click(hitArea));

      // Transition inspector should be open
      expect(screen.getByText('分支连线详情')).toBeDefined();

      // Edit condition and save
      const conditionInput = screen.getByTestId('transition-condition-input');
      await act(async () => fireEvent.change(conditionInput, { target: { value: 'payment.status == "SUCCESS"' } }));

      const saveBtn = screen.getByTestId('save-transition-button');
      await act(async () => fireEvent.click(saveBtn));

      expect(mockOnUpdateTransition).toHaveBeenCalledWith(101, 301, expect.objectContaining({
        conditionText: 'payment.status == "SUCCESS"',
      }));
    });

    it('has full accessibility attributes, dialog role, close button aria-label and accessible list', async () => {
      await render(
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

      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeDefined();
      expect(dialog.getAttribute('aria-modal')).toBe('true');
      expect(dialog.getAttribute('aria-labelledby')).toBe('focus-flow-modal-title');

      const closeBtn = screen.getByRole('button', { name: '关闭' });
      expect(closeBtn).toBeDefined();

      const accessibleView = screen.getByRole('region', { name: '流程步骤与流转可访问列表' });
      expect(accessibleView).toBeDefined();
      expect(accessibleView.textContent).toContain('Checkout Flow');
    });

    it('supports interactive edge editing in screen reader accessible view', async () => {
      await render(
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

      const accessibleView = screen.getByRole('region', { name: '流程步骤与流转可访问列表' });
      expect(accessibleView).toBeDefined();

      // 1. Step selection button
      const stepBtn = within(accessibleView).getByRole('button', { name: /^选择并编辑步骤 Submit Order/ });
      await act(async () => fireEvent.click(stepBtn));
      expect(screen.getByText('步骤属性')).toBeDefined();

      // 2. Transition selection button
      const editTransitionBtn = within(accessibleView).getByRole('button', { name: /^选择并编辑连线 Submit Order 至 Process Payment/ });
      await act(async () => fireEvent.click(editTransitionBtn));
      expect(screen.getByText('分支连线详情')).toBeDefined();

      // 3. Toggle default branch button
      const toggleDefaultBtn = within(accessibleView).getByRole('button', { name: '取消默认分支' });
      await act(async () => fireEvent.click(toggleDefaultBtn));
      expect(mockOnUpdateTransition).toHaveBeenCalledWith(101, 301, { isDefault: false });

      // 4. Disconnect button
      const disconnectBtn = within(accessibleView).getByRole('button', { name: '断开连接' });
      await act(async () => fireEvent.click(disconnectBtn));
      expect(mockOnDeleteTransition).toHaveBeenCalledWith(101, 301);
    });

    it('renders path projection error badge with retry button when loading paths fails', async () => {
      useWorkspaceStore.setState({
        ir: { ...(useWorkspaceStore.getState().ir || {}), projectId: '1' } as any,
      });
      vi.mocked(workspaceApi.getFlowPaths).mockImplementation(async () => {
        throw new Error('Failed to fetch paths');
      });

      await render(
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

      const errorBadge = await screen.findByTestId('path-projection-error');
      expect(errorBadge).toBeDefined();
      expect(errorBadge.textContent).toContain('路径加载失败');

      const retryBtn = screen.getByTestId('path-projection-retry-button');
      expect(retryBtn).toBeDefined();
      await act(async () => fireEvent.click(retryBtn));
    });

    it('supports keyboard selection on transition pill and step node card', async () => {
      await render(
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

      // Select transition via keydown on pill
      const labelPill = screen.getByTestId('transition-label-301');
      await act(async () => fireEvent.keyDown(labelPill, { key: 'Enter' }));
      expect(screen.getByText('分支连线详情')).toBeDefined();

      // Select step via keydown on step card
      const stepCards = document.querySelectorAll('.flow-node-card');
      expect(stepCards.length).toBeGreaterThanOrEqual(1);
      await act(async () => fireEvent.keyDown(stepCards[0], { key: ' ' }));
      expect(screen.getByText('步骤属性')).toBeDefined();
    });

    it('edits transition position order and passes position to onUpdateTransition', async () => {
      await render(
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

      const hitArea = screen.getByTestId('transition-hitarea-301');
      await act(async () => fireEvent.click(hitArea));

      const posInput = screen.getByTestId('transition-position-input');
      expect(posInput).toBeDefined();
      await act(async () => fireEvent.change(posInput, { target: { value: '2' } }));

      const saveBtn = screen.getByTestId('save-transition-button');
      await act(async () => fireEvent.click(saveBtn));

      expect(mockOnUpdateTransition).toHaveBeenCalledWith(101, 301, expect.objectContaining({
        position: 2,
      }));
    });

    it('displays related findings and choices in step and transition inspectors', async () => {
      useWorkspaceStore.setState({
        ir: {
          ...useWorkspaceStore.getState().ir,
          findings: [
            {
              findingId: 'step-issue-1',
              code: 'STEP_ERR',
              severity: 'error',
              title: 'Step Error Finding',
              description: 'Step 1 has missing output',
              stage: 'how',
              target: { targetType: 'flow_step', targetId: 1 },
              blockingScope: 'stage',
            },
            {
              findingId: 'trans-issue-301',
              code: 'TRANS_WARN',
              severity: 'warning',
              title: 'Transition Warning Finding',
              description: 'Transition condition is ambiguous',
              stage: 'how',
              target: { targetType: 'flow_transition', targetId: 301 },
              blockingScope: 'none',
            },
          ] as any,
        } as any,
        backendChoiceGroups: {
          g1: {
            id: 'g1',
            status: 'open',
            generationType: 'flow_refinement',
            choices: [
              { id: 'c1', stepId: 1, title: 'AI Suggested Branch Option' }
            ]
          } as any
        }
      });

      await render(
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

      // Step 1 selected by default -> verify step finding and choice
      const stepFinding = screen.getByTestId('step-finding-step-issue-1');
      expect(stepFinding).toBeDefined();
      expect(stepFinding.textContent).toContain('Step Error Finding');
      expect(stepFinding.textContent).toContain('阻断');

      const stepChoice = screen.getByTestId('step-choice-0');
      expect(stepChoice).toBeDefined();
      expect(stepChoice.textContent).toContain('AI Suggested Branch Option');

      // Click transition edge -> verify transition finding
      const hitArea = screen.getByTestId('transition-hitarea-301');
      await act(async () => fireEvent.click(hitArea));

      const transFinding = screen.getByTestId('transition-finding-trans-issue-301');
      expect(transFinding).toBeDefined();
      expect(transFinding.textContent).toContain('Transition Warning Finding');
      expect(transFinding.textContent).toContain('告警');
    });
  });

  describe('3. HowItWorks Page IA & Business Object Projection', () => {
    it('renders RuleSection above FlowSection and removes standalone Business Object section', async () => {
      await render(
        <MemoryRouter>
          <HowItWorks />
        </MemoryRouter>
      );

      // Section title for rules
      const ruleSectionHeader = screen.getByText('业务规则与约束');
      expect(ruleSectionHeader).toBeDefined();

      // Section title for flows
      const flowSectionHeader = screen.getByText('系统业务流程');
      expect(flowSectionHeader).toBeDefined();

      // RuleSection appears before FlowSection in DOM order
      expect(ruleSectionHeader.compareDocumentPosition(flowSectionHeader) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

      // Top-level standalone business objects title is not rendered as a standalone section
      // The only references are within the Flow card as projected items
      const standaloneBoHeader = screen.queryByText('业务数据对象');
      expect(standaloneBoHeader).toBeNull();
    });

    it('uses the canvas as the only flow view', async () => {
      await render(
        <MemoryRouter>
          <HowItWorks />
        </MemoryRouter>
      );

      expect(screen.queryByRole('button', { name: '列表视图' })).toBeNull();
      expect(screen.queryByRole('button', { name: '图形视图' })).toBeNull();
      expect(screen.getAllByRole('button', { name: '全屏专注' }).length).toBeGreaterThan(0);
    });

    it('renders Flow card summary badges (steps, transitions, rules, objects)', async () => {
      await render(
        <MemoryRouter>
          <HowItWorks />
        </MemoryRouter>
      );

      // Summary badges inside Checkout Flow card
      expect(screen.getAllByText(/2\s*步骤/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/1\s*分支流转/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/1\s*关联规则/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/2\s*涉及对象/).length).toBeGreaterThanOrEqual(1);
    });

    it('embeds Involved Business Objects projection in expanded Flow card with multi-flow warning', async () => {
      await render(
        <MemoryRouter>
          <HowItWorks />
        </MemoryRouter>
      );

      // "Order" BO is shared with "Refund Flow", so it must display the shared notice
      const orderProjection = await screen.findByTestId('flow-bo-projection-101-501');
      expect(orderProjection).toBeDefined();
      expect(orderProjection.textContent).toContain('Order');
      expect(orderProjection.textContent).toContain('Refund Flow');
      expect(orderProjection.textContent).toContain('入: #1');

      // "PaymentRecord" BO is not shared
      const paymentProjection = await screen.findByTestId('flow-bo-projection-101-502');
      expect(paymentProjection).toBeDefined();
      expect(paymentProjection.textContent).toContain('PaymentRecord');
      expect(paymentProjection.textContent).toContain('出: #1');
      expect(paymentProjection.textContent).toContain('入: #2');

      const boProjectionCards = screen.getAllByTestId(/flow-bo-projection-/);
      expect(boProjectionCards.length).toBeGreaterThanOrEqual(2);
    });

    it('clicking an involved Business Object opens it in the right object panel', async () => {
      await render(
        <MemoryRouter>
          <HowItWorks />
        </MemoryRouter>
      );

      // Click on the Order projection card
      const orderProjection = await screen.findByTestId('flow-bo-projection-101-501');
      await act(async () => fireEvent.click(orderProjection));

      // Right object panel opens with BO basics and attributes
      expect(await screen.findByDisplayValue('Order')).toBeDefined();
      expect(screen.getByText('order_id')).toBeDefined();
      expect(screen.getByText('Primary order identifier')).toBeDefined();
    });

    it('displays error card and retry button when flowObjectUsageErrors is set, without silent fallback', async () => {
      const loadFlowObjectUsageSpy = vi.fn().mockResolvedValue(undefined);
      useWorkspaceStore.setState({
        flowObjectUsages: {},
        flowObjectUsageLoading: {},
        flowObjectUsageErrors: { 101: 'Network Timeout 504' },
        loadFlowObjectUsage: loadFlowObjectUsageSpy,
      });

      await render(
        <MemoryRouter>
          <HowItWorks />
        </MemoryRouter>
      );

      const errorCard = screen.getByTestId('flow-bo-error-101');
      expect(errorCard).toBeDefined();
      expect(errorCard.textContent).toContain('Network Timeout 504');

      // Click retry
      const retryBtn = screen.getByRole('button', { name: '重试' });
      await act(async () => fireEvent.click(retryBtn));
      expect(loadFlowObjectUsageSpy).toHaveBeenCalledWith(101);
    });

    it('renders Flow Draft Preview Banner after FlowSection in DOM order', async () => {
      useWorkspaceStore.setState({
        activeDraft: {
          draftId: 'draft-flow-1',
          flows: [
            { flow_name: 'AI Generated Draft Flow', flow_description: 'Draft description', steps: [] }
          ]
        } as any,
        activeDraftType: 'flow',
      });

      await render(
        <MemoryRouter>
          <HowItWorks />
        </MemoryRouter>
      );

      const flowSectionHeader = screen.getByText('系统业务流程');
      const draftBannerTitle = screen.getByText(/AI 推荐的业务流程与实体草稿已生成|AI-Recommended Workflow/);
      expect(flowSectionHeader).toBeDefined();
      expect(draftBannerTitle).toBeDefined();

      // draft banner appears AFTER flowSectionHeader in document order
      expect(flowSectionHeader.compareDocumentPosition(draftBannerTitle) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });

    it('has aria-expanded and aria-controls on Flow card and RuleSection collapse headers', async () => {
      await render(
        <MemoryRouter>
          <HowItWorks />
        </MemoryRouter>
      );

      // RuleSection collapse button
      const ruleCollapseBtn = document.querySelector('button[aria-controls="how-rule-section-content"]');
      expect(ruleCollapseBtn).not.toBeNull();
      expect(ruleCollapseBtn?.getAttribute('aria-expanded')).toBe('true');
      expect(ruleCollapseBtn?.getAttribute('aria-controls')).toBe('how-rule-section-content');

      // Flow card collapse button
      const flowCollapseBtn = document.querySelector('button[aria-controls="flow-content-101"]');
      expect(flowCollapseBtn).not.toBeNull();
      expect(flowCollapseBtn?.getAttribute('aria-expanded')).toBe('true');
      expect(flowCollapseBtn?.getAttribute('aria-controls')).toBe('flow-content-101');
    });
  });
});
