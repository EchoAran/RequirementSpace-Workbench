import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import gsap from 'gsap';
import {
  X,
  Plus,
  Trash2,
  Users,
  Boxes,
  Workflow,
  Sparkles,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  ArrowRight,
  Link2,
  Unlink,
  HelpCircle,
  Maximize2,
  Minimize2,
} from 'lucide-react';
import { FlowNode, FlowStepNode, ActorNode, BusinessObjectNode } from '@/core/schema';
import { cn } from '@/lib/utils';

export interface FocusFlowCanvasModalProps {
  flow: FlowNode | null;
  isOpen: boolean;
  onClose: () => void;
  actors: ActorNode[];
  businessObjects: BusinessObjectNode[];
  onUpdateStep: (flowId: number, stepId: number, updates: Partial<FlowStepNode>) => Promise<void>;
  onAddStep: (flowId: number, initialData?: any) => Promise<void>;
  onDeleteStep: (flowId: number, stepId: number) => Promise<void>;
  onUpdateFlow?: (flowId: number, updates: { flowName?: string; flowDescription?: string }) => Promise<void>;
}

// Compute DAG hierarchical positions
function computeHierarchicalPositions(steps: FlowStepNode[]): Record<number, { x: number; y: number }> {
  const positions: Record<number, { x: number; y: number }> = {};
  if (steps.length === 0) return positions;

  const colWidth = 360;
  const rowHeight = 220;
  const visited = new Set<number>();

  const allNextIds = new Set(steps.flatMap((s) => s.nextStepIds || []));
  const startNodes = steps.filter((s) => !allNextIds.has(s.stepId));

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
      x: 60 + col * colWidth,
      y: 60 + currentRow * rowHeight,
    };

    const step = steps.find((s) => s.stepId === stepId);
    if (step && step.nextStepIds) {
      step.nextStepIds.forEach((nid: number, idx: number) => {
        if (!visited.has(nid)) {
          queue.push({ stepId: nid, col: col + 1, row: idx });
        }
      });
    }
  }

  // Handle orphan / unvisited steps
  steps.forEach((s) => {
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
        x: 60 + col * colWidth,
        y: 60 + currentRow * rowHeight,
      };
    }
  });

  return positions;
}

export function FocusFlowCanvasModal({
  flow,
  isOpen,
  onClose,
  actors,
  businessObjects,
  onUpdateStep,
  onAddStep,
  onDeleteStep,
  onUpdateFlow: _onUpdateFlow,
}: FocusFlowCanvasModalProps) {
  const { t } = useTranslation();
  const backdropRef = useRef<HTMLDivElement>(null);
  const modalCardRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const drawerRef = useRef<HTMLDivElement>(null);

  // Modal Resizable Dimensions State
  const [modalSize, setModalSize] = useState<{ width: number; height: number }>(() => ({
    width: typeof window !== 'undefined' ? Math.min(window.innerWidth - 48, 1560) : 1440,
    height: typeof window !== 'undefined' ? Math.min(window.innerHeight - 48, 920) : 840,
  }));
  const [isMaximized, setIsMaximized] = useState(false);
  const [isResizing, setIsResizing] = useState(false);

  // Pan & Zoom
  const [panZoom, setPanZoom] = useState({ scale: 1, x: 0, y: 0 });
  const [isPanningCanvas, setIsPanningCanvas] = useState(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number } | null>(null);

  // Custom node positions
  const [nodePositions, setNodePositions] = useState<Record<number, { x: number; y: number }>>({});
  const [activeDragStepId, setActiveDragStepId] = useState<number | null>(null);
  const [dragOffset, setDragOffset] = useState<{ x: number; y: number } | null>(null);

  // Selection
  const [selectedStepId, setSelectedStepId] = useState<number | null>(null);
  const [selectedLinkId, setSelectedLinkId] = useState<string | null>(null); // "fromId-toId"

  // Live Linking state (dragging connection line from port)
  const [linkingState, setLinkingState] = useState<{
    fromStepId: number;
    startX: number;
    startY: number;
    currentX: number;
    currentY: number;
  } | null>(null);

  // Quick Add Step Dialog inside Focus modal
  const [isAddStepOpen, setIsAddStepOpen] = useState(false);
  const [newStepName, setNewStepName] = useState('');
  const [newStepDesc, setNewStepDesc] = useState('');
  const [newStepType, setNewStepType] = useState<'actorAction' | 'systemAction' | 'judgment'>('actorAction');
  const [newStepActorIds, setNewStepActorIds] = useState<number[]>([]);
  const [newStepInputBoIds, setNewStepInputBoIds] = useState<number[]>([]);
  const [newStepOutputBoIds, setNewStepOutputBoIds] = useState<number[]>([]);
  const [newStepConnectFromId, setNewStepConnectFromId] = useState<number | null>(null);

  // Initialize layout when flow changes
  const steps = useMemo(() => flow?.flowSteps || [], [flow]);

  const defaultPositions = useMemo(() => {
    return computeHierarchicalPositions(steps);
  }, [steps]);

  useEffect(() => {
    if (isOpen && flow) {
      setNodePositions(defaultPositions);
      setPanZoom({ scale: 1, x: 40, y: 40 });
      setSelectedStepId(steps[0]?.stepId || null);
      setSelectedLinkId(null);

      // Default wider modal sizing adjusted to current window
      if (typeof window !== 'undefined') {
        setModalSize({
          width: Math.min(window.innerWidth - 48, 1560),
          height: Math.min(window.innerHeight - 48, 920),
        });
      }

      // GSAP Entrance animation
      if (backdropRef.current) {
        gsap.fromTo(
          backdropRef.current,
          { opacity: 0 },
          { opacity: 1, duration: 0.25, ease: 'power2.out' }
        );
      }
      if (modalCardRef.current) {
        gsap.fromTo(
          modalCardRef.current,
          { opacity: 0, scale: 0.96, y: 16 },
          { opacity: 1, scale: 1, y: 0, duration: 0.35, ease: 'back.out(1.2)' }
        );
      }
    }
  }, [isOpen, flow?.flowId, defaultPositions]);

  // Animate drawer when selection changes
  useEffect(() => {
    if (drawerRef.current && (selectedStepId !== null || selectedLinkId !== null)) {
      gsap.fromTo(
        drawerRef.current,
        { opacity: 0, x: 12 },
        { opacity: 1, x: 0, duration: 0.2, ease: 'power2.out' }
      );
    }
  }, [selectedStepId, selectedLinkId]);

  // Handle ESC key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;
      if (e.key === 'Escape') {
        if (isAddStepOpen) {
          setIsAddStepOpen(false);
        } else if (linkingState) {
          setLinkingState(null);
        } else {
          onClose();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isAddStepOpen, linkingState, onClose]);

  // Modal Resize Drag Handler
  const handleResizeStart = (
    e: React.MouseEvent,
    direction: 'e' | 's' | 'se' | 'w' | 'sw'
  ) => {
    if (isMaximized) return;
    e.stopPropagation();
    e.preventDefault();
    setIsResizing(true);

    const startX = e.clientX;
    const startY = e.clientY;
    const startW = modalSize.width;
    const startH = modalSize.height;

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const dx = moveEvent.clientX - startX;
      const dy = moveEvent.clientY - startY;

      let newW = startW;
      let newH = startH;

      if (direction.includes('e')) {
        newW = Math.min(window.innerWidth - 32, Math.max(860, startW + dx * 2));
      } else if (direction.includes('w')) {
        newW = Math.min(window.innerWidth - 32, Math.max(860, startW - dx * 2));
      }

      if (direction.includes('s')) {
        newH = Math.min(window.innerHeight - 32, Math.max(520, startH + dy * 2));
      }

      setModalSize({ width: Math.round(newW), height: Math.round(newH) });
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  // GSAP-Powered Auto layout function with smooth spring tweening
  const handleAutoLayout = useCallback(() => {
    const targetPos = computeHierarchicalPositions(steps);
    const proxy = { progress: 0 };
    const startPositions = { ...nodePositions };
    steps.forEach((s) => {
      if (!startPositions[s.stepId]) {
        startPositions[s.stepId] = defaultPositions[s.stepId] || { x: 60, y: 60 };
      }
    });

    gsap.to(proxy, {
      progress: 1,
      duration: 0.45,
      ease: 'power3.out',
      onUpdate: () => {
        const p = proxy.progress;
        const interpolated: Record<number, { x: number; y: number }> = {};
        steps.forEach((s) => {
          const from = startPositions[s.stepId] || { x: 0, y: 0 };
          const to = targetPos[s.stepId] || { x: 0, y: 0 };
          interpolated[s.stepId] = {
            x: Math.round(from.x + (to.x - from.x) * p),
            y: Math.round(from.y + (to.y - from.y) * p),
          };
        });
        setNodePositions(interpolated);
      },
    });
  }, [steps, nodePositions, defaultPositions]);

  // GSAP-Powered Fit to view
  const handleFitView = useCallback(() => {
    if (steps.length === 0) return;
    const positions = steps.map((s) => nodePositions[s.stepId] || defaultPositions[s.stepId] || { x: 0, y: 0 });
    const minX = Math.min(...positions.map((p) => p.x));
    const maxX = Math.max(...positions.map((p) => p.x + 280));
    const minY = Math.min(...positions.map((p) => p.y));
    const maxY = Math.max(...positions.map((p) => p.y + 160));

    const canvasW = canvasRef.current?.clientWidth || 1000;
    const canvasH = canvasRef.current?.clientHeight || 650;

    const widthRatio = (canvasW - 120) / (maxX - minX || 1);
    const heightRatio = (canvasH - 120) / (maxY - minY || 1);
    const targetScale = Math.min(1.15, Math.max(0.4, Math.min(widthRatio, heightRatio)));

    const targetX = Math.round((canvasW - (maxX - minX) * targetScale) / 2 - minX * targetScale);
    const targetY = Math.round((canvasH - (maxY - minY) * targetScale) / 2 - minY * targetScale);

    const animState = { scale: panZoom.scale, x: panZoom.x, y: panZoom.y };
    gsap.to(animState, {
      scale: targetScale,
      x: targetX,
      y: targetY,
      duration: 0.45,
      ease: 'power3.out',
      onUpdate: () => {
        setPanZoom({ scale: animState.scale, x: animState.x, y: animState.y });
      },
    });
  }, [steps, nodePositions, defaultPositions, panZoom]);

  // Mouse wheel zoom
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    setPanZoom((prev) => {
      const newScale = Math.min(2.0, Math.max(0.35, prev.scale * zoomFactor));
      return {
        ...prev,
        scale: Math.round(newScale * 100) / 100,
      };
    });
  }, []);

  // Canvas Pan Handlers
  const handleCanvasMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('.flow-node-card') || (e.target as HTMLElement).closest('.port-handle') || (e.target as HTMLElement).closest('button')) {
      return;
    }
    setIsPanningCanvas(true);
    setPanStart({ x: e.clientX - panZoom.x, y: e.clientY - panZoom.y });
    setSelectedLinkId(null);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    // 1. Pan Canvas
    if (isPanningCanvas && panStart) {
      setPanZoom((prev) => ({
        ...prev,
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      }));
      return;
    }

    // 2. Drag Step Node
    if (activeDragStepId !== null && dragOffset) {
      const newX = Math.round((e.clientX - dragOffset.x) / panZoom.scale);
      const newY = Math.round((e.clientY - dragOffset.y) / panZoom.scale);
      setNodePositions((prev) => ({
        ...prev,
        [activeDragStepId]: { x: Math.max(10, newX), y: Math.max(10, newY) },
      }));
      return;
    }

    // 3. Drag Link (Connecting from Port)
    if (linkingState) {
      const canvasRect = canvasRef.current?.getBoundingClientRect();
      if (canvasRect) {
        const mouseX = (e.clientX - canvasRect.left - panZoom.x) / panZoom.scale;
        const mouseY = (e.clientY - canvasRect.top - panZoom.y) / panZoom.scale;
        setLinkingState((prev) => (prev ? { ...prev, currentX: mouseX, currentY: mouseY } : null));
      }
    }
  };

  const handleMouseUp = (e: React.MouseEvent) => {
    setIsPanningCanvas(false);
    setActiveDragStepId(null);
    setDragOffset(null);

    // If we were dragging a link, check if dropped on a target node or target input port
    if (linkingState && flow) {
      const targetElement = document.elementFromPoint(e.clientX, e.clientY);
      const targetNodeEl = targetElement?.closest('[data-step-id]');
      if (targetNodeEl) {
        const targetId = parseInt(targetNodeEl.getAttribute('data-step-id') || '', 10);
        if (!isNaN(targetId) && targetId !== linkingState.fromStepId) {
          // Establish connection!
          const sourceStep = steps.find((s) => s.stepId === linkingState.fromStepId);
          if (sourceStep) {
            const currentNext = sourceStep.nextStepIds || [];
            if (!currentNext.includes(targetId)) {
              const updatedNext = [...currentNext, targetId];
              void onUpdateStep(flow.flowId, sourceStep.stepId, { nextStepIds: updatedNext });
            }
          }
        }
      }
      setLinkingState(null);
    }
  };

  // Node Drag Start
  const handleNodeMouseDown = (e: React.MouseEvent, stepId: number) => {
    if ((e.target as HTMLElement).closest('.port-handle') || (e.target as HTMLElement).closest('button')) {
      return;
    }
    e.stopPropagation();
    setSelectedStepId(stepId);
    setSelectedLinkId(null);
    setActiveDragStepId(stepId);

    const currentPos = nodePositions[stepId] || defaultPositions[stepId] || { x: 0, y: 0 };
    setDragOffset({
      x: e.clientX - currentPos.x * panZoom.scale,
      y: e.clientY - currentPos.y * panZoom.scale,
    });
  };

  // Port Drag Start (Output Port)
  const handlePortMouseDown = (e: React.MouseEvent, fromStepId: number, startX: number, startY: number) => {
    e.stopPropagation();
    e.preventDefault();
    setLinkingState({
      fromStepId,
      startX,
      startY,
      currentX: startX,
      currentY: startY,
    });
  };

  // Disconnect connection
  const handleDisconnect = async (fromStepId: number, toStepId: number) => {
    if (!flow) return;
    const sourceStep = steps.find((s) => s.stepId === fromStepId);
    if (!sourceStep) return;
    const updatedNext = (sourceStep.nextStepIds || []).filter((id) => id !== toStepId);
    await onUpdateStep(flow.flowId, fromStepId, { nextStepIds: updatedNext });
    setSelectedLinkId(null);
  };

  // Currently selected step object
  const selectedStep = useMemo(() => {
    return steps.find((s) => s.stepId === selectedStepId) || null;
  }, [steps, selectedStepId]);

  if (!isOpen || !flow) return null;

  const canvasWidth = 3800;
  const canvasHeight = 2800;

  return (
    <div
      ref={backdropRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
      onClick={onClose}
    >
      {/* Resizable Modal Window with Light Mode System Styling */}
      <div
        ref={modalCardRef}
        onClick={(e) => e.stopPropagation()}
        style={
          isMaximized
            ? { width: 'calc(100vw - 32px)', height: 'calc(100vh - 32px)' }
            : {
                width: `${modalSize.width}px`,
                height: `${modalSize.height}px`,
                maxWidth: 'calc(100vw - 32px)',
                maxHeight: 'calc(100vh - 32px)',
              }
        }
        className={cn(
          'relative bg-white border border-slate-200/90 rounded-3xl shadow-2xl flex flex-col overflow-hidden text-slate-900 transition-[width,height] duration-75',
          isResizing && 'transition-none select-none'
        )}
      >
        {/* 1. Modal Top Bar */}
        <header
          onDoubleClick={() => setIsMaximized((prev) => !prev)}
          className="flex h-16 shrink-0 items-center justify-between border-b border-slate-100 bg-gradient-to-r from-slate-50/90 via-indigo-50/20 to-slate-50/90 px-6 cursor-default select-none"
        >
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100 shadow-2xs">
              <Workflow className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-extrabold text-slate-900">{flow.flowName}</h2>
                <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-[10px] font-bold text-indigo-700 border border-indigo-100">
                  {t('how.focusMode', '专注流程画布')}
                </span>
              </div>
              <p className="text-xs text-slate-500 max-w-lg truncate">{flow.flowDescription || t('how.noDescription', '暂无描述')}</p>
            </div>
          </div>

          {/* Action Controls & Canvas Utilities */}
          <div className="flex items-center gap-2.5">
            {/* Quick Stats */}
            <div className="hidden lg:flex items-center gap-2 border-r border-slate-200 pr-3 text-xs font-bold text-slate-500">
              <span>{steps.length} {t('how.stepsCount', '步骤')}</span>
              <span>·</span>
              <span>{steps.flatMap((s) => s.nextStepIds || []).length} {t('how.linksCount', '分支连线')}</span>
            </div>

            <button
              type="button"
              onClick={() => {
                setNewStepName('');
                setNewStepDesc('');
                setNewStepType('actorAction');
                setNewStepActorIds(actors.length > 0 ? [actors[0].actorId] : []);
                setNewStepInputBoIds([]);
                setNewStepOutputBoIds([]);
                setNewStepConnectFromId(selectedStepId);
                setIsAddStepOpen(true);
              }}
              className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-1.5 text-xs font-bold text-white shadow-sm hover:bg-indigo-700 transition-colors cursor-pointer"
            >
              <Plus className="h-4 w-4" />
              {t('how.addStep', '添加步骤')}
            </button>

            <button
              type="button"
              onClick={handleAutoLayout}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-50 transition-colors shadow-2xs cursor-pointer"
              title={t('how.autoLayoutTitle', '自动分层整理所有步骤位置')}
            >
              <Sparkles className="h-3.5 w-3.5 text-amber-500" />
              {t('how.autoLayout', '自动排版')}
            </button>

            <button
              type="button"
              onClick={handleFitView}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-50 transition-colors shadow-2xs cursor-pointer"
              title={t('how.fitViewTitle', '适应画布视口并居中')}
            >
              <RotateCcw className="h-3.5 w-3.5 text-indigo-600" />
              {t('how.fitView', '适应屏幕')}
            </button>

            {/* Zoom controls */}
            <div className="flex items-center rounded-xl border border-slate-200 bg-white p-0.5 text-xs font-bold text-slate-600 shadow-2xs">
              <button
                type="button"
                onClick={() => setPanZoom((p) => ({ ...p, scale: Math.max(0.35, Math.round((p.scale - 0.1) * 10) / 10) }))}
                className="p-1 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                title="缩小"
              >
                <ZoomOut className="h-3.5 w-3.5" />
              </button>
              <span className="min-w-[40px] text-center text-[11px] font-mono">{Math.round(panZoom.scale * 100)}%</span>
              <button
                type="button"
                onClick={() => setPanZoom((p) => ({ ...p, scale: Math.min(2.0, Math.round((p.scale + 0.1) * 10) / 10) }))}
                className="p-1 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                title="放大"
              >
                <ZoomIn className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="h-5 w-[1px] bg-slate-200 mx-1"></div>

            {/* Maximize / Restore button */}
            <button
              type="button"
              onClick={() => setIsMaximized((prev) => !prev)}
              className="w-8 h-8 rounded-full border border-slate-200 bg-white hover:bg-slate-50 text-slate-500 hover:text-slate-800 flex items-center justify-center transition-colors cursor-pointer shadow-2xs"
              title={isMaximized ? '还原窗口大小' : '最大化窗口'}
            >
              {isMaximized ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
            </button>

            {/* Close button */}
            <button
              type="button"
              onClick={onClose}
              className="w-8 h-8 rounded-full border border-slate-200 bg-white hover:bg-slate-50 text-slate-400 hover:text-slate-700 flex items-center justify-center transition-colors cursor-pointer shadow-2xs"
              title={t('shell.close', '关闭')}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </header>

        {/* 2. Workspace Body: Left Canvas + Right Inspector */}
        <div className="flex flex-1 min-h-0 relative overflow-hidden bg-slate-50/70">
          {/* Canvas Area */}
          <div
            ref={canvasRef}
            onMouseDown={handleCanvasMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onWheel={handleWheel}
            className={`flex-1 h-full min-h-0 overflow-hidden relative select-none ${
              isPanningCanvas ? 'cursor-grabbing' : 'cursor-grab'
            }`}
            style={{
              backgroundColor: '#f8fafc',
              backgroundImage: 'radial-gradient(#cbd5e1 1.5px, transparent 1.5px)',
              backgroundSize: '24px 24px',
            }}
          >
            {/* Instructions floating banner */}
            <div className="absolute top-4 left-4 z-20 flex items-center gap-2 rounded-xl border border-slate-200/90 bg-white/90 backdrop-blur-md px-3.5 py-1.5 text-xs text-slate-600 shadow-sm">
              <HelpCircle className="h-4 w-4 text-indigo-600" />
              <span>{t('how.canvasTips', '💡 提示：按住步骤右侧点拖拽可快速连线；点击连线可断开；拖动节点自由布局')}</span>
            </div>

            {/* Transform Layer */}
            <div
              style={{
                width: `${canvasWidth}px`,
                height: `${canvasHeight}px`,
                transform: `translate(${panZoom.x}px, ${panZoom.y}px) scale(${panZoom.scale})`,
                transformOrigin: '0 0',
                position: 'relative',
              }}
            >
              {/* SVG Vector Line Layer */}
              <svg
                className="absolute inset-0 pointer-events-none"
                width={canvasWidth}
                height={canvasHeight}
                style={{ zIndex: 5, overflow: 'visible' }}
              >
                <defs>
                  <marker id="light-arrow-default" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
                    <polygon points="0 0, 8 3, 0 6" fill="#a5b4fc" />
                  </marker>
                  <marker id="light-arrow-selected" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto">
                    <polygon points="0 0, 9 3.5, 0 7" fill="#f43f5e" />
                  </marker>
                  <marker id="light-arrow-active" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
                    <polygon points="0 0, 8 3, 0 6" fill="#6366f1" />
                  </marker>
                </defs>

                {/* 1. Established Connections */}
                {steps.flatMap((step) => {
                  const fromPos = nodePositions[step.stepId] || defaultPositions[step.stepId];
                  if (!fromPos) return [];

                  return (step.nextStepIds || []).map((nid) => {
                    const toPos = nodePositions[nid] || defaultPositions[nid];
                    if (!toPos) return null;

                    // Always exit from right port of source, enter left port of target
                    const startX = fromPos.x + 280;
                    const startY = fromPos.y + 60;
                    const endX = toPos.x;
                    const endY = toPos.y + 60;

                    let pathD = '';
                    if (endX <= startX) {
                      // Loopback / backward curve: exits right, loops above/below, enters left
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

                    const linkId = `${step.stepId}-${nid}`;
                    const isSelected = selectedLinkId === linkId;
                    const isHighlighted = selectedStepId === step.stepId || selectedStepId === nid;

                    return (
                      <g key={linkId} className="pointer-events-auto">
                        {/* Thick clickable hit area */}
                        <path
                          d={pathD}
                          fill="none"
                          stroke="transparent"
                          strokeWidth={16}
                          className="cursor-pointer"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedLinkId(linkId);
                            setSelectedStepId(null);
                          }}
                        />
                        {/* Visual Line */}
                        <path
                          d={pathD}
                          fill="none"
                          stroke={isSelected ? '#f43f5e' : isHighlighted ? '#6366f1' : '#a5b4fc'}
                          strokeWidth={isSelected ? 3.5 : isHighlighted ? 3 : 2}
                          strokeDasharray={isSelected ? '6 4' : 'none'}
                          markerEnd={isSelected ? 'url(#light-arrow-selected)' : isHighlighted ? 'url(#light-arrow-active)' : 'url(#light-arrow-default)'}
                          className="transition-colors duration-150"
                        />
                      </g>
                    );
                  });
                })}

                {/* 2. Dragging Line (While Linking) */}
                {linkingState && (
                  <path
                    d={`M ${linkingState.startX} ${linkingState.startY} C ${linkingState.startX + 80} ${linkingState.startY}, ${linkingState.currentX - 80} ${linkingState.currentY}, ${linkingState.currentX} ${linkingState.currentY}`}
                    fill="none"
                    stroke="#6366f1"
                    strokeWidth={3}
                    strokeDasharray="6 4"
                    markerEnd="url(#light-arrow-active)"
                    className="animate-pulse"
                  />
                )}
              </svg>

              {/* Step Node Cards */}
              {steps.map((step, idx) => {
                const pos = nodePositions[step.stepId] || defaultPositions[step.stepId] || { x: 40 + idx * 320, y: 40 };
                const isSelected = selectedStepId === step.stepId;
                const isDragTarget = linkingState !== null && linkingState.fromStepId !== step.stepId;

                // Actors and BO names
                const stepActors = (step.actorIds || []).map((aid) => actors.find((a) => a.actorId === aid)?.actorName).filter(Boolean);
                const inputBOs = (step.inputBusinessObjectIds || []).map((bid) => businessObjects.find((b) => b.businessObjectId === bid)?.businessObjectName).filter(Boolean);
                const outputBOs = (step.outputBusinessObjectIds || []).map((bid) => businessObjects.find((b) => b.businessObjectId === bid)?.businessObjectName).filter(Boolean);

                const isJudgment = step.stepType === 'judgment';
                const isSystem = step.stepType === 'systemAction';

                return (
                  <div
                    key={step.stepId}
                    data-step-id={step.stepId}
                    style={{
                      position: 'absolute',
                      left: `${pos.x}px`,
                      top: `${pos.y}px`,
                      width: '280px',
                      zIndex: isSelected ? 30 : 10,
                    }}
                    onMouseDown={(e) => handleNodeMouseDown(e, step.stepId)}
                    className={cn(
                      'flow-node-card group relative rounded-2xl border transition-all cursor-grab active:cursor-grabbing select-none shadow-sm hover:shadow-md bg-white',
                      isJudgment
                        ? 'border-amber-300 bg-amber-50/40 hover:border-amber-400 border-dashed'
                        : isSystem
                        ? 'border-sky-200 bg-sky-50/40 hover:border-sky-400'
                        : 'border-slate-200 hover:border-indigo-400',
                      isSelected && 'ring-2 ring-indigo-500 border-transparent shadow-lg shadow-indigo-100/70',
                      isDragTarget && 'hover:ring-2 hover:ring-indigo-400 hover:scale-[1.02]'
                    )}
                  >
                    {/* Left Input Port (Target) */}
                    <div
                      className={cn(
                        'port-handle absolute -left-3 top-[50px] h-6 w-6 rounded-full border-2 border-slate-300 bg-white flex items-center justify-center transition-all shadow-2xs',
                        isDragTarget ? 'scale-125 border-indigo-500 bg-indigo-50 ring-4 ring-indigo-200' : 'group-hover:border-indigo-500'
                      )}
                      title={t('how.inputPort', '输入连接点')}
                    >
                      <span className="h-2 w-2 rounded-full bg-indigo-500"></span>
                    </div>

                    {/* Right Output Port (Source) */}
                    <div
                      onMouseDown={(e) => handlePortMouseDown(e, step.stepId, pos.x + 280, pos.y + 60)}
                      className="port-handle absolute -right-3 top-[50px] h-6 w-6 rounded-full border-2 border-indigo-600 bg-indigo-600 flex items-center justify-center cursor-crosshair transition-all hover:scale-125 hover:ring-4 hover:ring-indigo-200 shadow-sm"
                      title={t('how.outputPort', '拖拽以建立下一步连线')}
                    >
                      <ArrowRight className="h-3 w-3 text-white" />
                    </div>

                    {/* Node Content */}
                    <div className="p-4">
                      <div className="flex items-center justify-between gap-2 border-b border-slate-100 pb-2">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-indigo-50 text-[10px] font-black text-indigo-700 font-mono">
                            #{idx + 1}
                          </span>
                          <span className={cn(
                            'rounded-md px-1.5 py-0.5 text-[10px] font-bold truncate',
                            isJudgment ? 'bg-amber-100 text-amber-800' : isSystem ? 'bg-sky-100 text-sky-800' : 'bg-indigo-50 text-indigo-700'
                          )}>
                            {isJudgment ? '判断分支' : isSystem ? '系统操作' : '参与者动作'}
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={async (e) => {
                            e.stopPropagation();
                            if (window.confirm(`确定要删除步骤 "${step.stepName}" 吗？`)) {
                              await onDeleteStep(flow.flowId, step.stepId);
                              if (selectedStepId === step.stepId) setSelectedStepId(null);
                            }
                          }}
                          className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-rose-600 rounded-md transition-opacity cursor-pointer"
                          title="删除步骤"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>

                      {/* Step Title & Description */}
                      <div className="mt-2">
                        <h4 className="text-xs font-bold text-slate-900 line-clamp-1">{step.stepName}</h4>
                        {step.stepDescription && (
                          <p className="mt-1 text-[11px] text-slate-500 line-clamp-2 leading-relaxed">{step.stepDescription}</p>
                        )}
                      </div>

                      {/* Actors & Data Chips */}
                      <div className="mt-2.5 flex flex-wrap gap-1.5">
                        {stepActors.map((aname, i) => (
                          <span key={i} className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-700 border border-slate-200/60">
                            <Users className="h-2.5 w-2.5 text-indigo-600" />
                            {aname}
                          </span>
                        ))}
                        {inputBOs.length > 0 && (
                          <span className="inline-flex items-center gap-1 rounded-md bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800 border border-amber-200/60">
                            <Boxes className="h-2.5 w-2.5 text-amber-600" />
                            入: {inputBOs.slice(0, 1).join(', ')}{inputBOs.length > 1 ? ` +${inputBOs.length - 1}` : ''}
                          </span>
                        )}
                        {outputBOs.length > 0 && (
                          <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800 border border-emerald-200/60">
                            <Boxes className="h-2.5 w-2.5 text-emerald-600" />
                            出: {outputBOs.slice(0, 1).join(', ')}{outputBOs.length > 1 ? ` +${outputBOs.length - 1}` : ''}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 3. Right Property & Inspector Drawer */}
          <aside ref={drawerRef} className="w-80 shrink-0 border-l border-slate-200 bg-white p-5 overflow-y-auto flex flex-col gap-4 text-xs text-slate-800 shadow-xs">
            {/* Node is Selected */}
            {selectedStep ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-indigo-600 text-xs font-extrabold text-white">
                      #{steps.findIndex((s) => s.stepId === selectedStep.stepId) + 1}
                    </span>
                    <h3 className="font-black text-sm text-slate-900">{t('how.stepInspector', '步骤属性')}</h3>
                  </div>
                  <button
                    type="button"
                    onClick={async () => {
                      if (window.confirm(`确定要删除步骤 "${selectedStep.stepName}" 吗？`)) {
                        await onDeleteStep(flow.flowId, selectedStep.stepId);
                        setSelectedStepId(null);
                      }
                    }}
                    className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600 transition-colors cursor-pointer"
                    title="删除此步骤"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>

                {/* Step Name */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-slate-700">{t('how.stepNameLabel', '步骤名称')}</label>
                  <input
                    type="text"
                    value={selectedStep.stepName}
                    onChange={(e) => void onUpdateStep(flow.flowId, selectedStep.stepId, { stepName: e.target.value })}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-900 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 shadow-2xs"
                  />
                </div>

                {/* Step Description */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-slate-700">{t('how.stepDescLabel', '步骤描述')}</label>
                  <textarea
                    value={selectedStep.stepDescription || ''}
                    onChange={(e) => void onUpdateStep(flow.flowId, selectedStep.stepId, { stepDescription: e.target.value })}
                    rows={2}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-900 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 shadow-2xs"
                  />
                </div>

                {/* Step Type */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-slate-700">{t('how.stepTypeLabel', '步骤类型')}</label>
                  <select
                    value={selectedStep.stepType || 'actorAction'}
                    onChange={(e) => void onUpdateStep(flow.flowId, selectedStep.stepId, { stepType: e.target.value as any })}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-900 outline-none focus:border-indigo-500 shadow-2xs"
                  >
                    <option value="actorAction">{t('how.stepType.actorAction', '参与者动作')}</option>
                    <option value="systemAction">{t('how.stepType.systemAction', '系统操作')}</option>
                    <option value="judgment">{t('how.stepType.judgment', '判断分支')}</option>
                  </select>
                </div>

                {/* Actors */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-slate-700">{t('how.assignedActorsLabel', '关联参与者')}</label>
                  <div className="space-y-1 max-h-28 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50/50 p-2">
                    {actors.map((act) => {
                      const isChecked = (selectedStep.actorIds || []).includes(act.actorId);
                      return (
                        <label key={act.actorId} className="flex items-center gap-2 px-1 py-1 hover:bg-white rounded cursor-pointer">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={(e) => {
                              const next = e.target.checked
                                ? [...(selectedStep.actorIds || []), act.actorId]
                                : (selectedStep.actorIds || []).filter((id) => id !== act.actorId);
                              void onUpdateStep(flow.flowId, selectedStep.stepId, { actorIds: next });
                            }}
                            className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                          />
                          <span className="truncate text-slate-700">{act.actorName}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>

                {/* Business Objects Input/Output */}
                <div className="space-y-2">
                  <label className="text-[11px] font-bold text-slate-700">{t('how.businessObjectsLabel', '输入 / 输出业务对象')}</label>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-2 max-h-32 overflow-y-auto">
                      <p className="text-[10px] font-bold text-amber-700 mb-1">输入对象</p>
                      {businessObjects.map((bo) => {
                        const isChecked = (selectedStep.inputBusinessObjectIds || []).includes(bo.businessObjectId);
                        return (
                          <label key={bo.businessObjectId} className="flex items-center gap-1.5 py-0.5 text-[11px] cursor-pointer">
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={(e) => {
                                const next = e.target.checked
                                ? [...(selectedStep.inputBusinessObjectIds || []), bo.businessObjectId]
                                : (selectedStep.inputBusinessObjectIds || []).filter((id) => id !== bo.businessObjectId);
                                void onUpdateStep(flow.flowId, selectedStep.stepId, { inputBusinessObjectIds: next });
                              }}
                              className="rounded border-slate-300 text-amber-600 focus:ring-amber-500"
                            />
                            <span className="truncate text-slate-700">{bo.businessObjectName}</span>
                          </label>
                        );
                      })}
                    </div>

                    <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-2 max-h-32 overflow-y-auto">
                      <p className="text-[10px] font-bold text-emerald-700 mb-1">输出对象</p>
                      {businessObjects.map((bo) => {
                        const isChecked = (selectedStep.outputBusinessObjectIds || []).includes(bo.businessObjectId);
                        return (
                          <label key={bo.businessObjectId} className="flex items-center gap-1.5 py-0.5 text-[11px] cursor-pointer">
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={(e) => {
                                const next = e.target.checked
                                ? [...(selectedStep.outputBusinessObjectIds || []), bo.businessObjectId]
                                : (selectedStep.outputBusinessObjectIds || []).filter((id) => id !== bo.businessObjectId);
                                void onUpdateStep(flow.flowId, selectedStep.stepId, { outputBusinessObjectIds: next });
                              }}
                              className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                            />
                            <span className="truncate text-slate-700">{bo.businessObjectName}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Next Steps (Direct Links Checkbox Manager) */}
                <div className="space-y-1.5 pt-2 border-t border-slate-100">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-bold text-indigo-700 flex items-center gap-1">
                      <Link2 className="h-3.5 w-3.5" />
                      {t('how.nextStepsLabel', '下一步分支连线 (Next Steps)')}
                    </label>
                    <span className="text-[10px] text-slate-400">{(selectedStep.nextStepIds || []).length} 项</span>
                  </div>
                  <div className="space-y-1 max-h-36 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50/50 p-2">
                    {steps.filter((s) => s.stepId !== selectedStep.stepId).map((targetStep) => {
                      const isLinked = (selectedStep.nextStepIds || []).includes(targetStep.stepId);
                      return (
                        <label key={targetStep.stepId} className="flex items-center gap-2 px-1 py-1 hover:bg-white rounded cursor-pointer">
                          <input
                            type="checkbox"
                            checked={isLinked}
                            onChange={(e) => {
                              const next = e.target.checked
                                ? [...(selectedStep.nextStepIds || []), targetStep.stepId]
                                : (selectedStep.nextStepIds || []).filter((id) => id !== targetStep.stepId);
                              void onUpdateStep(flow.flowId, selectedStep.stepId, { nextStepIds: next });
                            }}
                            className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                          />
                          <span className="truncate text-slate-700">
                            #{steps.findIndex((s) => s.stepId === targetStep.stepId) + 1} {targetStep.stepName}
                          </span>
                        </label>
                      );
                    })}
                    {steps.length <= 1 && (
                      <p className="p-2 text-[11px] text-slate-400 text-center">暂无其他步骤可连接</p>
                    )}
                  </div>
                </div>
              </div>
            ) : selectedLinkId ? (
              /* Link is Selected */
              (() => {
                const [fromIdStr, toIdStr] = selectedLinkId.split('-');
                const fromId = parseInt(fromIdStr, 10);
                const toId = parseInt(toIdStr, 10);
                const fromNode = steps.find((s) => s.stepId === fromId);
                const toNode = steps.find((s) => s.stepId === toId);

                return (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                      <h3 className="font-extrabold text-sm text-slate-900 flex items-center gap-2">
                        <Link2 className="h-4 w-4 text-rose-500" />
                        {t('how.linkInspector', '分支连线详情')}
                      </h3>
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 space-y-3">
                      <div>
                        <span className="text-[10px] font-bold text-slate-500">起始步骤</span>
                        <p className="font-bold text-slate-900 truncate mt-0.5">{fromNode?.stepName || `步骤 #${fromId}`}</p>
                      </div>
                      <div className="flex justify-center text-slate-400">
                        <ArrowRight className="h-4 w-4 rotate-90" />
                      </div>
                      <div>
                        <span className="text-[10px] font-bold text-slate-500">目标下一步</span>
                        <p className="font-bold text-slate-900 truncate mt-0.5">{toNode?.stepName || `步骤 #${toId}`}</p>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleDisconnect(fromId, toId)}
                      className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-rose-50 border border-rose-200 px-4 py-2.5 text-xs font-bold text-rose-700 hover:bg-rose-100 transition-colors cursor-pointer"
                    >
                      <Unlink className="h-4 w-4" />
                      {t('how.disconnectLink', '断开此分支连线')}
                    </button>
                  </div>
                );
              })()
            ) : (
              /* Nothing Selected: General Flow Info */
              <div className="space-y-4">
                <div className="border-b border-slate-100 pb-3">
                  <h3 className="font-extrabold text-sm text-slate-900">{t('how.flowOverview', '流程概要')}</h3>
                  <p className="text-[11px] text-slate-500 mt-1">{flow.flowName}</p>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-3.5 text-slate-600 space-y-2 text-[11px]">
                  <p className="font-bold text-slate-800">💡 画布交互提示：</p>
                  <ul className="space-y-1.5 list-disc pl-4">
                    <li><strong className="text-slate-900">拖拽连线</strong>：按住步骤卡片右侧的箭头圆点拖动到其他步骤。</li>
                    <li><strong className="text-slate-900">断开连线</strong>：点击连线即可高亮选中并一键断开。</li>
                    <li><strong className="text-slate-900">自由布局</strong>：按住步骤卡片随意拖拽位置。</li>
                    <li><strong className="text-slate-900">缩放平移</strong>：滚轮缩放画布，按住空白处拖拽平移。</li>
                  </ul>
                </div>
              </div>
            )}
          </aside>
        </div>

        {/* 4. Resizing Handles for Modal Edges & Corners */}
        {!isMaximized && (
          <>
            {/* Right edge */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 'e')}
              className="absolute right-0 top-16 bottom-0 w-2 cursor-ew-resize hover:bg-indigo-500/20 z-40 transition-colors"
              title="拖动调整窗口宽度"
            />
            {/* Left edge */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 'w')}
              className="absolute left-0 top-16 bottom-0 w-2 cursor-ew-resize hover:bg-indigo-500/20 z-40 transition-colors"
              title="拖动调整窗口宽度"
            />
            {/* Bottom edge */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 's')}
              className="absolute left-0 right-0 bottom-0 h-2 cursor-ns-resize hover:bg-indigo-500/20 z-40 transition-colors"
              title="拖动调整窗口高度"
            />
            {/* Bottom-right diagonal corner */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 'se')}
              className="absolute right-1.5 bottom-1.5 w-5 h-5 cursor-nwse-resize z-50 flex items-center justify-center group/resize rounded-br-2xl"
              title="拖动调整窗口尺寸"
            >
              <svg className="w-3.5 h-3.5 text-slate-300 group-hover/resize:text-indigo-600 transition-colors" viewBox="0 0 24 24" fill="currentColor">
                <circle cx="20" cy="4" r="2" />
                <circle cx="20" cy="12" r="2" />
                <circle cx="12" cy="12" r="2" />
                <circle cx="20" cy="20" r="2" />
                <circle cx="12" cy="20" r="2" />
                <circle cx="4" cy="20" r="2" />
              </svg>
            </div>
            {/* Bottom-left diagonal corner */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 'sw')}
              className="absolute left-1.5 bottom-1.5 w-5 h-5 cursor-nesw-resize z-50 flex items-center justify-center group/resize rounded-bl-2xl"
              title="拖动调整窗口尺寸"
            />
          </>
        )}

        {/* 5. Quick Add Step Dialog (Inside Focus Modal) */}
        {isAddStepOpen && (
          <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-in fade-in">
            <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-4 text-slate-900">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <h3 className="text-sm font-bold text-slate-900">{t('how.addNewStepModalTitle', '新增流程步骤')}</h3>
                <button
                  type="button"
                  onClick={() => setIsAddStepOpen(false)}
                  className="text-slate-400 hover:text-slate-600 cursor-pointer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">步骤名称 *</label>
                  <input
                    type="text"
                    value={newStepName}
                    onChange={(e) => setNewStepName(e.target.value)}
                    placeholder="例如：输入手机号并获取验证码"
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900 outline-none focus:border-indigo-500 shadow-2xs"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">步骤描述</label>
                  <textarea
                    value={newStepDesc}
                    onChange={(e) => setNewStepDesc(e.target.value)}
                    rows={2}
                    placeholder="补充说明步骤的前置条件或操作细节"
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900 outline-none focus:border-indigo-500 shadow-2xs"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">步骤类型</label>
                  <select
                    value={newStepType}
                    onChange={(e) => setNewStepType(e.target.value as any)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900 outline-none shadow-2xs"
                  >
                    <option value="actorAction">参与者动作 (actorAction)</option>
                    <option value="systemAction">系统操作 (systemAction)</option>
                    <option value="judgment">判断分支 (judgment)</option>
                  </select>
                </div>

                {/* Actor Selector (Required when actorAction) */}
                {newStepType === 'actorAction' && (
                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 mb-1">
                      执行参与者角色 <span className="text-rose-500">*</span>
                    </label>
                    {actors.length > 0 ? (
                      <div className="space-y-1 max-h-28 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50/50 p-2">
                        {actors.map((act) => {
                          const isChecked = newStepActorIds.includes(act.actorId);
                          return (
                            <label key={act.actorId} className="flex items-center gap-2 px-1 py-1 hover:bg-white rounded cursor-pointer">
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setNewStepActorIds((prev) => [...prev, act.actorId]);
                                  } else {
                                    setNewStepActorIds((prev) => prev.filter((id) => id !== act.actorId));
                                  }
                                }}
                                className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                              />
                              <span className="truncate text-slate-700 text-xs">{act.actorName}</span>
                            </label>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-xl p-2.5">
                        当前暂未定义角色，请先在 What 阶段定义参与者角色，或在此将步骤类型切换为“系统操作”。
                      </p>
                    )}
                  </div>
                )}

                {/* Connect from Step */}
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">从哪个步骤连接至此新步骤？</label>
                  <select
                    value={newStepConnectFromId || ''}
                    onChange={(e) => setNewStepConnectFromId(e.target.value ? parseInt(e.target.value, 10) : null)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900 outline-none shadow-2xs"
                  >
                    <option value="">(不自动从已有步骤连线)</option>
                    {steps.map((s, idx) => (
                      <option key={s.stepId} value={s.stepId}>
                        #{idx + 1} {s.stepName}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsAddStepOpen(false)}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50 cursor-pointer shadow-2xs"
                >
                  取消
                </button>
                <button
                  type="button"
                  disabled={!newStepName.trim() || (newStepType === 'actorAction' && newStepActorIds.length === 0)}
                  onClick={async () => {
                    if (!newStepName.trim()) return;
                    if (newStepType === 'actorAction' && newStepActorIds.length === 0) {
                      alert(t('how.actorRequired', '参与者动作步骤必须选择至少一个参与者角色！'));
                      return;
                    }
                    await onAddStep(flow.flowId, {
                      stepName: newStepName.trim(),
                      stepDescription: newStepDesc.trim(),
                      stepType: newStepType,
                      actorIds: newStepActorIds,
                      inputBusinessObjectIds: newStepInputBoIds,
                      outputBusinessObjectIds: newStepOutputBoIds,
                      connectFromStepId: newStepConnectFromId,
                    });
                    setIsAddStepOpen(false);
                  }}
                  className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-700 disabled:opacity-50 cursor-pointer shadow-sm"
                >
                  确定添加
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
