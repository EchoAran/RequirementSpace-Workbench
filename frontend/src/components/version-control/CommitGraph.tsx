import { useMemo } from 'react';
import { GitCommitHorizontal } from 'lucide-react';
import { CommitSummary } from '@/core/versionControl';
import { cn } from '@/lib/utils';

/**
 * 自绘 SVG 提交图（Phase C）。
 *
 * 以提交时间倒序排列为行（y = index * ROW_H），父提交用贝塞尔 S 曲线连线；
 * merge 提交画两条入边（主父/副父）；父提交未在当前分页列表内时画向上残段 + 省略标记。
 * 分支着色：按提交首个分支名哈希到小调色板；无分支 → slate；merge → amber。
 *
 * 布局为简化垂直 DAG（不做完整泳道 lane 分配）：满足"Git 图"验收
 * （分叉/合并/父子连线/分支着色/点击选中），且可在无视觉回归工具下用 React 测试断言。
 */

interface CommitGraphProps {
  commits: CommitSummary[];
  selectedPublicId?: string | null;
  onSelect: (commit: CommitSummary) => void;
}

const ROW_H = 56;
const NODE_RADIUS = 7;
const NODE_LEFT = 24;
const CANVAS_WIDTH = 460;

// 分支着色小调色板（按分支名稳定哈希取色）。
const BRANCH_COLORS = ['#6366f1', '#0d9488', '#d97706', '#db2777', '#4f46e5', '#059669'];

function branchColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) | 0;
  return BRANCH_COLORS[Math.abs(hash) % BRANCH_COLORS.length];
}

interface EdgeSeg {
  fromY: number;
  toY: number;
  fromLoaded: boolean;
}

/**
 * 派生父提交连线：每行提交向每个父提交画一条边。
 * 父不在已加载集合 → fromLoaded=false（画残段 + 省略标记）。
 */
function edgeSegments(commits: CommitSummary[], byPublicId: Map<string, CommitSummary>): EdgeSeg[] {
  const segs: EdgeSeg[] = [];
  commits.forEach((commit, idx) => {
    for (const parentId of commit.parent_public_ids) {
      const parent = byPublicId.get(parentId);
      segs.push({
        fromY: (idx + 0.5) * ROW_H,
        toY: parent ? (commits.indexOf(parent) + 0.5) * ROW_H : (idx + 1.5) * ROW_H,
        fromLoaded: Boolean(parent),
      });
    }
  });
  return segs;
}

export function CommitGraph({ commits, selectedPublicId, onSelect }: CommitGraphProps) {
  const byPublicId = useMemo(() => new Map(commits.map((c) => [c.public_id, c])), [commits]);
  const edges = useMemo(() => edgeSegments(commits, byPublicId), [commits, byPublicId]);
  const height = commits.length * ROW_H;

  return (
    <div className="relative" style={{ minHeight: height }}>
      {/* SVG 边层：贝塞尔父子连线（不响应鼠标，避免遮挡节点） */}
      <svg
        aria-hidden="true"
        className="pointer-events-none absolute left-0 top-0 overflow-visible"
        width={CANVAS_WIDTH}
        height={height}
      >
        {edges.map((seg, i) => {
          const startY = seg.fromY;
          const endY = seg.toY;
          const d = `M ${NODE_LEFT} ${startY} C ${NODE_LEFT + 40} ${startY}, ${NODE_LEFT + 40} ${endY}, ${NODE_LEFT} ${endY}`;
          return (
            <g key={`edge-${i}`}>
              {!seg.fromLoaded && (
                <line
                  x1={NODE_LEFT}
                  y1={startY + NODE_RADIUS}
                  x2={NODE_LEFT}
                  y2={Math.min(startY + NODE_RADIUS + 14, endY)}
                  stroke="#cbd5e1"
                  strokeWidth="1.5"
                  strokeDasharray="3 3"
                />
              )}
              <path d={d} fill="none" stroke="#cbd5e1" strokeWidth="1.5" />
            </g>
          );
        })}
      </svg>

      {/* 节点层：绝对定位 HTML 按钮叠加在 SVG 之上 */}
      {commits.map((commit, idx) => {
        const isSelected = commit.public_id === selectedPublicId;
        const isMerge = commit.is_merge;
        const color = isMerge ? '#d97706' : (commit.branch_names[0] ? branchColor(commit.branch_names[0]) : '#64748b');
        // 父提交不在当前已加载集合时，在该行渲染向上省略标记（指示历史更早的提交未加载）。
        const hasUnloadedParent = commit.parent_public_ids.some((pid) => !byPublicId.has(pid));
        return (
          <div
            key={commit.public_id}
            className="absolute left-0 w-full"
            style={{ top: idx * ROW_H }}
          >
            {/* 节点圆点 */}
            <span
              aria-hidden="true"
              className="absolute rounded-full border-2 border-white shadow-sm"
              style={{
                left: NODE_LEFT - NODE_RADIUS,
                top: ROW_H / 2 - NODE_RADIUS,
                width: NODE_RADIUS * 2,
                height: NODE_RADIUS * 2,
                backgroundColor: color,
              }}
            />
            {/* 父未加载省略标记 */}
            {hasUnloadedParent && (
              <span
                aria-hidden="true"
                className="absolute text-[9px] font-bold text-slate-400"
                style={{ left: NODE_LEFT - 12, top: ROW_H / 2 + NODE_RADIUS + 1 }}
              >
                …
              </span>
            )}
            <button
              type="button"
              aria-current={isSelected ? 'true' : undefined}
              aria-label={`${commit.message}, ${commit.short_id}`}
              onClick={() => onSelect(commit)}
              className={cn(
                'ml-11 w-[calc(100%-2.75rem)] rounded-lg border border-transparent px-2 py-1.5 text-left transition-colors hover:border-slate-200 hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-indigo-400',
                isSelected && 'border-indigo-200 bg-indigo-50'
              )}
            >
              <span className="flex items-center gap-1.5">
                <GitCommitHorizontal className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                <span className="truncate text-sm font-medium text-slate-800">{commit.message}</span>
                {isMerge && (
                  <span className="shrink-0 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
                    merge
                  </span>
                )}
              </span>
              <span className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
                <span>{commit.author_email || commit.author_user_id || '-'}</span>
                <span className="font-mono">{commit.short_id}</span>
                {commit.branch_names.map((name) => (
                  <span key={name} className="rounded bg-slate-100 px-1.5 py-0.5 font-medium text-slate-600">{name}</span>
                ))}
              </span>
            </button>
          </div>
        );
      })}
    </div>
  );
}
