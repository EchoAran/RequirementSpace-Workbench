import { AlertTriangle, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import type { PathProjectionItem } from '@/core/schema';
import { cn } from '@/lib/utils';

type Props = {
  paths: PathProjectionItem[];
  selectedPathId: string | null;
  loading: boolean;
  error: string | null;
  onSelect: (pathId: string | null) => void;
  onRetry: () => void;
};

export function PathProjectionSelector({
  paths,
  selectedPathId,
  loading,
  error,
  onSelect,
  onRetry,
}: Props) {
  const { t } = useTranslation();
  const selectedPath = paths.find((path) => path.pathId === selectedPathId) || null;

  return (
    <div className="hidden md:flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-2.5 py-1 text-xs shadow-2xs">
      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{t('how.pathProjection.focus')}:</span>
      {loading ? (
        <span data-testid="path-projection-loading" className="flex items-center gap-1 text-slate-500 text-xs py-0.5">
          <Loader2 className="h-3 w-3 animate-spin text-indigo-600" />
          <span>{t('how.canvas.pathLoading')}</span>
        </span>
      ) : error ? (
        <div data-testid="path-projection-error" className="flex items-center gap-1.5 text-rose-600 text-xs py-0.5">
          <AlertTriangle className="h-3.5 w-3.5 text-rose-500" />
          <span className="truncate max-w-[120px]" title={error}>{t('how.canvas.pathError')}</span>
          <button type="button" data-testid="path-projection-retry-button" onClick={onRetry} className="ml-1 text-[11px] font-bold text-indigo-600 hover:text-indigo-800 underline cursor-pointer">{t('how.canvas.retry')}</button>
        </div>
      ) : paths.length > 0 ? (
        <>
          <select value={selectedPathId || ''} onChange={(event) => onSelect(event.target.value || null)} data-testid="path-projection-select" className="bg-transparent text-xs font-bold text-slate-700 focus:outline-none cursor-pointer">
            <option value="">{t('how.pathProjection.allPaths')} ({paths.length})</option>
            {paths.map((path) => (
              <option key={path.pathId} value={path.pathId}>
                {path.isMain ? '★ ' : ''}{path.name} {path.status !== 'valid' ? `(${path.status})` : ''}
              </option>
            ))}
          </select>
          {selectedPath && (
            <span className={cn('rounded px-1.5 py-0.5 text-[9px] font-black uppercase', selectedPath.status === 'valid' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-amber-50 text-amber-700 border border-amber-200')}>
              {selectedPath.status}
            </span>
          )}
        </>
      ) : (
        <span className="text-slate-400 text-[11px]">{t('how.canvas.noPaths')}</span>
      )}
    </div>
  );
}
