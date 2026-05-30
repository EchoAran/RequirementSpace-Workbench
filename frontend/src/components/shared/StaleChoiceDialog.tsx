import { AlertTriangle, RefreshCw, Check } from 'lucide-react';

interface StaleChoiceDialogProps {
  isOpen: boolean;
  staleReason: string;
  onForceAccept: () => void | Promise<void>;
  onRegenerate: () => void | Promise<void>;
  onCancel: () => void;
}

/**
 * StaleChoiceDialog (UX-5)
 *
 * When a choice's context has changed (feature/actor deleted, etc.),
 * this dialog asks the user whether to force-accept or regenerate.
 */
export function StaleChoiceDialog({
  isOpen,
  staleReason,
  onForceAccept,
  onRegenerate,
  onCancel,
}: StaleChoiceDialogProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="bg-white rounded-3xl shadow-2xl border border-slate-200 w-full max-w-md mx-4 p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center shrink-0">
            <AlertTriangle className="w-5 h-5 text-amber-600" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-800">项目上下文已变化</h3>
            <p className="text-xs text-slate-500 mt-0.5">此候选可能不适用当前项目状态</p>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-amber-50 border border-amber-100 mb-6">
          <p className="text-sm text-amber-800 leading-relaxed">{staleReason}</p>
        </div>

        <div className="flex flex-col gap-2">
          <button
            onClick={onForceAccept}
            className="inline-flex items-center justify-center gap-2 h-11 rounded-xl bg-amber-600 text-white text-sm font-bold hover:bg-amber-700 transition-colors"
          >
            <Check className="w-4 h-4" />
            仍要采纳
          </button>
          <button
            onClick={onRegenerate}
            className="inline-flex items-center justify-center gap-2 h-11 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            取消并重新生成
          </button>
          <button
            onClick={onCancel}
            className="inline-flex items-center justify-center h-11 rounded-xl border border-slate-200 text-slate-600 text-sm font-medium hover:bg-slate-50 transition-colors"
          >
            稍后再说
          </button>
        </div>
      </div>
    </div>
  );
}
