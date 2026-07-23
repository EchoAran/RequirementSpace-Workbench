import { useTranslation } from 'react-i18next';
import { CheckCircle2, Circle } from "lucide-react";

interface Option {
  label: string;
  checked: boolean;
  type?: 'blocking' | 'info';
}

export function ReadinessChecklist({ title, items }: { title: string; items: Option[] }) {
  const { t } = useTranslation();
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
      <h4 className="font-semibold text-sm text-slate-800 mb-3">{title}</h4>
      <div className="space-y-2.5">
        {items.map((it, idx) => (
          <div key={idx} className="flex items-start gap-2.5 text-sm">
            {it.checked ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0" />
            ) : (
              <Circle className="w-5 h-5 text-slate-300 flex-shrink-0" />
            )}
            <span className={it.checked ? "text-slate-600" : "text-slate-800 font-medium"}>
              {it.label}
              {!it.checked && it.type === 'blocking' && (
                <span className="ml-2 text-[10px] bg-red-100 text-red-600 px-1.5 py-0.5 rounded font-semibold align-middle">{t('gateCheck.blockingBadge')}</span>
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}