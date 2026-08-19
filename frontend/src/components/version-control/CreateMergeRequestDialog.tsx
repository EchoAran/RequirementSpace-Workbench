import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { GitPullRequest } from 'lucide-react';
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

  // 计算 Diff 摘要预览（与后端 MR 创建后的摘要一致：merge_base → source_head）
  useEffect(() => {
    if (!source || !target) { setDiffPreview(null); return; }
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
  }, [source, target, projectId]);

  if (!open) return null;

  const list = (branches || []).filter((b) => b.status !== 'deleted');

  const submit = async () => {
    if (!source || !target || !title.trim()) return;
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
      setError('versionControl.createMr.failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div ref={dialogRef} className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/60 p-4" role="dialog" aria-modal="true" aria-label={t('versionControl.createMr.ariaLabel')}>
      <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-4">
          <GitPullRequest className="h-5 w-5 text-indigo-600" />
          <h2 className="text-base font-bold text-slate-800">{t('versionControl.createMr.title')}</h2>
        </div>

        <div className="space-y-4 px-5 py-4">
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1 block text-xs font-semibold text-slate-600">{t('versionControl.createMr.sourceBranch')}</span>
              <select value={source} onChange={(e) => setSource(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
                <option value="">{t('versionControl.createMr.select')}</option>
                {list.map((b) => <option key={b.public_id} value={b.public_id}>{b.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-semibold text-slate-600">{t('versionControl.createMr.targetBranch')}</span>
              <select value={target} onChange={(e) => setTarget(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
                <option value="">{t('versionControl.createMr.select')}</option>
                {list.map((b) => <option key={b.public_id} value={b.public_id}>{b.name}</option>)}
              </select>
            </label>
          </div>

          <label className="block">
            <span className="mb-1 block text-xs font-semibold text-slate-600">{t('versionControl.createMr.titleLabel')}</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t('versionControl.createMr.titlePlaceholder')}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500" />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-semibold text-slate-600">{t('versionControl.createMr.descriptionLabel')}</span>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500" />
          </label>

          {diffPreview && (
            <div className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs text-slate-600">
              {t('versionControl.createMr.changesPreview', { added: diffPreview.added, modified: diffPreview.modified, removed: diffPreview.removed })}
            </div>
          )}

          {error && <p className="text-xs text-rose-600">{error}</p>}
        </div>

        <div className="flex justify-end gap-2 border-t border-slate-100 px-5 py-3">
          <button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50">{t('versionControl.createMr.cancel')}</button>
          <button type="button" onClick={submit} disabled={!source || !target || !title.trim() || submitting}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:bg-slate-300">
            {submitting ? t('versionControl.createMr.creating') : t('versionControl.createMr.create')}
          </button>
        </div>
      </div>
    </div>
  );
}
