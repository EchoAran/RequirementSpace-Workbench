import React, { useState, useMemo, useEffect } from 'react';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { DraftPreviewModal } from '@/components/shared/DraftPreviewModal';
import { IssueCard } from '@/components/shared/IssueCard';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Workflow, GitBranch, Sparkles, Check, X, RefreshCw, ChevronDown, ChevronRight, Plus, Trash2 } from 'lucide-react';
import { FlowStepTypeToText } from '@/core/schema';
import { buildStepDetail, buildSystemProjection, projectionPath } from '@/core/selectors';
import { 
  useWorkspaceStore, 
  selectIssues, 
  selectSelectedObject 
} from '@/store/useWorkspaceStore';

// Cycle-safe dynamic grid positioning algorithm for DAG visualization
const computeStepPositions = (steps: any[]) => {
  const positions: Record<number, { x: number; y: number }> = {};
  if (steps.length === 0) return positions;

  const colWidth = 330;
  const rowHeight = 180;
  const visited = new Set<number>();

  // Determine starting nodes (nodes that are not listed in any nextStepIds)
  const allNextIds = new Set(steps.flatMap(s => s.nextStepIds || []));
  const startNodes = steps.filter(s => !allNextIds.has(s.stepId));

  // BFS Queue: { stepId, col, row }
  const queue: { stepId: number; col: number; row: number }[] = [];
  if (startNodes.length > 0) {
    startNodes.forEach((sn, idx) => queue.push({ stepId: sn.stepId, col: 0, row: idx }));
  } else {
    queue.push({ stepId: steps[0].stepId, col: 0, row: 0 });
  }

  const colOccupancy: Record<number, number> = {};

  while (queue.length > 0) {
    const { stepId, col, row } = queue.shift()!;
    if (visited.has(stepId)) continue;
    visited.add(stepId);

    if (colOccupancy[col] === undefined) {
      colOccupancy[col] = 0;
    }
    const currentRow = colOccupancy[col]++;
    
    positions[stepId] = {
      x: 40 + col * colWidth,
      y: 40 + currentRow * rowHeight
    };

    const step = steps.find(s => s.stepId === stepId);
    if (step && step.nextStepIds) {
      step.nextStepIds.forEach((nid, idx) => {
        if (!visited.has(nid)) {
          // Spread branches vertically
          queue.push({ stepId: nid, col: col + 1, row: idx });
        }
      });
    }
  }

  // Handle orphan steps (fallback)
  steps.forEach(s => {
    if (positions[s.stepId] === undefined) {
      let col = 0;
      while (colOccupancy[col] !== undefined && colOccupancy[col] >= 3) {
        col++;
      }
      if (colOccupancy[col] === undefined) {
        colOccupancy[col] = 0;
      }
      const currentRow = colOccupancy[col]++;
      positions[s.stepId] = {
        x: 40 + col * colWidth,
        y: 40 + currentRow * rowHeight
      };
    }
  });

  return positions;
};

export function HowItWorks() {
  const { 
    highlightTarget,
    setSelectedObject,
    setHighlightTarget,
    createSlotFromIssue,
    expandSlot,
    updateIssueAttributes,
    openSlot,
    generateFlowsAndObjects,
    regenerateFlowsAndObjects,
    confirmFlowsAndObjects,
    discardDraft,
    activeDraft,
    activeDraftType,
    isGenerating,
    isLoading,
    addBusinessObject,
    deleteBusinessObject
  } = useWorkspaceStore();
  
  const [flowFeedback, setFlowFeedback] = useState('');
  const navigate = useNavigate();
  
  const ir = useWorkspaceStore(state => state.ir);
  const issues = useWorkspaceStore(selectIssues);
  const selectedObject = useWorkspaceStore(selectSelectedObject);
  const system = buildSystemProjection(ir);
  const [showAllIssues, setShowAllIssues] = useState(false);
  const [flowViews, setFlowViews] = useState<Record<number, 'canvas' | 'list'>>({});
  const [panZoomState, setPanZoomState] = useState<Record<number, { scale: number; x: number; y: number }>>({});
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [activeDragFlowId, setActiveDragFlowId] = useState<number | null>(null);
  const [selectedPathId, setSelectedPathId] = useState<string | null>(null);

  // Fold/Collapse state for flows
  const [collapsedFlows, setCollapsedFlows] = useState<Record<number, boolean>>({});

  // Manual Add Business Object Modal State
  const [isAddBusinessObjectModalOpen, setIsAddBusinessObjectModalOpen] = useState(false);
  const [newBusinessObjectName, setNewBusinessObjectName] = useState('');
  const [newBusinessObjectDesc, setNewBusinessObjectDesc] = useState('');

  // Draggable steps (repositioning nodes)
  const [customStepPositions, setCustomStepPositions] = useState<Record<number, { x: number; y: number }>>({});
  const [activeDragStepId, setActiveDragStepId] = useState<number | null>(null);
  const [stepDragStart, setStepDragStart] = useState<{ mouseX: number; mouseY: number; initialX: number; initialY: number } | null>(null);

  const handleMouseDown = (flowId: number, e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    if (target.closest('.interactive-node-card') || target.closest('button')) {
      return;
    }
    setSelectedPathId(null);
    e.preventDefault();
    const current = panZoomState[flowId] || { scale: 1, x: 0, y: 0 };
    setDragStart({ x: e.clientX - current.x, y: e.clientY - current.y });
    setActiveDragFlowId(flowId);
  };

  const handleStepMouseDown = (stepId: number, positions: Record<number, { x: number; y: number }>, e: React.MouseEvent) => {
    e.stopPropagation();
    if (e.button !== 0) return; // Only left click drags step
    
    const basePos = positions[stepId] || { x: 0, y: 0 };
    const currentPos = customStepPositions[stepId] || basePos;
    
    setStepDragStart({
      mouseX: e.clientX,
      mouseY: e.clientY,
      initialX: currentPos.x,
      initialY: currentPos.y
    });
    setActiveDragStepId(stepId);
  };

  const handleMouseMove = (flowId: number, e: React.MouseEvent) => {
    if (activeDragStepId !== null && stepDragStart) {
      e.preventDefault();
      const scale = (panZoomState[flowId] || { scale: 1 }).scale || 1;
      const dx = (e.clientX - stepDragStart.mouseX) / scale;
      const dy = (e.clientY - stepDragStart.mouseY) / scale;
      setCustomStepPositions(prev => ({
        ...prev,
        [activeDragStepId]: {
          x: stepDragStart.initialX + dx,
          y: stepDragStart.initialY + dy
        }
      }));
      return;
    }

    if (activeDragFlowId === flowId && dragStart) {
      e.preventDefault();
      const dx = e.clientX - dragStart.x;
      const dy = e.clientY - dragStart.y;
      setPanZoomState(prev => ({
        ...prev,
        [flowId]: {
          ...(prev[flowId] || { scale: 1 }),
          x: dx,
          y: dy
        }
      }));
    }
  };

  const handleMouseUpOrLeave = () => {
    setDragStart(null);
    setActiveDragFlowId(null);
    setActiveDragStepId(null);
    setStepDragStart(null);
  };

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
  const businessObjects = ir?.businessObjects || [];

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
      <style>{`
        @keyframes pathFlow {
          from {
            stroke-dashoffset: 20;
          }
          to {
            stroke-dashoffset: 0;
          }
        }
        .path-flow-active {
          stroke-dasharray: 6 4;
          animation: pathFlow 0.8s linear infinite;
        }
      `}</style>
      <div className="flex-1 p-6 pb-24 overflow-y-auto w-full">
        <div className="max-w-6xl mx-auto animate-in fade-in duration-500 space-y-8">
          
          <div className="flex flex-col gap-6 h-full content-start">
            
            {/* AI Flow Draft Preview Banner */}
            {activeDraft && activeDraftType === 'flow' && (
              <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-6 border border-amber-200/80 shadow-md animate-in slide-in-from-top-4 duration-500 space-y-4">
                <div className="flex justify-between items-start">
                  <div className="flex items-center gap-2 flex-1 mr-4">
                    <span className="p-1.5 bg-amber-100 text-amber-700 rounded-lg shrink-0">
                      <Sparkles className="w-5 h-5 animate-pulse" />
                    </span>
                    <div className="flex-1 space-y-2">
                      <div>
                        <h3 className="text-base font-bold text-slate-900">AI 推荐的业务流程与实体草稿已生成</h3>
                        <p className="text-xs text-slate-500 mt-0.5">AI 自动设计了契合系统模型的泳道步骤与关联业务数据对象。</p>
                      </div>
                      <div className="flex gap-2 items-center max-w-md">
                        <input
                          type="text"
                          value={flowFeedback}
                          onChange={(e) => setFlowFeedback(e.target.value)}
                          placeholder="补充流程调整意见 (可选)"
                          className="flex-1 px-3 py-1.5 bg-white border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800"
                          disabled={isGenerating || isLoading}
                        />
                        <button
                          onClick={async () => {
                            await regenerateFlowsAndObjects(flowFeedback || undefined);
                            setFlowFeedback('');
                          }}
                          disabled={isGenerating || isLoading}
                          className="flex items-center gap-1 px-3 py-1.5 border border-slate-250 bg-white text-slate-700 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                        >
                          <RefreshCw className={`w-3 h-3 text-indigo-500 ${isGenerating || isLoading ? 'animate-spin' : ''}`} />
                          重新推演
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={confirmFlowsAndObjects}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50"
                    >
                      <Check className="w-3.5 h-3.5" />
                      采纳并合并推荐
                    </button>
                    <button
                      onClick={discardDraft}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white text-slate-655 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                    >
                      <X className="w-3.5 h-3.5" />
                      放弃
                    </button>
                  </div>
                </div>

                {/* Flow preview preview cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-200/60">
                  {activeDraft.flows?.map((fl: any, idx: number) => (
                    <div key={idx} className="bg-white/80 p-4 rounded-xl border border-slate-200/50">
                      <h4 className="font-bold text-slate-800 text-xs flex items-center gap-1">
                        <Workflow className="w-3.5 h-3.5 text-indigo-500" />
                        流程: {fl.flow_name}
                      </h4>
                      <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">{fl.flow_description}</p>
                      <div className="mt-3 space-y-1.5">
                        <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest block">设计步骤:</span>
                        {fl.steps?.map((st: any, i: number) => (
                          <div key={i} className="text-[10px] text-slate-650 bg-slate-50 px-2.5 py-1 rounded border border-slate-100 font-medium">
                            步骤 {i + 1}: <span className="font-bold text-slate-700">{st.step_name}</span> ({st.step_type})
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                  {activeDraft.business_objects && activeDraft.business_objects.length > 0 && (
                    <div className="bg-white/80 p-4 rounded-xl border border-slate-200/50 sm:col-span-2">
                      <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest block mb-2">生成的数据对象 Business Objects:</span>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        {activeDraft.business_objects?.map((bo: any, idx: number) => (
                          <div key={idx} className="bg-slate-50 p-2.5 rounded-lg border border-slate-150">
                            <span className="font-bold text-xs text-slate-800 block">📦 {bo.business_object_name}</span>
                            <span className="text-[10px] text-slate-500 mt-0.5 block leading-normal">{bo.business_object_description}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
            
            {/* System Business Flow Models */}
            <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm relative w-full">
              <div className="flex justify-between items-center mb-6 border-b border-slate-100 pb-4">
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-1">系统业务流程模型</h2>
                      <p className="text-xs text-slate-400 uppercase tracking-widest font-bold">Multiple Business Processes</p>
                    </div>
                    <button
                      onClick={generateFlowsAndObjects}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 text-xs bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold px-4 py-2.5 rounded-xl border border-indigo-100/80 transition-colors shadow-sm disabled:opacity-50"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${isGenerating || isLoading ? 'animate-spin' : ''}`} />
                      AI 智能推演流程与对象
                    </button>
                  </div>
                </div>
                
                {/* Unclosed path logic */}
                <div className="flex items-center relative pl-4">
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
                          <button onClick={() => setShowAllIssues(false)} className="text-slate-400 hover:text-slate-655 bg-white border border-slate-200 hover:bg-slate-50 shadow-sm w-6 h-6 rounded-full flex items-center justify-center transition-all">
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

                  const isCollapsed = collapsedFlows[flow.flowId] === true;

                  return (
                    <div 
                      key={flow.flowId} 
                      onClick={() => setSelectedObject(flow)} 
                      className={`rounded-2xl border p-6 bg-slate-50/50 shadow-sm cursor-pointer transition-all ${
                        selectedObject?.id === flow.flowId.toString() || selectedObject?.flowId === flow.flowId 
                          ? 'ring-2 ring-indigo-500 bg-slate-50 border-transparent shadow-md' 
                          : 'border-slate-200 hover:border-indigo-200'
                      }`}
                    >
                      <div className={`flex flex-col gap-4 w-full ${isCollapsed ? '' : 'mb-6 pb-4 border-b border-slate-200/60'}`}>
                        <div className="space-y-3 min-w-0">
                          <div className="flex items-center justify-between">
                            <h3 className="font-extrabold text-slate-800 text-base flex items-center gap-2">
                              <Workflow className="w-5 h-5 text-indigo-650 shrink-0" />
                              <span className="truncate">{flow.flowName}</span>
                            </h3>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setCollapsedFlows(prev => ({ ...prev, [flow.flowId]: !prev[flow.flowId] }));
                              }}
                              className="p-1 hover:bg-slate-200 rounded text-slate-500 transition-colors shrink-0"
                              title={isCollapsed ? '展开流程' : '折叠流程'}
                            >
                              {isCollapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                            </button>
                          </div>
                          <p className="text-xs text-slate-500 leading-relaxed">{flow.flowDescription}</p>
                          {featNames.length > 0 && (
                            <div className="flex items-center gap-2 bg-indigo-50/40 border border-indigo-100/50 rounded-xl px-3 py-1.5 text-[11px] text-indigo-755 font-medium w-full">
                              <span className="shrink-0 flex items-center gap-1 font-extrabold text-indigo-800">📂 覆盖功能域：</span>
                              <span className="truncate font-semibold text-indigo-700">{featNames.join(' · ')}</span>
                            </div>
                          )}
                        </div>

                        {/* View Mode Toggle Switch */}
                        {!isCollapsed && (() => {
                          const viewMode = flowViews[flow.flowId] || 'canvas';
                          return (
                            <div className="flex flex-wrap items-center justify-end">
                              <div className="flex bg-slate-200/80 p-0.5 rounded-lg border border-slate-350 text-[10px] font-bold shadow-inner" onClick={(e) => e.stopPropagation()}>
                                <button
                                  type="button"
                                  onClick={() => setFlowViews(prev => ({ ...prev, [flow.flowId]: 'canvas' }))}
                                  className={`px-2.5 py-1 rounded-md transition-all flex items-center gap-1.5 ${
                                    viewMode === 'canvas' 
                                      ? 'bg-white text-indigo-600 shadow-sm' 
                                      : 'text-slate-500 hover:text-slate-700'
                                  }`}
                                >
                                  <GitBranch className="w-3 h-3" />
                                  拓扑画布
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setFlowViews(prev => ({ ...prev, [flow.flowId]: 'list' }))}
                                  className={`px-2.5 py-1 rounded-md transition-all flex items-center gap-1.5 ${
                                    viewMode === 'list' 
                                      ? 'bg-white text-indigo-600 shadow-sm' 
                                      : 'text-slate-500 hover:text-slate-700'
                                  }`}
                                >
                                  <Workflow className="w-3 h-3" />
                                  序列模式
                                </button>
                              </div>
                            </div>
                          );
                        })()}
                      </div>

                      {/* Content rendering based on View Mode */}
                      {!isCollapsed && (() => {
                        const viewMode = flowViews[flow.flowId] || 'canvas';
                        const steps = flow.flowSteps || [];

                        if (viewMode === 'canvas') {
                          const positions = computeStepPositions(steps);
                          const maxX = Object.values(positions).reduce((max, p) => Math.max(max, p.x), 50);
                          const maxY = Object.values(positions).reduce((max, p) => Math.max(max, p.y), 50);
                          const canvasWidth = Math.max(860, maxX + 320);
                          const canvasHeight = Math.max(380, maxY + 180);

                          const currentPanZoom = panZoomState[flow.flowId] || { scale: 1, x: 0, y: 0 };
                          const isDraggingThis = activeDragFlowId === flow.flowId;
                          const isDraggingNodeOrCanvas = isDraggingThis || activeDragStepId !== null;

                          return (
                            <div 
                              className={`relative w-full h-[460px] overflow-hidden border border-slate-200/80 bg-slate-50 rounded-2xl shadow-inner select-none ${
                                isDraggingNodeOrCanvas ? 'cursor-grabbing' : 'cursor-grab'
                              }`}
                              onMouseDown={(e) => handleMouseDown(flow.flowId, e)}
                              onMouseMove={(e) => {
                                if (isDraggingThis || activeDragStepId !== null) {
                                  handleMouseMove(flow.flowId, e);
                                }
                              }}
                              onMouseUp={handleMouseUpOrLeave}
                              onMouseLeave={handleMouseUpOrLeave}
                            >
                              {/* Drag Help Tip */}
                              <div className="absolute top-4 left-4 z-30 bg-slate-900/60 backdrop-blur-sm px-2.5 py-1 rounded-lg text-[9px] font-extrabold text-white flex items-center gap-1.5 pointer-events-none select-none shadow-sm">
                                <span>💡</span>
                                <span>按住鼠标左键可平移画布，按住节点卡片可自由拖拽位置</span>
                              </div>

                              {/* Floating Glassmorphic Zoom/Pan Toolbar */}
                              <div className="absolute bottom-4 right-4 z-30 flex items-center gap-1 bg-white/90 backdrop-blur-md border border-slate-200/80 p-1.5 rounded-xl shadow-md" onClick={e => e.stopPropagation()}>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setPanZoomState(prev => {
                                      const current = prev[flow.flowId] || { scale: 1, x: 0, y: 0 };
                                      return {
                                        ...prev,
                                        [flow.flowId]: { ...current, scale: Math.max(0.5, current.scale - 0.1) }
                                      };
                                    });
                                  }}
                                  title="缩小 (Zoom Out)"
                                  className="w-7 h-7 flex items-center justify-center rounded-lg border border-slate-200 hover:bg-slate-50 text-[10px] text-slate-655 hover:text-slate-800 transition-colors shadow-sm"
                                >
                                  ➖
                                </button>
                                <span className="text-[10px] font-extrabold text-slate-500 min-w-[36px] text-center">
                                  {Math.round(currentPanZoom.scale * 100)}%
                                </span>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setPanZoomState(prev => {
                                      const current = prev[flow.flowId] || { scale: 1, x: 0, y: 0 };
                                      return {
                                        ...prev,
                                        [flow.flowId]: { ...current, scale: Math.min(2.0, current.scale + 0.1) }
                                      };
                                    });
                                  }}
                                  title="放大 (Zoom In)"
                                  className="w-7 h-7 flex items-center justify-center rounded-lg border border-slate-200 hover:bg-slate-50 text-[10px] text-slate-655 hover:text-slate-800 transition-colors shadow-sm"
                                >
                                  ➕
                                </button>
                                <div className="w-[1px] h-4 bg-slate-200 mx-1"></div>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setPanZoomState(prev => ({
                                      ...prev,
                                      [flow.flowId]: { scale: 1, x: 0, y: 0 }
                                    }));
                                    setCustomStepPositions({}); // Reset panned nodes to their BFS default positions!
                                  }}
                                  title="重置视图"
                                  className="px-2 h-7 flex items-center justify-center rounded-lg border border-slate-200 hover:bg-slate-50 text-[10px] font-extrabold text-indigo-650 hover:text-indigo-700 transition-colors shadow-sm"
                                >
                                  🔄 重置
                                </button>
                              </div>

                              {/* Dotted Grid Canvas Area */}
                              <div 
                                className="relative bg-[radial-gradient(#e2e8f0_1.5px,transparent_1.5px)] [background-size:24px_24px] select-none overflow-visible"
                                style={{ 
                                  width: `${canvasWidth}px`, 
                                  height: `${canvasHeight}px`,
                                  transform: `translate(${currentPanZoom.x}px, ${currentPanZoom.y}px) scale(${currentPanZoom.scale})`,
                                  transformOrigin: '0 0',
                                  transition: isDraggingThis ? 'none' : 'transform 0.15s ease-out',
                                  overflow: 'visible',
                                }}
                              >
                                {/* Vector Connection Layer */}
                                <svg 
                                  className="absolute inset-0 pointer-events-none overflow-visible" 
                                  width={canvasWidth} 
                                  height={canvasHeight}
                                  style={{ zIndex: 10, overflow: 'visible' }}
                                >
                                  <defs>
                                    <marker id={`arrow-default-${flow.flowId}`} markerWidth="8" markerHeight="6" refX="6" refY="3" orient="auto">
                                      <polygon points="0 0, 8 3, 0 6" fill="#a5b4fc" />
                                    </marker>
                                    <marker id={`arrow-active-${flow.flowId}`} markerWidth="8" markerHeight="6" refX="6" refY="3" orient="auto">
                                      <polygon points="0 0, 8 3, 0 6" fill="#6366f1" />
                                    </marker>
                                  </defs>
                                  {steps.flatMap((step) => {
                                    const fromPos = customStepPositions[step.stepId] || positions[step.stepId];
                                    if (!fromPos) return [];

                                    return (step.nextStepIds || []).map((nid) => {
                                      const toPos = customStepPositions[nid] || positions[nid];
                                      if (!toPos) return null;

                                      const isLoopback = toPos.x < fromPos.x;

                                      const startX = isLoopback ? fromPos.x : fromPos.x + 260;
                                      const startY = fromPos.y + 65;
                                      const endX = isLoopback ? toPos.x + 260 : toPos.x;
                                      const endY = toPos.y + 65;

                                      let pathD = '';
                                      if (isLoopback) {
                                        // Loopback/Cycle: draw an elegant arc above the nodes from left edge of source to right edge of target
                                        const midX = (startX + endX) / 2;
                                        const arcHeight = Math.max(90, Math.abs(startX - endX) * 0.28);
                                        const controlY = Math.min(startY, endY) - arcHeight;
                                        pathD = `M ${startX} ${startY} Q ${midX} ${controlY} ${endX} ${endY}`;
                                      } else {
                                        // Forward: draw a beautiful S-curve (cubic Bezier)
                                        const cp1X = startX + 60;
                                        const cp1Y = startY;
                                        const cp2X = endX - 60;
                                        const cp2Y = endY;
                                        pathD = `M ${startX} ${startY} C ${cp1X} ${cp1Y}, ${cp2X} ${cp2Y}, ${endX} ${endY}`;
                                      }

                                      const pathId = `${step.stepId}-${nid}`;
                                      const isPathSelected = selectedPathId === pathId;
                                      const isStepRelated = selectedObject && (
                                        selectedObject.stepId === step.stepId || 
                                        selectedObject.stepId === nid ||
                                        selectedObject.id === step.stepId.toString() ||
                                        selectedObject.id === nid.toString()
                                      );
                                      const isActive = isPathSelected || isStepRelated;

                                      return (
                                        <g key={pathId} className="pointer-events-none">
                                          {/* Wide invisible click assistant path */}
                                          <path
                                            d={pathD}
                                            fill="none"
                                            stroke="transparent"
                                            strokeWidth={14}
                                            style={{ pointerEvents: 'stroke', cursor: 'pointer' }}
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              setSelectedPathId(pathId);
                                              // Clear selected step to avoid conflicting highlights
                                              setSelectedObject(null);
                                            }}
                                          />
                                          {/* Visual line path */}
                                          <path
                                            d={pathD}
                                            fill="none"
                                            stroke={isActive ? '#6366f1' : '#c7d2fe'}
                                            strokeWidth={isActive ? 3.5 : 2}
                                            markerEnd={isActive ? `url(#arrow-active-${flow.flowId})` : `url(#arrow-default-${flow.flowId})`}
                                            className={`${activeDragStepId !== null ? '' : 'transition-[stroke,stroke-width] duration-150'} ${isActive ? 'path-flow-active' : ''}`}
                                            style={{ pointerEvents: 'none' }}
                                          />
                                        </g>
                                      );
                                    });
                                  })}
                                </svg>

                                {/* Absolutely Positioned Interactive Node Cards */}
                                {steps.map((step, idx) => {
                                  const pos = customStepPositions[step.stepId] || positions[step.stepId];
                                  if (!pos) return null;

                                  const stepDetail = buildStepDetail(ir, step.id);
                                  const stepActors = (step.actorIds || [])
                                    .map(aid => (ir.actors || []).find(a => a.actorId === aid)?.actorName)
                                    .filter(Boolean);

                                  const stepTypeName = FlowStepTypeToText[step.stepType] || '动作';

                                  const stepBadgeStyle = step.stepType === 'judgment'
                                    ? 'bg-amber-50 border-amber-200 text-amber-800'
                                    : step.stepType === 'systemAction'
                                      ? 'bg-blue-50 border-blue-200 text-blue-800'
                                      : 'bg-indigo-50 border-indigo-200 text-indigo-800';

                                  const isSelected = selectedObject?.id === step.stepId.toString() || selectedObject?.stepId === step.stepId;

                                  return (
                                    <div
                                      key={step.stepId}
                                      onMouseDown={(e) => handleStepMouseDown(step.stepId, positions, e)}
                                      onClick={(e) => { 
                                        e.stopPropagation(); 
                                        setSelectedObject(step); 
                                        setHighlightTarget(step.stepId.toString()); 
                                      }}
                                      className={`absolute w-[260px] h-[130px] border p-3.5 rounded-2xl shadow-sm hover:shadow-md flex flex-col justify-between bg-white cursor-pointer group z-20 interactive-node-card ${
                                        activeDragStepId === step.stepId ? '' : 'transition-all duration-150'
                                      } ${
                                        isSelected 
                                          ? 'ring-2 ring-indigo-500 border-transparent shadow-lg shadow-indigo-100/50 scale-[1.02]' 
                                          : 'border-slate-200 hover:border-indigo-400'
                                      }`}
                                      style={{
                                        left: `${pos.x}px`,
                                        top: `${pos.y}px`,
                                      }}
                                    >
                                      <div className="flex justify-between items-center leading-none mb-1">
                                        <span className="text-[9px] font-extrabold text-slate-400 uppercase tracking-wider">Step #{idx + 1}</span>
                                        <span className={`text-[8px] font-extrabold px-1.5 py-0.5 border rounded-md uppercase tracking-wide ${stepBadgeStyle}`}>
                                          {stepTypeName}
                                        </span>
                                      </div>

                                      <div className="min-w-0 flex-1 my-1">
                                        <h4 className="font-extrabold text-slate-800 text-xs truncate group-hover:text-indigo-600 transition-colors leading-tight mb-0.5">{step.stepName}</h4>
                                        <div className="text-[9px] text-slate-400 truncate font-semibold">
                                          🎭 {stepActors.length > 0 ? stepActors.join(', ') : '系统自动'}
                                        </div>
                                      </div>

                                      {/* Inputs & Outputs */}
                                      {(stepDetail.inputs.length > 0 || stepDetail.outputs.length > 0) && (
                                        <div className="flex gap-1.5 text-[8px] mt-1 border-t border-slate-100/80 pt-1.5 overflow-hidden">
                                          {stepDetail.inputs.length > 0 && (
                                            <div className="truncate flex-1 max-w-[50%]">
                                              <span className="text-slate-400 font-extrabold mr-1">In:</span>
                                              <span className="text-slate-600 font-semibold">{stepDetail.inputs.join(', ')}</span>
                                            </div>
                                          )}
                                          {stepDetail.outputs.length > 0 && (
                                            <div className="truncate flex-1 max-w-[50%]">
                                              <span className="text-emerald-500 font-extrabold mr-1">Out:</span>
                                              <span className="text-emerald-700 font-semibold">{stepDetail.outputs.join(', ')}</span>
                                            </div>
                                          )}
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          );
                        } else {
                          // Traditional Scrollable Sequence List View
                          return (
                            <div className="flex items-center overflow-x-auto gap-4 py-4 scrollbar-thin scrollbar-thumb-slate-200 scrollbar-track-transparent">
                              {steps.map((step, idx) => {
                                const stepDetail = buildStepDetail(ir, step.id);
                                const stepActors = (step.actorIds || [])
                                  .map(aid => (ir.actors || []).find(a => a.actorId === aid)?.actorName)
                                  .filter(Boolean);

                                const stepTypeName = FlowStepTypeToText[step.stepType] || '动作';

                                const stepBadgeStyle = step.stepType === 'judgment'
                                  ? 'bg-amber-100 text-amber-800 border-amber-200'
                                  : step.stepType === 'systemAction'
                                    ? 'bg-blue-105 text-blue-800 border-blue-200'
                                    : 'bg-indigo-105 text-indigo-800 border-indigo-205';

                                const isSelected = selectedObject?.id === step.stepId.toString() || selectedObject?.stepId === step.stepId;

                                return (
                                  <div key={step.stepId} className="flex items-center shrink-0">
                                    <div
                                      onClick={(e) => { 
                                        e.stopPropagation(); 
                                        setSelectedObject(step); 
                                        setHighlightTarget(step.stepId.toString());
                                      }}
                                      className={`w-[260px] border p-4 rounded-xl shadow-sm transition-all flex flex-col gap-3 cursor-pointer bg-white ${
                                        isSelected 
                                          ? 'ring-2 ring-indigo-500 border-transparent shadow-md' 
                                          : 'border-slate-200 hover:border-indigo-300'
                                      }`}
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
                                        <span className="text-[10px] font-bold text-indigo-650 uppercase">
                                          执行者: {stepActors.length > 0 ? stepActors.join(', ') : '系统自动'}
                                        </span>
                                      </div>

                                      <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed">
                                        {step.stepDescription}
                                      </p>

                                      {/* Inputs & Outputs */}
                                      {(stepDetail.inputs.length > 0 || stepDetail.outputs.length > 0) && (
                                        <div className="border-t border-slate-100 pt-2 mt-auto space-y-1.5">
                                          {stepDetail.inputs.length > 0 && (
                                            <div className="flex flex-wrap gap-1 items-center">
                                              <span className="text-[9px] text-slate-400 font-bold shrink-0">输入:</span>
                                              {stepDetail.inputs.map(inp => (
                                                <span key={inp} className="text-[9px] bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded text-slate-600 font-medium">
                                                  {inp}
                                                </span>
                                              ))}
                                            </div>
                                          )}
                                          {stepDetail.outputs.length > 0 && (
                                            <div className="flex flex-wrap gap-1 items-center">
                                              <span className="text-[9px] text-slate-450 font-bold shrink-0">输出:</span>
                                              {stepDetail.outputs.map(out => (
                                                <span key={out} className="text-[9px] bg-emerald-50 border border-emerald-100 px-1.5 py-0.5 rounded text-emerald-700 font-medium">
                                                  {out}
                                                </span>
                                              ))}
                                            </div>
                                          )}
                                        </div>
                                      )}
                                    </div>

                                    {/* Arrow between steps */}
                                    {idx < (steps.length - 1) && (
                                      <ArrowRight className="w-5 h-5 text-slate-400 mx-2 shrink-0 animate-pulse" />
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          );
                        }
                      })()}
                    </div>
                  );
                })}
              </div>
            </section>

            {/* NEW/PORTED: Manual Business Object list management */}
            <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm relative w-full">
              <div className="flex justify-between items-center mb-6 border-b border-slate-100 pb-3">
                <div className="flex-1">
                  <h3 className="text-xs font-bold text-slate-800 uppercase tracking-widest flex items-center gap-2">
                    📦 数据实体与生命周期模型 (Business Objects & State Models)
                    <button
                      onClick={() => setIsAddBusinessObjectModalOpen(true)}
                      className="p-1 text-slate-400 hover:text-indigo-650 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-md transition-all shadow-sm"
                      title="手动创建业务对象"
                    >
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                  </h3>
                </div>
              </div>
              {businessObjects.length === 0 ? (
                <div className="bg-white border border-dashed border-slate-200 rounded-2xl p-8 text-center text-xs text-slate-450 shadow-sm select-none">
                  当前工作区还没有任何业务数据对象。请通过 AI 智能推演生成，或点击左上角加号手动添加。
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                  {businessObjects.map((object) => {
                    const relatedSteps = system.getRelatedStepsForObject(object.id || object.businessObjectId) as any[];
                    const stateChanges = relatedSteps
                      .flatMap((step: any) => buildStepDetail(ir, step.id).stateChanges)
                      .filter((value, index, array) => array.indexOf(value) === index);

                    const isSelected = selectedObject?.businessObjectId === object.businessObjectId || selectedObject?.id === object.id?.toString();

                    return (
                      <div
                        key={object.businessObjectId || object.id}
                        onClick={() => setSelectedObject(object)}
                        className={`bg-white rounded-xl p-5 border transition-all cursor-pointer flex flex-col gap-4 group relative ${
                          isSelected
                            ? 'border-l-4 border-l-indigo-600 border-slate-250 shadow-md shadow-indigo-600/5'
                            : 'border-slate-200 hover:border-indigo-300 shadow-sm'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <h4 className="font-extrabold text-slate-800 text-sm truncate">{object.businessObjectName || object.title}</h4>
                            <span className="text-[10px] text-slate-400 font-bold block mt-0.5">
                              {(object.businessObjectAttributes || []).length} 个字段属性
                            </span>
                          </div>
                          <span className="text-[10px] bg-slate-50 border border-slate-200 text-slate-650 px-2.5 py-0.5 rounded-lg font-bold shrink-0 leading-none">
                            数据实体
                          </span>
                        </div>
                        <div className="text-xs text-slate-500 leading-relaxed line-clamp-3">
                          {object.businessObjectDescription || object.description || '暂无业务对象描述说明。'}
                        </div>

                        {/* Merged Related Steps and State Transitions */}
                        {(relatedSteps.length > 0 || stateChanges.length > 0) && (
                          <div className="mt-2 pt-3 border-t border-slate-100 space-y-3 shrink-0">
                            {relatedSteps.length > 0 && (
                              <div className="space-y-1.5">
                                <span className="text-[9px] text-slate-400 font-bold uppercase tracking-wider block">关联操作步骤</span>
                                <div className="flex flex-wrap gap-1">
                                  {relatedSteps.map((s) => (
                                    <button
                                      key={s.id}
                                      type="button"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setSelectedObject(s);
                                        setHighlightTarget(s.id);
                                      }}
                                      className="text-[10px] bg-slate-50 border border-slate-200 hover:border-indigo-350 hover:text-indigo-755 rounded-md px-2 py-0.5 font-medium transition-all"
                                    >
                                      ⚙️ {s.title}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            )}

                            {stateChanges.length > 0 && (
                              <div className="space-y-1.5">
                                <span className="text-[9px] text-slate-400 font-bold uppercase tracking-wider block">生命周期状态变迁</span>
                                <div className="flex flex-wrap gap-1">
                                  {stateChanges.map((item) => (
                                    <span
                                      key={item}
                                      className="text-[9px] bg-indigo-50 border border-indigo-100 text-indigo-700 font-extrabold px-2 py-0.5 rounded-md shadow-sm"
                                    >
                                      {item}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        )}

                        {/* Delete Business Object Manual Control */}
                        <button
                          type="button"
                          onClick={async (e) => {
                            e.stopPropagation();
                            const ok = window.confirm(`确定删除业务实体“${object.businessObjectName || object.title}”吗？这会清除其所有属性和流程步骤中的输入输出绑定。`);
                            if (!ok) return;
                            await deleteBusinessObject(object.businessObjectId || Number(object.id));
                          }}
                          className="absolute right-4 bottom-4 p-1 rounded-md text-slate-350 hover:text-rose-600 hover:bg-rose-50 border border-transparent hover:border-rose-100 opacity-0 group-hover:opacity-100 transition-all shadow-sm"
                          title="删除该业务对象"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

          </div>
        </div>
      </div>

      {/* NEW/PORTED: Manual Add Business Object Modal */}
      {isAddBusinessObjectModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4 select-none animate-in fade-in duration-200">
          <div className="bg-white/95 border border-slate-200 shadow-2xl max-w-md w-full flex flex-col rounded-3xl animate-in scale-in-95 duration-200 overflow-hidden">
            <div className="p-6 pb-4 border-b border-slate-100 bg-slate-50/50">
              <h3 className="font-extrabold text-sm text-slate-800">📦 手动创建业务对象</h3>
              <p className="text-[10px] text-slate-500 mt-1">补充系统中的核心数据实体，后续可在右侧面板继续添加字段属性。</p>
            </div>
            <div className="p-6 space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">对象实体名称</label>
                <input
                  type="text"
                  value={newBusinessObjectName}
                  onChange={(e) => setNewBusinessObjectName(e.target.value)}
                  placeholder="例如：'订单'、'会员实体'、'审批记录'"
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">实体说明描述</label>
                <textarea
                  value={newBusinessObjectDesc}
                  onChange={(e) => setNewBusinessObjectDesc(e.target.value)}
                  placeholder="简述该业务对象承载的核心业务属性字段与关联用途说明。"
                  rows={3}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium resize-none leading-relaxed"
                />
              </div>
            </div>
            <div className="p-6 pt-4 border-t border-slate-100 flex justify-end gap-2 bg-slate-50/30">
              <button
                onClick={() => {
                  setIsAddBusinessObjectModalOpen(false);
                  setNewBusinessObjectName('');
                  setNewBusinessObjectDesc('');
                }}
                className="px-4 py-2 border border-slate-200 bg-white text-slate-655 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors shadow-sm"
              >
                取消
              </button>
              <button
                onClick={async () => {
                  if (!newBusinessObjectName.trim()) return;
                  await addBusinessObject(newBusinessObjectName.trim(), newBusinessObjectDesc.trim());
                  setIsAddBusinessObjectModalOpen(false);
                  setNewBusinessObjectName('');
                  setNewBusinessObjectDesc('');
                }}
                disabled={!newBusinessObjectName.trim()}
                className="px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50"
              >
                确定创建
              </button>
            </div>
          </div>
        </div>
      )}

      <DraftPreviewModal
        draft={activeDraft}
        draftType={activeDraftType}
        isWorking={isGenerating || isLoading}
        onDiscard={discardDraft}
        onRegenerate={(feedback) => regenerateFlowsAndObjects(feedback)}
        onConfirm={confirmFlowsAndObjects}
      />

      <RightObjectPanel />
    </div>
  );
}
