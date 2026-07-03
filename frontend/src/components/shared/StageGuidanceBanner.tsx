import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useWorkspaceStore, getFindingCapability } from '@/store/useWorkspaceStore';
import { ArrowRight, ChevronDown, ChevronUp, LocateFixed, RefreshCw, Sparkles, X, Heart, Cpu } from 'lucide-react';
import { Finding } from '@/core/schema';
import { cn } from '@/lib/utils';
import { getNextSuggestionPresentation } from '@/core/nextSuggestionPresentation';
import { findingTargetIds } from '@/core/findingPresentation';

interface StageGuidanceBannerProps {
  stage: 'what' | 'how' | 'scope';
}

const severityLabel: Record<string, string> = {
  high: '高风险',
  medium: '需处理',
  low: '提示',
};

const severityClass: Record<string, string> = {
  high: 'bg-rose-50 text-rose-700 border-rose-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  low: 'bg-slate-50 text-slate-600 border-slate-200',
};

export function StageGuidanceBanner({ stage }: StageGuidanceBannerProps) {
  const navigate = useNavigate();
  const ir = useWorkspaceStore((s) => s.ir);
  const findingsByView = useWorkspaceStore((s) => s.findingsByView) || { issues: [], next_action: [], gate: [], health: [] };
  const startFindingSuggestion = useWorkspaceStore((s) => s.startFindingSuggestion);
  const executeFindingIssueResolution = useWorkspaceStore((s) => s.executeFindingIssueResolution);
  const expandSlot = useWorkspaceStore((s) => s.expandSlot);
  const updateIssueAttributes = useWorkspaceStore((s) => s.updateIssueAttributes);
  const runDiagnosis = useWorkspaceStore((s) => s.runDiagnosis);
  const setSelectedObject = useWorkspaceStore((s) => s.setSelectedObject);
  const setHighlightTarget = useWorkspaceStore((s) => s.setHighlightTarget);
  const stageProgress = useWorkspaceStore((s) => s.stageProgress);

  const isLoading = useWorkspaceStore((s) => s.isLoading);
  const isGenerating = useWorkspaceStore((s) => s.isGenerating);
  const isDiagnosing = useWorkspaceStore((s) => s.isDiagnosing);
  const isWorking = isLoading || isGenerating || isDiagnosing;

  const [issuesExpanded, setIssuesExpanded] = useState(false);
  const [healthExpanded, setHealthExpanded] = useState(false);

  if (!ir) return null;

  // Filter findings by current stage
  const stageProgressItem = stageProgress?.stages?.find((s: any) => s.stage === stage);
  const stageAlreadyAdvanced = stageProgressItem?.statusCode === 'ready';
  const nextAction = stageAlreadyAdvanced
    ? null
    : (findingsByView.next_action || []).find((f) => f.stage === stage);
  const stageIssues = (findingsByView.issues || []).filter((f) => f.stage === stage);
  const stageHealthHints = (findingsByView.health || []).filter((f) => f.stage === stage);

  const totalActionable = (nextAction ? 1 : 0) + stageIssues.length + stageHealthHints.length;

  if (totalActionable === 0) {
    return (
      <div className="rounded-2xl border border-emerald-100 border-l-4 border-l-emerald-500 bg-emerald-50/40 p-4 shadow-sm">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-semibold leading-relaxed text-slate-600">
              当前阶段暂未发现待处理问题，模型结构健康。可以继续完善建模，或重新发起诊断。
            </p>
          </div>
          <button
            type="button"
            onClick={() => void runDiagnosis(stage)}
            disabled={isWorking}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-bold text-white shadow-sm transition-colors hover:bg-indigo-500 disabled:opacity-50"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', isWorking && 'animate-spin')} />
            重新诊断
          </button>
        </div>
      </div>
    );
  }

  const handleIssueClick = (issue: Finding) => {
    setSelectedObject(issue);
    const targetId = issue.metadata?.target_id || findingTargetIds(issue)[0];
    if (targetId) {
      setHighlightTarget(targetId);
    }
  };

  const handleIssueRepair = async (issue: Finding) => {
    const slotId = await executeFindingIssueResolution(issue.findingId);
    if (slotId) {
      await expandSlot(slotId);
    }
  };

  const handleIgnoreIssue = async (issue: Finding) => {
    await updateIssueAttributes(issue.findingId, { status: 'ignored' });
  };

  const hasHighRisk = stageIssues.some((issue) => issue.severity === 'blocking');

  return (
    <div
      className={cn(
        'rounded-2xl border border-l-4 bg-white p-5 shadow-sm space-y-4',
        hasHighRisk ? 'border-rose-100 border-l-rose-500' : 'border-amber-100 border-l-amber-500',
      )}
    >
      {/* 1. Next Action (Next suggestion) */}
      {nextAction && (() => {
        const presentation = getNextSuggestionPresentation(nextAction);
        return (
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between bg-slate-50/50 p-3.5 rounded-xl border border-slate-100">
            <div className="min-w-0 space-y-1.5">
              <span className="inline-flex items-center gap-1 rounded bg-indigo-50 px-2 py-0.5 text-[10px] font-black text-indigo-700 border border-indigo-100">
                <Cpu className="w-3 h-3" />
                下一步建议
              </span>
              <h4 className="text-xs font-black text-slate-800">{nextAction.title}</h4>
              <p className="text-xs font-medium leading-relaxed text-slate-500">
                {nextAction.description}
              </p>
            </div>

            <div className="flex shrink-0 items-center gap-2 self-end md:self-center">
              <button
                type="button"
                onClick={() => void startFindingSuggestion(nextAction, { navigate })}
                disabled={isWorking}
                className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-black text-white hover:bg-indigo-500 shadow-sm transition-all disabled:opacity-50 active:scale-95"
              >
                {presentation.icon === 'generate' && <Sparkles className="h-3.5 w-3.5" />}
                {presentation.icon === 'navigate' && <ArrowRight className="h-3.5 w-3.5" />}
                {presentation.icon === 'open' && <LocateFixed className="h-3.5 w-3.5" />}
                {presentation.icon === 'wait' && <Cpu className="h-3.5 w-3.5 animate-pulse" />}
                {presentation.icon === 'retry' && <RefreshCw className="h-3.5 w-3.5" />}
                <span>{presentation.label}</span>
              </button>
            </div>
          </div>
        );
      })()}

      {/* 2. Issues list */}
      {stageIssues.length > 0 && (
        <div className={cn(nextAction && 'border-t border-slate-100 pt-3.5')}>
          <button
            type="button"
            onClick={() => setIssuesExpanded((v) => !v)}
            className="flex w-full items-center justify-between gap-3 text-left hover:opacity-85 transition-opacity"
          >
            <div className="min-w-0">
              <div className="text-xs font-black text-slate-800 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 bg-rose-500 rounded-full animate-ping" />
                <span>仍有 {stageIssues.length} 个待处理问题</span>
              </div>
              {!issuesExpanded && (
                <div className="truncate text-[11px] text-slate-400 font-medium mt-0.5">
                  {stageIssues[0]?.title}
                </div>
              )}
            </div>
            {issuesExpanded ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
          </button>

          {issuesExpanded && (
            <div className="mt-3.5 space-y-3.5">
              {stageIssues.map((issue) => (
                <div
                  key={issue.findingId}
                  className="flex flex-col gap-3 rounded-xl border border-slate-200/60 bg-slate-50/50 p-4 md:flex-row md:items-start md:justify-between hover:border-slate-300 transition-colors"
                >
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={cn('rounded border px-1.5 py-0.5 text-[9px] font-black', severityClass[issue.severity])}>
                        {severityLabel[issue.severity] || issue.severity}
                      </span>
                      <span className="text-[10px] font-bold uppercase tracking-wide text-slate-400">
                        {issue.code}
                      </span>
                    </div>
                    <div className="text-xs font-black text-slate-800">{issue.title}</div>
                    <div className="line-clamp-2 text-xs leading-relaxed text-slate-500 font-medium">{issue.description}</div>
                  </div>

                  <div className="flex shrink-0 items-center gap-2 self-end md:self-start mt-2 md:mt-0">
                    <button
                      type="button"
                      onClick={() => handleIssueClick(issue)}
                      className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
                    >
                      <LocateFixed className="h-3.5 w-3.5" />
                      <span>定位</span>
                    </button>
                    {(() => {
                      const cap = getFindingCapability(issue);
                      return (
                        <button
                          type="button"
                          onClick={() => void handleIssueRepair(issue)}
                          disabled={isWorking || !cap.enabled}
                          className="inline-flex items-center gap-1 rounded-xl bg-slate-900 px-3.5 py-2 text-xs font-bold text-white shadow-sm hover:bg-slate-800 transition-colors disabled:opacity-50"
                        >
                          <Cpu className="h-3.5 w-3.5" />
                          <span>{cap.actionLabel}</span>
                        </button>
                      );
                    })()}
                    <button
                      type="button"
                      onClick={() => void handleIgnoreIssue(issue)}
                      disabled={isWorking}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-400 hover:text-slate-600 shadow-sm transition-colors disabled:opacity-50"
                      title="忽略"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 3. Health hints list */}
      {stageHealthHints.length > 0 && (
        <div className="border-t border-slate-100 pt-3.5">
          <button
            type="button"
            onClick={() => setHealthExpanded((v) => !v)}
            className="flex w-full items-center justify-between gap-3 text-left hover:opacity-85 transition-opacity"
          >
            <div className="min-w-0">
              <div className="text-xs font-black text-slate-700 flex items-center gap-1.5">
                <Heart className="w-4 h-4 text-emerald-500 shrink-0" />
                <span>空间健康：{stageHealthHints.length} 条可优化建议</span>
              </div>
            </div>
            {healthExpanded ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
          </button>

          {healthExpanded && (
            <div className="mt-3.5 space-y-3.5">
              {stageHealthHints.map((hint) => (
                <div
                  key={hint.findingId}
                  className="flex flex-col gap-3 rounded-xl border border-slate-200/60 bg-emerald-50/10 p-4 md:flex-row md:items-start md:justify-between hover:border-slate-300 transition-colors"
                >
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded border border-emerald-100 bg-emerald-50 text-emerald-700 px-1.5 py-0.5 text-[9px] font-black">
                        健康建议
                      </span>
                      <span className="text-[10px] font-bold uppercase tracking-wide text-slate-400">
                        {hint.code}
                      </span>
                    </div>
                    <div className="text-xs font-black text-slate-800">{hint.title}</div>
                    <div className="line-clamp-2 text-xs leading-relaxed text-slate-500 font-medium">{hint.description}</div>
                  </div>

                  <div className="flex shrink-0 items-center gap-2 self-end md:self-start mt-2 md:mt-0">
                    <button
                      type="button"
                      onClick={() => handleIssueClick(hint)}
                      className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
                    >
                      <LocateFixed className="h-3.5 w-3.5" />
                      <span>定位</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleIgnoreIssue(hint)}
                      disabled={isWorking}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-400 hover:text-slate-600 shadow-sm transition-colors disabled:opacity-50"
                      title="忽略"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
