import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { GitMerge, ListChecks, ArrowRight, AlertTriangle } from 'lucide-react';
import { workspaceApi } from '@/lib/api';
import {
  ConflictChoice,
  ConflictItem,
  ConflictResolution,
  MergePreviewResponse,
  MergeResponse,
} from '@/core/versionControl';
import { cn } from '@/lib/utils';

interface ConflictResolutionViewProps {
  projectId: string;
  mrRef: string;
  sourceBranchName: string;
  targetBranchName: string;
  onMerged: (result: MergeResponse) => void;
  onCancel: () => void;
  onError: (message: string) => void;
}

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (Array.isArray(value)) return value.join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function ConflictTypeBadge({ type, t }: { type: string; t: (k: string) => string }) {
  const labelKey = `versionControl.conflict.conflictTypes.${type}`;
  return (
    <span className="inline-flex items-center gap-1 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">
      <AlertTriangle className="h-3 w-3" />
      {t(labelKey)}
    </span>
  );
}

/**
 * 冲突解决工作台（阶段 6）。
 * 布局遵循 UI/UX 设计文档 3.6：左侧冲突队列、中间 base/target/source 三列、右侧显式选择。
 * 冲突逐项解决：保留目标、保留来源、受限手工编辑；全部解决后才允许发起合并。
 */
export function ConflictResolutionView({
  projectId,
  mrRef,
  sourceBranchName,
  targetBranchName,
  onMerged,
  onCancel,
  onError,
}: ConflictResolutionViewProps) {
  const { t } = useTranslation();
  const [preview, setPreview] = useState<MergePreviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [mobilePane, setMobilePane] = useState<'queue' | 'compare' | 'choose'>('queue');
  const [resolutions, setResolutions] = useState<Record<string, ConflictResolution>>({});
  const [manualValue, setManualValue] = useState('');
  const [merging, setMerging] = useState(false);

  const loadPreview = useCallback(() => {
    setLoading(true);
    workspaceApi.getMergePreview(projectId, mrRef)
      .then(setPreview)
      .catch((e) => onError(e?.detail || e?.message || 'merge preview failed'))
      .finally(() => setLoading(false));
  }, [projectId, mrRef, onError]);

  useEffect(() => {
    loadPreview();
  }, [loadPreview]);

  const conflicts = preview?.conflicts ?? [];
  const current = conflicts[currentIndex] ?? null;

  const resolve = (conflict: ConflictItem, choice: ConflictChoice) => {
    const resolution: ConflictResolution = {
      conflict_id: conflict.conflict_id,
      choice,
      ...(choice === 'manual' ? { manual_value: manualValue } : {}),
    };
    setResolutions((prev) => ({ ...prev, [conflict.conflict_id]: resolution }));
  };

  const isResolved = (conflict: ConflictItem) => Boolean(resolutions[conflict.conflict_id]);
  const resolvedCount = conflicts.filter(isResolved).length;
  const allResolved = resolvedCount === conflicts.length;

  const doMerge = async () => {
    if (!allResolved || conflicts.length === 0 || !preview) return;
    setMerging(true);
    try {
      // 携带预览绑定的三方 heads，服务端据此校验 source/target 未在解决冲突期间推进。
      const result = await workspaceApi.performMerge(projectId, mrRef, {
        resolutions: Object.values(resolutions),
        merge_base_public_id: preview.merge_base_public_id,
        source_head_public_id: preview.source_head_public_id,
        target_head_public_id: preview.target_head_public_id,
      });
      onMerged(result);
    } catch (e: any) {
      onError(e?.detail?.message || e?.detail || e?.message || 'merge failed');
    } finally {
      setMerging(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-400">
        {t('versionControl.conflict.loading')}
      </div>
    );
  }

  if (conflicts.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
        {t('versionControl.conflict.noConflicts')}
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-4">
      {/* 顶部：标题与进度 */}
      <div className="flex items-center gap-2">
        <GitMerge className="h-5 w-5 text-indigo-600" />
        <h2 className="text-base font-bold text-slate-800">{t('versionControl.conflict.title')}</h2>
        <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
          {sourceBranchName} → {targetBranchName}
        </span>
        <span className="ml-auto text-xs text-slate-500">
          {t('versionControl.conflict.progress', { resolved: resolvedCount, total: conflicts.length })}
        </span>
      </div>

      {/* 移动端分段控件：队列 ↔ 对比 ↔ 选择（替代三栏垂直堆叠）。 */}
      <div className="flex items-center gap-1 md:hidden">
        {(['queue', 'compare', 'choose'] as const).map((pane) => (
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
            {pane === 'queue'
              ? t('versionControl.conflict.queueTitle')
              : pane === 'compare'
                ? t('versionControl.conflict.title')
                : t('versionControl.conflict.choose')}
          </button>
        ))}
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 md:grid-cols-[minmax(0,200px)_minmax(0,1fr)_minmax(0,220px)]">
        {/* 左侧冲突队列 */}
        <div className={cn('min-h-0 overflow-y-auto rounded-xl border border-slate-200 bg-white', mobilePane !== 'queue' && 'hidden md:block')}>
          <div className="border-b border-slate-100 px-3 py-2">
            <p className="flex items-center gap-1 text-xs font-bold text-slate-700">
              <ListChecks className="h-3.5 w-3.5" />
              {t('versionControl.conflict.queueTitle')}
            </p>
          </div>
          <ul className="p-1">
            {conflicts.map((conflict, idx) => (
              <li key={conflict.conflict_id}>
                <button
                  type="button"
                  onClick={() => { setCurrentIndex(idx); setMobilePane('compare'); }}
                  aria-current={idx === currentIndex ? 'true' : undefined}
                  className={cn(
                    'w-full rounded-lg px-2 py-1.5 text-left text-xs hover:bg-indigo-50',
                    idx === currentIndex && 'bg-indigo-50 ring-1 ring-indigo-200',
                    isResolved(conflict) && 'opacity-60'
                  )}
                >
                  <div className="flex items-center gap-1.5">
                    <span aria-hidden="true" className={cn('h-1.5 w-1.5 rounded-full', isResolved(conflict) ? 'bg-emerald-500' : 'bg-amber-500')} />
                    <span className="sr-only">{isResolved(conflict) ? t('versionControl.conflict.resolved') : t('versionControl.conflict.unresolved')}</span>
                    <span className="truncate font-medium text-slate-700">{conflict.entity_name || conflict.entity_type}</span>
                  </div>
                  <p className="mt-0.5 truncate pl-3 text-[10px] text-slate-400">{conflict.path}</p>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* 中间 base/target/source 三列 */}
        <div className={cn('min-h-0 overflow-y-auto rounded-xl border border-slate-200 bg-white p-3', mobilePane !== 'compare' && 'hidden md:block')}>
          {current && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <ConflictTypeBadge type={current.conflict_type} t={t} />
                <span className="text-xs text-slate-500">
                  {current.entity_type} · {current.entity_name || current.entity_uuid}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
                  <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-slate-500">{t('versionControl.conflict.base')}</p>
                  <pre className="whitespace-pre-wrap break-all text-xs text-slate-600">{renderValue(current.base_value)}</pre>
                </div>
                <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-2">
                  <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-indigo-600">
                    {t('versionControl.conflict.target')} ({targetBranchName})
                  </p>
                  <pre className="whitespace-pre-wrap break-all text-xs text-slate-700">{renderValue(current.target_value)}</pre>
                </div>
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-2">
                  <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-emerald-600">
                    {t('versionControl.conflict.source')} ({sourceBranchName})
                  </p>
                  <pre className="whitespace-pre-wrap break-all text-xs text-slate-700">{renderValue(current.source_value)}</pre>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 右侧选择面板 */}
        <div className={cn('min-h-0 overflow-y-auto rounded-xl border border-slate-200 bg-white p-3', mobilePane !== 'choose' && 'hidden md:block')}>
          <p className="mb-2 text-xs font-bold text-slate-700">{t('versionControl.conflict.choose')}</p>
          {current && (
            <div className="space-y-2">
              <button
                type="button"
                onClick={() => resolve(current, 'target')}
                aria-pressed={resolutions[current.conflict_id]?.choice === 'target'}
                className={cn(
                  'w-full rounded-lg border px-3 py-2 text-left text-xs font-medium transition-colors',
                  resolutions[current.conflict_id]?.choice === 'target'
                    ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                    : 'border-slate-200 text-slate-700 hover:bg-slate-50'
                )}
              >
                {t('versionControl.conflict.keepTarget', { branch: targetBranchName })}
              </button>
              <button
                type="button"
                onClick={() => resolve(current, 'source')}
                aria-pressed={resolutions[current.conflict_id]?.choice === 'source'}
                className={cn(
                  'w-full rounded-lg border px-3 py-2 text-left text-xs font-medium transition-colors',
                  resolutions[current.conflict_id]?.choice === 'source'
                    ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
                    : 'border-slate-200 text-slate-700 hover:bg-slate-50'
                )}
              >
                {t('versionControl.conflict.keepSource', { branch: sourceBranchName })}
              </button>

              {/* 受限手工编辑：仅字段冲突支持 */}
              {current.conflict_type === 'same_field_different_value' && (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
                  <p className="mb-1 text-[10px] font-semibold text-slate-600">{t('versionControl.conflict.manualEdit')}</p>
                  <input
                    value={manualValue}
                    onChange={(e) => setManualValue(e.target.value)}
                    placeholder={t('versionControl.conflict.manualValue')}
                    className="w-full rounded border border-slate-200 bg-white px-2 py-1 text-xs"
                  />
                  <button
                    type="button"
                    disabled={!manualValue.trim()}
                    onClick={() => resolve(current, 'manual')}
                    className="mt-1 w-full rounded bg-slate-700 px-2 py-1 text-[11px] font-semibold text-white hover:bg-slate-800 disabled:bg-slate-300"
                  >
                    {t('versionControl.conflict.applyManual')}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* 底部操作 */}
          <div className="mt-4 space-y-2 border-t border-slate-100 pt-3">
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={() => setCurrentIndex((i) => Math.max(0, i - 1))}
                disabled={currentIndex === 0}
                className="rounded border border-slate-200 px-2 py-1 text-[11px] text-slate-500 hover:bg-slate-50 disabled:opacity-40"
              >
                {t('versionControl.conflict.previous')}
              </button>
              <button
                type="button"
                onClick={() => setCurrentIndex((i) => Math.min(conflicts.length - 1, i + 1))}
                disabled={currentIndex >= conflicts.length - 1}
                className="rounded border border-slate-200 px-2 py-1 text-[11px] text-slate-500 hover:bg-slate-50 disabled:opacity-40"
              >
                {t('versionControl.conflict.next')}
              </button>
            </div>
            <button
              type="button"
              onClick={doMerge}
              disabled={!allResolved || merging}
              className={cn(
                'flex w-full items-center justify-center gap-1 rounded-lg px-3 py-2 text-xs font-semibold text-white transition-colors',
                allResolved && !merging ? 'bg-indigo-600 hover:bg-indigo-700' : 'bg-slate-300'
              )}
            >
              <ArrowRight className="h-3.5 w-3.5" />
              {merging ? t('versionControl.conflict.merging') : t('versionControl.conflict.mergeNow')}
            </button>
            {!allResolved && (
              <p className="text-center text-[10px] text-slate-400">
                {t('versionControl.conflict.remaining', { count: conflicts.length - resolvedCount })}
              </p>
            )}
            <button
              type="button"
              onClick={onCancel}
              className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-500 hover:bg-slate-50"
            >
              {t('versionControl.conflict.cancel')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
