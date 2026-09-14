import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowLeftRight, Play } from 'lucide-react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { workspaceApi } from '@/lib/api';
import { CommitSummary } from '@/core/versionControl';

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
  branchRef: string;
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

export function CompareSelector({ projectId, baseRef, targetRef, branchRef, onChange }: CompareSelectorProps) {
  const { t } = useTranslation();
  const branches = useWorkspaceStore((s) => s.branches);
  const [base, setBase] = useState<RefState>({ kind: 'workspace', value: branchRef });
  const [target, setTarget] = useState<RefState>({ kind: 'workspace', value: branchRef });
  const [commitOptions, setCommitOptions] = useState<CommitSummary[]>([]);
  const [commitsLoading, setCommitsLoading] = useState(false);

  // 挂载时独立拉取提交选项（all + limit 200），与 store 已加载提交合并去重。
  useEffect(() => {
    let cancelled = false;
    setCommitsLoading(true);
    workspaceApi.listCommits(projectId, { all: true, limit: 200 }).then((res) => {
      if (cancelled) return;
      setCommitOptions(res.commits);
    }).catch(() => { /* 提交选项加载失败不阻塞比较器 */ })
      .finally(() => {
        if (!cancelled) setCommitsLoading(false);
      });
    return () => { cancelled = true; };
  }, [projectId]);

  // 从 URL 初始化（base_ref/target_ref 深链回读）。
  useEffect(() => {
    setBase(parseRef(baseRef) ?? { kind: 'workspace', value: branchRef });
    setTarget(parseRef(targetRef) ?? { kind: 'workspace', value: branchRef });
  }, [baseRef, targetRef, branchRef]);

  const swap = () => {
    setBase(target);
    setTarget(base);
  };

  const apply = () => {
    if (!isValidRef(base) || !isValidRef(target)) return;
    onChange(toRef(base), toRef(target));
  };

  const branchChoices = useMemo(() => {
    return branches || [];
  }, [branches]);

  const handleKindChange = (newKind: RefKind, setState: (s: RefState) => void) => {
    let defaultValue = '';
    if (newKind === 'workspace') {
      defaultValue = branchRef;
    } else if (newKind === 'branch') {
      defaultValue = branchChoices.find((b) => b.public_id === branchRef || b.name === branchRef)?.public_id ?? '';
    } else if (newKind === 'commit') {
      defaultValue = commitOptions[0]?.public_id || '';
    }
    setState({ kind: newKind, value: defaultValue });
  };

  const isValidRef = (state: RefState): boolean => {
    if (!state.value) return false;
    if (state.kind === 'commit' && commitOptions.length > 0) {
      return commitOptions.some((c) => c.public_id === state.value);
    }
    if (state.kind === 'branch') {
      return branchChoices.some((b) => b.public_id === state.value || b.name === state.value);
    }
    return true;
  };

  const canCompare = isValidRef(base) && isValidRef(target);

  const renderSide = (state: RefState, setState: (s: RefState) => void, label: string) => (
    <div className="flex min-w-0 flex-col gap-1">
      <span className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{label}</span>
      <div className="flex gap-1.5">
        <select
          value={state.kind}
          onChange={(e) => handleKindChange(e.target.value as RefKind, setState)}
          aria-label={`${label} ${t('versionControl.diff.base')}`}
          className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700 focus-visible:ring-2 focus-visible:ring-indigo-400"
        >
          <option value="workspace">workspace</option>
          <option value="branch">branch</option>
          <option value="commit">commit</option>
        </select>
        {state.kind === 'workspace' && (
          <select
            value={branchChoices.find((b) => b.public_id === state.value || b.name === state.value)?.public_id ?? state.value}
            onChange={(e) => setState({ ...state, value: e.target.value })}
            aria-label={`${label} value`}
            className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
          >
            {branchChoices.length === 0 ? (
              <option value={branchRef}>{branchRef}</option>
            ) : (
              branchChoices.map((b) => (
                <option key={b.public_id} value={b.public_id}>{b.name}</option>
              ))
            )}
          </select>
        )}
        {state.kind === 'branch' && (
          <select
            value={branchChoices.find((b) => b.public_id === state.value || b.name === state.value)?.public_id ?? state.value}
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
            {commitOptions.length === 0 && (
              <option value="">{commitsLoading ? t('shell.loading') : t('versionControl.compare.noCommits', '无可用提交')}</option>
            )}
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
        disabled={!canCompare}
        className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        <Play className="h-3.5 w-3.5" />
        {t('versionControl.diff.title')}
      </button>
    </div>
  );
}
