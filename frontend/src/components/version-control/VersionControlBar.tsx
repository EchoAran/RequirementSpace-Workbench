import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { GitCommitHorizontal } from 'lucide-react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { BranchSelector } from './BranchSelector';
import { CommitDialog } from './CommitDialog';
import { cn } from '@/lib/utils';

/**
 * 顶部栏版本控制区：分支选择器、未提交摘要与提交按钮。
 * main 只展示分支切换，不展示直接提交入口。
 */
export function VersionControlBar() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const currentBranch = useWorkspaceStore((s) => s.currentBranch);
  const [showCommit, setShowCommit] = useState(false);

  const isProtected = currentBranch?.is_protected || currentBranch?.name === 'main';
  const canWrite = Boolean(currentBranch?.permissions?.can_write) && !isProtected;
  const dirty = currentBranch?.workspace_dirty;
  const hasChanges = Boolean(dirty?.is_dirty && (dirty?.modified_entities_count ?? 0) > 0);

  const projectId = useWorkspaceStore((s) => s.ir?.projectId);

  const openDiffCompare = () => {
    if (!projectId) return;
    navigate(`/projects/${projectId}/repo?diff=1&branch=${encodeURIComponent(currentBranch?.public_id || 'main')}`);
  };

  return (
    <div className="flex items-center gap-2">
      <BranchSelector />

      {dirty && hasChanges && !isProtected && (
        <button
          type="button"
          onClick={() => setShowCommit(true)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs font-semibold text-amber-700 hover:bg-amber-100"
          title={t('versionControl.uncommitted', { count: dirty.modified_entities_count })}
        >
          <span className="h-2 w-2 rounded-full bg-amber-500" />
          {t('versionControl.uncommitted', { count: dirty.modified_entities_count })}
        </button>
      )}

      {!isProtected && canWrite && (
        <button
          type="button"
          onClick={() => setShowCommit(true)}
          disabled={!hasChanges}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-white',
            hasChanges ? 'bg-indigo-600 hover:bg-indigo-700' : 'cursor-not-allowed bg-slate-300'
          )}
          title={hasChanges ? t('versionControl.commit') : t('versionControl.commitDisabledNoChanges')}
        >
          <GitCommitHorizontal className="h-3.5 w-3.5" />
          {t('versionControl.commit')}
        </button>
      )}

      {/* main 受保护时不给直接提交入口，改为引导创建分支/发起 MR（设计文档 3.1）。 */}
      {isProtected && (
        <button
          type="button"
          onClick={() => projectId && navigate(`/projects/${projectId}/repo?new_branch=1`)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-2.5 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100"
        >
          <GitCommitHorizontal className="h-3.5 w-3.5" />
          {t('versionControl.guide.protectedAction')}
        </button>
      )}

      <CommitDialog open={showCommit} onClose={() => setShowCommit(false)} onCompare={openDiffCompare} />
    </div>
  );
}
