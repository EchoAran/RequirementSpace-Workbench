import { useTranslation } from 'react-i18next';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useWorkspaceStore, getFindingCapability } from '@/store/useWorkspaceStore';
import { ChevronDown, ChevronUp, RefreshCw, X } from 'lucide-react';
import { Finding } from '@/core/schema';
import { cn } from '@/lib/utils';
import { getNextSuggestionPresentation } from '@/core/nextSuggestionPresentation';
import { findingTargetIds } from '@/core/findingPresentation';
import { getFindingText } from '@/core/findingText';
import { getStageCheckMessage } from '@/core/stageProgressText';

interface StageGuidanceBannerProps {
  stage: 'what' | 'how' | 'scope';
}

export function StageGuidanceBanner({ stage }: StageGuidanceBannerProps) {
  const { t } = useTranslation();
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
  const backendFindingsLoaded = useWorkspaceStore((s) => s.backendFindingsLoaded);
  const requestStageTransition = useWorkspaceStore((s) => s.requestStageTransition);

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
  const stageNextAction = (findingsByView.next_action || []).find((f) => f.stage === stage);
  const stageIssues = (findingsByView.issues || []).filter((f) => f.stage === stage);
  const stageHealthHints = (findingsByView.health || []).filter((f) => f.stage === stage);
  const progressAction = stageProgressItem?.nextAction;
  const transitionAction = progressAction?.transitionAction || progressAction?.transition_action;
  const hasBlockingIssue = stageProgressItem?.statusCode === 'blocked'
    || (stageProgressItem?.blockingFindings || []).length > 0
    || stageIssues.some((issue) => issue.severity === 'blocking' || issue.blockingScope !== 'none');
  const canAdvance = stageProgressItem?.statusCode === 'ready_to_advance'
    && progressAction?.kind === 'stage_transition'
    && Boolean(transitionAction)
    && !hasBlockingIssue;
  const suggestionActionKind = stageNextAction?.metadata?.action?.kind;
  const isTransitionSuggestion = suggestionActionKind === 'stage_transition'
    || ['ENTER_HOW', 'ENTER_SCOPE', 'ENTER_PREVIEW'].includes(stageNextAction?.code || '');
  const nextAction = (
    (stageAlreadyAdvanced && stageNextAction?.metadata?.source_type !== 'perception_slot')
    || isTransitionSuggestion
  ) ? null : stageNextAction;
  const failedChecks = stageProgressItem?.failedChecks || [];
  const showStageStateNotice = !canAdvance
    && !nextAction
    && (failedChecks.length > 0 || ['blocked', 'analysis_running', 'unlocked_not_started', 'in_progress', 'locked'].includes(stageProgressItem?.statusCode));

  const totalActionable = (canAdvance ? 1 : 0) + (nextAction ? 1 : 0) + stageIssues.length + stageHealthHints.length + (showStageStateNotice ? 1 : 0);
  const scenarios = (ir.features || []).flatMap((feature) => feature.scenarios || []);
  const canDiagnose = stage === 'what'
    ? (ir.actors || []).length > 0 && (ir.features || []).length > 0
      && scenarios.length > 0 && scenarios.some((scenario) => (scenario.acceptanceCriteria || []).length > 0)
    : stage === 'how' && (ir.domainRules || []).length > 0
      && (ir.flows || []).length > 0 && (ir.businessObjects || []).length > 0;
  const hasPerceptionSuggestion = ir.perceptionSlot?.stage === stage
    || (findingsByView.next_action || []).some((finding) => finding.stage === stage
      && finding.metadata?.source_type === 'perception_slot' && finding.metadata?.status === 'ready');
  const diagnosisButton = canDiagnose ? (
    <button
      type="button"
      onClick={() => void runDiagnosis(stage)}
      disabled={isWorking}
      className="shrink-0 self-start rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-50 sm:self-auto"
    >
      {t(hasPerceptionSuggestion ? 'stageGuidance.reDiagnoseBtn' : 'stageGuidance.diagnoseBtn')}
    </button>
  ) : null;

  if ((!backendFindingsLoaded || !stageProgressItem) && totalActionable === 0) {
    return (
      <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs leading-relaxed text-slate-500">
          {t('stageGuidance.loading')}
        </p>
        {diagnosisButton}
      </div>
    );
  }

  if (totalActionable === 0) {
    return (
      <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs leading-relaxed text-slate-600">
          {t('stageGuidance.noIssues')}
        </p>
        {diagnosisButton}
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

  return (
    <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      {canAdvance && (
        <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-slate-50/60 p-4 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0 space-y-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">
              {t('stageGuidance.stageTransition')}
            </span>
            <h4 className="text-xs font-semibold text-slate-800">{t('stageGuidance.readyToAdvanceTitle')}</h4>
            <p className="text-xs leading-relaxed text-slate-500">
              {t('stageGuidance.readyToAdvanceDescription')}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void requestStageTransition(transitionAction, { navigate })}
            disabled={isWorking}
            className="shrink-0 self-end rounded-lg bg-slate-900 px-3.5 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-slate-700 disabled:opacity-50 md:self-center"
          >
            {t(`suggestion.${transitionAction === 'enter_how' ? 'enterHow' : transitionAction === 'enter_scope' ? 'enterScope' : 'enterPreview'}`)}
          </button>
        </div>
      )}

      {showStageStateNotice && (
        <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
          <div className="text-xs font-semibold text-slate-800">{t('stageGuidance.incompleteTitle')}</div>
          <div className="mt-1 text-xs leading-relaxed text-amber-700">
            {getStageCheckMessage(failedChecks[0], t) || t('stageGuidance.incompleteDescription')}
          </div>
        </div>
      )}

      {/* 1. Next Action (Next suggestion) */}
      {nextAction && (() => {
        const presentation = getNextSuggestionPresentation(nextAction);
        return (
          <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-slate-50/60 p-4 md:flex-row md:items-center md:justify-between">
            <div className="min-w-0 space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                {t('stageGuidance.nextActionSuggestion')}
              </span>
              <h4 className="text-xs font-semibold text-slate-800">{getFindingText(nextAction, t).title}</h4>
              <p className="text-xs leading-relaxed text-slate-500">
                {getFindingText(nextAction, t).description}
              </p>
            </div>

            {presentation.icon !== 'retry' && <div className="shrink-0 self-end md:self-center">
              <button
                type="button"
                onClick={() => void startFindingSuggestion(nextAction, { navigate })}
                disabled={isWorking}
                className="rounded-lg bg-slate-900 px-3.5 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-slate-700 disabled:opacity-50"
              >
                {presentation.label}
              </button>
            </div>}
          </div>
        );
      })()}

      {/* 2. Issues list */}
      {stageIssues.length > 0 && (
        <div className={cn((canAdvance || nextAction || showStageStateNotice) && 'border-t border-slate-100 pt-3.5')}>
          <button
            type="button"
            onClick={() => setIssuesExpanded((v) => !v)}
            className="flex w-full items-center justify-between gap-3 text-left transition-opacity hover:opacity-80"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  {t('stageGuidance.issuesLabel')}
                </span>
                <span className="rounded-md bg-rose-50 px-1.5 py-0.5 text-[10px] font-bold tabular-nums text-rose-600">
                  {stageIssues.length}
                </span>
              </div>
              {!issuesExpanded && stageIssues[0] && (
                <div className="mt-1 truncate text-xs text-slate-500">
                  {getFindingText(stageIssues[0], t).description}
                </div>
              )}
            </div>
            {issuesExpanded ? <ChevronUp className="h-4 w-4 shrink-0 text-slate-400" /> : <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />}
          </button>

          {issuesExpanded && (
            <div className="mt-3 space-y-2">
              {stageIssues.map((issue) => {
                const cap = getFindingCapability(issue);
                const text = getFindingText(issue, t);
                const hasTarget = Boolean(issue.metadata?.target_id) || findingTargetIds(issue).length > 0;
                return (
                  <div
                    key={issue.findingId}
                    onClick={hasTarget ? () => handleIssueClick(issue) : undefined}
                    className={cn(
                      'flex flex-col gap-2.5 rounded-xl border border-slate-200 bg-white p-3.5 transition-colors hover:border-slate-300 hover:bg-slate-50/60 md:flex-row md:items-start md:justify-between',
                      hasTarget && 'cursor-pointer',
                    )}
                  >
                    <div className="min-w-0 space-y-1">
                      <div className="text-xs font-semibold text-slate-800">{text.title}</div>
                      <div className="line-clamp-2 text-xs leading-relaxed text-slate-500">{text.description}</div>
                    </div>

                    <div className="flex shrink-0 items-center gap-1 self-end md:self-start">
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); void handleIssueRepair(issue); }}
                        disabled={isWorking || !cap.enabled}
                        className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-slate-700 disabled:opacity-50"
                      >
                        {cap.actionLabel}
                      </button>
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); void handleIgnoreIssue(issue); }}
                        disabled={isWorking}
                        className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-300 transition-colors hover:bg-slate-100 hover:text-slate-500 disabled:opacity-50"
                        title={t('stageGuidance.ignoreTooltip')}
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* 3. Health hints list */}
      {stageHealthHints.length > 0 && (
        <div className={cn((canAdvance || nextAction || showStageStateNotice || stageIssues.length > 0) && 'border-t border-slate-100 pt-3.5')}>
          <div className="flex w-full items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => setHealthExpanded((v) => !v)}
              className="flex min-w-0 flex-1 items-center justify-between gap-3 text-left transition-opacity hover:opacity-80"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    {t('stageGuidance.healthLabel')}
                  </span>
                  <span className="rounded-md bg-emerald-50 px-1.5 py-0.5 text-[10px] font-bold tabular-nums text-emerald-600">
                    {stageHealthHints.length}
                  </span>
                </div>
                {!healthExpanded && stageHealthHints[0] && (
                  <div className="mt-1 truncate text-xs text-slate-500">
                    {getFindingText(stageHealthHints[0], t).description}
                  </div>
                )}
              </div>
              {healthExpanded ? <ChevronUp className="h-4 w-4 shrink-0 text-slate-400" /> : <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />}
            </button>
            {canDiagnose && (
              <button
                type="button"
                onClick={() => void runDiagnosis(stage)}
                disabled={isWorking}
                title={t(hasPerceptionSuggestion ? 'stageGuidance.reDiagnoseBtn' : 'stageGuidance.diagnoseBtn')}
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-indigo-600 disabled:opacity-50"
              >
                <RefreshCw className={cn('h-3.5 w-3.5', isDiagnosing && 'animate-spin')} />
              </button>
            )}
          </div>

          {healthExpanded && (
            <div className="mt-3 space-y-2">
              {stageHealthHints.map((hint) => {
                const text = getFindingText(hint, t);
                const hasTarget = Boolean(hint.metadata?.target_id) || findingTargetIds(hint).length > 0;
                return (
                  <div
                    key={hint.findingId}
                    onClick={hasTarget ? () => handleIssueClick(hint) : undefined}
                    className={cn(
                      'flex flex-col gap-2.5 rounded-xl border border-slate-200 bg-white p-3.5 transition-colors hover:border-slate-300 hover:bg-slate-50/60 md:flex-row md:items-start md:justify-between',
                      hasTarget && 'cursor-pointer',
                    )}
                  >
                    <div className="min-w-0 space-y-1">
                      <div className="text-xs font-semibold text-slate-800">{text.title}</div>
                      <div className="line-clamp-2 text-xs leading-relaxed text-slate-500">{text.description}</div>
                    </div>

                    <div className="flex shrink-0 items-center gap-1 self-end md:self-start">
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); void handleIgnoreIssue(hint); }}
                        disabled={isWorking}
                        className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-300 transition-colors hover:bg-slate-100 hover:text-slate-500 disabled:opacity-50"
                        title={t('stageGuidance.ignoreTooltip')}
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
