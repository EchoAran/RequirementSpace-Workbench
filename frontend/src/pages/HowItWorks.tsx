import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { DraftPreviewModal } from '@/components/shared/DraftPreviewModal';
import { useNavigate, useLocation } from 'react-router-dom';
import { Workflow, GitBranch, Sparkles, Check, X, RefreshCw, ChevronDown, ChevronRight, Plus, Trash2, AlertTriangle, AlertCircle, Database, User, Folder, Maximize2, ShieldCheck } from 'lucide-react';
import { buildProjectRouteWithBranch, buildStepDetail, selectFlowSummary } from '@/core/selectors';
import { useLocalStorageState } from '@/lib/useLocalStorageState';
import { StageGuidanceBanner } from '@/components/shared/StageGuidanceBanner';
import { ConfirmTransitionModal } from '@/components/shared/ConfirmTransitionModal';
import { AIAddObjectDialog, type AIAddTargetType } from '@/components/shared/AIAddObjectDialog';
import { StatusBadge } from '@/components/shared/StatusBadge';
import {
  useWorkspaceStore,
  selectSelectedObject,
} from '@/store/useWorkspaceStore';
import { GlassSurface } from '@/components/ui/GlassSurface';
import { EmptyGuidance } from '@/components/ui/EmptyGuidance';
import { ChoiceGroupPreviewModal } from '@/components/shared/ChoiceGroupPreviewModal';
import { FocusFlowCanvasModal } from '@/components/shared/FocusFlowCanvasModal';
import { RuleSection } from '@/components/how/RuleSection';
import { FlowDraftCanvas } from '@/components/how/flow_canvas/FlowDraftCanvas';
import type { ActorNode, BusinessObjectNode, FeatureNode } from '@/core/schema';


// Cycle-safe dynamic grid positioning algorithm for DAG visualization
const computeStepPositions = (steps: any[], transitions: any[] = []) => {
  const positions: Record<number, { x: number; y: number }> = {};
  if (steps.length === 0) return positions;

  const colWidth = 330;
  const rowHeight = 180;
  const visited = new Set<number>();

  // Determine starting nodes (nodes that are not targets of any transition)
  const allTargetIds = new Set(transitions.map((t: any) => t.targetStepId));
  const startNodes = steps.filter((s: any) => !allTargetIds.has(s.stepId));

  // BFS Queue: { stepId, col, row }
  const queue: { stepId: number; col: number; row: number }[] = [];
  if (startNodes.length > 0) {
    startNodes.forEach((sn, idx) => queue.push({ stepId: sn.stepId, col: 0, row: idx }));
  } else {
    queue.push({ stepId: steps[0].stepId, col: 0, row: 0 });
  }

  const colOccupancy: Record<number, number> = {};

  while (queue.length > 0) {
    const { stepId, col } = queue.shift()!;
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

    const outgoing = transitions.filter((t: any) => t.sourceStepId === stepId);
    outgoing.forEach((tr: any, idx: number) => {
      if (!visited.has(tr.targetStepId)) {
        // Spread branches vertically
        queue.push({ stepId: tr.targetStepId, col: col + 1, row: idx });
      }
    });
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
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const {
    setSelectedObject,
    setHighlightTarget,
    generateFlows,
    regenerateFlows,
    confirmFlowDraft,
    loadFlowObjectUsage,
    flowObjectUsages,
    flowObjectUsageLoading,
    flowObjectUsageErrors,
    discardDraft,
    activeDraft,
    activeDraftType,
    isGenerating,
    isLoading,
    addBusinessObject,
    boDeletionError,
    setBoDeletionError,
    addFlow,
    updateFlow,
    deleteFlow,
    addFlowStep,
    updateFlowStep,
    deleteFlowStep,
    createFlowTransition,
    updateFlowTransition,
    deleteFlowTransition,
    runDiagnosis,
    requestStageTransition,
    confirmRepairDraft,
    discardRepairDraft,
    regenerateRepairDraft,
    activeChoiceGroup,
    isGeneratingChoices,
    choiceGroupGenerationProgress,
    acceptChoice,
    discardChoiceGroup,
    workspaceCanWrite,
  } = useWorkspaceStore();

  const isReadOnly = typeof workspaceCanWrite === 'function' ? !workspaceCanWrite() : false;

  const [flowFeedback, setFlowFeedback] = useState('');
  const [isTransitionModalOpen, setIsTransitionModalOpen] = useState(false);
  const [focusFlowId, setFocusFlowId] = useState<number | null>(null);
  const [focusStepId, setFocusStepId] = useState<number | null>(null);
  const [focusTransitionId, setFocusTransitionId] = useState<string | number | null>(null);

  // Resolve deep-link targets supplied by the overview and issue panels.
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

  const ir = useWorkspaceStore(state => state.ir);
  const highlightTarget = useWorkspaceStore(state => state.highlightTarget);

  useEffect(() => {
    if (!highlightTarget || !ir) return;

    // Check if highlightTarget matches a DomainRule
    const rule = (ir.domainRules || []).find(
      (r: any) => String(r.id || r.ruleId) === highlightTarget || r.logicalUuid === highlightTarget
    );
    if (rule) {
      const el = document.getElementById(`rule-card-${rule.id}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      return;
    }

    // Check if highlightTarget matches a Flow
    const flow = (ir.flows || []).find(
      (f: any) => String(f.flowId) === highlightTarget || f.logicalUuid === highlightTarget
    );
    if (flow) {
      const el = document.getElementById(`flow-${flow.flowId}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      return;
    }

    // Check if highlightTarget matches a Flow Step
    for (const f of ir.flows || []) {
      const step = (f.flowSteps || []).find(
        (s: any) => String(s.stepId) === highlightTarget || s.logicalUuid === highlightTarget
      );
      if (step) {
        setFocusFlowId(f.flowId);
        setFocusStepId(step.stepId);
        setFocusTransitionId(null);
        return;
      }
    }

    // Check if highlightTarget matches a Flow Transition
    for (const f of ir.flows || []) {
      const tr = (f.transitions || []).find(
        (t: any) => String(t.transitionId || t.id) === highlightTarget || t.logicalUuid === highlightTarget
      );
      if (tr) {
        setFocusFlowId(f.flowId);
        setFocusStepId(null);
        setFocusTransitionId(String(tr.transitionId || tr.id));
        return;
      }
    }
  }, [highlightTarget, ir]);
  const selectedObject = useWorkspaceStore(selectSelectedObject);
  const [panZoomState, setPanZoomState] = useState<Record<number, { scale: number; x: number; y: number }>>({});
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [activeDragFlowId, setActiveDragFlowId] = useState<number | null>(null);
  const [selectedPathId, setSelectedPathId] = useState<string | null>(null);

  // Fold/Collapse state for flows
  const [collapsedFlows, setCollapsedFlows] = useLocalStorageState<Record<number, boolean>>(`how-collapsed-flows-${ir?.projectId ?? ''}`, {});

  // Fold/Collapse state for per-flow business object sections
  const [collapsedBoSections, setCollapsedBoSections] = useLocalStorageState<Record<number, boolean>>(`how-collapsed-bo-sections-${ir?.projectId ?? ''}`, {});

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

  // Load flow object usages for expanded flows
  useEffect(() => {
    if (ir?.flows) {
      ir.flows.forEach((fl) => {
        if (!collapsedFlows[fl.flowId]) {
          void loadFlowObjectUsage(fl.flowId).catch(() => {});
        }
      });
    }
  }, [ir?.flows, collapsedFlows, loadFlowObjectUsage]);

  // Open editors participate in the branch-switch dirty-state contract.
  const setEditDirty = useWorkspaceStore((s) => s.setEditDirty);
  useEffect(() => {
    setEditDirty(
      isAddBusinessObjectModalOpen ||
        isAddFlowModalOpen ||
        isAddStepModalOpen ||
        isTransitionModalOpen ||
        isAIDialogOpen
    );
  }, [
    isAddBusinessObjectModalOpen,
    isAddFlowModalOpen,
    isAddStepModalOpen,
    isTransitionModalOpen,
    isAIDialogOpen,
    setEditDirty,
  ]);

  // Discarding a branch switch closes editors and clears their local state.
  const editDiscardVersion = useWorkspaceStore((s) => s.editDiscardVersion);
  useEffect(() => {
    if (editDiscardVersion === 0) return;
    setIsAddBusinessObjectModalOpen(false);
    setIsAddFlowModalOpen(false);
    setIsAddStepModalOpen(false);
    setIsTransitionModalOpen(false);
    setAiDialogTarget(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editDiscardVersion]);

  // Draggable steps (repositioning nodes)
  const [customStepPositions, setCustomStepPositions] = useState<Record<number, { x: number; y: number }>>({});
  const [activeDragStepId, setActiveDragStepId] = useState<number | null>(null);
  const [stepDragStart, setStepDragStart] = useState<{ mouseX: number; mouseY: number; initialX: number; initialY: number } | null>(null);

  const getStepTypeMeta = (stepType: 'actorAction' | 'systemAction' | 'judgment') => {
    if (stepType === 'judgment') {
      return {
        label: t('how.branchNode'),
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
        label: t('how.stepType.systemAction'),
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
      label: t('how.stepType.actorAction'),
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
          <h3 className="text-lg font-black text-slate-900 tracking-tight">{t('how.dependenciesTitle')}</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
            {t('how.dependenciesDescription')}
            </p>
            <p className="text-xs text-slate-400 leading-relaxed bg-slate-50 p-3 rounded-xl border border-slate-100/60">
            {t('how.dependenciesAction')}
            </p>
          </div>
          <button
            onClick={() => navigate(buildProjectRouteWithBranch(ir?.projectId, '/what', useWorkspaceStore.getState().branchRef))}
            className="w-full py-2.5 px-4 rounded-xl bg-slate-900 text-white text-xs font-bold hover:bg-slate-800 transition-colors shadow-sm"
          >
            {t('how.goToWhat')}
          </button>
        </div>
      </div>
    );
  }

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
        <div className="w-full max-w-7xl 2xl:max-w-[1720px] 3xl:max-w-[1920px] mx-auto animate-in fade-in duration-500 space-y-8">

          <div className="flex flex-col gap-6 h-full content-start">

            <StageGuidanceBanner stage="how" />

            {/* Domain Rules Space */}
            <RuleSection readOnly={isReadOnly} />

            {/* System Business Flow Models */}
            <GlassSurface className="p-6 relative w-full">
              <div className="flex items-start justify-between gap-4 mb-6 border-b border-slate-200/50 pb-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-sm font-bold text-slate-800 uppercase tracking-widest flex items-center gap-2">{t('how.title')}</h3>
                    {!isReadOnly && (
                      <>
                        <div className="relative group">
                          <button
                            onClick={() => setIsAddFlowModalOpen(true)}
                            className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-lg transition-all shadow-2xs cursor-pointer"
                            aria-label={t('how.manualFlowBtn')}
                          >
                            <Plus className="w-3.5 h-3.5" />
                          </button>
                        </div>
                        <div
                          className="relative group"
                          title={(ir?.domainRules || []).length === 0 ? t('how.domainRules.ruleRequiredForFlow') : undefined}
                        >
                          <button
                            onClick={() => setAiDialogTarget({ targetType: 'flow' })}
                            disabled={(ir?.domainRules || []).length === 0}
                            className="p-1 text-slate-400 hover:text-amber-600 hover:bg-amber-50 border border-transparent hover:border-amber-100 rounded-lg transition-all shadow-2xs cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                            aria-label={t('how.aiChatFlowBtn')}
                          >
                            <Sparkles className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {(() => {
                    const hasDomainRules = (ir?.domainRules || []).length > 0;
                    return (
                      <>
                        <div className="relative group" title={!hasDomainRules ? t('how.domainRules.ruleRequiredForFlow') : undefined}>
                          <button
                            onClick={() => void generateFlows()}
                            disabled={isGenerating || isLoading || !hasDomainRules || isReadOnly}
                            className="flex items-center gap-1.5 text-[10px] bg-indigo-50/80 hover:bg-indigo-100/80 text-indigo-700 font-bold px-3 py-1.5 rounded-xl border border-indigo-200/60 transition-all shadow-2xs disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                          >
                            <Sparkles className={`w-3.5 h-3.5 text-indigo-500 ${isGenerating || isLoading ? 'animate-pulse' : ''}`} />
                            {(ir?.flows || []).length > 0 ? t('how.regenerateBtn') : t('how.generateBtn')}
                          </button>
                        </div>
                      </>
                    );
                  })()}
                </div>
              </div>

              <div className="space-y-6">
                {(!ir?.flows || ir.flows.length === 0) && (ir?.domainRules || []).length > 0 && (
                  <EmptyGuidance
                    title={t('how.emptyTip')}
                    actionLabel={!isReadOnly ? t('how.generateBtn') : undefined}
                    onAction={!isReadOnly ? () => void generateFlows() : undefined}
                  />
                )}

                {(ir?.flows || []).map((flow) => {
                  const featNames = (flow.featureIds || [])
                    .map(fid => (ir?.features || []).find(f => f.featureId === fid)?.featureName)
                    .filter(Boolean) as string[];
                  const flowStatus = flow.confirmationStatus || flow.status || 'ai_assumption';

                  const isCollapsed = collapsedFlows[flow.flowId] === true;

                  return (
                    <div
                      key={flow.flowId}
                      id={`flow-${flow.flowId}`}
                      onClick={() => setSelectedObject(flow)}
                      className={`rounded-2xl border p-6 bg-slate-50/50 shadow-sm cursor-pointer transition-all ${
                        selectedObject?.id === flow.flowId?.toString() || selectedObject?.flowId === flow.flowId
                          ? 'ring-2 ring-indigo-500 bg-slate-50 border-transparent shadow-md'
                          : 'border-slate-200 hover:border-indigo-200'
                      }`}
                    >
                      <div className={`flex flex-col gap-4 w-full ${isCollapsed ? '' : 'mb-6 pb-4 border-b border-slate-200/60'}`}>
                        <div className="space-y-3 min-w-0">
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex min-w-0 items-center gap-2">
                              <Workflow className="w-5 h-5 text-indigo-600 shrink-0" />
                              <h3 className="min-w-0 font-bold text-base text-slate-900 tracking-tight">
                                <span className="block truncate">{flow.flowName}</span>
                              </h3>
                              <StatusBadge status={flowStatus} className="scale-90 origin-left shrink-0" />
                              {!isCollapsed && !isReadOnly && (
                                <div className="flex items-center gap-1.5 shrink-0" onClick={e => e.stopPropagation()}>
                                  <div className="relative group">
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setActiveFlowIdForNewStep(flow.flowId);
                                        setIsAddStepModalOpen(true);
                                      }}
                                      className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-lg transition-all shadow-2xs cursor-pointer"
                                      aria-label={t('how.addStepBtn')}
                                    >
                                      <Plus className="w-3.5 h-3.5" />
                                    </button>
                                    <div className="pointer-events-none absolute left-1/2 top-0 z-20 -translate-x-1/2 -translate-y-[calc(100%+8px)] whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[10px] font-bold text-white opacity-0 shadow-md transition-opacity group-hover:opacity-100">
                                      {t('how.addStepBtn')}
                                    </div>
                                  </div>
                                  <div className="relative group">
                                    <button
                                      type="button"
                                      onClick={async () => {
                                        const ok = window.confirm(t('how.deleteConfirm', { name: flow.flowName }));
                                        if (!ok) return;
                                        await deleteFlow(flow.flowId);
                                      }}
                                      className="p-1 hover:bg-rose-50 border border-transparent hover:border-rose-100 rounded-lg text-slate-400 hover:text-rose-600 transition-all flex items-center justify-center cursor-pointer shadow-2xs"
                                      aria-label={t('how.deleteBtn')}
                                    >
                                      <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                    <div className="pointer-events-none absolute left-1/2 top-0 z-20 -translate-x-1/2 -translate-y-[calc(100%+8px)] whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[10px] font-bold text-white opacity-0 shadow-md transition-opacity group-hover:opacity-100">
                                      {t('how.deleteBtn')}
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>
                            <button
                              type="button"
                              aria-expanded={!isCollapsed}
                              aria-controls={`flow-content-${flow.flowId}`}
                              onClick={(e) => {
                                e.stopPropagation();
                                setCollapsedFlows(prev => ({ ...prev, [flow.flowId]: !prev[flow.flowId] }));
                              }}
                              className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all shrink-0 cursor-pointer"
                              title={isCollapsed ? t('how.expandBtn') : t('how.collapseBtn')}
                            >
                              {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                            </button>
                          </div>
                          <p className="text-xs text-slate-500 leading-relaxed">{flow.flowDescription}</p>
                          {(() => {
                            const summary = selectFlowSummary(flow, ir?.domainRules || [], (ir?.findings as any) || []);
                            const totalFindings = summary.blockingFindingsCount + summary.warningFindingsCount;
                            return (
                              <div className="flex flex-wrap items-center gap-2 pt-1">
                                <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700 border border-slate-200/70">
                                  <Workflow className="w-3 h-3 text-indigo-600" />
                                  {summary.stepCount} {t('how.summary.steps', '步骤')}
                                </span>
                                <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700 border border-slate-200/70">
                                  <GitBranch className="w-3 h-3 text-indigo-600" />
                                  {summary.transitionCount} {t('how.summary.transitions', '分支流转')}
                                </span>
                                <span className="inline-flex items-center gap-1 rounded-md bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-800 border border-amber-200/70">
                                  <ShieldCheck className="w-3 h-3 text-amber-600" />
                                  {summary.ruleCount} {t('how.summary.rules', '关联规则')}
                                </span>
                                <span className="inline-flex items-center gap-1 rounded-md bg-sky-50 px-2 py-0.5 text-[10px] font-semibold text-sky-800 border border-sky-200/70">
                                  <Database className="w-3 h-3 text-sky-600" />
                                  {summary.boCount} {t('how.summary.objects', '涉及对象')}
                                </span>
                                {totalFindings > 0 && (
                                  <span
                                    className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-semibold border ${
                                      summary.blockingFindingsCount > 0
                                        ? 'bg-rose-50 text-rose-700 border-rose-200'
                                        : 'bg-amber-50 text-amber-700 border-amber-200'
                                    }`}
                                  >
                                    <AlertTriangle className="w-3 h-3" />
                                    {summary.blockingFindingsCount > 0
                                      ? `${summary.blockingFindingsCount} ${t('how.summary.blockingIssues', '阻断问题')}`
                                      : `${summary.warningFindingsCount} ${t('how.summary.warnings', '质量告警')}`}
                                  </span>
                                )}
                              </div>
                            );
                          })()}
                          {featNames.length > 0 && (
                            <div className="flex items-center gap-2 bg-indigo-50/40 border border-indigo-100/50 rounded-xl px-3 py-1.5 text-xs text-indigo-700 font-medium w-full">
                              <span className="shrink-0 flex items-center gap-1 font-extrabold text-indigo-800"><Folder className="w-3.5 h-3.5 text-indigo-500 shrink-0" /> {t('how.flowBindFeaturesLabel')}</span>
                              <span className="truncate font-semibold text-indigo-700">{featNames.join(' · ')}</span>
                            </div>
                          )}
                        </div>

                      </div>

                      {/* Canonical flow canvas */}
                      {!isCollapsed && (
                        <div id={`flow-content-${flow.flowId}`}>
                          {(() => {
                            const steps = flow.flowSteps || [];

                            const positions = computeStepPositions(steps, flow.transitions || []);
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
                                  title={t('how.zoomOut')}
                                  className="w-7 h-7 flex items-center justify-center rounded-lg border border-slate-200 hover:bg-slate-50 text-[10px] text-slate-600 hover:text-slate-800 transition-colors shadow-sm"
                                >
          {t('how.zoomOut')}
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
                                  title={t('how.zoomIn')}
                                  className="w-7 h-7 flex items-center justify-center rounded-lg border border-slate-200 hover:bg-slate-50 text-[10px] text-slate-600 hover:text-slate-800 transition-colors shadow-sm"
                                >
          {t('how.zoomIn')}
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
                                  title={t('how.fitView')}
                                  className="px-2 h-7 flex items-center justify-center rounded-lg border border-slate-200 hover:bg-slate-50 text-[10px] font-extrabold text-indigo-600 hover:text-indigo-700 transition-colors shadow-sm"
                                >
          {t('how.fitView')}
                                </button>
                                <div className="w-[1px] h-4 bg-slate-200 mx-1"></div>
                                <button
                                  type="button"
                                  onClick={() => setFocusFlowId(flow.flowId)}
                                  title={t('how.focusModeTooltip', '放大为独立全屏画布，编辑步骤与连接点')}
                                  className="px-2 h-7 flex items-center gap-1 rounded-lg border border-indigo-200 bg-indigo-50 hover:bg-indigo-100 text-[10px] font-extrabold text-indigo-700 transition-colors shadow-sm cursor-pointer"
                                >
                                  <Maximize2 className="w-3 h-3" />
                                  {t('how.focusMode', '全屏专注')}
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
                                  {(flow.transitions || []).map((tr: any) => {
                                    const fromPos = customStepPositions[tr.sourceStepId] || positions[tr.sourceStepId];
                                    const toPos = customStepPositions[tr.targetStepId] || positions[tr.targetStepId];
                                    if (!fromPos || !toPos) return null;

                                    // Always exit from right port of source, enter left port of target
                                    const startX = fromPos.x + 260;
                                    const startY = fromPos.y + 65;
                                    const endX = toPos.x;
                                    const endY = toPos.y + 65;

                                    let pathD = '';
                                    if (endX <= startX) {
                                      // Loopback / backward curve: exits right, loops above, enters left
                                      const midX = (startX + endX) / 2;
                                      const arcOffset = Math.max(75, Math.abs(startX - endX) * 0.2);
                                      const controlY = Math.min(startY, endY) - arcOffset;
                                      pathD = `M ${startX} ${startY} C ${startX + 80} ${startY}, ${startX + 40} ${controlY}, ${midX} ${controlY} S ${endX - 80} ${endY}, ${endX} ${endY}`;
                                    } else {
                                      // Standard forward curve: exits right, enters left
                                      const cp1X = startX + Math.min(80, (endX - startX) * 0.5);
                                      const cp1Y = startY;
                                      const cp2X = endX - Math.min(80, (endX - startX) * 0.5);
                                      const cp2Y = endY;
                                      pathD = `M ${startX} ${startY} C ${cp1X} ${cp1Y}, ${cp2X} ${cp2Y}, ${endX} ${endY}`;
                                    }

                                    const pathId = `${tr.sourceStepId}-${tr.targetStepId}`;
                                    const isPathSelected = selectedPathId === pathId;
                                    const isStepRelated = selectedObject && (
                                      selectedObject.stepId === tr.sourceStepId ||
                                      selectedObject.stepId === tr.targetStepId ||
                                      selectedObject.id === tr.sourceStepId.toString() ||
                                      selectedObject.id === tr.targetStepId.toString()
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
                                  })}
                                </svg>

                                {/* Absolutely Positioned Interactive Node Cards */}
                                {steps.map((step, idx) => {
                                  const pos = customStepPositions[step.stepId] || positions[step.stepId];
                                  if (!pos) return null;

                                  const stepDetail = buildStepDetail(ir, step.stepId);
                                  const stepActors = (step.actorIds || [])
                                    .map(aid => (ir?.actors || []).find(a => a.actorId === aid)?.actorName)
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
                                              const ok = window.confirm(t('how.stepDeleteConfirm', { name: step.stepName }));
                                              if (!ok) return;
                                              await deleteFlowStep(flow.flowId, step.stepId);
                                            }}
                                            className="p-0.5 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 border border-transparent opacity-0 group-hover:opacity-100 transition-all"
                                            title={t('how.deleteStepBtn')}
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
                                                  {stepActors.length > 0 ? stepActors.join(', ') : t('how.bindActorPlaceholder')}
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
                                              <span className="shrink-0 pt-0.5 text-[10px] font-extrabold text-slate-400">{t('how.stepInputBoLabel')}</span>
                                              <div className="min-w-0 flex flex-1 flex-nowrap gap-1 overflow-hidden">
                                                {renderIoTokens(stepDetail.inputs, 'input', ioVisibleCount)}
                                              </div>
                                            </div>
                                          )}
                                          {stepDetail.outputs.length > 0 && (
                                            <div className="flex items-start gap-1.5">
                                              <span className="shrink-0 pt-0.5 text-[10px] font-extrabold text-emerald-500">{t('how.stepOutputBoLabel')}</span>
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
                      })()}

                      {/* Flow Involved Business Objects Projection Section */}
                      {(() => {
                        const isLoadingBo = !!flowObjectUsageLoading[flow.flowId];
                        const boError = flowObjectUsageErrors[flow.flowId];
                        const boProjections = flowObjectUsages[flow.flowId] ?? [];
                        const flowSteps = flow.flowSteps || [];
                        const isBoSectionCollapsed = collapsedBoSections[flow.flowId] === true;

                        return (
                          <div id={`flow-bo-${flow.flowId}`} className="mt-6 pt-5 border-t border-slate-200/60 space-y-3" onClick={(e) => e.stopPropagation()}>
                            <div className="flex items-center justify-between">
                              <button
                                type="button"
                                aria-expanded={!isBoSectionCollapsed}
                                aria-controls={`flow-bo-content-${flow.flowId}`}
                                onClick={() => setCollapsedBoSections(prev => ({ ...prev, [flow.flowId]: !prev[flow.flowId] }))}
                                className="flex items-center gap-1.5 text-xs font-bold text-slate-800 hover:text-indigo-700 transition-colors cursor-pointer group/bo"
                              >
                                <ChevronRight className={`w-3.5 h-3.5 text-slate-400 group-hover/bo:text-indigo-500 transition-transform duration-200 ${isBoSectionCollapsed ? '' : 'rotate-90'}`} />
                                <Database className="w-4 h-4 text-indigo-600" />
                                {t('how.involvedBusinessObjects', '涉及业务对象')}
                                <span className="text-[10px] font-mono text-slate-400 font-normal">
                                  ({boProjections.length})
                                </span>
                              </button>
                              {!isReadOnly && (
                                <button
                                  type="button"
                                  onClick={() => setIsAddBusinessObjectModalOpen(true)}
                                  className="inline-flex items-center gap-1 text-[11px] font-bold text-indigo-600 hover:text-indigo-700 bg-indigo-50/70 hover:bg-indigo-100/70 border border-indigo-200/60 px-2 py-1 rounded-lg transition-colors cursor-pointer"
                                >
                                  <Plus className="w-3 h-3" />
                                  {t('how.createBusinessObjectBtn', '新建业务对象')}
                                </button>
                              )}
                            </div>

                            {!isBoSectionCollapsed && (isLoadingBo ? (
                              <div
                                data-testid={`flow-bo-loading-${flow.flowId}`}
                                className="rounded-xl border border-slate-200 bg-white/60 p-4 flex items-center justify-center gap-2 text-xs text-slate-500 animate-pulse"
                              >
                                <RefreshCw className="w-4 h-4 animate-spin text-indigo-500" />
                                <span>{t('how.objectUsageLoading', '正在加载对象投影...')}</span>
                              </div>
                            ) : boError ? (
                              <div
                                data-testid={`flow-bo-error-${flow.flowId}`}
                                className="rounded-xl border border-rose-200 bg-rose-50/50 p-4 flex items-center justify-between gap-3 text-xs text-rose-700"
                              >
                                <div className="flex items-center gap-2 min-w-0">
                                  <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
                                  <span className="truncate">{t('how.objectUsageError', '加载业务对象投影失败')}: {boError}</span>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => void loadFlowObjectUsage(flow.flowId).catch(() => {})}
                                  className="px-2.5 py-1 bg-white hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg text-[11px] font-bold transition-colors shrink-0 cursor-pointer"
                                >
                                  {t('how.retryLoad', '重试')}
                                </button>
                              </div>
                            ) : boProjections.length === 0 ? (
                              <div className="rounded-xl border border-dashed border-slate-200 bg-white/60 p-4 text-center text-xs text-slate-400">
                                {t('how.noInvolvedObjects', '当前流程各步骤暂未关联输入或输出业务对象')}
                              </div>
                            ) : (
                              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                {boProjections.map((bo) => {
                                  const isBoSelected = selectedObject?.businessObjectId === bo.businessObjectId;
                                  return (
                                    <div
                                      key={bo.businessObjectId}
                                      data-testid={`flow-bo-projection-${flow.flowId}-${bo.businessObjectId}`}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        const fullBo = (ir?.businessObjects || []).find((b: any) => b.businessObjectId === bo.businessObjectId);
                                        if (fullBo) setSelectedObject(fullBo);
                                      }}
                                      className={`group rounded-xl border bg-white p-3.5 transition-all cursor-pointer flex flex-col justify-between gap-2.5 hover:border-indigo-300 hover:shadow-md hover:-translate-y-px ${
                                        isBoSelected ? 'ring-2 ring-indigo-500 border-transparent shadow-md' : 'border-slate-200 shadow-2xs'
                                      }`}
                                    >
                                      <div className="space-y-1.5">
                                        <div className="flex items-center justify-between gap-2">
                                          <div className="flex min-w-0 items-center gap-2">
                                            <span className="w-6 h-6 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center shrink-0">
                                              <Database className="w-3 h-3 text-indigo-600" />
                                            </span>
                                            <span className="font-bold text-xs text-slate-900 truncate group-hover:text-indigo-700 transition-colors">
                                              {bo.name}
                                            </span>
                                          </div>
                                          <StatusBadge status={(bo.confirmationStatus as any) || 'confirmed'} className="scale-[0.8] origin-right shrink-0" />
                                        </div>
                                        {bo.description && (
                                          <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed pl-8">
                                            {bo.description}
                                          </p>
                                        )}
                                      </div>

                                      {/* Input / Output Step Badges */}
                                      <div className="flex flex-wrap gap-1 text-[10px]">
                                        {bo.inputAtStepIds.length > 0 && (
                                          <span className="inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 bg-amber-50 text-amber-800 border border-amber-200/60 font-medium">
                                            {t('how.canvas.inputBoPrefix')}#{bo.inputAtStepIds.map((sid) => flowSteps.findIndex((s: any) => s.stepId === sid) + 1 || sid).join(', #')}
                                          </span>
                                        )}
                                        {bo.outputAtStepIds.length > 0 && (
                                          <span className="inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 bg-emerald-50 text-emerald-800 border border-emerald-200/60 font-medium">
                                            {t('how.canvas.outputBoPrefix')}#{bo.outputAtStepIds.map((sid) => flowSteps.findIndex((s: any) => s.stepId === sid) + 1 || sid).join(', #')}
                                          </span>
                                        )}
                                        <span className="inline-flex items-center rounded-md px-1.5 py-0.5 bg-slate-100 text-slate-600 font-medium">
                                          {t('how.boFieldsFormat', { count: bo.attributes.length })}
                                        </span>
                                      </div>

                                      {/* Multi-flow shared notice */}
                                      {bo.otherFlowsCount > 0 && (
                                        <div className="flex items-center gap-1.5 rounded-lg bg-amber-50 border border-amber-200/80 px-2 py-1 text-[10px] text-amber-800">
                                          <AlertTriangle className="w-3 h-3 text-amber-600 shrink-0" />
                                          <span className="truncate" title={bo.otherFlowNames.join(', ')}>
                                            {t('how.multiFlowSharedNotice', {
                                              count: bo.otherFlowsCount,
                                              flows: bo.otherFlowNames.join(', ')
                                            })}
                                          </span>
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            ))}
                          </div>
                        );
                      })()}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </GlassSurface>

            {/* AI Flow Draft Preview Banner (Rendered after FlowSection) */}
            {activeDraft && activeDraftType === 'flow' && (
              <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-6 border border-amber-200/80 shadow-md animate-in slide-in-from-top-4 duration-500 space-y-4">
                <div className="flex justify-between items-start">
                  <div className="flex items-center gap-2 flex-1 mr-4">
                    <span className="p-1.5 bg-amber-100 text-amber-700 rounded-lg shrink-0">
                      <Sparkles className="w-5 h-5 animate-pulse" />
                    </span>
                    <div className="flex-1 space-y-2">
                      <div>
                        <h3 className="text-base font-bold text-slate-900">{t('how.generatedDraftTitle')}</h3>
                        <p className="text-xs text-slate-500 mt-0.5">{t('how.generatedDraftDescription')}</p>
                      </div>
                      <div className="flex gap-2 items-center max-w-md">
                        <input
                          type="text"
                          value={flowFeedback}
                          onChange={(e) => setFlowFeedback(e.target.value)}
                          placeholder={t('how.generatedDraftFeedbackPlaceholder')}
                          className="flex-1 px-3 py-1.5 bg-white border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800"
                          disabled={isGenerating || isLoading}
                        />
                        <button
                          onClick={async () => {
                            await regenerateFlows(flowFeedback || undefined);
                            setFlowFeedback('');
                          }}
                          disabled={isGenerating || isLoading}
                          className="flex items-center gap-1 px-3 py-1.5 border border-slate-200 bg-white text-slate-700 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                        >
                          <RefreshCw className={`w-3 h-3 text-indigo-500 ${isGenerating || isLoading ? 'animate-spin' : ''}`} />
                          {t('how.regenerateBtn')}
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={confirmFlowDraft}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50"
                    >
                      <Check className="w-3.5 h-3.5" />
                      {t('how.aiAdoptBtn')}
                    </button>
                    <button
                      onClick={discardDraft}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                    >
                      <X className="w-3.5 h-3.5" />
                      {t('scope.modal.discard')}
                    </button>
                  </div>
                </div>

                {/* Flow preview cards */}
                <div className="space-y-4 pt-2 border-t border-slate-200/60">
                  {activeDraft.flows?.map((fl: any, idx: number) => (
                    <div key={idx} className="bg-white/80 p-4 rounded-xl border border-slate-200/50">
                      <h4 className="font-bold text-slate-800 text-xs flex items-center gap-1">
                        <Workflow className="w-3.5 h-3.5 text-indigo-500" />
                        {t('how.flowLabelFormat', { name: fl.flow_name })}
                      </h4>
                      <p className="text-xs text-slate-500 mt-1 leading-relaxed">{fl.flow_description}</p>
                      <FlowDraftCanvas flow={fl} className="mt-3" />
                    </div>
                  ))}
                </div>
              </div>
            )}

          </div>
        </div>
      </div>

      {/* NEW/PORTED: Manual Add Business Object Modal */}
      {isAddBusinessObjectModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4 select-none animate-in fade-in duration-200">
          <div className="bg-white/95 border border-slate-200 shadow-2xl max-w-md w-full flex flex-col rounded-3xl animate-in scale-in-95 duration-200 overflow-hidden">
            <div className="p-6 pb-4 border-b border-slate-100 bg-slate-50/50">
              <h3 className="font-extrabold text-sm text-slate-800">{t('how.manualBoTitle')}</h3>
              <p className="text-[10px] text-slate-500 mt-1">{t('how.manualBoDesc')}</p>
            </div>
            <div className="p-6 space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">{t('how.boNameLabel')}</label>
                <input
                  type="text"
                  value={newBusinessObjectName}
                  onChange={(e) => setNewBusinessObjectName(e.target.value)}
                  placeholder={t('how.boNamePlaceholder')}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">{t('how.boDescLabel')}</label>
                <textarea
                  value={newBusinessObjectDesc}
                  onChange={(e) => setNewBusinessObjectDesc(e.target.value)}
                  placeholder={t('how.boDescPlaceholder')}
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
              {t('common.cancel')}
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
                {t('how.confirmAddBo', '确认添加')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* {t('how.manualFlowTitle')} Modal */}
      {isAddFlowModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4 select-none animate-in fade-in duration-200">
          <div className="bg-white/95 border border-slate-200 shadow-2xl max-w-lg w-full flex flex-col rounded-3xl animate-in scale-in-95 duration-200 overflow-hidden">
            <div className="p-6 pb-4 border-b border-slate-100 bg-slate-50/50">
        <h3 className="font-extrabold text-sm text-slate-800">{t('how.manualFlowTitle')}</h3>
              <p className="text-[10px] text-slate-500 mt-1">{t('how.manualFlowDesc')}</p>
            </div>
            <div className="p-6 space-y-4 max-h-[60vh] overflow-y-auto">
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">{t('how.flowNameLabel')}</label>
                <input
                  type="text"
                  value={newFlowName}
                  onChange={(e) => setNewFlowName(e.target.value)}
                  placeholder={t('how.flowNamePlaceholder')}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">{t('how.flowDescLabel')}</label>
                <textarea
                  value={newFlowDesc}
                  onChange={(e) => setNewFlowDesc(e.target.value)}
                  placeholder={t('how.flowDescPlaceholder')}
                  rows={3}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium resize-none leading-relaxed"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">
                  {t('how.flowBindFeaturesLabel')}
                </label>
                <div className="space-y-2 border border-slate-200/50 rounded-xl p-3 bg-slate-50 max-h-[180px] overflow-y-auto">
                  {(ir?.features || []).length === 0 ? (
                    <div className="text-xs text-slate-400 italic">{t('how.noFeaturesTip')}</div>
                  ) : (
                    (ir?.features || []).map((feat: FeatureNode) => {
                      const isLeaf = !feat.childrenIds || feat.childrenIds.length === 0;
                      const pathStr = getFeaturePath(feat.featureId, ir?.features || []);

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
                            <span className="text-[10px] text-slate-400 font-bold ml-1.5">({t('how.parentCategory')})</span>
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
              {t('common.cancel')}
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
                {t('how.confirmAddFlow', '确认添加')}
              </button>
            </div>
          </div>
        </div>
      )}

        {/* Manual step editor */}
      {isAddStepModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4 select-none animate-in fade-in duration-200">
          <div className="bg-white/95 border border-slate-200 shadow-2xl max-w-lg w-full flex flex-col rounded-3xl animate-in scale-in-95 duration-200 overflow-hidden">
            <div className="p-6 pb-4 border-b border-slate-100 bg-slate-50/50">
              <h3 className="font-extrabold text-sm text-slate-800">{t('how.manualStepTitle')}</h3>
              <p className="text-[10px] text-slate-500 mt-1">{t('how.manualStepDesc')}</p>
            </div>
            <div className="p-6 space-y-4 max-h-[60vh] overflow-y-auto">
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">{t('how.stepNameLabel')}</label>
                <input
                  type="text"
                  value={newStepName}
                  onChange={(e) => setNewStepName(e.target.value)}
                  placeholder={t('how.stepNamePlaceholder')}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">{t('how.stepTypeLabel')}</label>
                <select
                  value={newStepType}
                  onChange={(e) => setNewStepType(e.target.value as any)}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-semibold"
                >
                  <option value="actorAction">{t('how.stepPerformerUser')}</option>
                  <option value="systemAction">{t('how.stepPerformerSystem')}</option>
                  <option value="judgment">{t('how.stepPerformerJudgment')}</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">{t('how.stepDescLabel')}</label>
                <textarea
                  value={newStepDesc}
                  onChange={(e) => setNewStepDesc(e.target.value)}
                  placeholder={t('how.stepDescPlaceholder')}
                  rows={2}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium resize-none leading-relaxed"
                />
              </div>

              {/* Actors Checklist */}
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">
                  {t('how.stepActorsLabel')} {newStepType === 'actorAction' && <span className="text-amber-600 font-bold">{t('how.stepActorsRequired')}</span>}
                </label>
                <div className="space-y-2 border border-slate-200/50 rounded-xl p-3 bg-slate-50 max-h-[110px] overflow-y-auto">
                  {(ir?.actors || []).length === 0 ? (
                    <div className="text-xs text-slate-400 italic">{t('how.stepActorsEmpty')}</div>
                  ) : (
                    (ir?.actors || []).map((actor: ActorNode) => (
                      <label key={actor.actorId} className="flex items-center gap-2 text-xs font-semibold text-slate-700 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={newStepActorIds.includes(actor.actorId)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setNewStepActorIds([...newStepActorIds, actor.actorId]);
                            } else {
                              setNewStepActorIds(newStepActorIds.filter((id) => id !== actor.actorId));
                            }
                          }}
                          className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        {actor.actorName}
                      </label>
                    ))
                  )}
                </div>
              </div>

              {/* Input BOs Checklist */}
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">{t('how.stepInputBOsLabel')}</label>
                <div className="space-y-2 border border-slate-200/50 rounded-xl p-3 bg-slate-50 max-h-[100px] overflow-y-auto">
                  {(ir?.businessObjects || []).length === 0 ? (
                    <div className="text-xs text-slate-400 italic">{t('how.stepBOsEmpty')}</div>
                  ) : (
                    (ir?.businessObjects || []).map((bo: BusinessObjectNode) => (
                      <label key={bo.businessObjectId} className="flex items-center gap-2 text-xs font-semibold text-slate-700 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={newStepInputBoIds.includes(bo.businessObjectId)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setNewStepInputBoIds([...newStepInputBoIds, bo.businessObjectId]);
                            } else {
                              setNewStepInputBoIds(newStepInputBoIds.filter((id) => id !== bo.businessObjectId));
                            }
                          }}
                          className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        {bo.businessObjectName}
                      </label>
                    ))
                  )}
                </div>
              </div>

              {/* Output BOs Checklist */}
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">{t('how.stepOutputBOsLabel')}</label>
                <div className="space-y-2 border border-slate-200/50 rounded-xl p-3 bg-slate-50 max-h-[100px] overflow-y-auto">
                  {(ir?.businessObjects || []).length === 0 ? (
                    <div className="text-xs text-slate-400 italic">{t('how.stepBOsEmpty')}</div>
                  ) : (
                    (ir?.businessObjects || []).map((bo: BusinessObjectNode) => (
                      <label key={bo.businessObjectId} className="flex items-center gap-2 text-xs font-semibold text-slate-700 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={newStepOutputBoIds.includes(bo.businessObjectId)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setNewStepOutputBoIds([...newStepOutputBoIds, bo.businessObjectId]);
                            } else {
                              setNewStepOutputBoIds(newStepOutputBoIds.filter((id) => id !== bo.businessObjectId));
                            }
                          }}
                          className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        {bo.businessObjectName}
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
                {t('common.cancel')}
              </button>
              <button
                onClick={async () => {
                  if (!newStepName.trim()) return;
                  if (newStepType === 'actorAction' && newStepActorIds.length === 0) {
      alert(t('how.actorRequired'));
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
                {t('how.confirmAddStep', '确认添加')}
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
            const dId = activeDraft?.draftId;
            if (dId) discardRepairDraft(dId);
          } else {
            discardDraft();
          }
        }}
        onRegenerate={(feedback) => {
          if (activeDraftType === 'repair') {
            const dId = activeDraft?.draftId;
            if (dId) regenerateRepairDraft(dId);
          } else {
            regenerateFlows(feedback);
          }
        }}
        onConfirm={async () => {
          if (activeDraftType === 'repair') {
            const dId = activeDraft?.draftId;
            if (dId) await confirmRepairDraft(dId);
          } else {
            await confirmFlowDraft();
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
                <h3 className="font-extrabold text-sm text-slate-800">{t('how.boDeleteBlocked')}</h3>
                <p className="text-[10px] text-slate-500 mt-0.5">{t('how.boReferencedTip')}</p>
              </div>
            </div>
            <div className="p-6 space-y-4">
              <div className="p-4 bg-slate-50 border border-slate-100 rounded-2xl text-xs text-slate-600 leading-relaxed font-medium">
                {t(boDeletionError)}
              </div>
            </div>
            <div className="p-4 bg-slate-50/50 border-t border-slate-100 flex justify-end">
              <button
                type="button"
                onClick={() => setBoDeletionError(null)}
                className="px-5 py-2 rounded-xl text-xs font-bold text-white bg-slate-800 hover:bg-slate-700 active:scale-95 transition-all shadow-md shadow-slate-200/80"
              >
                {t('how.boUnderstand')}
              </button>
            </div>
          </div>
        </div>
      )}

      <AIAddObjectDialog
        isOpen={isAIDialogOpen}
        onClose={() => setAiDialogTarget(null)}
        projectId={ir?.projectId ?? ''}
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
          // Don't close modal — it handles its own diagnosing state
          await runDiagnosis('how');
        }}
        onForceUnlock={async () => {
          setIsTransitionModalOpen(false);
          await requestStageTransition('enter_scope', { navigate });
        }}
      />

      <ChoiceGroupPreviewModal
        group={activeChoiceGroup}
        isWorking={isGeneratingChoices || isLoading}
        isGeneratingChoices={isGeneratingChoices}
        generationProgress={choiceGroupGenerationProgress}
        onAccept={async (choiceId, expectedVersion) => {
          await acceptChoice(choiceId, false, expectedVersion);
        }}
        onDiscard={async () => {
          if (activeChoiceGroup) {
            await discardChoiceGroup(activeChoiceGroup.id);
          }
        }}
        onDefer={() => useWorkspaceStore.setState({ activeChoiceGroup: null })}
      />

      <FocusFlowCanvasModal
        flow={(ir?.flows || []).find((f: any) => f.flowId === focusFlowId) || null}
        isOpen={focusFlowId !== null}
        onClose={() => {
          setFocusFlowId(null);
          setFocusStepId(null);
          setFocusTransitionId(null);
        }}
        actors={ir?.actors || []}
        businessObjects={ir?.businessObjects || []}
        onUpdateStep={updateFlowStep}
        onAddStep={async (flowId, data) => {
          await addFlowStep(flowId, data);
        }}
        onDeleteStep={async (flowId, stepId) => {
          await deleteFlowStep(flowId, stepId);
        }}
        onUpdateFlow={async (flowId, data) => {
          await updateFlow(flowId, data);
        }}
        onCreateTransition={createFlowTransition}
        onUpdateTransition={updateFlowTransition}
        onDeleteTransition={deleteFlowTransition}
        readOnly={isReadOnly}
        initialSelectedStepId={focusStepId}
        initialSelectedTransitionId={focusTransitionId}
      />

      <RightObjectPanel />
    </div>
  );
}
