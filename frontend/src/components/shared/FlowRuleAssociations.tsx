import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { DomainRule } from '@/core/schema';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';

interface Props {
  targetKind: 'flow' | 'flow_step';
  targetLogicalUuid?: string;
  rules: DomainRule[];
  readOnly: boolean;
  onOpenRule: (rule: DomainRule) => void;
}

export function FlowRuleAssociations({ targetKind, targetLogicalUuid, rules, readOnly, onOpenRule }: Props) {
  const { t } = useTranslation();
  const replaceTargetRules = useWorkspaceStore(s => s.replaceTargetRules);
  const linkedIds = rules.filter(rule => rule.links?.some(link =>
    link.targetKind === targetKind && link.targetLogicalUuid === targetLogicalUuid && link.linkPurpose === 'applies_to'
  )).map(rule => rule.id);
  const linkedKey = JSON.stringify(linkedIds);
  const [selectedIds, setSelectedIds] = useState(linkedIds);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    setSelectedIds(JSON.parse(linkedKey));
    setError('');
  }, [targetKind, targetLogicalUuid, linkedKey]);
  const toggle = async (ruleId: number, checked: boolean) => {
    if (!targetLogicalUuid || readOnly || saving) return;
    const next = checked ? [...selectedIds, ruleId] : selectedIds.filter(id => id !== ruleId);
    setSelectedIds(next);
    setError('');
    setSaving(true);
    try {
      await replaceTargetRules(targetKind, targetLogicalUuid, next);
    } catch (err) {
      setSelectedIds(JSON.parse(linkedKey));
      setError(err instanceof Error ? err.message : t('how.ruleAssociations.saveFailed'));
    } finally {
      setSaving(false);
    }
  };
  return (
    <section className="space-y-2 border-t border-slate-200 pt-3" data-testid={`${targetKind}-rule-associations`}>
      <h4 className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">{t(`how.ruleAssociations.${targetKind}`)}</h4>
      <div className="max-h-44 space-y-2 overflow-y-auto">
        {rules.map(rule => {
          const linked = selectedIds.includes(rule.id);
          return (
            <label key={rule.id} data-testid={targetKind === 'flow_step' && linked ? `step-linked-rule-${rule.id}` : undefined}
              className="flex cursor-pointer items-start gap-2 text-xs transition-opacity hover:opacity-85">
              <input type="checkbox" className="mt-0.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" disabled={saving || readOnly}
                aria-label={rule.title} checked={linked} onChange={event => void toggle(rule.id, event.target.checked)} />
              <div className="min-w-0 flex-1">
                <button type="button" disabled={saving} onClick={event => { event.preventDefault(); event.stopPropagation(); onOpenRule(rule); }}
                  title={t('how.ruleAssociations.openRule')} className="text-left font-semibold text-indigo-700 hover:underline">
                  {rule.title}
                </button>
                <p className="line-clamp-2 text-[11px] text-slate-600">{rule.statement}</p>
              </div>
            </label>
          );
        })}
        {rules.length === 0 && <p className="text-[11px] text-slate-600">{t('how.ruleAssociations.noAvailable')}</p>}
      </div>
      {error && <p role="alert" className="text-xs text-rose-700">{t('how.ruleAssociations.saveFailed')}: {error}</p>}
    </section>
  );
}
