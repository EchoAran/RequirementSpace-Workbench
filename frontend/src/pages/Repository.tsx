import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { GitBranch, GitCommitHorizontal, GitFork, History, Plus, GitPullRequest } from 'lucide-react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { CommitSummary, DiffEntry } from '@/core/versionControl';
import { SemanticDiffView } from '@/components/version-control/SemanticDiffView';
import { CreateBranchDialog } from '@/components/version-control/CreateBranchDialog';
import { MergeRequestView } from '@/components/version-control/MergeRequestView';
import { VersionControlGuidance } from '@/components/version-control/VersionControlGuidance';
import { findIrNodeByUuid, jumpTargetForEntity } from '@/core/objectNavigation';
import { buildProjectRoute } from '@/core/selectors';
import { CommitGraph } from '@/components/version-control/CommitGraph';
import { CompareSelector } from '@/components/version-control/CompareSelector';
import { CommitDetailDialog } from '@/components/version-control/CommitDetailDialog';
import { cn } from '@/lib/utils';

/**
 * 仓库总览页：左栏分支列表、主栏提交时间线、右栏提交详情与动作。
 */
export function Repository() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const ir = useWorkspaceStore((s) => s.ir);
  const branches = useWorkspaceStore((s) => s.branches);
  const currentBranch = useWorkspaceStore((s) => s.currentBranch);
  const commits = useWorkspaceStore((s) => s.commits);
  const commitLoading = useWorkspaceStore((s) => s.commitLoading);
  const loadBranches = useWorkspaceStore((s) => s.loadBranches);
  const loadCommits = useWorkspaceStore((s) => s.loadCommits);
  const [selectedCommit, setSelectedCommit] = useState<CommitSummary | null>(null);
  const [showCreateBranch, setShowCreateBranch] = useState(false);
  const [showDiff, setShowDiff] = useState(false);
  const [showCommitDetail, setShowCommitDetail] = useState(false);
  const params = new URLSearchParams(location.search);
  const showDiffParam = params.get('diff') === '1';
  const requestBranchSwitch = useWorkspaceStore((s) => s.requestBranchSwitch);
  const setSelectedObject = useWorkspaceStore((s) => s.setSelectedObject);

  const projectId = ir?.projectId;

  useEffect(() => {
    void loadBranches();
    void loadCommits({ all: true });
  }, [loadBranches, loadCommits]);

  // URL 深链：?diff=1 打开当前分支工作区 vs head 的 Diff。
  useEffect(() => {
    setShowDiff(showDiffParam);
  }, [showDiffParam]);

  // 顶部"创建分支"深链：?new_branch=1 自动打开创建弹窗。
  // 依赖 location.search：已在仓库页时再次点击顶部"创建分支"（仅改 search）也会触发。
  useEffect(() => {
    if (params.get('new_branch') === '1') {
      setShowCreateBranch(true);
      const next = new URLSearchParams(location.search);
      next.delete('new_branch');
      navigate(`${location.pathname}?${next.toString()}`, { replace: true });
    }
  }, [location.search, navigate, location.pathname]);

  // 分支切换统一走守卫：存在未保存编辑时由全局弹窗确认，否则直接导航。
  const switchToBranch = useCallback(
    (publicId: string) => {
      if (!requestBranchSwitch(publicId)) return;
      const next = new URLSearchParams(location.search);
      next.set('branch', publicId);
      navigate(`${location.pathname}?${next.toString()}`);
    },
    [navigate, location.search, requestBranchSwitch]
  );

  const openDiff = (baseRef?: string, targetRef?: string) => {
    const next = new URLSearchParams(location.search);
    if (baseRef) next.set('base_ref', baseRef);
    else next.delete('base_ref');
    if (targetRef) next.set('target_ref', targetRef);
    else next.delete('target_ref');
    next.set('diff', '1');
    navigate(`${location.pathname}?${next.toString()}`);
  };

  const diffEntityType = params.get('entity_type') || undefined;
  const diffChangeType = params.get('change_type') || undefined;

  // Diff 筛选：通过 URL 保存，便于分享评审链接。
  const setDiffFilter = (entityType?: string, changeType?: string) => {
    const next = new URLSearchParams(location.search);
    next.set('diff', '1');
    if (entityType) next.set('entity_type', entityType);
    else next.delete('entity_type');
    if (changeType) next.set('change_type', changeType);
    else next.delete('change_type');
    navigate(`${location.pathname}?${next.toString()}`);
  };

  const jumpFromDiff = (entry: DiffEntry) => {
    if (!ir?.projectId) return;
    const page = jumpTargetForEntity(entry.entity_type);
    if (!page) return;
    const obj = findIrNodeByUuid(ir, entry.entity_type, entry.entity_uuid);
    if (obj) setSelectedObject(obj);
    navigate(buildProjectRoute(ir.projectId, page));
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  if (!projectId) return null;

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 p-5">
      <div className="flex items-center gap-2">
        <GitBranch className="h-5 w-5 text-indigo-600" />
        <h1 className="text-lg font-bold text-slate-800">{t('versionControl.repository.title')}</h1>
      </div>

      {/* 标签栏：Commits / Merge Requests */}
      {!showDiff && (
        <div role="tablist" aria-label={t('versionControl.repository.title')} className="flex items-center gap-1">
          {(['commits', 'mr'] as const).map((tab) => {
            const active = params.get('tab') === tab || (!params.get('tab') && tab === 'commits');
            const Icon = tab === 'mr' ? GitPullRequest : History;
            return (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => {
                  const next = new URLSearchParams(location.search);
                  if (tab === 'commits') next.delete('tab');
                  else next.set('tab', tab);
                  navigate(`${location.pathname}?${next.toString()}`);
                }}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium focus-visible:ring-2 focus-visible:ring-indigo-400',
                  active ? 'bg-indigo-100 text-indigo-700' : 'text-slate-600 hover:bg-slate-100'
                )}
              >
                <Icon className="h-4 w-4" />
                {tab === 'mr' ? t('versionControl.repository.mergeRequests') : t('versionControl.repository.commitTimeline')}
              </button>
            );
          })}
        </div>
      )}

      {/* 版本控制引导横幅（基线/main 保护/MR 审批/不支持功能） */}
      {!showDiff && <VersionControlGuidance />}

      {showDiff ? (
        <div className="flex min-h-0 flex-1 flex-col gap-2">
          <CompareSelector
            projectId={projectId}
            baseRef={params.get('base_ref') || undefined}
            targetRef={params.get('target_ref') || undefined}
            branchRef={currentBranch?.public_id || 'main'}
            onChange={(b, tg) => openDiff(b, tg)}
          />
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-slate-600">{t('versionControl.diff.title')}</p>
            {/* 变更种类筛选：通过 URL 保存，可分享评审链接 */}
            {([
              { key: undefined, label: t('versionControl.diff.filterAll') },
              { key: 'entity_added', label: t('versionControl.diff.filterAdded') },
              { key: 'entity_removed', label: t('versionControl.diff.filterRemoved') },
              { key: 'entity_updated', label: t('versionControl.diff.filterModified') },
              { key: 'relation_added', label: t('versionControl.diff.filterRelation') },
            ] as { key?: string; label: string }[]).map((f) => (
              <button
                key={f.key || 'all'}
                type="button"
                aria-pressed={diffChangeType === f.key}
                onClick={() => setDiffFilter(diffEntityType, f.key)}
                className={cn(
                  'rounded-lg border px-2.5 py-1 text-xs font-medium focus-visible:ring-2 focus-visible:ring-indigo-400',
                  diffChangeType === f.key
                    ? 'border-indigo-300 bg-indigo-50 text-indigo-700'
                    : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
          <SemanticDiffView
            projectId={projectId}
            baseRef={params.get('base_ref') || undefined}
            targetRef={params.get('target_ref') || undefined}
            branch={params.get('branch') || undefined}
            entityType={diffEntityType}
            changeType={diffChangeType}
            onJump={jumpFromDiff}
          />
        </div>
      ) : params.get('tab') === 'mr' ? (
        <MergeRequestView projectId={projectId} />
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 md:grid-cols-[minmax(0,220px)_minmax(0,1fr)_minmax(0,320px)]">
          {/* 左栏：分支列表 */}
          <aside className="min-h-0 overflow-y-auto rounded-xl border border-slate-200 bg-white">
            <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2">
              <p className="text-xs font-bold text-slate-700">{t('versionControl.repository.branchList')}</p>
              <button
                type="button"
                onClick={() => setShowCreateBranch(true)}
                aria-label={t('versionControl.repository.createBranch')}
                className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-xs text-indigo-600 hover:bg-indigo-50"
                title={t('versionControl.repository.createBranch')}
              >
                <Plus className="h-3.5 w-3.5" />
              </button>
            </div>
            <ul>
              {(branches || []).map((branch) => {
                const active = branch.public_id === currentBranch?.public_id;
                return (
                  <li key={branch.public_id}>
                    <button
                      type="button"
                      onClick={() => switchToBranch(branch.public_id)}
                      className={cn(
                        'flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-indigo-50',
                        active && 'bg-indigo-50 text-indigo-700'
                      )}
                    >
                      <GitBranch className="h-3.5 w-3.5 text-slate-400" />
                      <span className="min-w-0 flex-1 truncate font-medium">{branch.name}</span>
                      {branch.is_protected && <span className="rounded bg-amber-100 px-1 text-[10px] font-semibold text-amber-700">main</span>}
                    </button>
                  </li>
                );
              })}
              {(branches || []).length === 0 && (
                <li className="px-3 py-3 text-xs text-slate-400">{t('versionControl.repository.noBranches')}</li>
              )}
            </ul>
          </aside>

          {/* 主栏：提交时间线 */}
          <main className="min-h-0 overflow-y-auto rounded-xl border border-slate-200 bg-white">
            <div className="flex items-center gap-2 border-b border-slate-100 px-3 py-2">
              <History className="h-4 w-4 text-slate-400" />
              <p className="text-xs font-bold text-slate-700">{t('versionControl.repository.commitTimeline')}</p>
            </div>
            {commitLoading && !commits && <p className="px-4 py-4 text-sm text-slate-400">{t('shell.loading')}</p>}
            {!commitLoading && (!commits || commits.commits.length === 0) && (
              <p className="px-4 py-4 text-sm text-slate-400">{t('versionControl.repository.noCommits')}</p>
            )}
            {/* 只有一个基线提交时的引导：提示从创建分支开始并行探索（设计文档 3.3 空状态）。 */}
            {!commitLoading && commits?.commits.length === 1 && (
              <div className="mx-4 mt-3 rounded-lg border border-indigo-100 bg-indigo-50/50 p-3 text-xs text-slate-600">
                {t('versionControl.repository.noSecondCommit')}
              </div>
            )}
            <div className="px-4 py-4">
              <CommitGraph
                commits={commits?.commits || []}
                selectedPublicId={selectedCommit?.public_id}
                onSelect={setSelectedCommit}
              />
              {commits && commits.commits.length < commits.total && !commitLoading && (
                <button
                  type="button"
                  onClick={() => loadCommits({ all: true, append: true })}
                  className="mt-3 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
                >
                  {t('versionControl.repository.loadMore')}
                </button>
              )}
            </div>
          </main>

          {/* 右栏：提交详情与动作 */}
          <aside className="min-h-0 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4">
            {!selectedCommit ? (
              <p className="text-sm text-slate-400">{t('versionControl.diff.selectNode')}</p>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <GitCommitHorizontal className="h-4 w-4 text-indigo-600" />
                  <span className="font-mono text-xs text-slate-500">{selectedCommit.short_id}</span>
                </div>
                <h3 className="text-sm font-bold text-slate-800">{selectedCommit.message}</h3>
                <p className="text-xs text-slate-500">
                  {t('versionControl.repository.author')}: {selectedCommit.author_email || selectedCommit.author_user_id || '-'}
                </p>
                <p className="text-xs text-slate-500">{formatDate(selectedCommit.created_at)}</p>

                {selectedCommit.parent_public_ids.length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-bold text-slate-600">{t('versionControl.repository.parent')}</p>
                    <div className="flex flex-wrap gap-1">
                      {selectedCommit.parent_public_ids.map((pid) => (
                        <span key={pid} className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
                          {pid.slice(0, 8)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {selectedCommit.summary && (
                  <div>
                    <p className="mb-1 text-xs font-bold text-slate-600">{t('versionControl.repository.summary')}</p>
                    <p className="text-xs text-slate-500">
                      {t('versionControl.repository.changeSummary', {
                        added: selectedCommit.summary.features ?? 0,
                        removed: 0,
                        modified: selectedCommit.summary.actors ?? 0,
                      })}
                    </p>
                  </div>
                )}

                <div className="space-y-2">
                  <button
                    type="button"
                    onClick={() => openDiff(`commit:${selectedCommit.public_id}`)}
                    className="w-full rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
                  >
                    {t('versionControl.repository.compareWithWorkspace')}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowCreateBranch(true)}
                    className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
                  >
                    <GitFork className="h-4 w-4" />
                    {t('versionControl.repository.createBranchFromCommit')}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowCommitDetail(true)}
                    className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
                  >
                    {t('versionControl.repository.viewFullModel')}
                  </button>
                </div>
              </div>
            )}
          </aside>
        </div>
      )}

      <CreateBranchDialog
        open={showCreateBranch}
        onClose={() => setShowCreateBranch(false)}
        sourceCommitPublicId={selectedCommit?.public_id ?? null}
        onCreated={(publicId) => switchToBranch(publicId)}
      />
      <CommitDetailDialog
        projectId={projectId}
        commitRef={selectedCommit?.public_id ?? null}
        open={showCommitDetail}
        onClose={() => setShowCommitDetail(false)}
      />
    </div>
  );
}
