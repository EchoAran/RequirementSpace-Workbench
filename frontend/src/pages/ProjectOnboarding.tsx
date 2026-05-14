import { useState } from 'react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { Sparkles, ArrowRight, ArrowLeft, RefreshCw } from 'lucide-react';
export function ProjectOnboarding() {
  const { initializeWorkspace, setSystemView, isLoading, error } = useWorkspaceStore();
  const [prompt, setPrompt] = useState('');

  const handleGenerate = async () => {
    await initializeWorkspace(prompt);
  };

  return (
    <div className="flex-1 min-h-screen bg-slate-50 flex flex-col pt-20 px-6 font-sans">
      <div className="max-w-4xl mx-auto w-full animate-in fade-in slide-in-from-bottom-4 duration-700 relative pb-20">
        <button
          onClick={() => setSystemView('home')}
          className="absolute -top-12 left-0 flex items-center gap-1 text-slate-500 hover:text-slate-800 transition-colors text-sm font-medium"
        >
          <ArrowLeft className="w-4 h-4" /> 返回工作台首页
        </button>

        <div className="text-center mb-12">
           <div className="inline-flex items-center gap-2 px-3 py-1 bg-indigo-50 text-indigo-700 text-xs font-bold rounded-full mb-6 border border-indigo-100">
             <Sparkles className="w-4 h-4" />
             AI 应用架构师
           </div>
           <h1 className="text-4xl font-black text-slate-900 tracking-tight mb-4">
             从一句话开始，构建完整的应用体系
           </h1>
           <p className="text-slate-500 text-lg">
             输入您的原始业务想法，AI 将自动推演目标、拆解能力、识别角色并构建流程状态。
           </p>
        </div>

        <div className="bg-white rounded-3xl shadow-xl border border-slate-200 overflow-hidden relative">
           {isLoading && (
             <div className="absolute inset-0 bg-white/80 backdrop-blur-sm z-20 flex flex-col items-center justify-center">
               <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mb-4"></div>
               <p className="font-bold text-slate-700">正在调用 LLM 生成初始需求空间...</p>
               <p className="text-sm text-slate-500">将生成目标、角色、流程、数据与界面结构</p>
             </div>
           )}

           <div className="p-8">
             <label className="block text-sm font-bold text-slate-700 mb-3 tracking-wide">原始应用诉求</label>
             <textarea 
               value={prompt}
               onChange={(e) => setPrompt(e.target.value)}
               className="w-full h-32 p-4 text-slate-800 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none resize-none transition-shadow"
               placeholder="描述您想构建什么应用，目标用户是谁，核心流程是什么..."
               disabled={isLoading}
             />

             {!!error && (
               <div className="mt-3 text-sm text-rose-600 font-medium">
                 {error}
               </div>
             )}
             
             <div className="mt-8 flex justify-between items-center">
               <div className="flex gap-2">
                 <button 
                   onClick={() => setPrompt('我想做一个轻量的项目进度跟踪工具，支持看板视图和列表视图，能看当前项目的风险。')}
                   className="text-[11px] px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg transition-colors font-medium border border-slate-200"
                 >项目跟踪场景</button>
                 <button 
                   onClick={() => setPrompt('我想做一个给全公司使用的在线请假系统，员工提交后由直属经理审批，最后 HR 归档，要求有PC和移动端支持。')}
                   className="text-[11px] px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg transition-colors font-medium border border-slate-200"
                 >请假审批场景</button>
               </div>
               <div className="flex items-center gap-2">
                 <button 
                   onClick={handleGenerate}
                   disabled={!prompt.trim() || isLoading}
                   className="flex items-center gap-1.5 px-4 py-2 text-sm font-bold text-slate-600 bg-white border border-slate-200 hover:bg-slate-50 rounded-xl transition-all shadow-sm disabled:opacity-50"
                 >
                   <RefreshCw className="w-4 h-4 text-indigo-500" /> 更新起点
                 </button>
                 <button 
                   onClick={handleGenerate}
                   disabled={!prompt.trim() || isLoading}
                   className="flex items-center gap-2 bg-slate-900 text-white px-6 py-3 rounded-xl font-bold hover:bg-slate-800 transition-all disabled:opacity-50"
                 >
                   生成结构化起点
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
