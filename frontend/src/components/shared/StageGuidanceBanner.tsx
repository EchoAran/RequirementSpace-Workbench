import { useState } from 'react';
import { ArrowRight, ChevronDown, ChevronUp, LocateFixed, RefreshCw, Sparkles, X } from 'lucide-react';
import { Issue, PerceptionSlot } from '@/core/schema';
import { cn } from '@/lib/utils';

interface StageGuidanceBannerProps {
  slot?: PerceptionSlot;
  issues?: Issue[];
  onManualAction?: (slot: PerceptionSlot) => void;
  onAIAction?: (slot: PerceptionSlot) => void;
  onReDiagnose?: () => void;
  onIssueClick?: (issue: Issue) => void;
  onIssueCreateSlot?: (issue: Issue) => void;
  onIssueIgnore?: (issue: Issue) => void;
  isWorking?: boolean;
}

const severityLabel: Record<Issue['severity'], string> = {
  high: '高风险',
  medium: '需处理',
  low: '提示',
};

const severityClass: Record<Issue['severity'], string> = {
  high: 'bg-rose-50 text-rose-700 border-rose-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  low: 'bg-slate-50 text-slate-600 border-slate-200',
};

export function StageGuidanceBanner({
  slot,
  issues = [],
  onManualAction,
  onAIAction,
  onReDiagnose,
  onIssueClick,
  onIssueCreateSlot,
  onIssueIgnore,
  isWorking = false,
}: StageGuidanceBannerProps) {
  const openIssues = issues.filter((issue) => issue.status === 'open');
  const [expanded, setExpanded] = useState(false);
  const hideSlotActions = slot?.kind === 'how_onboarding';
  const isPerceptionSlot = slot?.kind === 'generative_perception_slot';
  const isStageTransitionSuggestion = slot?.kind === 'stage_gate_transition_confirm';
  const hasAiDiagnoseAction = Boolean(slot?.actions?.ai?.label?.includes('诊断'));
  const showReDiagnoseButton = Boolean(
    onReDiagnose && !hideSlotActions && (!slot || isPerceptionSlot) && (!slot || !hasAiDiagnoseAction)
  );

  if (!slot && openIssues.length === 0 && onReDiagnose) {
    return (
      <div className="rounded-lg border border-emerald-100 border-l-4 border-l-emerald-500 bg-emerald-50/40 p-3">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-semibold leading-relaxed text-slate-600">
              当前阶段暂未发现待处理 Issue，可以继续完善当前内容，或重新发起诊断。
            </p>
          </div>
          <button
            type="button"
            onClick={onReDiagnose}
            disabled={isWorking}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-bold text-white shadow-sm transition-colors hover:bg-indigo-500 disabled:opacity-50"
          >
            <RefreshCw className={cn('h-3 w-3', isWorking && 'animate-spin')} />
            重新诊断
          </button>
        </div>
      </div>
    );
  }

  if (!slot && openIssues.length === 0) return null;

  const isBlocking = Boolean(slot?.blocking || openIssues.some((issue) => issue.severity === 'high'));

  return (
    <div
      className={cn(
        'rounded-lg border border-l-4 bg-white p-4 shadow-sm',
        isBlocking ? 'border-rose-100 border-l-rose-500' : 'border-amber-100 border-l-amber-500',
      )}
    >
      <div className="flex flex-col gap-4">
        {slot && (
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="min-w-0 space-y-1">
              <span
                className={cn(
                  'inline-flex rounded border px-2 py-0.5 text-[10px] font-black',
                  slot.blocking
                    ? 'border-rose-200 bg-rose-50 text-rose-800'
                    : 'border-indigo-200 bg-indigo-50 text-indigo-800',
                )}
              >
                下一步建议
              </span>
              <p className="text-xs font-semibold leading-relaxed text-slate-700">
                {slot.description}
              </p>
            </div>

            <div className="flex shrink-0 items-center gap-2 self-end md:self-center">
              {showReDiagnoseButton && (
                <button
                  type="button"
                  onClick={onReDiagnose}
                  disabled={isWorking}
                  className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 shadow-sm transition-colors hover:bg-slate-50 disabled:opacity-50"
                >
                  <RefreshCw className={cn('h-3 w-3', isWorking && 'animate-spin')} />
                  重新诊断
                </button>
              )}
              {!hideSlotActions && slot.actions?.ai && onAIAction && (
                <button
                  type="button"
                  onClick={() => onAIAction(slot)}
                  disabled={isWorking}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-black text-white transition-colors disabled:opacity-50',
                    slot.blocking ? 'bg-rose-600 hover:bg-rose-500' : 'bg-indigo-600 hover:bg-indigo-500',
                  )}
                >
                  <Sparkles className="h-3 w-3" />
                  {slot.actions.ai.label}
                </button>
              )}
              {!hideSlotActions && (isPerceptionSlot || isStageTransitionSuggestion) && slot.actions?.manual && onManualAction && (
                <button
                  type="button"
                  onClick={() => onManualAction(slot)}
                  disabled={isWorking}
                  className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 shadow-sm transition-colors hover:bg-slate-50 disabled:opacity-50"
                >
                  {isPerceptionSlot ? <X className="h-3 w-3" /> : <ArrowRight className="h-3 w-3" />}
                  {isPerceptionSlot ? '忽略' : '进入下一阶段'}
                </button>
              )}
            </div>
          </div>
        )}

        {openIssues.length > 0 && (
          <div className={cn(slot && 'border-t border-slate-100 pt-3')}>
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              className="flex w-full items-center justify-between gap-3 text-left"
            >
              <div className="min-w-0">
                <div className="text-sm font-black text-slate-900">
                  仍有 {openIssues.length} 个 Issue 待处理
                </div>
                <div className="truncate text-xs text-slate-500">
                  {openIssues[0]?.title}
                </div>
              </div>
              {expanded ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
            </button>

            {expanded && (
              <div className="mt-3 space-y-2">
                {openIssues.map((issue) => (
                  <div
                    key={issue.id}
                    className="flex flex-col gap-2 rounded-md border border-slate-200 bg-slate-50/60 p-3 md:flex-row md:items-start md:justify-between"
                  >
                    <button
                      type="button"
                      onClick={() => onIssueClick?.(issue)}
                      className="min-w-0 flex-1 text-left"
                    >
                      <div className="mb-1 flex flex-wrap items-center gap-2">
                        <span className={cn('rounded border px-1.5 py-0.5 text-[10px] font-black', severityClass[issue.severity])}>
                          {severityLabel[issue.severity]}
                        </span>
                        <span className="text-[10px] font-bold uppercase tracking-wide text-slate-400">
                          {issue.domain || issue.category || issue.stage || 'issue'}
                        </span>
                      </div>
                      <div className="text-sm font-bold text-slate-900">{issue.title}</div>
                      <div className="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-500">{issue.description}</div>
                    </button>

                    <div className="flex shrink-0 items-center gap-2 self-end md:self-start">
                      <button
                        type="button"
                        onClick={() => onIssueClick?.(issue)}
                        className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-bold text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
                      >
                        <LocateFixed className="h-3 w-3" />
                        定位
                      </button>
                      {onIssueCreateSlot && (
                        <button
                          type="button"
                          onClick={() => onIssueCreateSlot(issue)}
                          disabled={isWorking}
                          className="inline-flex items-center gap-1 rounded-md bg-slate-900 px-2.5 py-1.5 text-xs font-bold text-white shadow-sm transition-colors hover:bg-slate-800 disabled:opacity-50"
                        >
                          <Sparkles className="h-3 w-3" />
                          AI 处理
                        </button>
                      )}
                      {onIssueIgnore && (
                        <button
                          type="button"
                          onClick={() => onIssueIgnore(issue)}
                          disabled={isWorking}
                          className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 shadow-sm transition-colors hover:bg-slate-50 hover:text-slate-700 disabled:opacity-50"
                          title="忽略"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
