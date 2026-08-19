import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { GitCommitHorizontal, X } from 'lucide-react';
import { workspaceApi } from '@/lib/api';
import { CommitDetail } from '@/core/versionControl';
import { useModalDialog } from '@/lib/useModalDialog';

/**
 * 历史版本只读查看弹窗（Phase F）。
 *
 * 打开时通过 getCommitDetail 拉取该提交的完整规范化 state，按对象类型分区只读渲染。
 * 只读快照直接消费后端 state 结构（键为 logical_uuid），不接入当前 IR。
 */

interface CommitDetailDialogProps {
  projectId: string;
  commitRef: string | null;
  open: boolean;
  onClose: () => void;
}

const SECTIONS: { key: string; labelKey: string }[] = [
  { key: 'actors', labelKey: 'versionControl.diff.entityType.actor' },
  { key: 'features', labelKey: 'versionControl.diff.entityType.feature' },
  { key: 'scenarios', labelKey: 'versionControl.diff.entityType.scenario' },
  { key: 'business_objects', labelKey: 'versionControl.diff.entityType.business_object' },
  { key: 'flows', labelKey: 'versionControl.diff.entityType.flow' },
  { key: 'scopes', labelKey: 'versionControl.diff.entityType.scope' },
];

export function CommitDetailDialog({ projectId, commitRef, open, onClose }: CommitDetailDialogProps) {
  const { t } = useTranslation();
  const [detail, setDetail] = useState<CommitDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  useModalDialog(open, onClose, dialogRef);

  const load = useCallback(() => {
    if (!open || !commitRef) return;
    setLoading(true);
    setDetail(null);
    workspaceApi.getCommitDetail(projectId, commitRef)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, [projectId, commitRef, open]);

  useEffect(() => { load(); }, [load]);

  if (!open) return null;

  const state = detail?.state as Record<string, unknown> | undefined;

  return (
    <div ref={dialogRef} className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/60 p-4" role="dialog" aria-modal="true" aria-label={t('versionControl.commitDetail.title')}>
      <div className="flex h-[80vh] w-full max-w-2xl flex-col rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-4">
          <GitCommitHorizontal className="h-5 w-5 text-indigo-600" />
          <h2 className="text-base font-bold text-slate-800">{t('versionControl.commitDetail.title')}</h2>
          {detail && (
            <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-[10px] text-slate-500">{detail.short_id}</span>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label={t('versionControl.commitDetail.close')}
            className="ml-auto rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {loading && <p className="text-sm text-slate-400">{t('shell.loading')}</p>}
          {!loading && detail && (
            <div className="mb-4 space-y-1 text-xs text-slate-500">
              <p className="font-bold text-slate-800">{detail.message}</p>
              <p>{detail.author_email || detail.author_user_id || '-'}</p>
              <p>{new Date(detail.created_at).toLocaleString()}</p>
              {detail.branch_names.length > 0 && (
                <p>{detail.branch_names.join(', ')}</p>
              )}
            </div>
          )}
          {!loading && (!state || Object.keys(state).length === 0) && (
            <p className="text-sm text-slate-400">{t('versionControl.commitDetail.empty')}</p>
          )}
          {!loading && state && (
            <div className="space-y-4">
              {SECTIONS.map((section) => {
                const items = (state[section.key] as Array<Record<string, unknown>> | undefined) || [];
                if (items.length === 0) return null;
                return (
                  <div key={section.key}>
                    <p className="mb-1.5 border-b border-slate-100 pb-1 text-xs font-bold text-slate-700">
                      {t(section.labelKey)} ({items.length})
                    </p>
                    <ul className="space-y-1.5">
                      {items.map((item) => (
                        <li key={String(item.logical_uuid ?? '')} className="rounded-lg border border-slate-100 bg-slate-50/50 p-2 text-xs">
                          <p className="font-medium text-slate-800">
                            {String(item.name ?? item.content ?? item.logical_uuid ?? '')}
                          </p>
                          <p className="mt-0.5 text-slate-400">
                            <span className="font-mono">{String(item.logical_uuid ?? '').slice(0, 8)}</span>
                            {item.confirmation_status && <span className="ml-2">{String(item.confirmation_status)}</span>}
                          </p>
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
