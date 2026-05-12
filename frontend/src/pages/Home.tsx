import { useEffect, useMemo } from 'react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { AppWindow, Plus, Clock, ArrowRight, Sparkles, LayoutGrid } from 'lucide-react';

export function Home() {
  const { setSystemView, openWorkspace, loadWorkspaces, workspaces, isLoading, error } = useWorkspaceStore();

  useEffect(() => {
    loadWorkspaces();
  }, [loadWorkspaces]);

  const sorted = useMemo(() => {
    return [...workspaces].sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1));
  }, [workspaces]);

  const formatRelativeTime = (iso: string) => {
    const t = Date.parse(iso);
    if (Number.isNaN(t)) return '未知时间';
    const diffMs = Date.now() - t;
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return '刚刚修改';
    if (mins < 60) return `${mins} 分钟前修改`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours} 小时前修改`;
    const days = Math.floor(hours / 24);
    return `${days} 天前修改`;
  };

  const renderStatusSticker = (p: any) => {
    if (p.status === '待确认缺口') {
      return (
        <span className="px-3 py-1.5 bg-amber-50 text-amber-700 text-[10px] font-bold rounded-xl border border-amber-200/60 uppercase tracking-widest flex items-center gap-1 shadow-sm">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>
          {p.status} {p.issueCount > 0 ? `(${p.issueCount})` : ''}
        </span>
      );
    }
    if (p.status === '设计中') {
      return (
        <span className="px-3 py-1.5 bg-sky-50 text-sky-700 text-[10px] font-bold rounded-xl border border-sky-200/60 uppercase tracking-widest shadow-sm">
          {p.status}
        </span>
      );
    }
    if (p.status === '草稿') {
      return (
        <span className="px-3 py-1.5 bg-slate-100 text-slate-600 text-[10px] font-bold rounded-xl border border-slate-200/60 uppercase tracking-widest shadow-sm">
          {p.status}
        </span>
      );
    }
    return (
      <span className="px-3 py-1.5 bg-slate-100 text-slate-600 text-[10px] font-bold rounded-xl border border-slate-200/60 uppercase tracking-widest shadow-sm">
        {p.status || '项目'}
      </span>
    );
  };

  return (
    <div className="flex-1 min-h-[100dvh] bg-[#F8FAFC] flex flex-col font-sans selection:bg-indigo-100 relative overflow-hidden">
      {/* Decorative Background */}
      <div className="absolute inset-0 z-0 pointer-events-none flex justify-center">
        <div className="absolute top-0 w-full h-[500px] bg-gradient-to-b from-indigo-50/80 to-transparent"></div>
        <div className="absolute -top-48 right-0 w-[600px] h-[600px] bg-indigo-300/20 rounded-full blur-[100px]"></div>
        <div className="absolute top-0 left-0 w-full h-full bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMSIgY3k9IjEiIHI9IjEiIGZpbGw9InJnYmEoMCwwLDAsMC4wMikiLz48L3N2Zz4=')] [mask-image:linear-gradient(to_bottom,white,transparent)]"></div>
      </div>

      {/* Top Navigation */}
      <header className="h-16 border-b border-slate-200/50 bg-white/60 backdrop-blur-xl flex items-center px-10 shrink-0 sticky top-0 z-20">
        <div className="flex items-center gap-3">
          <img src="/plume-gradient.svg" alt="Plume" className="w-7 h-7 shrink-0" />
          <span className="font-extrabold text-lg tracking-tight text-slate-900">需求空间工作台</span>
        </div>
        <div className="ml-auto flex items-center gap-4">
           <div className="w-8 h-8 overflow-hidden rounded-full bg-slate-200 ring-2 ring-white shadow-sm cursor-pointer hover:ring-indigo-100 transition-all">
             <img src="https://api.dicebear.com/7.x/notionists/svg?seed=Felix&backgroundColor=e0e7ff" alt="User avatar" />
           </div>
        </div>
      </header>

      <div className="flex-1 w-full max-w-7xl mx-auto px-8 sm:px-12 py-16 lg:py-24 z-10 flex flex-col relative">
        <div className="max-w-3xl mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-xs font-bold tracking-wide uppercase mb-6 shadow-sm">
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI-Powered Workspace</span>
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black text-slate-900 tracking-tight leading-[1.1] mb-6">
            将业务构想转化为<br className="hidden sm:block" />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-violet-600">可执行的产品定义</span>
          </h1>
          <p className="text-slate-500 text-lg sm:text-xl leading-relaxed max-w-3xl font-medium">
            通过自然语言自动化分析需求、生成工作流、识别系统缺口并产出界面原型。
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Create New Project Card */}
          <div 
            onClick={() => setSystemView('onboarding')}
            className="lg:col-span-5 bg-slate-900 text-white rounded-[2rem] cursor-pointer transition-all hover:shadow-2xl hover:shadow-indigo-900/20 hover:-translate-y-1 flex flex-col p-10 group relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
            <div className="absolute -right-10 -top-10 w-40 h-40 bg-indigo-500/30 blur-2xl rounded-full group-hover:bg-indigo-400/40 transition-colors"></div>

            <div className="w-16 h-16 bg-white/10 backdrop-blur-md rounded-2xl flex items-center justify-center mb-10 border border-white/10 group-hover:scale-110 transition-transform origin-bottom-left shadow-inner">
              <Plus className="w-8 h-8 text-white" />
            </div>
            <div className="mt-auto relative z-10">
              <h2 className="text-3xl font-bold mb-3 tracking-tight flex items-center gap-3">
                新建应用
                <ArrowRight className="w-6 h-6 opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all" />
              </h2>
              <p className="text-slate-400 text-base leading-relaxed max-w-[90%]">
                输入您的业务诉求或想法，唤起 AI 助手立即生成系统数据架构与流程约束。
              </p>
            </div>
          </div>

          {/* Recent Projects area */}
          <div className="lg:col-span-7 flex flex-col gap-4">
            <div className="flex items-center justify-between px-2 mb-2">
              <h2 className="text-sm font-bold text-slate-800 uppercase tracking-widest flex items-center gap-2">
                <LayoutGrid className="w-4 h-4 text-slate-400" />
                正在进行的项目
              </h2>
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 flex-1">
              {sorted.map((p) => (
                <div
                  key={p.id}
                  onClick={() => openWorkspace(p.id)}
                  className="bg-white border border-slate-200/60 p-8 rounded-[2rem] hover:border-indigo-300 hover:shadow-[0_8px_30px_rgb(0,0,0,0.06)] transition-all cursor-pointer flex flex-col group relative overflow-hidden"
                >
                  <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-50/50 rounded-bl-full -z-10 transition-transform group-hover:scale-110"></div>
                  <div className="flex justify-between items-start mb-8">
                    <div className="w-14 h-14 bg-indigo-50 text-indigo-600 rounded-2xl flex items-center justify-center border border-indigo-100">
                      <AppWindow className="w-7 h-7" strokeWidth={1.5} />
                    </div>
                    {renderStatusSticker(p)}
                  </div>
                  <h3 className="text-xl font-bold text-slate-900 mb-2 tracking-tight group-hover:text-indigo-600 transition-colors">
                    {p.name}
                  </h3>
                  <p className="text-sm text-slate-500 mb-8 line-clamp-2 leading-relaxed flex-1">
                    {p.idea || '暂无描述'}
                  </p>
                  <div className="text-[11px] text-slate-400 font-medium flex items-center gap-1.5 uppercase tracking-wider bg-slate-50 self-start px-3 py-1.5 rounded-lg border border-slate-100">
                    <Clock className="w-3.5 h-3.5" />
                    {formatRelativeTime(p.updatedAt)}
                  </div>
                </div>
              ))}

              {!isLoading && sorted.length === 0 && (
                <div className="bg-white/60 border border-slate-200/60 p-8 rounded-[2rem] flex flex-col items-center justify-center text-center">
                  <div className="w-14 h-14 bg-slate-100 text-slate-500 rounded-2xl flex items-center justify-center border border-slate-200/50 mb-4">
                    <AppWindow className="w-7 h-7" strokeWidth={1.5} />
                  </div>
                  <div className="text-sm font-bold text-slate-700 mb-1">暂无项目</div>
                  <div className="text-xs text-slate-500">点击左侧“新建应用”开始创建</div>
                </div>
              )}

              {isLoading && (
                <div className="bg-white/60 border border-slate-200/60 p-8 rounded-[2rem] flex items-center justify-center text-slate-500 text-sm">
                  正在加载项目列表...
                </div>
              )}
            </div>

            {error && (
              <div className="text-sm text-rose-600 px-2">
                {error}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

