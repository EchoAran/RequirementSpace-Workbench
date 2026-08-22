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
 * 布局为完整多泳道 DAG（lane 拓扑分配与多分支独立 x 坐标偏移）：满足"Git 图"验收
 * （分叉/合并/父子连线/分支着色/点击选中），且可在无视觉回归工具下用 React 测试断言。
 */

interface CommitGraphProps {
  commits: CommitSummary[];
  selectedPublicId?: string | null;
  onSelect: (commit: CommitSummary) => void;
}

const ROW_H = 56;
const NODE_RADIUS = 6;
const BASE_LEFT = 20;
const LANE_SPACING = 16;

// 分支着色小调色板（按分支名稳定哈希取色）。
const BRANCH_COLORS = ['#6366f1', '#0d9488', '#d97706', '#db2777', '#4f46e5', '#059669', '#2563eb', '#7c3aed'];

function branchColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) | 0;
  return BRANCH_COLORS[Math.abs(hash) % BRANCH_COLORS.length];
}

interface EdgeSeg {
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
  fromLoaded: boolean;
  color: string;
}

/**
 * 完整多泳道拓扑分配与父子连线生成。
 */
function layoutGraph(commits: CommitSummary[], byPublicId: Map<string, CommitSummary>) {
  const lanes: number[] = [];
  const activeLanes: (string | null)[] = [];
  let maxLane = 0;

  // 1. 为每个 Commit 计算所属泳道
  for (let i = 0; i < commits.length; i++) {
    const commit = commits[i];
    let lane = activeLanes.indexOf(commit.public_id);
    if (lane === -1) {
      lane = activeLanes.indexOf(null);
      if (lane === -1) {
        lane = activeLanes.length;
        activeLanes.push(commit.public_id);
      } else {
        activeLanes[lane] = commit.public_id;
      }
    }
    lanes.push(lane);
    maxLane = Math.max(maxLane, lane);

    // 清理其他重复指向当前 commit 的泳道槽位（汇聚时清理）
    for (let l = 0; l < activeLanes.length; l++) {
      if (l !== lane && activeLanes[l] === commit.public_id) {
        activeLanes[l] = null;
      }
    }

    // 为父提交分配泳道
    if (commit.parent_public_ids.length > 0) {
      const firstParent = commit.parent_public_ids[0];
      activeLanes[lane] = firstParent;

      for (let p = 1; p < commit.parent_public_ids.length; p++) {
        const otherParent = commit.parent_public_ids[p];
        if (!activeLanes.includes(otherParent)) {
          const emptySlot = activeLanes.indexOf(null);
          if (emptySlot === -1) {
            activeLanes.push(otherParent);
          } else {
            activeLanes[emptySlot] = otherParent;
          }
        }
      }
    } else {
      activeLanes[lane] = null;
    }
  }

  // 2. 生成贝塞尔连线
  const edges: EdgeSeg[] = [];
  commits.forEach((commit, idx) => {
    const fromLane = lanes[idx];
    const fromX = BASE_LEFT + fromLane * LANE_SPACING;
    const fromY = (idx + 0.5) * ROW_H;
    const isMerge = commit.is_merge;
    const edgeColor = isMerge ? '#f59e0b' : (commit.branch_names[0] ? branchColor(commit.branch_names[0]) : '#cbd5e1');

    commit.parent_public_ids.forEach((parentId, pIdx) => {
      const parent = byPublicId.get(parentId);
      if (parent) {
        const parentIdx = commits.indexOf(parent);
        const toLane = lanes[parentIdx] ?? fromLane;
        const toX = BASE_LEFT + toLane * LANE_SPACING;
        const toY = (parentIdx + 0.5) * ROW_H;
        edges.push({
          fromX,
          fromY,
          toX,
          toY,
          fromLoaded: true,
          color: pIdx > 0 ? '#f59e0b' : edgeColor,
        });
      } else {
        edges.push({
          fromX,
          fromY,
          toX: fromX,
          toY: (idx + 1.2) * ROW_H,
          fromLoaded: false,
          color: edgeColor,
        });
      }
    });
  });

  return { lanes, maxLane, edges };
}

export function CommitGraph({ commits, selectedPublicId, onSelect }: CommitGraphProps) {
  const byPublicId = useMemo(() => new Map(commits.map((c) => [c.public_id, c])), [commits]);
  const { lanes, maxLane, edges } = useMemo(() => layoutGraph(commits, byPublicId), [commits, byPublicId]);
  const height = commits.length * ROW_H;
  const graphWidth = Math.max(BASE_LEFT + (maxLane + 1) * LANE_SPACING + 20, 60);

  return (
    <div className="relative" style={{ minHeight: height }}>
      {/* SVG 边层：贝塞尔父子连线 */}
      <svg
        aria-hidden="true"
        className="pointer-events-none absolute left-0 top-0 overflow-visible"
        width={graphWidth}
        height={height}
      >
        {edges.map((seg, i) => {
          const { fromX, fromY, toX, toY } = seg;
          const midY = (fromY + toY) / 2;
          const d = `M ${fromX} ${fromY} C ${fromX} ${midY}, ${toX} ${midY}, ${toX} ${toY}`;
          return (
            <g key={`edge-${i}`}>
              {!seg.fromLoaded ? (
                <line
                  x1={fromX}
                  y1={fromY + NODE_RADIUS}
                  x2={toX}
                  y2={toY}
                  stroke={seg.color}
                  strokeWidth="1.5"
                  strokeDasharray="3 3"
                />
              ) : (
                <path d={d} fill="none" stroke={seg.color} strokeWidth="1.5" strokeOpacity={0.8} />
              )}
            </g>
          );
        })}
      </svg>

      {/* 节点层：绝对定位 HTML 按钮叠加在 SVG 之上 */}
      {commits.map((commit, idx) => {
        const isSelected = commit.public_id === selectedPublicId;
        const isMerge = commit.is_merge;
        const color = isMerge ? '#d97706' : (commit.branch_names[0] ? branchColor(commit.branch_names[0]) : '#64748b');
        const nodeX = BASE_LEFT + lanes[idx] * LANE_SPACING;
        const contentLeft = Math.max(BASE_LEFT + (maxLane + 1) * LANE_SPACING + 12, 44);
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
              className="absolute rounded-full border-2 border-white shadow-xs"
              style={{
                left: nodeX - NODE_RADIUS,
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
                style={{ left: nodeX - 10, top: ROW_H / 2 + NODE_RADIUS + 1 }}
              >
                …
              </span>
            )}
            <button
              type="button"
              aria-current={isSelected ? 'true' : undefined}
              aria-label={`${commit.message}, ${commit.short_id}`}
              onClick={() => onSelect(commit)}
              style={{ marginLeft: `${contentLeft}px`, width: `calc(100% - ${contentLeft + 8}px)` }}
              className={cn(
                'rounded-lg border border-transparent px-2 py-1.5 text-left transition-colors hover:border-slate-200 hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-indigo-400',
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
