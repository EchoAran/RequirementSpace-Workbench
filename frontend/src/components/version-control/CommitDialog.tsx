import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { GitCommitHorizontal, GitFork, Lock, RefreshCw } from 'lucide-react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { workspaceApi } from '@/lib/api';
import { DiffSummary } from '@/core/versionControl';
import { useModalDialog } from '@/lib/useModalDialog';

interface CommitDialogProps {
  open: boolean;
  onClose: () => void;
  onCompare?: () => void;
}

/**
 * 提交变更弹窗：填写提交说明，展示本次语义变更摘要与预期 head，
 * 并处理无变更/无权限/受保护/409 冲突等状态。
 */
export function CommitDialog({ open, onClose, onCompare }: CommitDialogProps) {
  const { t } = useTranslation();
  const currentBranch = useWorkspaceStore((s) => s.currentBranch);
  const commitLoading = useWorkspaceStore((s) => s.commitLoading);
  const commitError = useWorkspaceStore((s) => s.commitError);
  const createCommit = useWorkspaceStore((s) => s.createCommit);
  const refreshWorkspace = useWorkspaceStore((s) => s.refreshWorkspace);
  const loadCommits = useWorkspaceStore((s) => s.loadCommits);
  const [message, setMessage] = useState('');
  const [summary, setSummary] = useState<DiffSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);

  const isProtected = currentBranch?.is_protected || currentBranch?.name === 'main';
  const canWrite = Boolean(currentBranch?.permissions?.can_write) && !isProtected;
  const dirty = currentBranch?.workspace_dirty;
  const hasChanges = Boolean(dirty?.is_dirty && (dirty?.modified_entities_count ?? 0) > 0);
  const isConflict = commitError === 'versionControl.commitConflict';
  const dialogRef = useRef<HTMLDivElement>(null);
  useModalDialog(open, onClose, dialogRef);

  useEffect(() => {
    if (!open) return;
    setMessage('');
    setSummary(null);
    const projectId = useWorkspaceStore.getState().ir?.projectId;
    if (!projectId || !currentBranch?.public_id) return;
    let cancelled = false;
    setSummaryLoading(true);
    workspaceApi
      .getSemanticDiff(projectId, { branch: currentBranch.public_id, limit: 1 })
      .then((res) => {
        if (!cancelled) setSummary(res.summary);
      })
      .catch(() => {
        if (!cancelled) setSummary(null);
      })
      .finally(() => {
        if (!cancelled) setSummaryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, currentBranch?.public_id]);

  if (!open) return null;

  const submit = async () => {
    if (!message.trim() || !canWrite) return;
    const ok = await createCommit(message.trim(), currentBranch?.head_commit_public_id ?? '');
    if (ok) {
      setMessage('');
      onClose();
    }
  };

  const refresh = () => {
    void refreshWorkspace();
    void loadCommits();
    setSummary(null);
  };

  return (
    <div ref={dialogRef} className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/60 p-4" role="dialog" aria-modal="true" aria-label={t('versionControl.commitDialog.title')}>
      <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-4">
          <GitCommitHorizontal className="h-5 w-5 text-indigo-600" />
          <h2 className="text-base font-bold text-slate-800">{t('versionControl.commitDialog.title')}</h2>
        </div>

        <div className="space-y-4 px-5 py-4">
          {isProtected && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              <Lock className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <p>{t('versionControl.commitDisabledProtected')}</p>
            </div>
          )}

          {!isProtected && !canWrite && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
              {t('versionControl.commitDialog.noPermission') || 'no permission'}
            </div>
          )}

          {!isProtected && !hasChanges && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
              {t('versionControl.commitDisabledNoChanges')}
            </div>
          )}

          {isConflict && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
              <p className="font-semibold">{t('versionControl.commitDialog.conflictTitle')}</p>
              <p className="mt-1">{t('versionControl.commitDialog.conflictMessage')}</p>
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  onClick={refresh}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-rose-700"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  {t('versionControl.commitDialog.refresh')}
                </button>
                {onCompare && (
                  <button
                    type="button"
                    onClick={() => { onClose(); onCompare(); }}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-rose-300 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-100"
                  >
                    {t('versionControl.commitDialog.compare')}
                  </button>
                )}
              </div>
            </div>
          )}

          {!isProtected && (
            <>
              <label className="block">
                <span className="mb-1 block text-xs font-semibold text-slate-600">
                  {t('versionControl.commitDialog.messageLabel')}
                </span>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  rows={3}
                  placeholder={t('versionControl.commitDialog.messagePlaceholder')}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
                />
              </label>

              <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                <p className="mb-1 text-xs font-semibold text-slate-500">{t('versionControl.commitDialog.summaryTitle')}</p>
                {summaryLoading ? (
                  <p className="text-xs text-slate-400">{t('shell.loading')}</p>
                ) : summary ? (
                  <p className="text-xs text-slate-700">
                    {t('versionControl.repository.changeSummary', {
                      added: summary.total_added,
                      removed: summary.total_removed,
                      modified: summary.total_modified,
                    })}
                  </p>
                ) : (
                  <p className="text-xs text-slate-400">{t('versionControl.diff.empty')}</p>
                )}
              </div>

              <p className="flex items-center gap-1.5 text-xs text-slate-400">
                <GitFork className="h-3.5 w-3.5" />
                {t('versionControl.commitDialog.expectedHead')}: {currentBranch?.head_commit_public_id?.slice(0, 8) || '-'}
              </p>

              {commitError && !isConflict && (
                <p className="text-xs text-rose-600">
                  {commitError.startsWith('versionControl.') ? t(commitError) : commitError}
                </p>
              )}
            </>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-slate-100 px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            {t('versionControl.commitDialog.cancel')}
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={!canWrite || !message.trim() || commitLoading}
            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            <GitCommitHorizontal className="h-4 w-4" />
            {commitLoading ? t('shell.loading') : t('versionControl.commit')}
          </button>
        </div>
      </div>
    </div>
  );
}
