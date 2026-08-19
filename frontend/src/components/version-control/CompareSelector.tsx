import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowLeftRight, GitBranch, GitCommitHorizontal, Play } from 'lucide-react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { workspaceApi } from '@/lib/api';
import { CommitSummary } from '@/core/versionControl';
import { cn } from '@/lib/utils';

/**
 * 任意版本比较选择器（Phase D）。
 *
 * 基准/目标各选一个 ref（workspace / branch / commit），支持交换与开始比较。
 * 比较状态由调用方通过 URL（base_ref/target_ref）保存，可刷新/分享/深链。
 * 复用 DiffRefInfo 的三类 ref 语义：commit:<id> / branch:<id> / workspace:<branchRef>。
 */

type RefKind = 'workspace' | 'branch' | 'commit';

interface RefState {
  kind: RefKind;
  value: string; // commit public_id / branch public_id / branchRef(workspace)
}

interface CompareSelectorProps {
  projectId: string;
  baseRef?: string;
  targetRef?: string;
  branchRef?: string;
  onChange: (baseRef: string | undefined, targetRef: string | undefined) => void;
}

function parseRef(ref?: string): RefState | null {
  if (!ref) return null;
  const idx = ref.indexOf(':');
  if (idx <= 0) return null;
  const kind = ref.slice(0, idx) as RefKind;
  const value = ref.slice(idx + 1);
  if (!['workspace', 'branch', 'commit'].includes(kind) || !value) return null;
  return { kind, value };
}

function toRef(state: RefState): string {
  return `${state.kind}:${state.value}`;
}

export function CompareSelector({ projectId, baseRef, targetRef, branchRef = 'main', onChange }: CompareSelectorProps) {
  const { t } = useTranslation();
  const branches = useWorkspaceStore((s) => s.branches);
  const [base, setBase] = useState<RefState>({ kind: 'workspace', value: branchRef });
  const [target, setTarget] = useState<RefState>({ kind: 'workspace', value: branchRef });
  const [commitOptions, setCommitOptions] = useState<CommitSummary[]>([]);

  // 挂载时独立拉取提交选项（all + limit 200），与 store 已加载提交合并去重。
  useEffect(() => {
    let cancelled = false;
    workspaceApi.listCommits(projectId, { all: true, limit: 200 }).then((res) => {
      if (cancelled) return;
      setCommitOptions(res.commits);
    }).catch(() => { /* 提交选项加载失败不阻塞比较器 */ });
    return () => { cancelled = true; };
  }, [projectId]);

  // 从 URL 初始化（base_ref/target_ref 深链回读）。
  useEffect(() => {
    const b = parseRef(baseRef);
    const tg = parseRef(targetRef);
    if (b) setBase(b);
    if (tg) setTarget(tg);
  }, [baseRef, targetRef]);

  const swap = () => {
    setBase(target);
    setTarget(base);
  };

  const apply = () => onChange(toRef(base), toRef(target));

  const branchChoices = useMemo(() => {
    const list = branches || [];
    // workspace 的 ref 值是当前分支，无需作为 branch 下拉项；只列非 workspace 分支。
    return list;
  }, [branches]);

  const renderSide = (state: RefState, setState: (s: RefState) => void, label: string) => (
    <div className="flex min-w-0 flex-col gap-1">
      <span className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{label}</span>
      <div className="flex gap-1.5">
        <select
          value={state.kind}
          onChange={(e) => setState({ ...state, kind: e.target.value as RefKind })}
          aria-label={`${label} ${t('versionControl.diff.base')}`}
          className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700 focus-visible:ring-2 focus-visible:ring-indigo-400"
        >
          <option value="workspace">workspace</option>
          <option value="branch">branch</option>
          <option value="commit">commit</option>
        </select>
        {state.kind === 'workspace' && (
          <select
            value={state.value}
            onChange={(e) => setState({ ...state, value: e.target.value })}
            aria-label={`${label} value`}
            className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
          >
            <option value={branchRef}>{branchRef}</option>
          </select>
        )}
        {state.kind === 'branch' && (
          <select
            value={state.value}
            onChange={(e) => setState({ ...state, value: e.target.value })}
            aria-label={`${label} value`}
            className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
          >
            {branchChoices.map((b) => (
              <option key={b.public_id} value={b.public_id}>{b.name}</option>
            ))}
          </select>
        )}
        {state.kind === 'commit' && (
          <select
            value={state.value}
            onChange={(e) => setState({ ...state, value: e.target.value })}
            aria-label={`${label} value`}
            className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
          >
            {commitOptions.map((c) => (
              <option key={c.public_id} value={c.public_id}>{c.short_id} · {c.message}</option>
            ))}
          </select>
        )}
      </div>
    </div>
  );

  return (
    <div className="flex flex-wrap items-end gap-2 rounded-xl border border-slate-200 bg-white p-3">
      {renderSide(base, setBase, t('versionControl.diff.base'))}
      <button
        type="button"
        onClick={swap}
        aria-label="swap"
        className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-slate-50"
      >
        <ArrowLeftRight className="h-4 w-4" />
      </button>
      {renderSide(target, setTarget, t('versionControl.diff.target'))}
      <button
        type="button"
        onClick={apply}
        className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-700"
      >
        <Play className="h-3.5 w-3.5" />
        {t('versionControl.diff.title')}
      </button>
    </div>
  );
}
