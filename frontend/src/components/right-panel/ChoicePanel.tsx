import { useState } from 'react';
import { Choice, RequirementSpaceIR } from '@/core/schema';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { ActionButton, ActionRow, ImpactSummary, PanelShell, PatchSummary, Section, TextField } from './shared';

export function ChoicePanel({ choice, ir }: { choice: Choice; ir: RequirementSpaceIR }) {
  const { acceptChoice, rejectChoice, rewrite } = useWorkspaceStore();
  const [instruction, setInstruction] = useState('');

  return (
    <PanelShell title={choice.title} subtitle="Choice">
      <Section title="依据">
        <div className="rounded-xl border border-slate-200 px-3 py-3 text-sm text-slate-700">
          {choice.rationale || '暂无说明'}
        </div>
      </Section>

      <Section title="Patch 摘要">
        <PatchSummary patch={choice.patch} />
      </Section>

      <Section title="Impact Preview">
        <ImpactSummary ir={ir} impact={choice.impactPreview} />
      </Section>

      <Section title="改写">
        <TextField label="改写指令" value={instruction} onChange={setInstruction} multiline />
        <ActionButton variant="secondary" onClick={() => void rewrite({ kind: 'choice', choiceId: choice.id }, instruction)}>
          生成改写提案
        </ActionButton>
      </Section>

      <Section title="动作">
        <ActionRow>
          <ActionButton onClick={() => void acceptChoice(choice.id)}>采纳 Choice</ActionButton>
          <ActionButton variant="danger" onClick={() => void rejectChoice(choice.id)}>
            拒绝 Choice
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}
