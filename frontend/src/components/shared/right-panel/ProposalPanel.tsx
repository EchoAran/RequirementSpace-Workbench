import { Proposal, RequirementSpaceIR } from '@/types';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { ActionButton, ActionRow, ImpactSummary, PanelShell, PatchSummary, Section } from './shared';

export function ProposalPanel({ proposal, ir }: { proposal: Proposal; ir: RequirementSpaceIR }) {
  const { acceptProposal, rejectProposal } = useWorkspaceStore();

  return (
    <PanelShell title={proposal.title} subtitle="Proposal">
      <Section title="摘要">
        <div className="rounded-xl border border-slate-200 px-3 py-3 text-sm text-slate-700">
          {proposal.summary || '暂无摘要'}
        </div>
      </Section>

      <Section title="Scope">
        <pre className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-700 overflow-auto">
          {JSON.stringify(proposal.scope, null, 2)}
        </pre>
      </Section>

      <Section title="Patch">
        <PatchSummary patch={proposal.patch} />
      </Section>

      <Section title="Impact Preview">
        <ImpactSummary ir={ir} impact={proposal.impactPreview} />
      </Section>

      <Section title="动作">
        <ActionRow>
          <ActionButton onClick={() => void acceptProposal(proposal.id)}>采纳 Proposal</ActionButton>
          <ActionButton variant="danger" onClick={() => void rejectProposal(proposal.id)}>
            拒绝 Proposal
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}
