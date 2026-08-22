import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronRight, FilePlus2, FileMinus2, FilePenLine, Link2, Link2Off, ArrowDownUp } from 'lucide-react';
import { workspaceApi } from '@/lib/api';
import {
  DiffChangeType,
  DiffEntry,
  DiffResult,
  DiffTypeSummary,
} from '@/core/versionControl';
import { DiffEntityDetail } from './DiffEntityDetail';
import { cn } from '@/lib/utils';

interface SemanticDiffViewProps {
  projectId: string;
  baseRef?: string;
  targetRef?: string;
  branch?: string;
  entityType?: string;
  changeType?: string;
  onEntitySelect?: (entry: DiffEntry) => void;
  onJump?: (entry: DiffEntry) => void;
}

const ENTITY_TYPE_LABELS: Record<string, string> = {
  actor: 'actor',
  feature: 'feature',
  feature_relation: 'feature_relation',
  scenario: 'scenario',
  acceptance_criterion: 'acceptance_criterion',
  business_object: 'business_object',
  business_object_attribute: 'business_object_attribute',
  flow: 'flow',
  flow_step: 'flow_step',
  scope: 'scope',
  project_metadata: 'project_metadata',
};

const CHANGE_TYPE_ICONS: Record<DiffChangeType, typeof FilePlus2> = {
  entity_added: FilePlus2,
  entity_removed: FileMinus2,
  entity_updated: FilePenLine,
  field_changed: FilePenLine,
  relation_added: Link2,
  relation_removed: Link2Off,
  ordered_item_moved: ArrowDownUp,
};

function ChangeIcon({ type, className }: { type: DiffChangeType; className?: string }) {
  const Icon = CHANGE_TYPE_ICONS[type] || FilePenLine;
  return <Icon className={className} />;
}

function changeColor(type: DiffChangeType): string {
  switch (type) {
    case 'entity_added':
    case 'relation_added':
      return 'text-emerald-600';
    case 'entity_removed':
    case 'relation_removed':
      return 'text-rose-600';
    case 'ordered_item_moved':
      return 'text-amber-600';
    default:
      return 'text-indigo-600';
  }
}

function changeLabelKey(type: DiffChangeType): string {
  switch (type) {
    case 'entity_added':
      return 'versionControl.diff.entityAdded';
    case 'entity_removed':
      return 'versionControl.diff.entityRemoved';
    case 'entity_updated':
      return 'versionControl.diff.entityUpdated';
    case 'field_changed':
      return 'versionControl.diff.fieldChanged';
    case 'relation_added':
      return 'versionControl.diff.relationAdded';
    case 'relation_removed':
      return 'versionControl.diff.relationRemoved';
    case 'ordered_item_moved':
      return 'versionControl.diff.orderedMoved';
    default:
      return 'versionControl.diff.entityUpdated';
  }
}

function typeLabelKey(entityType: string): string {
  const base = ENTITY_TYPE_LABELS[entityType] || entityType;
  return `versionControl.diff.entityType.${base}`;
}

/**
 * 语义 Diff 工作台：左侧按对象类型分组的变更树，右侧选中变更的文本/关系详情。
 * 支持按对象类型与变更种类筛选，状态由 props 传入（可来自 URL）。
 */
export function SemanticDiffView({
  projectId,
  baseRef,
  targetRef,
  branch,
  entityType,
  changeType,
  onEntitySelect,
  onJump,
}: SemanticDiffViewProps) {
  const { t } = useTranslation();
  const [result, setResult] = useState<DiffResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<DiffEntry | null>(null);
  const [collapsedTypes, setCollapsedTypes] = useState<Set<string>>(new Set());
  const [mobilePane, setMobilePane] = useState<'tree' | 'detail'>('tree');
  const currentDiffReqId = useRef(0);

  const PAGE_SIZE = 50;

  const load = useCallback(async (isAppend = false) => {
    if (isAppend) {
      if (loadingMore || loading) return;
      setLoadingMore(true);
    } else {
      setLoading(true);
      setLoadingMore(false);
      setError(null);
    }
    const reqId = isAppend ? currentDiffReqId.current : ++currentDiffReqId.current;
    try {
      const currentOffset = isAppend && result ? result.entries.length : 0;
      const res = await workspaceApi.getSemanticDiff(projectId, {
        base_ref: baseRef,
        target_ref: targetRef,
        branch,
        entity_type: entityType,
        change_type: changeType,
        limit: PAGE_SIZE,
        offset: currentOffset,
      });

      if (currentDiffReqId.current !== reqId) return;

      setResult((prev) => {
        if (isAppend && prev) {
          return {
            ...res,
            entries: [...prev.entries, ...res.entries],
          };
        }
        return res;
      });
      setError(null);
    } catch (e) {
      if (currentDiffReqId.current === reqId) {
        setError(e instanceof Error ? e.message : 'versionControl.errors.loadDiffFailed');
      }
    } finally {
      if (currentDiffReqId.current === reqId) {
        if (isAppend) {
          setLoadingMore(false);
        } else {
          setLoading(false);
        }
      } else if (isAppend) {
        setLoadingMore(false);
      }
    }
  }, [projectId, baseRef, targetRef, branch, entityType, changeType, result, loading, loadingMore]);

  useEffect(() => {
    setResult(null);
    setSelected(null);
    setError(null);
    setLoadingMore(false);
    void load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, baseRef, targetRef, branch, entityType, changeType]);

  const grouped = useMemo(() => {
    if (!result) return [] as { type: string; summary?: DiffTypeSummary; entries: DiffEntry[] }[];
    const byType: Record<string, DiffEntry[]> = {};
    for (const entry of result.entries) {
      (byType[entry.entity_type] ||= []).push(entry);
    }
    return Object.keys(byType)
      .sort()
      .map((type) => ({
        type,
        summary: result.summary.by_type[type],
        entries: byType[type],
      }));
  }, [result]);

  const toggleType = (type: string) => {
    setCollapsedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const selectEntry = (entry: DiffEntry) => {
    setSelected(entry);
    onEntitySelect?.(entry);
  };

  return (
    <div className="flex h-full min-h-0 w-full flex-col gap-3">
      {loading && <p className="text-sm text-slate-400">{t('shell.loading')}</p>}
      {error && <p className="text-sm text-rose-600">{error}</p>}

      {result && (
        <>
          {/* 移动端分段控件：树 ↔ 详情（替代垂直堆叠，设计文档 4 抽屉式单列降级）。 */}
          <div className="flex items-center gap-1 md:hidden">
            {(['tree', 'detail'] as const).map((pane) => (
              <button
                key={pane}
                type="button"
                aria-pressed={mobilePane === pane}
                onClick={() => setMobilePane(pane)}
                className={cn(
                  'rounded-lg px-3 py-1.5 text-xs font-medium',
                  mobilePane === pane ? 'bg-indigo-100 text-indigo-700' : 'text-slate-600 hover:bg-slate-100'
                )}
              >
                {pane === 'tree' ? t('versionControl.diff.treeTitle') : t('versionControl.diff.selectNode')}
              </button>
            ))}
          </div>
        <div className="grid min-h-[580px] w-full grid-cols-1 gap-6 md:grid-cols-[360px_minmax(0,1fr)]">
          {/* 左侧：变更树 */}
          <div className={cn('min-h-0 w-full overflow-hidden rounded-2xl border border-slate-200 bg-white flex flex-col shadow-sm', mobilePane !== 'tree' && 'hidden md:flex')}>
            <div className="border-b border-slate-100 bg-slate-50/60 px-4 py-3 flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-800">{t('versionControl.diff.treeTitle')}</p>
                {result.summary.total_added + result.summary.total_removed + result.summary.total_modified === 0 ? (
                  <p className="mt-0.5 text-xs text-slate-400">{t('versionControl.diff.empty')}</p>
                ) : (
                  <p className="mt-0.5 text-xs text-slate-500 font-medium">
                    {t('versionControl.repository.changeSummary', {
                      added: result.summary.total_added,
                      removed: result.summary.total_removed,
                      modified: result.summary.total_modified,
                    })}
                  </p>
                )}
              </div>
              {result.total > 0 && (
                <span className="text-[11px] font-bold text-slate-500 bg-white px-2 py-0.5 rounded-lg border border-slate-200/80 shadow-2xs">
                  {t('versionControl.diff.paginationCount', { shown: result.entries.length, total: result.total })}
                </span>
              )}
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto">
              {grouped.length === 0 && !loading && (
                <p className="px-4 py-6 text-sm text-slate-400 text-center">{t('versionControl.diff.empty')}</p>
              )}

              {grouped.map((group) => {
                const collapsed = collapsedTypes.has(group.type);
                return (
                  <div key={group.type} className="border-b border-slate-50">
                    <button
                      type="button"
                      onClick={() => toggleType(group.type)}
                      aria-expanded={!collapsed}
                      aria-controls={`diff-group-${group.type}`}
                      className="flex w-full items-center gap-1.5 px-4 py-2.5 text-left text-xs font-bold text-slate-700 hover:bg-slate-50 transition-colors"
                    >
                      <ChevronRight className={cn('h-3.5 w-3.5 text-slate-400 transition-transform', collapsed && '-rotate-90')} />
                      <span>{t(typeLabelKey(group.type))}</span>
                      <span className="ml-auto text-[11px] font-medium text-slate-400">
                        {group.summary ? `+${group.summary.added} ~${group.summary.modified} -${group.summary.removed}` : group.entries.length}
                      </span>
                    </button>

                    {!collapsed && (
                      <ul id={`diff-group-${group.type}`} className="ml-4 border-l border-slate-100 pb-1">
                        {group.entries.map((entry, i) => {
                          const isSelected = selected?.entity_uuid === entry.entity_uuid && selected?.path === entry.path && selected?.change_type === entry.change_type;
                          return (
                            <li key={`${entry.change_type}-${entry.entity_uuid}-${i}`}>
                              <button
                                type="button"
                                onClick={() => { selectEntry(entry); setMobilePane('detail'); }}
                                aria-current={isSelected ? 'true' : undefined}
                                className={cn(
                                  'flex w-full items-start gap-2 px-3 py-1.5 text-left text-xs transition-colors rounded-lg mx-1',
                                  isSelected ? 'bg-indigo-50 text-indigo-900 font-semibold' : 'text-slate-700 hover:bg-slate-50'
                                )}
                              >
                                <ChangeIcon type={entry.change_type} className={cn('mt-0.5 h-3.5 w-3.5 shrink-0', changeColor(entry.change_type))} />
                                <span className="min-w-0 flex-1">
                                  <span className="block truncate">{entry.entity_name || entry.entity_uuid}</span>
                                  <span className={cn('block text-[10px] font-medium', changeColor(entry.change_type))}>
                                    {t(changeLabelKey(entry.change_type))}
                                    {entry.field ? ` · ${entry.field}` : ''}
                                  </span>
                                </span>
                              </button>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                );
              })}

              {result.entries.length < result.total && (
                <div className="p-3 text-center border-t border-slate-100">
                  <button
                    type="button"
                    disabled={loadingMore}
                    onClick={() => void load(true)}
                    className="inline-flex items-center gap-1 rounded-lg bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-600 hover:bg-indigo-100 disabled:opacity-50 cursor-pointer"
                  >
                    {loadingMore ? t('shell.loading') : t('versionControl.diff.loadMore', { remaining: result.total - result.entries.length })}
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* 右侧：详情 */}
          <div className={cn('min-h-0 min-w-0 w-full overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-sm', mobilePane !== 'detail' && 'hidden md:block')}>
            {!selected ? (
              <div className="flex h-full min-h-[300px] flex-col items-center justify-center text-center p-6 text-slate-400">
                <p className="text-sm font-medium">{t('versionControl.diff.selectNode')}</p>
              </div>
            ) : (
              <DiffEntityDetail entry={selected} onJump={onJump} />
            )}
          </div>
        </div>
        </>
      )}
    </div>
  );
}

