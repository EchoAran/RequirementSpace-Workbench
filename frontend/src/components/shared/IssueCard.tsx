import React from 'react';
import { Finding } from '@/core/schema';
import { cn } from '@/lib/utils';
import { getFindingCapability, useWorkspaceStore } from '@/store/useWorkspaceStore';
import { findingSeverityLabel, findingTargetIds } from '@/core/findingPresentation';

export interface IssueCardProps {
  issue: Finding;
  onClick: (issue: Finding) => void;
  onCreateSlot: (issue: Finding) => void;
  onIgnore: (issue: Finding) => void;
}

const severityText = {
  high: '高风险',
  medium: '需处理',
  low: '提示',
};

export const IssueCard: React.FC<IssueCardProps> = ({ issue, onClick, onCreateSlot, onIgnore }) => {
  const ir = useWorkspaceStore((state) => state.ir);
  const severity = findingSeverityLabel(issue);
  const relatedNodeTitles = findingTargetIds(issue)
    .map((nodeId) => ir?.nodes[nodeId]?.title)
    .filter((title): title is string => Boolean(title));

  const { actionLabel, enabled } = getFindingCapability(issue);

  return (
    <div
      className={cn(
        'flex flex-col rounded-xl shadow-sm border border-slate-200 transition-all bg-white group',
        severity === 'high'
          ? 'border-l-4 border-l-rose-500 hover:ring-2 hover:ring-rose-500/20'
          : severity === 'medium'
            ? 'border-l-4 border-l-amber-400 hover:ring-2 hover:ring-amber-500/20'
            : 'border-l-4 border-l-slate-400 hover:ring-2 hover:ring-slate-500/20',
      )}
    >
      <div className="p-4 cursor-pointer flex-1" onClick={() => onClick(issue)}>
        <div className="flex justify-between items-start mb-2">
          <h4 className="font-bold text-sm text-slate-900 leading-tight">{issue.title}</h4>
          <span
            className={cn(
              'px-1.5 py-0.5 text-[10px] font-black rounded shrink-0 ml-2',
              severity === 'high'
                ? 'bg-rose-50 text-rose-600'
                : severity === 'medium'
                  ? 'bg-amber-50 text-amber-600'
                  : 'bg-slate-50 text-slate-600',
            )}
          >
            {severityText[severity]}
          </span>
        </div>
        <p className="text-xs text-slate-500 leading-relaxed mb-3 line-clamp-2">{issue.description}</p>

        {relatedNodeTitles.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {relatedNodeTitles.map((title) => (
              <span
                key={title}
                className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600 font-medium"
              >
                {title}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 px-4 py-3 border-t border-slate-100 bg-slate-50/50 rounded-b-xl">
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (enabled) onCreateSlot(issue);
          }}
          disabled={!enabled}
          className={cn(
            'flex-1 py-1.5 text-xs font-bold rounded-md transition-colors shadow-sm',
            enabled
              ? 'bg-slate-900 text-white hover:bg-slate-800'
              : 'bg-slate-200 text-slate-400 cursor-not-allowed',
          )}
        >
          {actionLabel}
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onIgnore(issue);
          }}
          className="flex-1 py-1.5 text-xs font-bold border border-slate-200 text-slate-600 rounded-md bg-white hover:bg-slate-50 transition-colors shadow-sm"
        >
          忽略
        </button>
      </div>
    </div>
  );
};
