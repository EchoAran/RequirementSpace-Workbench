import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { GitBranch } from 'lucide-react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { workspaceApi } from '@/lib/api';
import { useModalDialog } from '@/lib/useModalDialog';

interface CreateBranchDialogProps {
  open: boolean;
  onClose: () => void;
  /** 默认来源提交 public_id；缺省基于当前分支 head。 */
  sourceCommitPublicId?: string | null;
  onCreated?: (publicId: string) => void;
}

/**
 * 新建分支弹窗：输入名称与说明，可选从指定提交创建。
 */
export function CreateBranchDialog({ open, onClose, sourceCommitPublicId, onCreated }: CreateBranchDialogProps) {
  const { t } = useTranslation();
  const dialogRef = useRef<HTMLDivElement>(null);
  useModalDialog(open, onClose, dialogRef);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const projectId = useWorkspaceStore.getState().ir?.projectId;
  // 创建新分支是项目成员的通用能力，不受当前分支（含受保护 main）写权限限制。

  const submit = async () => {
    if (!projectId || !name.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await workspaceApi.createBranch(projectId, {
        name: name.trim(),
        description: description.trim() || undefined,
        source_commit_public_id: sourceCommitPublicId || undefined,
      });
      onCreated?.(created.public_id);
      setName('');
      setDescription('');
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'versionControl.errors.createBranchFailed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div ref={dialogRef} className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/60 p-4" role="dialog" aria-modal="true" aria-label={t('versionControl.createBranch.title')}>
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-4">
          <GitBranch className="h-5 w-5 text-indigo-600" />
          <h2 className="text-base font-bold text-slate-800">{t('versionControl.createBranch.title')}</h2>
        </div>

        <div className="space-y-4 px-5 py-4">
          <label className="block">
            <span className="mb-1 block text-xs font-semibold text-slate-600">{t('versionControl.createBranch.nameLabel')}</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('versionControl.createBranch.namePlaceholder')}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-semibold text-slate-600">{t('versionControl.createBranch.descriptionLabel')}</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
            />
          </label>

          {sourceCommitPublicId && (
            <p className="text-xs text-slate-400">
              {t('versionControl.commitDialog.expectedHead')}: {sourceCommitPublicId.slice(0, 8)}
            </p>
          )}

          {error && <p className="text-xs text-rose-600">{error}</p>}
        </div>

        <div className="flex justify-end gap-2 border-t border-slate-100 px-5 py-3">
          <button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50">
            {t('versionControl.createBranch.cancel')}
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={!name.trim() || submitting}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {submitting ? t('shell.loading') : t('versionControl.createBranch.submit')}
          </button>
        </div>
      </div>
    </div>
  );
}
