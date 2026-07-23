import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { NodeStatus } from '@/core/schema';
import { NodeStatusToText } from '@/core/presentationLabels';

interface StatusBadgeProps {
  status: NodeStatus | string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const { t } = useTranslation();
  const statusStyles: Record<string, string> = {
    'confirmed': 'bg-emerald-50 text-emerald-700 border-emerald-200 border',
    'confirmed_zh': 'bg-emerald-50 text-emerald-700 border-emerald-200 border',
    'ready': 'bg-emerald-50 text-emerald-700 border-emerald-200 border',
    
    'ai_assumption': 'bg-indigo-50 text-indigo-700 border-indigo-200 border',
    'ai_assumption_zh': 'bg-indigo-50 text-indigo-700 border-indigo-200 border',
    'ai_presumption_zh': 'bg-indigo-50 text-indigo-700 border-indigo-200 border',

    'needs_confirmation': 'bg-amber-50 text-amber-700 border-amber-200 border',
    'needs_confirmation_zh': 'bg-amber-50 text-amber-700 border-amber-200 border',
    'warning': 'bg-amber-50 text-amber-700 border-amber-200 border',

    'conflict': 'bg-rose-50 text-rose-600 border-rose-200 border',
    'conflict_zh': 'bg-rose-50 text-rose-600 border-rose-200 border',
    'error': 'bg-rose-50 text-rose-600 border-rose-200 border',

    'deferred': 'bg-slate-50 text-slate-600 border-slate-200 border',
    'deferred_zh': 'bg-slate-50 text-slate-600 border-slate-200 border',

    'excluded': 'bg-zinc-100/50 text-zinc-400 border-zinc-200/50 border line-through',
    'excluded_zh': 'bg-zinc-100/50 text-zinc-400 border-zinc-200/50 border line-through',
    
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
    candidate: t('status.candidate'),
    selected: t('status.selected'),
    rejected: t('status.rejected'),
    archived: t('status.archived'),
  };
  const displayText = (NodeStatusToText as Record<string, string>)[status] || extraText[status] || status;

  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-bold tracking-wide', statusStyles[status] || 'bg-slate-50 text-slate-600 border-slate-200 border', className)}>
      {displayText}
    </span>
  );
}
