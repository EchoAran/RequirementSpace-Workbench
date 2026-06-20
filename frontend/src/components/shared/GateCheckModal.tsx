import { useState } from 'react';
import { useWorkspaceStore, getFindingCapability } from '@/store/useWorkspaceStore';
import { AlertTriangle, Cpu, Loader2, X, ArrowRight } from 'lucide-react';
import { Finding } from '@/core/schema';

/**
 * 根据 capability kind 返回区分化错误提示文案。
 */
function getErrorMessageByCapability(kind: string, fallbackMsg: string): string {
  switch (kind) {
    case 'ai_repair':
      return 'AI 修复失败，请稍后重试或手动处理。';
    case 'generation_draft':
      return '草稿生成失败，请稍后重试。';
    case 'open_panel':
      return '无法定位处理位置，请手动查找对应步骤。';
    case 'manual_action':
      return '无法打开处理建议，请手动处理。';
    default:
      return fallbackMsg;
  }
}

export default function GateCheckModal() {
  const activeGateCheck = useWorkspaceStore((s) => s.activeGateCheck);
  const executeGateFindingAction = useWorkspaceStore((s) => s.executeGateFindingAction);
  const snoozeGateFinding = useWorkspaceStore((s) => s.snoozeGateFinding);

  const [runningFindingId, setRunningFindingId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!activeGateCheck) return null;

  const { action, findings, onPass, onCancel } = activeGateCheck;

  const getActionLabel = (act: string) => {
    switch (act) {
      case 'enter_how':
        return '进入”怎么运作 (How)”阶段';
      case 'enter_scope':
        return '进入”范围与交付 (Scope)”阶段';
      case 'generate_preview':
        return '生成方案预览';
      case 'export':
        return '文档导出';
      case 'save_checkpoint':
        return '保存版本检查点';
      default:
        return '执行该操作';
    }
  };

  const handleResolveFinding = async (finding: Finding) => {
    setRunningFindingId(finding.findingId);
    setErrorMessage(null);
    try {
      await executeGateFindingAction(finding);

      const store = useWorkspaceStore.getState();
      if (store.pendingGenerationConflict) {
        return; // Keep modal open for conflict resolution
      }
      if (store.activeChoiceGroup || store.activeDraft) {
        return; // Keep modal open to show prompt
      }
      onCancel();
    } catch (err: any) {
      console.error('Gate finding resolution failed:', finding.code, err);
      const cap = getFindingCapability(finding);
      // 优先使用 capability 区分的产品文案，err.message 作为技术附注
      const capMsg = getErrorMessageByCapability(cap.kind, err.message || '自动处理失败，请稍后重试。');
      setErrorMessage(capMsg);
    } finally {
      setRunningFindingId(null);
    }
  };

  const handleCancel = () => {
    findings.forEach((finding) => {
      snoozeGateFinding(action, finding);
    });
    onCancel();
  };

  const handleContinue = () => {
    findings.forEach((finding) => {
      snoozeGateFinding(action, finding);
    });
    onPass();
  };

  const activeChoiceGroup = useWorkspaceStore((s) => s.activeChoiceGroup);
  const activeDraft = useWorkspaceStore((s) => s.activeDraft);
  const pendingGenerationConflict = useWorkspaceStore((s) => s.pendingGenerationConflict);

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white/90 backdrop-blur-md rounded-3xl border border-slate-200/80 shadow-2xl max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-rose-50 text-rose-500 rounded-lg">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-800 tracking-tight">模型就绪度检查未通过</h2>
              <p className="text-[10.5px] text-slate-400 font-medium mt-0.5">
                在{getActionLabel(action)}前，需要补齐或确认以下关键模型依赖
              </p>
            </div>
          </div>
          <button 
            onClick={onCancel}
            className="text-slate-400 hover:text-slate-600 p-1.5 hover:bg-slate-100 rounded-full transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Dynamic Alerts */}
        {errorMessage && (
          <div className="mx-6 mt-4 p-3 bg-rose-50 text-rose-700 text-xs rounded-xl border border-rose-200 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {(activeChoiceGroup || activeDraft) && (
          <div className="mx-6 mt-4 p-3 bg-indigo-50 text-indigo-700 text-xs rounded-xl border border-indigo-200 flex items-center gap-2">
            <Cpu className="w-4 h-4 shrink-0 animate-pulse" />
            <span>AI 已生成草稿或候选方案。请先采纳候选方案或确认草稿，再重新进入阶段。</span>
          </div>
        )}

        {pendingGenerationConflict && (
          <div className="mx-6 mt-4 p-3 bg-amber-50 text-amber-700 text-xs rounded-xl border border-amber-200 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 animate-bounce" />
            <span>检测到生成冲突，请处理冲突后再试。</span>
          </div>
        )}

        {/* Findings List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {findings.map((finding) => {
            const cap = getFindingCapability(finding);
            const hasProcessorAction = cap.enabled;
            const isRunning = runningFindingId === finding.findingId;

            return (
              <div
                key={finding.findingId}
                className="bg-white border border-slate-200/60 rounded-2xl p-4 shadow-sm hover:shadow-md transition-shadow flex flex-col md:flex-row md:items-start justify-between gap-4"
              >
                <div className="space-y-1.5 max-w-md">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded font-bold border border-slate-200">
                      {finding.code}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 bg-rose-50 text-rose-600 rounded font-bold border border-rose-100">
                      阻塞
                    </span>
                  </div>
                  <h3 className="text-xs font-black text-slate-800">{finding.title}</h3>
                  <p className="text-xs text-slate-500 leading-relaxed font-medium">{finding.description}</p>
                </div>

                <div className="shrink-0 flex items-center">
                  {hasProcessorAction ? (
                    <button
                      disabled={runningFindingId !== null}
                      onClick={() => handleResolveFinding(finding)}
                      className="w-full md:w-auto flex items-center justify-center gap-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 disabled:opacity-50 text-xs px-3.5 py-2 rounded-xl border border-indigo-100 font-bold transition-all shadow-sm active:scale-95"
                    >
                      {isRunning ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Cpu className="w-3.5 h-3.5" />
                      )}
                      <span>{cap.actionLabel}</span>
                    </button>
                  ) : (
                    <span className="text-[10px] text-slate-400 font-semibold italic bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100">
                      请返回对应步骤手动修补
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-slate-50/50 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-3">
          <button
            onClick={handleCancel}
            className="w-full sm:w-auto text-xs px-5 py-2.5 rounded-xl border border-slate-200 hover:bg-slate-100 text-slate-600 font-bold transition-colors shadow-sm"
          >
            暂不处理 (Cancel)
          </button>
          
          <button
            onClick={handleContinue}
            className="w-full sm:w-auto flex items-center justify-center gap-1.5 text-xs px-5 py-2.5 bg-slate-800 hover:bg-slate-900 text-white rounded-xl font-bold transition-colors shadow-md active:scale-95"
          >
            <span>继续进入 (Continue anyway)</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

      </div>
    </div>
  );
}
