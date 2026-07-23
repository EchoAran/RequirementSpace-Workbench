import { useTranslation } from 'react-i18next';
import React from 'react';
import {
  GraphPatch,
  ImpactPreview,
  LinkType,
  RequirementLink,
  RequirementSpaceIR,
} from '@/core/schema';
import { NodeKindToText, ScopeStatusToText } from '@/core/presentationLabels';



export function PanelShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div className="w-full h-full bg-white overflow-y-auto">
      <div className="sticky top-0 z-10 bg-white/95 backdrop-blur border-b border-slate-200 px-5 py-4">
        <div className="text-xs font-bold uppercase tracking-widest text-slate-400">{subtitle || t('panel.node')}</div>
        <h2 className="text-lg font-bold text-slate-900 mt-1">{title}</h2>
      </div>
      <div className="p-5 space-y-5">{children}</div>
    </div>
  );
}

export function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">{title}</h3>
        {action}
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

export function TextField({
  label,
  value,
  onChange,
  placeholder,
  multiline = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  multiline?: boolean;
}) {
  return (
    <label className="block space-y-1.5">
      <div className="text-xs text-slate-500 font-medium">{label}</div>
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 min-h-[88px]"
        />
      ) : (
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700"
        />
      )}
    </label>
  );
}

export function SelectField({
  label,
  value,
  options,
  onChange,
  disabled = false,
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <label className="block space-y-1.5">
      <div className="text-xs text-slate-500 font-medium">{label}</div>
      <select
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 bg-white disabled:bg-slate-50 disabled:text-slate-400 disabled:cursor-not-allowed"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function ActionRow({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-2">{children}</div>;
}

export function ActionButton({
  onClick,
  children,
  variant = 'primary',
  disabled,
}: {
  onClick: () => void;
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'danger';
  disabled?: boolean;
}) {
  const className =
    variant === 'primary'
      ? 'bg-slate-900 text-white hover:bg-slate-800 border-slate-900'
      : variant === 'danger'
        ? 'bg-rose-50 text-rose-700 hover:bg-rose-100 border-rose-200'
        : 'bg-white text-slate-700 hover:bg-slate-50 border-slate-200';

  const disabledClass = disabled ? 'opacity-50 cursor-not-allowed pointer-events-none' : '';

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`px-3 py-2 rounded-xl border text-sm font-semibold transition-colors ${className} ${disabledClass}`}
    >
      {children}
    </button>
  );
}

export function Badge({ children }: { children: React.ReactNode }) {
  return <span className="inline-flex px-2 py-1 rounded-full bg-slate-100 text-slate-600 text-xs font-semibold">{children}</span>;
}

export function LinkList({
  ir,
  nodeId,
}: {
  ir: RequirementSpaceIR;
  nodeId: string;
}) {
  const { t } = useTranslation();
  const nodeMap = ir.nodes || {};
  const allLinks = (Array.isArray(ir.links) ? ir.links : Object.values(ir.links || {})) as RequirementLink[];
  const dedupeLinks = (links: RequirementLink[]) =>
    Array.from(new Map(links.map((link) => [link.id, link])).values());

  const incoming = dedupeLinks(allLinks.filter((link: RequirementLink) => link.targetId === nodeId));
  const outgoing = dedupeLinks(allLinks.filter((link: RequirementLink) => link.sourceId === nodeId));

  const renderLinks = (links: RequirementLink[], directionLabel: string) => (
    <div className="space-y-2">
      <div className="text-xs font-medium text-slate-500">{directionLabel}</div>
      {links.length === 0 && <div className="text-xs text-slate-400 italic">{t('panel.noLinks')}</div>}
      {links.map((link) => {
        const relatedId = link.sourceId === nodeId ? link.targetId : link.sourceId;
        const relatedNode = nodeMap[relatedId];
        const relatedKindText = relatedNode?.kind
          ? NodeKindToText[relatedNode.kind as keyof typeof NodeKindToText]
          : '';
        return (
          <div key={link.id} className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
            <div className="font-medium">{t('panel.relationships.' + link.type) as any}</div>
            <div className="text-xs text-slate-500 mt-1">
              {relatedNode?.title || relatedId}
              {relatedNode ? ` / ${relatedKindText}` : ''}
            </div>
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="space-y-3">
      {renderLinks(outgoing, t('panel.outgoingLinks'))}
      {renderLinks(incoming, t('panel.incomingLinks'))}
    </div>
  );
}

export function PatchSummary({ patch }: { patch?: GraphPatch }) {
  const { t } = useTranslation();
  const safePatch = patch || {};
  const summary = [
    { label: t('panel.patchCounts.addNodes'), count: safePatch.addNodes?.length || 0 },
    { label: t('panel.patchCounts.updateNodes'), count: safePatch.updateNodes?.length || 0 },
    { label: t('panel.patchCounts.addLinks'), count: safePatch.addLinks?.length || 0 },
    { label: t('panel.patchCounts.removeLinkIds'), count: safePatch.removeLinkIds?.length || 0 },
    { label: t('panel.patchCounts.addSlots'), count: safePatch.addSlots?.length || 0 },
    { label: t('panel.patchCounts.addIssues'), count: safePatch.addIssues?.length || 0 },
  ].filter((item) => item.count > 0);

  return (
    <div className="space-y-2">
      {summary.length === 0 && <div className="text-xs text-slate-400 italic">{t('panel.noImpact')}</div>}
      {summary.map(({ label, count }) => (
        <div key={label} className="flex items-center justify-between rounded-xl border border-slate-200 px-3 py-2 text-sm">
          <span className="text-slate-600">{label}</span>
          <span className="font-semibold text-slate-900">{count}</span>
        </div>
      ))}
    </div>
  );
}

export function ImpactSummary({ ir, impact }: { ir: RequirementSpaceIR; impact: ImpactPreview }) {
  const { t } = useTranslation();
  const nodeMap = ir.nodes || {};
  const safeImpact = impact || {};
  const groups = [
    ['goals', safeImpact.affectedGoals || []],
    ['actors', safeImpact.affectedActors || []],
    ['flows', safeImpact.affectedFlows || []],
    ['objects', safeImpact.affectedObjects || []],
    ['screens', safeImpact.affectedScreens || []],
    ['newIssues', safeImpact.newIssues || []],
    ['resolvedIssues', safeImpact.resolvedIssues || []],
  ] as const;

  return (
    <div className="space-y-2">
      {groups.map(([label, ids]) =>
        ids.length > 0 ? (
          <div key={label} className="rounded-xl border border-slate-200 px-3 py-2">
            <div className="text-xs font-medium text-slate-500">{t('panel.impactMetrics.' + label) as any}</div>
            <div className="text-sm text-slate-700 mt-1">
              {ids.map((id: string | number) => nodeMap[id]?.title || id).join(', ')}
            </div>
          </div>
        ) : null,
      )}
    </div>
  );
}

export function scopeOptions() {
  return Object.entries(ScopeStatusToText).map(([value, label]) => ({ value, label }));
}
