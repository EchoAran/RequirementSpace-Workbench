import { Choice, ChoiceGroup, Issue, Proposal, RequirementSpaceIR, RequirementSlot } from '@/types';
import { selectSelectedObject, useWorkspaceStore } from '@/store/useWorkspaceStore';
import { ChoiceGroupPanel } from './right-panel/ChoiceGroupPanel';
import { ChoicePanel } from './right-panel/ChoicePanel';
import { IssuePanel } from './right-panel/IssuePanel';
import { NodePanel } from './right-panel/NodePanel';
import { PanelShell } from './right-panel/shared';
import { ProposalPanel } from './right-panel/ProposalPanel';
import { SlotPanel } from './right-panel/SlotPanel';

const findChoiceById = (ir: RequirementSpaceIR | null, choiceId: string | null): Choice | null => {
  if (!ir || !choiceId) return null;
  for (const group of Object.values(ir.choiceGroups || {})) {
    const choice = (group.choices || []).find((item) => item.id === choiceId);
    if (choice) return choice;
  }
  return null;
};

export function RightObjectPanel() {
  const ir = useWorkspaceStore((state) => state.ir);
  const selectedObject: any = useWorkspaceStore(selectSelectedObject);

  if (!ir) return null;

  if (!selectedObject) {
    return (
      <PanelShell title="选择一个对象" subtitle="Inspector">
        <div className="text-sm text-slate-500 leading-relaxed">
          右侧面板统一审阅和编辑 Node、Issue、Slot、ChoiceGroup、Choice、Proposal。
        </div>
      </PanelShell>
    );
  }

  if (ir.nodes[selectedObject.id]) {
    return <NodePanel node={ir.nodes[selectedObject.id]} ir={ir} />;
  }
  if (ir.issues[selectedObject.id]) {
    return <IssuePanel issue={ir.issues[selectedObject.id] as Issue} ir={ir} />;
  }
  if (ir.slots[selectedObject.id]) {
    return <SlotPanel slot={ir.slots[selectedObject.id] as RequirementSlot} ir={ir} />;
  }
  if (ir.choiceGroups[selectedObject.id]) {
    return <ChoiceGroupPanel choiceGroup={ir.choiceGroups[selectedObject.id] as ChoiceGroup} ir={ir} />;
  }
  if (ir.proposals[selectedObject.id]) {
    return <ProposalPanel proposal={ir.proposals[selectedObject.id] as Proposal} ir={ir} />;
  }

  const choice = findChoiceById(ir, selectedObject.id);
  if (choice) {
    return <ChoicePanel choice={choice} ir={ir} />;
  }

  return (
    <PanelShell title={selectedObject.title || selectedObject.id} subtitle="Inspector">
      <pre className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 overflow-auto">
        {JSON.stringify(selectedObject, null, 2)}
      </pre>
    </PanelShell>
  );
}
