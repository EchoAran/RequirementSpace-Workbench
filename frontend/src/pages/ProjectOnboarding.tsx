import { useState } from 'react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { Sparkles, ArrowRight, ArrowLeft, RefreshCw, Users, Layers, Check, Trash2, Edit3, Plus } from 'lucide-react';

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
    error 
  } = useWorkspaceStore();

  const [prompt, setPrompt] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [feedback, setFeedback] = useState('');

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    await startAIOnboarding(prompt, name || undefined, description || undefined);
  };

  const handleCreateBlank = async () => {
    if (!prompt.trim()) return;
    const finalName = name.trim() || '未命名需求空间';
    const finalDesc = description.trim() || '由用户手动初始化的空白需求空间项目。';
    await createBlankWorkspace(finalName, finalDesc, prompt);
  };

  const handleRegenerate = async () => {
    // Under mock logic, we trigger regenerateAIOnboarding. We can clear feedback afterwards.
    await regenerateAIOnboarding();
    setFeedback('');
  };

  const handleConfirm = async () => {
    await confirmAIOnboarding();
  };

  const handleDiscard = async () => {
    await discardAIOnboarding();
  };

  const isWorking = isLoading || isGenerating;

  // Render Draft Preview UI if activeDraft is present
  if (activeDraft && activeDraftType === 'project') {
    return (
      <div className="flex-1 min-h-screen bg-slate-50 flex flex-col pt-16 px-6 font-sans">
        <div className="max-w-5xl mx-auto w-full animate-in fade-in slide-in-from-bottom-4 duration-700 relative pb-20">
          <div className="flex justify-between items-center mb-8">
            <button
              onClick={handleDiscard}
              className="flex items-center gap-1.5 text-slate-500 hover:text-slate-800 transition-colors text-sm font-medium"
            >
              <ArrowLeft className="w-4 h-4" /> 返回重新配置
            </button>
            <div className="inline-flex items-center gap-1 px-3 py-1 bg-amber-50 text-amber-700 text-xs font-bold rounded-full border border-amber-200">
              <Sparkles className="w-3.5 h-3.5 animate-pulse" />
              AI 架构推演草稿
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left Preview Columns */}
            <div className="lg:col-span-2 space-y-6">
              {/* Core Project Card */}
              <div className="bg-white rounded-3xl p-8 border border-slate-200/80 shadow-md">
                <span className="text-[10px] bg-indigo-50 text-indigo-700 font-bold px-2.5 py-1 rounded-lg uppercase tracking-wider">项目概要</span>
                <h2 className="text-2xl font-black text-slate-900 mt-3 mb-2 tracking-tight">
                  {activeDraft.project_preview?.project_name}
                </h2>
                <p className="text-slate-600 leading-relaxed text-sm">
                  {activeDraft.project_preview?.project_description}
                </p>
                <div className="mt-6 pt-6 border-t border-slate-100 flex items-start gap-3">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-widest shrink-0 mt-0.5">原始诉求:</span>
                  <p className="text-xs text-slate-500 italic bg-slate-50 p-3 rounded-xl border border-slate-100 w-full line-clamp-3">
                    "{activeDraft.user_requirements}"
                  </p>
                </div>
              </div>

              {/* Roles Section */}
              <div className="bg-white rounded-3xl p-8 border border-slate-200/80 shadow-md">
                <h3 className="text-lg font-bold text-slate-900 mb-5 flex items-center gap-2">
                  <Users className="w-5 h-5 text-indigo-500" />
                  系统角色定义 ({activeDraft.actors?.length || 0})
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {activeDraft.actors?.map((actor: any, idx: number) => (
                    <div key={idx} className="p-4 bg-slate-50 border border-slate-200/60 rounded-2xl flex flex-col justify-between">
                      <div>
                        <h4 className="font-bold text-slate-800 text-sm mb-1">{actor.actor_name}</h4>
                        <p className="text-xs text-slate-500 leading-relaxed">{actor.actor_description}</p>
                      </div>
                      <div className="mt-3 flex items-center text-[10px] text-indigo-600 font-bold">
                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 mr-1.5"></span>
                        AI 参与者候选
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Feature Modules Section */}
              <div className="bg-white rounded-3xl p-8 border border-slate-200/80 shadow-md">
                <h3 className="text-lg font-bold text-slate-900 mb-5 flex items-center gap-2">
                  <Layers className="w-5 h-5 text-indigo-500" />
                  拆解功能模块 ({activeDraft.features?.length || 0})
                </h3>
                <div className="space-y-4">
                  {activeDraft.features?.map((feat: any, idx: number) => (
                    <div key={idx} className="p-5 bg-slate-50 border border-slate-200/60 rounded-2xl flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                          <h4 className="font-bold text-slate-800 text-sm">{feat.feature_name}</h4>
                        </div>
                        <p className="text-xs text-slate-500 max-w-xl pl-4 leading-relaxed">{feat.feature_description}</p>
                      </div>
                      <div className="flex flex-wrap gap-1 shrink-0">
                        {feat.actor_names?.map((actName: string, i: number) => (
                          <span key={i} className="text-[10px] font-bold px-2 py-1 bg-white border border-slate-200 rounded-lg text-slate-600">
                            {actName}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Right Action Dashboard Panel */}
            <div className="space-y-6">
              <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-lg sticky top-24 space-y-6">
                <div>
                  <h3 className="font-black text-slate-900 text-base mb-1">推演确认面板</h3>
                  <p className="text-xs text-slate-500">您可以直接采纳，或对推演提出改善意见进行重新生成。</p>
                </div>

                {/* Adjusting Opinion Input */}
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-700 flex items-center gap-1">
                    <Edit3 className="w-3.5 h-3.5 text-slate-500" />
                    补充调整意见 (可选)
                  </label>
                  <textarea
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    placeholder="例如：'请增加一个资产扫码归还场景'，或 '增加 HR 审核角色'"
                    className="w-full h-24 p-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-xs text-slate-800 resize-none transition-shadow"
                    disabled={isWorking}
                  />
                </div>

                <div className="space-y-3 pt-2">
                  <button
                    onClick={handleConfirm}
                    disabled={isWorking}
                    className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-sm py-3 px-4 rounded-xl shadow-lg shadow-indigo-100 transition-all disabled:opacity-50"
                  >
                    <Check className="w-4 h-4" />
                    应用草稿，进入工作区
                  </button>

                  <div className="grid grid-cols-2 gap-3">
                    <button
                      onClick={handleRegenerate}
                      disabled={isWorking}
                      className="flex items-center justify-center gap-1.5 px-3 py-2.5 border border-slate-200 hover:bg-slate-50 text-slate-700 font-bold text-xs rounded-xl transition-colors disabled:opacity-50"
                    >
                      <RefreshCw className="w-3.5 h-3.5 text-indigo-500" />
                      重新推演
                    </button>
                    <button
                      onClick={handleDiscard}
                      disabled={isWorking}
                      className="flex items-center justify-center gap-1.5 px-3 py-2.5 border border-rose-100 hover:bg-rose-50 text-rose-600 font-bold text-xs rounded-xl transition-colors disabled:opacity-50"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-rose-500" />
                      放弃草稿
                    </button>
                  </div>
                </div>

                {error && (
                  <div className="p-3 bg-rose-50 border border-rose-100 text-rose-600 text-xs font-medium rounded-xl">
                    {error}
                  </div>
                )}

                {isWorking && (
                  <div className="flex items-center justify-center gap-2 text-xs text-slate-500 bg-slate-50 p-3 rounded-xl border border-slate-100 animate-pulse">
                    <div className="w-4.5 h-4.5 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
                    AI 正在重新生成草稿，请稍候...
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Otherwise, render configuration options
  return (
    <div className="flex-1 min-h-screen bg-slate-50 flex flex-col pt-16 px-6 font-sans">
      <div className="max-w-4xl mx-auto w-full animate-in fade-in slide-in-from-bottom-4 duration-700 relative pb-20">
        <button
          onClick={() => setSystemView('home')}
          className="absolute -top-10 left-0 flex items-center gap-1 text-slate-500 hover:text-slate-800 transition-colors text-sm font-medium"
        >
          <ArrowLeft className="w-4 h-4" /> 返回工作台首页
        </button>

        <div className="text-center mb-12 mt-4">
           <div className="inline-flex items-center gap-2 px-3 py-1 bg-indigo-50 text-indigo-700 text-xs font-bold rounded-full mb-5 border border-indigo-100 shadow-sm">
             <Sparkles className="w-4 h-4" />
             AI 应用架构师
           </div>
           <h1 className="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight mb-4">
             开始构建完整的应用体系
           </h1>
           <p className="text-slate-500 text-sm max-w-xl mx-auto">
             输入您的业务想法，由 AI 推演系统架构，或直接建立空白项目，完全自主掌控需求细节。
           </p>
        </div>

        <div className="bg-white rounded-3xl shadow-xl border border-slate-200/80 overflow-hidden relative">
           {isWorking && (
             <div className="absolute inset-0 bg-white/85 backdrop-blur-sm z-20 flex flex-col items-center justify-center">
               <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mb-4"></div>
               <p className="font-bold text-slate-800 text-base">正在调用 AI 生成初始需求空间...</p>
               <p className="text-sm text-slate-500 mt-1">将生成项目底座、角色定义、以及初始功能树</p>
             </div>
           )}

           <div className="p-8 space-y-6">
             {/* General Project Metadata */}
             <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
               <div className="space-y-1.5">
                 <label className="text-xs font-bold text-slate-700 tracking-wide uppercase">项目名称 (可选)</label>
                 <input
                   type="text"
                   value={name}
                   onChange={(e) => setName(e.target.value)}
                   className="w-full p-3 text-slate-800 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none transition-shadow text-sm"
                   placeholder="可选，留空则由 AI 自动生成"
                   disabled={isWorking}
                 />
               </div>
               <div className="space-y-1.5">
                 <label className="text-xs font-bold text-slate-700 tracking-wide uppercase">项目简述 (可选)</label>
                 <input
                   type="text"
                   value={description}
                   onChange={(e) => setDescription(e.target.value)}
                   className="w-full p-3 text-slate-800 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none transition-shadow text-sm"
                   placeholder="可选，留空则由 AI 自动生成"
                   disabled={isWorking}
                 />
               </div>
             </div>

             {/* Application Requirements */}
             <div className="space-y-1.5">
               <label className="text-xs font-bold text-slate-700 tracking-wide uppercase">
                 项目业务诉求与愿景描述 (必填)
               </label>
               <textarea 
                 value={prompt}
                 onChange={(e) => setPrompt(e.target.value)}
                 className="w-full h-36 p-4 text-slate-800 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none resize-none transition-shadow text-sm"
                 placeholder="描述您想构建什么应用，目标用户是谁，核心流程是什么（无论是推演还是空白创建，此项均必填），例如：'我想做一个轻量的项目进度跟踪工具，支持看板视图和列表视图，能看当前项目的风险。'"
                 disabled={isWorking}
               />
             </div>

             {!!error && (
               <div className="text-xs text-rose-600 font-semibold bg-rose-50 p-3 rounded-xl border border-rose-100">
                 {error}
               </div>
             )}
             
             {/* Bottom Quick Presets & Creation Actions */}
             <div className="pt-6 border-t border-slate-100 flex flex-col sm:flex-row sm:justify-end sm:items-center gap-4">
               <div className="flex items-center gap-3 justify-end w-full">
                 <button 
                   onClick={handleCreateBlank}
                   disabled={!prompt.trim() || isWorking}
                   className="flex items-center gap-1.5 px-5 py-3 text-xs font-bold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 hover:border-slate-300 rounded-xl transition-all shadow-sm disabled:opacity-50 cursor-pointer"
                 >
                   <Plus className="w-3.5 h-3.5 text-slate-400" />
                   手动创建空白空间
                 </button>
                 <button 
                   onClick={handleGenerate}
                   disabled={!prompt.trim() || isWorking}
                   className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-3 rounded-xl font-bold text-sm hover:shadow-lg hover:shadow-indigo-100 transition-all disabled:opacity-50 disabled:hover:shadow-none shadow-md cursor-pointer"
                 >
                   <Sparkles className="w-4 h-4" />
                   AI 智能引导推演
                   <ArrowRight className="w-4 h-4" />
                 </button>
               </div>
             </div>
           </div>
        </div>
      </div>
    </div>
  );
}
