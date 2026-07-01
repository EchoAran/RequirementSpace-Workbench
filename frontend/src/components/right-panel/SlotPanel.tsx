import { RequirementSpaceIR, RequirementSlot } from '@/core/schema';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { ActionButton, ActionRow, Badge, PanelShell, Section } from './shared';

export function SlotPanel({ slot, ir }: { slot: RequirementSlot; ir: RequirementSpaceIR }) {
  const { expandSlot, clearPerceptionSlot, setSelectedObject } = useWorkspaceStore();
  const choiceGroup = Object.values(ir.choiceGroups || {}).find((group) => group.slotId === slot.id) || null;

  return (
    <PanelShell title={slot.name} subtitle="Slot">
      <Section title="Status">
        <div className="flex flex-wrap gap-2">
          <Badge>{slot.status}</Badge>
          <Badge>{slot.ownerProjection}</Badge>
          <Badge>{slot.arity}</Badge>
        </div>
      </Section>

      <Section title="Context">
        <div className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
          Owner node: {ir.nodes?.[slot.ownerNodeId]?.title || slot.ownerNodeId}
        </div>
        <div className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
          Expected kinds: {(slot.expectedKinds || []).join(', ') || 'Not specified'}
        </div>
        <div className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
          {slot.description || 'No description'}
        </div>
      </Section>

      <Section title="ChoiceGroup">
        {choiceGroup ? (
          <button
            type="button"
            onClick={() => setSelectedObject(choiceGroup as any)}
            className="w-full text-left rounded-xl border border-slate-200 px-3 py-3 hover:border-indigo-300 transition-colors"
          >
            <div className="text-sm font-semibold text-slate-900">Open ChoiceGroup</div>
            <div className="text-xs text-slate-500 mt-1">{choiceGroup.choices.length} choices</div>
          </button>
        ) : (
          <div className="text-xs text-slate-400 italic">No ChoiceGroup yet</div>
        )}
      </Section>

      <Section title="Actions">
        <ActionRow>
          <ActionButton onClick={() => void expandSlot(slot.id)}>Expand Slot</ActionButton>
          <ActionButton variant="secondary" onClick={() => void clearPerceptionSlot()}>
            Ignore Slot
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}
