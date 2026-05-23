import { NodeStatus } from "@/core/schema";
import { StatusBadge } from "./StatusBadge";
import { ObjectLinkChips } from "./ObjectLinkChips";

export interface FlowStepCardProps {
  name: string;
  type: string;
  actor: string;
  status: NodeStatus;
  inputs?: string[];
  outputs?: string[];
  rules?: string[];
  stateChanges?: string[];
  relatedPages?: string[];
  relatedIssueCount?: number;
  relatedChoiceCount?: number;
  nextSteps?: string[];
  exceptionSteps?: string[];
  slots?: { id: string; title: string; choiceCount: number; status?: string }[];
  onClick?: () => void;
  onSlotClick?: (slotId: string) => void;
  active?: boolean;
}

export function FlowStepCard({ name, type, actor, status, inputs, outputs, rules, stateChanges, relatedPages, relatedIssueCount, relatedChoiceCount, nextSteps, exceptionSteps, slots, onClick, onSlotClick, active }: FlowStepCardProps) {
  return (
    <div 
      onClick={onClick}
      className={`border rounded-xl p-4 bg-white transition-all cursor-pointer ${
        active ? 'border-sky-500 ring-1 ring-sky-500 shadow-md' : 'border-slate-200 hover:border-slate-300 shadow-sm hover:shadow'
      }`}
    >
      <div className="flex justify-between items-start mb-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded font-medium">{type}</span>
            <span className="text-xs bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded font-medium flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-slate-400"></span>{actor}</span>
          </div>
          <h4 className="font-semibold text-slate-900">{name}</h4>
        </div>
        <StatusBadge status={status} />
      </div>

      <div className="space-y-2 mt-3 text-sm">
        {inputs && inputs.length > 0 && (
          <div className="flex gap-2 items-start">
            <span className="text-slate-400 text-xs mt-0.5 w-10 flex-shrink-0">输入</span>
            <span className="text-slate-700">{inputs.join(", ")}</span>
          </div>
        )}
        {outputs && outputs.length > 0 && (
          <div className="flex gap-2 items-start">
            <span className="text-slate-400 text-xs mt-0.5 w-10 flex-shrink-0">输出</span>
            <span className="text-slate-700">{outputs.join(", ")}</span>
          </div>
        )}
        {rules && rules.length > 0 && (
          <div className="flex gap-2 items-start">
            <span className="text-amber-500 text-xs mt-0.5 w-10 flex-shrink-0 font-medium">触发规则</span>
            <span className="text-amber-800 bg-amber-50 rounded px-1 -mx-1">{rules.join(", ")}</span>
          </div>
        )}
        {stateChanges && stateChanges.length > 0 && (
          <div className="flex gap-2 items-start">
            <span className="text-indigo-500 text-xs mt-0.5 w-10 flex-shrink-0 font-medium">状态</span>
            <span className="text-indigo-800 bg-indigo-50 rounded px-1 -mx-1">{stateChanges.join(", ")}</span>
          </div>
        )}
      </div>

      {slots && slots.length > 0 && (
        <div className="mt-3 space-y-2">
          {slots.map(s => (
            <div 
              key={s.id} 
              className="bg-purple-50/50 border border-purple-100 rounded-lg p-2 text-xs hover:border-purple-300 transition-colors"
              onClick={(e) => { e.stopPropagation(); onSlotClick?.(s.id); }}
            >
              <div className="flex justify-between items-center mb-1">
                <span className="font-bold text-purple-700 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-500"></span>
                  槽位：{s.title}
                </span>
                <span className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-bold">
                  {(s as any).status === 'filled' ? '已填补' : (s as any).status === 'deferred' ? '已暂缓' : '待决策'}
                </span>
              </div>
              <div className="text-purple-600/80 pl-2.5">
                {s.choiceCount > 0 ? `${s.choiceCount} 个 Choice` : (s as any).status === 'empty' ? '点击展开 Slot' : '生成中...'}
              </div>
            </div>
          ))}
        </div>
      )}

      {(relatedIssueCount || relatedChoiceCount) ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {(relatedIssueCount || 0) > 0 && (
            <span className="rounded-full bg-rose-50 px-2 py-1 text-[11px] font-semibold text-rose-700">
              {relatedIssueCount} 个关联 Issue
            </span>
          )}
          {(relatedChoiceCount || 0) > 0 && (
            <span className="rounded-full bg-blue-50 px-2 py-1 text-[11px] font-semibold text-blue-700">
              {relatedChoiceCount} 个关联 Choice
            </span>
          )}
        </div>
      ) : null}

      {relatedPages && relatedPages.length > 0 && (
        <div className="mt-3 pt-3 border-t border-slate-100">
           <ObjectLinkChips objects={relatedPages.map(p => ({ id: p, name: p, type: '页面' }))} />
        </div>
      )}

      {(nextSteps?.length || exceptionSteps?.length) ? (
        <div className="mt-3 pt-3 border-t border-slate-100 space-y-1">
          {nextSteps && nextSteps.length > 0 && (
            <div className="text-[11px] text-slate-500 flex items-center gap-1.5">
              <span className="text-slate-400 font-medium w-10 flex-shrink-0">下一步</span>
              <span className="font-medium text-slate-700">{nextSteps.join("、")}</span>
            </div>
          )}
          {exceptionSteps && exceptionSteps.length > 0 && (
            <div className="text-[11px] text-rose-500 flex items-center gap-1.5">
              <span className="text-rose-400 font-medium w-10 flex-shrink-0">异常分支</span>
              <span className="font-medium text-rose-700">{exceptionSteps.join("、")}</span>
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}
