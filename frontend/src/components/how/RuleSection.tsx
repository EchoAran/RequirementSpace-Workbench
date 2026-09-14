import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { useLocalStorageState } from '@/lib/useLocalStorageState';
import {
  Scale,
  Plus,
  Trash2,
  AlertCircle,
  Link2,
  RefreshCw,
  Sparkles,
  ChevronDown,
  ChevronRight,
  User,
  Boxes,
  Film,
  ClipboardCheck,
  Database,
  KeyRound,
  Workflow,
  Footprints,
  Target,
  CircleDot,
  List,
  LayoutGrid,
  CornerDownRight,
} from 'lucide-react';
import { GlassSurface } from '@/components/ui/GlassSurface';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { findIrNodeByUuid } from '@/core/objectNavigation';
import type { DomainRule, RequirementSpace, RuleLink } from '@/core/schema';

interface RuleSectionProps {
  readOnly?: boolean;
}

/** 关联对象类型的标识：图标 + 颜色（不同类型有不同视觉标识） */
const LINK_KIND_META: Record<string, { icon: typeof User; chip: string; text: string }> = {
  actor: { icon: User, chip: 'bg-teal-50 hover:bg-teal-100 border-teal-200/70', text: 'text-teal-700' },
  feature: { icon: Boxes, chip: 'bg-indigo-50 hover:bg-indigo-100 border-indigo-200/70', text: 'text-indigo-700' },
  scenario: { icon: Film, chip: 'bg-sky-50 hover:bg-sky-100 border-sky-200/70', text: 'text-sky-700' },
  acceptance_criterion: { icon: ClipboardCheck, chip: 'bg-violet-50 hover:bg-violet-100 border-violet-200/70', text: 'text-violet-700' },
  business_object: { icon: Database, chip: 'bg-amber-50 hover:bg-amber-100 border-amber-200/70', text: 'text-amber-700' },
  business_object_attribute: { icon: KeyRound, chip: 'bg-amber-50 hover:bg-amber-100 border-amber-200/70', text: 'text-amber-700' },
  flow: { icon: Workflow, chip: 'bg-emerald-50 hover:bg-emerald-100 border-emerald-200/70', text: 'text-emerald-700' },
  flow_step: { icon: Footprints, chip: 'bg-emerald-50 hover:bg-emerald-100 border-emerald-200/70', text: 'text-emerald-700' },
  flow_transition: { icon: CornerDownRight, chip: 'bg-emerald-50 hover:bg-emerald-100 border-emerald-200/70', text: 'text-emerald-700' },
  scope: { icon: Target, chip: 'bg-rose-50 hover:bg-rose-100 border-rose-200/70', text: 'text-rose-700' },
};

const LINK_FALLBACK_META = { icon: CircleDot, chip: 'bg-slate-50 hover:bg-slate-100 border-slate-200/70', text: 'text-slate-600' };

/** 定位 flow_transition 所属流程 */
function findTransitionFlow(ir: RequirementSpace | null, node: any): any {
  if (!ir || !node) return null;
  return (ir.flows || []).find((flow: any) =>
    (flow?.transitions || []).some((tr: any) =>
      tr === node || (node.logicalUuid && tr?.logicalUuid === node.logicalUuid)
    )
  ) || null;
}

/** 按对象类型从 IR 节点取展示名称 */
function resolveLinkName(node: any, kind: string, ir: RequirementSpace | null): string {
  if (!node) return '';
  switch (kind) {
    case 'actor': return node.actorName || '';
    case 'feature': return node.featureName || '';
    case 'scenario': return node.scenarioName || '';
    case 'acceptance_criterion': return node.criterionContent || '';
    case 'business_object': return node.businessObjectName || '';
    case 'business_object_attribute': return node.businessObjectAttributeName || '';
    case 'flow': return node.flowName || '';
    case 'flow_step': return node.stepName || node.stepDescription || '';
    case 'flow_transition': {
      // 连线展示名：label / 条件文本优先，否则“源步骤 → 目标步骤”
      if (node.label || node.conditionText) return node.label || node.conditionText;
      const flow = findTransitionFlow(ir, node);
      if (!flow) return '';
      const stepName = (stepId: number) =>
        (flow.flowSteps || []).find((s: any) => s?.stepId === stepId)?.stepName || '';
      const source = stepName(node.sourceStepId);
      const target = stepName(node.targetStepId);
      return source || target ? `${source} → ${target}` : '';
    }
    case 'scope': return node.reason || 'Scope';
    default: return node.title || node.name || '';
  }
}

/** 展示名称截断（验收标准等文本可能很长） */
function truncateName(name: string, max = 24): string {
  const clean = name.replace(/\s+/g, ' ').trim();
  return clean.length > max ? `${clean.slice(0, max)}…` : clean;
}

/** 关联对象 chips：点击展示对象详情（右侧面板）；按宽度自动展示数量，溢出折叠 */
const RuleLinkChips: React.FC<{ links: RuleLink[] }> = ({ links }) => {
  const ir = useWorkspaceStore((s) => s.ir);
  const setSelectedObject = useWorkspaceStore((s) => s.setSelectedObject);
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [fitCount, setFitCount] = useState<number | null>(null);
  const ghostRef = useRef<HTMLDivElement>(null);

  // 幽灵行测量：渲染全部 chips，统计首行能容纳的数量；容器宽度变化时重新测量
  useEffect(() => {
    const ghost = ghostRef.current;
    if (!ghost) return;
    const measure = () => {
      const chips = Array.from(ghost.querySelectorAll<HTMLElement>('[data-ghost-chip]'));
      if (chips.length === 0) return;
      const firstTop = chips[0].offsetTop;
      let count = 1;
      for (let i = 1; i < chips.length; i++) {
        if (chips[i].offsetTop !== firstTop) break;
        count++;
      }
      setFitCount((prev) => (prev === count ? prev : count));
    };
    measure();
    if (typeof ResizeObserver !== 'undefined') {
      const ro = new ResizeObserver(measure);
      ro.observe(ghost);
      return () => ro.disconnect();
    }
  }, [links]);

  const visibleCount = expanded ? links.length : (fitCount ?? links.length);
  const hasOverflow = visibleCount < links.length;

  const renderChip = (link: RuleLink, ghost: boolean) => {
    const meta = LINK_KIND_META[link.targetKind] || LINK_FALLBACK_META;
    const IconComp = meta.icon;
    const node = ir ? findIrNodeByUuid(ir, link.targetKind, link.targetLogicalUuid) : null;
    const name = resolveLinkName(node, link.targetKind, ir);
    const displayName = name
      ? truncateName(name, link.targetKind === 'acceptance_criterion' ? 32 : 24)
      : (link.contextText ? truncateName(link.contextText, 20) : link.targetKind);
    // 连线没有专属对象面板：chip 仅展示名称与图标，不可点击
    const clickable = Boolean(node) && link.targetKind !== 'flow_transition';
    return (
      <button
        key={link.id}
        data-ghost-chip={ghost ? '' : undefined}
        onClick={(e) => {
          e.stopPropagation();
          if (clickable) setSelectedObject(node);
        }}
        disabled={!clickable}
        title={name || link.contextText || `${link.targetKind}:${link.targetLogicalUuid}`}
        className={`inline-flex items-center gap-1 min-w-0 text-[10px] px-2 py-0.5 rounded-full border font-semibold transition-colors ${meta.chip} ${meta.text} ${
          clickable ? 'cursor-pointer' : 'cursor-default opacity-70'
        }`}
      >
        <IconComp className="w-3 h-3 shrink-0" />
        <span className="truncate max-w-[200px]">{displayName}</span>
      </button>
    );
  };

  return (
    <div className="relative mt-3 pt-2.5 border-t border-slate-100">
      <div className="flex items-center gap-1.5 mb-1.5">
        <Link2 className="w-3 h-3 text-slate-400" />
        <span className="text-[10px] text-slate-400 font-semibold">
          {t('how.domainRules.linkedObjects')}
        </span>
        <span className="text-[10px] text-slate-300 font-mono">{links.length}</span>
        {hasOverflow && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setExpanded((v) => !v);
            }}
            className="ml-auto text-[10px] text-slate-400 hover:text-indigo-600 font-semibold flex items-center gap-0.5 cursor-pointer transition-colors"
          >
            {expanded ? (
              <>{t('common.collapse')} <ChevronDown className="w-3 h-3" /></>
            ) : (
              <>+{links.length - visibleCount} <ChevronRight className="w-3 h-3" /></>
            )}
          </button>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5 items-center">
        {links.slice(0, visibleCount).map((link) => renderChip(link, false))}
      </div>
      {/* 测量幽灵行（不可见，不影响布局） */}
      <div
        ref={ghostRef}
        aria-hidden
        className="absolute inset-x-0 top-0 -z-10 h-0 overflow-hidden opacity-0 pointer-events-none flex flex-wrap gap-1.5 items-center"
      >
        {links.map((link) => renderChip(link, true))}
      </div>
    </div>
  );
};

export const RuleSection: React.FC<RuleSectionProps> = ({ readOnly = false }) => {
  const { t } = useTranslation();
  const ir = useWorkspaceStore((s) => s.ir);
  const workspaceCanWrite = useWorkspaceStore((s) => s.workspaceCanWrite);
  const canWrite = typeof workspaceCanWrite === 'function' ? workspaceCanWrite() : true;
  const isReadOnly = readOnly || !canWrite;

  const createDomainRule = useWorkspaceStore((s) => s.createDomainRule);
  const generateRules = useWorkspaceStore((s) => s.generateRules);
  const isGeneratingChoices = useWorkspaceStore((s) => s.isGeneratingChoices);
  const generatingChoiceGroupType = useWorkspaceStore((s) => s.generatingChoiceGroupType);
  const isDiscoveringRules = isGeneratingChoices && generatingChoiceGroupType === 'rule';
  const highlightTarget = useWorkspaceStore((s) => s.highlightTarget);
  const setSelectedObject = useWorkspaceStore((s) => s.setSelectedObject);

  const rules: DomainRule[] = ir?.domainRules || [];

  // Section state
  const [isCollapsed, setIsCollapsed] = useLocalStorageState('how-rule-section-collapsed', false);
  const [viewMode, setViewMode] = useLocalStorageState<'card' | 'compact'>('how-rule-view-mode', 'card');

  // Rule Creation Modal state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newStatement, setNewStatement] = useState('');
  const [newParentId, setNewParentId] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleOpenCreateModal = () => {
    if (isReadOnly) return;
    setNewTitle('');
    setNewStatement('');
    setNewParentId(null);
    setErrorMessage(null);
    setIsCreateModalOpen(true);
  };

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isReadOnly || !newTitle.trim() || !newStatement.trim()) return;

    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await createDomainRule({
        title: newTitle.trim(),
        statement: newStatement.trim(),
        origin: 'manual',
        confirmationStatus: 'needs_confirmation',
        parentRuleId: newParentId,
      });
      setIsCreateModalOpen(false);
    } catch (err: any) {
      setErrorMessage(err?.response?.data?.detail || err.message || t('how.domainRules.createFailed'));
    } finally {
      setIsSubmitting(false);
    }
  };

  /** 打开右侧处理面板进行编辑（与其他对象卡片一致） */
  const handleOpenEditor = (rule: DomainRule) => {
    setSelectedObject({ ...rule, kind: 'rule' });
  };

  const handleDeleteRule = async (ruleId: number) => {
    if (isReadOnly) return;
    if (!window.confirm(t('how.domainRules.deleteConfirm'))) return;
    try {
      await useWorkspaceStore.getState().deleteDomainRule(ruleId);
    } catch (err) {
      console.error('Failed to delete rule:', err);
    }
  };

  const renderDeleteButton = (rule: DomainRule) => (
    <button
      onClick={(e) => {
        e.stopPropagation();
        handleDeleteRule(rule.id);
      }}
      className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded transition-colors cursor-pointer shrink-0"
      title={t('common.delete')}
    >
      <Trash2 className="w-3.5 h-3.5" />
    </button>
  );

  /** 按 parentRuleId 构建层级树（父规则缺失的视为顶级，防环） */
  const ruleTree = useMemo(() => {
    const byId = new Map<number, DomainRule>();
    rules.forEach((r) => byId.set(r.id, r));
    const childrenOf = new Map<number, DomainRule[]>();
    const roots: DomainRule[] = [];
    for (const r of rules) {
      const parent = r.parentRuleId ? byId.get(r.parentRuleId) : null;
      if (parent && parent.id !== r.id) {
        const list = childrenOf.get(parent.id) || [];
        list.push(r);
        childrenOf.set(parent.id, list);
      } else {
        roots.push(r);
      }
    }
    return { roots, childrenOf };
  }, [rules]);

  /* ---------------- 卡片视图 ---------------- */
  const renderRuleCard = (rule: DomainRule, depth: number, visited: Set<number>): React.ReactNode => {
    if (visited.has(rule.id) || depth > 4) return null;
    visited.add(rule.id);
    const children = ruleTree.childrenOf.get(rule.id) || [];
    const confirmationStatus = rule.confirmationStatus || 'needs_confirmation';
    const isHighlighted =
      highlightTarget === String(rule.id) || highlightTarget === rule.logicalUuid;
    const links = rule.links || [];

    return (
      <div key={rule.id} className="min-w-0">
        <div
          id={`rule-card-${rule.id}`}
          onClick={() => handleOpenEditor(rule)}
          className={`bg-white/90 rounded-xl border p-4 shadow-2xs transition-all flex flex-col cursor-pointer ${
            isHighlighted
              ? 'border-indigo-500 ring-2 ring-indigo-400 bg-indigo-50/20'
              : 'border-slate-200/80 hover:border-indigo-200 hover:shadow-xs'
          }`}
        >
          {/* Rule Card Header：删除按钮移至状态徽章前 */}
          <div className="flex items-start justify-between gap-2 mb-2">
            <h4 className="font-bold text-slate-900 text-sm leading-snug tracking-tight min-w-0">
              {rule.title}
            </h4>
            <div className="flex items-center gap-1.5 shrink-0">
              {!isReadOnly && renderDeleteButton(rule)}
              <StatusBadge status={confirmationStatus as any} />
            </div>
          </div>

          {/* Rule Statement */}
          <p className="text-xs text-slate-500 leading-relaxed whitespace-pre-wrap">
            {rule.statement}
          </p>

          {/* Linked Objects */}
          {links.length > 0 && <RuleLinkChips links={links} />}
        </div>

        {/* Children (层级结构) */}
        {children.length > 0 && (
          <div className="ml-4 pl-4 mt-2 space-y-2 border-l-2 border-slate-200/70">
            {children.map((child) => renderRuleCard(child, depth + 1, visited))}
          </div>
        )}
      </div>
    );
  };

  /* ---------------- 紧凑视图 ---------------- */
  const renderCompactRow = (rule: DomainRule, depth: number, visited: Set<number>): React.ReactNode => {
    if (visited.has(rule.id) || depth > 4) return null;
    visited.add(rule.id);
    const children = ruleTree.childrenOf.get(rule.id) || [];
    const confirmationStatus = rule.confirmationStatus || 'needs_confirmation';
    const isHighlighted =
      highlightTarget === String(rule.id) || highlightTarget === rule.logicalUuid;
    const links = rule.links || [];

    return (
      <div key={rule.id} className="min-w-0">
        <div
          id={`rule-card-${rule.id}`}
          onClick={() => handleOpenEditor(rule)}
          style={{ marginLeft: depth * 16 }}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border bg-white/90 shadow-2xs transition-all cursor-pointer ${
            isHighlighted
              ? 'border-indigo-500 ring-1 ring-indigo-400 bg-indigo-50/30'
              : 'border-slate-200/80 hover:border-indigo-200 hover:shadow-xs'
          }`}
        >
          {depth > 0 && <CornerDownRight className="w-3 h-3 text-slate-300 shrink-0" />}
          <span className="text-xs font-bold text-slate-800 truncate min-w-0 flex-1" title={rule.title}>
            {rule.title}
          </span>
          <span
            className="hidden md:block text-[10px] text-slate-500 truncate max-w-[40%]"
            title={rule.statement}
          >
            {rule.statement.replace(/\s+/g, ' ')}
          </span>
          {links.length > 0 && (
            <span
              className="flex items-center gap-0.5 text-[10px] text-slate-400 font-semibold shrink-0"
              title={t('how.domainRules.linkedObjects')}
            >
              <Link2 className="w-3 h-3" />
              {links.length}
            </span>
          )}
          {!isReadOnly && renderDeleteButton(rule)}
          <StatusBadge status={confirmationStatus as any} className="shrink-0" />
        </div>

        {children.length > 0 && (
          <div className="space-y-1 mt-1">
            {children.map((child) => renderCompactRow(child, depth + 1, visited))}
          </div>
        )}
      </div>
    );
  };

  return (
    <GlassSurface className="p-6 relative w-full mb-6">
      {/* Section Header */}
      <div className="flex items-start justify-between gap-4 border-b border-slate-200/50 pb-4 mb-6">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-bold text-slate-800 uppercase tracking-widest flex items-center gap-2">{t('how.domainRules.sectionTitle')}</h3>
          {rules.length > 0 && (
            <span className="text-[10px] font-bold text-slate-400 bg-slate-100/80 px-2 py-0.5 rounded-full">
              {rules.length}
            </span>
          )}
          {!isReadOnly && (
            <>
              <div className="relative group">
                <button
                  onClick={handleOpenCreateModal}
                  className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-lg transition-all shadow-2xs cursor-pointer"
                  aria-label={t('how.domainRules.addRule')}
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="relative group">
                <button
                  onClick={() => void generateRules()}
                  disabled={isDiscoveringRules}
                  className="p-1 text-slate-400 hover:text-amber-600 hover:bg-amber-50 border border-transparent hover:border-amber-100 rounded-lg transition-all shadow-2xs cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                  aria-label={t('how.domainRules.aiDiscover')}
                  title={t('how.domainRules.aiDiscoverTooltip')}
                >
                  {isDiscoveringRules ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>
            </>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {/* 折叠按钮 */}
          <button
            onClick={() => setIsCollapsed((v) => !v)}
            aria-expanded={!isCollapsed}
            aria-controls="how-rule-section-content"
            className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-lg transition-all shadow-2xs cursor-pointer"
            aria-label={isCollapsed ? t('common.expand') : t('common.collapse')}
            title={isCollapsed ? t('common.expand') : t('common.collapse')}
          >
            {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {/* 视图切换按钮 */}
          <button
            onClick={() => setViewMode((v) => (v === 'card' ? 'compact' : 'card'))}
            className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-lg transition-all shadow-2xs cursor-pointer"
            aria-label={viewMode === 'card' ? t('how.domainRules.compactView') : t('how.domainRules.cardView')}
            title={viewMode === 'card' ? t('how.domainRules.compactView') : t('how.domainRules.cardView')}
          >
            {viewMode === 'card' ? <List className="w-4 h-4" /> : <LayoutGrid className="w-4 h-4" />}
          </button>
          {!isReadOnly && (
            <button
              onClick={() => void generateRules()}
              disabled={isDiscoveringRules}
              className="flex items-center gap-1.5 text-[10px] bg-indigo-50/80 hover:bg-indigo-100/80 text-indigo-700 font-bold px-3 py-1.5 rounded-xl border border-indigo-200/60 transition-all shadow-2xs disabled:opacity-50 cursor-pointer"
            >
              <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
              {rules.length > 0 ? t('how.domainRules.aiRediscover') : t('how.domainRules.aiDiscover')}
            </button>
          )}
        </div>
      </div>

      {/* Content Area */}
      {!isCollapsed && (
        <div id="how-rule-section-content">
          {rules.length === 0 && (
            <div className="rounded-xl border border-dashed border-amber-200 bg-amber-50/40 p-6 text-center">
              <div className="w-10 h-10 rounded-full bg-amber-100 text-amber-600 flex items-center justify-center mx-auto mb-3">
                <AlertCircle className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-bold text-slate-800 mb-1">
                {t('how.domainRules.stateNotStartedTitle')}
              </h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto mb-4 leading-relaxed">
                {t('how.domainRules.stateNotStartedDesc')}
              </p>
              {!isReadOnly && (
                <div className="flex items-center justify-center gap-3">
                  <button
                    onClick={() => void generateRules()}
                    disabled={isDiscoveringRules}
                    className="flex items-center gap-1.5 text-[10px] bg-indigo-50/80 hover:bg-indigo-100/80 text-indigo-700 font-bold px-3 py-1.5 rounded-xl border border-indigo-200/60 transition-all shadow-2xs disabled:opacity-50 cursor-pointer"
                  >
                    {isDiscoveringRules ? (
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
                    )}
                    {t('how.domainRules.aiDiscover')}
                  </button>
                  <button
                    onClick={handleOpenCreateModal}
                    className="text-[10px] bg-white hover:bg-slate-50 text-slate-700 font-bold px-3 py-1.5 rounded-xl border border-slate-200 shadow-2xs transition-all cursor-pointer"
                  >
                    {t('how.domainRules.addFirstRule')}
                  </button>
                </div>
              )}
            </div>
          )}

          {rules.length > 0 && (
            viewMode === 'card' ? (
              <div className="space-y-2.5">
                {ruleTree.roots.map((root) => renderRuleCard(root, 0, new Set<number>()))}
              </div>
            ) : (
              <div className="space-y-1">
                {ruleTree.roots.map((root) => renderCompactRow(root, 0, new Set<number>()))}
              </div>
            )
          )}
        </div>
      )}

      {/* Create Rule Modal（无遮罩，屏幕居中，点击空白处关闭；portal 渲染避免被 GlassSurface 的 backdrop-filter 困住） */}
      {isCreateModalOpen && createPortal(
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          onClick={() => setIsCreateModalOpen(false)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl ring-1 ring-slate-900/10 border border-slate-200 max-w-lg w-full p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-bold text-slate-900 mb-4 flex items-center gap-2">
              <Scale className="w-5 h-5 text-indigo-600" />
              {t('how.domainRules.createModalTitle')}
            </h3>

            {errorMessage && (
              <div className="mb-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-700">
                {errorMessage}
              </div>
            )}

            <form onSubmit={handleCreateRule} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  {t('how.domainRules.titleLabel')}
                </label>
                <input
                  type="text"
                  required
                  maxLength={255}
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder={t('how.domainRules.titlePlaceholder')}
                  className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 focus:outline-hidden focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  {t('how.domainRules.statementLabel')}
                </label>
                <textarea
                  required
                  rows={4}
                  value={newStatement}
                  onChange={(e) => setNewStatement(e.target.value)}
                  placeholder={t('how.domainRules.statementPlaceholder')}
                  className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 focus:outline-hidden focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              {rules.length > 0 && (
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    {t('how.domainRules.parentRuleLabel')}
                  </label>
                  <select
                    value={newParentId || ''}
                    onChange={(e) => setNewParentId(e.target.value ? Number(e.target.value) : null)}
                    className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 focus:outline-hidden focus:border-indigo-500 bg-white"
                  >
                    <option value="">{t('how.domainRules.noParentRule')}</option>
                    {rules.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.title}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="flex items-center justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="text-xs px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 font-medium transition-colors cursor-pointer"
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !newTitle.trim() || !newStatement.trim()}
                  className="text-xs px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium transition-colors disabled:opacity-50 cursor-pointer"
                >
                  {isSubmitting ? t('common.saving') : t('common.create')}
                </button>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}
    </GlassSurface>
  );
};
