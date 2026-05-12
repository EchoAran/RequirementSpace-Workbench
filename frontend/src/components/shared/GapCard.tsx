import React from 'react';
import { Issue } from '@/types';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';

export interface GapCardProps {
  gap: Issue;
  onClick: (gap: Issue) => void;
  onGenerate: (gap: Issue) => void;
  onDefer: (gap: Issue) => void;
}

export const GapCard: React.FC<GapCardProps> = ({ gap, onClick, onGenerate, onDefer }) => {
  const ir = useWorkspaceStore(state => state.ir);
  
  return (
    <div 
      className={cn(
        "gap-card flex flex-col rounded-xl shadow-sm border border-slate-200 transition-all bg-white group",
        gap.severity === 'high' ? 'border-l-4 border-l-rose-500 hover:ring-2 hover:ring-rose-500/20' : 
        gap.severity === 'medium' ? 'border-l-4 border-l-amber-400 hover:ring-2 hover:ring-amber-500/20' :
        'border-l-4 border-l-slate-400 hover:ring-2 hover:ring-slate-500/20'
      )}
    >
      <div 
        className="p-4 cursor-pointer flex-1"
        onClick={() => onClick(gap)}
      >
        <div className="flex justify-between items-start mb-2">
          <h4 className="font-bold text-sm text-slate-900 leading-tight">
            {gap.title}
          </h4>
          <span className={`px-1.5 py-0.5 text-[10px] font-black rounded shrink-0 ml-2 ${
            gap.severity === 'high' ? 'bg-rose-50 text-rose-600' : 
            gap.severity === 'medium' ? 'bg-amber-50 text-amber-600' : 'bg-slate-50 text-slate-600'
          }`}>
            {gap.severity}严重度
          </span>
        </div>
        <p className="text-xs text-slate-500 leading-relaxed mb-3 line-clamp-2">{gap.description}</p>
        
        {gap.relatedNodeIds && gap.relatedNodeIds.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {gap.relatedNodeIds.map(objId => {
              const objName = ir?.nodes[objId]?.title || objId;
              return (
                <span key={objId} className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600 font-medium">
                  {objName}
                </span>
              );
            })}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 px-4 py-3 border-t border-slate-100 bg-slate-50/50 rounded-b-xl">
        <button 
          onClick={(e) => { e.stopPropagation(); onGenerate(gap); }}
          className="flex-1 py-1.5 text-[11px] font-bold bg-slate-900 text-white rounded-md hover:bg-slate-800 transition-colors shadow-sm"
        >
          生成建议候选
        </button>
        <button 
          onClick={(e) => { e.stopPropagation(); onDefer(gap); }}
          className="flex-1 py-1.5 text-[11px] font-bold border border-slate-200 text-slate-600 rounded-md bg-white hover:bg-slate-50 transition-colors shadow-sm"
        >
          暂缓
        </button>
      </div>
    </div>
  );
}
