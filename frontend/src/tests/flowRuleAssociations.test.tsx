import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { FlowRuleAssociations } from '../components/shared/FlowRuleAssociations';
import { FocusFlowCanvasModal } from '../components/shared/FocusFlowCanvasModal';
import { RightObjectPanel } from '../components/shared/RightObjectPanel';
import { DomainRule, FlowNode } from '../core/schema';
import { useWorkspaceStore } from '../store/useWorkspaceStore';

vi.mock('gsap', () => ({ default: { fromTo: vi.fn() } }));

const rules = [
  { id: 1, title: '步骤校验', statement: '输入不能为空', links: [
    { targetKind: 'flow_step', targetLogicalUuid: 'step-1', linkPurpose: 'applies_to' },
  ] },
  { id: 2, title: '分支规则', statement: '校验成功进入完成', links: [
    { targetKind: 'flow_transition', targetLogicalUuid: 'transition-1', linkPurpose: 'applies_to' },
  ] },
  { id: 3, title: '流程时限', statement: '两天内完成', links: [
    { targetKind: 'flow', targetLogicalUuid: 'flow-1', linkPurpose: 'applies_to' },
  ] },
  { id: 4, title: '来源证据', statement: '这是来源而非约束', links: [
    { targetKind: 'flow_step', targetLogicalUuid: 'step-1', linkPurpose: 'source' },
  ] },
] as DomainRule[];
const replaceTargetRules = vi.fn().mockResolvedValue(undefined);
const onOpenRule = vi.fn();
beforeEach(() => {
  vi.clearAllMocks();
  replaceTargetRules.mockResolvedValue(undefined);
  useWorkspaceStore.setState({ replaceTargetRules, workspaceCanWrite: () => true,
    selectedObject: null, ir: { domainRules: rules } as any });
});
afterEach(cleanup);

describe('Flow rule associations', () => {
  it.each(['flow_step', 'flow'] as const)('saves direct applies_to associations immediately for %s', async kind => {
    const target = kind === 'flow' ? 'flow-1' : 'step-1';
    render(<FlowRuleAssociations targetKind={kind} targetLogicalUuid={target} rules={rules}
      readOnly={false} onOpenRule={onOpenRule} />);
    const linked = screen.getByRole('checkbox', { name: kind === 'flow' ? '流程时限' : '步骤校验' }) as HTMLInputElement;
    const branch = screen.getByRole('checkbox', { name: '分支规则' }) as HTMLInputElement;
    expect(screen.getAllByRole('checkbox')).toHaveLength(rules.length);
    expect(linked.checked).toBe(true);
    expect(branch.checked).toBe(false);
    expect((screen.getByRole('checkbox', { name: '来源证据' }) as HTMLInputElement).checked).toBe(false);
    fireEvent.click(linked);
    expect(replaceTargetRules).toHaveBeenNthCalledWith(1, kind, target, []);
    await waitFor(() => expect(branch.disabled).toBe(false));
    fireEvent.click(branch);
    expect(replaceTargetRules).toHaveBeenNthCalledWith(2, kind, target, [2]);
    await waitFor(() => expect(branch.disabled).toBe(false));
    expect(linked.checked).toBe(false);
    expect(branch.checked).toBe(true);
  });

  it('restores saved associations after failure and retries on the next toggle', async () => {
    replaceTargetRules.mockRejectedValueOnce(new Error('network failed'));
    render(<FlowRuleAssociations targetKind="flow_step" targetLogicalUuid="step-1" rules={rules}
      readOnly={false} onOpenRule={onOpenRule} />);
    const checkbox = screen.getByRole('checkbox', { name: '步骤校验' }) as HTMLInputElement;
    fireEvent.click(checkbox);
    expect((await screen.findByRole('alert')).textContent).toContain('network failed');
    expect(checkbox.checked).toBe(true);
    expect(checkbox.disabled).toBe(false);
    expect(replaceTargetRules).toHaveBeenNthCalledWith(1, 'flow_step', 'step-1', []);
    fireEvent.click(checkbox);
    await waitFor(() => expect(checkbox.disabled).toBe(false));
    expect(replaceTargetRules).toHaveBeenCalledTimes(2);
    expect(replaceTargetRules).toHaveBeenNthCalledWith(2, 'flow_step', 'step-1', []);
    expect(checkbox.checked).toBe(false);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('opens the shared rule editor in read-only mode without enabling association edits', () => {
    render(<FlowRuleAssociations targetKind="flow_step" targetLogicalUuid="step-1" rules={rules}
      readOnly onOpenRule={onOpenRule} />);
    expect(screen.getAllByRole('checkbox').every(checkbox => (checkbox as HTMLInputElement).disabled)).toBe(true);
    fireEvent.click(screen.getByRole('checkbox', { name: '步骤校验' }));
    expect(replaceTargetRules).not.toHaveBeenCalled();
    expect((screen.getByRole('checkbox', { name: '步骤校验' }) as HTMLInputElement).checked).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: /步骤校验/ }));
    expect(onOpenRule).toHaveBeenCalledWith(rules[0]);
  });

  it('switches targets without retaining selections from another step', async () => {
    const props = { targetKind: 'flow_step' as const, rules, readOnly: false, onOpenRule };
    const { rerender } = render(<FlowRuleAssociations {...props} targetLogicalUuid="step-1" />);
    const branch = screen.getByRole('checkbox', { name: '分支规则' }) as HTMLInputElement;
    fireEvent.click(branch);
    await waitFor(() => expect(branch.disabled).toBe(false));
    expect(branch.checked).toBe(true);
    rerender(<FlowRuleAssociations {...props} targetLogicalUuid="step-2" />);
    expect(screen.getAllByRole('checkbox')).toHaveLength(rules.length);
    expect(screen.getAllByRole('checkbox').every(checkbox => !(checkbox as HTMLInputElement).checked)).toBe(true);
    expect(replaceTargetRules).toHaveBeenCalledTimes(1);
    expect(replaceTargetRules).toHaveBeenCalledWith('flow_step', 'step-1', [1, 2]);
  });

  it('shows step and branch associations separately in the full-screen editor', () => {
    const flow = {
      kind: 'flow', flowId: 1, logicalUuid: 'flow-1', flowName: '订单流程', flowDescription: '', featureIds: [],
      flowSteps: [1, 2].map(id => ({ kind: 'flow_step', stepId: id, logicalUuid: `step-${id}`,
        stepName: `步骤 ${id}`, stepDescription: '', stepType: 'actorAction', actorIds: [],
        inputBusinessObjectIds: [], outputBusinessObjectIds: [] })),
      transitions: [{ transitionId: 1, logicalUuid: 'transition-1', sourceStepId: 1, targetStepId: 2,
        label: '校验成功', ruleIds: [2] }],
    } as FlowNode;
    const onClose = vi.fn();
    render(<FocusFlowCanvasModal flow={flow} isOpen onClose={onClose} actors={[]} businessObjects={[]}
      onUpdateStep={vi.fn()} onAddStep={vi.fn()} onDeleteStep={vi.fn()} />);
    const direct = within(screen.getByTestId('flow_step-rule-associations'));
    expect((direct.getByRole('checkbox', { name: '步骤校验' }) as HTMLInputElement).checked).toBe(true);
    expect((direct.getByRole('checkbox', { name: '分支规则' }) as HTMLInputElement).checked).toBe(false);
    expect((direct.getByRole('checkbox', { name: '流程时限' }) as HTMLInputElement).checked).toBe(false);
    expect(screen.queryByTestId('flow-rule-associations')).toBeNull();
    fireEvent.click(screen.getByTestId('step-transition-item-1'));
    expect(screen.queryByTestId('flow_step-rule-associations')).toBeNull();
    expect((screen.getByTestId('rule-checkbox-2') as HTMLInputElement).checked).toBe(true);
    expect((screen.getByTestId('rule-checkbox-1') as HTMLInputElement).checked).toBe(false);
    expect((screen.getByTestId('rule-checkbox-3') as HTMLInputElement).checked).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /分支规则/ }));
    expect(useWorkspaceStore.getState().selectedObject?.kind).toBe('rule');
    expect(onClose).toHaveBeenCalled();
  });

  it('edits flow-wide associations from the right-side flow processing panel', async () => {
    useWorkspaceStore.setState({ selectedObject: {
      kind: 'flow', flowId: 1, logicalUuid: 'flow-1', flowName: '订单流程', flowDescription: '',
    } as any });
    render(<RightObjectPanel />);
    const panel = within(screen.getByTestId('flow-rule-associations'));
    const linked = panel.getByRole('checkbox', { name: '流程时限' }) as HTMLInputElement;
    const branch = panel.getByRole('checkbox', { name: '分支规则' }) as HTMLInputElement;
    expect(linked.checked).toBe(true);
    expect((panel.getByRole('checkbox', { name: '步骤校验' }) as HTMLInputElement).checked).toBe(false);
    expect(branch.checked).toBe(false);
    fireEvent.click(linked);
    expect(replaceTargetRules).toHaveBeenNthCalledWith(1, 'flow', 'flow-1', []);
    await waitFor(() => expect(branch.disabled).toBe(false));
    fireEvent.click(branch);
    expect(replaceTargetRules).toHaveBeenNthCalledWith(2, 'flow', 'flow-1', [2]);
    await waitFor(() => expect(branch.disabled).toBe(false));
    expect(branch.checked).toBe(true);
  });

  it('opens flow rule content in the shared processing panel', () => {
    useWorkspaceStore.setState({ selectedObject: {
      kind: 'flow', flowId: 1, logicalUuid: 'flow-1', flowName: '订单流程',
    } as any });
    render(<RightObjectPanel />);
    const button = within(screen.getByTestId('flow-rule-associations')).getByRole('button', { name: /流程时限/ });
    // happy-dom activates the enclosing label before React handles MouseEvent clicks.
    fireEvent(button, new Event('click', { bubbles: true, cancelable: true }));
    expect(useWorkspaceStore.getState().selectedObject).toEqual({ ...rules[2], kind: 'rule' });
    expect(screen.queryByTestId('flow-rule-associations')).toBeNull();
    expect(replaceTargetRules).not.toHaveBeenCalled();
  });

  it('keeps flow associations read-only in non-writable workspaces', () => {
    useWorkspaceStore.setState({ workspaceCanWrite: () => false, selectedObject: {
      kind: 'flow', flowId: 1, logicalUuid: 'flow-1', flowName: '订单流程',
    } as any });
    render(<RightObjectPanel />);
    const panel = within(screen.getByTestId('flow-rule-associations'));
    expect(panel.getByText('流程时限')).toBeDefined();
    expect(panel.queryByRole('button', { name: '编辑关联' })).toBeNull();
    expect(replaceTargetRules).not.toHaveBeenCalled();
  });
});
