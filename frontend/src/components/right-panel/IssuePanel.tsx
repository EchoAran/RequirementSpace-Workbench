import { useState } from 'react';
import { Finding, RequirementSpaceIR } from '@/core/schema';
import { getFindingCapability, useWorkspaceStore } from '@/store/useWorkspaceStore';
import { findingTargetIds } from '@/core/findingPresentation';
import { ActionButton, ActionRow, Badge, PanelShell, Section } from './shared';

export function IssuePanel({ issue, ir }: { issue: Finding; ir: RequirementSpaceIR }) {
  const { updateIssueAttributes, executeFindingIssueResolution, expandSlot } = useWorkspaceStore();
  const [description] = useState(issue.description || '');
  const targetIds = findingTargetIds(issue);
  const capability = getFindingCapability(issue);

  const openIssueFlow = async () => {
    const slotId = await executeFindingIssueResolution(issue.findingId);
    if (slotId) {
      await expandSlot(slotId);
    }
  };

  return (
    <PanelShell title={issue.title} subtitle="Issue">
      <Section title="状态">
        <div className="flex flex-wrap gap-2">
          <Badge>{issue.severity}</Badge>
          <Badge>{issue.code}</Badge>
          <Badge>{issue.status || 'open'}</Badge>
        </div>
      </Section>

      <Section title="说明">
        <div className="text-sm leading-relaxed text-slate-600">{description}</div>
      </Section>

      <Section title="关联节点">
        {targetIds.length === 0 && <div className="text-xs text-slate-400 italic">暂无关联节点</div>}
        {targetIds.map((nodeId) => (
          <div key={nodeId} className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
            {ir.nodes[nodeId]?.title || nodeId}
          </div>
        ))}
      </Section>

      <Section title="动作">
        <ActionRow>
          {(() => {
            return (
              <ActionButton
                onClick={() => void openIssueFlow()}
                disabled={!capability.enabled}
              >
                {capability.actionLabel}
              </ActionButton>
            );
          })()}
          <ActionButton variant="secondary" onClick={() => void updateIssueAttributes(issue.findingId, { status: 'ignored' })}>
            忽略 Issue
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}
