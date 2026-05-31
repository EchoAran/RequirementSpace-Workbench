import React from 'react';
import { X } from 'lucide-react';

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
            <div>
              <h3 className="text-base font-black text-slate-900 tracking-wide">确认进入下一个阶段</h3>
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
        <div className="p-6 pb-10 overflow-y-auto space-y-6">
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
                推荐
              </div>
              <div className="space-y-1.5 flex-1 pr-12">
                <h4 className="font-extrabold text-slate-900 text-xs tracking-wide">
                  启动 AI智能诊断
                </h4>
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
              <div className="space-y-1.5 flex-1 pr-4">
                <h4 className="font-extrabold text-slate-900 text-xs tracking-wide flex items-center gap-1.5">
                  直接进入下一阶段
                </h4>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
