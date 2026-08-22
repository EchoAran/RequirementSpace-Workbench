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
    <div
      ref={dialogRef}
      className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
      aria-label={t('versionControl.commitDialog.title')}
    >
      <div className="w-full max-w-lg rounded-3xl border border-slate-200/80 bg-white shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="flex items-center gap-3 border-b border-slate-100 bg-slate-50/50 px-6 py-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 border border-indigo-100 shadow-sm shrink-0">
            <GitCommitHorizontal className="h-5 w-5" />
          </div>
          <h2 className="text-base font-black text-slate-900 tracking-tight">{t('versionControl.commitDialog.title')}</h2>
        </div>

        <div className="space-y-4 p-6 text-left">
          {isProtected && (
            <div className="flex items-start gap-2.5 rounded-2xl border border-amber-200 bg-amber-50/80 p-3.5 text-xs text-amber-800">
              <Lock className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-600" />
              <p className="font-medium leading-relaxed">{t('versionControl.commitDisabledProtected')}</p>
            </div>
          )}

          {!isProtected && !canWrite && (
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3.5 text-xs text-slate-600 font-medium">
              {t('versionControl.commitDialog.noPermission') || 'no permission'}
            </div>
          )}

          {!isProtected && !hasChanges && (
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3.5 text-xs text-slate-600 font-medium">
              {t('versionControl.commitDisabledNoChanges')}
            </div>
          )}

          {isConflict && (
            <div className="rounded-2xl border border-rose-200 bg-rose-50/80 p-4 text-xs text-rose-800 space-y-2">
              <p className="font-bold">{t('versionControl.commitDialog.conflictTitle')}</p>
              <p className="font-medium leading-relaxed">{t('versionControl.commitDialog.conflictMessage')}</p>
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  onClick={refresh}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-rose-600 px-3.5 py-2 text-xs font-bold text-white shadow-sm hover:bg-rose-700 active:scale-95 transition-all cursor-pointer"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  {t('versionControl.commitDialog.refresh')}
                </button>
                {onCompare && (
                  <button
                    type="button"
                    onClick={() => { onClose(); onCompare(); }}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-rose-300 bg-white px-3.5 py-2 text-xs font-bold text-rose-700 hover:bg-rose-100/50 transition-all cursor-pointer"
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
                <span className="mb-1.5 block text-xs font-bold text-slate-700">
                  {t('versionControl.commitDialog.messageLabel')}
                </span>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  rows={3}
                  placeholder={t('versionControl.commitDialog.messagePlaceholder')}
                  className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3.5 py-2.5 text-xs text-slate-800 font-medium outline-none focus:bg-white focus:border-indigo-500 transition-all shadow-xs"
                />
              </label>

              <div className="rounded-2xl border border-slate-100 bg-slate-50/80 p-3.5 space-y-1">
                <p className="text-[11px] font-bold text-slate-500">{t('versionControl.commitDialog.summaryTitle')}</p>
                {summaryLoading ? (
                  <p className="text-xs text-slate-400 font-medium">{t('shell.loading')}</p>
                ) : summary ? (
                  <p className="text-xs text-slate-700 font-medium">
                    {t('versionControl.repository.changeSummary', {
                      added: summary.total_added,
                      removed: summary.total_removed,
                      modified: summary.total_modified,
                    })}
                  </p>
                ) : (
                  <p className="text-xs text-slate-400 font-medium">{t('versionControl.diff.empty')}</p>
                )}
              </div>

              <p className="flex items-center gap-1.5 text-xs text-slate-400 font-medium">
                <GitFork className="h-3.5 w-3.5" />
                {t('versionControl.commitDialog.expectedHead')}: <span className="font-mono text-slate-600">{currentBranch?.head_commit_public_id?.slice(0, 8) || '-'}</span>
              </p>

              {commitError && !isConflict && (
                <p className="text-xs font-bold text-rose-600">
                  {commitError.startsWith('versionControl.') ? t(commitError) : commitError}
                </p>
              )}
            </>
          )}
        </div>

        <div className="flex justify-end gap-2.5 border-t border-slate-100 bg-slate-50/60 px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-600 hover:bg-slate-50 transition-all cursor-pointer"
          >
            {t('versionControl.commitDialog.cancel')}
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={!canWrite || !message.trim() || commitLoading}
            className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-bold text-white shadow-md hover:bg-indigo-700 active:scale-95 disabled:cursor-not-allowed disabled:bg-slate-300 transition-all cursor-pointer"
          >
            <GitCommitHorizontal className="h-4 w-4" />
            {commitLoading ? t('shell.loading') : t('versionControl.commit')}
          </button>
        </div>
      </div>
    </div>
  );
}
