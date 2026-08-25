import { twMerge } from 'tailwind-merge';
import { CheckCircle2, AlertCircle, Sparkles, ShieldAlert, HeartPulse, HelpCircle } from 'lucide-react';

export type BadgeStatusType =
  | 'confirmed'
  | 'needs_confirmation'
  | 'ai_assumption'
  | 'in_scope'
  | 'out_of_scope'
  | 'issue'
  | 'gate'
  | 'health'
  | 'open'
  | 'resolved';

interface TokenBadgeProps {
  status: BadgeStatusType | string;
  label?: string;
  size?: 'sm' | 'md';
  showIcon?: boolean;
  className?: string;
}

export function TokenBadge({
  status,
  label,
  size = 'md',
  showIcon = true,
  className,
}: TokenBadgeProps) {
  const getStatusConfig = (s: string) => {
    switch (s) {
      case 'confirmed':
      case 'resolved':
        return {
          bg: 'bg-emerald-50 text-emerald-700 border-emerald-200/60',
          icon: CheckCircle2,
          defaultLabel: '已确认',
        };
      case 'needs_confirmation':
        return {
          bg: 'bg-amber-50 text-amber-700 border-amber-200/60',
          icon: AlertCircle,
          defaultLabel: '待确认',
        };
      case 'ai_assumption':
        return {
          bg: 'bg-purple-50 text-purple-700 border-purple-200/60',
          icon: Sparkles,
          defaultLabel: 'AI 假设',
        };
      case 'in_scope':
        return {
          bg: 'bg-indigo-50 text-indigo-700 border-indigo-200/60',
          icon: CheckCircle2,
          defaultLabel: '范围内',
        };
      case 'out_of_scope':
        return {
          bg: 'bg-slate-100 text-slate-600 border-slate-200/60',
          icon: HelpCircle,
          defaultLabel: '范围外',
        };
      case 'issue':
      case 'open':
        return {
          bg: 'bg-rose-50 text-rose-700 border-rose-200/60',
          icon: AlertCircle,
          defaultLabel: '缺陷',
        };
      case 'gate':
        return {
          bg: 'bg-amber-50 text-amber-800 border-amber-200/60',
          icon: ShieldAlert,
          defaultLabel: '门禁',
        };
      case 'health':
        return {
          bg: 'bg-sky-50 text-sky-700 border-sky-200/60',
          icon: HeartPulse,
          defaultLabel: '健康度',
        };
      default:
        return {
          bg: 'bg-slate-100 text-slate-700 border-slate-200/60',
          icon: HelpCircle,
          defaultLabel: s,
        };
    }
  };

  const config = getStatusConfig(status);
  const Icon = config.icon;
  const displayText = label || config.defaultLabel;

  const sizeClasses = size === 'sm'
    ? 'text-[10px] px-1.5 py-0.5 gap-1'
    : 'text-xs px-2.5 py-0.5 gap-1.5';

  return (
    <span
      className={twMerge(
        'inline-flex items-center font-medium rounded-full border shadow-2xs transition-colors duration-200 select-none',
        config.bg,
        sizeClasses,
        className,
      )}
    >
      {showIcon && <Icon className={size === 'sm' ? 'w-2.5 h-2.5 shrink-0' : 'w-3.5 h-3.5 shrink-0'} aria-hidden="true" />}
      <span>{displayText}</span>
    </span>
  );
}
