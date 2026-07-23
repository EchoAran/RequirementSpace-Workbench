import { useTranslation } from 'react-i18next';
import { AlertTriangle, RefreshCw, X } from 'lucide-react';

interface GenerationConflictDialogProps {
  isOpen: boolean;
  generationLabel: string;
  isWorking?: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export function GenerationConflictDialog({
  isOpen,
  generationLabel,
  isWorking = false,
  onClose,
  onConfirm,
}: GenerationConflictDialogProps) {
  const { t } = useTranslation();
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[85] flex items-center justify-center bg-slate-900/55 p-4 backdrop-blur-sm"
      onClick={isWorking ? undefined : onClose}
    >
      <div
        className="w-full max-w-lg overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 bg-gradient-to-r from-amber-50/80 to-rose-50/50 p-6">
          <div className="flex items-start gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-100 text-amber-700 shadow-sm">
              <AlertTriangle className="h-5 w-5" />
            </span>
            <div className="space-y-1">
              <h3 className="text-base font-black text-slate-900">{t('conflictDialog.modalTitle')}</h3>
              <p className="text-xs leading-relaxed text-slate-500">
                {t('conflictDialog.modalDesc', { label: generationLabel })}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isWorking}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-400 transition-colors hover:bg-slate-50 hover:text-slate-600 disabled:opacity-50"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 p-6">
          <div className="rounded-2xl border border-amber-100 bg-amber-50/70 p-4 text-sm leading-relaxed text-amber-800">
            {t('conflictDialog.warningTip', { label: generationLabel })}
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 text-xs leading-relaxed text-slate-500">
            {t('conflictDialog.suggestTip')}
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/60 p-6">
          <button
            type="button"
            onClick={onClose}
            disabled={isWorking}
            className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-50"
          >
            {t('conflictDialog.keepBtn')}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isWorking}
            className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-black text-white shadow-sm transition-colors hover:bg-indigo-700 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isWorking ? 'animate-spin' : ''}`} />
            {t('conflictDialog.discardBtn')}
          </button>
        </div>
      </div>
    </div>
  );
}