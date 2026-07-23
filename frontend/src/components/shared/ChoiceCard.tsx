import { useTranslation } from 'react-i18next';
import React from 'react';
import { Choice } from '@/core/schema';
import { AlertTriangle, CheckCircle2, Undo2, Zap } from 'lucide-react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { getChoicePresentation } from '@/core/choicePresentation';

export interface ChoiceCardProps {
  choice: Choice;
  onAccept: (choice: Choice) => void;
  onPreview?: (choice: Choice) => void;
  onRewrite: (choice: Choice) => void;
  onReject: (choice: Choice) => void;
}

export const ChoiceCard: React.FC<ChoiceCardProps> = ({ choice, onAccept, onPreview, onRewrite, onReject }) => {
  const { t, i18n } = useTranslation();
  const ir = useWorkspaceStore((state) => state.ir);

  const nodeCount = choice.patch?.addNodes?.length || 0;
  const linkCount = choice.patch?.addLinks?.length || 0;
  const impact = choice.impactPreview;
  const isPreviewEnabled = typeof onPreview === 'function';
  const presentation = getChoicePresentation(choice, t, i18n);

  const handlePreview = () => {
    if (onPreview) {
      onPreview(choice);
    }
  };

  const handleCardKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (!isPreviewEnabled) return;
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handlePreview();
    }
  };

  return (
    <div
      role={isPreviewEnabled ? 'button' : undefined}
      tabIndex={isPreviewEnabled ? 0 : undefined}
      onClick={isPreviewEnabled ? handlePreview : undefined}
      onKeyDown={handleCardKeyDown}
      className={`bg-blue-50 border border-blue-200 rounded-2xl p-4 relative overflow-hidden flex flex-col justify-between h-full transition-[border-color,box-shadow] ${
        isPreviewEnabled
          ? 'cursor-pointer hover:border-blue-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-300 focus:ring-offset-2'
          : 'hover:shadow-md'
      }`}
    >
      <div className="absolute top-0 right-0 px-2 py-1 bg-blue-500 text-white text-[10px] font-bold tracking-wider">
        {t('choiceCard.badge')}
      </div>

      <div>
        <div className="mb-2 pr-12 bg-blue-50">
          <h4 className="font-bold text-blue-900 text-sm leading-tight">{presentation.title}</h4>
        </div>

        <div className="space-y-3">
          <div className="rounded-lg bg-white/60 p-2.5 text-xs text-blue-800 border border-blue-100 shadow-sm leading-relaxed">
            <span className="font-bold text-blue-900">{t('choiceCard.rationaleLabel')}</span>
            {presentation.rationale}
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="flex items-start gap-1 p-1.5 rounded bg-white">
              <Zap className="w-3.5 h-3.5 text-amber-500 shrink-0" />
              <div className="flex flex-col">
                <span className="text-slate-400 font-bold">{t('choiceCard.patchSummary')}</span>
                <span className="text-slate-700">
                  {t('choiceCard.patchDesc', { nodeCount, linkCount })}
                </span>
              </div>
            </div>

            {impact?.resolvedIssues && impact.resolvedIssues.length > 0 && (
              <div className="flex items-start gap-1 p-1.5 rounded bg-white">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                <div className="flex flex-col">
                  <span className="text-slate-400 font-bold">{t('choiceCard.resolvedIssues')}</span>
                  <span className="text-emerald-700 line-clamp-1">{t('choiceCard.resolvedIssuesDesc', { count: impact.resolvedIssues.length })}</span>
                </div>
              </div>
            )}

            {impact?.newIssues && impact.newIssues.length > 0 && (
              <div className="flex items-start gap-1 p-1.5 rounded bg-rose-50 border border-rose-100">
                <AlertTriangle className="w-3.5 h-3.5 text-rose-500 shrink-0" />
                <div className="flex flex-col">
                  <span className="text-rose-400 font-bold">{t('choiceCard.newIssues')}</span>
                  <span className="text-rose-700 font-semibold line-clamp-1">{t('choiceCard.newIssuesDesc', { count: impact.newIssues.length })}</span>
                </div>
              </div>
            )}

            <div className="flex items-start gap-1 p-1.5 rounded bg-white">
              <Undo2 className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
              <div className="flex flex-col">
                <span className="text-slate-400 font-bold">{t('choiceCard.reversibility')}</span>
                <span className="text-indigo-700 font-semibold">{t('choiceCard.reversibilityDesc')}</span>
              </div>
            </div>
          </div>

          {impact && (
            <div className="flex flex-wrap gap-1 mt-2">
              <span className="text-[10px] text-slate-400 mr-1 mt-0.5">{t('choiceCard.impactScope')}</span>
              {impact.affectedObjects.map((objectId) => (
                <span
                  key={objectId}
                  className="rounded border border-blue-200 bg-white px-1.5 py-0.5 text-[10px] text-blue-700 font-bold line-clamp-1 max-w-[80px]"
                >
                  {t('choiceCard.dataType', { title: ir?.nodes[objectId]?.title || objectId })}
                </span>
              ))}
              {impact.affectedFlows.map((flowId) => (
                <span
                  key={flowId}
                  className="rounded border border-blue-200 bg-white px-1.5 py-0.5 text-[10px] text-blue-700 font-bold line-clamp-1 max-w-[80px]"
                >
                  {t('choiceCard.flowType', { title: ir?.nodes[flowId]?.title || flowId })}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 pt-4 mt-auto">
        <button
          onClick={(event) => {
            event.stopPropagation();
            onAccept(choice);
          }}
          className="flex-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition-colors shadow-sm"
        >
          {t('choiceCard.acceptBtn')}
        </button>
        <button
          onClick={(event) => {
            event.stopPropagation();
            onRewrite(choice);
          }}
          className="px-4 py-1.5 bg-white text-blue-600 hover:bg-blue-50 text-xs font-bold rounded-lg border border-blue-200 transition-colors shadow-sm"
        >
          {t('choiceCard.rewriteBtn')}
        </button>
        <button
          onClick={(event) => {
            event.stopPropagation();
            onReject(choice);
          }}
          className="px-3 py-1.5 text-slate-500 hover:text-slate-700 hover:bg-slate-100/80 text-xs font-medium rounded-lg transition-colors"
        >
          {t('choiceCard.rejectBtn')}
        </button>
      </div>
    </div>
  );
};
