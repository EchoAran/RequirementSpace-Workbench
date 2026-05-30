import React from 'react';
import { Sparkles, X, Zap } from 'lucide-react';

interface ConfirmTransitionModalProps {
  isOpen: boolean;
  onClose: () => void;
  stage: 'what' | 'how';
  onAIDiagnose: () => void;
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
  if (!isOpen) return null;

  const currentStageName = stage === 'what' ? '要做什么 (What)' : '怎么运作 (How)';
  const nextStageName = stage === 'what' ? '怎么运作 (How)' : '范围决策 (Scope)';

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-md animate-in fade-in duration-300"
      onClick={onClose}
    >
      <div 
        className="w-full max-w-xl bg-white/95 backdrop-blur-xl border border-slate-200/80 rounded-3xl shadow-2xl flex flex-col overflow-hidden max-h-[90vh] animate-in zoom-in-95 duration-300"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-6 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-indigo-50/50 to-sky-50/50">
          <div className="flex items-center gap-3">
            <span className="p-2 bg-indigo-100/80 text-indigo-700 rounded-2xl shrink-0">
              <Sparkles className="w-5 h-5 text-indigo-600 animate-pulse" />
            </span>
            <div>
              <h3 className="text-base font-black text-slate-900 tracking-wide">申请解锁进入下一阶段</h3>
              <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mt-0.5 font-mono">
                Transition Gate Confirmation
              </p>
            </div>
          </div>
          <button 
            onClick={onClose} 
            disabled={isWorking}
            className="w-8 h-8 rounded-full border border-slate-200 bg-white hover:bg-slate-50 text-slate-400 hover:text-slate-600 flex items-center justify-center shadow-sm transition-all"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6">
          <div className="space-y-2 text-left">
            <p className="text-xs text-slate-600 leading-relaxed font-semibold">
              恭喜！当前 <b>{currentStageName}</b> 阶段的基础硬性建模规则已全部满足！
            </p>
            <p className="text-[11px] text-slate-500 leading-relaxed bg-slate-50 p-3 rounded-2xl border border-slate-100/60 font-medium">
              为了保障系统需求模型的深度与严谨度，我们强烈建议您先运行一次 <b>AI 智能诊断</b>，以自动发掘、定位并补齐隐藏在业务逻辑背后的隐性数据与角色缺口。您也可以选择直接进入下一阶段。
            </p>
          </div>

          <div className="space-y-4">
            {/* Option A (AI Diagnose) */}
            <div 
              onClick={!isWorking ? onAIDiagnose : undefined}
              className={`p-5 rounded-2xl border-2 transition-all cursor-pointer flex flex-col md:flex-row items-start gap-4 relative select-none ${
                isWorking 
                  ? 'opacity-60 cursor-not-allowed border-slate-100 bg-slate-50/50' 
                  : 'border-indigo-500 bg-indigo-50/20 hover:bg-indigo-50/30 hover:shadow-md'
              }`}
            >
              <div className="absolute top-3 right-4 bg-indigo-600 text-white font-extrabold text-[9px] px-2 py-0.5 rounded-full uppercase tracking-wider shadow-sm select-none font-mono">
                💡 强烈推荐
              </div>
              <div className="p-2.5 bg-indigo-100 text-indigo-700 rounded-xl shrink-0">
                <Sparkles className="w-5 h-5" />
              </div>
              <div className="space-y-1.5 flex-1 pr-12">
                <h4 className="font-extrabold text-slate-900 text-xs tracking-wide">
                  启动 AI 智能诊断并补齐 (推荐)
                </h4>
                <p className="text-[10px] text-slate-500 leading-relaxed font-medium">
                  AI 诊断感知器将自动针对系统参与者、功能树及场景标准进行全景推演，补充潜在的关联与逻辑槽位，让需求完美收敛。
                </p>
              </div>
            </div>

            {/* Option B (Force Unlock) */}
            <div 
              onClick={!isWorking ? onForceUnlock : undefined}
              className={`p-5 rounded-2xl border transition-all cursor-pointer flex flex-col md:flex-row items-start gap-4 relative select-none ${
                isWorking 
                  ? 'opacity-60 cursor-not-allowed border-slate-100 bg-slate-50/50' 
                  : 'border-slate-200 bg-white hover:border-amber-300 hover:bg-slate-50/50 hover:shadow-sm'
              }`}
            >
              <div className="p-2.5 bg-amber-50 text-amber-600 border border-amber-100 rounded-xl shrink-0">
                <Zap className="w-5 h-5" />
              </div>
              <div className="space-y-1.5 flex-1 pr-4">
                <h4 className="font-extrabold text-slate-900 text-xs tracking-wide flex items-center gap-1.5">
                  直接进入下一阶段
                </h4>
                <p className="text-[10px] text-slate-500 leading-relaxed font-medium">
                  绕过 AI 辅助智能审查环节，直接永久解锁当前阶段并跳转推进至 <b>{nextStageName}</b> 规划设计。
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 pt-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/50 shrink-0">
          <button
            onClick={onClose}
            disabled={isWorking}
            className="px-4 py-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 text-xs font-bold rounded-xl shadow-sm transition-all disabled:opacity-50"
          >
            暂不进入，留在当前
          </button>
          
          <button
            onClick={!isWorking ? onAIDiagnose : undefined}
            disabled={isWorking}
            className="flex items-center gap-1.5 px-4.5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-black rounded-xl shadow-md transition-all active:scale-[0.98] disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5" />
            运行 AI 智能诊断
          </button>
        </div>
      </div>
    </div>
  );
}
