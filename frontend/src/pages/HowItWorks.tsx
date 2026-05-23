import { useState } from 'react';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { IssueCard } from '@/components/shared/IssueCard';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Workflow, GitBranch } from 'lucide-react';
import { FlowStepTypeToText } from '@/core/schema';
import { buildStepDetail, buildSystemProjection, projectionPath } from '@/core/selectors';
import { 
  useWorkspaceStore, 
  selectIssues, 
  selectSelectedObject 
} from '@/store/useWorkspaceStore';

export function HowItWorks() {
  const { 
    highlightTarget,
    setSelectedObject,
    setHighlightTarget,
    createSlotFromIssue,
    expandSlot,
    updateIssueAttributes,
    openSlot,
  } = useWorkspaceStore();
  const navigate = useNavigate();
  
  const ir = useWorkspaceStore(state => state.ir);
  const issues = useWorkspaceStore(selectIssues);
  const selectedObject = useWorkspaceStore(selectSelectedObject);
  const system = buildSystemProjection(ir);
  const [showAllIssues, setShowAllIssues] = useState(false);

  const isWhatComplete = (ir?.actors || []).length > 0 && (ir?.features || []).length > 0;

  if (!isWhatComplete) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 bg-slate-50 min-h-[80vh] w-full">
        <div className="max-w-md w-full bg-white rounded-3xl p-8 border border-slate-200 shadow-lg text-center space-y-6 animate-in fade-in duration-300">
          <div className="mx-auto w-16 h-16 rounded-2xl bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-500 shadow-sm animate-pulse">
            <Workflow className="w-8 h-8" />
          </div>
          <div className="space-y-2">
            <h3 className="text-lg font-black text-slate-900 tracking-tight">业务流程建模前置依赖未满足</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              根据高一致性建模方法论，业务流程 (How) 是<b>执行角色</b>针对系统中的<b>功能特征点</b>展开的流转演化。
            </p>
            <p className="text-xs text-slate-400 leading-relaxed bg-slate-50 p-3 rounded-xl border border-slate-100/60">
              请先在 <b>“要做什么 (What)”</b> 页面中至少定义一个参与者角色与系统功能节点，然后才能在此处定义流程步骤及输入输出实体关系。
            </p>
          </div>
          <button
            onClick={() => navigate('/what')}
            className="w-full py-2.5 px-4 rounded-xl bg-slate-900 text-white text-xs font-bold hover:bg-slate-800 transition-colors shadow-sm"
          >
            → 前往 What 阶段进行角色与能力建模
          </button>
        </div>
      </div>
    );
  }

  const abnormalIssues = system.abnormalIssues.length ? system.abnormalIssues : issues.filter(g => g.category === 'flow_gap' || g.category === 'rule_gap');

  const topIssue = abnormalIssues.length > 0 ? abnormalIssues[0] : null;
  const businessObjects = system.businessObjects.length ? system.businessObjects : Object.values((ir as any)?.nodes || {}).filter((n: any) => n.kind === 'business_object');

  const openIssueFlow = async (issueId: string) => {
    const slotId = await createSlotFromIssue(issueId);
    if (slotId) {
      await expandSlot(slotId);
    }
  };

  const jumpToProjection = (projection: any) => {
    return navigate(projectionPath(projection));
  };

  return (
    <div className="flex-1 flex w-full relative">
      <div className="flex-1 p-6 pb-24 overflow-y-auto w-full">
        <div className="max-w-6xl mx-auto animate-in fade-in duration-500">
          
          <div className="flex flex-col gap-6 h-full content-start">
            
            {/* System Business Flow Models */}
            <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm relative w-full">
              <div className="flex justify-between items-center mb-6 border-b border-slate-100 pb-4">
                <div>
                  <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">系统业务流程模型</h2>
                  <p className="text-xs text-slate-400 uppercase tracking-widest font-bold">Multiple Business Processes</p>
                </div>
                
                {/* Unclosed path logic */}
                <div className="flex items-center relative">
                  {topIssue ? (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg py-1.5 px-3 flex items-center gap-2 shadow-sm cursor-pointer hover:bg-amber-100 transition-colors" onClick={() => setShowAllIssues(!showAllIssues)}>
                       <div className="flex items-center justify-center w-5 h-5 rounded-full bg-amber-100 text-amber-600 text-xs font-bold">
                         !
                       </div>
                       <div>
                          <div className="flex items-center gap-1.5">
                             <span className="text-[9px] bg-amber-100 text-amber-700 px-1 rounded font-bold whitespace-nowrap">{topIssue.title}</span>
                             <span className="text-amber-900 text-xs font-bold leading-none line-clamp-1 max-w-[150px]">{topIssue.description}</span>
                          </div>
                       </div>
                       <div className="ml-1 pl-2 border-l border-amber-200 text-amber-600 text-[10px] font-bold flex items-center leading-none">
                         {showAllIssues ? '收起' : `全部 (${abnormalIssues.length}) →`}
                       </div>
                    </div>
                  ) : (
                    <div className="bg-emerald-50 border border-emerald-200 rounded-lg py-1.5 px-3 flex items-center gap-2 shadow-sm">
                      <div className="flex items-center justify-center w-5 h-5 rounded-full bg-emerald-100 text-emerald-600 text-xs font-bold">OK</div>
                      <div className="text-emerald-900 text-xs font-bold leading-none">暂无流程 Issue</div>
                    </div>
                  )}

                  {/* Dropdown Menu */}
                  {showAllIssues && (
                    <>
                      <div className="fixed inset-0 z-30" onClick={() => setShowAllIssues(false)}></div>
                      <div className="absolute top-[110%] right-0 mt-1 w-[800px] max-w-[calc(100vw-200px)] bg-white rounded-xl shadow-xl border border-slate-200 z-40 flex flex-col overflow-hidden max-h-[60vh] animate-in slide-in-from-top-2 duration-200 pointer-events-auto">
                        <div className="flex items-center justify-between p-4 border-b border-slate-100 bg-slate-50/50 shrink-0">
                          <div>
                            <h3 className="font-bold text-slate-800 text-sm flex items-center gap-2">
                              <span className="flex items-center justify-center w-6 h-6 rounded-full bg-amber-100 text-amber-600 shadow-sm text-xs">!</span>
                              未闭环路径诊断细节
                              <span className="text-[10px] bg-white border border-slate-200 px-2 py-0.5 rounded-full text-slate-600 shadow-sm">
                                {abnormalIssues.length > 0 ? abnormalIssues.length : 1} 项
                              </span>
                            </h3>
                          </div>
                          <button onClick={() => setShowAllIssues(false)} className="text-slate-400 hover:text-slate-600 bg-white border border-slate-200 hover:bg-slate-50 shadow-sm w-6 h-6 rounded-full flex items-center justify-center transition-all">
                            <span className="sr-only">Close</span>
                            <span className="text-sm font-bold">&times;</span>
                          </button>
                        </div>
                        
                        <div className="p-4 overflow-y-auto bg-slate-50/30 flex-1">
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {abnormalIssues.map(issue => (
                              <IssueCard
                                key={issue.id}
                                issue={issue as any}
                                onClick={() => {
                                  setSelectedObject(issue as any);
                                  if (issue.relatedNodeIds[0]) setHighlightTarget(issue.relatedNodeIds[0]);
                                  if ((issue as any).suggestedProjection) jumpToProjection((issue as any).suggestedProjection);
                                  setShowAllIssues(false);
                                }}
                                onCreateSlot={() => { void openIssueFlow(issue.id); setShowAllIssues(false); }}
                                onIgnore={() => { void updateIssueAttributes(issue.id, { status: 'ignored' }); setShowAllIssues(false); }}
                              />
                            ))}
                            
                            {abnormalIssues.length === 0 && (
                              <div className="text-xs text-slate-500 italic">暂无异常/规则 Issue。</div>
                            )}
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>

              <div className="space-y-8">
                {(!ir?.flows || ir.flows.length === 0) && (
                  <div className="text-center py-16 border-2 border-dashed border-slate-200 rounded-2xl text-slate-500 italic text-sm">
                    当前需求空间没有定义任何业务流程。请尝试通过 AI 智能推演生成。
                  </div>
                )}
                
                {(ir?.flows || []).map((flow) => {
                  const featNames = (flow.featureIds || [])
                    .map(fid => (ir.features || []).find(f => f.featureId === fid)?.featureName)
                    .filter(Boolean) as string[];

                  return (
                    <div key={flow.flowId} onClick={() => setSelectedObject(flow)} className={`rounded-2xl border p-6 bg-slate-50/50 shadow-sm cursor-pointer transition-all ${selectedObject?.id === flow.flowId.toString() || selectedObject?.flowId === flow.flowId ? 'ring-2 ring-indigo-500 bg-slate-50 border-transparent shadow-md' : 'border-slate-200 hover:border-indigo-200'}`}>
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                        <div className="space-y-1">
                          <h3 className="font-bold text-slate-800 text-lg flex items-center gap-2">
                            <Workflow className="w-5 h-5 text-indigo-600" />
                            {flow.flowName}
                          </h3>
                          <p className="text-xs text-slate-500 leading-normal">{flow.flowDescription}</p>
                        </div>
                        {featNames.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 shrink-0 self-start sm:self-center">
                            {featNames.map(fName => (
                              <span key={fName} className="text-[9px] bg-indigo-50 border border-indigo-100 text-indigo-700 font-bold px-2 py-0.5 rounded-md">
                                关联功能: {fName}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Steps flow container */}
                      <div className="flex items-center overflow-x-auto gap-4 py-4 scrollbar-thin">
                        {(flow.flowSteps || []).map((step, idx) => {
                          const stepDetail = buildStepDetail(ir, step.id);
                          const stepActors = (step.actorIds || [])
                            .map(aid => (ir.actors || []).find(a => a.actorId === aid)?.actorName)
                            .filter(Boolean);

                          const stepTypeName = FlowStepTypeToText[step.stepType] || '动作';

                          const stepBadgeStyle = step.stepType === 'judgment'
                            ? 'bg-amber-100 text-amber-800 border-amber-200'
                            : step.stepType === 'systemAction'
                              ? 'bg-blue-100 text-blue-800 border-blue-200'
                              : 'bg-indigo-100 text-indigo-800 border-indigo-200';

                          return (
                            <div key={step.stepId} className="flex items-center shrink-0">
                              <div
                                onClick={(e) => { e.stopPropagation(); setSelectedObject(step); }}
                                className={`w-[260px] border p-4 rounded-xl shadow-sm transition-all flex flex-col gap-3 cursor-pointer bg-white ${selectedObject?.id === step.stepId.toString() || selectedObject?.stepId === step.stepId ? 'ring-2 ring-indigo-500 border-transparent shadow-md' : 'border-slate-200 hover:border-indigo-300'}`}
                              >
                                <div className="flex justify-between items-start">
                                  <div className="flex items-center gap-1.5">
                                    <span className="w-5 h-5 rounded-full bg-slate-900 text-white flex items-center justify-center text-[10px] font-bold">
                                      {idx + 1}
                                    </span>
                                    <span className={`text-[9px] font-bold px-1.5 py-0.5 border rounded ${stepBadgeStyle}`}>
                                      {stepTypeName}
                                    </span>
                                  </div>
                                </div>

                                <div>
                                  <h4 className="font-bold text-slate-800 text-sm mb-1 truncate">{step.stepName}</h4>
                                  <span className="text-[10px] font-bold text-indigo-600 uppercase">
                                    执行者: {stepActors.length > 0 ? stepActors.join(', ') : '系统自动'}
                                  </span>
                                </div>

                                <p className="text-[11px] text-slate-600 line-clamp-2 leading-relaxed">
                                  {step.stepDescription}
                                </p>

                                {/* Inputs & Outputs */}
                                {(stepDetail.inputs.length > 0 || stepDetail.outputs.length > 0) && (
                                  <div className="border-t border-slate-100 pt-2 mt-auto space-y-1.5">
                                    {stepDetail.inputs.length > 0 && (
                                      <div className="flex flex-wrap gap-1 items-center">
                                        <span className="text-[9px] text-slate-400 font-bold shrink-0">输入:</span>
                                        {stepDetail.inputs.map(inp => (
                                          <span key={inp} className="text-[9px] bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded text-slate-600">
                                            {inp}
                                          </span>
                                        ))}
                                      </div>
                                    )}
                                    {stepDetail.outputs.length > 0 && (
                                      <div className="flex flex-wrap gap-1 items-center">
                                        <span className="text-[9px] text-slate-400 font-bold shrink-0">输出:</span>
                                        {stepDetail.outputs.map(out => (
                                          <span key={out} className="text-[9px] bg-emerald-50 border border-emerald-100 px-1.5 py-0.5 rounded text-emerald-700">
                                            {out}
                                          </span>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>

                              {/* Arrow between steps */}
                              {idx < (flow.flowSteps.length - 1) && (
                                <ArrowRight className="w-5 h-5 text-slate-400 mx-2 shrink-0 animate-pulse" />
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
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
                  const relatedSteps = system.getRelatedStepsForObject(obj.id) as any[];
                  const stateChanges = relatedSteps
                    .flatMap((step: any) => buildStepDetail(ir, step.id).stateChanges)
                    .filter((value, index, array) => array.indexOf(value) === index);

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
                          <div className="text-xs text-slate-500 italic">暂无</div>
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

                      <div className="mt-4">
                        <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">状态变化</div>
                        {stateChanges.length === 0 ? (
                          <div className="text-xs text-slate-500 italic">暂无显式状态迁移</div>
                        ) : (
                          <div className="flex flex-wrap gap-2">
                            {stateChanges.map((item) => (
                              <span
                                key={item}
                                className="text-[11px] px-2 py-1 rounded-lg bg-indigo-50 border border-indigo-100 text-indigo-700"
                              >
                                {item}
                              </span>
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
