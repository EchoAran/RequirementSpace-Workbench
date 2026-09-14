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
    flow_step: t('panel.step'),
    flow_transition: t('panel.flow_transition', '流程流转'),
    domain_rule: t('panel.domain_rule', '业务规则'),
    scope: t('panel.scope'),
    project: t('panel.project'),
  };
  // 按 targetType 从对应的类型化集合解析名称，避免落入扁平 nodes 映射的 id 冲突
  // （actor/feature/flow/属性等共用数字 id 空间，扁平映射会被后注册的类型覆盖）
  const findTargetName = (targetId: string, kind = targetType) => {
    const id = String(targetId);
    switch (kind) {
      case 'actor':
        return ir.actors?.find((actor) => String(actor.actorId) === id)?.actorName;
      case 'feature':
        return ir.features?.find((feature) => String(feature.featureId) === id)?.featureName;
      case 'scenario':
        return ir.features?.flatMap((feature) => feature.scenarios || [])
          .find((scenario) => String(scenario.scenarioId) === id)?.scenarioName;
      case 'acceptance_criterion':
        return ir.features?.flatMap((feature) => feature.scenarios || [])
          .flatMap((scenario) => scenario.acceptanceCriteria || [])
          .find((criterion) => String(criterion.criterionId) === id)?.criterionContent;
      case 'business_object':
        return ir.businessObjects?.find((object) => String(object.businessObjectId) === id)?.businessObjectName;
      case 'business_object_attribute':
        return ir.businessObjects?.flatMap((object) => object.businessObjectAttributes || [])
          .find((attr) => String(attr.businessObjectAttributeId) === id)?.businessObjectAttributeName;
      case 'flow':
        return ir.flows?.find((flow) => String(flow.flowId) === id)?.flowName;
      case 'flow_step':
      case 'step':
        return ir.flows?.flatMap((flow) => flow.flowSteps || [])
          .find((step) => String(step.stepId) === id)?.stepName;
      case 'flow_transition':
        return ir.flows?.flatMap((flow) => flow.transitions || [])
          .find((transition) => String(transition.transitionId ?? transition.id) === id)?.label;
      case 'domain_rule':
        return ir.domainRules?.find((rule) => String(rule.id) === id || rule.logicalUuid === id)?.title;
      default:
        return ir.nodes?.[id]?.title;
    }
  };
  const relatedTargets = targetType === 'feature_actor_pair'
    ? (() => {
        const [featureId, actorId] = String(issue.metadata?.feature_id ?? targetIds[0] ?? '').split(':');
        const resolvedFeatureId = String(issue.metadata?.feature_id ?? featureId);
        const resolvedActorId = String(issue.metadata?.actor_id ?? actorId);
        return [
          { label: t('panel.feature'), value: findTargetName(resolvedFeatureId, 'feature') || t('panel.relatedTargetEmpty') },
          { label: t('panel.actor'), value: findTargetName(resolvedActorId, 'actor') || t('panel.relatedTargetEmpty') },
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
