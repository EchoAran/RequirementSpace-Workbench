import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, RefreshCw, Check } from 'lucide-react';

interface StaleChoiceDialogProps {
  isOpen: boolean;
  staleReason: string;
  onForceAccept: () => void | Promise<void>;
  onRegenerate: () => void | Promise<void>;
  onCancel: () => void;
}

export function StaleChoiceDialog({
  isOpen,
  staleReason,
  onForceAccept,
  onRegenerate,
  onCancel,
}: StaleChoiceDialogProps) {
  const { t } = useTranslation();
  if (!isOpen || typeof document === 'undefined') return null;

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl shadow-2xl border border-slate-200/80 w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="flex items-start gap-3.5 border-b border-slate-100 bg-gradient-to-r from-amber-50/80 to-rose-50/50 p-6">
          <div className="w-11 h-11 rounded-2xl bg-amber-100 text-amber-700 flex items-center justify-center shrink-0 shadow-sm">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div className="space-y-1 text-left">
            <h3 className="text-base font-black text-slate-900 tracking-tight">{t('panel.staleChoiceTitle')}</h3>
            <p className="text-xs text-slate-500 font-medium leading-relaxed">{t('panel.staleChoiceSubtitle')}</p>
          </div>
        </div>

        <div className="p-6 space-y-4">
          <div className="p-4 rounded-2xl bg-amber-50/70 border border-amber-100 text-left">
            <p className="text-xs text-amber-800 leading-relaxed font-medium">{staleReason}</p>
          </div>
        </div>

        <div className="flex flex-col gap-2.5 p-6 pt-0">
          <button
            type="button"
            onClick={onForceAccept}
            className="inline-flex items-center justify-center gap-2 py-2.5 rounded-xl bg-amber-600 text-white text-xs font-bold hover:bg-amber-700 shadow-sm active:scale-95 transition-all cursor-pointer"
          >
            <Check className="w-4 h-4" />
            <span>{t('panel.staleChoiceAdopt')}</span>
          </button>
          <button
            type="button"
            onClick={onRegenerate}
            className="inline-flex items-center justify-center gap-2 py-2.5 rounded-xl bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-700 shadow-sm active:scale-95 transition-all cursor-pointer"
          >
            <RefreshCw className="w-4 h-4" />
            <span>{t('panel.staleChoiceRegenerate')}</span>
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center justify-center py-2.5 rounded-xl border border-slate-200 bg-white text-slate-600 text-xs font-bold hover:bg-slate-50 transition-all cursor-pointer"
          >
            {t('panel.staleChoiceCancel')}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
