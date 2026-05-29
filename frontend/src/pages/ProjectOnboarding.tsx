import { useState } from 'react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { ArrowLeft } from 'lucide-react';
import { DraftPreviewModal } from '@/components/shared/DraftPreviewModal';
import { useNavigate } from 'react-router-dom';
import { buildProjectRoute } from '@/core/selectors';

export function ProjectOnboarding() {
  const {
    startAIOnboarding,
    confirmAIOnboarding,
    regenerateAIOnboarding,
    discardAIOnboarding,
    createBlankWorkspace,
    activeDraft,
    activeDraftType,
    isLoading,
    isGenerating,
    error,
  } = useWorkspaceStore();
  const navigate = useNavigate();

  const [prompt, setPrompt] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const isWorking = isLoading || isGenerating;

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    await startAIOnboarding(prompt.trim(), name.trim() || undefined, description.trim() || undefined);
  };

  const handleCreateBlank = async () => {
    if (!prompt.trim()) return;
    const finalName = name.trim() || '未命名需求空间';
    const finalDesc = description.trim() || '由用户手动初始化的空白需求空间项目。';
    await createBlankWorkspace(finalName, finalDesc, prompt.trim());
    const state = useWorkspaceStore.getState();
    if (state.currentSystemView === 'workspace' && state.ir) {
      navigate(buildProjectRoute(state.ir.projectId, '/overview'));
    }
  };

  const handleConfirmDraft = async () => {
    await confirmAIOnboarding();
    const state = useWorkspaceStore.getState();
    if (state.currentSystemView === 'workspace' && state.ir) {
      navigate(buildProjectRoute(state.ir.projectId, '/overview'));
    }
  };

  return (
    <div className="flex-1 min-h-screen bg-slate-50 flex flex-col pt-16 px-6 font-sans">
      <div className="max-w-4xl mx-auto w-full animate-in fade-in slide-in-from-bottom-4 duration-500 relative pb-20">
        <button
          type="button"
          onClick={() => navigate('/home')}
          className="absolute -top-10 left-0 flex items-center gap-1 text-slate-500 hover:text-slate-800 transition-colors text-sm font-medium"
        >
          <ArrowLeft className="w-4 h-4" />
          返回工作台首页
        </button>

        <div className="text-center mb-10 mt-4">
          <h1 className="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight mb-4">
            开始构建项目需求
          </h1>
        </div>

        <div className="bg-white rounded-3xl shadow-xl border border-slate-200/80 overflow-hidden relative">
          {isWorking && (
            <div className="absolute inset-0 bg-white/85 backdrop-blur-sm z-20 flex flex-col items-center justify-center">
              <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mb-4" />
              <p className="font-bold text-slate-800 text-base">正在处理项目草稿...</p>
              <p className="text-sm text-slate-500 mt-1">这会生成项目概要、角色定义和初始功能树。</p>
            </div>
          )}

          <div className="p-8 space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-700 tracking-wide">项目名称（可选）</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full p-3 text-slate-800 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none transition-shadow text-sm"
                  placeholder="留空则由 AI 自动生成"
                  disabled={isWorking}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-700 tracking-wide">项目简述（可选）</label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full p-3 text-slate-800 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none transition-shadow text-sm"
                  placeholder="一句话描述业务目标"
                  disabled={isWorking}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 tracking-wide">项目业务诉求与愿景（必填）</label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                className="w-full h-36 p-4 text-slate-800 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none resize-none transition-shadow text-sm"
                placeholder="描述你想构建什么应用、目标用户是谁、核心流程是什么。"
                disabled={isWorking}
              />
            </div>

            {error && (
              <div className="p-3 bg-rose-50 border border-rose-100 text-rose-600 text-xs font-medium rounded-xl">
                {error}
              </div>
            )}
          </div>

          <div className="p-6 bg-slate-50 border-t border-slate-100 flex flex-col sm:flex-row justify-end gap-3">
            <button
              type="button"
              onClick={handleCreateBlank}
              disabled={!prompt.trim() || isWorking}
              className="inline-flex h-12 min-w-[168px] items-center justify-center rounded-xl border border-slate-200 bg-white px-6 text-sm font-bold text-slate-700 transition-colors hover:bg-slate-100 disabled:opacity-50"
            >
              创建空白项目
            </button>
            <div className="relative group">
              <div className="pointer-events-none absolute bottom-full right-0 mb-2 w-56 rounded-xl border border-slate-200 bg-white px-3 py-2 text-left text-xs font-medium leading-relaxed text-slate-600 shadow-lg opacity-0 translate-y-1 transition-all duration-200 group-hover:opacity-100 group-hover:translate-y-0 group-focus-within:opacity-100 group-focus-within:translate-y-0">
                先生成草稿预览，确认后再进入工作区。
              </div>
              <button
                type="button"
                onClick={handleGenerate}
                disabled={!prompt.trim() || isWorking}
                className="inline-flex h-12 min-w-[168px] items-center justify-center rounded-xl bg-indigo-600 px-6 text-sm font-bold text-white shadow-lg shadow-indigo-100 transition-colors hover:bg-indigo-700 disabled:opacity-50"
              >
                生成AI项目草稿
              </button>
            </div>
          </div>
        </div>
      </div>

      <DraftPreviewModal
        draft={activeDraftType === 'project' ? activeDraft : null}
        draftType={activeDraftType === 'project' ? activeDraftType : null}
        isWorking={isWorking}
        onDiscard={discardAIOnboarding}
        onRegenerate={(feedback) => regenerateAIOnboarding(feedback)}
        onConfirm={handleConfirmDraft}
        confirmLabel="确认并进入工作区"
      />
    </div>
  );
}
