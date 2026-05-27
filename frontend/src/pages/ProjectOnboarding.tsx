import { useState } from 'react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { ArrowLeft, Plus, Sparkles } from 'lucide-react';
import { DraftPreviewModal } from '@/components/shared/DraftPreviewModal';

export function ProjectOnboarding() {
  const {
    startAIOnboarding,
    confirmAIOnboarding,
    regenerateAIOnboarding,
    discardAIOnboarding,
    createBlankWorkspace,
    activeDraft,
    activeDraftType,
    setSystemView,
    isLoading,
    isGenerating,
    error,
  } = useWorkspaceStore();

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
  };

  return (
    <div className="flex-1 min-h-screen bg-slate-50 flex flex-col pt-16 px-6 font-sans">
      <div className="max-w-4xl mx-auto w-full animate-in fade-in slide-in-from-bottom-4 duration-500 relative pb-20">
        <button
          type="button"
          onClick={() => setSystemView('home')}
          className="absolute -top-10 left-0 flex items-center gap-1 text-slate-500 hover:text-slate-800 transition-colors text-sm font-medium"
        >
          <ArrowLeft className="w-4 h-4" />
          返回工作台首页
        </button>

        <div className="text-center mb-10 mt-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-indigo-50 text-indigo-700 text-xs font-bold rounded-full mb-5 border border-indigo-100 shadow-sm">
            <Sparkles className="w-4 h-4" />
            AI 应用架构助手
          </div>
          <h1 className="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight mb-4">
            开始构建完整的应用体系
          </h1>
          <p className="text-slate-500 text-sm max-w-xl mx-auto leading-relaxed">
            输入业务想法后生成项目草稿。草稿会在弹窗中预览，确认后才会进入工作区。
          </p>
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
              className="flex items-center justify-center gap-2 px-5 py-3 bg-white border border-slate-200 text-slate-700 rounded-xl text-sm font-bold hover:bg-slate-100 transition-colors disabled:opacity-50"
            >
              <Plus className="w-4 h-4" />
              创建空白项目
            </button>
            <button
              type="button"
              onClick={handleGenerate}
              disabled={!prompt.trim() || isWorking}
              className="flex items-center justify-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-bold shadow-lg shadow-indigo-100 transition-colors disabled:opacity-50"
            >
              <Sparkles className="w-4 h-4" />
              生成 AI 项目草稿
            </button>
          </div>
        </div>
      </div>

      <DraftPreviewModal
        draft={activeDraftType === 'project' ? activeDraft : null}
        draftType={activeDraftType === 'project' ? activeDraftType : null}
        isWorking={isWorking}
        onDiscard={discardAIOnboarding}
        onRegenerate={(feedback) => regenerateAIOnboarding(feedback)}
        onConfirm={confirmAIOnboarding}
        confirmLabel="确认并进入工作区"
      />
    </div>
  );
}
