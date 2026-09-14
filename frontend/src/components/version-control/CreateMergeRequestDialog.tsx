import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertCircle, GitPullRequest } from 'lucide-react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { workspaceApi } from '@/lib/api';
import { useModalDialog } from '@/lib/useModalDialog';

interface CreateMergeRequestDialogProps {
  projectId: string;
  open: boolean;
  onClose: () => void;
  onCreated: (publicId: string) => void;
}

export function CreateMergeRequestDialog({ projectId, open, onClose, onCreated }: CreateMergeRequestDialogProps) {
  const { t } = useTranslation();
  const branches = useWorkspaceStore((s) => s.branches);
  const dialogRef = useRef<HTMLDivElement>(null);
  useModalDialog(open, onClose, dialogRef);
  const [source, setSource] = useState('');
  const [target, setTarget] = useState('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [diffPreview, setDiffPreview] = useState<{ added: number; removed: number; modified: number } | null>(null);

  useEffect(() => {
    if (!open) return;
    setSource('');
    setTarget('');
    setTitle('');
    setDescription('');
    setError(null);
    setDiffPreview(null);
  }, [open]);

  const list = (branches || []).filter((b) => b.status !== 'deleted');
  const selectedSourceBranch = list.find((b) => b.public_id === source);
  const isSourceEmpty = Boolean(selectedSourceBranch && !selectedSourceBranch.head_commit_id && !selectedSourceBranch.head_commit_public_id);
  // 计算 Diff 摘要预览（与后端 MR 创建后的摘要一致：merge_base → source_head）
  useEffect(() => {
    if (!source || !target || isSourceEmpty) { setDiffPreview(null); return; }
    workspaceApi.previewMergeRequest(projectId, {
      source_branch_public_id: source,
      target_branch_public_id: target,
    }).then((res) => {
      setDiffPreview({
        added: res.diff_summary.total_added,
        removed: res.diff_summary.total_removed,
        modified: res.diff_summary.total_modified,
      });
    }).catch(() => setDiffPreview(null));
  }, [source, target, projectId, isSourceEmpty]);

  if (!open) return null;

  const submit = async () => {
    if (!source || !target || !title.trim() || isSourceEmpty) return;
    setSubmitting(true);
    setError(null);
    try {
      const mr = await workspaceApi.createMergeRequest(projectId, {
        source_branch_public_id: source,
        target_branch_public_id: target,
        title: title.trim(),
        description: description.trim() || undefined,
      });
      onCreated(mr.public_id);
    } catch (e: any) {
      const errDetail = e?.detail || e?.response?.data?.detail || e?.message || '';
      if (errDetail === 'source_branch_empty') {
        setError(t('versionControl.errors.source_branch_empty') || '源分支尚无任何提交记录，请先在当前分支提交变更后再创建合并请求');
      } else if (errDetail === 'source_target_same') {
        setError(t('versionControl.errors.source_target_same') || '源分支与目标分支不能相同');
      } else if (errDetail === 'duplicate_open_mr') {
        setError(t('versionControl.errors.duplicate_open_mr') || '已存在同源同目标的开放合并请求，请勿重复创建');
      } else if (errDetail === 'source_branch_not_found') {
        setError(t('versionControl.errors.source_branch_not_found') || '未找到源分支');
      } else if (errDetail === 'target_branch_not_found') {
        setError(t('versionControl.errors.target_branch_not_found') || '未找到目标分支');
      } else if (errDetail === 'source_branch_required') {
        setError(t('versionControl.errors.source_branch_required') || '请选择源分支');
      } else if (errDetail === 'target_branch_required') {
        setError(t('versionControl.errors.target_branch_required') || '请选择目标分支');
      } else if (errDetail.includes('insufficient_project_role')) {
        setError(t('versionControl.errors.permission_denied') || '项目权限不足，无法创建合并请求');
      } else {
        setError(errDetail ? `${t('versionControl.createMr.failed')}: ${errDetail}` : t('versionControl.createMr.failed'));
      }
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
      aria-label={t('versionControl.createMr.ariaLabel')}
    >
      <div className="w-full max-w-lg rounded-3xl border border-slate-200/80 bg-white shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="flex items-center gap-3 border-b border-slate-100 bg-slate-50/50 px-6 py-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 border border-indigo-100 shadow-sm shrink-0">
            <GitPullRequest className="h-5 w-5" />
          </div>
          <h2 className="text-base font-black text-slate-900 tracking-tight">{t('versionControl.createMr.title')}</h2>
        </div>

        <div className="space-y-4 p-6 text-left">
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1.5 block text-xs font-bold text-slate-700">{t('versionControl.createMr.sourceBranch')}</span>
              <select
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3.5 py-2.5 text-xs text-slate-800 font-medium outline-none focus:bg-white focus:border-indigo-500 transition-all shadow-xs"
              >
                <option value="">{t('versionControl.createMr.select')}</option>
                {list.map((b) => <option key={b.public_id} value={b.public_id}>{b.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-bold text-slate-700">{t('versionControl.createMr.targetBranch')}</span>
              <select
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3.5 py-2.5 text-xs text-slate-800 font-medium outline-none focus:bg-white focus:border-indigo-500 transition-all shadow-xs"
              >
                <option value="">{t('versionControl.createMr.select')}</option>
                {list.map((b) => <option key={b.public_id} value={b.public_id}>{b.name}</option>)}
              </select>
            </label>
          </div>

          {isSourceEmpty && (
            <div className="flex items-start gap-2.5 rounded-2xl border border-amber-200 bg-amber-50/90 p-3.5 text-xs text-amber-800 font-medium">
              <AlertCircle className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
              <span>{t('versionControl.errors.source_branch_empty')}</span>
            </div>
          )}

          <label className="block">
            <span className="mb-1.5 block text-xs font-bold text-slate-700">{t('versionControl.createMr.titleLabel')}</span>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t('versionControl.createMr.titlePlaceholder')}
              className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3.5 py-2.5 text-xs text-slate-800 font-medium outline-none focus:bg-white focus:border-indigo-500 transition-all shadow-xs"
            />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-xs font-bold text-slate-700">{t('versionControl.createMr.descriptionLabel')}</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-3.5 py-2.5 text-xs text-slate-800 font-medium outline-none focus:bg-white focus:border-indigo-500 transition-all shadow-xs"
            />
          </label>

          {diffPreview && (
            <div className="rounded-2xl border border-slate-100 bg-slate-50/80 p-3.5 text-xs text-slate-600 font-medium">
              {t('versionControl.createMr.changesPreview', { added: diffPreview.added, modified: diffPreview.modified, removed: diffPreview.removed })}
            </div>
          )}

          {error && <p className="text-xs font-bold text-rose-600">{error.startsWith('versionControl.') ? t(error) : error}</p>}
        </div>

        <div className="flex justify-end gap-2.5 border-t border-slate-100 bg-slate-50/60 px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-600 hover:bg-slate-50 transition-all cursor-pointer"
          >
            {t('versionControl.createMr.cancel')}
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={!source || !target || !title.trim() || submitting || isSourceEmpty}
            className="rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-bold text-white shadow-md hover:bg-indigo-700 active:scale-95 disabled:bg-slate-300 disabled:cursor-not-allowed transition-all cursor-pointer"
          >
            {submitting ? t('versionControl.createMr.creating') : t('versionControl.createMr.create')}
          </button>
        </div>
      </div>
    </div>
  );
}
