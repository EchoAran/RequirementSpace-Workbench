import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { LayoutDashboard, Target, Activity, CheckSquare, Eye, ChevronLeft, ChevronRight } from 'lucide-react';
import {
  useWorkspaceStore,
  selectPageHealth
} from '@/store/useWorkspaceStore';
import { buildProjectRoute, buildReadiness, extractWorkspacePage } from '@/core/selectors';

export function LeftNav() {
  const location = useLocation();
  const navigate = useNavigate();
  const ir = useWorkspaceStore(s => s.ir);
  const activePage = useWorkspaceStore(s => s.activePage);
  const [collapsed, setCollapsed] = useState(false);
  const readinessScore = buildReadiness(ir).overallScore;
  const locationPage = extractWorkspacePage(location.pathname);
  const resolvedActivePage = locationPage || activePage;

  const stageProgress = useWorkspaceStore(s => s.stageProgress);

  const getCounts = (path: string) => {
    if (stageProgress && stageProgress.stages) {
      const stageMap: Record<string, string> = {
        '/what': 'what',
        '/flow': 'how',
        '/scope': 'scope',
      };

      const stageKey = stageMap[path];
      if (stageKey) {
        const item = stageProgress.stages.find((s: any) => s.stage === stageKey);
        if (item) {
          const issueCount = item.blockingFindings ? item.blockingFindings.length : 0;
          const hasBlockingSlot = item.statusCode === 'blocked';
          const disabled = !item.unlocked;

          let disabledReason = '';
          if (disabled) {
            if (stageKey === 'how') {
              const whatItem = stageProgress.stages.find((s: any) => s.stage === 'what');
              if (whatItem && !whatItem.unlocked) {
                disabledReason = '需先完成并解锁 What 阶段';
              } else {
                disabledReason = '需先补齐 What 阶段的所有核心建模规则';
              }
            } else if (stageKey === 'scope') {
              const howItem = stageProgress.stages.find((s: any) => s.stage === 'how');
              if (howItem && !howItem.unlocked) {
                disabledReason = '需先完成并解锁 How 阶段';
              } else {
                disabledReason = '需先补齐 How 阶段的所有核心建模规则';
              }
            }
          }

          return {
            issueCount,
            hasBlockingSlot,
            statusCode: item.statusCode,
            statusLabel: item.statusLabel,
            disabled,
            disabledReason
          };
        }
      } else if (path === '/preview') {
        return {
          issueCount: 0,
          hasBlockingSlot: false,
          statusCode: 'shadow_available',
          statusLabel: '可预演',
          disabled: false,
          disabledReason: ''
        };
      }
      return {
        issueCount: 0,
        hasBlockingSlot: false,
        statusCode: 'ready',
        statusLabel: '已就绪',
        disabled: false,
        disabledReason: ''
      };
    }

    console.warn('[deprecated] evaluateMandatoryChecks fallback is used; core gating must read StageProgress');
    return selectPageHealth({ ir } as any, path);
  };

  const NavItems = [
    { page: '/overview' as const, label: '概览', icon: LayoutDashboard },
    { page: '/what' as const, label: '要做什么', icon: Target },
    { page: '/flow' as const, label: '怎么运作', icon: Activity },
    { page: '/scope' as const, label: '范围与交付', icon: CheckSquare },
    { page: '/preview' as const, label: '方案预览', icon: Eye },
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
        <img src={`${import.meta.env.BASE_URL}plume-gradient.svg`} alt="Plume" className="w-7 h-7 shrink-0" />
        {!collapsed && <span className="font-bold text-lg tracking-tight italic text-slate-800">需求空间工作台</span>}
      </div>
      <div className={cn("flex-1 space-y-1 overflow-y-auto overflow-x-hidden", collapsed ? "p-2" : "p-4")}>
        {NavItems.map((item) => {
          const isActive = resolvedActivePage === item.page;
          const Icon = item.icon;
          const { issueCount, hasBlockingSlot, statusCode, statusLabel, disabled, disabledReason } = getCounts(item.page);
          const to = buildProjectRoute(ir?.projectId, item.page);

          const InnerContent = collapsed ? (
             <div className="flex justify-center items-center w-full relative" title={item.label}>
                <Icon className="h-5 w-5 shrink-0" />
                {hasBlockingSlot && <div className="absolute -top-1 -right-1 w-2 h-2 bg-rose-500 rounded-full animate-pulse border border-white"></div>}
                {!hasBlockingSlot && issueCount > 0 && <div className="absolute -top-1 -right-1 w-2 h-2 bg-amber-500 rounded-full border border-white"></div>}
             </div>
          ) : (
            <div className="flex flex-col gap-1.5 w-full overflow-hidden">
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2 overflow-hidden">
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="text-sm shrink-0 whitespace-nowrap font-medium text-slate-800 truncate">{item.label}</span>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  {hasBlockingSlot && <div className="w-1.5 h-1.5 bg-rose-500 rounded-full animate-pulse shrink-0"></div>}
                  <span className={cn(
                    "text-[10px] px-1.5 py-0.5 rounded font-bold whitespace-nowrap shadow-sm border",
                    statusCode === 'ready' || statusCode === 'real_ready' ? "bg-emerald-50 text-emerald-700 border-emerald-100" :
                    statusCode === 'shadow_available' ? "bg-indigo-50 text-indigo-700 border-indigo-100" :
                    statusCode === 'needs_attention' ? "bg-rose-50 text-rose-700 border-rose-100" :
                    statusCode === 'in_progress' ? "bg-amber-50 text-amber-700 border-amber-100" :
                    statusCode === 'not_started' ? "bg-slate-50 text-slate-500 border-slate-200" :
                    statusCode === 'locked' ? "bg-slate-100/70 text-slate-400 border-slate-200/50" :
                    "bg-slate-100 text-slate-500 border-slate-200"
                  )}>
                    {statusLabel}
                  </span>
                </div>
              </div>

              <div className="pl-6 min-h-[14px] flex items-center">
                {(issueCount > 0 || hasBlockingSlot) ? (
                  <span className="text-[10px] text-slate-400 font-medium whitespace-nowrap truncate">
                    {item.page === '/preview' ? (
                      statusLabel
                    ) : (
                      <>
                        {issueCount > 0 && (String(issueCount) + ' 待处理')}
                        {issueCount > 0 && hasBlockingSlot && ' / '}
                        {hasBlockingSlot && '有阻塞建议'}
                      </>
                    )}
                  </span>
                ) : disabled ? (
                  <span className="text-[10px] text-slate-400 font-medium leading-tight">
                    {disabledReason}
                  </span>
                ) : null}
              </div>
            </div>
          );

          return (
            <Link
              key={item.page}
              to={disabled ? '#' : to}
              onClick={(e) => {
                if (stageProgress && stageProgress.stages) {
                  if (disabled) {
                    e.preventDefault();
                    const stageMap: Record<string, string> = {
                      '/flow': 'what',
                      '/scope': 'how'
                    };
                    const prevStageKey = stageMap[item.page];
                    if (prevStageKey) {
                      const prevStage = stageProgress.stages.find((s: any) => s.stage === prevStageKey);
                      if (prevStage) {
                        if (prevStage.statusCode === 'ready_to_advance') {
                          const actionMap: Record<string, 'enter_how' | 'enter_scope' | 'enter_preview'> = {
                            'what': 'enter_how',
                            'how': 'enter_scope',
                            'scope': 'enter_preview'
                          };
                          useWorkspaceStore.getState().requestStageTransition(actionMap[prevStageKey], { navigate });
                        } else {
                          let reason = prevStage.failedChecks && prevStage.failedChecks[0]?.message;
                          if (!reason) {
                            if (prevStageKey === 'what') reason = '需先补齐 What 阶段的所有核心建模规则';
                            else if (prevStageKey === 'how') reason = '需先补齐 How 阶段的核心规则';
                            else reason = '当前阶段未解锁';
                          }
                          useWorkspaceStore.getState().setError(reason);
                        }
                      }
                    }
                  }
                  return;
                }

                // Exact Legacy Fallback Click Intercept
                const isFlowUnlocked = ir?.unlockedStages?.includes('what');
                const isScopeUnlocked = ir?.unlockedStages?.includes('how');

                let intercept = false;
                if (item.page === '/flow' && !isFlowUnlocked) intercept = true;
                if (item.page === '/scope' && !isScopeUnlocked) intercept = true;

                if (intercept) {
                  e.preventDefault();
                  if (item.page === '/flow') {
                    const whatHealth = getCounts('/what') as any;
                    const isWhatReady = whatHealth.statusCode === 'ready_to_advance' || whatHealth.nextSlot?.kind === 'stage_gate_transition_confirm';
                    if (isWhatReady) {
                      useWorkspaceStore.getState().requestStageTransition('enter_how', { navigate });
                    } else {
                      useWorkspaceStore.getState().setError(whatHealth.disabledReason || '需先补齐 What 阶段的所有核心建模规则');
                    }
                  } else if (item.page === '/scope') {
                    const flowHealth = getCounts('/flow') as any;
                    const isFlowReady = flowHealth.statusCode === 'ready_to_advance' || flowHealth.nextSlot?.kind === 'stage_gate_transition_confirm';
                    if (isFlowReady) {
                      useWorkspaceStore.getState().requestStageTransition('enter_scope', { navigate });
                    } else {
                      const isWhatUnlocked = ir?.unlockedStages?.includes('what');
                      const reason = !isWhatUnlocked
                        ? '需先完成并解锁 What 阶段'
                        : (flowHealth.disabledReason || '需先补齐 How 阶段的核心规则');
                      useWorkspaceStore.getState().setError(reason);
                    }
                  } else {
                    useWorkspaceStore.getState().setError(disabledReason || '当前阶段未解锁');
                  }
                }
              }}
              className={cn(
                "flex items-center rounded-xl transition-colors relative block",
                collapsed ? "p-3 justify-center" : "p-3",
                disabled ? "opacity-60 grayscale bg-slate-50/20 hover:bg-slate-100/50 cursor-not-allowed" : isActive ? "bg-indigo-50 text-indigo-700 font-semibold" : "hover:bg-slate-100 text-slate-600"
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
              <div className="bg-indigo-500 h-2 rounded-full" style={{ width: String(readinessScore) + '%' }}></div>
            </div>
            <div className="text-xs text-right mt-1 font-mono font-bold text-slate-700">{readinessScore}%</div>
          </div>
        </div>
      )}
    </nav>
  );
}
