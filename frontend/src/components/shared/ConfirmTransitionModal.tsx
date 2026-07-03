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

  const currentStageName = stage === 'what' ? '要做什么 (What)' : '怎么运作 (How)';
  const nextStageName = stage === 'what' ? '怎么运作 (How)' : '范围决策 (Scope)';

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
      setLocalError(err?.message || '诊断过程出错，请稍后重试。');
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
              {status === 'idle' && '确认进入下一个阶段'}
              {status === 'diagnosing' && '正在运行 AI 智能诊断'}
              {status === 'passed' && 'AI 智能诊断通过'}
              {status === 'blocked' && '建议补齐设计漏洞'}
              {status === 'failed' && '智能诊断异常'}
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
                  当前 <b>{currentStageName}</b> 阶段的基础硬性建模规则已全部满足！
                </p>
                <p className="text-[11px] text-slate-500 leading-relaxed bg-slate-50 p-3 rounded-2xl border border-slate-100/60 font-medium">
                  为了保障系统需求模型的深度与严谨度，我们强烈建议您先运行一次 <b>AI 智能诊断</b>，以自动发掘、定位并补齐隐藏在业务逻辑背后的隐性数据与角色缺口。您也可以选择直接进入下一阶段。
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
                    推荐
                  </span>
                  <span className="font-extrabold text-slate-900 text-xs tracking-wide flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-indigo-600" />
                    启动 AI 智能诊断
                  </span>
                  <span className="text-[10px] text-slate-500 font-medium">
                    通过大模型扫描，查找不一致、遗漏场景及未定义的业务实体。
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
                    直接进入下一阶段
                  </span>
                  <span className="text-[10px] text-slate-500 font-medium">
                    跳过智能诊断，直接解锁并在 {nextStageName} 继续工作。
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
                  大模型正在全力诊断中...
                </h4>
                <p className="text-[11px] text-slate-500 max-w-sm">
                  AI 正在分析本阶段需求规则，可能需要 5-10 秒，请稍后，此过程不会关闭弹窗。
                </p>
              </div>
            </div>
          )}

          {status === 'passed' && (
            <div className="space-y-6 py-4">
              <div className="flex items-center gap-4 bg-emerald-50 border border-emerald-200/80 p-5 rounded-2xl">
                <CheckCircle2 className="w-8 h-8 text-emerald-600 shrink-0" />
                <div className="text-left">
                  <h4 className="font-extrabold text-slate-900 text-xs">诊断完成：未发现明显设计漏洞！</h4>
                  <p className="text-[10px] text-slate-500 mt-1 font-medium">
                    AI 没有在此阶段的规则中发现未定义的角色、遗漏的用例流程，设计状态十分健康。
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={onForceUnlock}
                  className="flex-1 rounded-xl bg-indigo-600 py-3 text-xs font-black text-white hover:bg-indigo-500 shadow-md transition-all active:scale-95"
                >
                  确认进入 {nextStageName}
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-xl border border-slate-200 px-5 py-3 text-xs font-bold text-slate-600 hover:bg-slate-50 transition-all"
                >
                  取消
                </button>
              </div>
            </div>
          )}

          {status === 'blocked' && (
            <div className="space-y-6 py-2">
              <div className="flex items-start gap-4 bg-amber-50 border border-amber-200/80 p-5 rounded-2xl">
                <AlertTriangle className="w-6 h-6 text-amber-600 shrink-0 mt-0.5" />
                <div className="text-left space-y-2">
                  <h4 className="font-extrabold text-slate-900 text-xs">AI 建议补充以下重要设计漏洞</h4>
                  <div className="p-3 bg-white rounded-xl border border-amber-100 space-y-1">
                    <div className="font-bold text-slate-800 text-[11px]">
                      {nextSuggestion?.title}
                    </div>
                    <div className="text-slate-500 text-[10px] leading-relaxed">
                      {nextSuggestion?.description}
                    </div>
                  </div>
                  <p className="text-[10px] text-slate-500 font-medium">
                    我们强烈建议您前往处理并修复该漏洞，以保持需求的高质量建模。
                  </p>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-3">
                <button
                  type="button"
                  onClick={handleResolveSuggestion}
                  className="flex-1 rounded-xl bg-indigo-600 py-3 text-xs font-black text-white hover:bg-indigo-500 shadow-md transition-all active:scale-95"
                >
                  去处理建议
                </button>
                <button
                  type="button"
                  onClick={onForceUnlock}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-xs font-bold text-slate-600 hover:bg-slate-50 hover:text-slate-800 transition-all font-mono"
                >
                  忽略并强制进入下一阶段
                </button>
              </div>
            </div>
          )}

          {status === 'failed' && (
            <div className="space-y-6 py-4">
              <div className="flex items-center gap-4 bg-rose-50 border border-rose-200/80 p-5 rounded-2xl">
                <XCircle className="w-8 h-8 text-rose-600 shrink-0" />
                <div className="text-left">
                  <h4 className="font-extrabold text-slate-900 text-xs">AI 智能诊断异常</h4>
                  <p className="text-[10px] text-rose-500 mt-1 font-medium">
                    {localError || '网络或后台计算异常，无法完成深度诊断。'}
                  </p>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-3">
                <button
                  type="button"
                  onClick={handleDiagnose}
                  className="flex-1 rounded-xl bg-indigo-600 py-3 text-xs font-black text-white hover:bg-indigo-500 shadow-md transition-all active:scale-95"
                >
                  重新诊断
                </button>
                <button
                  type="button"
                  onClick={onForceUnlock}
                  className="flex-1 rounded-xl border border-slate-200 bg-white py-3 text-xs font-bold text-slate-600 hover:bg-slate-50 transition-all active:scale-95 text-center"
                >
                  跳过诊断并直接进入下一阶段
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
