import { cn } from '@/lib/utils';
import { NodeStatus, NodeStatusToText } from '@/types';

interface StatusBadgeProps {
  status: NodeStatus | string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const statusStyles: Record<string, string> = {
    'confirmed': 'bg-emerald-50 text-emerald-700 border-emerald-200 border',
    '已确认': 'bg-emerald-50 text-emerald-700 border-emerald-200 border',
    'ready': 'bg-emerald-50 text-emerald-700 border-emerald-200 border',
    
    'ai_assumption': 'bg-indigo-50 text-indigo-700 border-indigo-200 border',
    'AI 假设': 'bg-indigo-50 text-indigo-700 border-indigo-200 border',

    'needs_confirmation': 'bg-amber-50 text-amber-700 border-amber-200 border',
    '待确认': 'bg-amber-50 text-amber-700 border-amber-200 border',
    'warning': 'bg-amber-50 text-amber-700 border-amber-200 border',

    'conflict': 'bg-rose-50 text-rose-600 border-rose-200 border',
    '有冲突': 'bg-rose-50 text-rose-600 border-rose-200 border',
    'error': 'bg-rose-50 text-rose-600 border-rose-200 border',

    'deferred': 'bg-slate-50 text-slate-600 border-slate-200 border',
    '暂缓': 'bg-slate-50 text-slate-600 border-slate-200 border',

    'excluded': 'bg-zinc-100/50 text-zinc-400 border-zinc-200/50 border line-through',
    '已排除': 'bg-zinc-100/50 text-zinc-400 border-zinc-200/50 border line-through',
    
    // For Issue status
    'open': 'bg-rose-50 text-rose-600 border-rose-200 border',
    'resolved': 'bg-emerald-50 text-emerald-700 border-emerald-200 border',
    'ignored': 'bg-slate-50 text-slate-600 border-slate-200 border',

    // For Choice status
    'candidate': 'bg-blue-50 text-blue-700 border-blue-200 border',
    'selected': 'bg-emerald-50 text-emerald-700 border-emerald-200 border',
    'rejected': 'bg-zinc-100/50 text-zinc-400 border-zinc-200/50 border line-through',
    'archived': 'bg-slate-50 text-slate-600 border-slate-200 border',
  };

  const extraText: Record<string, string> = {
    candidate: '候选',
    selected: '已采纳',
    rejected: '已拒绝',
    archived: '已归档',
  };
  const displayText = (NodeStatusToText as Record<string, string>)[status] || extraText[status] || status;

  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-bold tracking-wide', statusStyles[status] || 'bg-slate-50 text-slate-600 border-slate-200 border', className)}>
      {displayText}
    </span>
  );
}
