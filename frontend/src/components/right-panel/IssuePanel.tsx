import { useState } from 'react';
import { Finding, RequirementSpaceIR } from '@/core/schema';
import { getFindingCapability, useWorkspaceStore } from '@/store/useWorkspaceStore';
import { findingTargetIds } from '@/core/findingPresentation';
import { ActionButton, ActionRow, PanelShell, Section } from './shared';

export function IssuePanel({ issue, ir }: { issue: Finding; ir: RequirementSpaceIR }) {
  const { updateIssueAttributes, executeFindingIssueResolution, expandSlot } = useWorkspaceStore();
  const [description] = useState(issue.description || '');
  const targetIds = findingTargetIds(issue);
  const capability = getFindingCapability(issue);
  const targetType = issue.target?.targetType || issue.target?.target_type;
  const targetTypeLabel: Record<string, string> = {
    actor: '参与者',
    feature: '功能',
    scenario: '场景',
    acceptance_criterion: '验收标准',
    business_object: '业务对象',
    flow: '业务流程',
    step: '流程步骤',
    scope: '范围项',
    project: '项目',
  };
  const findTargetName = (targetId: string) => {
    return ir.nodes?.[targetId]?.title
      || ir.actors?.find((actor) => String(actor.actorId) === targetId)?.actorName
      || ir.features?.find((feature) => String(feature.featureId) === targetId)?.featureName
      || ir.flows?.find((flow) => String(flow.flowId) === targetId)?.flowName
      || ir.businessObjects?.find((object) => String(object.businessObjectId) === targetId)?.businessObjectName;
  };
  const relatedTargets = targetType === 'feature_actor_pair'
    ? (() => {
        const [featureId, actorId] = String(issue.metadata?.feature_id ?? targetIds[0] ?? '').split(':');
        const resolvedFeatureId = String(issue.metadata?.feature_id ?? featureId);
        const resolvedActorId = String(issue.metadata?.actor_id ?? actorId);
        return [
          { label: '功能', value: findTargetName(resolvedFeatureId) || '未找到对应功能' },
          { label: '参与者', value: findTargetName(resolvedActorId) || '未找到对应参与者' },
        ];
      })()
    : targetIds.map((targetId) => ({
        label: targetTypeLabel[targetType || ''] || '关联对象',
        value: findTargetName(targetId) || '未找到关联对象',
      }));

  const openIssueFlow = async () => {
    const slotId = await executeFindingIssueResolution(issue.findingId);
    if (slotId) {
      await expandSlot(slotId);
    }
  };

  return (
    <PanelShell title={issue.title} subtitle="Issue">
      <Section title="说明">
        <div className="text-sm leading-relaxed text-slate-600">{description}</div>
      </Section>

      <Section title="关联节点">
        {relatedTargets.length === 0 && <div className="text-xs text-slate-400 italic">暂无关联节点</div>}
        {relatedTargets.map((target) => (
          <div key={target.label} className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
            <span className="text-slate-400">{target.label}：</span>{target.value}
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
