import { useEffect, useState } from 'react';
import { GitPullRequest, Check, X, MessageSquare, RotateCcw, Plus, GitMerge } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { workspaceApi } from '@/lib/api';
import {
  MergeRequestSummary,
  MergeRequestDetail,
  DiffEntry,
} from '@/core/versionControl';
import { SemanticDiffView } from './SemanticDiffView';
import { extractVcError, extractActionError } from '@/core/versionControlErrors';
import { CreateMergeRequestDialog } from './CreateMergeRequestDialog';
import { ConflictResolutionView } from './ConflictResolutionView';
import { cn } from '@/lib/utils';

interface MergeRequestViewProps {
  projectId: string;
}

export function MergeRequestView({ projectId }: MergeRequestViewProps) {
  const { t } = useTranslation();
  const [mrs, setMrs] = useState<MergeRequestSummary[]>([]);
  const [mrTotal, setMrTotal] = useState(0);
  const [loadingMrs, setLoadingMrs] = useState(false);
  const [selectedMr, setSelectedMr] = useState<MergeRequestDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [reviewComment, setReviewComment] = useState('');
  const [reviewDecision, setReviewDecision] = useState<'approved' | 'changes_requested'>('approved');
  const [showConflictView, setShowConflictView] = useState(false);
  const [mergeError, setMergeError] = useState('');
  const [mergeErrorInfo, setMergeErrorInfo] = useState<{ code?: string; reasons?: string[]; compareRef?: string } | null>(null);
  const [actionError, setActionError] = useState('');
  const [merging, setMerging] = useState(false);
  const navigate = useNavigate();
  const [showCreateMr, setShowCreateMr] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<DiffEntry | null>(null);
  const [newComment, setNewComment] = useState('');
  const [newCommentRequired, setNewCommentRequired] = useState(false);

  const addComment = async () => {
    if (!selectedMr || !newComment.trim()) return;
    setActionError('');
    try {
      await workspaceApi.addMergeRequestComment(projectId, selectedMr.public_id, {
        entity_uuid: selectedEntry?.entity_uuid,
        field_path: (selectedEntry?.field ?? selectedEntry?.path) || undefined,
        relation_key: selectedEntry?.relation_type,
        comment: newComment.trim(),
        required: newCommentRequired,
      });
      setNewComment('');
      setSelectedEntry(null);
      setNewCommentRequired(false);
      selectMr(selectedMr);
    } catch (e: any) {
      setActionError(t('versionControl.mergeRequest.errors.commentFailed'));
    }
  };

  const loads = () => {
    setLoadingMrs(true);
    workspaceApi.listMergeRequests(projectId, { limit: 50 }).then((res) => {
      setMrs(res.items);
      setMrTotal(res.total);
    }).finally(() => setLoadingMrs(false));
  };

  useEffect(() => { loads(); }, [projectId]);

  const selectMr = (mr: MergeRequestSummary) => {
    setLoadingDetail(true);
    workspaceApi.getMergeRequestDetail(projectId, mr.public_id).then((d) => {
      setSelectedMr(d);
    }).finally(() => setLoadingDetail(false));
  };

  const submitReview = async () => {
    if (!selectedMr) return;
    setActionError('');
    try {
      await workspaceApi.reviewMergeRequest(projectId, selectedMr.public_id, {
        decision: reviewDecision,
        comment: reviewComment,
      });
      selectMr(selectedMr);
      loads();
    } catch (e: any) {
      setActionError(extractActionError(e));
    }
  };

  const doClose = async () => {
    if (!selectedMr) return;
    setActionError('');
    try {
      await workspaceApi.closeMergeRequest(projectId, selectedMr.public_id);
      setSelectedMr(null);
      loads();
    } catch (e: any) {
      setActionError(extractActionError(e));
    }
  };

  const startMerge = async () => {
    if (!selectedMr) return;
    setMergeError('');
    setMerging(true);
    try {
      const preview = await workspaceApi.getMergePreview(projectId, selectedMr.public_id);
      if (preview.conflict_count === 0) {
        // 直接合并时携带预览绑定的三方 heads，服务端据此校验 source/target 未在预览后推进。
        const result = await workspaceApi.performMerge(projectId, selectedMr.public_id, {
          resolutions: [],
          merge_base_public_id: preview.merge_base_public_id,
          source_head_public_id: preview.source_head_public_id,
          target_head_public_id: preview.target_head_public_id,
        });
        setShowConflictView(false);
        loads();
        selectMr(selectedMr);
        setMergeError('');
        return result;
      }
      // 存在冲突：打开冲突解决视图
      setShowConflictView(true);
    } catch (e: any) {
      const { token, info } = extractVcError(e);
      setMergeError(token);
      setMergeErrorInfo(info);
    } finally {
      setMerging(false);
    }
  };

  const statusClass = (status: string) => {
    switch (status) {
      case 'open': return 'bg-blue-100 text-blue-700';
      case 'approved': case 'mergeable': return 'bg-emerald-100 text-emerald-700';
      case 'changes_requested': return 'bg-amber-100 text-amber-700';
      case 'merged': return 'bg-purple-100 text-purple-700';
      case 'closed': return 'bg-slate-100 text-slate-500';
      default: return 'bg-slate-100 text-slate-600';
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-5">
      <div className="flex items-center gap-2">
        <GitPullRequest className="h-5 w-5 text-indigo-600" />
        <h1 className="text-lg font-bold text-slate-800">{t('versionControl.mergeRequest.listTitle')}</h1>
        <span className="text-sm text-slate-400">{t('versionControl.mergeRequest.total', { count: mrTotal })}</span>
        <button
          onClick={() => setShowCreateMr(true)}
          className="ml-auto inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700"
        >
          <Plus className="h-3.5 w-3.5" /> {t('versionControl.mergeRequest.newMr')}
        </button>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 md:grid-cols-[minmax(0,240px)_minmax(0,1fr)]">
        {/* MR 列表 */}
        <div className="min-h-0 overflow-y-auto rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-3 py-2">
            <p className="text-xs font-bold text-slate-700">{t('versionControl.mergeRequest.openMrs')}</p>
          </div>
          {loadingMrs && <p className="px-3 py-2 text-xs text-slate-400">{t('shell.loading')}</p>}
          {!loadingMrs && mrs.length === 0 && <p className="px-3 py-2 text-xs text-slate-400">{t('versionControl.mergeRequest.noMrs')}</p>}
          <ul>
            {mrs.map((mr) => (
              <li key={mr.public_id}>
                <button
                  type="button"
                  onClick={() => selectMr(mr)}
                  className={cn(
                    'w-full border-b border-slate-50 px-3 py-2 text-left hover:bg-indigo-50',
                    selectedMr?.public_id === mr.public_id && 'bg-indigo-50'
                  )}
                >
                  <p className="text-sm font-medium text-slate-800 truncate">{mr.title}</p>
                  <p className="text-xs text-slate-500">{mr.source_branch_name} → {mr.target_branch_name}</p>
                  <div className="mt-1 flex items-center gap-1.5">
                    <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-semibold', statusClass(mr.status))}>
                      {t(`versionControl.mergeRequest.status.${mr.status}`)}
                    </span>
                    {mr.active_review_count > 0 && <span className="text-[10px] text-emerald-600">✓{mr.active_review_count}</span>}
                    {mr.total_comments > 0 && <span className="text-[10px] text-slate-400">💬{mr.total_comments}</span>}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* MR 详情 */}
        <div className="min-h-0 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4">
          {!selectedMr ? (
            <p className="text-sm text-slate-400">{t('versionControl.mergeRequest.selectPlaceholder')}</p>
          ) : loadingDetail ? (
            <p className="text-sm text-slate-400">{t('shell.loading')}</p>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-bold text-slate-800">{selectedMr.title}</h2>
                <span className={cn('rounded px-2 py-0.5 text-xs font-semibold', statusClass(selectedMr.status))}>
                  {t(`versionControl.mergeRequest.status.${selectedMr.status}`)}
                </span>
              </div>

              <p className="text-sm text-slate-600">
                {selectedMr.source_branch_name} → {selectedMr.target_branch_name}
                {selectedMr.source_head_short && <span className="ml-2 font-mono text-xs text-slate-400">@{selectedMr.source_head_short}</span>}
              </p>

              {selectedMr.description && <p className="text-xs text-slate-500">{selectedMr.description}</p>}

              {/* Diff 摘要快照 */}
              {selectedMr.merge_base_public_id && selectedMr.source_head_public_id && (
                <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                  <p className="mb-2 text-xs font-bold text-slate-600">{t('versionControl.mergeRequest.changesHeader', { base: 'merge_base', source: 'source' })}</p>
                  <SemanticDiffView
                    projectId={projectId}
                    baseRef={`commit:${selectedMr.merge_base_public_id}`}
                    targetRef={`commit:${selectedMr.source_head_public_id}`}
                    onEntitySelect={setSelectedEntry}
                  />
                  {/* Diff 行内评论表单 */}
                  {selectedEntry && (
                    <div className="mt-3 rounded border border-indigo-200 bg-indigo-50 p-3 text-xs">
                      <p className="mb-1 font-semibold text-indigo-700">
                        {t('versionControl.mergeRequest.commentOn', { target: `${selectedEntry.entity_type} · ${selectedEntry.entity_name || selectedEntry.entity_uuid}` })}
                        {selectedEntry.field && <span className="text-slate-500"> · {selectedEntry.field}</span>}
                      </p>
                      <textarea
                        value={newComment}
                        onChange={(e) => setNewComment(e.target.value)}
                        rows={2}
                        className="w-full rounded border border-slate-200 px-2 py-1 text-xs"
                        placeholder={t('versionControl.mergeRequest.commentPlaceholder')}
                      />
                      <div className="mt-1 flex items-center gap-3">
                        <label className="flex items-center gap-1 cursor-pointer">
                          <input type="checkbox" checked={newCommentRequired} onChange={(e) => setNewCommentRequired(e.target.checked)} className="h-3 w-3" />
                          <span className="text-[10px] text-slate-600">{t('versionControl.mergeRequest.blocksMerge')}</span>
                        </label>
                        <button onClick={addComment} disabled={!newComment.trim()} className="rounded bg-indigo-600 px-3 py-1 text-[11px] font-semibold text-white hover:bg-indigo-700 disabled:bg-slate-300">
                          {t('versionControl.mergeRequest.postComment')}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* 评论列表 */}
              {selectedMr.comments && selectedMr.comments.length > 0 && (
                <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                  <p className="mb-2 text-xs font-bold text-slate-600">{t('versionControl.mergeRequest.commentsHeader', { count: selectedMr.comments.length })}</p>
                  {selectedMr.comments.map((c) => (
                    <div key={c.id} className="mb-2 flex items-start gap-2 rounded border border-slate-100 bg-white p-2 text-xs">
                      <MessageSquare className="mt-0.5 h-3.5 w-3.5 text-slate-400" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="font-medium">{c.author_email || c.author_user_id || '-'}</span>
                          {c.required && <span className="rounded bg-rose-100 px-1 text-[10px] font-semibold text-rose-700">{t('versionControl.mergeRequest.required')}</span>}
                          <span className={cn('rounded px-1 text-[10px]', c.status === 'active' ? 'bg-slate-100 text-slate-600' : c.status === 'resolved' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700')}>{t(`versionControl.mergeRequest.status.${c.status}`)}</span>
                        </div>
                        {(c.entity_uuid || c.field_path || c.relation_key) && (
                          <p className="mt-0.5 text-[10px] text-slate-400">
                            {c.entity_uuid && <span className="font-mono">{c.entity_uuid.slice(0, 8)}</span>}
                            {c.field_path && <span> · {c.field_path}</span>}
                            {c.relation_key && <span> · {c.relation_key}</span>}
                            {c.effective_source_head_id != null && <span className="ml-1">@#{c.effective_source_head_id}</span>}
                            {c.expired_by_source_head_id != null && <span className="ml-1 text-amber-600">➔#{c.expired_by_source_head_id}</span>}
                          </p>
                        )}
                        <p className="mt-0.5 text-slate-700">{c.comment}</p>
                        {c.status === 'active' && (
                          <button
                            onClick={() => { workspaceApi.resolveMrComment(projectId, selectedMr.public_id, c.id).then(() => selectMr(selectedMr)).catch(() => setActionError(t('versionControl.mergeRequest.errors.resolveFailed'))); }}
                            className="mt-1 inline-flex items-center gap-1 text-[10px] text-emerald-600 hover:text-emerald-800"
                          >
                            <Check className="h-3 w-3" /> {t('versionControl.mergeRequest.resolve')}
                          </button>
                        )}
                        {c.status === 'resolved' && (
                          <button
                            onClick={() => { workspaceApi.reopenMrComment(projectId, selectedMr.public_id, c.id).then(() => selectMr(selectedMr)).catch(() => setActionError(t('versionControl.mergeRequest.errors.reopenFailed'))); }}
                            className="mt-1 inline-flex items-center gap-1 text-[10px] text-amber-600 hover:text-amber-800"
                          >
                            <RotateCcw className="h-3 w-3" /> {t('versionControl.mergeRequest.reopen')}
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* 审批状态 */}
              {selectedMr.reviews.length > 0 && (
                <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                  <p className="mb-2 text-xs font-bold text-slate-600">{t('versionControl.mergeRequest.reviewsHeader')}</p>
                  {selectedMr.reviews.map((r) => (
                    <div key={r.id} className={cn('mb-1 flex items-start gap-2 text-xs', r.status === 'stale' && 'opacity-50')}>
                      {r.decision === 'approved' ? <Check className="mt-0.5 h-3.5 w-3.5 text-emerald-600" /> : <X className="mt-0.5 h-3.5 w-3.5 text-rose-600" />}
                      <span className="font-medium">{r.reviewer_email || r.reviewer_user_id}</span>
                      <span className="text-slate-500">{r.decision === 'approved' ? t('versionControl.mergeRequest.approve') : t('versionControl.mergeRequest.requestChanges')}</span>
                      {r.status === 'stale' && (
                        <span className="rounded bg-amber-100 px-1 text-amber-700" title={r.stale_reason ?? ''}>
                          {r.stale_reason
                            ? t('versionControl.mergeRequest.staleReason', { reason: r.stale_reason })
                            : t('versionControl.mergeRequest.stale')}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* 阻塞原因 */}
              {selectedMr.blocking_reasons && selectedMr.blocking_reasons.length > 0 && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
                  <p className="font-semibold">{t('versionControl.mergeRequest.whyCantMerge')}</p>
                  <ul className="mt-1 list-inside list-disc space-y-0.5">
                    {selectedMr.blocking_reasons.map((r, i) => <li key={i}>{t(`versionControl.mergeRequest.blocking.${r}`)}</li>)}
                  </ul>
                </div>
              )}

              {/* 审批面板 */}
              {selectedMr.can_approve && selectedMr.status !== 'merged' && selectedMr.status !== 'closed' && (
                <div className="space-y-2 rounded-lg border border-indigo-200 bg-indigo-50 p-3">
                  <p className="text-xs font-bold text-indigo-700">{t('versionControl.mergeRequest.submitReview')}</p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setReviewDecision('approved')}
                      className={cn('rounded px-2.5 py-1 text-xs font-semibold', reviewDecision === 'approved' ? 'bg-emerald-600 text-white' : 'bg-white text-emerald-700 border border-emerald-200')}
                    >{t('versionControl.mergeRequest.approve')}</button>
                    <button
                      onClick={() => setReviewDecision('changes_requested')}
                      className={cn('rounded px-2.5 py-1 text-xs font-semibold', reviewDecision === 'changes_requested' ? 'bg-amber-600 text-white' : 'bg-white text-amber-700 border border-amber-200')}
                    >{t('versionControl.mergeRequest.requestChanges')}</button>
                  </div>
                  <textarea value={reviewComment} onChange={(e) => setReviewComment(e.target.value)} rows={2} className="w-full rounded border border-slate-200 px-2 py-1 text-xs" placeholder={t('versionControl.mergeRequest.reviewOptionalComment')} />
                  <button onClick={submitReview} className="rounded bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700">{t('versionControl.mergeRequest.submitReview')}</button>
                </div>
              )}

              {/* 合并按钮：仅审批满足且 MR 可合并时显示 */}
              {selectedMr.can_merge && selectedMr.status !== 'merged' && selectedMr.status !== 'closed' && (
                <button
                  onClick={startMerge}
                  disabled={merging}
                  className="inline-flex items-center gap-1 rounded bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:bg-slate-300"
                >
                  <GitMerge className="h-3.5 w-3.5" />
                  {merging ? t('versionControl.mergeRequest.merging') : t('versionControl.mergeRequest.mergeButton')}
                </button>
              )}

              {/* 合并错误提示：token 由 t() 解析，head_changed 提供刷新/比较动作 */}
              {mergeError && (
                <div className="rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
                  {mergeError.startsWith('versionControl.') ? t(mergeError) : mergeError}
                  {mergeErrorInfo?.code === 'head_changed' && mergeErrorInfo.compareRef && (
                    <div className="mt-1.5 flex gap-2">
                      <button
                        type="button"
                        onClick={() => { setMergeError(''); selectMr(selectedMr); }}
                        className="rounded bg-slate-700 px-2 py-1 text-[10px] font-semibold text-white hover:bg-slate-800"
                      >
                        {t('versionControl.commitDialog.refresh')}
                      </button>
                      <button
                        type="button"
                        onClick={() => navigate(`/projects/${projectId}/repo?diff=1&base_ref=${encodeURIComponent(mergeErrorInfo.compareRef!)}`)}
                        className="rounded bg-indigo-600 px-2 py-1 text-[10px] font-semibold text-white hover:bg-indigo-700"
                      >
                        {t('versionControl.commitDialog.compare')}
                      </button>
                    </div>
                  )}
                  {mergeErrorInfo?.code === 'merge_blocked' && mergeErrorInfo.reasons && (
                    <ul className="mt-1 list-inside list-disc">
                      {mergeErrorInfo.reasons.map((r, i) => (
                        <li key={i}>{t(`versionControl.mergeRequest.blocking.${r}`)}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {/* 副操作（审批/评论/关闭）错误提示 */}
              {actionError && (
                <div className="rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
                  {actionError.startsWith('versionControl.') ? t(actionError) : actionError}
                </div>
              )}

              {/* 冲突解决视图 */}
              {showConflictView && selectedMr && (
                <ConflictResolutionView
                  projectId={projectId}
                  mrRef={selectedMr.public_id}
                  sourceBranchName={selectedMr.source_branch_name}
                  targetBranchName={selectedMr.target_branch_name}
                  onMerged={() => {
                    setShowConflictView(false);
                    loads();
                    selectMr(selectedMr);
                  }}
                  onCancel={() => setShowConflictView(false)}
                  onError={(msg) => setMergeError(msg)}
                />
              )}

              {/* 关闭按钮 */}
              {selectedMr.status !== 'merged' && selectedMr.status !== 'closed' && (
                <button
                  onClick={doClose}
                  className="rounded border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-50"
                >{t('versionControl.mergeRequest.close')}</button>
              )}
            </div>
          )}
        </div>
      </div>
      <CreateMergeRequestDialog
        projectId={projectId}
        open={showCreateMr}
        onClose={() => setShowCreateMr(false)}
        onCreated={(publicId) => {
          setShowCreateMr(false);
          loads();
          // 选中新创建的 MR
          workspaceApi.getMergeRequestDetail(projectId, publicId).then(setSelectedMr);
        }}
      />
    </div>
  );
}
