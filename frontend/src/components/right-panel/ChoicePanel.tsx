import { useTranslation } from 'react-i18next';
import { useState } from 'react';
import { Choice, RequirementSpaceIR } from '@/core/schema';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { ActionButton, ActionRow, ImpactSummary, PanelShell, PatchSummary, Section, TextField } from './shared';
import { ChoicePreviewRenderer } from '@/components/shared/ChoicePreviewRenderer';
import { getChoicePresentation, getChoiceTypeLabel } from '@/core/choicePresentation';

export function ChoicePanel({ choice, ir }: { choice: Choice; ir: RequirementSpaceIR }) {
  const { t, i18n } = useTranslation();
  const { acceptChoice, rejectChoice, rewrite } = useWorkspaceStore();
  const [instruction, setInstruction] = useState('');
  const isDraftPayload = (choice as any).applyMode === 'draft_payload';
  const draftType = (choice as any).draftType;
  const presentation = getChoicePresentation(choice, t, i18n);
  const draftTypeLabel = getChoiceTypeLabel(choice, t) || draftType;

  return (
    <PanelShell title={presentation.title} subtitle={t('panel.choice')}>
      <Section title={t('panel.rationale')}>
        <div className="rounded-xl border border-slate-200 px-3 py-3 text-sm text-slate-700">
          {presentation.rationale}
        </div>
      </Section>

      {isDraftPayload && draftType ? (
        <Section title={t('panel.previewTitle', { type: draftTypeLabel })}>
          <div className="rounded-xl border border-slate-200 p-3">
            <ChoicePreviewRenderer
              draftType={draftType}
              preview={(choice as any).preview}
              payload={(choice as any).payload}
            />
          </div>
        </Section>
      ) : (
        <>
          <Section title={t('panel.patchSummary')}>
            <PatchSummary patch={choice.patch} />
          </Section>
          <Section title={t('panel.impact')}>
            <ImpactSummary ir={ir} impact={choice.impactPreview} />
          </Section>
        </>
      )}

      <Section title={t('panel.instruction')}>
        <TextField label={t('panel.instruction')} value={instruction} onChange={setInstruction} multiline />
        <ActionButton variant="secondary" onClick={() => void rewrite({ kind: 'choice', choiceId: choice.id }, instruction)}>
          {t('panel.regenerateBtn')}
        </ActionButton>
      </Section>

      <Section title={t('panel.actionTitle')}>
        <ActionRow>
          <ActionButton onClick={() => void acceptChoice(choice.id)}>{t('panel.acceptChoice')}</ActionButton>
          <ActionButton variant="danger" onClick={() => void rejectChoice(choice.id)}>
            {t('panel.rejectChoice')}
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}
