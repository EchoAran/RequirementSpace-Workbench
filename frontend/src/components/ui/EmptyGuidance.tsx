import { LucideIcon, Sparkles, Inbox } from 'lucide-react';
import { twMerge } from 'tailwind-merge';

interface EmptyGuidanceProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  actionLabel?: string;
  actionIcon?: LucideIcon;
  onAction?: () => void;
  className?: string;
}

export function EmptyGuidance({
  icon: Icon = Inbox,
  title,
  description,
  actionLabel,
  actionIcon: ActionIcon = Sparkles,
  onAction,
  className,
}: EmptyGuidanceProps) {
  return (
    <div
      className={twMerge(
        'flex flex-col items-center justify-center p-8 rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 text-center transition-all duration-300',
        className,
      )}
    >
      <div className="w-12 h-12 rounded-2xl bg-white shadow-xs border border-slate-100 flex items-center justify-center text-slate-400 mb-3.5">
        <Icon className="w-6 h-6 text-slate-400" aria-hidden="true" />
      </div>
      <h4 className="text-sm font-semibold text-slate-700 mb-1">{title}</h4>
      {description && (
        <p className="text-xs text-slate-500 max-w-sm mb-4 leading-relaxed">
          {description}
        </p>
      )}
      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 active:scale-95 rounded-xl shadow-xs transition-all duration-200 cursor-pointer"
        >
          <ActionIcon className="w-3.5 h-3.5" aria-hidden="true" />
          <span>{actionLabel}</span>
        </button>
      )}
    </div>
  );
}
