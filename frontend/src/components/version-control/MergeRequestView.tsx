import { useEffect, useMemo, useRef, useState } from 'react';
import { GitPullRequest, Check, X, MessageSquare, RotateCcw, Plus, GitMerge, ChevronDown, ChevronUp } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { workspaceApi } from '@/lib/api';
import {
  MergeRequestSummary,
  MergeRequestDetail,
  DiffEntry,
} from '@/core/versionControl';
import { SemanticDiffView } from './SemanticDiffView';
import { formatFieldLabel } from './DiffEntityDetail';
import { extractVcError, extractActionError } from '@/core/versionControlErrors';
import { CreateMergeRequestDialog } from './CreateMergeRequestDialog';
import { ConflictResolutionView } from './ConflictResolutionView';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { cn } from '@/lib/utils';

interface MergeRequestViewProps {
  projectId: string;
}

type MrStatusFilter = 'open' | 'merged' | 'closed' | 'all';

export function MergeRequestView({ projectId }: MergeRequestViewProps) {
  const { t } = useTranslation();
  const [statusFilter, setStatusFilter] = useState<MrStatusFilter>('open');
  const [mrs, setMrs] = useState<MergeRequestSummary[]>([]);
  const [mrTotal, setMrTotal] = useState(0);
  const [loadingMrs, setLoadingMrs] = useState(false);
  const [mrsError, setMrsError] = useState<string | null>(null);

  const [selectedMr, setSelectedMr] = useState<MergeRequestDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const currentDetailReqId = useRef(0);

  const [reviewComment, setReviewComment] = useState('');
  const [reviewDecision, setReviewDecision] = useState<'approved' | 'changes_requested'>('approved');
  const [showConflictView, setShowConflictView] = useState(false);
  const [mergeError, setMergeError] = useState('');
  const [mergeErrorInfo, setMergeErrorInfo] = useState<{ code?: string; reasons?: string[]; compareRef?: string } | null>(null);
  const [actionError, setActionError] = useState('');
  const [merging, setMerging] = useState(false);
  const navigate = useNavigate();
  const currentBranch = useWorkspaceStore((s) => s.currentBranch);
  const [showCreateMr, setShowCreateMr] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<DiffEntry | null>(null);
  const [newComment, setNewComment] = useState('');
  const [newCommentRequired, setNewCommentRequired] = useState(false);
  const [commentComposerOpen, setCommentComposerOpen] = useState(false);
  const [requestedMrRef, setRequestedMrRef] = useState<string | null>(null);
  const [loadingMoreMrs, setLoadingMoreMrs] = useState(false);

  const currentListReqId = useRef(0);

  const [activeDetailTab, setActiveDetailTab] = useState<'diff' | 'overview'>('diff');

  // 评审与讨论统一时间线：评审记录与评论按时间先后合并
  const activityItems = useMemo(() => {
    if (!selectedMr) return [];
    const items = [
      ...selectedMr.reviews.map((r) => ({ kind: 'review' as const, ts: r.created_at || '', review: r, comment: null })),
      ...selectedMr.comments.map((c) => ({ kind: 'comment' as const, ts: c.created_at || '', review: null, comment: c })),
    ];
    return items.sort((a, b) => a.ts.localeCompare(b.ts));
  }, [selectedMr]);

  const PAGE_SIZE = 50;

  const loads = (isAppend = false) => {
    if (isAppend) {
      if (loadingMoreMrs || loadingMrs) return;
      setLoadingMoreMrs(true);
    } else {
      setLoadingMrs(true);
      setLoadingMoreMrs(false);
      setMrsError(null);
    }
    const reqId = isAppend ? currentListReqId.current : ++currentListReqId.current;
    const currentOffset = isAppend ? mrs.length : 0;
    const query: { limit: number; offset?: number; status?: string } = { limit: PAGE_SIZE, offset: currentOffset };
    if (statusFilter !== 'all') {
      query.status = statusFilter;
    }
    workspaceApi.listMergeRequests(projectId, query)
      .then((res) => {
        if (currentListReqId.current !== reqId) return;
        if (isAppend) {
          setMrs((prev) => [...prev, ...res.items]);
        } else {
          setMrs(res.items);
        }
        setMrTotal(res.total);
        setMrsError(null);
      })
      .catch((e) => {
        if (currentListReqId.current === reqId) {
          setMrsError(e instanceof Error ? e.message : 'versionControl.mergeRequest.errors.listFailed');
        }
      })
      .finally(() => {
        if (currentListReqId.current === reqId) {
          if (isAppend) {
            setLoadingMoreMrs(false);
          } else {
            setLoadingMrs(false);
          }
        } else if (isAppend) {
          setLoadingMoreMrs(false);
        }
      });
  };

  useEffect(() => {
    setMrs([]);
    setSelectedMr(null);
    setMrsError(null);
    setLoadingMoreMrs(false);
    loads(false);
  }, [projectId, statusFilter]);

  const selectMr = (mr: MergeRequestSummary | MergeRequestDetail | string) => {
    const targetRef = typeof mr === 'string' ? mr : mr.public_id;
    const reqId = ++currentDetailReqId.current;
    setRequestedMrRef(targetRef);
    setSelectedMr(null);
    setLoadingDetail(true);
    setDetailError(null);
    // 切换 MR 时重置评论状态，避免把评论发到另一份 MR 的变更对象上
    setSelectedEntry(null);
    setNewComment('');
    setNewCommentRequired(false);
    setCommentComposerOpen(false);
    workspaceApi.getMergeRequestDetail(projectId, targetRef)
      .then((d) => {
        if (currentDetailReqId.current === reqId) {
          setSelectedMr(d);
        }
      })
      .catch((e) => {
        if (currentDetailReqId.current === reqId) {
          setDetailError(e instanceof Error ? e.message : 'versionControl.mergeRequest.errors.detailFailed');
        }
      })
      .finally(() => {
        if (currentDetailReqId.current === reqId) {
          setLoadingDetail(false);
        }
      });
  };

  const handleEntrySelect = (entry: DiffEntry) => {
    const sameEntry = selectedEntry
      && selectedEntry.entity_uuid === entry.entity_uuid
      && selectedEntry.path === entry.path
      && selectedEntry.change_type === entry.change_type;
    if (!sameEntry) {
      // 切换评论目标时清空草稿并收起，避免把评论发到错误对象上
      setNewComment('');
      setNewCommentRequired(false);
      setCommentComposerOpen(false);
    }
    setSelectedEntry(entry);
  };

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

  const handleMergeSuccess = async (targetMrRef: string) => {
    setShowConflictView(false);
    setMergeError('');
    loads();
    selectMr(targetMrRef);
    try {
      await useWorkspaceStore.getState().loadBranches();
      await useWorkspaceStore.getState().loadCommits({ all: true });
      await useWorkspaceStore.getState().refreshWorkspace();
    } catch (e) {
      console.warn('Post-merge store refresh error:', e);
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
        await handleMergeSuccess(selectedMr.public_id);
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
    <div className="flex flex-col gap-6 w-full">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <GitPullRequest className="h-5 w-5 text-indigo-600" />
          <h2 className="text-base font-black text-slate-900">{t('versionControl.mergeRequest.listTitle')}</h2>
          <span className="text-xs font-bold text-slate-400 bg-white px-2 py-0.5 rounded-lg border border-slate-200/80 shadow-2xs">
            {t('versionControl.mergeRequest.total', { count: mrTotal })}
          </span>
        </div>
        <button
          onClick={() => setShowCreateMr(true)}
          className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-bold text-white hover:bg-indigo-700 transition-colors shadow-sm cursor-pointer"
        >
          <Plus className="h-3.5 w-3.5" /> {t('versionControl.mergeRequest.newMr')}
        </button>
      </div>

      <div className="grid min-h-[580px] grid-cols-1 gap-6 md:grid-cols-[300px_minmax(0,1fr)]">
        {/* MR 列表 */}
        <div className="h-[720px] flex flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 bg-slate-50/60 p-3">
            <div className="flex items-center gap-1 rounded-xl bg-slate-100 p-1">
              {(['open', 'merged', 'closed', 'all'] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setStatusFilter(s)}
                  className={cn(
                    'flex-1 rounded-lg py-1 text-[11px] font-bold transition-all cursor-pointer',
                    statusFilter === s ? 'bg-white text-slate-900 shadow-2xs' : 'text-slate-500 hover:text-slate-900'
                  )}
                >
                  {t(`versionControl.mergeRequest.filter.${s}`, s)}
                </button>
              ))}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {loadingMrs && <p className="px-4 py-4 text-xs text-slate-400 text-center">{t('shell.loading')}</p>}
            {mrsError && (
              <div className="p-4 text-xs text-rose-600 text-center">
                <p>{mrsError}</p>
                <button type="button" onClick={() => loads(false)} className="mt-2 text-xs font-bold text-indigo-600 hover:underline cursor-pointer">
                  {t('shell.retry', '重试')}
                </button>
              </div>
            )}
            {!loadingMrs && !mrsError && mrs.length === 0 && (
              <p className="px-4 py-6 text-xs text-slate-400 text-center">{t('versionControl.mergeRequest.noMrs')}</p>
            )}
            <ul className="space-y-1">
              {mrs.map((mr) => (
                <li key={mr.public_id}>
                  <button
                    type="button"
                    onClick={() => selectMr(mr)}
                    className={cn(
                      'w-full border-b border-slate-50 p-3 text-left rounded-xl transition-colors cursor-pointer',
                      (selectedMr?.public_id === mr.public_id || requestedMrRef === mr.public_id) ? 'bg-indigo-50/80 shadow-2xs' : 'hover:bg-slate-50'
                    )}
                  >
                    <p className="text-xs font-bold text-slate-900 truncate">{mr.title}</p>
                    <p className="text-[11px] text-slate-500 mt-0.5">{mr.source_branch_name} → {mr.target_branch_name}</p>
                    <div className="mt-2 flex items-center gap-1.5">
                      <span className={cn('rounded-md px-1.5 py-0.5 text-[10px] font-bold', statusClass(mr.status))}>
                        {t(`versionControl.mergeRequest.status.${mr.status}`)}
                      </span>
                      {mr.active_review_count > 0 && <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">✓{mr.active_review_count}</span>}
                      {mr.total_comments > 0 && <span className="text-[10px] font-bold text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">💬{mr.total_comments}</span>}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
            {mrs.length < mrTotal && (
              <div className="p-3 text-center border-t border-slate-100">
                <button
                  type="button"
                  disabled={loadingMoreMrs}
                  onClick={() => loads(true)}
                  className="inline-flex items-center gap-1 rounded-xl bg-indigo-50 px-3 py-1.5 text-xs font-bold text-indigo-600 hover:bg-indigo-100 disabled:opacity-50 cursor-pointer"
                >
                  {loadingMoreMrs ? t('shell.loading') : t('versionControl.mergeRequest.loadMore', { remaining: mrTotal - mrs.length })}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* MR 详情 */}
        <div className="h-[720px] flex flex-col rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          {!selectedMr && !loadingDetail && !detailError ? (
            <div className="flex h-full flex-col items-center justify-center text-center p-6 text-slate-400">
              <GitPullRequest className="h-10 w-10 text-slate-300 mb-2 stroke-[1.5]" />
              <p className="text-sm font-semibold text-slate-600">{t('versionControl.mergeRequest.selectPlaceholder')}</p>
            </div>
          ) : loadingDetail ? (
            <div className="flex h-full flex-col items-center justify-center text-center p-6 text-slate-400">
              <p className="text-xs font-medium">{t('shell.loading')}</p>
            </div>
          ) : detailError ? (
            <div className="flex h-full flex-col items-center justify-center text-center p-6 text-rose-600">
              <p className="text-xs font-medium">{detailError}</p>
              <button
                type="button"
                onClick={() => requestedMrRef && selectMr(requestedMrRef)}
                className="mt-2 rounded-xl bg-indigo-50 px-3 py-1.5 text-xs font-bold text-indigo-600 hover:bg-indigo-100 cursor-pointer"
              >
                {t('shell.retry', '重试加载')}
              </button>
            </div>
          ) : selectedMr ? (
            <div className="flex h-full flex-col min-h-0">
              {/* MR Header */}
              <div className="border-b border-slate-100 bg-slate-50/50 px-6 py-4 shrink-0">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h2 className="text-base font-black text-slate-900 truncate">{selectedMr.title}</h2>
                      <span className={cn('rounded-md px-2 py-0.5 text-[11px] font-bold shrink-0', statusClass(selectedMr.status))}>
                        {t(`versionControl.mergeRequest.status.${selectedMr.status}`)}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                      <span className="font-semibold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded">{selectedMr.source_branch_name}</span>
                      <span>→</span>
                      <span className="font-semibold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded">{selectedMr.target_branch_name}</span>
                      {selectedMr.source_head_short && <span className="font-mono text-slate-400">@{selectedMr.source_head_short}</span>}
                      {selectedMr.author_email && <span className="text-slate-400">· {t('versionControl.mergeRequest.createdBy', { author: selectedMr.author_email })}</span>}
                    </div>
                  </div>

                  {/* Actions Header Toolbar */}
                  <div className="flex items-center gap-2 shrink-0">
                    {selectedMr.can_merge && selectedMr.status !== 'merged' && selectedMr.status !== 'closed' && (
                      <button
                        onClick={startMerge}
                        disabled={merging}
                        className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-emerald-700 disabled:bg-slate-300 shadow-sm cursor-pointer"
                      >
                        <GitMerge className="h-3.5 w-3.5" />
                        {merging ? t('versionControl.mergeRequest.merging') : t('versionControl.mergeRequest.mergeButton')}
                      </button>
                    )}
                    {selectedMr.status !== 'merged' && selectedMr.status !== 'closed' && (
                      <button
                        onClick={doClose}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 cursor-pointer shadow-2xs"
                      >
                        {t('versionControl.mergeRequest.close')}
                      </button>
                    )}
                  </div>
                </div>

                {/* Tabs Switcher */}
                <div className="mt-4 flex items-center gap-2 border-t border-slate-200/60 pt-3">
                  <button
                    type="button"
                    onClick={() => setActiveDetailTab('diff')}
                    className={cn(
                      'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer',
                      activeDetailTab === 'diff'
                        ? 'bg-indigo-600 text-white shadow-sm'
                        : 'text-slate-600 hover:bg-slate-200/60'
                    )}
                  >
                    <span>{t('versionControl.diff.title', '变更对比')}</span>
                    {selectedMr.diff_summary && (
                      <span className={cn(
                        'text-[10px] px-1.5 py-0.2 rounded-md font-mono',
                        activeDetailTab === 'diff' ? 'bg-indigo-700/80 text-white' : 'bg-slate-200 text-slate-700'
                      )}>
                        +{selectedMr.diff_summary.total_added} ~{selectedMr.diff_summary.total_modified} -{selectedMr.diff_summary.total_removed}
                      </span>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveDetailTab('overview')}
                    className={cn(
                      'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer',
                      activeDetailTab === 'overview'
                        ? 'bg-indigo-600 text-white shadow-sm'
                        : 'text-slate-600 hover:bg-slate-200/60'
                    )}
                  >
                    <span>{t('versionControl.mergeRequest.overviewTab', '概览与评审')}</span>
                    {selectedMr.comments && selectedMr.comments.length > 0 && (
                      <span className={cn(
                        'text-[10px] px-1.5 py-0.2 rounded-md font-mono',
                        activeDetailTab === 'overview' ? 'bg-indigo-700/80 text-white' : 'bg-slate-200 text-slate-700'
                      )}>
                        💬 {selectedMr.comments.length}
                      </span>
                    )}
                    {selectedMr.reviews && selectedMr.reviews.length > 0 && (
                      <span className={cn(
                        'text-[10px] px-1.5 py-0.2 rounded-md font-mono',
                        activeDetailTab === 'overview' ? 'bg-indigo-700/80 text-white' : 'bg-slate-200 text-slate-700'
                      )}>
                        ✓ {selectedMr.reviews.filter(r => r.decision === 'approved').length}
                      </span>
                    )}
                  </button>
                </div>
              </div>

              {/* Tab Content */}
              {activeDetailTab === 'diff' ? (
                <div className="flex-1 min-h-0 flex flex-col p-4 overflow-hidden bg-slate-50/30">
                  {selectedMr.merge_base_public_id && selectedMr.source_head_public_id ? (
                    <div className="relative flex-1 min-h-0 flex flex-col">
                      <div className="min-h-0 flex-1">
                        <SemanticDiffView
                          projectId={projectId}
                          baseRef={`commit:${selectedMr.merge_base_public_id}`}
                          targetRef={`commit:${selectedMr.source_head_public_id}`}
                          onEntitySelect={handleEntrySelect}
                        />
                      </div>
                      {/* 行内评论收起态：右下角固定入口胶囊，不挤占 diff 布局 */}
                      {selectedEntry && !commentComposerOpen && (
                        <button
                          type="button"
                          onClick={() => setCommentComposerOpen(true)}
                          className="absolute bottom-3 right-3 z-10 flex max-w-[calc(100%-1.5rem)] items-center gap-2 rounded-full border border-indigo-200 bg-white/95 py-1.5 pl-3 pr-1.5 text-[11px] font-bold text-indigo-900 shadow-lg shadow-indigo-900/10 backdrop-blur-sm transition-all hover:border-indigo-300 hover:shadow-xl cursor-pointer"
                        >
                          <MessageSquare className="h-3.5 w-3.5 shrink-0 text-indigo-500" />
                          <span className="max-w-[14rem] truncate">
                            {`${selectedEntry.entity_type} · ${selectedEntry.entity_name || selectedEntry.entity_uuid}`}
                          </span>
                          <span className="flex items-center gap-0.5 rounded-full bg-indigo-50 px-2 py-0.5 text-indigo-600">
                            {t('versionControl.mergeRequest.writeComment')}
                            <ChevronUp className="h-3 w-3" />
                          </span>
                        </button>
                      )}
                      {/* 行内评论展开态：锚定右下角的浮动卡片，覆盖式呈现避免遮挡详情布局 */}
                      {selectedEntry && commentComposerOpen && (
                        <div className="absolute bottom-3 right-3 z-10 w-[22rem] max-w-[calc(100%-1.5rem)] rounded-2xl border border-indigo-200 bg-white/95 p-3 text-xs shadow-xl shadow-indigo-900/10 backdrop-blur-sm">
                          <div className="mb-1.5 flex items-center justify-between gap-2">
                            <p className="flex min-w-0 items-center gap-1.5 font-bold text-indigo-900">
                              <MessageSquare className="h-3.5 w-3.5 shrink-0 text-indigo-500" />
                              <span className="truncate">
                                {t('versionControl.mergeRequest.commentOn', { target: `${selectedEntry.entity_type} · ${selectedEntry.entity_name || selectedEntry.entity_uuid}` })}
                              </span>
                              {selectedEntry.field && <span className="shrink-0 font-normal text-indigo-500"> · {selectedEntry.field}</span>}
                            </p>
                            <button
                              type="button"
                              onClick={() => setCommentComposerOpen(false)}
                              title={t('versionControl.mergeRequest.collapseComposer')}
                              aria-label={t('versionControl.mergeRequest.collapseComposer')}
                              className="shrink-0 rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 cursor-pointer"
                            >
                              <ChevronDown className="h-3.5 w-3.5" />
                            </button>
                          </div>
                          <textarea
                            value={newComment}
                            onChange={(e) => setNewComment(e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Escape') setCommentComposerOpen(false); }}
                            rows={3}
                            autoFocus
                            className="w-full resize-none rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs focus:outline-indigo-500"
                            placeholder={t('versionControl.mergeRequest.commentPlaceholder')}
                          />
                          <div className="mt-2 flex items-center justify-between">
                            <label className="flex items-center gap-1.5 cursor-pointer">
                              <input type="checkbox" checked={newCommentRequired} onChange={(e) => setNewCommentRequired(e.target.checked)} className="h-3.5 w-3.5 rounded text-indigo-600" />
                              <span className="text-[11px] font-medium text-slate-700">{t('versionControl.mergeRequest.blocksMerge')}</span>
                            </label>
                            <button
                              onClick={addComment}
                              disabled={!newComment.trim()}
                              className="rounded-lg bg-indigo-600 px-3.5 py-1 text-xs font-bold text-white hover:bg-indigo-700 disabled:bg-slate-300 cursor-pointer"
                            >
                              {t('versionControl.mergeRequest.postComment')}
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="flex h-full items-center justify-center text-xs text-slate-400">
                      暂无可比对的基线提交
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                  {/* 合并描述：纯排版区块，不做卡片容器 */}
                  {selectedMr.description && (
                    <div>
                      <p className="text-xs font-bold text-slate-800 uppercase tracking-widest">{t('versionControl.mergeRequest.descriptionTitle')}</p>
                      <p className="mt-2 text-xs leading-relaxed text-slate-600 whitespace-pre-wrap">{selectedMr.description}</p>
                    </div>
                  )}

                  {/* 错误提示 */}
                  {mergeError && (
                    <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
                      {mergeError.startsWith('versionControl.') ? t(mergeError) : mergeError}
                      {mergeErrorInfo?.code === 'head_changed' && mergeErrorInfo.compareRef && (
                        <div className="mt-2 flex gap-2">
                          <button
                            type="button"
                            onClick={() => { setMergeError(''); selectMr(selectedMr); }}
                            className="rounded-lg bg-slate-700 px-2.5 py-1 text-[11px] font-bold text-white hover:bg-slate-800"
                          >
                            {t('versionControl.commitDialog.refresh')}
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              const branchParam = currentBranch?.public_id || currentBranch?.name;
                              const branchQuery = branchParam ? `&branch=${encodeURIComponent(branchParam)}` : '';
                              navigate(`/projects/${projectId}/repo?diff=1&base_ref=${encodeURIComponent(mergeErrorInfo.compareRef!)}${branchQuery}`);
                            }}
                            className="rounded-lg bg-indigo-600 px-2.5 py-1 text-[11px] font-bold text-white hover:bg-indigo-700"
                          >
                            {t('versionControl.commitDialog.compare')}
                          </button>
                        </div>
                      )}
                      {mergeErrorInfo?.code === 'merge_blocked' && mergeErrorInfo.reasons && (
                        <ul className="mt-1.5 list-inside list-disc space-y-0.5">
                          {mergeErrorInfo.reasons.map((r, i) => (
                            <li key={i}>{t(`versionControl.mergeRequest.blocking.${r}`)}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}

                  {actionError && (
                    <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
                      {actionError.startsWith('versionControl.') ? t(actionError) : actionError}
                    </div>
                  )}

                  {/* 评审与讨论：提交评审面板 + 评审记录 + 评论的统一时间线 */}
                  <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                    <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/60 px-4 py-3">
                      <p className="text-xs font-bold text-slate-800">{t('versionControl.mergeRequest.activityTitle')}</p>
                      <span className="text-[11px] font-medium text-slate-400">{activityItems.length}</span>
                    </div>

                    {/* 提交评审（仅开放状态且有权限时） */}
                    {selectedMr.can_approve && selectedMr.status !== 'merged' && selectedMr.status !== 'closed' && (
                      <div className="space-y-2.5 border-b border-slate-100 bg-indigo-50/40 px-4 py-3.5">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-xs font-bold text-indigo-900">{t('versionControl.mergeRequest.submitReview')}</p>
                          <div className="flex gap-1.5">
                            <button
                              type="button"
                              onClick={() => setReviewDecision('approved')}
                              className={cn('rounded-xl px-3 py-1.5 text-xs font-bold transition-colors cursor-pointer', reviewDecision === 'approved' ? 'bg-emerald-600 text-white shadow-2xs' : 'bg-white text-emerald-700 border border-emerald-200 hover:bg-emerald-50')}
                            >
                              ✓ {t('versionControl.mergeRequest.approve')}
                            </button>
                            <button
                              type="button"
                              onClick={() => setReviewDecision('changes_requested')}
                              className={cn('rounded-xl px-3 py-1.5 text-xs font-bold transition-colors cursor-pointer', reviewDecision === 'changes_requested' ? 'bg-amber-600 text-white shadow-2xs' : 'bg-white text-amber-700 border border-amber-200 hover:bg-amber-50')}
                            >
                              ✕ {t('versionControl.mergeRequest.requestChanges')}
                            </button>
                          </div>
                        </div>
                        <textarea
                          value={reviewComment}
                          onChange={(e) => setReviewComment(e.target.value)}
                          rows={2}
                          className="w-full rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs focus:outline-indigo-500"
                          placeholder={t('versionControl.mergeRequest.reviewOptionalComment')}
                        />
                        <div className="flex justify-end">
                          <button
                            type="button"
                            onClick={submitReview}
                            className="rounded-xl bg-indigo-600 px-4 py-1.5 text-xs font-bold text-white hover:bg-indigo-700 shadow-2xs cursor-pointer"
                          >
                            {t('versionControl.mergeRequest.submitReview')}
                          </button>
                        </div>
                      </div>
                    )}

                    {activityItems.length === 0 ? (
                      <p className="px-4 py-8 text-center text-xs text-slate-400">{t('versionControl.mergeRequest.activityEmpty')}</p>
                    ) : (
                      <ul className="divide-y divide-slate-50">
                        {activityItems.map((item) => {
                          if (item.kind === 'review' && item.review) {
                            const r = item.review;
                            return (
                              <li key={`review-${r.id}`} className={cn('flex items-start gap-3 px-4 py-3.5', r.status === 'stale' && 'opacity-60')}>
                                <div className={cn('flex h-7 w-7 shrink-0 items-center justify-center rounded-full border', r.decision === 'approved' ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50')}>
                                  {r.decision === 'approved' ? (
                                    <Check className="h-3.5 w-3.5 text-emerald-600" />
                                  ) : (
                                    <X className="h-3.5 w-3.5 text-amber-600" />
                                  )}
                                </div>
                                <div className="min-w-0 flex-1">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="text-xs font-bold text-slate-800">{r.reviewer_email || r.reviewer_user_id}</span>
                                    <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-bold', r.decision === 'approved' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700')}>
                                      {r.decision === 'approved' ? t('versionControl.mergeRequest.approve') : t('versionControl.mergeRequest.requestChanges')}
                                    </span>
                                    {r.status === 'stale' && (
                                      <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">
                                        {r.stale_reason ? t('versionControl.mergeRequest.staleReason', { reason: r.stale_reason }) : t('versionControl.mergeRequest.stale')}
                                      </span>
                                    )}
                                    {item.ts && <span className="ml-auto text-[10px] text-slate-400">{new Date(item.ts).toLocaleString()}</span>}
                                  </div>
                                  {r.comment && <p className="mt-1.5 whitespace-pre-wrap text-xs leading-relaxed text-slate-600">{r.comment}</p>}
                                </div>
                              </li>
                            );
                          }
                          const c = item.comment!;
                          return (
                            <li key={`comment-${c.id}`} className="flex items-start gap-3 px-4 py-3.5">
                              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-slate-50">
                                <MessageSquare className="h-3.5 w-3.5 text-slate-400" />
                              </div>
                              <div className="min-w-0 flex-1">
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className="text-xs font-bold text-slate-800">{c.author_email || c.author_user_id || '-'}</span>
                                  {c.required && <span className="rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-bold text-rose-700">{t('versionControl.mergeRequest.required')}</span>}
                                  <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-semibold', c.status === 'active' ? 'bg-slate-100 text-slate-600' : c.status === 'resolved' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700')}>{t(`versionControl.mergeRequest.commentStatus.${c.status}`)}</span>
                                  {(c.entity_uuid || c.field_path) && (
                                    <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-600">
                                      {t('versionControl.mergeRequest.inlineComment')}
                                      {c.field_path ? ` · ${formatFieldLabel(c.field_path, t)}` : ''}
                                    </span>
                                  )}
                                  {item.ts && <span className="ml-auto text-[10px] text-slate-400">{new Date(item.ts).toLocaleString()}</span>}
                                </div>
                                <p className="mt-1.5 whitespace-pre-wrap text-xs leading-relaxed text-slate-700">{c.comment}</p>
                                <div className="mt-2">
                                  {c.status === 'active' && (
                                    <button
                                      onClick={() => { workspaceApi.resolveMrComment(projectId, selectedMr.public_id, c.id).then(() => selectMr(selectedMr)).catch(() => setActionError(t('versionControl.mergeRequest.errors.resolveFailed'))); }}
                                      className="inline-flex cursor-pointer items-center gap-1 text-[11px] font-bold text-emerald-600 hover:text-emerald-800"
                                    >
                                      <Check className="h-3.5 w-3.5" /> {t('versionControl.mergeRequest.resolve')}
                                    </button>
                                  )}
                                  {c.status === 'resolved' && (
                                    <button
                                      onClick={() => { workspaceApi.reopenMrComment(projectId, selectedMr.public_id, c.id).then(() => selectMr(selectedMr)).catch(() => setActionError(t('versionControl.mergeRequest.errors.reopenFailed'))); }}
                                      className="inline-flex cursor-pointer items-center gap-1 text-[11px] font-bold text-amber-600 hover:text-amber-800"
                                    >
                                      <RotateCcw className="h-3.5 w-3.5" /> {t('versionControl.mergeRequest.reopen')}
                                    </button>
                                  )}
                                </div>
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : null}
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
      {/* 冲突解决视图 */}
      {showConflictView && selectedMr && (
        <ConflictResolutionView
          projectId={projectId}
          mrRef={selectedMr.public_id}
          sourceBranchName={selectedMr.source_branch_name}
          targetBranchName={selectedMr.target_branch_name}
          onMerged={async () => {
            await handleMergeSuccess(selectedMr.public_id);
          }}
          onCancel={() => setShowConflictView(false)}
          onError={(msg) => setMergeError(msg)}
        />
      )}
    </div>
  );
}
