import React from 'react';
import {
  GraphPatch,
  ImpactPreview,
  LinkType,
  NodeKindToText,
  RequirementLink,
  RequirementSpaceIR,
  ScopeStatusToText,
} from '@/core/schema';

export const LINK_LABELS: Record<LinkType, string> = {
  realizes: '实现',
  supports: '支撑',
  performed_by: '由...执行',
  owns: '拥有',
  precedes: '前置于',
  branches_to: '分支至',
  guards: '守卫',
  reads: '读取',
  writes: '写入',
  changes_state: '改变状态',
  depends_on: '依赖',
  diagnoses: '诊断',
  contains: '包含',
  accessible_by: '可被访问',
  binds_field: '绑定字段',
  invokes_step: '触发步骤',
};

export function PanelShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="w-full h-full bg-white overflow-y-auto">
      <div className="sticky top-0 z-10 bg-white/95 backdrop-blur border-b border-slate-200 px-5 py-4">
        <div className="text-xs font-bold uppercase tracking-widest text-slate-400">{subtitle || '建模对象'}</div>
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
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block space-y-1.5">
      <div className="text-xs text-slate-500 font-medium">{label}</div>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 bg-white"
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
}: {
  onClick: () => void;
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'danger';
}) {
  const className =
    variant === 'primary'
      ? 'bg-slate-900 text-white hover:bg-slate-800 border-slate-900'
      : variant === 'danger'
        ? 'bg-rose-50 text-rose-700 hover:bg-rose-100 border-rose-200'
        : 'bg-white text-slate-700 hover:bg-slate-50 border-slate-200';

  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-2 rounded-xl border text-sm font-semibold transition-colors ${className}`}
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
  const dedupeLinks = (links: RequirementLink[]) =>
    Array.from(new Map(links.map((link) => [link.id, link])).values());

  const incoming = dedupeLinks(ir.links.filter((link) => link.targetId === nodeId));
  const outgoing = dedupeLinks(ir.links.filter((link) => link.sourceId === nodeId));

  const renderLinks = (links: RequirementLink[], directionLabel: string) => (
    <div className="space-y-2">
      <div className="text-xs font-medium text-slate-500">{directionLabel}</div>
      {links.length === 0 && <div className="text-xs text-slate-400 italic">暂无</div>}
      {links.map((link) => {
        const relatedId = link.sourceId === nodeId ? link.targetId : link.sourceId;
        const relatedNode = ir.nodes[relatedId];
        return (
          <div key={link.id} className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
            <div className="font-medium">{LINK_LABELS[link.type]}</div>
            <div className="text-xs text-slate-500 mt-1">
              {relatedNode?.title || relatedId}
              {relatedNode ? ` / ${NodeKindToText[relatedNode.kind]}` : ''}
            </div>
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="space-y-3">
      {renderLinks(outgoing, '从当前对象发出')}
      {renderLinks(incoming, '流向当前对象')}
    </div>
  );
}

export function PatchSummary({ patch }: { patch?: GraphPatch }) {
  const safePatch = patch || {};
  const summary = [
    { label: '新增节点', count: safePatch.addNodes?.length || 0 },
    { label: '更新节点', count: safePatch.updateNodes?.length || 0 },
    { label: '新增关系', count: safePatch.addLinks?.length || 0 },
    { label: '移除关系', count: safePatch.removeLinkIds?.length || 0 },
    { label: '新增槽位', count: safePatch.addSlots?.length || 0 },
    { label: '新增问题', count: safePatch.addIssues?.length || 0 },
  ].filter((item) => item.count > 0);

  return (
    <div className="space-y-2">
      {summary.length === 0 && <div className="text-xs text-slate-400 italic">暂无变更内容</div>}
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
  const safeImpact = impact || {};
  const groups = [
    ['目标', safeImpact.affectedGoals || []],
    ['角色', safeImpact.affectedActors || []],
    ['流程', safeImpact.affectedFlows || []],
    ['对象', safeImpact.affectedObjects || []],
    ['界面', safeImpact.affectedScreens || []],
    ['新增问题', safeImpact.newIssues || []],
    ['已解决问题', safeImpact.resolvedIssues || []],
  ] as const;

  return (
    <div className="space-y-2">
      {groups.map(([label, ids]) =>
        ids.length > 0 ? (
          <div key={label} className="rounded-xl border border-slate-200 px-3 py-2">
            <div className="text-xs font-medium text-slate-500">{label}</div>
            <div className="text-sm text-slate-700 mt-1">
              {ids.map((id) => ir.nodes[id]?.title || id).join(', ')}
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
