import React from 'react';
import {
  GraphPatch,
  ImpactPreview,
  LinkType,
  NodeKind,
  NodeKindToText,
  RequirementLink,
  RequirementNode,
  RequirementSpaceIR,
  ScopeStatusToText,
} from '@/core/schema';

export const LINK_LABELS: Record<LinkType, string> = {
  realizes: '实现',
  supports: '支撑',
  performed_by: '执行者',
  owns: '负责',
  precedes: '前置',
  branches_to: '分支',
  guards: '约束',
  reads: '读取',
  writes: '写入',
  changes_state: '触发状态变化',
  depends_on: '依赖',
  diagnoses: '诊断',
  contains: '包含',
  accessible_by: '可访问',
  binds_field: '绑定字段',
  invokes_step: '触发步骤',
};

export type RelationSpec = {
  label: string;
  linkType: LinkType;
  direction: 'out' | 'in';
  targetKinds: string[];
  multiple?: boolean;
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
        <div className="text-xs font-bold uppercase tracking-widest text-slate-400">{subtitle || 'IR Object'}</div>
        <h2 className="text-lg font-bold text-slate-900 mt-1">{title}</h2>
      </div>
      <div className="p-5 space-y-5">{children}</div>
    </div>
  );
}

export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h3 className="text-[11px] font-bold uppercase tracking-widest text-slate-400">{title}</h3>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

export function TextField({
  label,
  value,
  onChange,
  multiline = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
}) {
  return (
    <label className="block space-y-1.5">
      <div className="text-xs text-slate-500 font-medium">{label}</div>
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 min-h-[88px]"
        />
      ) : (
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
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
  const incoming = ir.links.filter((link) => link.targetId === nodeId);
  const outgoing = ir.links.filter((link) => link.sourceId === nodeId);

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
              {relatedNode ? ` · ${NodeKindToText[relatedNode.kind]}` : ''}
            </div>
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="space-y-3">
      {renderLinks(outgoing, '出向关系')}
      {renderLinks(incoming, '入向关系')}
    </div>
  );
}

export function PatchSummary({ patch }: { patch: GraphPatch }) {
  const summary = [
    { label: '新增节点', count: patch.addNodes?.length || 0 },
    { label: '更新节点', count: patch.updateNodes?.length || 0 },
    { label: '新增关系', count: patch.addLinks?.length || 0 },
    { label: '删除关系', count: patch.removeLinkIds?.length || 0 },
    { label: '新增 Slot', count: patch.addSlots?.length || 0 },
    { label: '新增 Issue', count: patch.addIssues?.length || 0 },
  ].filter((item) => item.count > 0);

  return (
    <div className="space-y-2">
      {summary.length === 0 && <div className="text-xs text-slate-400 italic">空 Patch</div>}
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
  const groups = [
    ['目标', impact.affectedGoals],
    ['角色', impact.affectedActors],
    ['流程', impact.affectedFlows],
    ['数据', impact.affectedObjects],
    ['界面', impact.affectedScreens],
    ['新增 Issue', impact.newIssues || []],
    ['解决 Issue', impact.resolvedIssues || []],
  ] as const;

  return (
    <div className="space-y-2">
      {groups.map(([label, ids]) =>
        ids.length > 0 ? (
          <div key={label} className="rounded-xl border border-slate-200 px-3 py-2">
            <div className="text-xs font-medium text-slate-500">{label}</div>
            <div className="text-sm text-slate-700 mt-1">
              {ids.map((id) => ir.nodes[id]?.title || id).join('、')}
            </div>
          </div>
        ) : null,
      )}
    </div>
  );
}

export function RelationEditor({
  ir,
  node,
  spec,
  onApplyPatch,
}: {
  ir: RequirementSpaceIR;
  node: RequirementNode;
  spec: RelationSpec;
  onApplyPatch: (patch: GraphPatch) => Promise<void>;
}) {
  const matchingLinks = ir.links.filter((link) => {
    if (link.type !== spec.linkType) return false;
    return spec.direction === 'out' ? link.sourceId === node.id : link.targetId === node.id;
  });
  const selectedIds = matchingLinks.map((link) => (spec.direction === 'out' ? link.targetId : link.sourceId));
  const options = Object.values(ir.nodes).filter((candidate) => spec.targetKinds.includes(candidate.kind) && candidate.id !== node.id);

  const buildLink = (targetId: string): RequirementLink => ({
    id: `link_${node.id}_${spec.linkType}_${targetId}_${Date.now()}`,
    sourceId: spec.direction === 'out' ? node.id : targetId,
    targetId: spec.direction === 'out' ? targetId : node.id,
    type: spec.linkType,
    status: 'active',
    source: { type: 'user', text: '右侧面板关系编辑' },
  });

  const replaceSingle = async (targetId: string) => {
    const removeLinkIds = matchingLinks.map((link) => link.id);
    const patch: GraphPatch = { removeLinkIds };
    if (targetId) {
      patch.addLinks = [buildLink(targetId)];
    }
    await onApplyPatch(patch);
  };

  const addMulti = async (targetId: string) => {
    if (!targetId || selectedIds.includes(targetId)) return;
    await onApplyPatch({ addLinks: [buildLink(targetId)] });
  };

  const removeMulti = async (targetId: string) => {
    const link = matchingLinks.find((item) =>
      spec.direction === 'out' ? item.targetId === targetId : item.sourceId === targetId,
    );
    if (!link) return;
    await onApplyPatch({ removeLinkIds: [link.id] });
  };

  return (
    <div className="rounded-xl border border-slate-200 p-3 space-y-2">
      <div className="text-xs font-medium text-slate-500">{spec.label}</div>
      {!spec.multiple ? (
        <select
          value={selectedIds[0] || ''}
          onChange={(e) => void replaceSingle(e.target.value)}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm bg-white"
        >
          <option value="">未设置</option>
          {options.map((option) => (
            <option key={option.id} value={option.id}>
              {option.title}
            </option>
          ))}
        </select>
      ) : (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            {selectedIds.length === 0 && <span className="text-xs text-slate-400 italic">暂无</span>}
            {selectedIds.map((targetId) => (
              <button
                key={targetId}
                type="button"
                onClick={() => void removeMulti(targetId)}
                className="px-2 py-1 rounded-full border border-slate-200 text-xs text-slate-700 hover:border-rose-200 hover:text-rose-600"
              >
                {ir.nodes[targetId]?.title || targetId} ×
              </button>
            ))}
          </div>
          <select
            defaultValue=""
            onChange={(e) => {
              const targetId = e.target.value;
              e.target.value = '';
              void addMulti(targetId);
            }}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm bg-white"
          >
            <option value="">添加关系</option>
            {options.map((option) => (
              <option key={option.id} value={option.id}>
                {option.title}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}

export function scopeOptions() {
  return Object.entries(ScopeStatusToText).map(([value, label]) => ({ value, label }));
}
