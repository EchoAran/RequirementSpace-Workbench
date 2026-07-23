import { RequirementSpaceIR, RequirementSlot } from '@/core/schema';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { ActionButton, ActionRow, Badge, PanelShell, Section } from './shared';
import { useTranslation } from 'react-i18next';

export function SlotPanel({ slot, ir }: { slot: RequirementSlot; ir: RequirementSpaceIR }) {
  const { t } = useTranslation();
  const { expandSlot, clearPerceptionSlot, setSelectedObject } = useWorkspaceStore();
  const choiceGroup = Object.values(ir.choiceGroups || {}).find((group) => group.slotId === slot.id) || null;

  return (
    <PanelShell title={slot.name} subtitle={t('panel.slotDetail.slot')}>
      <Section title={t('panel.status')}>
        <div className="flex flex-wrap gap-2">
          <Badge>{slot.status}</Badge>
          <Badge>{slot.ownerProjection}</Badge>
          <Badge>{slot.arity}</Badge>
        </div>
      </Section>

      <Section title={t('panel.slotDetail.context')}>
        <div className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
          {t('panel.slotDetail.ownerNode', { name: ir.nodes?.[slot.ownerNodeId]?.title || slot.ownerNodeId })}
        </div>
        <div className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
          {t('panel.slotDetail.expectedKinds', {
            kinds: (slot.expectedKinds || []).join(', ') || t('panel.slotDetail.notSpecified'),
          })}
        </div>
        <div className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
          {slot.description || t('panel.noDescription')}
        </div>
      </Section>

      <Section title={t('panel.choiceGroup')}>
        {choiceGroup ? (
          <button
            type="button"
            onClick={() => setSelectedObject(choiceGroup as any)}
            className="w-full text-left rounded-xl border border-slate-200 px-3 py-3 hover:border-indigo-300 transition-colors"
          >
            <div className="text-sm font-semibold text-slate-900">{t('panel.slotDetail.openChoiceGroup')}</div>
            <div className="text-xs text-slate-500 mt-1">{t('panel.choicesCount', { count: choiceGroup.choices.length })}</div>
          </button>
        ) : (
          <div className="text-xs text-slate-400 italic">{t('panel.slotDetail.noChoiceGroup')}</div>
        )}
      </Section>

      <Section title={t('panel.actionTitle')}>
        <ActionRow>
          <ActionButton onClick={() => void expandSlot(slot.id)}>{t('panel.slotDetail.expand')}</ActionButton>
          <ActionButton variant="secondary" onClick={() => void clearPerceptionSlot()}>
            {t('panel.slotDetail.ignore')}
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}
