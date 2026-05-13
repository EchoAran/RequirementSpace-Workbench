import { useState } from 'react';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { FlowStepCard } from '@/components/shared/FlowStepCard';
import { GapCard } from '@/components/shared/GapCard';
import { 
  useWorkspaceStore, 
  selectFlowSteps, 
  selectIssues, 
  selectCandidates, 
  selectSelectedObject 
} from '@/store/useWorkspaceStore';

export function HowItWorks() {
  const { 
    highlightTarget,
    setSelectedObject, setHighlightTarget, generateCandidate, deferObject,
  } = useWorkspaceStore();
  
  const ir = useWorkspaceStore(state => state.ir);
  const flowSteps = useWorkspaceStore(selectFlowSteps);
  const gaps = useWorkspaceStore(selectIssues);
  const candidates = useWorkspaceStore(selectCandidates);
  const selectedObject = useWorkspaceStore(selectSelectedObject);

  const swimlanes = ['员工', '直属经理', '系统', 'HR / 外部系统'];
  const [showAllGaps, setShowAllGaps] = useState(false);
  
  const abnormalGaps = gaps.filter(g => g.category === 'flow_gap' || g.category === 'rule_gap');

  const getStepsBySwimlane = (lane: string) => {
    return flowSteps.filter(s => s.actor === lane || s.swimlane === lane);
  };

  const getStepNextSteps = (stepId: string) => {
    if (!ir) return [];
    return ir.links.filter(l => l.sourceId === stepId && l.type === 'precedes')
                   .map(l => ir.nodes[l.targetId]?.title).filter(Boolean) as string[];
  };

  const getStepExceptionSteps = (stepId: string) => {
    if (!ir) return [];
    return ir.links.filter(l => l.sourceId === stepId && l.type === 'branches_to')
                   .map(l => ir.nodes[l.targetId]?.title).filter(Boolean) as string[];
  };
  
  const getStepSlots = (stepId: string) => {
    if (!ir || !ir.slots) return [];
    return Object.values(ir.slots).filter(s => {
      return s.context?.relatedNodeIds?.includes(stepId);
    }).map(s => {
      const groupCount = ir.choiceGroups[s.choiceGroupId]?.choices?.length || 0;
      return {
        id: s.id,
        title: s.name,
        candidatesCount: groupCount
      };
    });
  };

  const topGap = abnormalGaps.length > 0 ? abnormalGaps[0] : null;
  const businessObjects = Object.values(ir?.nodes || {}).filter((n: any) => n.kind === 'business_object');

  return (
    <div className="flex-1 flex w-full relative">
      <div className="flex-1 p-6 pb-24 overflow-y-auto w-full">
        <div className="max-w-6xl mx-auto animate-in fade-in duration-500">
          
          <div className="flex flex-col gap-6 h-full content-start">
            
            {/* Main Flow Swimlanes */}
            <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm relative overflow-x-auto w-full">
              <div className="flex justify-between items-center mb-6 border-b border-slate-100 pb-4">
                <div>
                  <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">主线流程与可追踪泳道</h2>
                  <p className="text-xs text-slate-500 uppercase tracking-widest font-bold">Traceable Swimlanes</p>
                </div>
                
                {/* Unclosed path logic */}
                <div className="flex items-center relative">
                  {topGap ? (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg py-1.5 px-3 flex items-center gap-2 shadow-sm cursor-pointer hover:bg-amber-100 transition-colors" onClick={() => setShowAllGaps(!showAllGaps)}>
                       <div className="flex items-center justify-center p-0.5 font-bold text-amber-500 text-sm">
                         ⚠️
                       </div>
                       <div>
                          <div className="flex items-center gap-1.5">
                             <span className="text-[9px] bg-amber-100 text-amber-700 px-1 rounded font-bold whitespace-nowrap">{topGap.title}</span>
                             <span className="text-amber-900 text-xs font-bold leading-none line-clamp-1 max-w-[150px]">{topGap.description}</span>
                          </div>
                       </div>
                       <div className="ml-1 pl-2 border-l border-amber-200 text-amber-600 text-[10px] font-bold flex items-center leading-none">
                         {showAllGaps ? '收起' : `全部 (${abnormalGaps.length}) →`}
                       </div>
                    </div>
                  ) : (
                    <div className="bg-emerald-50 border border-emerald-200 rounded-lg py-1.5 px-3 flex items-center gap-2 shadow-sm">
                      <div className="flex items-center justify-center p-0.5 font-bold text-emerald-500 text-sm">✓</div>
                      <div className="text-emerald-900 text-xs font-bold leading-none">暂无流程缺口</div>
                    </div>
                  )}

                  {/* Dropdown Menu */}
                  {showAllGaps && (
                    <>
                      <div className="fixed inset-0 z-30" onClick={() => setShowAllGaps(false)}></div>
                      <div className="absolute top-[110%] right-0 mt-1 w-[800px] max-w-[calc(100vw-200px)] bg-white rounded-xl shadow-xl border border-slate-200 z-40 flex flex-col overflow-hidden max-h-[60vh] animate-in slide-in-from-top-2 duration-200 pointer-events-auto">
                        <div className="flex items-center justify-between p-4 border-b border-slate-100 bg-slate-50/50 shrink-0">
                          <div>
                            <h3 className="font-bold text-slate-800 text-sm flex items-center gap-2">
                              <span className="flex items-center justify-center w-6 h-6 rounded-full bg-amber-100 text-amber-600 shadow-sm text-xs">⚠️</span>
                              未闭环路径诊断细节 
                              <span className="text-[10px] bg-white border border-slate-200 px-2 py-0.5 rounded-full text-slate-600 shadow-sm">
                                {abnormalGaps.length > 0 ? abnormalGaps.length : 1} 项
                              </span>
                            </h3>
                          </div>
                          <button onClick={() => setShowAllGaps(false)} className="text-slate-400 hover:text-slate-600 bg-white border border-slate-200 hover:bg-slate-50 shadow-sm w-6 h-6 rounded-full flex items-center justify-center transition-all">
                            <span className="sr-only">Close</span>
                            <span className="text-sm font-bold">&times;</span>
                          </button>
                        </div>
                        
                        <div className="p-4 overflow-y-auto bg-slate-50/30 flex-1">
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {abnormalGaps.map(gap => (
                              <GapCard 
                                key={gap.id}
                                gap={gap as any}
                                onClick={() => {
                                  setSelectedObject(gap as any);
                                  if (gap.relatedNodeIds[0]) setHighlightTarget(gap.relatedNodeIds[0]);
                                  setShowAllGaps(false);
                                }}
                                onGenerate={() => { generateCandidate(gap.id); setShowAllGaps(false); }}
                                onDefer={() => { deferObject(gap.id); setShowAllGaps(false); }}
                              />
                            ))}
                            
                            {abnormalGaps.length === 0 && (
                              <div className="text-xs text-slate-500 italic">暂无异常/规则缺口。</div>
                            )}
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
              
              <div className="flex min-w-[800px] gap-4">
                {swimlanes.map((lane, laneIdx) => (
                  <div key={lane} className="flex-1 border bg-slate-50/50 border-slate-100 rounded-xl flex flex-col min-h-[500px]">
                    <div className="p-3 border-b border-slate-100 bg-white rounded-t-xl shrink-0">
                       <h3 className="text-xs font-bold text-center text-slate-600">{lane}</h3>
                    </div>
                    <div className="flex-1 p-3 space-y-4 relative isolate">
                      {getStepsBySwimlane(lane).map(step => {
                        const nextSteps = getStepNextSteps(step.id);
                        const excSteps = getStepExceptionSteps(step.id);
                        const linkedSlots = getStepSlots(step.id);
                        
                        return (
                          <div key={step.id} className="relative z-10 w-full" onClick={() => setSelectedObject(step)}>
                            <div className={`
                              rounded-xl transition-all cursor-pointer shadow-sm
                              ${selectedObject?.id === step.id ? 'ring-2 ring-indigo-500 ring-offset-2 border-transparent' : 'border border-transparent hover:border-indigo-300'}
                              ${highlightTarget === step.id ? 'ring-2 ring-amber-400' : ''}
                            `}>
                              <FlowStepCard 
                                name={step.title}
                                type={step.stepType}
                                actor={step.actor}
                                status={step.status}
                                inputs={step.input}
                                outputs={step.output}
                                nextSteps={nextSteps.length > 0 ? nextSteps : undefined}
                                exceptionSteps={excSteps.length > 0 ? excSteps : undefined}
                                slots={linkedSlots}
                                active={false}
                                onClick={() => setSelectedObject(step)}
                                onSlotClick={(slotId) => {
                                  if (ir?.slots[slotId] && ir.slots[slotId].choiceGroupId) {
                                    const cg = ir.choiceGroups[ir.slots[slotId].choiceGroupId];
                                    if (cg) setSelectedObject(cg);
                                  }
                                }}
                              />
                            </div>
                          </div>
                        );
                      })}

                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* State Transitions Container beneath Flow Swimlanes */}
            <section className="w-full bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
              <div className="mb-6 border-b border-slate-100 pb-4 flex justify-between items-start">
                <div>
                  <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">业务对象状态模型摘要</h2>
                  <p className="text-xs text-slate-500 uppercase tracking-widest font-bold">State Machine Models</p>
                </div>
              </div>
              
              <div className="space-y-4">
                {businessObjects.length === 0 && (
                  <div className="text-sm text-slate-500 italic">暂无业务对象。可在流程步骤中“绑定业务对象”或手动补充。</div>
                )}

                {businessObjects.map((obj: any) => {
                  const relatedStepIds = (ir?.links || [])
                    .filter((l: any) => (l.sourceId === obj.id || l.targetId === obj.id) && (l.type === 'reads' || l.type === 'writes' || l.type === 'changes_state'))
                    .map((l: any) => (l.sourceId === obj.id ? l.targetId : l.sourceId))
                    .filter((id: string) => ir?.nodes?.[id]?.kind === 'flow_step');
                  const relatedSteps = [...new Set(relatedStepIds)].map((id) => ir?.nodes?.[id]).filter(Boolean) as any[];

                  return (
                    <div
                      key={obj.id}
                      onClick={() => setSelectedObject(obj)}
                      className="border border-slate-200 rounded-xl p-5 bg-slate-50 shadow-sm cursor-pointer hover:border-indigo-300 hover:bg-slate-50/80 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="font-bold text-slate-800 text-base flex items-center gap-2">
                            <span className="truncate">{obj.title}</span>
                            <span className="bg-white border border-slate-200 text-slate-400 text-[10px] font-bold px-2 py-0.5 rounded shadow-sm shrink-0">Data Object</span>
                          </div>
                          <div className="mt-1 text-xs text-slate-600 line-clamp-2">{obj.description || '暂无描述'}</div>
                        </div>
                      </div>

                      <div className="mt-4">
                        <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">关联流程步骤</div>
                        {relatedSteps.length === 0 ? (
                          <div className="text-xs text-slate-500 italic">暂无 reads/writes/changes_state 链路。</div>
                        ) : (
                          <div className="flex flex-wrap gap-2">
                            {relatedSteps.map((s) => (
                              <button
                                key={s.id}
                                onClick={(e) => { e.stopPropagation(); setSelectedObject(s); setHighlightTarget(s.id); }}
                                className="text-[11px] px-2 py-1 rounded-lg bg-white border border-slate-200 text-slate-700 hover:border-indigo-300 hover:text-indigo-700 transition-colors"
                              >
                                {s.title}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

          </div>
        </div>
      </div>
      
      
      <RightObjectPanel />
    </div>
  );
}
