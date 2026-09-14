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
  Check,
  ChevronLeft,
  ChevronRight,
  HelpCircle,
  Maximize2,
  Minimize2,
  AlertTriangle,
} from 'lucide-react';
import { FlowNode, FlowStepNode, FlowTransition, NodeStatus, ActorNode, BusinessObjectNode, Finding, DomainRule } from '@/core/schema';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { selectTransitionLabel, selectFindingsForStep, selectFindingsForTransition } from '@/core/selectors';
import { cn } from '@/lib/utils';
import { useLocalStorageState } from '@/lib/useLocalStorageState';
import { PathProjectionSelector } from '@/components/how/flow_canvas/PathProjectionSelector';
import { FlowRuleAssociations } from '@/components/shared/FlowRuleAssociations';

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
  onCreateTransition?: (flowId: number, payload: { sourceStepId: number; targetStepId: number; conditionText?: string; label?: string; isDefault?: boolean; ruleIds?: number[] }) => Promise<void>;
  onUpdateTransition?: (flowId: number, transitionId: number, updates: Partial<FlowTransition>) => Promise<void>;
  onDeleteTransition?: (flowId: number, transitionId: number) => Promise<void>;
  readOnly?: boolean;
  initialSelectedStepId?: number | null;
  initialSelectedTransitionId?: string | number | null;
}

// Compute DAG hierarchical positions
function computeHierarchicalPositions(steps: FlowStepNode[], transitions: FlowTransition[] = []): Record<number, { x: number; y: number }> {
  const positions: Record<number, { x: number; y: number }> = {};
  if (steps.length === 0) return positions;

  const colWidth = 360;
  const rowHeight = 220;
  const visited = new Set<number>();

  const allTargetIds = new Set(transitions.map((t) => t.targetStepId));
  const startNodes = steps.filter((s) => !allTargetIds.has(s.stepId));

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

    const outgoing = transitions.filter((t) => t.sourceStepId === stepId);
    outgoing.forEach((tr, idx) => {
      if (!visited.has(tr.targetStepId)) {
        queue.push({ stepId: tr.targetStepId, col: col + 1, row: idx });
      }
    });
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

const EMPTY_FINDINGS: Finding[] = [];

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
  onCreateTransition,
  onUpdateTransition,
  onDeleteTransition,
  readOnly,
  initialSelectedStepId,
  initialSelectedTransitionId,
}: FocusFlowCanvasModalProps) {
  const { t } = useTranslation();
  const workspaceCanWrite = useWorkspaceStore((s) => s.workspaceCanWrite);
  const domainRules = useWorkspaceStore((s) => s.ir?.domainRules || []);
  const refineFlow = useWorkspaceStore((s) => s.refineFlow);
  const isGeneratingChoices = useWorkspaceStore((s) => s.isGeneratingChoices);
  const backendChoiceGroups = useWorkspaceStore((s) => s.backendChoiceGroups || {});
  const canWrite = typeof workspaceCanWrite === 'function' ? workspaceCanWrite() : true;
  const effectiveReadOnly = Boolean(readOnly ?? !canWrite);

  const activeRefinementGroup = useMemo(() => {
    if (!flow) return null;
    const flowIdNum = Number(flow.flowId || flow.id);
    const groups = Object.values(backendChoiceGroups || {});
    return groups.find(
      (g: any) =>
        (g.generationType === 'flow_refinement' || g.generation_type === 'flow_refinement') &&
        (g.status === 'open' || g.status === 'pending') &&
        (Number(g.target?.flow_id) === flowIdNum ||
         Number(g.target?.target_id) === flowIdNum ||
         Number(g.target?.flowId) === flowIdNum ||
         Number(g.target?.targetId) === flowIdNum)
    );
  }, [backendChoiceGroups, flow]);

  const refinementPreview = useMemo(() => {
    const candidate = activeRefinementGroup?.choices?.[0];
    return candidate?.preview || candidate?.payload || null;
  }, [activeRefinementGroup]);

  const refinementSteps = useMemo(() => {
    return Array.isArray(refinementPreview?.steps_added) ? refinementPreview.steps_added : [];
  }, [refinementPreview]);

  const refinementTransitions = useMemo(() => {
    const added = Array.isArray(refinementPreview?.transitions_added) ? refinementPreview.transitions_added : [];
    const updated = Array.isArray(refinementPreview?.transitions_updated) ? refinementPreview.transitions_updated : [];
    return { added, updated };
  }, [refinementPreview]);

  const refinementRules = useMemo(() => {
    return Array.isArray(refinementPreview?.rules_added) ? refinementPreview.rules_added : [];
  }, [refinementPreview]);

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
  const [canvasTipsCollapsed, setCanvasTipsCollapsed] = useLocalStorageState('flow-canvas-tips-collapsed', false);
  const [inspectorCollapsed, setInspectorCollapsed] = useLocalStorageState('flow-inspector-collapsed', false);

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
  const [selectedLinkId, setSelectedLinkId] = useState<string | null>(null);
  const [selectedPathId, setSelectedPathId] = useState<string | null>(null);

  const loadFlowPaths = useWorkspaceStore((s) => s.loadFlowPaths);
  const flowPathProjections = useWorkspaceStore((s) => s.flowPathProjections);
  const flowPathLoading = useWorkspaceStore((s) => s.flowPathLoading);
  const flowPathErrors = useWorkspaceStore((s) => s.flowPathErrors);
  const paths = useMemo(() => {
    return (flow ? flowPathProjections[flow.flowId] : []) || [];
  }, [flow, flowPathProjections]);

  const selectedPath = useMemo(() => {
    return paths.find((p) => p.pathId === selectedPathId) || null;
  }, [paths, selectedPathId]);

  useEffect(() => {
    if (isOpen && flow) {
      void loadFlowPaths(flow.flowId).catch(() => {});
    }
  }, [isOpen, flow?.flowId, loadFlowPaths]);

  useEffect(() => {
    if (initialSelectedStepId !== undefined && initialSelectedStepId !== null) {
      setSelectedStepId(initialSelectedStepId);
      setSelectedLinkId(null);
    }
  }, [initialSelectedStepId]);

  useEffect(() => {
    if (initialSelectedTransitionId !== undefined && initialSelectedTransitionId !== null) {
      setSelectedLinkId(String(initialSelectedTransitionId));
      setSelectedStepId(null);
    }
  }, [initialSelectedTransitionId]);

  // Transition form editing state
  const [transitionLabel, setTransitionLabel] = useState('');
  const [transitionCondition, setTransitionCondition] = useState('');
  const [transitionPosition, setTransitionPosition] = useState<number | ''>('');
  const [transitionIsDefault, setTransitionIsDefault] = useState(false);
  const [transitionTags, setTransitionTags] = useState<string[]>([]);
  const [transitionStatus, setTransitionStatus] = useState<NodeStatus>('confirmed');
  const [transitionRuleIds, setTransitionRuleIds] = useState<number[]>([]);
  const [isSavingTransition, setIsSavingTransition] = useState(false);

  const selectedTransition = useMemo(() => {
    if (!selectedLinkId || !flow?.transitions) return null;
    return flow.transitions.find((t) => String(t.transitionId || t.id) === selectedLinkId) || null;
  }, [selectedLinkId, flow?.transitions]);

  useEffect(() => {
    if (selectedTransition) {
      setTransitionLabel(selectedTransition.label || '');
      setTransitionCondition(selectedTransition.conditionText || '');
      setTransitionPosition(selectedTransition.position ?? '');
      setTransitionIsDefault(Boolean(selectedTransition.isDefault));
      setTransitionTags(selectedTransition.semanticTags || (selectedTransition as any).tags || []);
      setTransitionStatus((selectedTransition.confirmationStatus as NodeStatus) || 'confirmed');
      setTransitionRuleIds(selectedTransition.ruleIds || []);
    }
  }, [selectedTransition]);

  const handleSaveTransition = async () => {
    if (!flow || !selectedTransition || effectiveReadOnly) return;
    const tId = selectedTransition.transitionId || selectedTransition.id;
    if (!tId) return;
    setIsSavingTransition(true);
    try {
      const updates: any = {
        label: transitionLabel.trim(),
        conditionText: transitionCondition.trim(),
        isDefault: transitionIsDefault,
        semanticTags: transitionTags,
        confirmationStatus: transitionStatus,
        ruleIds: transitionRuleIds,
      };
      if (transitionPosition !== '') {
        updates.position = Number(transitionPosition);
      }
      if (onUpdateTransition) {
        await onUpdateTransition(flow.flowId, tId, updates);
      } else {
        await useWorkspaceStore.getState().updateFlowTransition(flow.flowId, tId, updates);
      }
    } finally {
      setIsSavingTransition(false);
    }
  };

  const handleDeleteSelectedTransition = async () => {
    if (!flow || !selectedTransition || effectiveReadOnly) return;
    const tId = selectedTransition.transitionId || selectedTransition.id;
    if (!tId) return;
    if (onDeleteTransition) {
      await onDeleteTransition(flow.flowId, tId);
    } else {
      await useWorkspaceStore.getState().deleteFlowTransition(flow.flowId, tId);
    }
    setSelectedLinkId(null);
  };

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
    return computeHierarchicalPositions(steps, flow?.transitions || []);
  }, [steps]);

  const resolveRefinementNodePos = useCallback(
    (ref: any) => {
      if (typeof ref === 'number') {
        const step = steps.find((s, idx) => idx + 1 === ref || s.stepId === ref);
        if (step) return nodePositions[step.stepId] || defaultPositions[step.stepId] || { x: 40, y: 40 };
      }
      if (typeof ref === 'string') {
        const rIdx = refinementSteps.findIndex((rs: any) => rs.temp_id === ref);
        if (rIdx !== -1) {
          return { x: 60 + (steps.length + rIdx) * 320, y: 80 };
        }
        const step = steps.find((s) => s.logicalUuid === ref || String(s.stepId) === ref);
        if (step) return nodePositions[step.stepId] || defaultPositions[step.stepId] || { x: 40, y: 40 };
      }
      return null;
    },
    [steps, refinementSteps, nodePositions, defaultPositions]
  );

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
    // 仅在打开/切换流程时初始化视图；编辑内容引起的 defaultPositions 变化
    // 不应重置平移缩放、节点位置、选中项或重播入场动画（否则每次编辑都会抖动）
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, flow?.flowId]);

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
    const targetPos = computeHierarchicalPositions(steps, flow?.transitions || []);
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
    if (linkingState && flow && !effectiveReadOnly) {
      const targetElement = document.elementFromPoint(e.clientX, e.clientY);
      const targetNodeEl = targetElement?.closest('[data-step-id]');
      if (targetNodeEl) {
        const targetId = parseInt(targetNodeEl.getAttribute('data-step-id') || '', 10);
        if (!isNaN(targetId) && targetId !== linkingState.fromStepId) {
          if (onCreateTransition) {
            void onCreateTransition(flow.flowId, { sourceStepId: linkingState.fromStepId, targetStepId: targetId, isDefault: true });
          } else {
            void useWorkspaceStore.getState().createFlowTransition(flow.flowId, { sourceStepId: linkingState.fromStepId, targetStepId: targetId, isDefault: true });
          }
        }
      }
      setLinkingState(null);
    } else if (linkingState) {
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
    if (effectiveReadOnly) return;
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
  const handleDisconnect = async (fromStepId: number, toStepId: number, transitionId?: number) => {
    if (!flow || effectiveReadOnly) return;
    const trans = (flow.transitions || []).find(t => (transitionId && (t.transitionId === transitionId || t.id === transitionId)) || (t.sourceStepId === fromStepId && t.targetStepId === toStepId));
    const tId = transitionId || trans?.transitionId || trans?.id;
    if (tId) {
      if (onDeleteTransition) {
        await onDeleteTransition(flow.flowId, tId);
      } else {
        await useWorkspaceStore.getState().deleteFlowTransition(flow.flowId, tId);
      }
    }
    setSelectedLinkId(null);
  };

  // Currently selected step object
  const selectedStep = useMemo(() => {
    return steps.find((s) => s.stepId === selectedStepId) || null;
  }, [steps, selectedStepId]);

  const openRule = (rule: DomainRule) => {
    useWorkspaceStore.getState().setSelectedObject({ ...rule, kind: 'rule' });
    onClose();
  };

  const storeFindings = useWorkspaceStore((s) => s.ir?.findings);
  const irFindings = storeFindings || EMPTY_FINDINGS;

  const stepFindings = useMemo(() => {
    if (!selectedStep) return [];
    return selectFindingsForStep(selectedStep, irFindings);
  }, [irFindings, selectedStep]);

  const transitionFindings = useMemo(() => {
    if (!selectedTransition) return [];
    return selectFindingsForTransition(selectedTransition, irFindings);
  }, [irFindings, selectedTransition]);

  const stepChoices = useMemo(() => {
    if (!selectedStep) return [];
    const groups = Object.values(backendChoiceGroups || {});
    return groups.flatMap((g: any) =>
      (g.choices || []).filter((c: any) =>
        c.stepId === selectedStep.stepId ||
        c.target?.stepId === selectedStep.stepId ||
        c.target?.step_id === selectedStep.stepId
      )
    );
  }, [selectedStep, backendChoiceGroups]);

  // 步骤文本草稿：本地即时回显 + 防抖提交，避免每次击键都触发保存与全量刷新
  const [stepNameDraft, setStepNameDraft] = useState('');
  const [stepDescDraft, setStepDescDraft] = useState('');
  const stepTextSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const step = steps.find((s) => s.stepId === selectedStepId);
    setStepNameDraft(step?.stepName || '');
    setStepDescDraft(step?.stepDescription || '');
    if (stepTextSaveTimer.current) {
      clearTimeout(stepTextSaveTimer.current);
      stepTextSaveTimer.current = null;
    }
    // 仅在切换选中步骤时同步草稿；编辑保存后的内容刷新不应覆盖正在输入的草稿
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedStepId]);

  const scheduleStepTextSave = (field: 'stepName' | 'stepDescription', value: string) => {
    if (!flow || selectedStepId === null || effectiveReadOnly) return;
    if (stepTextSaveTimer.current) clearTimeout(stepTextSaveTimer.current);
    stepTextSaveTimer.current = setTimeout(() => {
      stepTextSaveTimer.current = null;
      void onUpdateStep(flow.flowId, selectedStepId, { [field]: value });
    }, 500);
  };

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
        role="dialog"
        aria-modal="true"
        aria-labelledby="focus-flow-modal-title"
        className={cn(
          'relative bg-white border border-slate-200/90 rounded-3xl shadow-2xl flex flex-col overflow-hidden text-slate-900 transition-[width,height] duration-75',
          isResizing && 'transition-none select-none'
        )}
      >
      {/* Canvas header */}
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
                <h2 id="focus-flow-modal-title" className="text-base font-extrabold text-slate-900">{flow.flowName}</h2>
                <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-[10px] font-bold text-indigo-700 border border-indigo-100">
                  {t('how.focusMode', '专注流程画布')}
                </span>
                {effectiveReadOnly && (
                  <span className="rounded-md bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700 border border-amber-200">
                    {t('common.readOnly', '只读模式')}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 max-w-lg truncate">{flow.flowDescription || t('how.noDescription', '暂无描述')}</p>
            </div>
          </div>

          {/* Action Controls & Canvas Utilities */}
          <div className="flex items-center gap-2.5">
            {activeRefinementGroup && (
              <span
                data-testid="refinement-overlay-badge"
                className="hidden lg:inline-flex items-center gap-1 rounded-full bg-emerald-100 border border-emerald-200 px-2 py-0.5 text-[10px] font-extrabold text-emerald-800"
              >
                <Sparkles className="h-3 w-3 text-emerald-600 animate-pulse" />
                {t('how.refinementOverlayBadge', '细化候选待处理')}
                {refinementSteps.length > 0 && t('how.canvas.refinementStepsDelta', ` (+${refinementSteps.length}步骤)`, { count: refinementSteps.length })}
                {refinementTransitions.added.length > 0 && t('how.canvas.refinementTransitionsDelta', ` (+${refinementTransitions.added.length}转移)`, { count: refinementTransitions.added.length })}
                {refinementRules.length > 0 && t('how.canvas.refinementRulesDelta', ` (+${refinementRules.length}规则)`, { count: refinementRules.length })}
              </span>
            )}

            {flow && (
              <PathProjectionSelector
                paths={paths}
                selectedPathId={selectedPathId}
                loading={Boolean(flowPathLoading[flow.flowId])}
                error={flowPathErrors[flow.flowId] || null}
                onSelect={setSelectedPathId}
                onRetry={() => void loadFlowPaths(flow.flowId).catch(() => {})}
              />
            )}

            {!effectiveReadOnly && (
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
            )}

            {!effectiveReadOnly && (
              <button
                type="button"
                disabled={isGeneratingChoices}
                onClick={async () => {
                  await refineFlow(flow.flowId, selectedStepId || undefined);
                  onClose();
                }}
                className="inline-flex items-center gap-1.5 rounded-xl border border-indigo-200 bg-indigo-50/80 hover:bg-indigo-100 text-indigo-700 px-3 py-1.5 text-xs font-bold transition-colors cursor-pointer shadow-2xs disabled:opacity-50"
                title={selectedStepId ? t('how.refineStepPathTitle', '针对当前选中步骤深入细化前后路径与规则') : t('how.refineFlowTitle', '针对当前流程深入细化分支与规则')}
              >
                <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
                {selectedStepId ? t('how.refineStepPath', '深入分析步骤路径') : t('how.refineFlowPath', '深入分析路径')}
              </button>
            )}

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
                title={t('how.canvas.zoomOut', '缩小')}
              >
                <ZoomOut className="h-3.5 w-3.5" />
              </button>
              <span className="min-w-[40px] text-center text-[11px] font-mono">{Math.round(panZoom.scale * 100)}%</span>
              <button
                type="button"
                onClick={() => setPanZoom((p) => ({ ...p, scale: Math.min(2.0, Math.round((p.scale + 0.1) * 10) / 10) }))}
                className="p-1 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                title={t('how.canvas.zoomIn', '放大')}
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
              title={isMaximized ? t('how.canvas.restoreWindow', '还原窗口大小') : t('how.canvas.maximizeWindow', '最大化窗口')}
            >
              {isMaximized ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
            </button>

            {/* Close button */}
            <button
              type="button"
              onClick={onClose}
              aria-label={t('shell.close', '关闭')}
              className="w-8 h-8 rounded-full border border-slate-200 bg-white hover:bg-slate-50 text-slate-400 hover:text-slate-700 flex items-center justify-center transition-colors cursor-pointer shadow-2xs"
              title={t('shell.close', '关闭')}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </header>

        {/* Screen Reader Accessible Alternative View */}
        <section aria-label={t('how.canvas.accessibleViewTitle', '流程步骤与流转可访问列表')} className="sr-only">
          <h3>{flow.flowName} - {t('how.canvas.accessibleSteps', '步骤列表')}</h3>
          <ul>
            {steps.map((step, idx) => {
              const outTransitions = (flow.transitions || []).filter((t) => t.sourceStepId === step.stepId);
              return (
                <li key={step.stepId}>
                  <h4>{idx + 1}. {step.stepName} ({step.stepType})</h4>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedStepId(step.stepId);
                      setSelectedLinkId(null);
                    }}
                  >
                    {t('how.canvas.selectStep', { name: step.stepName, defaultValue: `选择步骤 ${step.stepName}` })}
                  </button>
                  {step.stepDescription && <p>{step.stepDescription}</p>}
                  {outTransitions.length > 0 ? (
                    <div>
                      <h5>{t('how.canvas.accessibleTransitions', '分支流转列表')}:</h5>
                      <ul>
                        {outTransitions.map((trans) => {
                          const target = steps.find((s) => s.stepId === trans.targetStepId);
                          const tId = trans.transitionId || trans.id;
                          return (
                            <li key={trans.transitionId || `${trans.sourceStepId}-${trans.targetStepId}`}>
                              <span>
                                → {target?.stepName || t('how.canvas.stepNumbered', '步骤 #{{id}}', { id: trans.targetStepId })}
                                {trans.conditionText ? ` [${trans.conditionText}]` : ''}
                                {trans.position !== undefined ? t('how.canvas.weightNumbered', ' (权重: {{position}})', { position: trans.position }) : ''}
                                {trans.isDefault ? ` (${t('how.canvas.defaultBranch', '默认分支')})` : ''}
                              </span>
                              <div>
                                <button
                                  type="button"
                                  onClick={() => {
                                    if (tId) setSelectedLinkId(String(tId));
                                    setSelectedStepId(null);
                                  }}
                                >
                                  {t('how.canvas.selectTransition', {
                                    from: step.stepName,
                                    to: target?.stepName || trans.targetStepId,
                                  })}
                                </button>
                                {!effectiveReadOnly && tId && (
                                  <>
                                    <button
                                      type="button"
                                      onClick={async () => {
                                        if (onUpdateTransition) {
                                          await onUpdateTransition(flow.flowId, tId, { isDefault: !trans.isDefault });
                                        } else {
                                          await useWorkspaceStore.getState().updateFlowTransition(flow.flowId, tId, { isDefault: !trans.isDefault });
                                        }
                                      }}
                                    >
                                      {trans.isDefault
                                        ? t('how.canvas.clearDefault', '取消默认分支')
                                        : t('how.canvas.setDefaultBranch', '设为默认分支')}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={async () => {
                                        if (onDeleteTransition) {
                                          await onDeleteTransition(flow.flowId, tId);
                                        } else {
                                          await useWorkspaceStore.getState().deleteFlowTransition(flow.flowId, tId);
                                        }
                                        if (selectedLinkId === String(tId)) {
                                          setSelectedLinkId(null);
                                        }
                                      }}
                                    >
                                      {t('how.canvas.disconnectTransition', '断开连接')}
                                    </button>
                                  </>
                                )}
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ) : (
                    <p>{t('how.canvas.noOutbound', '终点步骤，无流出分支')}</p>
                  )}
                </li>
              );
            })}
          </ul>
        </section>

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
              <button
                type="button"
                onClick={() => setCanvasTipsCollapsed((v) => !v)}
                title={canvasTipsCollapsed ? t('how.canvasTipsAriaExpand') : t('how.canvasTipsAriaCollapse')}
                className="shrink-0 cursor-pointer"
              >
                <HelpCircle className="h-4 w-4 text-indigo-600" />
              </button>
              {!canvasTipsCollapsed && (
                <span>{t('how.canvasTips', '💡 提示：按住步骤右侧点拖拽可快速连线；点击连线可断开；拖动节点自由布局')}</span>
              )}
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
                  <marker id="light-arrow-refinement" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
                    <polygon points="0 0, 8 3, 0 6" fill="#059669" />
                  </marker>
                </defs>

                {/* Persisted transitions */}
                {(flow.transitions || []).map((trans) => {
                  const fromPos = nodePositions[trans.sourceStepId] || defaultPositions[trans.sourceStepId];
                  const toPos = nodePositions[trans.targetStepId] || defaultPositions[trans.targetStepId];
                  if (!fromPos || !toPos) return null;

                  const startX = fromPos.x + 280;
                  const startY = fromPos.y + 60;
                  const endX = toPos.x;
                  const endY = toPos.y + 60;

                  let pathD = '';
                  let midX = (startX + endX) / 2;
                  let midY = (startY + endY) / 2;
                  if (endX <= startX) {
                    const arcOffset = Math.max(75, Math.abs(startX - endX) * 0.2);
                    const controlY = Math.min(startY, endY) - arcOffset;
                    midY = controlY;
                    pathD = `M ${startX} ${startY} C ${startX + 80} ${startY}, ${startX + 40} ${controlY}, ${midX} ${controlY} S ${endX - 80} ${endY}, ${endX} ${endY}`;
                  } else {
                    const cp1X = startX + Math.min(80, (endX - startX) * 0.5);
                    const cp1Y = startY;
                    const cp2X = endX - Math.min(80, (endX - startX) * 0.5);
                    const cp2Y = endY;
                    pathD = `M ${startX} ${startY} C ${cp1X} ${cp1Y}, ${cp2X} ${cp2Y}, ${endX} ${endY}`;
                  }

                  const transId = trans.transitionId || trans.id;
                  const linkId = transId ? String(transId) : `${trans.sourceStepId}-${trans.targetStepId}`;
                  const isSelected = selectedLinkId === linkId;
                  const isHighlighted = selectedStepId === trans.sourceStepId || selectedStepId === trans.targetStepId;
                  const isInSelectedPath = selectedPath ? selectedPath.transitionIds.includes(transId || -1) : false;
                  const labelMeta = selectTransitionLabel(trans);

                    return (
                      <g key={linkId} data-testid={`transition-edge-${linkId}`} className="pointer-events-auto">
                        {/* Thick clickable hit area */}
                        <path
                          data-testid={`transition-hitarea-${linkId}`}
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
                          stroke={isSelected ? '#f43f5e' : isInSelectedPath ? '#059669' : isHighlighted ? '#6366f1' : '#a5b4fc'}
                          strokeWidth={isSelected ? 3.5 : isInSelectedPath ? 3.5 : isHighlighted ? 3 : 2}
                          strokeDasharray={isSelected ? '6 4' : 'none'}
                          markerEnd={isSelected ? 'url(#light-arrow-selected)' : isInSelectedPath ? 'url(#light-arrow-refinement)' : isHighlighted ? 'url(#light-arrow-active)' : 'url(#light-arrow-default)'}
                          className="transition-colors duration-150"
                        />
                        {/* Edge Label Pill at Midpoint */}
                        <foreignObject
                          x={midX - 70}
                          y={midY - 14}
                          width={140}
                          height={28}
                          className="overflow-visible pointer-events-auto"
                        >
                          <div
                            data-testid={`transition-label-${linkId}`}
                            tabIndex={0}
                            role="button"
                            aria-label={t('how.canvas.selectTransitionLabel', '流转: {{text}}', { text: labelMeta.text })}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault();
                                e.stopPropagation();
                                setSelectedLinkId(linkId);
                                setSelectedStepId(null);
                              }
                            }}
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedLinkId(linkId);
                              setSelectedStepId(null);
                            }}
                            className={cn(
                              "inline-flex items-center gap-1 max-w-[136px] px-2 py-0.5 rounded-full text-[10px] font-bold shadow-2xs border cursor-pointer select-none transition-all truncate",
                              isSelected
                                ? "bg-rose-50 text-rose-800 border-rose-300 ring-2 ring-rose-200"
                                : isInSelectedPath
                                ? "bg-emerald-50 text-emerald-800 border-emerald-300 ring-1 ring-emerald-200"
                                : isHighlighted
                                ? "bg-indigo-50 text-indigo-800 border-indigo-200"
                                : labelMeta.status === 'unspecified'
                                ? "bg-slate-50 text-slate-400 border-dashed border-slate-300 hover:border-slate-400"
                                : labelMeta.status === 'condition_fallback'
                                ? "bg-amber-50 text-amber-800 border-amber-200 font-mono hover:border-amber-300"
                                : "bg-white text-slate-700 border-slate-200 hover:border-indigo-300 hover:text-indigo-700"
                            )}
                            title={labelMeta.text}
                          >
                            {trans.isDefault && (
                              <span className="rounded bg-indigo-100 text-indigo-700 px-1 text-[8px] font-black shrink-0">
                                [{t('how.canvas.defaultBranchShort', '默认')}]
                              </span>
                            )}
                            <span className="truncate">{labelMeta.text}</span>
                          </div>
                        </foreignObject>
                      </g>
                    );
                  })}

                {/* Candidate refinement transitions */}
                {refinementTransitions.added.map((trans: any, tIdx: number) => {
                  const fromPos = resolveRefinementNodePos(trans.source_step_ref);
                  const toPos = resolveRefinementNodePos(trans.target_step_ref);
                  if (!fromPos || !toPos) return null;

                  const startX = fromPos.x + 280;
                  const startY = fromPos.y + 60;
                  const endX = toPos.x;
                  const endY = toPos.y + 60;

                  let pathD = '';
                  if (endX <= startX) {
                    const midX = (startX + endX) / 2;
                    const arcOffset = Math.max(75, Math.abs(startX - endX) * 0.2);
                    const controlY = Math.min(startY, endY) - arcOffset;
                    pathD = `M ${startX} ${startY} C ${startX + 80} ${startY}, ${startX + 40} ${controlY}, ${midX} ${controlY} S ${endX - 80} ${endY}, ${endX} ${endY}`;
                  } else {
                    const cp1X = startX + Math.min(80, (endX - startX) * 0.5);
                    const cp1Y = startY;
                    const cp2X = endX - Math.min(80, (endX - startX) * 0.5);
                    const cp2Y = endY;
                    pathD = `M ${startX} ${startY} C ${cp1X} ${cp1Y}, ${cp2X} ${cp2Y}, ${endX} ${endY}`;
                  }

                  const candTransKey = trans.temp_id || `cand-trans-${tIdx}`;
                  return (
                    <g key={candTransKey} data-testid={`candidate-transition-edge-${candTransKey}`}>
                      <path
                        d={pathD}
                        fill="none"
                        stroke="#059669"
                        strokeWidth={2.5}
                        strokeDasharray="6 4"
                        markerEnd="url(#light-arrow-refinement)"
                        className="animate-pulse"
                      />
                    </g>
                  );
                })}

                {/* In-progress connection */}
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
                const isInSelectedPath = selectedPath ? selectedPath.stepIds.includes(step.stepId) : false;

                return (
                  <div
                    key={step.stepId}
                    data-step-id={step.stepId}
                    tabIndex={0}
                    role="button"
                    aria-label={t('how.canvas.selectStep', { name: step.stepName, defaultValue: `选择步骤 ${step.stepName}` })}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        e.stopPropagation();
                        setSelectedStepId(step.stepId);
                        setSelectedLinkId(null);
                      }
                    }}
                    style={{
                      position: 'absolute',
                      left: `${pos.x}px`,
                      top: `${pos.y}px`,
                      width: '280px',
                      zIndex: isSelected ? 30 : isInSelectedPath ? 20 : 10,
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
                      !isSelected && isInSelectedPath && 'ring-2 ring-emerald-500 border-emerald-500 bg-emerald-50/30 shadow-md shadow-emerald-100/60',
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
                    {!effectiveReadOnly && (
                      <div
                        onMouseDown={(e) => handlePortMouseDown(e, step.stepId, pos.x + 280, pos.y + 60)}
                        className="port-handle absolute -right-3 top-[50px] h-6 w-6 rounded-full border-2 border-indigo-600 bg-indigo-600 flex items-center justify-center cursor-crosshair transition-all hover:scale-125 hover:ring-4 hover:ring-indigo-200 shadow-sm"
                        title={t('how.outputPort', '拖拽以建立下一步连线')}
                      >
                        <ArrowRight className="h-3 w-3 text-white" />
                      </div>
                    )}

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
                            {isJudgment ? t('how.canvas.stepTypeJudgment', '判断分支') : isSystem ? t('how.canvas.stepTypeSystem', '系统操作') : t('how.canvas.stepTypeActor', '参与者动作')}
                          </span>
                          {isInSelectedPath && (
                            <span className="rounded-md bg-emerald-100 text-emerald-800 px-1 py-0.5 text-[9px] font-extrabold truncate">
                              {selectedPath?.isMain ? t('how.canvas.mainPath', '主路径') : t('how.canvas.subPath', '分支路径')}
                            </span>
                          )}
                        </div>
                        {!effectiveReadOnly && (
                          <button
                            type="button"
                            onClick={async (e) => {
                              e.stopPropagation();
                              if (window.confirm(t('how.canvas.deleteStepConfirm', '确定要删除步骤 "{{name}}" 吗？', { name: step.stepName }))) {
                                await onDeleteStep(flow.flowId, step.stepId);
                                if (selectedStepId === step.stepId) setSelectedStepId(null);
                              }
                            }}
                            className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-rose-600 rounded-md transition-opacity cursor-pointer"
                            title={t('how.canvas.deleteStep', '删除步骤')}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
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
                            {t('how.canvas.inputBoPrefix', '入: ')}{inputBOs.slice(0, 1).join(', ')}{inputBOs.length > 1 ? ` +${inputBOs.length - 1}` : ''}
                          </span>
                        )}
                        {outputBOs.length > 0 && (
                          <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800 border border-emerald-200/60">
                            <Boxes className="h-2.5 w-2.5 text-emerald-600" />
                            {t('how.canvas.outputBoPrefix', '出: ')}{outputBOs.slice(0, 1).join(', ')}{outputBOs.length > 1 ? ` +${outputBOs.length - 1}` : ''}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}

              {/* Candidate refinement steps */}
              {refinementSteps.map((refStep: any, rIdx: number) => {
                const overlayX = 60 + (steps.length + rIdx) * 320;
                const overlayY = 80;
                const linkedRules = refinementRules.filter(
                  (r: any) =>
                    r.parent_rule_ref === refStep.temp_id ||
                    (Array.isArray(r.source_links) &&
                      r.source_links.some((sl: any) => sl.target_ref === refStep.temp_id || sl.target_kind === 'flow_step'))
                );
                return (
                  <div
                    key={refStep.temp_id || `overlay-step-${rIdx}`}
                    data-testid={`candidate-step-${refStep.temp_id || rIdx}`}
                    style={{
                      position: 'absolute',
                      left: `${overlayX}px`,
                      top: `${overlayY}px`,
                      width: '280px',
                      zIndex: 25,
                    }}
                    className="flow-node-card rounded-2xl border-2 border-dashed border-emerald-500 bg-emerald-50/95 p-4 shadow-lg backdrop-blur-xs transition-all pointer-events-auto"
                  >
                    <div className="flex items-center justify-between gap-2 border-b border-emerald-200 pb-2 mb-2">
                      <div className="flex items-center gap-1.5">
                        <span className="rounded-md bg-emerald-600 px-1.5 py-0.5 text-[9px] font-black text-white uppercase tracking-wider">
                          {t('choicePreview.refinementAddBadge', '+新增候选')}
                        </span>
                        <span className="text-[10px] font-mono font-bold text-emerald-800">
                          {refStep.temp_id || `+S${rIdx + 1}`}
                        </span>
                      </div>
                      <span className="rounded bg-white/80 border border-emerald-200 px-1.5 py-0.5 text-[9px] font-bold text-emerald-700">
                        {refStep.step_type === 'systemAction' ? t('how.canvas.stepTypeSystem', '系统操作') : refStep.step_type === 'judgment' ? t('how.canvas.stepTypeJudgment', '判断分支') : t('how.canvas.stepTypeActor', '参与者动作')}
                      </span>
                    </div>
                    <h5 className="text-xs font-black text-slate-800 line-clamp-1">{refStep.name}</h5>
                    {refStep.description && (
                      <p className="mt-1 text-[11px] text-slate-600 line-clamp-2 leading-relaxed font-medium">
                        {refStep.description}
                      </p>
                    )}
                    {/* Candidate rule badges */}
                    {(linkedRules.length > 0 ? linkedRules : refinementRules).map((r: any, ruleIdx: number) => (
                      <div
                        key={r.temp_id || `rule-badge-${ruleIdx}`}
                        data-testid={`candidate-rule-badge-${r.temp_id || ruleIdx}`}
                        className="mt-2 rounded-md bg-white/90 border border-emerald-300 p-1.5 text-[10px] text-emerald-950 shadow-2xs"
                      >
                        <div className="flex items-center gap-1 font-extrabold text-emerald-800 text-[9px]">
                          <span className="rounded bg-emerald-700 px-1 text-white text-[8px]">{t('how.canvas.aiAssumptionRule', 'AI推测规则')}</span>
                          <span className="truncate">{r.title || r.name || t('how.canvas.detailedRule', '细化规则')}</span>
                        </div>
                        <div className="mt-0.5 text-[9px] text-slate-600 line-clamp-2">{r.statement}</div>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Property inspector */}
          <aside
            ref={drawerRef}
            className={cn(
              'relative shrink-0 border-l border-slate-200 bg-white text-xs text-slate-800 shadow-xs',
              inspectorCollapsed ? 'w-10' : 'w-full md:w-80 p-5 overflow-y-auto flex flex-col gap-4',
            )}
          >
            {/* Collapse toggle — flush edge tab on the panel border */}
            <button
              type="button"
              onClick={() => setInspectorCollapsed((v) => !v)}
              className="group absolute left-0 top-1/2 z-10 flex h-14 w-4 -translate-y-1/2 items-center justify-center rounded-r-md border border-l-0 border-slate-200 bg-white/90 text-slate-400 shadow-xs backdrop-blur-sm hover:bg-indigo-50 hover:text-indigo-600 transition-colors cursor-pointer"
              title={inspectorCollapsed ? t('how.inspectorExpand', '展开属性面板') : t('how.inspectorCollapse', '收起属性面板')}
            >
              {inspectorCollapsed
                ? <ChevronLeft className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5" />
                : <ChevronRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />}
            </button>
            {!inspectorCollapsed && (<>
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
                  {!effectiveReadOnly && (
                    <button
                      type="button"
                      onClick={async () => {
                        if (window.confirm(t('how.canvas.deleteStepConfirm', '确定要删除步骤 "{{name}}" 吗？', { name: selectedStep.stepName }))) {
                          await onDeleteStep(flow.flowId, selectedStep.stepId);
                          setSelectedStepId(null);
                        }
                      }}
                      className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600 transition-colors cursor-pointer"
                      title={t('how.canvas.deleteThisStep', '删除此步骤')}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>

                {!effectiveReadOnly && (
                  <button
                    type="button"
                    disabled={isGeneratingChoices}
                    onClick={async () => {
                      await refineFlow(flow.flowId, selectedStep.stepId);
                      onClose();
                    }}
                    className="w-full inline-flex items-center justify-center gap-1.5 rounded-xl border border-indigo-200 bg-indigo-50/70 hover:bg-indigo-100 text-indigo-700 py-1.5 text-xs font-bold transition-colors cursor-pointer shadow-2xs disabled:opacity-50"
                  >
                    <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
                    {t('how.refineStepPath', '深入分析步骤路径')}
                  </button>
                )}

                {/* Step Name */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-slate-700">{t('how.stepNameLabel', '步骤名称')}</label>
                  <input
                    type="text"
                    disabled={effectiveReadOnly}
                    value={stepNameDraft}
                    onChange={(e) => {
                      setStepNameDraft(e.target.value);
                      scheduleStepTextSave('stepName', e.target.value);
                    }}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-900 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 shadow-2xs disabled:bg-slate-50 disabled:text-slate-500"
                  />
                </div>

                {/* Step Description */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-slate-700">{t('how.stepDescLabel', '步骤描述')}</label>
                  <textarea
                    value={stepDescDraft}
                    disabled={effectiveReadOnly}
                    onChange={(e) => {
                      setStepDescDraft(e.target.value);
                      scheduleStepTextSave('stepDescription', e.target.value);
                    }}
                    rows={2}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-900 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 shadow-2xs disabled:bg-slate-50 disabled:text-slate-500"
                  />
                </div>

                {/* Step Type */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-slate-700">{t('how.stepTypeLabel', '步骤类型')}</label>
                  <select
                    value={selectedStep.stepType || 'actorAction'}
                    disabled={effectiveReadOnly}
                    onChange={(e) => void onUpdateStep(flow.flowId, selectedStep.stepId, { stepType: e.target.value as any })}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-900 outline-none focus:border-indigo-500 shadow-2xs disabled:bg-slate-50 disabled:text-slate-500"
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
                        <label key={act.actorId} className={cn("flex items-center gap-2 px-1 py-1 hover:bg-white rounded cursor-pointer", effectiveReadOnly && "cursor-not-allowed opacity-80")}>
                          <input
                            type="checkbox"
                            checked={isChecked}
                            disabled={effectiveReadOnly}
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
                      <p className="text-[10px] font-bold text-amber-700 mb-1">{t('how.canvas.inputObjects', '输入对象')}</p>
                      {businessObjects.map((bo) => {
                        const isChecked = (selectedStep.inputBusinessObjectIds || []).includes(bo.businessObjectId);
                        return (
                          <label key={bo.businessObjectId} className={cn("flex items-center gap-1.5 py-0.5 text-[11px] cursor-pointer", effectiveReadOnly && "cursor-not-allowed opacity-80")}>
                            <input
                              type="checkbox"
                              checked={isChecked}
                              disabled={effectiveReadOnly}
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
                      <p className="text-[10px] font-bold text-emerald-700 mb-1">{t('how.canvas.outputObjects', '输出对象')}</p>
                      {businessObjects.map((bo) => {
                        const isChecked = (selectedStep.outputBusinessObjectIds || []).includes(bo.businessObjectId);
                        return (
                          <label key={bo.businessObjectId} className={cn("flex items-center gap-1.5 py-0.5 text-[11px] cursor-pointer", effectiveReadOnly && "cursor-not-allowed opacity-80")}>
                            <input
                              type="checkbox"
                              checked={isChecked}
                              disabled={effectiveReadOnly}
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

                {/* Flow Transitions */}
                <div className="space-y-1.5 pt-2 border-t border-slate-100">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-bold text-indigo-700 flex items-center gap-1">
                      <Link2 className="h-3.5 w-3.5" />
                      {t('how.transitionsLabel', '流转分支 (Transitions)')}
                    </label>
                    <span className="text-[10px] text-slate-400">
                      {t('how.canvas.itemsCount', '{{count}} 项', { count: (flow.transitions || []).filter((t) => t.sourceStepId === selectedStep.stepId).length })}
                    </span>
                  </div>
                  <div className="space-y-1 max-h-36 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50/50 p-2">
                    {(flow.transitions || []).filter((t) => t.sourceStepId === selectedStep.stepId).map((trans) => {
                      const targetStep = steps.find((s) => s.stepId === trans.targetStepId);
                      const transId = trans.transitionId || trans.id;
                      return (
                        <div
                          key={transId || `${trans.sourceStepId}-${trans.targetStepId}`}
                          data-testid={`step-transition-item-${transId}`}
                          onClick={() => {
                            if (transId) {
                              setSelectedLinkId(String(transId));
                              setSelectedStepId(null);
                            }
                          }}
                          className="flex items-center justify-between px-2 py-1 bg-white border border-slate-200/80 rounded-lg text-xs hover:border-indigo-300 cursor-pointer transition-colors"
                        >
                          <span className="truncate text-slate-700 font-medium">
                            → {targetStep?.stepName || t('how.canvas.stepNumbered', '步骤 #{{id}}', { id: trans.targetStepId })}
                                  {trans.conditionText ? ` (${trans.conditionText})` : ''}
                            {trans.isDefault ? ` [${t('how.canvas.defaultBranch', '默认分支')}]` : ''}
                          </span>
                          {!effectiveReadOnly && (
                            <button
                              type="button"
                              onClick={() => {
                                void handleDisconnect(trans.sourceStepId, trans.targetStepId, transId);
                              }}
                              className="text-slate-400 hover:text-rose-600 p-0.5"
                              title={t('how.canvas.deleteTransition', '删除流转')}
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          )}
                        </div>
                      );
                    })}
                    {(flow.transitions || []).filter((t) => t.sourceStepId === selectedStep.stepId).length === 0 && (
                      <p className="p-2 text-[11px] text-slate-400 text-center">{t('how.canvas.noOutboundTransitions', '暂无流出分支，可通过画布端口拖拽连线')}</p>
                    )}
                  </div>
                </div>

                <FlowRuleAssociations key={selectedStep.logicalUuid || selectedStep.stepId}
                  targetKind="flow_step" targetLogicalUuid={selectedStep.logicalUuid}
                  rules={domainRules} readOnly={effectiveReadOnly} onOpenRule={openRule} />

                {/* Related Findings for Step */}
                <div className="space-y-1.5 pt-2 border-t border-slate-100">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-bold text-rose-800 flex items-center gap-1">
                      <AlertTriangle className="h-3.5 w-3.5 text-rose-600" />
                      {t('how.canvas.relatedFindings', '关联发现 (Findings)')}
                    </label>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {t('how.canvas.itemsCount', '{{count}} 项', { count: stepFindings.length })}
                    </span>
                  </div>
                  <div className="space-y-1 max-h-36 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50/50 p-2">
                    {stepFindings.map((f) => {
                      const isBlocking = (f.severity as string) === 'error' || (f.severity as string) === 'blocking' || f.blockingScope !== 'none';
                      return (
                        <div
                          key={f.findingId}
                          data-testid={`step-finding-${f.findingId}`}
                          className={cn(
                            "rounded-lg bg-white border p-2 text-xs shadow-2xs space-y-1",
                            isBlocking ? 'border-rose-200' : 'border-amber-200'
                          )}
                        >
                          <div className="flex items-center justify-between gap-1 font-semibold text-slate-800">
                            <span className="truncate">{f.title}</span>
                            <span className={cn(
                              "shrink-0 text-[9px] px-1 py-0.5 rounded border font-bold",
                              isBlocking ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-amber-50 text-amber-700 border-amber-200'
                            )}>
                              {isBlocking ? t('how.canvas.blocking', '阻断') : t('how.canvas.warning', '告警')}
                            </span>
                          </div>
                          {f.description && (
                            <p className="text-[10px] text-slate-500 line-clamp-2 leading-relaxed">
                              {f.description}
                            </p>
                          )}
                        </div>
                      );
                    })}
                    {stepFindings.length === 0 && (
                      <p className="p-2 text-[11px] text-slate-400 text-center">{t('how.canvas.noRelatedFindings', '暂无关联发现')}</p>
                    )}
                  </div>
                </div>

                {/* Related Choices for Step */}
                <div className="space-y-1.5 pt-2 border-t border-slate-100">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-bold text-indigo-800 flex items-center gap-1">
                      <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
                      {t('how.canvas.relatedChoices', '关联选项 (Choices)')}
                    </label>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {t('how.canvas.itemsCount', '{{count}} 项', { count: stepChoices.length })}
                    </span>
                  </div>
                  <div className="space-y-1 max-h-36 overflow-y-auto rounded-xl border border-indigo-100 bg-indigo-50/30 p-2">
                    {stepChoices.map((choice: any, idx: number) => (
                      <div key={idx} data-testid={`step-choice-${idx}`} className="rounded-lg bg-white border border-indigo-200 p-2 text-xs space-y-0.5">
                        <p className="font-semibold text-indigo-900">{choice.title || choice.description || t('how.canvas.choiceNumbered', '选项 #{{id}}', { id: idx + 1 })}</p>
                        {choice.description && choice.title && (
                          <p className="text-[10px] text-slate-500 line-clamp-2">{choice.description}</p>
                        )}
                      </div>
                    ))}
                    {stepChoices.length === 0 && (
                      <p className="p-2 text-[11px] text-slate-400 text-center">{t('how.canvas.noRelatedChoices', '暂无关联选项')}</p>
                    )}
                  </div>
                </div>
              </div>
            ) : selectedTransition ? (
              /* Transition Edge is Selected */
              (() => {
                const fromNode = steps.find((s) => s.stepId === selectedTransition.sourceStepId);
                const toNode = steps.find((s) => s.stepId === selectedTransition.targetStepId);

                return (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                      <h3 className="font-extrabold text-sm text-slate-900 flex items-center gap-2">
                        <Link2 className="h-4 w-4 text-rose-500" />
                        {t('how.linkInspector', '分支连线详情')}
                      </h3>
                      <span className={cn(
                        'rounded-md px-2 py-0.5 text-[10px] font-bold',
                        transitionIsDefault ? 'bg-indigo-50 text-indigo-700 border border-indigo-200' : 'bg-slate-100 text-slate-600'
                      )}>
                        {transitionIsDefault ? t('how.canvas.defaultBranch', '默认分支') : t('how.canvas.normalBranch', '普通分支')}
                      </span>
                    </div>

                    {/* Nodes Connected */}
                    <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 space-y-3">
                      <div>
                        <span className="text-[10px] font-bold text-slate-500">{t('how.canvas.fromStep', '起始步骤')}</span>
                        <p className="font-bold text-slate-900 truncate mt-0.5">{fromNode?.stepName || t('how.canvas.stepNumbered', '步骤 #{{id}}', { id: selectedTransition.sourceStepId })}</p>
                      </div>
                      <div className="flex justify-center text-slate-400">
                        <ArrowRight className="h-4 w-4 rotate-90" />
                      </div>
                      <div>
                        <span className="text-[10px] font-bold text-slate-500">{t('how.canvas.toStep', '目标下一步')}</span>
                        <p className="font-bold text-slate-900 truncate mt-0.5">{toNode?.stepName || t('how.canvas.stepNumbered', '步骤 #{{id}}', { id: selectedTransition.targetStepId })}</p>
                      </div>
                    </div>

                    {/* Form Controls */}
                    <div className="space-y-3">
                      <div>
                        <label className="text-[11px] font-bold text-slate-700">{t('how.canvas.transitionLabelField', '分支标签 (Label)')}</label>
                        <input
                          type="text"
                          data-testid="transition-label-input"
                          disabled={effectiveReadOnly}
                          value={transitionLabel}
                          onChange={(e) => setTransitionLabel(e.target.value)}
                          placeholder={t('how.canvas.transitionLabelPlaceholder', '例如: 审核通过 / 金额超限')}
                          className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-800 shadow-2xs focus:border-indigo-500 focus:outline-none disabled:bg-slate-50 disabled:text-slate-500"
                        />
                      </div>

                      <div>
                        <label className="text-[11px] font-bold text-slate-700">{t('how.canvas.transitionConditionField', '流转条件 (Condition Text)')}</label>
                        <textarea
                          rows={2}
                          data-testid="transition-condition-input"
                          disabled={effectiveReadOnly}
                          value={transitionCondition}
                          onChange={(e) => setTransitionCondition(e.target.value)}
                          placeholder={t('how.canvas.transitionConditionPlaceholder', '例如: amount >= 10000')}
                          className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-800 shadow-2xs focus:border-indigo-500 focus:outline-none disabled:bg-slate-50 disabled:text-slate-500"
                        />
                      </div>

                      <div>
                        <label className="text-[11px] font-bold text-slate-700">{t('how.canvas.positionLabel', '同源流转优先级 (Position)')}</label>
                        <input
                          type="number"
                          min="0"
                          step="1"
                          data-testid="transition-position-input"
                          disabled={effectiveReadOnly}
                          value={transitionPosition}
                          onChange={(e) => setTransitionPosition(e.target.value === '' ? '' : Math.max(0, parseInt(e.target.value, 10) || 0))}
                          placeholder={t('how.canvas.positionPlaceholder', '例如: 0, 1, 2...')}
                          className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-800 shadow-2xs focus:border-indigo-500 focus:outline-none disabled:bg-slate-50 disabled:text-slate-500"
                        />
                        <p className="text-[10px] text-slate-400 mt-0.5">{t('how.canvas.positionHelp', '同一源步骤发出的多分支中判定优先级（数字越小越优先判定）')}</p>
                      </div>

                      <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50/50 p-2.5">
                        <div>
                          <span className="text-xs font-bold text-slate-800">{t('how.canvas.setDefaultBranch', '设为默认分支')}</span>
                          <p className="text-[10px] text-slate-500">{t('how.canvas.defaultBranchHelp', '无匹配条件时默认执行的路径')}</p>
                        </div>
                        <input
                          type="checkbox"
                          data-testid="transition-default-checkbox"
                          disabled={effectiveReadOnly}
                          checked={transitionIsDefault}
                          onChange={(e) => setTransitionIsDefault(e.target.checked)}
                          className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer disabled:cursor-not-allowed"
                        />
                      </div>

                      <div>
                        <label className="text-[11px] font-bold text-slate-700">{t('how.canvas.semanticTagsField', '语义标签 (逗号分隔)')}</label>
                        <input
                          type="text"
                          data-testid="transition-tags-input"
                          disabled={effectiveReadOnly}
                          value={transitionTags.join(', ')}
                          onChange={(e) => setTransitionTags(e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
                          placeholder="happy_path, exception, timeout"
                          className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-800 shadow-2xs focus:border-indigo-500 focus:outline-none disabled:bg-slate-50 disabled:text-slate-500"
                        />
                      </div>

                      <div>
                        <label className="text-[11px] font-bold text-slate-700">{t('how.canvas.statusField', '确认状态')}</label>
                        <select
                          value={transitionStatus}
                          data-testid="transition-status-select"
                          disabled={effectiveReadOnly}
                          onChange={(e) => setTransitionStatus(e.target.value as NodeStatus)}
                          className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-800 shadow-2xs focus:border-indigo-500 focus:outline-none disabled:bg-slate-50 disabled:text-slate-500"
                        >
                          <option value="confirmed">{t('how.canvas.statusConfirmed', '已确认 (Confirmed)')}</option>
                          <option value="needs_confirmation">{t('how.canvas.statusNeedsConfirmation', '待确认 (Needs Confirmation)')}</option>
                          <option value="ai_assumption">{t('how.canvas.statusAiAssumption', 'AI推测 (AI Assumption)')}</option>
                        </select>
                      </div>

                      {/* Linked Rules */}
                      <div>
                        <p className="mb-2 text-[11px] text-slate-600">{t('how.ruleAssociations.flow_transitionHint')}</p>
                        <label className="text-[11px] font-bold text-slate-700 flex items-center justify-between">
                          <span className="flex items-center gap-1">
                            <Workflow className="h-3.5 w-3.5 text-indigo-600" />
                            {t('how.canvas.linkedRulesField', '关联业务规则 (Linked Rules)')}
                          </span>
                          <span className="text-[10px] text-slate-400">
                            {t('how.canvas.selectedCount', '{{count}} 已选', { count: transitionRuleIds.length })}
                          </span>
                        </label>
                        <div className="mt-1 max-h-36 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50/50 p-2 space-y-1">
                          {domainRules.length === 0 ? (
                            <p className="text-[10px] text-slate-400 py-1 text-center">{t('how.canvas.noAvailableRules', '暂无可用业务规则')}</p>
                          ) : (
                            domainRules.map((rule) => {
                              const isChecked = transitionRuleIds.includes(rule.id);
                              return (
                                <div
                                  key={rule.id}
                                  className={cn(
                                    "flex items-start gap-2 p-1.5 rounded-lg border text-xs cursor-pointer transition-colors",
                                    isChecked ? "bg-indigo-50/70 border-indigo-200 text-indigo-900" : "bg-white border-slate-200/80 text-slate-700 hover:bg-slate-50",
                                    effectiveReadOnly && "cursor-not-allowed opacity-80"
                                  )}
                                >
                                  <input
                                    type="checkbox"
                                    data-testid={`rule-checkbox-${rule.id}`}
                                    aria-label={rule.title}
                                    checked={isChecked}
                                    disabled={effectiveReadOnly}
                                    onChange={(e) => {
                                      if (e.target.checked) {
                                        setTransitionRuleIds((prev) => [...prev, rule.id]);
                                      } else {
                                        setTransitionRuleIds((prev) => prev.filter((id) => id !== rule.id));
                                      }
                                    }}
                                    className="mt-0.5 h-3.5 w-3.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                                  />
                                  <div className="min-w-0 flex-1">
                                    <button type="button" onClick={() => openRule(rule)}
                                      title={t('how.ruleAssociations.openRule')}
                                      className="text-left text-[11px] font-bold text-indigo-700 hover:underline">
                                      #{rule.id} {rule.title}
                                    </button>
                                    {rule.statement && (
                                      <p className="text-[10px] text-slate-500 line-clamp-1 mt-0.5">{rule.statement}</p>
                                    )}
                                  </div>
                                </div>
                              );
                            })
                          )}
                        </div>
                      </div>

                      {/* Transition Findings */}
                      <div className="space-y-1.5 pt-2 border-t border-slate-100">
                        <div className="flex items-center justify-between">
                          <label className="text-[11px] font-bold text-rose-800 flex items-center gap-1">
                            <AlertTriangle className="h-3.5 w-3.5 text-rose-600" />
                            {t('how.canvas.relatedFindings', '关联发现 (Findings)')}
                          </label>
                          <span className="text-[10px] text-slate-400 font-mono">
                            {t('how.canvas.itemsCount', '{{count}} 项', { count: transitionFindings.length })}
                          </span>
                        </div>
                        <div className="space-y-1 max-h-36 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50/50 p-2">
                          {transitionFindings.map((f) => {
                            const isBlocking = (f.severity as string) === 'error' || (f.severity as string) === 'blocking' || f.blockingScope !== 'none';
                            return (
                              <div
                                key={f.findingId}
                                data-testid={`transition-finding-${f.findingId}`}
                                className={cn(
                                  "rounded-lg bg-white border p-2 text-xs shadow-2xs space-y-1",
                                  isBlocking ? 'border-rose-200' : 'border-amber-200'
                                )}
                              >
                                <div className="flex items-center justify-between gap-1 font-semibold text-slate-800">
                                  <span className="truncate">{f.title}</span>
                                  <span className={cn(
                                    "shrink-0 text-[9px] px-1 py-0.5 rounded border font-bold",
                                    isBlocking ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-amber-50 text-amber-700 border-amber-200'
                                  )}>
                                    {isBlocking ? t('how.canvas.blocking', '阻断') : t('how.canvas.warning', '告警')}
                                  </span>
                                </div>
                                {f.description && (
                                  <p className="text-[10px] text-slate-500 line-clamp-2 leading-relaxed">
                                    {f.description}
                                  </p>
                                )}
                              </div>
                            );
                          })}
                          {transitionFindings.length === 0 && (
                            <p className="p-2 text-[11px] text-slate-400 text-center">{t('how.canvas.noRelatedFindings', '暂无关联发现')}</p>
                          )}
                        </div>
                      </div>

                      {!effectiveReadOnly && (
                        <button
                          type="button"
                          data-testid="save-transition-button"
                          onClick={handleSaveTransition}
                          disabled={isSavingTransition}
                          className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-700 transition-colors shadow-2xs cursor-pointer disabled:opacity-50"
                        >
                          <Check className="h-3.5 w-3.5" />
                          {isSavingTransition ? t('how.canvas.saving', '保存中...') : t('how.canvas.saveTransition', '保存分支设置')}
                        </button>
                      )}
                    </div>

                    {!effectiveReadOnly && (
                      <button
                        type="button"
                        data-testid="delete-transition-button"
                        onClick={handleDeleteSelectedTransition}
                        className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-rose-50 border border-rose-200 px-4 py-2.5 text-xs font-bold text-rose-700 hover:bg-rose-100 transition-colors cursor-pointer"
                      >
                        <Unlink className="h-4 w-4" />
                        {t('how.canvas.disconnectLink', '断开此分支连线')}
                      </button>
                    )}
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
                  <p className="font-bold text-slate-800">{t('how.canvas.canvasTipsTitle', '💡 画布交互提示：')}</p>
                  <ul className="space-y-1.5 list-disc pl-4">
                    <li><strong className="text-slate-900">{t('how.canvas.tipDragLink', '拖拽连线')}</strong>：{t('how.canvas.tipDragLinkDesc', '按住步骤卡片右侧的箭头圆点拖动到其他步骤。')}</li>
                    <li><strong className="text-slate-900">{t('how.canvas.tipDisconnect', '断开连线')}</strong>：{t('how.canvas.tipDisconnectDesc', '点击连线即可高亮选中并一键断开。')}</li>
                    <li><strong className="text-slate-900">{t('how.canvas.tipFreeLayout', '自由布局')}</strong>：{t('how.canvas.tipFreeLayoutDesc', '按住步骤卡片随意拖拽位置。')}</li>
                    <li><strong className="text-slate-900">{t('how.canvas.tipZoomPan', '缩放平移')}</strong>：{t('how.canvas.tipZoomPanDesc', '滚轮缩放画布，按住空白处拖拽平移。')}</li>
                  </ul>
                </div>
              </div>
            )}
            </>)}
          </aside>
        </div>

      {/* Modal resize handles */}
        {!isMaximized && (
          <>
            {/* Right edge */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 'e')}
              className="absolute right-0 top-16 bottom-0 w-2 cursor-ew-resize hover:bg-indigo-500/20 z-40 transition-colors"
              title={t('how.canvas.resizeWidth', '拖动调整窗口宽度')}
            />
            {/* Left edge */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 'w')}
              className="absolute left-0 top-16 bottom-0 w-2 cursor-ew-resize hover:bg-indigo-500/20 z-40 transition-colors"
              title={t('how.canvas.resizeWidth', '拖动调整窗口宽度')}
            />
            {/* Bottom edge */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 's')}
              className="absolute left-0 right-0 bottom-0 h-2 cursor-ns-resize hover:bg-indigo-500/20 z-40 transition-colors"
              title={t('how.canvas.resizeHeight', '拖动调整窗口高度')}
            />
            {/* Bottom-right diagonal corner */}
            <div
              onMouseDown={(e) => handleResizeStart(e, 'se')}
              className="absolute right-1.5 bottom-1.5 w-5 h-5 cursor-nwse-resize z-50 flex items-center justify-center group/resize rounded-br-2xl"
              title={t('how.canvas.resizeDimensions', '拖动调整窗口尺寸')}
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
              title={t('how.canvas.resizeDimensions', '拖动调整窗口尺寸')}
            />
          </>
        )}

      {/* Quick step editor */}
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
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">{t('how.canvas.addStepName', '步骤名称 *')}</label>
                  <input
                    type="text"
                    value={newStepName}
                    onChange={(e) => setNewStepName(e.target.value)}
                    placeholder={t('how.canvas.addStepNamePlaceholder', '例如：输入手机号并获取验证码')}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900 outline-none focus:border-indigo-500 shadow-2xs"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">{t('how.canvas.addStepDesc', '步骤描述')}</label>
                  <textarea
                    value={newStepDesc}
                    onChange={(e) => setNewStepDesc(e.target.value)}
                    rows={2}
                    placeholder={t('how.canvas.addStepDescPlaceholder', '补充说明步骤的前置条件或操作细节')}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900 outline-none focus:border-indigo-500 shadow-2xs"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">{t('how.canvas.addStepType', '步骤类型')}</label>
                  <select
                    value={newStepType}
                    onChange={(e) => setNewStepType(e.target.value as any)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900 outline-none shadow-2xs"
                  >
                    <option value="actorAction">{t('how.canvas.actorActionOption', '参与者动作 (actorAction)')}</option>
                    <option value="systemAction">{t('how.canvas.systemActionOption', '系统操作 (systemAction)')}</option>
                    <option value="judgment">{t('how.canvas.judgmentOption', '判断分支 (judgment)')}</option>
                  </select>
                </div>

                {/* Actor Selector (Required when actorAction) */}
                {newStepType === 'actorAction' && (
                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 mb-1">
                      {t('how.canvas.actorRoleRequired', '执行参与者角色')} <span className="text-rose-500">*</span>
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
                        {t('how.canvas.noActorTip', '当前暂未定义角色，请先在 What 阶段定义参与者角色，或在此将步骤类型切换为“系统操作”。')}
                      </p>
                    )}
                  </div>
                )}

                {/* Connect from Step */}
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">{t('how.canvas.connectFromStep', '从哪个步骤连接至此新步骤？')}</label>
                  <select
                    value={newStepConnectFromId || ''}
                    onChange={(e) => setNewStepConnectFromId(e.target.value ? parseInt(e.target.value, 10) : null)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900 outline-none shadow-2xs"
                  >
                    <option value="">{t('how.canvas.noAutoConnect', '(不自动从已有步骤连线)')}</option>
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
                  {t('how.canvas.cancel', '取消')}
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
                  {t('how.canvas.confirmAdd', '确定添加')}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
