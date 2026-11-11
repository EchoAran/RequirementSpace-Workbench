import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { RuleSection } from '../components/how/RuleSection';
import { useWorkspaceStore } from '../store/useWorkspaceStore';

vi.mock('react-i18next', () => ({
  initReactI18next: {
    type: '3rdParty',
    init: vi.fn(),
  },
  useTranslation: () => ({
    t: (key: string, options?: any) => {
      if (options?.defaultValue) return options.defaultValue;
      return key;
    },
    i18n: {
      changeLanguage: vi.fn().mockResolvedValue(true),
      language: 'zh-CN',
    },
  }),
}));

const renderRuleSection = (props?: { readOnly?: boolean }) =>
  render(
    <MemoryRouter>
      <RuleSection {...props} />
    </MemoryRouter>
  );

describe('RuleSection Component', () => {
  const mockCreateDomainRule = vi.fn();
  const mockUpdateDomainRule = vi.fn();
  const mockDeleteDomainRule = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    useWorkspaceStore.setState({
      ir: {
        domainRules: [],
      } as any,
      createDomainRule: mockCreateDomainRule,
      updateDomainRule: mockUpdateDomainRule,
      deleteDomainRule: mockDeleteDomainRule,
      workspaceCanWrite: () => true,
      selectedObject: null,
      selectedObjectId: null,
    } as any);
  });

  it('renders the empty rule state with creation actions', () => {
    renderRuleSection();
    expect(screen.getByText('how.domainRules.stateNotStartedTitle')).toBeDefined();
    expect(screen.getByText('how.domainRules.stateNotStartedDesc')).toBeDefined();
    expect(screen.getByText('how.domainRules.addFirstRule')).toBeDefined();
  });

  it('renders State 3: active rules list with badges and links', () => {
    useWorkspaceStore.setState({
      ir: {
        domainRules: [
          {
            id: 1,
            logicalUuid: 'rule-uuid-1',
            projectId: 1,
            title: 'Payment Idempotency Rule',
            statement: 'Orders with same idempotency key must not charge twice.',
            origin: 'manual',
            confirmationStatus: 'confirmed',
            links: [
              {
                id: 10,
                logicalUuid: 'link-uuid-10',
                projectId: 1,
                ruleId: 1,
                targetKind: 'flow_step',
                targetLogicalUuid: 'step-uuid-1',
                linkPurpose: 'applies_to',
                contextText: '',
                createdAt: '',
                updatedAt: '',
              },
            ],
            childRuleIds: [],
            createdAt: '',
            updatedAt: '',
          },
        ],
      } as any,
    } as any);

    renderRuleSection();
    expect(screen.getByText('Payment Idempotency Rule')).toBeDefined();
    expect(screen.getByText('Orders with same idempotency key must not charge twice.')).toBeDefined();
    // 关联对象展示：无法解析对象时回退到类型标识（幽灵测量行会渲染一份副本）
    expect(screen.getByText('how.domainRules.linkedObjects')).toBeDefined();
    expect(screen.getAllByText('flow_step').length).toBeGreaterThan(0);
  });

  it('renders rules as hierarchy when parent rule exists', () => {
    useWorkspaceStore.setState({
      ir: {
        domainRules: [
          {
            id: 1, logicalUuid: 'u1', projectId: 1, title: 'Parent Rule',
            statement: 'Parent statement.', origin: 'manual', confirmationStatus: 'confirmed',
            links: [], childRuleIds: [2], parentRuleId: null, createdAt: '', updatedAt: '',
          },
          {
            id: 2, logicalUuid: 'u2', projectId: 1, title: 'Child Rule',
            statement: 'Child statement.', origin: 'manual', confirmationStatus: 'confirmed',
            links: [], childRuleIds: [], parentRuleId: 1, createdAt: '', updatedAt: '',
          },
        ],
      } as any,
    } as any);

    renderRuleSection();
    expect(screen.getByText('Parent Rule')).toBeDefined();
    expect(screen.getByText('Child Rule')).toBeDefined();
  });

  it('disables and hides write action buttons when readOnly=true', () => {
    useWorkspaceStore.setState({
      ir: {
        domainRules: [
          {
            id: 1,
            logicalUuid: 'rule-uuid-1',
            projectId: 1,
            title: 'Read Only Rule',
            statement: 'Statements here.',
            origin: 'manual',
            confirmationStatus: 'needs_confirmation',
            links: [],
            childRuleIds: [],
            createdAt: '',
            updatedAt: '',
          },
        ],
      } as any,
      workspaceCanWrite: () => false,
    } as any);

    renderRuleSection({ readOnly: true });
    expect(screen.queryByText('how.domainRules.addRule')).toBeNull();
    expect(screen.queryByTitle('common.edit')).toBeNull();
    expect(screen.queryByTitle('common.delete')).toBeNull();
  });

  it('allows creating a domain rule via modal', async () => {
    mockCreateDomainRule.mockResolvedValueOnce({ id: 2 });
    renderRuleSection();

    const addBtn = screen.getByLabelText('how.domainRules.addRule');
    fireEvent.click(addBtn);

    expect(screen.getByText('how.domainRules.createModalTitle')).toBeDefined();

    const titleInput = screen.getByPlaceholderText('how.domainRules.titlePlaceholder');
    const statementInput = screen.getByPlaceholderText('how.domainRules.statementPlaceholder');

    fireEvent.change(titleInput, { target: { value: 'New Test Rule' } });
    fireEvent.change(statementInput, { target: { value: 'Every request must have auth header.' } });

    const submitBtn = screen.getByText('common.create');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockCreateDomainRule).toHaveBeenCalledWith({
        title: 'New Test Rule',
        statement: 'Every request must have auth header.',
        origin: 'manual',
        confirmationStatus: 'needs_confirmation',
        parentRuleId: null,
      });
    });
  });

  it('opens the right panel with object details when clicking a link chip (no navigation)', async () => {
    useWorkspaceStore.setState({
      ir: {
        domainRules: [
          {
            id: 1,
            logicalUuid: 'rule-uuid-1',
            projectId: 1,
            title: 'Linked Rule',
            statement: 'Statement.',
            origin: 'manual',
            confirmationStatus: 'confirmed',
            links: [
              {
                id: 10,
                logicalUuid: 'link-uuid-10',
                projectId: 1,
                ruleId: 1,
                targetKind: 'flow_step',
                targetLogicalUuid: 'step-uuid-1',
                linkPurpose: 'applies_to',
                contextText: '',
                createdAt: '',
                updatedAt: '',
              },
            ],
            childRuleIds: [],
            createdAt: '',
            updatedAt: '',
          },
        ],
        flows: [
          {
            kind: 'flow',
            flowId: 3,
            flowName: 'Main Flow',
            flowDescription: '',
            featureIds: [],
            flowSteps: [
              {
                kind: 'flow_step',
                stepId: 77,
                stepName: 'Submit Order',
                stepDescription: '',
                stepType: 'actorAction',
                actorIds: [],
                inputBusinessObjectIds: [],
                outputBusinessObjectIds: [],
                logicalUuid: 'step-uuid-1',
              },
            ],
            logicalUuid: 'flow-uuid-3',
          },
        ],
      } as any,
    } as any);

    renderRuleSection();

    const chip = screen.getAllByTitle('Submit Order')[0];
    fireEvent.click(chip);

    await waitFor(() => {
      const selected = useWorkspaceStore.getState().selectedObject as any;
      expect(selected?.kind).toBe('flow_step');
      expect(selected?.stepId).toBe(77);
    });
  });

  it('switches to the compact view and keeps rules visible', () => {
    useWorkspaceStore.setState({
      ir: {
        domainRules: [
          {
            id: 1, logicalUuid: 'u1', projectId: 1, title: 'Some Rule',
            statement: 'Statement.', origin: 'manual', confirmationStatus: 'confirmed',
            links: [], childRuleIds: [], createdAt: '', updatedAt: '',
          },
        ],
      } as any,
    } as any);

    renderRuleSection();

    expect(screen.getByText('Some Rule')).toBeDefined();

    const toggleBtn = screen.getByLabelText('how.domainRules.compactView');
    fireEvent.click(toggleBtn);

    expect(screen.getByText('Some Rule')).toBeDefined();
  });

  it('opens the right object panel editor when clicking a rule card', async () => {
    const rule = {
      id: 6,
      logicalUuid: 'rule-uuid-6',
      projectId: 1,
      title: 'Clickable Rule',
      statement: 'Card click opens editor.',
      origin: 'manual' as const,
      confirmationStatus: 'confirmed',
      links: [],
      childRuleIds: [],
      createdAt: '',
      updatedAt: '',
    };

    useWorkspaceStore.setState({ ir: { domainRules: [rule] } } as any);

    renderRuleSection();

    fireEvent.click(screen.getByText('Clickable Rule'));

    await waitFor(() => {
      const selected = useWorkspaceStore.getState().selectedObject as any;
      expect(selected?.kind).toBe('rule');
      expect(selected?.id).toBe(6);
    });
  });

  it('allows deleting a domain rule after confirmation prompt', async () => {
    window.confirm = vi.fn().mockReturnValue(true);

    const ruleToDelete = {
      id: 9,
      logicalUuid: 'rule-uuid-9',
      projectId: 1,
      title: 'Rule to Delete',
      statement: 'Will be deleted.',
      origin: 'manual' as const,
      confirmationStatus: 'confirmed',
      links: [],
      childRuleIds: [],
      createdAt: '',
      updatedAt: '',
    };

    useWorkspaceStore.setState({
      ir: {
        domainRules: [ruleToDelete],
      } as any,
    } as any);

    renderRuleSection();

    const deleteBtn = screen.getByTitle('common.delete');
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(mockDeleteDomainRule).toHaveBeenCalledWith(9);
    });
  });

  it('collapses and expands the rules content area', () => {
    useWorkspaceStore.setState({
      ir: {
        domainRules: [
          {
            id: 1, logicalUuid: 'u1', projectId: 1, title: 'Some Rule',
            statement: 'Statement.', origin: 'manual', confirmationStatus: 'confirmed',
            links: [], childRuleIds: [], createdAt: '', updatedAt: '',
          },
        ],
      } as any,
    } as any);

    renderRuleSection();

    const content = document.getElementById('how-rule-section-content');
    expect(content).not.toBeNull();

    const collapseBtn = screen.getByTitle('common.collapse');
    fireEvent.click(collapseBtn);
    expect(document.getElementById('how-rule-section-content')).toBeNull();

    const expandBtn = screen.getByTitle('common.expand');
    fireEvent.click(expandBtn);
    expect(document.getElementById('how-rule-section-content')).not.toBeNull();
  });
});
