/**
 * ProjectInterviewDialog — chat dialog for the "先简单聊聊" project creation flow.
 *
 * An AI interview agent asks questions to gather project requirements.
 * When ready, the user can complete the interview, which creates the project
 * with the gathered requirements and navigates to the workspace.
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Send, Loader2, Bot, User, Check, X } from 'lucide-react';
import { workspaceApi } from '@/lib/api';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { buildProjectRoute } from '@/core/selectors';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface ProjectInterviewDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ProjectInterviewDialog({ isOpen, onClose }: ProjectInterviewDialogProps) {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [summary, setSummary] = useState('');
  const [isCompleting, setIsCompleting] = useState(false);
  const [projectName, setProjectName] = useState('');
  const [projectDesc, setProjectDesc] = useState('');
  const [step, setStep] = useState<'name_input' | 'chat' | 'ready' | 'completing' | 'done'>('name_input');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Start the interview with an initial AI greeting
  const handleStartInterview = useCallback(async () => {
    if (!projectName.trim()) return;
    setStep('chat');

    const initialMessages: ChatMessage[] = [];
    setMessages(initialMessages);

    setIsSending(true);
    try {
      const res = await workspaceApi.interviewChat(initialMessages);
      setMessages([{ role: 'assistant', content: res.reply }]);
      if (res.is_ready) {
        setIsReady(true);
        setSummary(res.summary);
        setStep('ready');
      }
    } catch {
      setMessages([{ role: 'assistant', content: '你好！请告诉我你想构建一个什么样的项目？' }]);
    } finally {
      setIsSending(false);
    }
  }, [projectName]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isSending) return;
    setInput('');
    setIsSending(true);

    const updatedMessages = [...messages, { role: 'user' as const, content: text }];
    setMessages(updatedMessages);

    try {
      const res = await workspaceApi.interviewChat(updatedMessages);
      setMessages(prev => [...prev, { role: 'assistant', content: res.reply }]);
      if (res.is_ready) {
        setIsReady(true);
        setSummary(res.summary);
        setStep('ready');
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: '抱歉，通信异常，请稍后重试。' }]);
    } finally {
      setIsSending(false);
    }
  }, [input, messages, isSending]);

  const handleComplete = useCallback(async () => {
    if (!summary) return;
    setIsCompleting(true);
    setStep('completing');

    try {
      const finalName = projectName.trim() || '未命名项目';
      const finalDesc = projectDesc.trim() || '通过AI访谈创建的项目';
      const result = await workspaceApi.completeInterview(finalName, finalDesc, summary);

      // Set the draft in the store so DraftPreviewModal in ProjectOnboarding shows it
      if (result.draftId || result.draft_id) {
        const draft = {
          draftId: result.draftId ?? result.draft_id,
          draft_id: result.draftId ?? result.draft_id,
          projectPreview: result.projectPreview ?? result.project_preview ?? {},
          project_preview: result.projectPreview ?? result.project_preview ?? {},
          actors: result.actors ?? [],
          features: result.features ?? [],
        };
        useWorkspaceStore.setState({
          activeDraft: draft,
          activeDraftType: 'project',
          currentSystemView: 'onboarding',
        });
      }

      setStep('done');

      // Close dialog after brief pause — DraftPreviewModal takes over
      setTimeout(() => {
        onClose();
      }, 800);
    } catch {
      setStep('ready');
      setIsCompleting(false);
    }
  }, [summary, projectName, projectDesc, onClose]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (step === 'name_input') return;
      handleSend();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4 animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="bg-white border border-slate-200 shadow-2xl w-full max-w-lg flex flex-col rounded-3xl animate-in scale-in-95 duration-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        style={{ maxHeight: 'min(85vh, 600px)' }}
      >
        {/* ── Header ── */}
        <div className="p-5 pb-3 border-b border-slate-100 bg-gradient-to-r from-indigo-50/80 to-slate-50/80">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-indigo-100 rounded-xl flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-indigo-600" />
              </div>
              <div>
                <h3 className="font-extrabold text-sm text-slate-800">先简单聊聊</h3>
                <p className="text-[10px] text-slate-500 mt-0.5">AI 将通过对话了解你的项目需求</p>
              </div>
            </div>
            <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-xl transition-all">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* ── Name Input Step ── */}
        {step === 'name_input' && (
          <div className="p-6 space-y-4">
            <div className="text-center">
              <Bot className="w-12 h-12 text-indigo-200 mx-auto mb-3" />
              <p className="text-sm text-slate-600 leading-relaxed mb-4">
                在开始对话前，请先给你的项目起个名字。
              </p>
            </div>
            <input
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="例如：极简本地音乐播放器"
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800"
              onKeyDown={(e) => { if (e.key === 'Enter') handleStartInterview(); }}
            />
            <div className="space-y-1.5">
              <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">项目简述（可选）</label>
              <input
                type="text"
                value={projectDesc}
                onChange={(e) => setProjectDesc(e.target.value)}
                placeholder="一句话描述项目目标"
                className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800"
              />
            </div>
            <button
              onClick={handleStartInterview}
              disabled={!projectName.trim()}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-sm rounded-xl transition-colors shadow-sm disabled:opacity-50"
            >
              开始访谈
            </button>
          </div>
        )}

        {/* ── Chat Messages ── */}
        {(step === 'chat' || step === 'ready' || step === 'completing') && (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
              {messages.map((msg, i) => (
                <div key={i} className={`flex gap-2 max-w-[85%] ${msg.role === 'user' ? 'ml-auto flex-row-reverse' : ''}`}>
                  <div className={`w-7 h-7 rounded-xl flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-indigo-100' : 'bg-slate-100'}`}>
                    {msg.role === 'user' ? <User className="w-3.5 h-3.5 text-indigo-600" /> : <Bot className="w-3.5 h-3.5 text-slate-600" />}
                  </div>
                  <div className={`px-3.5 py-2 rounded-2xl text-xs leading-relaxed whitespace-pre-wrap ${msg.role === 'user' ? 'bg-indigo-500 text-white rounded-tr-md' : 'bg-slate-50 border border-slate-100 text-slate-700 rounded-tl-md'}`}>
                    {msg.content}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* ── Action area ── */}
            <div className="border-t border-slate-100 p-4 pt-3 space-y-2">
              {step === 'chat' && (
                <div className="flex gap-2">
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="回答AI的问题..."
                    rows={2}
                    className="flex-1 px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium resize-none leading-relaxed"
                  />
                  <button
                    onClick={handleSend}
                    disabled={!input.trim() || isSending}
                    className="self-end p-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl transition-colors shadow-sm disabled:opacity-50"
                  >
                    {isSending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  </button>
                </div>
              )}

              {step === 'ready' && (
                <div className="flex gap-2">
                  <button
                    onClick={handleComplete}
                    disabled={isCompleting}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl transition-colors shadow-sm disabled:opacity-50"
                  >
                    {isCompleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                    完成访谈，创建项目
                  </button>
                  <button
                    onClick={() => setStep('chat')}
                    className="px-4 py-2.5 border border-slate-200 text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors"
                  >
                    继续对话
                  </button>
                </div>
              )}

              {step === 'completing' && (
                <div className="flex items-center justify-center gap-2 py-2.5 text-xs text-slate-500">
                  <Loader2 className="w-4 h-4 text-indigo-500 animate-spin" />
                  正在创建项目...
                </div>
              )}
            </div>
          </>
        )}

        {/* ── Done ── */}
        {step === 'done' && (
          <div className="p-6 text-center">
            <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm font-bold px-4 py-4 rounded-2xl flex items-center justify-center gap-2">
              <Check className="w-5 h-5" />
              项目已创建，正在跳转...
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
