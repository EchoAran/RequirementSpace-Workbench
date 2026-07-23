import { useTranslation } from 'react-i18next';
import { ChoiceGroup, RequirementSpaceIR } from '@/core/schema';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { ChoicePreviewRenderer } from '@/components/shared/ChoicePreviewRenderer';
import { Trash2, AlertTriangle, RefreshCw } from 'lucide-react';
import { ActionButton, ActionRow, Badge, PanelShell, Section } from './shared';
import { getChoicePresentation, getChoiceTypeLabel } from '@/core/choicePresentation';

export function ChoiceGroupPanel({ choiceGroup, ir }: { choiceGroup: ChoiceGroup; ir: RequirementSpaceIR }) {
  const { t, i18n } = useTranslation();
  const { addChoiceToGroup, setSelectedObject, discardChoiceGroup, regenerateChoiceGroup, acceptChoice } = useWorkspaceStore();
  const slot = choiceGroup.slotId ? ir.slots?.[choiceGroup.slotId] : undefined;
  const isStale = (choiceGroup as any).status === 'stale';
  const generationType = (choiceGroup as any).generationType || choiceGroup.sourceType;
  const generationTypeLabel = getChoiceTypeLabel({ generationType }, t) || generationType;
  const groupStatus = t(`panel.choiceGroupStatus.${choiceGroup.status}`, { defaultValue: choiceGroup.status });

  const handleDiscard = async () => {
    const id = typeof choiceGroup.id === 'string' ? parseInt(choiceGroup.id, 10) : choiceGroup.id;
    await discardChoiceGroup(id);
  };

  const handleRegenerate = async () => {
    const id = typeof choiceGroup.id === 'string' ? parseInt(choiceGroup.id, 10) : choiceGroup.id;
    await regenerateChoiceGroup(id);
  };

  const handleAcceptChoice = async (choiceId: number | string) => {
    const numericId = typeof choiceId === 'string' ? parseInt(choiceId, 10) : choiceId;
    await acceptChoice(String(numericId));
  };

  return (
    <PanelShell
      title={slot?.name || t('panel.choiceGroupTitle', { id: choiceGroup.id })}
      subtitle={generationTypeLabel || t('panel.choiceGroup')}
    >
      {/* Status badges */}
      <Section title={t('panel.status')}>
        <div className="flex flex-wrap gap-2">
          <Badge>{groupStatus}</Badge>
          {isStale && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 text-[10px] font-bold border border-amber-200">
              <AlertTriangle className="w-3 h-3" />
              {t('panel.stale')}
            </span>
          )}
          {generationTypeLabel && <Badge>{generationTypeLabel}</Badge>}
          <Badge>{t('panel.choicesCount', { count: choiceGroup.choices?.length || 0 })}</Badge>
        </div>
      </Section>

      {/* Slot (if applicable) */}
      {slot && (
        <Section title={t('panel.slot')}>
          <button
            type="button"
            onClick={() => setSelectedObject(slot as any)}
            className="w-full text-left rounded-xl border border-slate-200 px-3 py-3 hover:border-indigo-300 transition-colors"
          >
            <div className="text-sm font-semibold text-slate-900">{slot.name}</div>
            <div className="text-xs text-slate-500 mt-1">{slot.description || t('panel.noDescription')}</div>
          </button>
        </Section>
      )}

      {/* Generation type info for non-slot groups */}
      {!slot && generationType && (
        <Section title={t('panel.generationType')}>
            <div className="text-sm text-slate-700">{generationTypeLabel}</div>
        </Section>
      )}

      {/* Target info */}
      {(choiceGroup as any).target && (
        <Section title={t('panel.targetNode')}>
          <pre className="text-xs text-slate-500 bg-slate-50 p-2 rounded-lg overflow-x-auto">
            {JSON.stringify((choiceGroup as any).target, null, 2)}
          </pre>
        </Section>
      )}

      {/* Choices list with preview */}
      <Section title={t('panel.choices')}>
        {(!choiceGroup.choices || choiceGroup.choices.length === 0) && (
          <div className="text-xs text-slate-400 italic">{t('panel.noChoices')}</div>
        )}
        {choiceGroup.choices?.map((choice: any) => {
          const isFailed = choice.status === 'failed' || choice.status === 'discarded';
          const isDraftPayload = choice.applyMode === 'draft_payload';
          const draftType = choice.draftType || generationType;
          const presentation = getChoicePresentation({ ...choice, draftType }, t, i18n);
          return (
            <div
              key={choice.id}
              className={`rounded-xl border px-3 py-3 mb-2 ${
                isFailed ? 'border-red-100 bg-red-50/50 opacity-60' :
                isStale ? 'border-amber-200 bg-amber-50/30' :
                'border-slate-200 hover:border-indigo-300'
              }`}
            >
              <div className="flex items-start justify-between mb-1">
                <div>
                  <span className="text-sm font-semibold text-slate-900">{presentation.title}</span>
                  {isFailed && <span className="ml-2 text-[10px] text-red-500 font-medium">{t('panel.failed')}</span>}
                  {isStale && !isFailed && <span className="ml-2 text-[10px] text-amber-600 font-medium">{t('panel.stale')}</span>}
                </div>
              </div>
              <div className="text-xs text-slate-500 mt-1 line-clamp-2">{presentation.rationale}</div>
              {/* Type-appropriate preview */}
              {isDraftPayload && draftType && choice.preview && (
                <div className="mt-2 p-2 bg-white rounded-lg border border-slate-100">
                  <ChoicePreviewRenderer
                    draftType={draftType}
                    preview={choice.preview}
                    payload={choice.payload}
                  />
                </div>
              )}
              {/* Actions */}
              {!isFailed && (
                <div className="flex gap-2 mt-2">
                  {draftType && (
                    <button
                      onClick={() => handleAcceptChoice(choice.id)}
                      className="text-xs px-3 py-1 rounded-lg bg-indigo-50 text-indigo-700 font-medium hover:bg-indigo-100 transition-colors"
                    >
                      {t('panel.adoptBtn')}
                    </button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </Section>

      {/* Group-level actions */}
      {choiceGroup.status !== 'resolved' && choiceGroup.status !== 'discarded' && (
        <Section title={t('panel.actionTitle')}>
          <ActionRow>
            <ActionButton onClick={handleDiscard} variant="danger">
              <Trash2 className="w-4 h-4" />
              {t('panel.discardGroup')}
            </ActionButton>
            {isStale && (
              <ActionButton onClick={handleRegenerate}>
                <RefreshCw className="w-4 h-4" />
                {t('panel.regenerateGroup')}
              </ActionButton>
            )}
          </ActionRow>
        </Section>
      )}
    </PanelShell>
  );
}
