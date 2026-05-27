import { ChoiceGroup, RequirementSpaceIR } from '@/core/schema';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { ActionButton, ActionRow, Badge, PanelShell, Section } from './shared';

export function ChoiceGroupPanel({ choiceGroup, ir }: { choiceGroup: ChoiceGroup; ir: RequirementSpaceIR }) {
  const { addChoiceToGroup, setSelectedObject } = useWorkspaceStore();
  const slot = ir.slots[choiceGroup.slotId];

  return (
    <PanelShell title={slot?.name || choiceGroup.id} subtitle="ChoiceGroup">
      <Section title="状态">
        <div className="flex flex-wrap gap-2">
          <Badge>{choiceGroup.status}</Badge>
          <Badge>{choiceGroup.selectionMode}</Badge>
          <Badge>{choiceGroup.choices.length} 个 Choice</Badge>
        </div>
      </Section>

      <Section title="所属 Slot">
        {slot ? (
          <button
            type="button"
            onClick={() => setSelectedObject(slot as any)}
            className="w-full text-left rounded-xl border border-slate-200 px-3 py-3 hover:border-indigo-300 transition-colors"
          >
            <div className="text-sm font-semibold text-slate-900">{slot.name}</div>
            <div className="text-xs text-slate-500 mt-1">{slot.description || '暂无说明'}</div>
          </button>
        ) : (
          <div className="text-xs text-slate-400 italic">Slot 不存在</div>
        )}
      </Section>

      <Section title="Choices">
        {choiceGroup.choices.length === 0 && <div className="text-xs text-slate-400 italic">暂无 Choice</div>}
        {choiceGroup.choices.map((choice) => (
          <button
            key={choice.id}
            type="button"
            onClick={() => setSelectedObject(choice as any)}
            className="w-full text-left rounded-xl border border-slate-200 px-3 py-3 hover:border-indigo-300 transition-colors"
          >
            <div className="text-sm font-semibold text-slate-900">{choice.title}</div>
            <div className="text-xs text-slate-500 mt-1 line-clamp-2">{choice.rationale || '暂无说明'}</div>
          </button>
        ))}
      </Section>

      <Section title="动作">
        <ActionRow>
          <ActionButton onClick={() => void addChoiceToGroup(choiceGroup.id, { title: '新增 Choice', rationale: '' })}>
            新增 Choice
          </ActionButton>
          <ActionButton variant="secondary" onClick={() => slot && setSelectedObject(slot as any)}>
            返回 Slot
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}
