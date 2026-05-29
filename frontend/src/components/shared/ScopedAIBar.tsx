import React, { useEffect, useMemo, useState, useRef } from 'react';
import { ProjectionKind } from '@/core/schema';
import { selectCurrentPage, selectSelectedObject, useWorkspaceStore } from '@/store/useWorkspaceStore';
import { Sparkles, Minus, Zap } from 'lucide-react';

type AIScope =
  | { kind: 'workspace'; label: string }
  | { kind: 'projection'; projection: ProjectionKind; label: string }
  | { kind: 'node'; nodeId: string; label: string };

type AIIntent = 'diagnose' | 'rewrite' | 'explain_impact';

const INTENT_LABELS: Record<AIIntent, string> = {
  diagnose: '智能规范诊断',
  rewrite: 'AI 智能自动建模',
  explain_impact: '链路联动分析',
};

const pageToProjection = (page: string): ProjectionKind => {
  if (page === '/flow') return 'system';
  if (page === '/scope') return 'data';
  if (page === '/preview') return 'ui';
  if (page === '/' || page === '/what') return 'goal';
  return 'goal';
};

const pageToStageLabel = (page: string): string => {
  if (page === '/flow') return 'How 运作流建模';
  if (page === '/scope') return 'Scope 范围决策';
  if (page === '/preview') return 'Preview 方案预览';
  return 'What 角色能力建模';
};

const getObjectId = (obj: any): string => {
  const id =
    obj?.id ??
    obj?.actorId ??
    obj?.featureId ??
    obj?.scenarioId ??
    obj?.criterionId ??
    obj?.businessObjectId ??
    obj?.businessObjectAttributeId ??
    obj?.flowId ??
    obj?.stepId ??
    obj?.scopeId ??
    obj?.perceptionSlotId;

  return id !== undefined && id !== null ? String(id) : '';
};

const getObjectTitle = (obj: any): string => {
  const title =
    obj?.title ??
    obj?.name ??
    obj?.actorName ??
    obj?.featureName ??
    obj?.scenarioName ??
    obj?.criterionContent ??
    obj?.businessObjectName ??
    obj?.businessObjectAttributeName ??
    obj?.flowName ??
    obj?.stepName ??
    obj?.scopeStatus ??
    obj?.perceptionKind ??
    getObjectId(obj);

  return title !== undefined && title !== null && String(title).trim()
    ? String(title)
    : '未命名对象';
};

const getObjectKind = (obj: any): string | undefined => {
  return obj?.kind || (
    obj?.scenarioId !== undefined ? 'scenario' :
    obj?.criterionId !== undefined ? 'acceptance_criterion' :
    obj?.actorId !== undefined ? 'actor' :
    obj?.featureId !== undefined ? 'feature' :
    obj?.businessObjectAttributeId !== undefined ? 'business_object_attribute' :
    obj?.businessObjectId !== undefined ? 'business_object' :
    obj?.stepId !== undefined ? 'flow_step' :
    obj?.flowId !== undefined ? 'flow' :
    obj?.scopeId !== undefined ? 'scope' :
    obj?.perceptionSlotId !== undefined ? 'perception_slot' :
    undefined
  );
};

const getObjectScopePrefix = (kind?: string): string => {
  if (kind === 'feature') return '能力点';
  if (kind === 'flow') return '业务流程';
  if (kind === 'flow_step') return '流程步骤';
  if (kind === 'business_object') return '数据对象';
  if (kind === 'business_object_attribute') return '数据字段';
  if (kind === 'actor') return '业务角色';
  if (kind === 'scenario') return '业务场景';
  if (kind === 'acceptance_criterion') return '验收标准';
  if (kind === 'scope') return '范围决策';
  if (kind === 'perception_slot') return '感知槽';
  return '选中项';
};

export function ScopedAIBar() {
  const {
    ir,
    isLoading,
    lastActionMessage,
    runDiagnosis,
    executeNextSuggestion,
    nextSuggestions,
    rewrite,
    explainImpact,
  } = useWorkspaceStore();
  const selectedObject: any = useWorkspaceStore(selectSelectedObject);
  const currentPage = useWorkspaceStore(selectCurrentPage);

  // Fold state
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Drag position offsets (user preferred position)
  const [preferredPosition, setPreferredPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const dragStartMouse = useRef({ x: 0, y: 0 });
  const isDragAction = useRef(false);

  // Track browser window dimensions for dynamic scaling
  const [windowSize, setWindowSize] = useState({
    width: typeof window !== 'undefined' ? window.innerWidth : 1000,
    height: typeof window !== 'undefined' ? window.innerHeight : 800,
  });

  // Clamp preferred position and synchronize on resize
  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      setWindowSize({ width, height });

      // Keep preferred position within maximum boundaries (collapsed bounds)
      const W = 48;
      const H = 48;
      const minX = 40 + W - width;
      const maxX = 8;
      const minY = 40 + H - height;
      const maxY = 8;

      setPreferredPosition(prev => ({
        x: Math.max(minX, Math.min(maxX, prev.x)),
        y: Math.max(minY, Math.min(maxY, prev.y)),
      }));
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Compute actual clamped position for rendering
  const renderedPosition = useMemo(() => {
    if (isCollapsed) return preferredPosition;

    // In expanded state, clamp preferred position to viewport boundaries of the panel
    const W = Math.min(860, windowSize.width - 32);
    const H = 280;

    const minX = 40 + W - windowSize.width;
    const maxX = 8;
    const minY = 40 + H - windowSize.height;
    const maxY = 8;

    return {
      x: Math.max(minX, Math.min(maxX, preferredPosition.x)),
      y: Math.max(minY, Math.min(maxY, preferredPosition.y)),
    };
  }, [preferredPosition, isCollapsed, windowSize]);

  const handleMouseDown = (e: React.MouseEvent) => {
    // Only drag on left click
    if (e.button !== 0) return;
    
    const target = e.target as HTMLElement;
    // If not collapsed, prevent dragging when clicking buttons, select, or input inside the panel
    if (!isCollapsed) {
      if (target.closest('button') || target.closest('select') || target.closest('input')) return;
    }

    setIsDragging(true);
    dragStartMouse.current = { x: e.clientX, y: e.clientY };
    isDragAction.current = false;
    
    setDragStart({
      x: e.clientX - renderedPosition.x,
      y: e.clientY - renderedPosition.y,
    });
  };

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - dragStartMouse.current.x;
      const dy = e.clientY - dragStartMouse.current.y;
      if (Math.abs(dx) > 4 || Math.abs(dy) > 4) {
        isDragAction.current = true;
      }
      
      let newX = e.clientX - dragStart.x;
      let newY = e.clientY - dragStart.y;

      const W = isCollapsed ? 48 : Math.min(860, windowSize.width - 32);
      const H = isCollapsed ? 48 : 280;

      const minX = 40 + W - windowSize.width;
      const maxX = 8;
      const minY = 40 + H - windowSize.height;
      const maxY = 8;

      setPreferredPosition({
        x: Math.max(minX, Math.min(maxX, newX)),
        y: Math.max(minY, Math.min(maxY, newY)),
      });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, dragStart, isCollapsed, windowSize]);

  const scopes = useMemo(() => {
    const nextScopes: AIScope[] = [
      { kind: 'projection', projection: pageToProjection(currentPage), label: `当前阶段: ${pageToStageLabel(currentPage)}` },
      { kind: 'workspace', label: '整个系统空间' },
    ];

    if (!selectedObject) return nextScopes;

    const nodeId = getObjectId(selectedObject);
    const title = getObjectTitle(selectedObject);
    const kind = getObjectKind(selectedObject);
    nextScopes.unshift({
      kind: 'node',
      nodeId,
      label: `${getObjectScopePrefix(kind)}: ${title}`,
    });

    return nextScopes;
  }, [currentPage, selectedObject]);

  const [selectedScopeIndex, setSelectedScopeIndex] = useState(0);
  const [intent, setIntent] = useState<AIIntent>('diagnose');
  const [instruction, setInstruction] = useState('');

  useEffect(() => {
    setSelectedScopeIndex(0);
    setIntent('diagnose');
  }, [selectedObject, currentPage]);

  const currentStage = useMemo(() => {
    if (currentPage === '/flow') return 'how';
    if (currentPage === '/scope') return 'scope';
    if (currentPage === '/preview') return 'preview';
    return 'what';
  }, [currentPage]);

  const currentSuggestion = (nextSuggestions || {})[currentStage];

  const showSuggestionCard = useMemo(() => {
    return intent === 'diagnose' && currentSuggestion && currentSuggestion.status !== 'failed';
  }, [intent, currentSuggestion]);

  const scope = scopes[selectedScopeIndex] || scopes[0];

  const placeholder =
    intent === 'rewrite'
      ? scope.kind === 'workspace'
        ? '输入 AI 建模指令，例如：推演创建名称和描述、补全功能叶子节点'
        : `输入针对【${scope.label}】的自动建模与补全指令`
      : '当前诊断与影响分析动作无需额外指令，点击“执行”即可启动';

  const handleSubmit = async () => {
    if (intent === 'rewrite' && !instruction.trim()) return;

    if (intent === 'diagnose') {
      await runDiagnosis(scope.kind === 'workspace' ? { trigger: 'manual' } : scope);
    } else if (intent === 'rewrite') {
      await rewrite(scope, instruction);
    } else if (intent === 'explain_impact') {
      await explainImpact(scope, undefined, (scope as any).nodeId);
    }

    setInstruction('');
  };

  if (isCollapsed) {
    return (
      <div 
        className="fixed bottom-6 right-6 z-50"
        style={{
          transform: `translate(${renderedPosition.x}px, ${renderedPosition.y}px)`,
          transition: isDragging ? 'none' : undefined,
        }}
      >
        <button
          onClick={(e) => {
            if (isDragAction.current) {
              e.preventDefault();
              e.stopPropagation();
              return;
            }
            setIsCollapsed(false);
          }}
          onMouseDown={handleMouseDown}
          className={`w-12 h-12 rounded-full bg-gradient-to-tr from-indigo-600 to-violet-500 text-white flex items-center justify-center shadow-xl hover:shadow-indigo-200 hover:scale-105 border-2 border-white animate-in fade-in zoom-in-50 duration-200 ${
            isDragging ? 'cursor-grabbing' : 'cursor-grab transition-all active:scale-95'
          }`}
          style={{
            transition: isDragging ? 'none' : undefined,
          }}
          title="按住左键拖拽移动，轻点展开 AI 助手"
        >
          <Sparkles className="w-5 h-5 animate-pulse" />
        </button>
      </div>
    );
  }

  return (
    <div 
      className="fixed bottom-6 right-6 z-40 w-[min(860px,calc(100vw-2rem))] select-none"
      style={{
        transform: `translate(${renderedPosition.x}px, ${renderedPosition.y}px)`,
        transition: isDragging ? 'none' : undefined,
      }}
    >
      <div className="bg-white/95 backdrop-blur-md rounded-3xl shadow-2xl border border-slate-200/80 overflow-hidden flex flex-col">
        {/* Premium Draggable Handle Bar */}
        <div 
          onMouseDown={handleMouseDown}
          className={`px-4 py-2 bg-slate-50/80 border-b border-slate-100 flex items-center justify-between ${
            isDragging ? 'cursor-grabbing' : 'cursor-grab'
          }`}
          title="按住左键拖拽移动"
        >
          <div className="flex items-center gap-2">
            <span className="p-1 bg-indigo-50 rounded-lg text-indigo-500">
              <Sparkles className="w-3.5 h-3.5 animate-pulse" />
            </span>
            <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-1.5 font-mono">
              AI 智能建模助手
            </span>
          </div>
          <button 
            type="button"
            onClick={() => setIsCollapsed(true)}
            className="p-1 hover:bg-slate-200 rounded-md text-slate-400 hover:text-slate-600 transition-colors"
            title="折叠助手"
          >
            <Minus className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Floating Panel Content */}
        <div className="p-4 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-slate-400 font-bold uppercase tracking-wider pl-1">诊断范围:</span>
              <select
                value={selectedScopeIndex}
                onChange={(e) => setSelectedScopeIndex(Number(e.target.value))}
                className="bg-slate-50 hover:bg-slate-100 border border-slate-200 text-slate-700 text-xs font-extrabold px-3 py-2 rounded-xl outline-none cursor-pointer focus:ring-2 focus:ring-indigo-500 shadow-sm"
              >
                {scopes.map((item, index) => (
                  <option key={`${item.kind}-${index}`} value={index}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="h-4 w-px bg-slate-200 mx-1"></div>

              {(['diagnose', 'rewrite', 'explain_impact'] as AIIntent[]).map((item) => {
                return (
                  <button
                    key={item}
                    type="button"
                    onClick={() => {
                      setIntent(item);
                    }}
                    className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all shadow-sm ${
                      intent === item
                        ? 'bg-indigo-600 text-white border border-indigo-500'
                        : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50 hover:border-slate-300'
                    }`}
                  >
                    {INTENT_LABELS[item]}
                  </button>
                );
              })}
          </div>

          {showSuggestionCard && (
            <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
              {currentSuggestion.status === 'running' ? (
                <div className="bg-slate-50 border border-slate-200/80 rounded-2xl p-3.5 flex items-center gap-3 shadow-inner">
                  <span className="flex h-2.5 w-2.5 relative shrink-0">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-500"></span>
                  </span>
                  <div className="text-xs flex-1">
                    <p className="font-bold text-slate-700">{currentSuggestion.title || 'AI 正在深度诊断中'}</p>
                    <p className="text-slate-400 mt-0.5 text-[10px]">正在感知系统在当前建模阶段的设计缝隙，请稍候...</p>
                  </div>
                </div>
              ) : (
                <div className="bg-amber-50/50 border border-amber-200/80 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm">
                  <div className="flex items-start gap-3">
                    <span className="p-2 bg-amber-100/80 text-amber-600 rounded-xl mt-0.5 shrink-0">
                      <Sparkles className="w-4 h-4 animate-pulse" />
                    </span>
                    <div className="text-xs flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-extrabold text-amber-800 uppercase tracking-widest text-[10px] bg-amber-100/60 px-2 py-0.5 rounded font-mono">AI 感知槽建议</span>
                        <span className="font-black text-slate-700">{currentSuggestion.title}</span>
                      </div>
                      <p className="text-slate-600 mt-1.5 leading-relaxed font-medium text-xs">{currentSuggestion.description}</p>
                    </div>
                  </div>
                  {currentSuggestion.code?.endsWith('_SLOT') && (
                    <button
                      type="button"
                      onClick={() => void executeNextSuggestion(currentStage)}
                      className="self-end sm:self-center px-4 py-2 bg-gradient-to-r from-amber-500 to-orange-500 text-white font-extrabold text-xs rounded-xl shadow hover:from-amber-600 hover:to-orange-600 hover:scale-102 hover:shadow-amber-100 transition-all shrink-0 active:scale-98 flex items-center gap-1.5 cursor-pointer"
                    >
                      <Zap className="w-3.5 h-3.5" />
                      <span>处理此感知槽</span>
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="flex items-center gap-2">
            <input
              type="text"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              disabled={intent !== 'rewrite'}
              placeholder={placeholder}
              className="flex-1 bg-slate-50 text-slate-800 border border-slate-200/80 text-sm rounded-xl px-4 py-2.5 placeholder:text-slate-400 outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60 shadow-inner"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  void handleSubmit();
                }
              }}
            />
            <button
              type="button"
              onClick={() => void handleSubmit()}
              disabled={isLoading || (intent === 'rewrite' && !instruction.trim())}
              className="px-5 py-2.5 bg-indigo-600 border border-indigo-500 text-white font-extrabold rounded-xl text-sm hover:bg-indigo-500 transition-colors shadow-sm disabled:opacity-60 shrink-0"
            >
              {isLoading ? '正在建模...' : '执行'}
            </button>
          </div>

          <div className="text-xs text-slate-500 bg-slate-50 border border-slate-100 p-2.5 rounded-xl leading-normal font-medium flex items-center gap-1.5 shadow-sm min-h-[36px]">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 shrink-0 animate-pulse"></span>
            <span>
              {lastActionMessage || `当前将对 【${scope.label}】 执行 【${INTENT_LABELS[intent]}】 操作。`}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
