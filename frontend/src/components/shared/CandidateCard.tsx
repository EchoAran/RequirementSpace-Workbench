import React from 'react';
import { Choice } from '@/types';
import { Sparkles, ArrowRight, Zap, CheckCircle2, AlertTriangle, Undo2 } from 'lucide-react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';

export interface CandidateCardProps {
  candidate: Choice;
  onAccept: (c: Choice) => void;
  onRewrite: (c: Choice) => void;
  onReject: (c: Choice) => void;
}

export const CandidateCard: React.FC<CandidateCardProps> = ({ candidate, onAccept, onRewrite, onReject }) => {
  const ir = useWorkspaceStore(state => state.ir);

  const nodeCount = candidate.proposedNodeIds?.length || 0;
  const linkCount = candidate.proposedLinkIds?.length || 0;
  const impact = candidate.impactPreview;

  return (
    <div className="candidate-card bg-blue-50 border border-blue-200 rounded-2xl p-4 relative overflow-hidden flex flex-col justify-between h-full hover:shadow-md transition-shadow">
      <div className="absolute top-0 right-0 px-2 py-1 bg-blue-500 text-white text-[10px] font-bold tracking-wider">AI 候选方案</div>
      
      <div>
        <div className="mb-2 pr-12 bg-blue-50">
          <h4 className="font-bold text-blue-900 text-sm leading-tight">
            {candidate.title}
          </h4>
        </div>
        
        <div className="space-y-3">
          <div className="rounded-lg bg-white/60 p-2.5 text-xs text-blue-800 border border-blue-100 shadow-sm leading-relaxed">
            <span className="font-bold text-blue-900">生成理由：</span>{candidate.rationale}
          </div>
          
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <div className="flex items-start gap-1 p-1.5 rounded bg-white">
               <Zap className="w-3.5 h-3.5 text-amber-500 shrink-0" />
               <div className="flex flex-col">
                 <span className="text-slate-400 font-bold">变更范围</span>
                 <span className="text-slate-700">调整 {nodeCount} 个节点, {linkCount} 条关联</span>
               </div>
            </div>
            
            {impact?.resolvedIssues && impact.resolvedIssues.length > 0 && (
              <div className="flex items-start gap-1 p-1.5 rounded bg-white">
                 <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                 <div className="flex flex-col">
                   <span className="text-slate-400 font-bold">解决问题</span>
                   <span className="text-emerald-700 line-clamp-1">修复 {impact.resolvedIssues.length} 项风险</span>
                 </div>
              </div>
            )}

            {impact?.newIssues && impact.newIssues.length > 0 && (
              <div className="flex items-start gap-1 p-1.5 rounded bg-rose-50 border border-rose-100">
                 <AlertTriangle className="w-3.5 h-3.5 text-rose-500 shrink-0" />
                 <div className="flex flex-col">
                   <span className="text-rose-400 font-bold">引入风险</span>
                   <span className="text-rose-700 font-semibold line-clamp-1">{impact.newIssues.length} 个新诊断项</span>
                 </div>
              </div>
            )}
            
            <div className="flex items-start gap-1 p-1.5 rounded bg-white">
               <Undo2 className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
               <div className="flex flex-col">
                 <span className="text-slate-400 font-bold">可逆性</span>
                 <span className="text-indigo-700 font-semibold">支持随时撤销</span>
               </div>
            </div>
          </div>
          
          {impact && (
            <div className="flex flex-wrap gap-1 mt-2">
              <span className="text-[10px] text-slate-400 mr-1 mt-0.5">影响覆盖:</span>
              {impact.affectedObjects && impact.affectedObjects.map(objId => {
                const objName = ir?.nodes[objId]?.title || '业务数据';
                return (
                  <span key={objId} className="rounded border border-blue-200 bg-white px-1.5 py-0.5 text-[10px] text-blue-700 font-bold line-clamp-1 max-w-[80px]">
                    数据:{objName}
                  </span>
                );
              })}
              {impact.affectedFlows && impact.affectedFlows.map(objId => {
                const objName = ir?.nodes[objId]?.title || '审批流程';
                return (
                  <span key={objId} className="rounded border border-blue-200 bg-white px-1.5 py-0.5 text-[10px] text-blue-700 font-bold line-clamp-1 max-w-[80px]">
                    流程:{objName}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 pt-4 mt-auto">
        <button 
          onClick={() => onAccept(candidate)}
          className="flex-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-[11px] font-bold rounded-lg transition-colors shadow-sm"
        >
          查看 / 采纳
        </button>
        <button 
          onClick={() => onRewrite(candidate)}
          className="px-4 py-1.5 bg-white text-blue-600 hover:bg-blue-50 text-[11px] font-bold rounded-lg border border-blue-200 transition-colors shadow-sm"
        >
          改写
        </button>
        <button 
          onClick={() => onReject(candidate)}
          className="px-3 py-1.5 text-slate-500 hover:text-slate-700 hover:bg-slate-100/80 text-[11px] font-medium rounded-lg transition-colors"
        >
          暂无视
        </button>
      </div>
    </div>
  );
}
