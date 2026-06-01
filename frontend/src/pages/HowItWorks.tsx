import React, { useState, useMemo, useEffect } from 'react';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { DraftPreviewModal } from '@/components/shared/DraftPreviewModal';
import { useNavigate, useLocation } from 'react-router-dom';
import { ArrowRight, Workflow, GitBranch, Sparkles, Check, X, RefreshCw, ChevronDown, ChevronRight, Plus, Trash2, AlertTriangle, Database, User, Folder } from 'lucide-react';
import { buildProjectRoute, buildStepDetail, buildSystemProjection, getStageIssues, projectionPath } from '@/core/selectors';
import { StageGuidanceBanner } from '@/components/shared/StageGuidanceBanner';
import { ConfirmTransitionModal } from '@/components/shared/ConfirmTransitionModal';
import { AIAddObjectDialog, type AIAddTargetType } from '@/components/shared/AIAddObjectDialog';
import { StatusBadge } from '@/components/shared/StatusBadge';
import {
  useWorkspaceStore,
  selectSelectedObject,
  selectPageHealth,
} from '@/store/useWorkspaceStore';
import { ChoiceGroupPreviewModal } from '@/components/shared/ChoiceGroupPreviewModal';


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

const getFeaturePath = (featureId: number, features: any[]): string => {
  const path: string[] = [];
  let current = features.find(f => f.featureId === featureId);
  while (current) {
    path.unshift(current.featureName);
    current = current.parentId ? features.find(f => f.featureId === current.parentId) : null;
  }
  return path.join(' / ');
};

export function HowItWorks() {
  const navigate = useNavigate();
  const location = useLocation();
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
    deleteBusinessObject,
    boDeletionError,
    setBoDeletionError,
    setPendingManualAction,
    addFlow,
    deleteFlow,
    addFlowStep,
    deleteFlowStep,
    runDiagnosis,
    unlockStageGate,
    confirmRepairDraft,
    discardRepairDraft,
    regenerateRepairDraft,
    activeChoiceGroup,
    isGeneratingChoices,
    choiceGroupGenerationProgress,
    acceptChoice,
    discardChoiceGroup,
    clearPerceptionSlot,
  } = useWorkspaceStore();

  const [flowFeedback, setFlowFeedback] = useState('');
  const [isTransitionModalOpen, setIsTransitionModalOpen] = useState(false);

  // 从 URL 参数解析高亮目标（来自概览页假设账本点击跳转）
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const highlight = params.get('highlight');
    if (!highlight) return;
    const [kind, ...idParts] = highlight.split('-');
    const id = parseInt(idParts.join('-'), 10);
    if (isNaN(id)) return;
    navigate(location.pathname, { replace: true });

    setTimeout(() => {
      const el = document.getElementById(`${kind}-${id}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('ring-2', 'ring-indigo-400', 'ring-offset-2', 'rounded-xl');
        setTimeout(() => el.classList.remove('ring-2', 'ring-indigo-400', 'ring-offset-2', 'rounded-xl'), 3000);
      }
      if (kind === 'flow') {
        const flow = ir?.flows?.find((f: any) => f.flowId === id);
        if (flow) setSelectedObject(flow);
      } else if (kind === 'business_object') {
        const bo = ir?.businessObjects?.find((b: any) => b.businessObjectId === id);
        if (bo) setSelectedObject(bo);
      }
    }, 200);
  }, [location.search]);

  const handleManualAction = (slot: any) => {
    if (slot.kind === 'generative_perception_slot') {
      void clearPerceptionSlot();
      return;
    }

    if (slot.kind === 'stage_gate_transition_confirm') {
      setIsTransitionModalOpen(true);
      return;
    }

    const targetId = slot.targetId || slot.actions?.manual?.targetId;
    const targetRoute = slot.actions?.manual?.targetRoute;
    if (targetId) {
      const targetKey = targetId.toString();
      setHighlightTarget(targetKey);
      const bo = ir?.businessObjects?.find((item: any) => item.businessObjectId === targetId);
      const flow = ir?.flows?.find((item: any) => item.flowId === targetId);
      const step = ir?.flows?.flatMap((flowItem: any) => flowItem.flowSteps || []).find((item: any) => item.stepId === targetId);
      setSelectedObject(bo || flow || step || null);
    }
    if (targetRoute && targetRoute !== '/flow') {
      navigate(buildProjectRoute(ir?.projectId, targetRoute));
    }
  };

  const handleAIAction = async (slot: any) => {
    const kind = slot.kind;
    if (kind === 'stage_gate_transition_confirm') {
      await runDiagnosis();
    } else if (kind === 'how_onboarding' || kind === 'missing_flow') {
      await generateFlowsAndObjects();
    } else {
      if (slot.id) {
        await expandSlot(slot.id);
      }
    }
  };

  const ir = useWorkspaceStore(state => state.ir);
  const pageHealth = selectPageHealth({ ir } as any, '/flow');
  const selectedObject = useWorkspaceStore(selectSelectedObject);
  const system = buildSystemProjection(ir);
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

  // 
  const [isAddFlowModalOpen, setIsAddFlowModalOpen] = useState(false);
  const [newFlowName, setNewFlowName] = useState('');
  const [newFlowDesc, setNewFlowDesc] = useState('');
  const [newFlowFeatureIds, setNewFlowFeatureIds] = useState<number[]>([]);

  const [aiDialogTarget, setAiDialogTarget] = useState<{ targetType: AIAddTargetType; anchor?: Record<string, any> } | null>(null);
  const isAIDialogOpen = aiDialogTarget !== null;

  const [isAddStepModalOpen, setIsAddStepModalOpen] = useState(false);
  const [activeFlowIdForNewStep, setActiveFlowIdForNewStep] = useState<number | null>(null);
  const [newStepName, setNewStepName] = useState('');
  const [newStepDesc, setNewStepDesc] = useState('');
  const [newStepType, setNewStepType] = useState<'actorAction' | 'systemAction' | 'judgment'>('actorAction');
  const [newStepActorIds, setNewStepActorIds] = useState<number[]>([]);
  const [newStepInputBoIds, setNewStepInputBoIds] = useState<number[]>([]);
  const [newStepOutputBoIds, setNewStepOutputBoIds] = useState<number[]>([]);

  // Draggable steps (repositioning nodes)
  const [customStepPositions, setCustomStepPositions] = useState<Record<number, { x: number; y: number }>>({});
  const [activeDragStepId, setActiveDragStepId] = useState<number | null>(null);
  const [stepDragStart, setStepDragStart] = useState<{ mouseX: number; mouseY: number; initialX: number; initialY: number } | null>(null);

  const getStepTypeMeta = (stepType: 'actorAction' | 'systemAction' | 'judgment') => {
    if (stepType === 'judgment') {
      return {
        label: '分支结点',
        badgeClass: 'bg-amber-50 border-amber-200 text-amber-800',
        numberClass: 'bg-amber-500 text-white',
        cardClass: 'border-amber-300/90 bg-amber-50/70 hover:border-amber-400 border-dashed',
        selectedClass: 'border-amber-400 shadow-lg shadow-amber-100/70',
        shapeClass: 'rounded-[24px]',
        clipPath: undefined,
        titleClass: 'group-hover:text-amber-700',
        actorToneClass: 'text-amber-700',
        showActor: false,
        descriptionClampClass: 'line-clamp-1',
        ioVisibleCount: 1,
      } as const;
    }

    if (stepType === 'systemAction') {
      return {
        label: '系统动作',
        badgeClass: 'bg-sky-50 border-sky-200 text-sky-800',
        numberClass: 'bg-sky-500 text-white',
        cardClass: 'border-sky-200 bg-sky-50/45 hover:border-sky-400',
        selectedClass: 'ring-2 ring-sky-500 border-transparent shadow-lg shadow-sky-100/70',
        shapeClass: 'rounded-[28px]',
        clipPath: undefined,
        titleClass: 'group-hover:text-sky-700',
        actorToneClass: 'text-sky-700',
        showActor: false,
        descriptionClampClass: 'line-clamp-1',
        ioVisibleCount: 1,
      } as const;
    }

    return {
      label: '用户动作',
      badgeClass: 'bg-indigo-50 border-indigo-200 text-indigo-800',
      numberClass: 'bg-indigo-600 text-white',
      cardClass: 'border-slate-200 bg-white hover:border-indigo-400',
      selectedClass: 'ring-2 ring-indigo-500 border-transparent shadow-lg shadow-indigo-100/50',
      shapeClass: 'rounded-2xl',
      clipPath: undefined,
      titleClass: 'group-hover:text-indigo-600',
      actorToneClass: 'text-slate-500',
      showActor: true,
      descriptionClampClass: 'line-clamp-2',
      ioVisibleCount: 2,
    } as const;
  };

  const renderIoTokens = (items: string[], tone: 'input' | 'output', visibleCount = 2) => {
    const visibleItems = items.slice(0, visibleCount);
    const hiddenCount = Math.max(0, items.length - visibleItems.length);
    const tokenClass =
      tone === 'input'
        ? 'border-slate-200 bg-slate-100 text-slate-700'
        : 'border-emerald-100 bg-emerald-50 text-emerald-700';

    return (
      <>
        {visibleItems.map((item) => (
          <span
            key={`${tone}-${item}`}
            className={`min-w-0 max-w-[92px] truncate rounded-full border px-1.5 py-0.5 text-[10px] font-semibold ${tokenClass}`}
            title={item}
          >
            {item}
          </span>
        ))}
        {hiddenCount > 0 && (
          <span className="rounded-full border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] font-semibold text-slate-500">
            +{hiddenCount}
          </span>
        )}
      </>
    );
  };

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
              根据高一致性建模方法论，业务流程 (How) 是<b>执行参与者</b>针对系统中的<b>功能特征点</b>展开的流转演化。
            </p>
            <p className="text-xs text-slate-400 leading-relaxed bg-slate-50 p-3 rounded-xl border border-slate-100/60">
              请先在 <b>“要做什么 (What)”</b> 页面中至少定义一个参与者与系统功能节点，然后才能在此处定义流程步骤及输入输出实体关系。
            </p>
          </div>
          <button
            onClick={() => navigate(buildProjectRoute(ir?.projectId, '/what'))}
            className="w-full py-2.5 px-4 rounded-xl bg-slate-900 text-white text-xs font-bold hover:bg-slate-800 transition-colors shadow-sm"
          >
            → 前往 What 阶段进行参与者与能力建模
          </button>
        </div>
      </div>
    );
  }

  const howIssues = getStageIssues(ir, 'how');
  const businessObjects = ir?.businessObjects || [];

  const openIssueFlow = async (issueId: string) => {
    const slotId = await createSlotFromIssue(issueId);
    if (slotId) {
      await expandSlot(slotId);
    }
  };

  const jumpToProjection = (projection: any) => {
    return navigate(buildProjectRoute(ir?.projectId, projectionPath(projection)));
  };

  const handleIssueClick = (issue: any) => {
    setSelectedObject(issue as any);
    if (issue.relatedNodeIds?.[0]) {
      setHighlightTarget(issue.relatedNodeIds[0]);
    }
    if (issue.suggestedProjection) {
      jumpToProjection(issue.suggestedProjection);
    }
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

            {pageHealth.nextSlot && (
              <StageGuidanceBanner
                slot={pageHealth.nextSlot}
                issues={howIssues as any}
                onManualAction={handleManualAction}
                onAIAction={handleAIAction}
                onReDiagnose={runDiagnosis}
                onIssueClick={handleIssueClick}
                onIssueCreateSlot={(issue) => { void openIssueFlow(issue.id); }}
                onIssueIgnore={(issue) => void updateIssueAttributes(issue.id, { status: 'ignored' })}
                isWorking={isGenerating || isLoading}
              />
            )}

            {!pageHealth.nextSlot && (
              <StageGuidanceBanner
                issues={howIssues as any}
                onReDiagnose={runDiagnosis}
                onIssueClick={handleIssueClick}
                onIssueCreateSlot={(issue) => { void openIssueFlow(issue.id); }}
                onIssueIgnore={(issue) => void updateIssueAttributes(issue.id, { status: 'ignored' })}
                isWorking={isGenerating || isLoading}
              />
            )}

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
                          className="flex items-center gap-1 px-3 py-1.5 border border-slate-200 bg-white text-slate-700 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
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
                      className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
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
                      <p className="text-xs text-slate-500 mt-1 leading-relaxed">{fl.flow_description}</p>
                      <div className="mt-3 space-y-1.5">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">设计步骤:</span>
                        {fl.steps?.map((st: any, i: number) => (
                          <div key={i} className="text-[10px] text-slate-600 bg-slate-50 px-2.5 py-1 rounded border border-slate-100 font-medium">
                            步骤 {i + 1}: <span className="font-bold text-slate-700">{st.step_name}</span> ({st.step_type})
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                  {activeDraft.business_objects && activeDraft.business_objects.length > 0 && (
                    <div className="bg-white/80 p-4 rounded-xl border border-slate-200/50 sm:col-span-2">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-2">生成的数据对象 Business Objects:</span>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        {activeDraft.business_objects?.map((bo: any, idx: number) => (
                          <div key={idx} className="bg-slate-50 p-2.5 rounded-lg border border-slate-200/50">
                            <span className="font-bold text-xs text-slate-800 flex items-center gap-1"><Database className="w-3.5 h-3.5 text-indigo-500 shrink-0" /> {bo.business_object_name}</span>
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
              <div className="flex items-start justify-between gap-4 mb-6 border-b border-slate-100 pb-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h2 className="text-xl font-bold text-slate-900 tracking-tight">系统业务流程模型</h2>
                    <div className="relative group">
                      <button
                        onClick={() => setIsAddFlowModalOpen(true)}
                        className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-md transition-all shadow-sm"
                        aria-label="手动添加业务对象"
                      >
                        <Plus className="w-3.5 h-3.5" />
                      </button>
                      <div className="pointer-events-none absolute left-1/2 top-0 z-20 -translate-x-1/2 -translate-y-[calc(100%+8px)] whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[10px] font-bold text-white opacity-0 shadow-md transition-opacity group-hover:opacity-100">
                        手动组建业务流程
                      </div>
                    </div>
                    <div className="relative group">
                      <button
                        onClick={() => setAiDialogTarget({ targetType: 'flow' })}
                        className="p-1 text-slate-400 hover:text-amber-600 hover:bg-amber-50 border border-transparent hover:border-amber-100 rounded-md transition-all shadow-sm"
                        aria-label="AI 对话添加流程"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                      </button>
                      <div className="pointer-events-none absolute left-1/2 top-0 z-20 -translate-x-1/2 -translate-y-[calc(100%+8px)] whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[10px] font-bold text-white opacity-0 shadow-md transition-opacity group-hover:opacity-100">
                        AI 对话添加流程
                      </div>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => void generateFlowsAndObjects()}
                    disabled={isGenerating || isLoading}
                    className="flex items-center gap-1.5 text-[10px] bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold px-3 py-1.5 rounded-xl border border-indigo-100/80 transition-colors shadow-sm disabled:opacity-50"
                  >
                    <Sparkles className={`w-3.5 h-3.5 text-indigo-500 ${isGenerating || isLoading ? 'animate-pulse' : ''}`} />
                    AI 智能推演流程与对象
                  </button>
                </div>
              </div>

              <div className="space-y-8">
                {(!ir?.flows || ir.flows.length === 0) && (
                  <div className="text-center py-16 border-2 border-dashed border-slate-200 rounded-2xl text-slate-500 italic text-sm flex flex-col items-center justify-center gap-4 select-none">
                    <span>当前需求空间没有定义任何业务流程。您可以尝试通过 AI 智能推演生成，或者手动组建业务流程。</span>
                    <div className="relative group">
                      <button
                        onClick={() => setIsAddFlowModalOpen(true)}
                        className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-md transition-all shadow-sm"
                        aria-label="手动组建业务流程"
                      >
                        <Plus className="w-3.5 h-3.5" />
                      </button>
                      <div className="pointer-events-none absolute left-1/2 top-0 z-20 -translate-x-1/2 -translate-y-[calc(100%+8px)] whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[10px] font-bold text-white opacity-0 shadow-md transition-opacity group-hover:opacity-100">
                        手动组建首条业务流程
                      </div>
                    </div>
                  </div>
                )}

                {(ir?.flows || []).map((flow) => {
                  const featNames = (flow.featureIds || [])
                    .map(fid => (ir.features || []).find(f => f.featureId === fid)?.featureName)
                    .filter(Boolean) as string[];
                  const flowStatus = flow.confirmationStatus || flow.status || 'ai_assumption';

                  const isCollapsed = collapsedFlows[flow.flowId] === true;

                  return (
                    <div
                      key={flow.flowId}
                      id={`flow-${flow.flowId}`}
                      onClick={() => setSelectedObject(flow)}
                      className={`rounded-2xl border p-6 bg-slate-50/50 shadow-sm cursor-pointer transition-all ${
                        selectedObject?.id === flow.flowId.toString() || selectedObject?.flowId === flow.flowId
                          ? 'ring-2 ring-indigo-500 bg-slate-50 border-transparent shadow-md'
                          : 'border-slate-200 hover:border-indigo-200'
                      }`}
                    >
                      <div className={`flex flex-col gap-4 w-full ${isCollapsed ? '' : 'mb-6 pb-4 border-b border-slate-200/60'}`}>
                        <div className="space-y-3 min-w-0">
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex min-w-0 items-center gap-2">
                              <Workflow className="w-5 h-5 text-indigo-600 shrink-0" />
                              <h3 className="min-w-0 font-extrabold text-base text-slate-800">
                                <span className="block truncate">{flow.flowName}</span>
                              </h3>
                              <StatusBadge status={flowStatus} className="scale-90 origin-left shrink-0" />
                              {!isCollapsed && (
                                <div className="flex items-center gap-1.5 shrink-0" onClick={e => e.stopPropagation()}>
                                  <div className="relative group">
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setActiveFlowIdForNewStep(flow.flowId);
                                        setIsAddStepModalOpen(true);
                                      }}
                                      className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-md transition-all shadow-sm"
                                      aria-label="添加流程步骤"
                                    >
                                      <Plus className="w-3.5 h-3.5" />
                                    </button>
                                    <div className="pointer-events-none absolute left-1/2 top-0 z-20 -translate-x-1/2 -translate-y-[calc(100%+8px)] whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[10px] font-bold text-white opacity-0 shadow-md transition-opacity group-hover:opacity-100">
                                      手动添加步骤
                                    </div>
                                  </div>
                                  <div className="relative group">
                                    <button
                                      type="button"
                                      onClick={async () => {
                                        const ok = window.confirm(`确认要删除业务流程“${flow.flowName}”吗？此操作无法撤销。`);
                                        if (!ok) return;
                                        await deleteFlow(flow.flowId);
                                      }}
                                      className="p-1 hover:bg-rose-50 border border-transparent hover:border-rose-100 rounded-lg text-slate-400 hover:text-rose-600 transition-all flex items-center justify-center animate-none"
                                      aria-label="删除流程"
                                    >
                                      <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                    <div className="pointer-events-none absolute left-1/2 top-0 z-20 -translate-x-1/2 -translate-y-[calc(100%+8px)] whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[10px] font-bold text-white opacity-0 shadow-md transition-opacity group-hover:opacity-100">
                                      删除流程
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>
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
                            <div className="flex items-center gap-2 bg-indigo-50/40 border border-indigo-100/50 rounded-xl px-3 py-1.5 text-xs text-indigo-700 font-medium w-full">
                              <span className="shrink-0 flex items-center gap-1 font-extrabold text-indigo-800"><Folder className="w-3.5 h-3.5 text-indigo-500 shrink-0" /> 覆盖功能域：</span>
                              <span className="truncate font-semibold text-indigo-700">{featNames.join(' · ')}</span>
                            </div>
                          )}
                        </div>

                        {/* View Mode Toggle Switch & Manual Actions */}
                        {!isCollapsed && (() => {
                          const viewMode = flowViews[flow.flowId] || 'canvas';
                          return (
                            <div className="flex flex-wrap items-center justify-between gap-3 w-full">
                              <div className="flex bg-slate-200/80 p-0.5 rounded-lg border border-slate-300 text-[10px] font-bold shadow-inner ml-auto" onClick={(e) => e.stopPropagation()}>
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
                                  className="w-7 h-7 flex items-center justify-center rounded-lg border border-slate-200 hover:bg-slate-50 text-[10px] text-slate-600 hover:text-slate-800 transition-colors shadow-sm"
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
                                  className="w-7 h-7 flex items-center justify-center rounded-lg border border-slate-200 hover:bg-slate-50 text-[10px] text-slate-600 hover:text-slate-800 transition-colors shadow-sm"
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
                                  className="px-2 h-7 flex items-center justify-center rounded-lg border border-slate-200 hover:bg-slate-50 text-[10px] font-extrabold text-indigo-600 hover:text-indigo-700 transition-colors shadow-sm"
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

                                  const stepDetail = buildStepDetail(ir, step.stepId);
                                  const stepActors = (step.actorIds || [])
                                    .map(aid => (ir.actors || []).find(a => a.actorId === aid)?.actorName)
                                    .filter(Boolean);
                                  const stepMeta = getStepTypeMeta(step.stepType);
                                  const ioVisibleCount = stepMeta.ioVisibleCount;

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
                                      className={`absolute w-[260px] h-[148px] overflow-hidden border p-3.5 shadow-sm hover:shadow-md flex flex-col justify-between cursor-pointer group z-20 interactive-node-card ${
                                        activeDragStepId === step.stepId ? '' : 'transition-all duration-150'
                                      } ${stepMeta.shapeClass} ${
                                        isSelected
                                          ? `${stepMeta.cardClass} ${stepMeta.selectedClass} scale-[1.02]`
                                          : stepMeta.cardClass
                                      }`}
                                      style={{
                                        left: `${pos.x}px`,
                                        top: `${pos.y}px`,
                                        clipPath: stepMeta.clipPath,
                                      }}
                                    >
                                      <div className="flex justify-between items-center leading-none mb-1">
                                        <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider">Step #{idx + 1}</span>
                                        <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                                          <button
                                            type="button"
                                            onClick={async () => {
                                              const ok = window.confirm(`确认删除步骤“${step.stepName}”吗？`);
                                              if (!ok) return;
                                              await deleteFlowStep(flow.flowId, step.stepId);
                                            }}
                                            className="p-0.5 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 border border-transparent opacity-0 group-hover:opacity-100 transition-all"
                                            title="删除步骤"
                                          >
                                            <Trash2 className="w-3.5 h-3.5" />
                                          </button>
                                          <span className={`text-[10px] font-extrabold px-1.5 py-0.5 border rounded-md tracking-wide ${stepMeta.badgeClass}`}>
                                            {stepMeta.label}
                                          </span>
                                        </div>
                                      </div>

                                      <div className="min-w-0 flex-1 my-1 space-y-1">
                                        <div className="flex items-start gap-2">
                                          <span className={`mt-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-extrabold ${stepMeta.numberClass}`}>
                                            {idx + 1}
                                          </span>
                                          <div className="min-w-0 flex-1">
                                            <h4 className={`font-extrabold text-slate-800 text-xs truncate transition-colors leading-tight ${stepMeta.titleClass}`}>{step.stepName}</h4>
                                            {stepMeta.showActor && (
                                              <div className={`mt-1 text-[10px] truncate font-semibold ${stepMeta.actorToneClass}`}>
                                                <span className="flex items-center gap-1">
                                                  <User className="w-3 h-3 text-slate-400 shrink-0" />
                                                  {stepActors.length > 0 ? stepActors.join(', ') : '待绑定角色'}
                                                </span>
                                              </div>
                                            )}
                                          </div>
                                        </div>
                                        {!stepMeta.showActor && step.stepDescription && (
                                          <p className={`${stepMeta.descriptionClampClass} text-[10px] leading-relaxed text-slate-500`}>
                                            {step.stepDescription}
                                          </p>
                                        )}
                                      </div>

                                      {(stepDetail.inputs.length > 0 || stepDetail.outputs.length > 0) && (
                                        <div className="mt-1 space-y-1 border-t border-slate-100/80 pt-2">
                                          {stepDetail.inputs.length > 0 && (
                                            <div className="flex items-start gap-1.5">
                                              <span className="shrink-0 pt-0.5 text-[10px] font-extrabold text-slate-400">输入</span>
                                              <div className="min-w-0 flex flex-1 flex-nowrap gap-1 overflow-hidden">
                                                {renderIoTokens(stepDetail.inputs, 'input', ioVisibleCount)}
                                              </div>
                                            </div>
                                          )}
                                          {stepDetail.outputs.length > 0 && (
                                            <div className="flex items-start gap-1.5">
                                              <span className="shrink-0 pt-0.5 text-[10px] font-extrabold text-emerald-500">输出</span>
                                              <div className="min-w-0 flex flex-1 flex-nowrap gap-1 overflow-hidden">
                                                {renderIoTokens(stepDetail.outputs, 'output', ioVisibleCount)}
                                              </div>
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
                                const stepDetail = buildStepDetail(ir, step.stepId);
                                const stepActors = (step.actorIds || [])
                                  .map(aid => (ir.actors || []).find(a => a.actorId === aid)?.actorName)
                                  .filter(Boolean);
                                const stepMeta = getStepTypeMeta(step.stepType);

                                const isSelected = selectedObject?.id === step.stepId.toString() || selectedObject?.stepId === step.stepId;

                                return (
                                  <div key={step.stepId} className="flex items-center shrink-0">
                                    <div
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setSelectedObject(step);
                                        setHighlightTarget(step.stepId.toString());
                                      }}
                                      className={`w-[260px] border p-4 shadow-sm transition-all flex flex-col gap-3 cursor-pointer group ${stepMeta.shapeClass} ${
                                        isSelected
                                          ? `${stepMeta.cardClass} ${stepMeta.selectedClass}`
                                          : stepMeta.cardClass
                                      }`}
                                      style={{ clipPath: stepMeta.clipPath }}
                                    >
                                      <div className="flex justify-between items-start">
                                        <div className="flex items-center gap-1.5">
                                          <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${stepMeta.numberClass}`}>
                                            {idx + 1}
                                          </span>
                                          <span className={`text-[10px] font-bold px-1.5 py-0.5 border rounded ${stepMeta.badgeClass}`}>
                                            {stepMeta.label}
                                          </span>
                                        </div>

                                        <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                                          <button
                                            type="button"
                                            onClick={async () => {
                                              const ok = window.confirm(`确认删除步骤“${step.stepName}”吗？`);
                                              if (!ok) return;
                                              await deleteFlowStep(flow.flowId, step.stepId);
                                            }}
                                            className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 border border-transparent hover:border-rose-100 transition-colors"
                                            title="删除此步骤"
                                          >
                                            <Trash2 className="w-3.5 h-3.5" />
                                          </button>
                                        </div>
                                      </div>

                                      <div>
                                        <h4 className={`font-bold text-slate-800 text-sm mb-1 truncate transition-colors ${stepMeta.titleClass}`}>{step.stepName}</h4>
                                        {stepMeta.showActor && (
                                          <span className="text-[10px] font-bold text-indigo-600">
                                            <span className="flex items-center gap-1">
                                              <User className="w-3 h-3 text-slate-400 shrink-0" />
                                              {stepActors.length > 0 ? stepActors.join(', ') : '待绑定角色'}
                                            </span>
                                          </span>
                                        )}
                                      </div>

                                      <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">
                                        {step.stepDescription}
                                      </p>

                                      {/* Inputs & Outputs */}
                                      {(stepDetail.inputs.length > 0 || stepDetail.outputs.length > 0) && (
                                        <div className="border-t border-slate-100 pt-2 mt-auto space-y-1.5">
                                          {stepDetail.inputs.length > 0 && (
                                            <div className="flex flex-wrap gap-1 items-center">
                                              <span className="text-[10px] text-slate-400 font-bold shrink-0">输入:</span>
                                              {renderIoTokens(stepDetail.inputs, 'input')}
                                            </div>
                                          )}
                                          {stepDetail.outputs.length > 0 && (
                                            <div className="flex flex-wrap gap-1 items-center">
                                              <span className="text-[10px] text-slate-500 font-bold shrink-0">输出:</span>
                                              {renderIoTokens(stepDetail.outputs, 'output')}
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
                    <span className="flex items-center gap-2"><Database className="w-5 h-5 text-indigo-600 shrink-0" /> 业务数据</span>
                    <button
                      onClick={() => setIsAddBusinessObjectModalOpen(true)}
                      className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-md transition-all shadow-sm"
                      title="手动创建业务对象"
                    >
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => setAiDialogTarget({ targetType: 'business_object' })}
                      className="p-1 text-slate-400 hover:text-amber-600 hover:bg-amber-50 border border-transparent hover:border-amber-100 rounded-md transition-all shadow-sm"
                      title="AI 对话添加业务对象"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                    </button>
                  </h3>
                </div>
              </div>
              {businessObjects.length === 0 ? (
                <div className="bg-white border border-dashed border-slate-200 rounded-2xl p-8 text-center text-xs text-slate-500 shadow-sm select-none">
                  当前工作区还没有任何业务数据对象。请通过 AI 智能推演生成，或点击左上角加号手动添加。
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                  {businessObjects.map((object) => {
                    const relatedSteps = system.getRelatedStepsForObject(object.id || object.businessObjectId) as any[];
                    const stateChanges = relatedSteps
                      .flatMap((step: any) => buildStepDetail(ir, step.stepId).stateChanges)
                      .filter((value, index, array) => array.indexOf(value) === index);
                    const objectStatus = object.confirmationStatus || object.status || 'ai_assumption';

                    const isSelected = selectedObject?.businessObjectId === object.businessObjectId || selectedObject?.id === object.id?.toString();

                    return (
                      <div
                        key={object.businessObjectId || object.id}
                        id={`business_object-${object.businessObjectId || object.id}`}
                        onClick={() => setSelectedObject(object)}
                        className={`bg-white rounded-xl p-5 border transition-all cursor-pointer flex flex-col gap-4 group relative ${
                          isSelected
                            ? 'border-l-4 border-l-indigo-600 border-slate-200 shadow-md shadow-indigo-600/5'
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
                          <StatusBadge status={objectStatus} className="scale-90 origin-right shrink-0" />
                        </div>
                        <div className="text-xs text-slate-500 leading-relaxed line-clamp-3">
                          {object.businessObjectDescription || object.description || '暂无业务对象描述说明。'}
                        </div>

                        {/* Merged Related Steps and State Transitions */}
                        {(relatedSteps.length > 0 || stateChanges.length > 0) && (
                          <div className="mt-2 pt-3 border-t border-slate-100 space-y-3 shrink-0">
                            {relatedSteps.length > 0 && (
                              <div className="space-y-1.5">
                                <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">关联操作步骤</span>
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
                                      className="text-[10px] bg-slate-50 border border-slate-200 hover:border-indigo-300 hover:text-indigo-700 rounded-md px-2 py-0.5 font-medium transition-all"
                                    >
                                      ⚙️ {s.title}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            )}

                            {stateChanges.length > 0 && (
                              <div className="space-y-1.5">
                                <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">生命周期状态变迁</span>
                                <div className="flex flex-wrap gap-1">
                                  {stateChanges.map((item) => (
                                    <span
                                      key={item}
                                      className="text-[10px] bg-indigo-50 border border-indigo-100 text-indigo-700 font-extrabold px-2 py-0.5 rounded-md shadow-sm"
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
                          className="absolute right-4 bottom-4 p-1 rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-50 border border-transparent hover:border-rose-100 opacity-0 group-hover:opacity-100 transition-all shadow-sm"
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
              <h3 className="font-extrabold text-sm text-slate-800">手动创建业务对象</h3>
              <p className="text-[10px] text-slate-500 mt-1">补充系统流程中会流转的数据对象。</p>
            </div>
            <div className="p-6 space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">对象名称</label>
                <input
                  type="text"
                  value={newBusinessObjectName}
                  onChange={(e) => setNewBusinessObjectName(e.target.value)}
                  placeholder="例如：播放状态"
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">对象描述</label>
                <textarea
                  value={newBusinessObjectDesc}
                  onChange={(e) => setNewBusinessObjectDesc(e.target.value)}
                  placeholder="说明该业务对象承载的数据内容与用途"
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
                className="px-4 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors shadow-sm"
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

      {/* 手动组建业务流程 Modal */}
      {isAddFlowModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4 select-none animate-in fade-in duration-200">
          <div className="bg-white/95 border border-slate-200 shadow-2xl max-w-lg w-full flex flex-col rounded-3xl animate-in scale-in-95 duration-200 overflow-hidden">
            <div className="p-6 pb-4 border-b border-slate-100 bg-slate-50/50">
              <h3 className="font-extrabold text-sm text-slate-800">📂 手动组建业务流程</h3>
              <p className="text-[10px] text-slate-500 mt-1">创建一条核心业务流转主线，并关联相应的叶子功能（Leaf Features）。</p>
            </div>
            <div className="p-6 space-y-4 max-h-[60vh] overflow-y-auto">
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">流程名称</label>
                <input
                  type="text"
                  value={newFlowName}
                  onChange={(e) => setNewFlowName(e.target.value)}
                  placeholder="例如：本地歌词匹配流程"
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">流程描述</label>
                <textarea
                  value={newFlowDesc}
                  onChange={(e) => setNewFlowDesc(e.target.value)}
                  placeholder="说明该流程的业务目标、参与者和关键流转"
                  rows={3}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium resize-none leading-relaxed"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">
                  关联业务功能域 (仅限勾选叶子功能)
                </label>
                <div className="space-y-2 border border-slate-200/50 rounded-xl p-3 bg-slate-50 max-h-[180px] overflow-y-auto">
                  {(ir?.features || []).length === 0 ? (
                    <div className="text-xs text-slate-400 italic">当前工作区暂无任何功能模块。</div>
                  ) : (
                    (ir.features || []).map((feat: any) => {
                      const isLeaf = !feat.childrenIds || feat.childrenIds.length === 0;
                      const pathStr = getFeaturePath(feat.featureId, ir.features || []);

                      return (
                        <label
                          key={feat.featureId}
                          className={`flex items-center space-x-2 text-xs font-semibold select-none leading-relaxed ${
                            isLeaf ? 'text-slate-700 cursor-pointer hover:text-indigo-600' : 'text-slate-400 cursor-not-allowed opacity-60'
                          }`}
                        >
                          <input
                            type="checkbox"
                            disabled={!isLeaf}
                            checked={newFlowFeatureIds.includes(feat.featureId)}
                            onChange={(e) => {
                              if (!isLeaf) return;
                              if (e.target.checked) {
                                setNewFlowFeatureIds([...newFlowFeatureIds, feat.featureId]);
                              } else {
                                setNewFlowFeatureIds(newFlowFeatureIds.filter(id => id !== feat.featureId));
                              }
                            }}
                            className="w-3.5 h-3.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 disabled:opacity-50"
                          />
                          <span>{pathStr}</span>
                          {!isLeaf && (
                            <span className="text-[10px] text-slate-400 font-bold ml-1.5">(父级分类，不可选)</span>
                          )}
                        </label>
                      );
                    })
                  )}
                </div>
              </div>
            </div>
            <div className="p-6 pt-4 border-t border-slate-100 flex justify-end gap-2 bg-slate-50/30">
              <button
                onClick={() => {
                  setIsAddFlowModalOpen(false);
                  setNewFlowName('');
                  setNewFlowDesc('');
                  setNewFlowFeatureIds([]);
                }}
                className="px-4 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors shadow-sm"
              >
                取消
              </button>
              <button
                onClick={async () => {
                  if (!newFlowName.trim()) return;
                  await addFlow(newFlowName.trim(), newFlowDesc.trim(), newFlowFeatureIds);
                  setIsAddFlowModalOpen(false);
                  setNewFlowName('');
                  setNewFlowDesc('');
                  setNewFlowFeatureIds([]);
                }}
                disabled={!newFlowName.trim()}
                className="px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50"
              >
                确定创建
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 手动添加步骤 Modal */}
      {isAddStepModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4 select-none animate-in fade-in duration-200">
          <div className="bg-white/95 border border-slate-200 shadow-2xl max-w-lg w-full flex flex-col rounded-3xl animate-in scale-in-95 duration-200 overflow-hidden">
            <div className="p-6 pb-4 border-b border-slate-100 bg-slate-50/50">
              <h3 className="font-extrabold text-sm text-slate-800">手动添加流程步骤</h3>
              <p className="text-[10px] text-slate-500 mt-1">为当前流程补充步骤、参与者、输入对象与输出对象。</p>
            </div>
            <div className="p-6 space-y-4 max-h-[60vh] overflow-y-auto">
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">步骤名称 (必填)</label>
                <input
                  type="text"
                  value={newStepName}
                  onChange={(e) => setNewStepName(e.target.value)}
                  placeholder="例如：选择本地歌词目录"
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">步骤执行类型 (必填)</label>
                <select
                  value={newStepType}
                  onChange={(e) => setNewStepType(e.target.value as any)}
                  className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-semibold"
                >
                  <option value="actorAction">用户参与者交互步骤 (actorAction)</option>
                  <option value="systemAction">系统后台自动步骤 (systemAction)</option>
                  <option value="judgment">逻辑分支判定步骤 (judgment)</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">步骤描述</label>
                <textarea
                  value={newStepDesc}
                  onChange={(e) => setNewStepDesc(e.target.value)}
                  placeholder="说明该步骤的触发条件、处理动作和产出"
                  rows={2}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium resize-none leading-relaxed"
                />
              </div>

              {/* Actors Checklist */}
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">
                  参与执行参与者 {newStepType === 'actorAction' && <span className="text-amber-600 font-bold">(交互步骤必选)</span>}
                </label>
                <div className="space-y-2 border border-slate-200/50 rounded-xl p-3 bg-slate-50 max-h-[110px] overflow-y-auto">
                  {(ir?.actors || []).length === 0 ? (
                    <div className="text-xs text-slate-400 italic">暂无可用参与者，请在 What 阶段定义。</div>
                  ) : (
                    (ir.actors || []).map((actor: any) => (
                      <label key={actor.actorId} className="flex items-center space-x-2 text-xs font-semibold text-slate-700 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={newStepActorIds.includes(actor.actorId)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setNewStepActorIds([...newStepActorIds, actor.actorId]);
                            } else {
                              setNewStepActorIds(newStepActorIds.filter(id => id !== actor.actorId));
                            }
                          }}
                          className="w-3.5 h-3.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span>{actor.actorName}</span>
                      </label>
                    ))
                  )}
                </div>
              </div>

              {/* Inputs Checklist */}
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">输入业务对象</label>
                <div className="space-y-2 border border-slate-200/50 rounded-xl p-3 bg-slate-50 max-h-[110px] overflow-y-auto">
                  {(ir?.businessObjects || []).length === 0 ? (
                    <div className="text-xs text-slate-400 italic">暂无可用业务数据对象。</div>
                  ) : (
                    (ir.businessObjects || []).map((bo: any) => (
                      <label key={bo.businessObjectId} className="flex items-center space-x-2 text-xs font-semibold text-slate-700 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={newStepInputBoIds.includes(bo.businessObjectId)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setNewStepInputBoIds([...newStepInputBoIds, bo.businessObjectId]);
                            } else {
                              setNewStepInputBoIds(newStepInputBoIds.filter(id => id !== bo.businessObjectId));
                            }
                          }}
                          className="w-3.5 h-3.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span>{bo.businessObjectName}</span>
                      </label>
                    ))
                  )}
                </div>
              </div>

              {/* Outputs Checklist */}
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">输出业务对象</label>
                <div className="space-y-2 border border-slate-200/50 rounded-xl p-3 bg-slate-50 max-h-[110px] overflow-y-auto">
                  {(ir?.businessObjects || []).length === 0 ? (
                    <div className="text-xs text-slate-400 italic">暂无可用业务数据对象。</div>
                  ) : (
                    (ir.businessObjects || []).map((bo: any) => (
                      <label key={bo.businessObjectId} className="flex items-center space-x-2 text-xs font-semibold text-slate-700 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={newStepOutputBoIds.includes(bo.businessObjectId)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setNewStepOutputBoIds([...newStepOutputBoIds, bo.businessObjectId]);
                            } else {
                              setNewStepOutputBoIds(newStepOutputBoIds.filter(id => id !== bo.businessObjectId));
                            }
                          }}
                          className="w-3.5 h-3.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span>{bo.businessObjectName}</span>
                      </label>
                    ))
                  )}
                </div>
              </div>
            </div>
            <div className="p-6 pt-4 border-t border-slate-100 flex justify-end gap-2 bg-slate-50/30">
              <button
                onClick={() => {
                  setIsAddStepModalOpen(false);
                  setActiveFlowIdForNewStep(null);
                  setNewStepName('');
                  setNewStepDesc('');
                  setNewStepType('actorAction');
                  setNewStepActorIds([]);
                  setNewStepInputBoIds([]);
                  setNewStepOutputBoIds([]);
                }}
                className="px-4 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors shadow-sm"
              >
                取消
              </button>
              <button
                onClick={async () => {
                  if (!newStepName.trim()) return;
                  if (newStepType === 'actorAction' && newStepActorIds.length === 0) {
                    alert('用户参与者交互步骤必须勾选至少一个参与者！');
                    return;
                  }
                  if (activeFlowIdForNewStep === null) return;
                  await addFlowStep(activeFlowIdForNewStep, {
                    stepName: newStepName.trim(),
                    stepDescription: newStepDesc.trim(),
                    stepType: newStepType,
                    actorIds: newStepActorIds,
                    inputBusinessObjectIds: newStepInputBoIds,
                    outputBusinessObjectIds: newStepOutputBoIds,
                  });
                  setIsAddStepModalOpen(false);
                  setActiveFlowIdForNewStep(null);
                  setNewStepName('');
                  setNewStepDesc('');
                  setNewStepType('actorAction');
                  setNewStepActorIds([]);
                  setNewStepInputBoIds([]);
                  setNewStepOutputBoIds([]);
                }}
                disabled={!newStepName.trim()}
                className="px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50"
              >
                确定添加
              </button>
            </div>
          </div>
        </div>
      )}

      <DraftPreviewModal
        draft={activeDraft}
        draftType={activeDraftType}
        isWorking={isGenerating || isLoading}
        onDiscard={() => {
          if (activeDraftType === 'repair') {
            const dId = activeDraft?.draftId || activeDraft?.draft_id;
            if (dId) discardRepairDraft(dId);
          } else {
            discardDraft();
          }
        }}
        onRegenerate={(feedback) => {
          if (activeDraftType === 'repair') {
            const dId = activeDraft?.draftId || activeDraft?.draft_id;
            if (dId) regenerateRepairDraft(dId);
          } else {
            regenerateFlowsAndObjects(feedback)
          };
        }}
        onConfirm={async () => {
          if (activeDraftType === 'repair') {
            const dId = activeDraft?.draftId || activeDraft?.draft_id;
            if (dId) await confirmRepairDraft(dId);
          } else {
            await confirmFlowsAndObjects();
          }
        }}
      />

      {/* BO Reference Deletion Warning Modal Dialog */}
      {boDeletionError && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4 select-none animate-in fade-in duration-200">
          <div className="bg-white/95 border border-rose-100 shadow-2xl max-w-md w-full flex flex-col rounded-3xl animate-in scale-in-95 duration-200 overflow-hidden">
            <div className="p-6 pb-4 border-b border-rose-50 bg-rose-50/20 flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-rose-100/80 flex items-center justify-center text-rose-600">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-extrabold text-sm text-slate-800">业务对象删除受阻</h3>
                <p className="text-[10px] text-slate-500 mt-0.5">该对象正在被流程步骤引用。</p>
              </div>
            </div>
            <div className="p-6 space-y-4">
              <div className="p-4 bg-slate-50 border border-slate-100 rounded-2xl text-xs text-slate-600 leading-relaxed font-medium">
                {boDeletionError}
              </div>
            </div>
            <div className="p-4 bg-slate-50/50 border-t border-slate-100 flex justify-end">
              <button
                type="button"
                onClick={() => setBoDeletionError(null)}
                className="px-5 py-2 rounded-xl text-xs font-bold text-white bg-slate-800 hover:bg-slate-700 active:scale-95 transition-all shadow-md shadow-slate-200/80"
              >
                我明白了
              </button>
            </div>
          </div>
        </div>
      )}

      <AIAddObjectDialog
        isOpen={isAIDialogOpen}
        onClose={() => setAiDialogTarget(null)}
        projectId={ir?.projectId ?? 0}
        targetType={aiDialogTarget?.targetType ?? 'actor'}
        anchor={aiDialogTarget?.anchor}
        onConfirm={async () => {
          setAiDialogTarget(null);
          const { refreshWorkspace } = useWorkspaceStore.getState();
          await refreshWorkspace();
        }}
      />

      <ConfirmTransitionModal
        isOpen={isTransitionModalOpen}
        onClose={() => setIsTransitionModalOpen(false)}
        stage="how"
        isWorking={isLoading}
        onAIDiagnose={async () => {
          setIsTransitionModalOpen(false);
          await runDiagnosis();
        }}
        onForceUnlock={async () => {
          setIsTransitionModalOpen(false);
          await unlockStageGate('how');
          navigate(buildProjectRoute(ir?.projectId, '/scope'));
        }}
      />

      <ChoiceGroupPreviewModal
        group={activeChoiceGroup}
        isWorking={isGeneratingChoices || isLoading}
        isGeneratingChoices={isGeneratingChoices}
        generationProgress={choiceGroupGenerationProgress}
        onAccept={async (choiceId) => {
          await acceptChoice(choiceId);
        }}
        onDiscard={async () => {
          if (activeChoiceGroup) {
            await discardChoiceGroup(activeChoiceGroup.id);
          }
        }}
        onDefer={() => useWorkspaceStore.setState({ activeChoiceGroup: null })}
      />

      <RightObjectPanel />
    </div>
  );
}

