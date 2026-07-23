import { useTranslation } from 'react-i18next';
import React from 'react';
import { X, Sparkles, CheckCircle2, AlertTriangle, XCircle, ArrowRight, Loader2 } from 'lucide-react';
import { useWorkspaceStore } from '../../store/useWorkspaceStore';

interface ConfirmTransitionModalProps {
  isOpen: boolean;
  onClose: () => void;
  stage: 'what' | 'how';
  onAIDiagnose: () => Promise<void>;
  onForceUnlock: () => void;
  isWorking?: boolean;
}

export function ConfirmTransitionModal({
  isOpen,
  onClose,
  stage,
  onAIDiagnose,
  onForceUnlock,
  isWorking = false,
}: ConfirmTransitionModalProps) {
  const { t } = useTranslation();
  const [status, setStatus] = React.useState<'idle' | 'diagnosing' | 'passed' | 'blocked' | 'failed'>('idle');
  const [localError, setLocalError] = React.useState<string | null>(null);

  const nextSuggestion = useWorkspaceStore((s) => s.nextSuggestions[stage]);
  const isStoreDiagnosing = useWorkspaceStore((s) => s.isDiagnosing);
  const startFindingSuggestion = useWorkspaceStore((s) => s.startFindingSuggestion);

  // Sync state with open/close
  React.useEffect(() => {
    if (isOpen) {
      setStatus('idle');
      setLocalError(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const currentStageName = stage === 'what' ? t('suggestion.whatName') : t('suggestion.howName');
  const nextStageName = stage === 'what' ? t('suggestion.howName') : t('suggestion.scopeName');

  const handleDiagnose = async () => {
    setStatus('diagnosing');
    setLocalError(null);
    try {
      await onAIDiagnose();
      
      // Fetch latest nextSuggestion from store getState
      const latestSug = useWorkspaceStore.getState().nextSuggestions[stage];
      // Diagnosis passed if: no suggestion, or suggestion action is stage_transition (ready to enter next stage)
      if (
        !latestSug ||
        latestSug.code === 'ENTER_HOW' ||
        latestSug.code === 'ENTER_SCOPE' ||
        latestSug.metadata?.action?.kind === 'stage_transition'
      ) {
        setStatus('passed');
      } else {
        setStatus('blocked');
      }
    } catch (err: any) {
      setLocalError(err?.message || t('suggestion.diagnoseErrorDefault'));
      setStatus('failed');
    }
  };

  const handleResolveSuggestion = async () => {
    if (nextSuggestion) {
      onClose(); // Close modal first to not lose context
      await startFindingSuggestion(nextSuggestion);
    }
  };

  const isAnyLoading = isWorking || isStoreDiagnosing || status === 'diagnosing';

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-md animate-in fade-in duration-300"
      onClick={!isAnyLoading ? onClose : undefined}
    >
      <div 
        className="w-full max-w-xl bg-white border border-slate-200/80 rounded-3xl shadow-2xl flex flex-col overflow-hidden max-h-[90vh] animate-in zoom-in-95 duration-300"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-6 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-indigo-50/50 to-sky-50/50">
          <div>
            <h3 className="text-base font-black text-slate-900 tracking-wide">
              {status === 'idle' && t('suggestion.confirmTransitionTitle')}
              {status === 'diagnosing' && t('suggestion.diagnosingTitle')}
              {status === 'passed' && t('suggestion.passedTitle')}
              {status === 'blocked' && t('suggestion.blockedTitle')}
              {status === 'failed' && t('suggestion.failedTitle')}
            </h3>
          </div>
          <button 
            onClick={onClose} 
            disabled={isAnyLoading}
            className="w-8 h-8 rounded-full border border-slate-200 bg-white hover:bg-slate-50 text-slate-400 hover:text-slate-600 flex items-center justify-center shadow-sm transition-all disabled:opacity-50"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6">
          {status === 'idle' && (
            <>
              <div className="space-y-2 text-left">
                <p className="text-xs text-slate-600 leading-relaxed font-semibold">
                  {t('suggestion.hardcodedRulesMet', { stage: currentStageName })}
                </p>
                <p className="text-[11px] text-slate-500 leading-relaxed bg-slate-50 p-3 rounded-2xl border border-slate-100/60 font-medium">
                  {t('suggestion.hardcodedRulesAdvise')}
                </p>
              </div>

              <div className="space-y-4">
                {/* Option A (AI Diagnose) */}
                <button
                  type="button"
                  onClick={handleDiagnose}
                  className="w-full p-5 rounded-2xl border-2 border-indigo-500 bg-indigo-50/20 hover:bg-indigo-50/30 hover:shadow-md transition-all text-left relative flex flex-col gap-1.5 active:scale-[0.99]"
                >
                  <span className="absolute top-3 right-4 bg-indigo-600 text-white font-extrabold text-[9px] px-2 py-0.5 rounded-full uppercase tracking-wider font-mono">
                    {t('suggestion.recommendedBadge')}
                  </span>
                  <span className="font-extrabold text-slate-900 text-xs tracking-wide flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-indigo-600" />
                    {t('suggestion.diagnoseBtn')}
                  </span>
                  <span className="text-[10px] text-slate-500 font-medium">
                    {t('suggestion.diagnoseDesc')}
                  </span>
                </button>

                {/* Option B (Force Unlock) */}
                <button
                  type="button"
                  onClick={onForceUnlock}
                  className="w-full p-5 rounded-2xl border border-slate-200 bg-white hover:border-amber-300 hover:bg-slate-50/50 hover:shadow-sm transition-all text-left flex flex-col gap-1.5 active:scale-[0.99]"
                >
                  <span className="font-extrabold text-slate-900 text-xs tracking-wide flex items-center gap-1.5">
                    <ArrowRight className="w-4 h-4 text-slate-500" />
                    {t('suggestion.forceUnlockBtn')}
                  </span>
                  <span className="text-[10px] text-slate-500 font-medium">
                    {t('suggestion.forceUnlockDesc', { stage: nextStageName })}
                  </span>
                </button>
              </div>
            </>
          )}

          {status === 'diagnosing' && (
            <div className="flex flex-col items-center py-12 space-y-4 text-center">
              <Loader2 className="w-10 h-10 text-indigo-600 animate-spin" />
              <div className="space-y-1">
                <h4 className="font-extrabold text-slate-900 text-sm tracking-wide">
                  {t('suggestion.diagnosingMessage')}
                </h4>
                <p className="text-[11px] text-slate-500 max-w-sm">
                  {t('suggestion.diagnosingDesc')}
                </p>
              </div>
            </div>
          )}

          {status === 'passed' && (
            <div className="space-y-6 py-4">
              <div className="flex items-center gap-4 bg-emerald-50 border border-emerald-200/80 p-5 rounded-2xl">
                <CheckCircle2 className="w-8 h-8 text-emerald-600 shrink-0" />
                <div className="text-left">
                  <h4 className="font-extrabold text-slate-900 text-xs">{t('suggestion.passedMessage')}</h4>
                  <p className="text-[10px] text-slate-500 mt-1 font-medium">
                    {t('suggestion.passedDesc')}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={onForceUnlock}
                  className="flex-1 rounded-xl bg-indigo-600 py-3 text-xs font-black text-white hover:bg-indigo-500 shadow-md transition-all active:scale-95"
                >
                  {t('suggestion.enterNextStage', { stage: nextStageName })}
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-xl border border-slate-200 px-5 py-3 text-xs font-bold text-slate-600 hover:bg-slate-50 transition-all"
                >
                  {t('suggestion.cancel')}
                </button>
              </div>
            </div>
          )}

          {status === 'blocked' && (
            <div className="space-y-6 py-2">
              <div className="flex items-start gap-4 bg-amber-50 border border-amber-200/80 p-5 rounded-2xl">
                <AlertTriangle className="w-6 h-6 text-amber-600 shrink-0 mt-0.5" />
                <div className="text-left space-y-2">
                  <h4 className="font-extrabold text-slate-900 text-xs">{t('suggestion.blockedMessage')}</h4>
                  <div className="p-3 bg-white rounded-xl border border-amber-100 space-y-1">
                    <div className="font-bold text-slate-800 text-[11px]">
                      {nextSuggestion?.title}
                    </div>
                    <div className="text-slate-500 text-[10px] leading-relaxed">
                      {nextSuggestion?.description}
                    </div>
                  </div>
                  <p className="text-[10px] text-slate-500 font-medium">
                    {t('suggestion.blockedDesc')}
                  </p>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-3">
                <button
                  type="button"
                  onClick={handleResolveSuggestion}
                  className="flex-1 rounded-xl bg-indigo-600 py-3 text-xs font-black text-white hover:bg-indigo-500 shadow-md transition-all active:scale-95"
                >
                  {t('suggestion.resolveBtn')}
                </button>
                <button
                  type="button"
                  onClick={onForceUnlock}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-xs font-bold text-slate-600 hover:bg-slate-50 hover:text-slate-800 transition-all font-mono"
                >
                  {t('suggestion.ignoreAndForce')}
                </button>
              </div>
            </div>
          )}

          {status === 'failed' && (
            <div className="space-y-6 py-4">
              <div className="flex items-center gap-4 bg-rose-50 border border-rose-200/80 p-5 rounded-2xl">
                <XCircle className="w-8 h-8 text-rose-600 shrink-0" />
                <div className="text-left">
                  <h4 className="font-extrabold text-slate-900 text-xs">{t('suggestion.failedMessage')}</h4>
                  <p className="text-[10px] text-rose-500 mt-1 font-medium">
                    {localError || t('suggestion.failedDesc')}
                  </p>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-3">
                <button
                  type="button"
                  onClick={handleDiagnose}
                  className="flex-1 rounded-xl bg-indigo-600 py-3 text-xs font-black text-white hover:bg-indigo-500 shadow-md transition-all active:scale-95"
                >
                  {t('suggestion.diagnoseRetry')}
                </button>
                <button
                  type="button"
                  onClick={onForceUnlock}
                  className="flex-1 rounded-xl border border-slate-200 bg-white py-3 text-xs font-bold text-slate-600 hover:bg-slate-50 transition-all active:scale-95 text-center"
                >
                  {t('suggestion.skipAndEnter')}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
