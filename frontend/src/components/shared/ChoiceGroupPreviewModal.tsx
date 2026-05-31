import { useEffect, useState } from 'react';
import {
  Check,
  RefreshCw,
  Sparkles,
  X,
  AlertTriangle,
  Loader2,
  Trash2,
} from 'lucide-react';
import { ChoicePreviewRenderer } from './ChoicePreviewRenderer';

interface ChoiceGroupPreviewModalProps {
  /** The choice group from any generation type (project_creation, actor, scenario, …) */
  group: any | null;
  isWorking: boolean;
  isGeneratingChoices: boolean;
  generationProgress: {
    totalCandidates: number;
    completedCandidates: number;
    candidateStatuses: Record<number, 'pending' | 'generating' | 'complete' | 'failed'>;
  } | null;
  initialChoiceId?: string | number | null;
  onAccept: (choiceId: string) => void | Promise<void>;
  onDiscard: () => void | Promise<void>;
  onDefer: () => void;
  onRegenerate?: (choiceId?: string) => void | Promise<void>;
}

export function ChoiceGroupPreviewModal({
  group,
  isWorking,
  isGeneratingChoices,
  generationProgress,
  initialChoiceId,
  onAccept,
  onDiscard,
  onDefer,
  onRegenerate,
}: ChoiceGroupPreviewModalProps) {
  const [activeChoiceIndex, setActiveChoiceIndex] = useState(0);

  useEffect(() => {
    const successfulChoices = ((group?.choices || []) as any[]).filter(choice => choice.status === 'candidate');
    if (successfulChoices.length === 0) {
      setActiveChoiceIndex(0);
      return;
    }

    if (initialChoiceId === undefined || initialChoiceId === null) {
      setActiveChoiceIndex(0);
      return;
    }

    const nextIndex = successfulChoices.findIndex(choice => String(choice.id) === String(initialChoiceId));
    setActiveChoiceIndex(nextIndex >= 0 ? nextIndex : 0);
  }, [group, initialChoiceId]);

  /* ── Progress overlay during generation (show even without group) ── */
  if (isGeneratingChoices) {
    const total = generationProgress?.totalCandidates || 2;
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
        <div className="bg-white rounded-3xl shadow-2xl border border-slate-200 w-full max-w-2xl mx-4 p-8">
          <div className="text-center">
            <Loader2 className="w-10 h-10 text-indigo-600 animate-spin mx-auto mb-4" />
            <h3 className="text-lg font-bold text-slate-800 mb-2">
              {group?.generationType === 'actor' ? '正在生成参与者方案' :
               group?.generationType === 'scenario' ? '正在生成场景方案' :
               group?.generationType === 'feature' ? '正在生成功能树方案' :
               group?.generationType === 'flow' ? '正在生成流程方案' :
               group?.generationType === 'scope' ? '正在生成范围分析方案' :
               group?.generationType === 'acceptance_criteria' ? '正在生成验收标准方案' :
               '正在生成项目草稿方案'}
            </h3>
            <div className="space-y-2 mt-6">
              {Array.from({ length: total }).map((_, i) => {
                const status = generationProgress?.candidateStatuses?.[i] || (generationProgress ? 'pending' : 'generating');
                const label = ['方案 A', '方案 B', '方案 C', '方案 D', '方案 E'][i] || `方案 ${i + 1}`;
                return (
                  <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-slate-50">
                    {status === 'complete' ? (
                      <Check className="w-5 h-5 text-emerald-500 shrink-0" />
                    ) : status === 'failed' ? (
                      <AlertTriangle className="w-5 h-5 text-red-500 shrink-0" />
                    ) : status === 'generating' ? (
                      <Loader2 className="w-5 h-5 text-indigo-500 animate-spin shrink-0" />
                    ) : (
                      <div className="w-5 h-5 rounded-full border-2 border-slate-300 shrink-0" />
                    )}
                    <span className="text-sm text-slate-700">
                      {label}
                      {status === 'complete' ? ' — 已就绪' :
                       status === 'failed' ? ' — 生成失败' :
                       status === 'generating' ? ' — 生成中...' : ''}
                    </span>
                  </div>
                );
              })}
            </div>
            <p className="text-xs text-slate-400 mt-4">
              {generationProgress?.completedCandidates || 0}/{generationProgress?.totalCandidates || total} 完成
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (!group) return null;

  const choices = (group.choices || []) as any[];
  const successfulChoices = choices.filter(c => c.status === 'candidate');
  const failedChoices = choices.filter(c => c.status === 'failed');

  const activeChoice = successfulChoices[activeChoiceIndex] || successfulChoices[0];
  const totalSuccessful = successfulChoices.length;
  const totalFailed = failedChoices.length;

  /* ── All-failed state ────────────────────────────────── */
  if (successfulChoices.length === 0) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
        <div className="bg-white rounded-3xl shadow-2xl border border-slate-200 w-full max-w-lg mx-4 p-8 text-center">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h3 className="text-lg font-bold text-slate-800 mb-2">所有候选方案生成失败</h3>
          <p className="text-sm text-slate-500 mb-6">
            {group.statusDetail?.error_summary || '生成过程出现错误，请重试。'}
          </p>
          {failedChoices.length > 0 && (
            <div className="text-left space-y-2 mb-6">
              {failedChoices.map((fc: any) => (
                <div key={fc.id} className="p-3 rounded-xl bg-rose-50 border border-rose-100 text-xs text-rose-600">
                  <strong>{fc.title}</strong>: {fc.error?.message || '未知错误'}
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-3 justify-center">
            {onRegenerate && (
              <button onClick={() => onRegenerate()} className="inline-flex items-center gap-2 h-11 px-6 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700 transition-colors">
                <RefreshCw className="w-4 h-4" />
                重新生成
              </button>
            )}
            <button onClick={onDiscard} className="inline-flex items-center gap-2 h-11 px-6 rounded-xl border border-slate-200 text-slate-700 text-sm font-bold hover:bg-slate-50 transition-colors">
              <X className="w-4 h-4" />
              关闭
            </button>
          </div>
        </div>
      </div>
    );
  }

  const hasPartialFailure = totalFailed > 0;
  const draftType = activeChoice?.draftType || group.generationType || '';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="bg-white rounded-3xl shadow-2xl border border-slate-200 w-full max-w-2xl mx-4 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-slate-100 shrink-0">
          <div className="flex items-center justify-between mb-1">
            <h3 className="text-lg font-bold text-slate-800">
              {draftType === 'actor' ? '选择参与者方案' :
               draftType === 'scenario' ? '选择场景方案' :
               draftType === 'feature' ? '选择功能树方案' :
               draftType === 'flow' ? '选择流程与对象方案' :
               draftType === 'scope' ? '选择范围分析方案' :
               draftType === 'acceptance_criteria' ? '选择验收标准方案' :
               '选择项目草稿方案'}
            </h3>
            <button onClick={onDefer} className="text-slate-400 hover:text-slate-600 transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>
          {hasPartialFailure && (
            <div className="mt-2 p-3 bg-amber-50 border border-amber-100 rounded-xl text-xs text-amber-700 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              {totalSuccessful} 个方案已生成，{totalFailed} 个方案生成失败
            </div>
          )}
          {group.statusDetail?.comparison_summary && (
            <p className="text-xs text-slate-500 mt-2 leading-relaxed">
              对比：{group.statusDetail.comparison_summary}
            </p>
          )}
        </div>

        {/* Candidate tabs */}
        {totalSuccessful > 1 && (
          <div className="flex gap-2 px-6 pt-4 pb-2 overflow-x-auto shrink-0">
            {successfulChoices.map((c: any, i: number) => (
              <button
                key={c.id}
                onClick={() => setActiveChoiceIndex(i)}
                className={`shrink-0 px-4 py-2 rounded-xl text-xs font-bold transition-colors ${
                  i === activeChoiceIndex
                    ? 'bg-indigo-100 text-indigo-700 border border-indigo-200'
                    : 'bg-slate-50 text-slate-600 border border-slate-200 hover:bg-slate-100'
                }`}
              >
                {c.title}
              </button>
            ))}
          </div>
        )}

        {/* Candidate preview via ChoicePreviewRenderer */}
        {activeChoice && (
          <div className="flex-1 overflow-y-auto p-6">
            <ChoicePreviewRenderer
              draftType={draftType}
              preview={activeChoice.preview}
              payload={activeChoice.payload}
              comparisonSummary={activeChoice.comparisonSummary}
            />
          </div>
        )}

        {/* Failed choices */}
        {failedChoices.length > 0 && (
          <div className="px-6 pb-2 shrink-0">
            <details className="group">
              <summary className="text-xs text-slate-400 cursor-pointer hover:text-slate-600">
                {failedChoices.length} 个生成失败的方案（点击展开）
              </summary>
              <div className="mt-2 space-y-2">
                {failedChoices.map((fc: any) => (
                  <div key={fc.id} className="flex items-center justify-between p-2 rounded-lg bg-rose-50 border border-rose-100">
                    <div className="text-xs text-rose-600">
                      <strong>{fc.title}</strong>: {fc.error?.message || '未知错误'}
                    </div>
                    {onRegenerate && (
                      <button
                        onClick={() => onRegenerate(fc.id)}
                        className="text-xs text-indigo-600 hover:text-indigo-800 font-medium shrink-0 ml-2"
                      >
                        重试
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </details>
          </div>
        )}

        {/* Actions */}
        <div className="p-6 border-t border-slate-100 bg-slate-50/50 shrink-0">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex gap-2">
              <button
                onClick={onDefer}
                className="inline-flex items-center gap-1.5 h-10 px-4 rounded-xl border border-slate-200 bg-white text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
              >
                稍后处理
              </button>
              <button
                onClick={onDiscard}
                className="inline-flex items-center gap-1.5 h-10 px-4 rounded-xl border border-red-200 bg-white text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                丢弃全部
              </button>
            </div>
            <div className="flex gap-2">
              {onRegenerate && (
                <button
                  onClick={() => onRegenerate()}
                  disabled={isWorking}
                  className="inline-flex items-center gap-1.5 h-10 px-4 rounded-xl border border-slate-200 bg-white text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-50"
                >
                  <RefreshCw className="w-4 h-4" />
                  重新生成
                </button>
              )}
              {activeChoice && (
                <button
                  onClick={() => onAccept(activeChoice.id)}
                  disabled={isWorking}
                  className="inline-flex items-center gap-1.5 h-10 px-6 rounded-xl bg-indigo-600 text-sm font-bold text-white shadow-lg shadow-indigo-100 hover:bg-indigo-700 transition-colors disabled:opacity-50"
                >
                  <Sparkles className="w-4 h-4" />
                  采纳此方案
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
