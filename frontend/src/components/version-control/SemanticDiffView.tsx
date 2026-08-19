import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronRight, FilePlus2, FileMinus2, FilePenLine, Link2, Link2Off, ArrowDownUp } from 'lucide-react';
import { workspaceApi } from '@/lib/api';
import {
  DiffChangeType,
  DiffEntry,
  DiffResult,
  DiffTypeSummary,
} from '@/core/versionControl';
import { cn } from '@/lib/utils';
import { jumpTargetForEntity } from '@/core/objectNavigation';

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

function jumpLabelKey(entityType: string): string {
  switch (jumpTargetForEntity(entityType)) {
    case '/what': return 'versionControl.diff.jumpToWhat';
    case '/flow': return 'versionControl.diff.jumpToFlow';
    case '/scope': return 'versionControl.diff.jumpToScope';
    default: return 'versionControl.diff.jumpToWhat';
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
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<DiffEntry | null>(null);
  const [collapsedTypes, setCollapsedTypes] = useState<Set<string>>(new Set());
  const [mobilePane, setMobilePane] = useState<'tree' | 'detail'>('tree');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await workspaceApi.getSemanticDiff(projectId, {
        base_ref: baseRef,
        target_ref: targetRef,
        branch,
        entity_type: entityType,
        change_type: changeType,
        limit: 500,
      });
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'versionControl.errors.loadDiffFailed');
    } finally {
      setLoading(false);
    }
  }, [projectId, baseRef, targetRef, branch, entityType, changeType]);

  useEffect(() => {
    void load();
  }, [load]);

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
    <div className="flex h-full min-h-0 flex-col gap-3">
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
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          {/* 左侧：变更树 */}
          <div className={cn('min-h-0 overflow-y-auto rounded-xl border border-slate-200 bg-white', mobilePane !== 'tree' && 'hidden md:block')}>
            <div className="border-b border-slate-100 px-3 py-2">
              <p className="text-xs font-bold text-slate-700">{t('versionControl.diff.treeTitle')}</p>
              {result.summary.total_added + result.summary.total_removed + result.summary.total_modified === 0 ? (
                <p className="mt-1 text-xs text-slate-400">{t('versionControl.diff.empty')}</p>
              ) : (
                <p className="mt-1 text-xs text-slate-500">
                  {t('versionControl.repository.changeSummary', {
                    added: result.summary.total_added,
                    removed: result.summary.total_removed,
                    modified: result.summary.total_modified,
                  })}
                </p>
              )}
            </div>

            {grouped.length === 0 && !loading && (
              <p className="px-3 py-4 text-sm text-slate-400">{t('versionControl.diff.empty')}</p>
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
                    className="flex w-full items-center gap-1.5 px-3 py-2 text-left text-sm hover:bg-slate-50"
                  >
                    <ChevronRight className={cn('h-4 w-4 text-slate-400 transition-transform', collapsed && '-rotate-90')} />
                    <span className="font-semibold text-slate-700">{t(typeLabelKey(group.type))}</span>
                    <span className="ml-auto text-xs text-slate-400">
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
                                'flex w-full items-start gap-2 px-3 py-1.5 text-left text-xs hover:bg-indigo-50',
                                isSelected && 'bg-indigo-50'
                              )}
                            >
                              <ChangeIcon type={entry.change_type} className={cn('mt-0.5 h-3.5 w-3.5', changeColor(entry.change_type))} />
                              <span className="min-w-0 flex-1">
                                <span className="block truncate font-medium text-slate-700">{entry.entity_name || entry.entity_uuid}</span>
                                <span className={cn('block text-[10px]', changeColor(entry.change_type))}>
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
          </div>

          {/* 右侧：详情 */}
          <div className={cn('min-h-0 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4', mobilePane !== 'detail' && 'hidden md:block')}>
            {!selected ? (
              <p className="text-sm text-slate-400">{t('versionControl.diff.selectNode')}</p>
            ) : (
              <EntryDetail entry={selected} t={t} onJump={onJump} />
            )}
          </div>
        </div>
        </>
      )}
    </div>
  );
}

// i18next 的 t 类型签名较长，这里用轻量类型收窄。
type TranslateFn = (key: string, options?: Record<string, unknown>) => string;

function EntryDetail({ entry, t, onJump }: { entry: DiffEntry; t: TranslateFn; onJump?: (entry: DiffEntry) => void }) {
  const before = entry.before;
  const after = entry.after;

  const renderValue = (value: unknown): string => {
    if (value === null || value === undefined) return '—';
    if (typeof value === 'object') return JSON.stringify(value, null, 2);
    return String(value);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <ChangeIcon type={entry.change_type} className={cn('h-4 w-4', changeColor(entry.change_type))} />
        <span className={cn('text-sm font-bold', changeColor(entry.change_type))}>{t(changeLabelKey(entry.change_type))}</span>
        <span className="text-xs text-slate-400">{t(typeLabelKey(entry.entity_type))}</span>
        {onJump && jumpTargetForEntity(entry.entity_type) && (
          <button
            type="button"
            onClick={() => onJump(entry)}
            className="ml-auto rounded border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[10px] font-semibold text-indigo-700 hover:bg-indigo-100"
          >
            {t(jumpLabelKey(entry.entity_type))}
          </button>
        )}
      </div>

      <div className="text-sm font-medium text-slate-700">{entry.entity_name || entry.entity_uuid}</div>
      {entry.field && <div className="text-xs text-slate-500">{t('versionControl.diff.fieldChanged')}: {entry.field}</div>}

      {(entry.change_type === 'relation_added' || entry.change_type === 'relation_removed') && (
        <div className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs">
          <p className="text-slate-500">{t('versionControl.diff.relation')}: {entry.relation_type || entry.path}</p>
          <p className="mt-1 font-medium text-slate-700">{entry.related_entity_name || entry.related_entity_uuid}</p>
        </div>
      )}

      {(entry.change_type === 'field_changed' || entry.change_type === 'entity_added' || entry.change_type === 'entity_removed') && (
        <>
          {(before !== undefined || after !== undefined) && (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {(entry.change_type === 'field_changed' || entry.change_type === 'entity_removed') && (
                <div className="rounded-lg border border-rose-100 bg-rose-50 p-3">
                  <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-rose-500">{t('versionControl.diff.before')}</p>
                  <pre className="whitespace-pre-wrap text-xs text-rose-800">{renderValue(before)}</pre>
                </div>
              )}
              {(entry.change_type === 'field_changed' || entry.change_type === 'entity_added') && (
                <div className="rounded-lg border border-emerald-100 bg-emerald-50 p-3">
                  <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-emerald-600">{t('versionControl.diff.after')}</p>
                  <pre className="whitespace-pre-wrap text-xs text-emerald-800">{renderValue(after)}</pre>
                </div>
              )}
            </div>
          )}

          {entry.text_blocks.length > 0 && (
            <div className="space-y-1 rounded-lg border border-slate-100 p-3">
              <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">{t('versionControl.diff.textChanges')}</p>
              {entry.text_blocks.map((block, i) => (
                <div key={i} className="text-xs">
                  {block.before_lines.map((line, j) => (
                    <p key={`b${j}`} className="bg-rose-50 px-2 text-rose-700">- {line}</p>
                  ))}
                  {block.after_lines.map((line, j) => (
                    <p key={`a${j}`} className="bg-emerald-50 px-2 text-emerald-700">+ {line}</p>
                  ))}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {entry.change_type === 'ordered_item_moved' && (
        <div className="rounded-lg border border-amber-100 bg-amber-50 p-3 text-xs text-amber-800">
          <p>{t('versionControl.diff.orderedMoved')}</p>
          {entry.before_position !== undefined && entry.after_position !== undefined && (
            <p className="mt-1">#{entry.before_position} → #{entry.after_position}</p>
          )}
        </div>
      )}
    </div>
  );
}
