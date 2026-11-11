import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertCircle, History, RotateCcw, X } from 'lucide-react';
import { workspaceApi } from '@/lib/api';
import { CommitDetail, CommitSummary } from '@/core/versionControl';
import { useModalDialog } from '@/lib/useModalDialog';

interface RevertCommitDialogProps {
  projectId: string;
  commit: CommitSummary | null;
  currentBranchName?: string;
  open: boolean;
  onClose: () => void;
  onReverted: (newCommit: CommitDetail) => void;
}

export function RevertCommitDialog({
  projectId,
  commit,
  currentBranchName,
  open,
  onClose,
  onReverted,
}: RevertCommitDialogProps) {
  const { t } = useTranslation();
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  useModalDialog(open, onClose, dialogRef);

  useEffect(() => {
    if (open && commit) {
      setMessage(t('versionControl.repository.revertDefaultMessage', {
        shortId: commit.short_id,
        message: commit.message,
        defaultValue: `回滚至提交: [@${commit.short_id}] ${commit.message}`,
      }));
      setError(null);
      setLoading(false);
    }
  }, [open, commit, t]);

  if (!open || !commit) return null;

  const handleRevert = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commit) return;
    setLoading(true);
    setError(null);

    try {
      const result = await workspaceApi.revertCommit(projectId, commit.public_id, {
        branch_ref: currentBranchName,
        message: message.trim() || undefined,
      });
      onReverted(result);
      onClose();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || t('versionControl.repository.revertFailed');
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="revert-commit-title"
        className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-5"
      >
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-50 text-amber-600 border border-amber-200">
              <RotateCcw className="h-4 w-4" />
            </div>
            <div>
              <h2 id="revert-commit-title" className="text-base font-black text-slate-900">
                {t('versionControl.repository.revertDialogTitle')}
              </h2>
              <p className="text-xs text-slate-400 font-medium">
                {t('versionControl.repository.revertCommitTarget')}: <span className="font-mono font-bold text-slate-700">@{commit.short_id}</span>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="rounded-xl border border-amber-200/80 bg-amber-50/60 p-3.5 text-xs text-amber-900 leading-relaxed flex items-start gap-2.5">
          <AlertCircle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
          <div>{t('versionControl.repository.revertDialogDesc')}</div>
        </div>

        <form onSubmit={handleRevert} className="space-y-4">
          <div className="rounded-xl bg-slate-50 p-3 border border-slate-100 text-xs space-y-2">
            <div className="flex items-center justify-between text-slate-500">
              <span>{t('versionControl.repository.revertBranchTarget')}:</span>
              <span className="font-bold text-slate-800 font-mono">{currentBranchName || t('versionControl.repository.currentBranch', '当前分支')}</span>
            </div>
            <div className="flex items-start justify-between text-slate-500 gap-2">
              <span className="shrink-0">{t('versionControl.repository.revertCommitTarget')}:</span>
              <span className="font-medium text-slate-700 line-clamp-2 text-right">
                <span className="font-mono font-bold text-indigo-600">@{commit.short_id}</span> - {commit.message}
              </span>
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">
              {t('versionControl.repository.revertMessageLabel')}
            </label>
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              required
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-800 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              placeholder={t('versionControl.repository.revertMessagePlaceholder', '请输入回滚提交的说明...')}
            />
          </div>

          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 font-medium">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50 transition-colors cursor-pointer"
            >
              {t('common.cancel')}
            </button>
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-1.5 rounded-xl bg-amber-600 px-4 py-2 text-xs font-bold text-white hover:bg-amber-700 transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
            >
              <History className="h-3.5 w-3.5" />
              {loading ? t('versionControl.repository.reverting') : t('versionControl.repository.revertConfirmButton')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
