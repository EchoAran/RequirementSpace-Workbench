import { RequirementSpaceIR, RequirementSlot } from '@/types';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { ActionButton, ActionRow, Badge, PanelShell, Section } from './shared';

export function SlotPanel({ slot, ir }: { slot: RequirementSlot; ir: RequirementSpaceIR }) {
  const { expandSlot, applyPatch, setSelectedObject } = useWorkspaceStore();
  const choiceGroup = Object.values(ir.choiceGroups || {}).find((group) => group.slotId === slot.id) || null;

  return (
    <PanelShell title={slot.name} subtitle="Slot">
      <Section title="状态">
        <div className="flex flex-wrap gap-2">
          <Badge>{slot.status}</Badge>
          <Badge>{slot.ownerProjection}</Badge>
          <Badge>{slot.arity}</Badge>
        </div>
      </Section>

      <Section title="上下文">
        <div className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
          所属节点: {ir.nodes[slot.ownerNodeId]?.title || slot.ownerNodeId}
        </div>
        <div className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
          期望类型: {slot.expectedKinds.join('、') || '未指定'}
        </div>
        <div className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
          {slot.description || '暂无说明'}
        </div>
      </Section>

      <Section title="ChoiceGroup">
        {choiceGroup ? (
          <button
            type="button"
            onClick={() => setSelectedObject(choiceGroup as any)}
            className="w-full text-left rounded-xl border border-slate-200 px-3 py-3 hover:border-indigo-300 transition-colors"
          >
            <div className="text-sm font-semibold text-slate-900">打开 ChoiceGroup</div>
            <div className="text-xs text-slate-500 mt-1">{choiceGroup.choices.length} 个 Choice</div>
          </button>
        ) : (
          <div className="text-xs text-slate-400 italic">尚未生成 ChoiceGroup</div>
        )}
      </Section>

      <Section title="动作">
        <ActionRow>
          <ActionButton onClick={() => void expandSlot(slot.id)}>展开 Slot</ActionButton>
          <ActionButton
            variant="secondary"
            onClick={() => void applyPatch({ updateSlots: [{ id: slot.id, status: 'deferred' }] })}
          >
            暂缓 Slot
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}
