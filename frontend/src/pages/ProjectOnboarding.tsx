import { useState } from 'react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { Sparkles, ArrowRight, ArrowLeft, CheckCircle2, Info, RefreshCw, LayoutDashboard } from 'lucide-react';
import { workspaceApi } from '@/lib/api';

export function ProjectOnboarding() {
  const { initializeWorkspace, setSystemView } = useWorkspaceStore();
  const [prompt, setPrompt] = useState('我想做一个给全公司使用的在线请假系统，员工提交后由直属经理审批，最后 HR 归档，要求有PC和移动端支持。');
  const [isGenerating, setIsGenerating] = useState(false);
  const [summary, setSummary] = useState<any>(null);

  const handleGenerate = async () => {
    setIsGenerating(true);
    setSummary(null);
    try {
      const analyzed = await workspaceApi.analyzePrompt(prompt);
      setSummary(analyzed);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleConfirm = () => {
    initializeWorkspace(prompt);
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
           {isGenerating && (
             <div className="absolute inset-0 bg-white/80 backdrop-blur-sm z-20 flex flex-col items-center justify-center">
               <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mb-4"></div>
               <p className="font-bold text-slate-700">正在进行多维度推演分析...</p>
               <p className="text-sm text-slate-500">正在生成目标、角色、流程闭环和架构边界</p>
             </div>
           )}

           <div className="p-8">
             <label className="block text-sm font-bold text-slate-700 mb-3 tracking-wide">原始应用诉求 (Natural Language Prompt)</label>
             <textarea 
               value={prompt}
               onChange={(e) => setPrompt(e.target.value)}
               className="w-full h-32 p-4 text-slate-800 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none resize-none transition-shadow"
               placeholder="描述您想构建什么应用，目标用户是谁，核心流程是什么..."
               disabled={summary !== null}
             />
             
             {!summary && (
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
                 <button 
                   onClick={handleGenerate}
                   disabled={!prompt.trim() || isGenerating}
                   className="flex items-center gap-2 bg-slate-900 text-white px-6 py-3 rounded-xl font-bold hover:bg-slate-800 transition-all disabled:opacity-50"
                 >
                   生成结构化起点
                   <ArrowRight className="w-4 h-4" />
                 </button>
               </div>
             )}
           </div>
           
           {summary && (
             <div className="border-t border-slate-100 bg-slate-50/50 p-8 animate-in fade-in slide-in-from-top-4">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="font-bold text-slate-800 text-lg flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    初步检查与摘要
                  </h3>
                  <div className="bg-emerald-50 text-emerald-700 text-xs px-3 py-1 rounded-full font-bold border border-emerald-100">
                    {summary.taskType}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-8 mb-8">
                  <div>
                    <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">推断出的核心目标</h4>
                    <ul className="space-y-2">
                      {summary.goals.map((g: string, i: number) => (
                        <li key={i} className="text-sm font-medium text-slate-700 flex items-start gap-2">
                          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0 mt-1.5"></span>
                          {g}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <div className="mb-6">
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">推断出的角色</h4>
                      <div className="flex flex-wrap gap-2">
                        {summary.actors.map((a: string, i: number) => (
                          <span key={i} className="text-xs font-bold text-slate-600 bg-white border border-slate-200 px-2 py-1 rounded shadow-sm">
                            {a}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">推断出的核心对象</h4>
                      <div className="flex flex-wrap gap-2">
                        {summary.objects.map((o: string, i: number) => (
                          <span key={i} className="text-xs font-bold text-sky-700 bg-sky-50 border border-sky-100 px-2 py-1 rounded shadow-sm">
                            {o}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mb-8 p-5 bg-white border border-slate-200 rounded-2xl shadow-sm">
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">推断出的主流程</h4>
                  <div className="flex items-center flex-wrap gap-2">
                    {summary.flows.map((f: string, i: number) => (
                      <div key={i} className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-700 bg-slate-50 border border-slate-100 px-3 py-1.5 rounded-lg">{f}</span>
                        {i < summary.flows.length - 1 && <ArrowRight className="w-4 h-4 text-slate-300 mx-1" />}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mb-8 p-5 bg-amber-50 border border-amber-100 rounded-2xl">
                  <h4 className="text-xs font-bold text-amber-600 uppercase tracking-widest mb-3 flex items-center gap-1.5">
                    <Info className="w-4 h-4" /> 开放问题 (进入工作台后可决策)
                  </h4>
                  <ul className="space-y-2">
                    {summary.questions.map((q: string, i: number) => (
                      <li key={i} className="text-sm text-amber-800 flex items-start gap-2">
                        <span className="text-amber-500 font-bold shrink-0">{i + 1}.</span>
                        {q}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="flex items-center justify-end gap-3 pt-6 border-t border-slate-200">
                  <button 
                    onClick={() => { setSummary(null); setPrompt(''); }}
                    className="flex items-center gap-1.5 px-4 py-2 text-sm font-bold text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-colors"
                  >
                    <RefreshCw className="w-4 h-4" /> 重写诉求
                  </button>
                  <button 
                    onClick={handleGenerate}
                    className="flex items-center gap-1.5 px-4 py-2 text-sm font-bold text-slate-600 bg-white border border-slate-200 hover:bg-slate-50 rounded-xl transition-all shadow-sm"
                  >
                    <Sparkles className="w-4 h-4 text-indigo-500" /> 更新起点
                  </button>
                  <button 
                    onClick={handleConfirm}
                    className="flex items-center gap-2 bg-indigo-600 text-white px-6 py-2.5 rounded-xl font-bold hover:bg-indigo-700 transition-all shadow-[0_0_15px_rgba(79,70,229,0.3)]"
                  >
                    <LayoutDashboard className="w-4 h-4" /> 直接进入工作台
                  </button>
                </div>
             </div>
           )}
        </div>
      </div>
    </div>
  );
}
