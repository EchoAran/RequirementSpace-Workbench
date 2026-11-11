import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { GitBranch, AlertCircle } from 'lucide-react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { useAuthStore } from '@/store/useAuthStore';
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
  const [loadingRole, setLoadingRole] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentUserRole, setCurrentUserRole] = useState<string | null>(null);

  const user = useAuthStore((s) => s.user);
  const projectId = useWorkspaceStore.getState().ir?.projectId;
  const branchRef = useWorkspaceStore((s) => s.branchRef);

  useEffect(() => {
    if (open && projectId && user?.id) {
      setLoadingRole(true);
      workspaceApi.listProjectMembers(projectId)
        .then((members) => {
          const m = members.find((item) => item.userId === user.id);
          setCurrentUserRole(m?.role || 'viewer');
        })
        .catch(() => setCurrentUserRole(null))
        .finally(() => setLoadingRole(false));
    } else if (!open) {
      setCurrentUserRole(null);
      setLoadingRole(false);
    }
  }, [open, projectId, user?.id]);

  if (!open) return null;

  const isReadOnlyRole = currentUserRole === null || currentUserRole === 'viewer' || currentUserRole === 'reviewer';

  const submit = async () => {
    if (!projectId || !name.trim() || isReadOnlyRole || loadingRole) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await workspaceApi.createBranch(projectId, {
        name: name.trim(),
        description: description.trim() || undefined,
        source_commit_public_id: sourceCommitPublicId || undefined,
        source_branch_public_id: sourceCommitPublicId ? undefined : branchRef,
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
    <div
      ref={dialogRef}
      className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
      aria-label={t('versionControl.createBranch.title')}
    >
      <div className="w-full max-w-md rounded-3xl border border-slate-200/80 bg-white shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="flex items-center gap-3 border-b border-slate-100 bg-slate-50/50 px-6 py-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 border border-indigo-100 shadow-sm shrink-0">
            <GitBranch className="h-5 w-5" />
          </div>
          <h2 className="text-base font-black text-slate-900 tracking-tight">{t('versionControl.createBranch.title')}</h2>
        </div>

        <div className="space-y-4 p-6">
          <label className="block text-left">
            <span className="mb-1.5 block text-xs font-bold text-slate-700">{t('versionControl.createBranch.nameLabel')}</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('versionControl.createBranch.namePlaceholder')}
              className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3.5 py-2.5 text-xs text-slate-800 font-medium outline-none focus:bg-white focus:border-indigo-500 transition-all shadow-xs"
            />
          </label>

          <label className="block text-left">
            <span className="mb-1.5 block text-xs font-bold text-slate-700">{t('versionControl.createBranch.descriptionLabel')}</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3.5 py-2.5 text-xs text-slate-800 font-medium outline-none focus:bg-white focus:border-indigo-500 transition-all shadow-xs"
            />
          </label>

          {sourceCommitPublicId && (
            <p className="text-xs text-slate-400 font-medium text-left">
              {t('versionControl.commitDialog.expectedHead')}: <span className="font-mono text-slate-600">{sourceCommitPublicId.slice(0, 8)}</span>
            </p>
          )}

          {isReadOnlyRole && !loadingRole && (
            <div className="flex items-center gap-2 rounded-2xl bg-amber-50/80 p-3 text-xs font-medium text-amber-800 border border-amber-200">
              <AlertCircle className="h-4 w-4 shrink-0 text-amber-600" />
              <span>{t('versionControl.errors.branchCreationForbidden', '当前项目角色（Viewer/Reviewer）为只读模式，无权创建分支。')}</span>
            </div>
          )}

          {error && <p className="text-xs font-bold text-rose-600 text-left">{error}</p>}
        </div>

        <div className="flex justify-end gap-2.5 border-t border-slate-100 bg-slate-50/60 px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-600 hover:bg-slate-50 transition-all cursor-pointer"
          >
            {t('versionControl.createBranch.cancel')}
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={!name.trim() || submitting || isReadOnlyRole || loadingRole}
            className="rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-bold text-white shadow-md hover:bg-indigo-700 active:scale-95 disabled:cursor-not-allowed disabled:bg-slate-300 transition-all cursor-pointer"
          >
            {submitting || loadingRole ? t('shell.loading') : t('versionControl.createBranch.submit')}
          </button>
        </div>
      </div>
    </div>
  );
}
