import { useTranslation } from 'react-i18next';
import { Finding, RequirementSpaceIR } from '@/core/schema';
import { getFindingCapability, useWorkspaceStore } from '@/store/useWorkspaceStore';
import { findingTargetIds } from '@/core/findingPresentation';
import { ActionButton, ActionRow, PanelShell, Section } from './shared';
import { getFindingText } from '@/core/findingText';

export function IssuePanel({ issue, ir }: { issue: Finding; ir: RequirementSpaceIR }) {
  const { t } = useTranslation();
  const { updateIssueAttributes, executeFindingIssueResolution, expandSlot } = useWorkspaceStore();
  const localizedIssue = getFindingText(issue, t);
  const targetIds = findingTargetIds(issue);
  const capability = getFindingCapability(issue);
  const targetType = issue.target?.targetType || issue.target?.target_type;
  const targetTypeLabel: Record<string, string> = {
    actor: t('panel.actor'),
    feature: t('panel.feature'),
    scenario: t('panel.scenario'),
    acceptance_criterion: t('panel.acceptance_criterion'),
    business_object: t('panel.business_object'),
    flow: t('panel.flow'),
    step: t('panel.step'),
    scope: t('panel.scope'),
    project: t('panel.project'),
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
          { label: t('panel.feature'), value: findTargetName(resolvedFeatureId) || t('panel.relatedTargetEmpty') },
          { label: t('panel.actor'), value: findTargetName(resolvedActorId) || t('panel.relatedTargetEmpty') },
        ];
      })()
    : targetIds.map((targetId) => ({
        label: targetTypeLabel[targetType || ''] || t('panel.node'),
        value: findTargetName(targetId) || t('panel.relatedTargetEmpty'),
      }));

  const openIssueFlow = async () => {
    const slotId = await executeFindingIssueResolution(issue.findingId);
    if (slotId) {
      await expandSlot(slotId);
    }
  };

  return (
    <PanelShell title={localizedIssue.title} subtitle={t('panel.issue')}>
      <Section title={t('panel.description')}>
        <div className="text-sm leading-relaxed text-slate-600">{localizedIssue.description}</div>
      </Section>

      <Section title={t('panel.dependencies')}>
        {relatedTargets.length === 0 && <div className="text-xs text-slate-400 italic">{t('panel.relatedTargetEmpty')}</div>}
        {relatedTargets.map((target) => (
          <div key={target.label} className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
            <span className="text-slate-400">{target.label}：</span>{target.value}
          </div>
        ))}
      </Section>

      <Section title={t('panel.actionTitle')}>
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
            {t('panel.ignoreIssue')}
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}
