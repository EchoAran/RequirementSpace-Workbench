/**
 * ScopedAIBar — floating AI assistant with explain (Q&A) and edit modes.
 *
 * Explain mode: user selects scope, asks natural-language questions.
 * Edit mode: user selects a node object, describes changes via chat,
 *   generates an edit draft with diff preview, confirms or discards.
 */

import React, { useEffect, useMemo, useState, useRef, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { ProjectionKind } from '@/core/schema';
import { selectSelectedObject, useWorkspaceStore } from '@/store/useWorkspaceStore';
import {
  Sparkles, Minus, Send, Loader2, Bot, User, RotateCcw, Check, X, FileText,
} from 'lucide-react';
import { workspaceApi } from '@/lib/api';
import { cn } from '@/lib/utils';

type AIScope =
  | { kind: 'workspace'; label: string }
  | { kind: 'projection'; projection: ProjectionKind; label: string }
  | { kind: 'node'; nodeId: string; label: string };

type AIMode = 'explain' | 'edit';

type EditStep = 'idle' | 'creating_session' | 'chat' | 'ready' | 'generating' | 'preview' | 'confirming' | 'done';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

const pageToProjection = (page: string): ProjectionKind => {
  if (page === '/flow') return 'system';
  if (page === '/scope') return 'data';
  if (page === '/preview') return 'ui';
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
    obj?.id ?? obj?.actorId ?? obj?.featureId ?? obj?.scenarioId ??
    obj?.criterionId ?? obj?.businessObjectId ?? obj?.businessObjectAttributeId ??
    obj?.flowId ?? obj?.stepId ?? obj?.scopeId ?? obj?.perceptionSlotId;
  return id !== undefined && id !== null ? String(id) : '';
};

const getObjectTitle = (obj: any): string => {
  const title = obj?.title ?? obj?.name ?? obj?.actorName ?? obj?.featureName ??
    obj?.scenarioName ?? obj?.criterionContent ?? obj?.businessObjectName ??
    obj?.businessObjectAttributeName ?? obj?.flowName ?? obj?.stepName ?? getObjectId(obj);
  return title !== undefined && title !== null && String(title).trim() ? String(title) : '未命名对象';
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
    obj?.perceptionSlotId !== undefined ? 'perception_slot' : undefined
  );
};

const getObjectScopePrefix = (kind?: string): string => {
  const m: Record<string, string> = {
    feature: '能力点', flow: '业务流程', flow_step: '流程步骤',
    business_object: '数据对象', business_object_attribute: '数据字段',
    actor: '业务角色', scenario: '业务场景', acceptance_criterion: '验收标准',
    scope: '范围决策', perception_slot: '感知槽',
  };
  return m[kind || ''] || '选中项';
};

/** Map frontend object kind to backend edit target_type. */
const kindToEditType = (kind?: string): string | null => {
  if (kind === 'actor') return 'actor';
  if (kind === 'feature') return 'feature';
  if (kind === 'flow') return 'flow';
  if (kind === 'business_object') return 'business_object';
  return null;
};

/** Map frontend object kind to backend explain target_type. */
const kindToExplainType: Record<string, string> = {
  actor: 'actor', feature: 'feature', flow: 'flow',
  business_object: 'business_object', flow_step: 'flow',
  scenario: 'feature', acceptance_criterion: 'feature',
};

export function ScopedAIBar() {
  const { ir } = useWorkspaceStore();
  const selectedObject: any = useWorkspaceStore(selectSelectedObject);
  const location = useLocation();
  // Derive current page from URL directly (avoids stale store state on refresh)
  const pageMatch = location.pathname.match(/\/(overview|what|flow|scope|preview)$/);
  const currentPage = pageMatch ? `/${pageMatch[1]}` : '/overview';

  // ── Shared state ──
  const [isCollapsed, setIsCollapsed] = useState(true);
  const [preferredPosition, setPreferredPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const dragStartMouse = useRef({ x: 0, y: 0 });
  const isDragAction = useRef(false);

  // ── Mode state ──
  const [mode, setMode] = useState<AIMode>('explain');

  // ── Explain state ──
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ── Edit state ──
  const [editStep, setEditStep] = useState<EditStep>('idle');
  const [editSessionId, setEditSessionId] = useState<number | null>(null);
  const [editMessages, setEditMessages] = useState<ChatMessage[]>([]);
  const [editInput, setEditInput] = useState('');
  const [editDraft, setEditDraft] = useState<any>(null);
  const [editIsSending, setEditIsSending] = useState(false);
  const [editIsConfirming, setEditIsConfirming] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const editMessagesEndRef = useRef<HTMLDivElement>(null);

  // ── Window resize ──
  const [windowSize, setWindowSize] = useState({
    width: typeof window !== 'undefined' ? window.innerWidth : 1000,
    height: typeof window !== 'undefined' ? window.innerHeight : 800,
  });

  useEffect(() => {
    const handleResize = () => {
      setWindowSize({ width: window.innerWidth, height: window.innerHeight });
      setPreferredPosition(prev => ({
        x: Math.max(40 + 48 - window.innerWidth, Math.min(8, prev.x)),
        y: Math.max(40 + 48 - window.innerHeight, Math.min(8, prev.y)),
      }));
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
  useEffect(() => { editMessagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [editMessages]);

  const renderedPosition = useMemo(() => {
    if (isCollapsed) return preferredPosition;
    const W = Math.min(480, windowSize.width - 32);
    return {
      x: Math.max(40 + W - windowSize.width, Math.min(8, preferredPosition.x)),
      y: Math.max(40 + 280 - windowSize.height, Math.min(8, preferredPosition.y)),
    };
  }, [preferredPosition, isCollapsed, windowSize]);

  // ── Drag handlers ──
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    const target = e.target as HTMLElement;
    if (!isCollapsed && target.closest('button, select, textarea, input')) return;
    setIsDragging(true);
    dragStartMouse.current = { x: e.clientX, y: e.clientY };
    isDragAction.current = false;
    setDragStart({ x: e.clientX - renderedPosition.x, y: e.clientY - renderedPosition.y });
  };

  useEffect(() => {
    if (!isDragging) return;
    const onMove = (e: MouseEvent) => {
      const dx = e.clientX - dragStartMouse.current.x;
      const dy = e.clientY - dragStartMouse.current.y;
      if (Math.abs(dx) > 4 || Math.abs(dy) > 4) isDragAction.current = true;
      const W = isCollapsed ? 48 : Math.min(480, windowSize.width - 32);
      setPreferredPosition({
        x: Math.max(40 + W - windowSize.width, Math.min(8, e.clientX - dragStart.x)),
        y: Math.max(40 + 48 - windowSize.height, Math.min(8, e.clientY - dragStart.y)),
      });
    };
    const onUp = () => setIsDragging(false);
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    return () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
  }, [isDragging, dragStart, isCollapsed, windowSize]);

  // ── Scope ──
  const scopes = useMemo(() => {
    const next: AIScope[] = [
      { kind: 'projection', projection: pageToProjection(currentPage), label: `当前阶段: ${pageToStageLabel(currentPage)}` },
      { kind: 'workspace', label: '整个系统空间' },
    ];
    if (selectedObject) {
      next.unshift({ kind: 'node', nodeId: getObjectId(selectedObject), label: `${getObjectScopePrefix(getObjectKind(selectedObject))}: ${getObjectTitle(selectedObject)}` });
    }
    return next;
  }, [currentPage, selectedObject]);

  const [selectedScopeIndex, setSelectedScopeIndex] = useState(0);

  useEffect(() => { setSelectedScopeIndex(0); }, [selectedObject, currentPage]);

  const scope = scopes[selectedScopeIndex] || scopes[0];
  const isNodeScope = scope.kind === 'node';
  const editTargetType = isNodeScope ? kindToEditType(getObjectKind(selectedObject)) : null;
  const canEdit = isNodeScope && editTargetType !== null;

  // ── Mode switching ──
  const handleModeChange = useCallback(async (newMode: AIMode) => {
    if (newMode === mode) return;
    // If edit mode has an active draft in progress, discard it
    if (mode === 'edit' && editDraft && editStep !== 'done' && editStep !== 'idle') {
      const discardId = editDraft?.draftId ?? editDraft?.draft_id;
      if (discardId) {
        try { await workspaceApi.discardAIAddObjectDraft(discardId); } catch { /* ignore */ }
      }
    }
    setEditStep('idle');
    setEditSessionId(null);
    setEditMessages([]);
    setEditDraft(null);
    setEditError(null);
    setMode(newMode);
  }, [mode, editDraft, editStep]);

  // Auto-restrict scope to node when entering edit mode
  useEffect(() => {
    if (mode === 'edit') {
      const nodeIdx = scopes.findIndex(s => s.kind === 'node');
      if (nodeIdx >= 0) setSelectedScopeIndex(nodeIdx);
    }
  }, [mode, scopes]);

  // ── Explain handlers ──
  const toExplainScope = useCallback((s: AIScope): any => {
    if (s.kind === 'node') {
      const kind = getObjectKind(selectedObject);
      return { kind: 'node', target_type: kindToExplainType[kind || ''] || 'feature', target_id: parseInt(s.nodeId, 10) || 0 };
    }
    if (s.kind === 'projection') {
      const stageMap: Record<string, string> = { goal: 'what', system: 'how', data: 'scope', ui: 'preview' };
      return { kind: 'projection', stage: stageMap[(s as any).projection] || 'what' };
    }
    return { kind: 'workspace' };
  }, [selectedObject]);

  const handleExplainSubmit = useCallback(async () => {
    const q = question.trim();
    if (!q || isLoading) return;
    setIsLoading(true); setError(null);
    setMessages(prev => [...prev, { role: 'user', content: q }]);
    setQuestion('');
    try {
      const projectId = ir?.projectId ?? (ir as any)?.project_id ?? 0;
      const res = await workspaceApi.explainAI(projectId, toExplainScope(scope), q);
      setMessages(prev => [...prev, { role: 'assistant', content: res.answer || '(收到空回答)' }]);
    } catch (err: any) {
      const m = err?.detail || '请求失败，请稍后重试';
      setError(m);
      setMessages(prev => [...prev, { role: 'assistant', content: m }]);
    } finally { setIsLoading(false); }
  }, [question, isLoading, scope, toExplainScope, ir]);

  const handleExplainKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleExplainSubmit(); }
  };

  const handleClear = () => { setMessages([]); setError(null); };

  // ── Edit handlers ──
  const handleEditStart = useCallback(async () => {
    if (!canEdit || !isNodeScope || !editTargetType) return;
    setEditStep('creating_session'); setEditError(null);
    try {
      const projectId = ir?.projectId ?? (ir as any)?.project_id ?? 0;
      const targetId = parseInt(scope.nodeId, 10);
      const session = await workspaceApi.createAIEditSession(projectId, targetId, editTargetType);
      const sid = session.sessionId ?? session.session_id;
      setEditSessionId(sid);
      setEditStep('chat');
    } catch (err: any) {
      setEditError(err?.detail || '创建编辑会话失败');
      setEditStep('idle');
    }
  }, [canEdit, isNodeScope, editTargetType, scope, ir]);

  const handleEditSend = useCallback(async () => {
    const text = editInput.trim();
    if (!text || !editSessionId || editIsSending) return;
    setEditInput('');
    setEditIsSending(true);
    setEditMessages(prev => [...prev, { role: 'user', content: text }]);
    try {
      const res = await workspaceApi.sendAIAddSessionMessage(editSessionId, text);
      const reply = res.assistantMessage ?? res.assistant_message ?? '';
      setEditMessages(prev => [...prev, { role: 'assistant', content: reply }]);
      if (res.isReadyToGenerate ?? res.is_ready_to_generate) setEditStep('ready');
    } catch (err: any) {
      setEditMessages(prev => [...prev, { role: 'assistant', content: err?.detail || '发送失败' }]);
    } finally { setEditIsSending(false); }
  }, [editInput, editSessionId, editIsSending]);

  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleEditSend(); }
  };

  const handleGenerateEditDraft = useCallback(async () => {
    if (!editSessionId) return;
    setEditStep('generating'); setEditError(null);
    try {
      const res = await workspaceApi.generateAIAddObjectDraft(editSessionId);
      setEditDraft(res);
      setEditStep('preview');
    } catch (err: any) {
      setEditError(err?.detail || '生成编辑草稿失败');
      setEditStep('ready');
    }
  }, [editSessionId]);

  const handleConfirmEdit = useCallback(async () => {
    if (!editDraft) return;
    setEditIsConfirming(true); setEditError(null);
    try {
      await workspaceApi.confirmAIAddObjectDraft(editDraft.draftId ?? editDraft.draft_id);
      setEditStep('done');
      // Refresh workspace
      useWorkspaceStore.getState().refreshWorkspace();
      setTimeout(() => {
        setEditStep('idle'); setEditSessionId(null); setEditMessages([]); setEditDraft(null);
      }, 1500);
    } catch (err: any) {
      setEditError(err?.detail || '确认失败');
    } finally { setEditIsConfirming(false); }
  }, [editDraft]);

  const handleDiscardEdit = useCallback(async () => {
    if (!editDraft) return;
    try { await workspaceApi.discardAIAddObjectDraft(editDraft.draftId ?? editDraft.draft_id); } catch { /* ignore */ }
    setEditDraft(null); setEditStep('idle'); setEditSessionId(null); setEditMessages([]); setEditError(null);
  }, [editDraft]);

  // ── Collapsed state ──
  if (isCollapsed) {
    return (
      <div className="fixed bottom-6 right-6 z-50" style={{ transform: `translate(${renderedPosition.x}px, ${renderedPosition.y}px)`, transition: isDragging ? 'none' : undefined }}>
        <button
          onClick={(e) => { if (isDragAction.current) { e.preventDefault(); e.stopPropagation(); return; } setIsCollapsed(false); }}
          onMouseDown={handleMouseDown}
          className={`w-12 h-12 rounded-full bg-gradient-to-tr from-indigo-600 to-violet-500 text-white flex items-center justify-center shadow-xl hover:shadow-indigo-200 hover:scale-105 border-2 border-white animate-in fade-in zoom-in-50 duration-200 ${isDragging ? 'cursor-grabbing' : 'cursor-grab transition-all active:scale-95'}`}
        >
          <Sparkles className="w-5 h-5 animate-pulse" />
        </button>
      </div>
    );
  }

  // ── Expanded state ──
  return (
    <div className="fixed bottom-6 right-6 z-40 w-[min(480px,calc(100vw-2rem))] select-none" style={{ transform: `translate(${renderedPosition.x}px, ${renderedPosition.y}px)`, transition: isDragging ? 'none' : undefined }}>
      <div className="bg-white/95 backdrop-blur-md rounded-3xl shadow-2xl border border-slate-200/80 overflow-hidden flex flex-col">
        {/* ── Header + Mode Selector ── */}
        <div onMouseDown={handleMouseDown} className={`px-4 py-2 bg-slate-50/80 border-b border-slate-100 ${isDragging ? 'cursor-grabbing' : 'cursor-grab'}`}>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="p-1 bg-indigo-50 rounded-lg text-indigo-500"><Sparkles className="w-3.5 h-3.5" /></span>
              <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest font-mono">AI 助手</span>
            </div>
            <button type="button" onClick={() => setIsCollapsed(true)} className="p-1 hover:bg-slate-200 rounded-md text-slate-400 hover:text-slate-600 transition-colors"><Minus className="w-3.5 h-3.5" /></button>
          </div>
          {/* Mode segmented control */}
          <div className="flex bg-slate-100 rounded-xl p-0.5" onMouseDown={e => e.stopPropagation()}>
            <button
              type="button"
              onClick={() => handleModeChange('explain')}
              className={`flex-1 py-1.5 text-[10px] font-bold rounded-lg transition-all ${mode === 'explain' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
            >
              问答
            </button>
            <button
              type="button"
              onClick={() => handleModeChange('edit')}
              className={`flex-1 py-1.5 text-[10px] font-bold rounded-lg transition-all ${mode === 'edit' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
            >
              修改
            </button>
          </div>
        </div>

        {/* ── Scope Selector (explain mode) / Target Display (edit mode) ── */}
        {mode === 'explain' && (
          <div className="px-4 pt-2.5 pb-1">
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider shrink-0">范围:</span>
              <select
                value={selectedScopeIndex}
                onChange={(e) => setSelectedScopeIndex(Number(e.target.value))}
                className="flex-1 bg-slate-50 hover:bg-slate-100 border border-slate-200 text-slate-700 text-xs font-extrabold px-3 py-1.5 rounded-xl outline-none cursor-pointer focus:ring-2 focus:ring-indigo-500 shadow-sm"
              >
                {scopes.map((item, index) => (
                  <option key={`${item.kind}-${index}`} value={index}>{item.label}</option>
                ))}
              </select>
            </div>
          </div>
        )}
        {mode === 'edit' && (
          <div className="px-4 pt-2.5 pb-1">
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider shrink-0">对象:</span>
              <span className="flex-1 bg-slate-100 text-slate-700 text-xs font-extrabold px-3 py-1.5 rounded-xl">
                {isNodeScope ? scope.label : '请选中一个具体对象'}
              </span>
            </div>
            {!canEdit && (
              <p className="text-[10px] text-amber-600 mt-1 font-medium">修改模式需要选中一个具体对象（角色/功能/流程/业务对象）</p>
            )}
          </div>
        )}

        {/* ── Explain Panel ── */}
        {mode === 'explain' && (
          <>
            <div className="px-4 py-2 max-h-[320px] overflow-y-auto space-y-2.5 min-h-[100px]">
              {messages.length === 0 && (
                <div className="text-center py-6">
                  <Bot className="w-8 h-8 text-indigo-200 mx-auto mb-2" />
                  <p className="text-[10px] text-slate-400 leading-relaxed">输入你的问题，AI 将基于当前范围内的项目数据进行解释回答。</p>
                </div>
              )}
              {messages.map((msg, i) => (
                <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                  <div className={`w-6 h-6 rounded-xl flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-indigo-100' : 'bg-slate-100'}`}>
                    {msg.role === 'user' ? <User className="w-3 h-3 text-indigo-600" /> : <Bot className="w-3 h-3 text-slate-600" />}
                  </div>
                  <div className={`px-3 py-2 rounded-2xl text-xs leading-relaxed whitespace-pre-wrap max-w-[80%] ${msg.role === 'user' ? 'bg-indigo-500 text-white rounded-tr-md' : 'bg-slate-50 border border-slate-100 text-slate-700 rounded-tl-md'}`}>
                    {msg.content}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {error && (
              <div className="px-4 pb-1">
                <div className="bg-rose-50 border border-rose-200 text-rose-700 text-[10px] font-bold px-3 py-2 rounded-xl">{error}</div>
              </div>
            )}

            <div className="px-4 pb-3 pt-1 border-t border-slate-100">
              <div className="flex items-center gap-1.5 text-[9px] text-slate-400 bg-slate-50 border border-slate-100/50 rounded-lg p-1.5 mb-2 font-medium">
                <Sparkles className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                <span>AI 将参考项目知识库中已启用且处理成功的资料。</span>
              </div>
              <div className="flex gap-2">
                <textarea ref={inputRef} value={question} onChange={e => setQuestion(e.target.value)} onKeyDown={handleExplainKeyDown} placeholder="输入你的问题..." rows={1}
                  className="flex-1 px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium resize-none leading-relaxed" />
                <button onClick={handleExplainSubmit} disabled={!question.trim() || isLoading}
                  className="self-end p-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed">
                  {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </button>
              </div>
              <div className="flex items-center justify-between mt-2">
                <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
                  <span>当前将对【{scope.label}】进行解释回答</span>
                </div>
                {messages.length > 0 && (
                  <button onClick={handleClear} className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-slate-600"><RotateCcw className="w-3 h-3" />清除</button>
                )}
              </div>
            </div>
          </>
        )}

        {/* ── Edit Panel ── */}
        {mode === 'edit' && (
          <>
            {editStep === 'idle' && (
              <div className="px-4 py-6 text-center">
                <FileText className="w-8 h-8 text-indigo-200 mx-auto mb-2" />
                <p className="text-[10px] text-slate-400 leading-relaxed mb-3">选中一个对象后，通过对话描述你想做的修改。</p>
                <button
                  type="button"
                  onClick={handleEditStart}
                  disabled={!canEdit}
                  className="px-4 py-2 bg-indigo-600 text-white text-xs font-bold rounded-xl hover:bg-indigo-700 transition-colors shadow-sm disabled:opacity-50"
                >
                  开始编辑
                </button>
              </div>
            )}

            {(editStep === 'creating_session') && (
              <div className="px-4 py-8 flex items-center justify-center gap-2 text-xs text-slate-500">
                <Loader2 className="w-4 h-4 animate-spin text-indigo-500" />
                创建编辑会话...
              </div>
            )}

            {(editStep === 'chat' || editStep === 'ready' || editStep === 'generating') && (
              <>
                <div className="px-4 py-2 max-h-[280px] overflow-y-auto space-y-2.5 min-h-[80px]">
                  {editMessages.length === 0 && (
                    <div className="text-center py-4">
                      <p className="text-[10px] text-slate-400">描述你想对【{scope.label}】做的修改...</p>
                    </div>
                  )}
                  {editMessages.map((msg, i) => (
                    <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                      <div className={`w-6 h-6 rounded-xl flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-indigo-100' : 'bg-slate-100'}`}>
                        {msg.role === 'user' ? <User className="w-3 h-3 text-indigo-600" /> : <Bot className="w-3 h-3 text-slate-600" />}
                      </div>
                      <div className={`px-3 py-2 rounded-2xl text-xs leading-relaxed max-w-[80%] ${msg.role === 'user' ? 'bg-indigo-500 text-white rounded-tr-md' : 'bg-slate-50 border border-slate-100 text-slate-700 rounded-tl-md'}`}>
                        {msg.content}
                      </div>
                    </div>
                  ))}
                  <div ref={editMessagesEndRef} />
                </div>

                {editError && (
                  <div className="px-4 pb-1">
                    <div className="bg-rose-50 border border-rose-200 text-rose-700 text-[10px] font-bold px-3 py-2 rounded-xl">{editError}</div>
                  </div>
                )}

                <div className="px-4 pb-3 pt-1 border-t border-slate-100 space-y-2">
                  <div className="flex items-center gap-1.5 text-[9px] text-slate-400 bg-slate-50 border border-slate-100/50 rounded-lg p-1.5 mb-1 font-medium">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                    <span>AI 将参考项目知识库中已启用且处理成功的资料。</span>
                  </div>
                  {editStep === 'chat' && (
                    <div className="flex gap-2">
                      <textarea value={editInput} onChange={e => setEditInput(e.target.value)} onKeyDown={handleEditKeyDown} placeholder="描述修改内容..." rows={1}
                        className="flex-1 px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium resize-none leading-relaxed" />
                      <button onClick={handleEditSend} disabled={!editInput.trim() || editIsSending}
                        className="self-end p-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl transition-colors shadow-sm disabled:opacity-50">
                        {editIsSending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                      </button>
                    </div>
                  )}
                  {editStep === 'ready' && (
                    <div className="flex gap-2">
                      <button onClick={handleGenerateEditDraft} className="flex-1 flex items-center justify-center gap-1.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl transition-colors shadow-sm">
                        <Sparkles className="w-4 h-4" />生成编辑草稿
                      </button>
                      <button onClick={() => { setEditStep('chat'); }} className="px-3 py-2 border border-slate-200 text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50">继续对话</button>
                    </div>
                  )}
                  {editStep === 'generating' && (
                    <div className="flex items-center justify-center gap-2 py-2 text-xs text-slate-500">
                      <Loader2 className="w-4 h-4 animate-spin text-indigo-500" />正在生成编辑草稿...
                    </div>
                  )}
                </div>
              </>
            )}

            {editStep === 'preview' && editDraft && (
              <div className="px-4 py-3">
                <div className="bg-amber-50/80 border border-amber-100 rounded-2xl p-4 space-y-2">
                  <div className="flex items-center gap-1.5 text-[10px] font-bold text-amber-700 uppercase tracking-wider">
                    <FileText className="w-3.5 h-3.5" />修改预览
                  </div>
                  <div className="space-y-2">
                    {Object.entries(editDraft.preview || {}).map(([field, change]: [string, any]) => (
                      <div key={field} className="bg-white border border-amber-100 rounded-xl p-3">
                        <div className="text-[10px] font-bold text-slate-500 uppercase mb-1.5">{field}</div>
                        <div className="text-xs text-rose-600 line-through mb-0.5">{String(change.old || '')}</div>
              <div className="text-xs text-emerald-700 font-bold">{String(change.new || '')}</div>
                      </div>
                    ))}
                  </div>
                  {editDraft.rationale && (
                    <p className="text-[10px] text-slate-500 italic border-t border-amber-100/60 pt-2 mt-1">{editDraft.rationale}</p>
                  )}
                </div>
                {editError && (
                  <div className="mt-2 bg-rose-50 border border-rose-200 text-rose-700 text-[10px] font-bold px-3 py-2 rounded-xl">{editError}</div>
                )}
                <div className="flex gap-2 mt-3">
                  <button onClick={handleConfirmEdit} disabled={editIsConfirming}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl transition-colors shadow-sm disabled:opacity-50">
                    {editIsConfirming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}确认修改
                  </button>
                  <button onClick={handleDiscardEdit} disabled={editIsConfirming}
                    className="px-4 py-2.5 border border-slate-200 text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50">丢弃</button>
                </div>
              </div>
            )}

            {editStep === 'done' && (
              <div className="px-4 pb-3">
                <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-bold px-4 py-3 rounded-2xl flex items-center gap-2">
                  <Check className="w-4 h-4" />修改已保存！
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
