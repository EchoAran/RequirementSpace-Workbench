/**
 * AIAddObjectDialog — conversational dialog for AI-powered single-object addition.
 *
 * Wraps the interview → draft → confirm lifecycle into a chat UI.
 * Uses the backend's ai_add_session endpoints to drive a multi-turn interview,
 * then generates a previewable draft that the user can confirm or discard.
 *
 * Props:
 *   targetType — which object type to create (actor, feature_leaf, etc.)
 *   anchor    — entry context (parent_feature_id, related_flow_id, etc.)
 *   onConfirm — callback fired after successful confirmation (refresh data)
 */

import { useTranslation } from 'react-i18next';
import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Send,
  Sparkles,
  Bot,
  User,
  Check,
  X,
  Loader2,
  FileText,
} from 'lucide-react';
import { workspaceApi } from '@/lib/api';
import { cn } from '@/lib/utils';

export type AIAddTargetType =
  | 'actor'
  | 'feature_leaf'
  | 'feature_branch'
  | 'flow'
  | 'business_object';

interface AIAddObjectDialogProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  targetType: AIAddTargetType;
  anchor?: Record<string, any>;
  onConfirm: () => void;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

type DialogStep = 'creating' | 'chat' | 'ready' | 'generating' | 'preview' | 'confirming' | 'done';



export function AIAddObjectDialog({
  isOpen,
  onClose,
  projectId,
  targetType,
  anchor,
  onConfirm,
}: AIAddObjectDialogProps) {
  const { t } = useTranslation();
  const [step, setStep] = useState<DialogStep>('creating');
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [draft, setDraft] = useState<any>(null);
  const [isSending, setIsSending] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Create session on mount
  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;

    (async () => {
      setStep('creating');
      setError(null);
      try {
        const session = await workspaceApi.createAIAddSession({
          project_id: projectId,
          target_type: targetType,
          anchor: anchor || {},
        });
        if (cancelled) return;
        setSessionId(session.sessionId ?? session.session_id);
        setStep('chat');
      } catch (err: any) {
        if (cancelled) return;
        setError(err?.detail || t('addObjectDialog.createSessionFailed'));
        setStep('chat');
      }
    })();

    return () => { cancelled = true; };
  }, [isOpen, projectId, targetType, anchor]);

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = useCallback(async () => {
    const text = inputValue.trim();
    if (!text || !sessionId || isSending) return;

    setInputValue('');
    setIsSending(true);
    setMessages(prev => [...prev, { role: 'user', content: text }]);

    try {
      const res = await workspaceApi.sendAIAddSessionMessage(sessionId, text);
      setMessages(prev => [...prev, { role: 'assistant', content: res.assistantMessage ?? res.assistant_message ?? '' }]);
      if (res.isReadyToGenerate ?? res.is_ready_to_generate) {
        setStep('ready');
      }
    } catch (err: any) {
      setMessages(prev => [...prev, { role: 'assistant', content: err?.detail || t('addObjectDialog.sendMessageFailed') }]);
    } finally {
      setIsSending(false);
    }
  }, [inputValue, sessionId, isSending]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleGenerateDraft = useCallback(async () => {
    if (!sessionId) return;
    setStep('generating');
    setError(null);
    try {
      const res = await workspaceApi.generateAIAddObjectDraft(sessionId);
      setDraft(res);
      setStep('preview');
    } catch (err: any) {
      setError(err?.detail || t('addObjectDialog.generateDraftFailed'));
      setStep('ready');
    }
  }, [sessionId]);

  const handleConfirm = useCallback(async () => {
    if (!draft) return;
    setIsConfirming(true);
    setError(null);
    try {
      await workspaceApi.confirmAIAddObjectDraft(draft.draftId ?? draft.draft_id);
      setStep('done');
      onConfirm();
      setTimeout(() => onClose(), 1200);
    } catch (err: any) {
      setError(err?.detail || t('addObjectDialog.confirmFailed'));
    } finally {
      setIsConfirming(false);
    }
  }, [draft, onConfirm, onClose]);

  const handleDiscard = useCallback(async () => {
    if (!draft) return;
    try {
      await workspaceApi.discardAIAddObjectDraft(draft.draftId ?? draft.draft_id);
    } catch {
      // Ignore discard errors
    }
    setDraft(null);
    setStep('chat');
    setMessages([]);
    setSessionId(null);
    setError(null);
  }, [draft]);

  const handleRestart = useCallback(() => {
    setDraft(null);
    setStep('chat');
    setError(null);
  }, []);

  const handleClose = useCallback(() => {
    // Discard draft if exists
    if (draft) {
      workspaceApi.discardAIAddObjectDraft(draft.draftId ?? draft.draft_id).catch(() => {});
    }
    setDraft(null);
    setMessages([]);
    setSessionId(null);
    setStep('creating');
    setError(null);
    onClose();
  }, [draft, onClose]);

  if (!isOpen) return null;

  const targetLabels: Record<AIAddTargetType, string> = {
    actor: t('addObjectDialog.targetLabels.actor'),
    feature_leaf: t('addObjectDialog.targetLabels.feature_leaf'),
    feature_branch: t('addObjectDialog.targetLabels.feature_branch'),
    flow: t('addObjectDialog.targetLabels.flow'),
    business_object: t('addObjectDialog.targetLabels.business_object'),
  };
  const targetLabel = targetLabels[targetType] || targetType;
  const preview = draft?.preview ?? {};

  return (
    <div
      className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4 select-none animate-in fade-in duration-200"
      onClick={handleClose}
    >
      <div
        className="bg-white border border-slate-200 shadow-2xl w-full max-w-lg flex flex-col rounded-3xl animate-in scale-in-95 duration-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        style={{ maxHeight: 'min(90vh, 680px)' }}
      >
        {/* ── Header ── */}
        <div className="p-5 pb-3 border-b border-slate-100 bg-gradient-to-r from-indigo-50/80 to-slate-50/80">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-indigo-100 rounded-xl flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-indigo-600" />
              </div>
              <div>
                <h3 className="font-extrabold text-sm text-slate-800">{t('addObjectDialog.headerTitle', { target: targetLabel })}</h3>
                <p className="text-[10px] text-slate-500 mt-0.5">
                  {step === 'creating' && t('addObjectDialog.stepTitle.creating')}
                  {step === 'chat' && t('addObjectDialog.stepTitle.chat')}
                  {step === 'ready' && t('addObjectDialog.stepTitle.ready')}
                  {step === 'generating' && t('addObjectDialog.stepTitle.generating')}
                  {step === 'preview' && t('addObjectDialog.stepTitle.preview')}
                  {step === 'confirming' && t('addObjectDialog.stepTitle.confirming')}
                  {step === 'done' && t('addObjectDialog.stepTitle.done')}
                </p>
              </div>
            </div>
            <button
              onClick={handleClose}
              className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-xl transition-all"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* ── Messages ── */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
          {step === 'creating' && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 text-indigo-500 animate-spin" />
            </div>
          )}

          {messages.length === 0 && step !== 'creating' && (
            <div className="text-center py-8 px-4">
              <Bot className="w-10 h-10 text-indigo-200 mx-auto mb-3" />
              <p className="whitespace-pre-line text-xs text-slate-500 leading-relaxed">
                {t('addObjectDialog.chatTip', { target: targetLabel })}
              </p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={cn(
                'flex gap-2.5 max-w-[85%]',
                msg.role === 'user' ? 'ml-auto flex-row-reverse' : '',
              )}
            >
              <div
                className={cn(
                  'w-7 h-7 rounded-xl flex items-center justify-center shrink-0',
                  msg.role === 'user' ? 'bg-indigo-100' : 'bg-slate-100',
                )}
              >
                {msg.role === 'user' ? (
                  <User className="w-3.5 h-3.5 text-indigo-600" />
                ) : (
                  <Bot className="w-3.5 h-3.5 text-slate-600" />
                )}
              </div>
              <div
                className={cn(
                  'px-3.5 py-2 rounded-2xl text-xs leading-relaxed whitespace-pre-wrap',
                  msg.role === 'user'
                    ? 'bg-indigo-500 text-white rounded-tr-md'
                    : 'bg-slate-50 border border-slate-100 text-slate-700 rounded-tl-md',
                )}
              >
                {msg.content}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* ── Error ── */}
        {error && (
          <div className="px-4 pb-2">
            <div className="bg-rose-50 border border-rose-200 text-rose-700 text-[10px] font-bold px-3 py-2 rounded-xl">
              {error}
            </div>
          </div>
        )}

        {/* ── Preview (when draft is ready) ── */}
        {step === 'preview' && draft && (
          <div className="px-4 pb-3">
            <div className="bg-indigo-50/80 border border-indigo-100 rounded-2xl p-4 space-y-2">
              <div className="flex items-center gap-1.5 text-[10px] font-bold text-indigo-700 uppercase tracking-wider">
                <FileText className="w-3.5 h-3.5" />
                {t('addObjectDialog.previewTitle')}
              </div>
              <div className="space-y-1.5 text-xs text-slate-700">
                {preview.name && (
                  <p><span className="font-bold text-slate-800">{t('addObjectDialog.previewFields.name')}</span>{preview.name}</p>
                )}
                {preview.description && (
                  <p><span className="font-bold text-slate-800">{t('addObjectDialog.previewFields.description')}</span>{preview.description}</p>
                )}
                {preview.featureKind && (
                  <p><span className="font-bold text-slate-800">{t('addObjectDialog.previewFields.type')}</span>
                    {preview.featureKind === 'leaf' ? t('addObjectDialog.previewFields.feature_leaf') : t('addObjectDialog.previewFields.feature_branch')}
                  </p>
                )}
                {preview.actorIds && preview.actorIds.length > 0 && (
                  <p><span className="font-bold text-slate-800">{t('addObjectDialog.previewFields.actorIds')}</span>{preview.actorIds.join(', ')}</p>
                )}
                {preview.featureIds && preview.featureIds.length > 0 && (
                  <p><span className="font-bold text-slate-800">{t('addObjectDialog.previewFields.featureIds')}</span>{preview.featureIds.join(', ')}</p>
                )}
                {preview.attributeCount !== undefined && (
                  <p><span className="font-bold text-slate-800">{t('addObjectDialog.previewFields.attributeCount')}</span>{preview.attributeCount}</p>
                )}
              </div>
              {draft.rationale && (
                <p className="text-[10px] text-slate-500 italic border-t border-indigo-100/60 pt-2 mt-1">
                  {draft.rationale}
                </p>
              )}
            </div>
          </div>
        )}

        {/* ── Done message ── */}
        {step === 'done' && (
          <div className="px-4 pb-3">
            <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-bold px-4 py-3 rounded-2xl flex items-center gap-2">
              <Check className="w-4 h-4" />
              {t('addObjectDialog.createSuccess', { target: targetLabel })}
            </div>
          </div>
        )}

        {/* ── Bottom area ── */}
        <div className="border-t border-slate-100 p-4 pt-3 space-y-2">
          {/* Action buttons instead of input */}
          {step === 'ready' && (
            <div className="flex gap-2">
              <button
                onClick={handleGenerateDraft}
                className="flex-1 flex items-center justify-center gap-1.5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl transition-colors shadow-sm"
              >
                <Sparkles className="w-4 h-4" />
                {t('addObjectDialog.generateDraftBtn')}
              </button>
              <button
                onClick={handleRestart}
                className="px-4 py-2.5 border border-slate-200 text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors"
              >
                {t('addObjectDialog.continueChatBtn')}
              </button>
            </div>
          )}

          {step === 'preview' && (
            <div className="flex gap-2">
              <button
                onClick={handleConfirm}
                disabled={isConfirming}
                className="flex-1 flex items-center justify-center gap-1.5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl transition-colors shadow-sm disabled:opacity-50"
              >
                {isConfirming ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Check className="w-4 h-4" />
                )}
                {t('addObjectDialog.confirmBtn')}
              </button>
              <button
                onClick={handleDiscard}
                disabled={isConfirming}
                className="px-4 py-2.5 border border-slate-200 text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
              >
                {t('addObjectDialog.discardBtn')}
              </button>
            </div>
          )}

          {step === 'generating' && (
            <div className="flex items-center justify-center gap-2 py-2.5 text-xs text-slate-500">
              <Loader2 className="w-4 h-4 text-indigo-500 animate-spin" />
              {t('addObjectDialog.generatingDraftTip', { target: targetLabel })}
            </div>
          )}

          {step === 'chat' && (
            <div className="flex gap-2">
              <textarea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t('addObjectDialog.inputPlaceholder', { target: targetLabel })}
                rows={2}
                className="flex-1 px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium resize-none leading-relaxed"
              />
              <button
                onClick={handleSend}
                disabled={!inputValue.trim() || isSending}
                className="self-end p-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
