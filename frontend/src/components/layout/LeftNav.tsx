import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { LayoutDashboard, Target, Activity, CheckSquare, Eye, ChevronLeft, ChevronRight } from 'lucide-react';
import { 
  useWorkspaceStore, 
  selectPageHealth
} from '@/store/useWorkspaceStore';

export function LeftNav() {
  const location = useLocation();
  const ir = useWorkspaceStore(s => s.ir);
  const [collapsed, setCollapsed] = useState(false);

  const calculateCoverage = (nodes: any[]) => {
    if (nodes.length === 0) return 0;
    const confirmed = nodes.filter(n => n.status === 'confirmed').length;
    return Math.floor((confirmed / nodes.length) * 100);
  };

  const allNodes = ir ? Object.values(ir.nodes || {}) : [];
  const goals = allNodes.filter((n: any) => n.kind === 'goal');
  const actors = allNodes.filter((n: any) => n.kind === 'actor');
  const flowSteps = allNodes.filter((n: any) => n.kind === 'flow_step');
  const screens = allNodes.filter((n: any) => n.kind === 'screen');
  const dataObjects = allNodes.filter((n: any) => n.kind === 'business_object');

  const readinessScore = Math.floor(
    (calculateCoverage(goals) +
      calculateCoverage(actors) +
      calculateCoverage(flowSteps) +
      calculateCoverage(screens) +
      calculateCoverage(dataObjects)) / 5
  );

  const getCounts = (path: string) => {
    return selectPageHealth({ ir } as any, path);
  };

  const NavItems = [
    { path: '/', label: '概览', icon: LayoutDashboard },
    { path: '/what', label: '要做什么', icon: Target },
    { path: '/flow', label: '怎么运作', icon: Activity },
    { path: '/scope', label: '范围与交付', icon: CheckSquare },
    { path: '/preview', label: '方案预览', icon: Eye },
  ];

  return (
    <nav className={cn(
      "bg-white border-r border-slate-200 flex flex-col shrink-0 min-h-screen transition-all duration-300 relative",
      collapsed ? "w-16" : "w-64"
    )}>
      <button 
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-3 top-[calc(50%+2rem)] -translate-y-1/2 bg-white border border-slate-200 rounded-full w-6 h-6 flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-300 shadow-sm hover:shadow z-20 transition-all"
      >
        {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
      </button>

      <div className={cn("h-16 border-b border-slate-200 flex flex-shrink-0 items-center transition-all", collapsed ? "justify-center px-0" : "px-6 gap-3")}>
        <img src="/plume-gradient.svg" alt="Plume" className="w-7 h-7 shrink-0" />
        {!collapsed && <span className="font-bold text-lg tracking-tight italic text-slate-800">需求空间工作台</span>}
      </div>
      
      <div className={cn("flex-1 space-y-1 overflow-y-auto overflow-x-hidden", collapsed ? "p-2" : "p-4")}>
        {NavItems.map((item) => {
          const isActive = location.pathname === item.path;
          const Icon = item.icon;
          const { gapCount, todoCount, hasRisk, status, disabled } = getCounts(item.path);
          
          const InnerContent = collapsed ? (
             <div className="flex justify-center items-center w-full relative" title={item.label}>
                <Icon className="h-5 w-5 shrink-0" />
                {hasRisk && <div className="absolute -top-1 -right-1 w-2 h-2 bg-rose-500 rounded-full animate-pulse border border-white"></div>}
                {!hasRisk && (gapCount > 0 || todoCount > 0) && <div className="absolute -top-1 -right-1 w-2 h-2 bg-amber-500 rounded-full border border-white"></div>}
             </div>
          ) : (
            <div className="flex flex-col gap-1.5 w-full overflow-hidden">
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2 overflow-hidden">
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="text-sm shrink-0 whitespace-nowrap font-medium text-slate-800 truncate">{item.label}</span>
                </div>
                
                <div className="flex items-center gap-1.5 shrink-0">
                  {hasRisk && <div className="w-1.5 h-1.5 bg-rose-500 rounded-full animate-pulse shrink-0"></div>}
                  <span className={cn(
                    "text-[10px] px-1.5 py-0.5 rounded font-medium italic whitespace-nowrap",
                    status === '已收敛' ? "bg-emerald-100 text-emerald-700" :
                    status === '可预览' ? "bg-indigo-100 text-indigo-700" :
                    status === '阻塞' ? "bg-rose-100 text-rose-700" :
                    status === '待决策' ? "bg-amber-100 text-amber-700" :
                    status === '未开始' || status === '不可用' ? "bg-slate-100 text-slate-500" :
                    "bg-slate-200 text-slate-600"
                  )}>
                    {status}
                  </span>
                </div>
              </div>
              
              <div className="pl-6 min-h-[14px] flex items-center">
                {disabled && item.path === '/preview' ? (
                  <span className="text-[10px] text-slate-500 leading-tight">需要先生成流程和角色后可查看</span>
                ) : (gapCount > 0 || todoCount > 0) ? (
                  <span className="text-[10px] text-slate-400 font-medium whitespace-nowrap truncate">
                    {item.path === '/preview' ? (
                      `${todoCount} 个待处理`
                    ) : (
                      <>
                        {gapCount > 0 && `${gapCount} 缺口`}
                        {gapCount > 0 && todoCount > 0 && ' / '}
                        {todoCount > 0 && `${todoCount} 待确认`}
                      </>
                    )}
                  </span>
                ) : null}
              </div>
            </div>
          );
          
          if (disabled) {
            return (
              <div 
                key={item.path} 
                className={cn("flex items-center rounded-xl transition-colors relative block opacity-50 cursor-not-allowed grayscale bg-slate-50/30", collapsed ? "p-3 justify-center" : "p-3")}
              >
                {InnerContent}
              </div>
            );
          }

          return (
            <Link 
              key={item.path} 
              to={item.path}
              className={cn(
                "flex items-center rounded-xl transition-colors relative block",
                collapsed ? "p-3 justify-center" : "p-3",
                isActive ? "bg-indigo-50 text-indigo-700 font-semibold" : "hover:bg-slate-100 text-slate-600"
              )}
            >
              {InnerContent}
            </Link>
          );
        })}
      </div>

      {!collapsed && (
        <div className="p-4 border-t border-slate-200 shrink-0">
          <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
            <div className="text-xs text-slate-500 mb-1 italic">整体成熟度</div>
            <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
              <div className="bg-indigo-500 h-2 rounded-full" style={{ width: `${readinessScore}%` }}></div>
            </div>
            <div className="text-xs text-right mt-1 font-mono font-bold text-slate-700">{readinessScore}%</div>
          </div>
        </div>
      )}
    </nav>
  );
}
