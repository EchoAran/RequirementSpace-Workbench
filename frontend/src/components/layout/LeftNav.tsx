import { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { LayoutDashboard, Target, Activity, CheckSquare, Eye, GitBranch, ChevronLeft, ChevronRight } from 'lucide-react';
import {
  useWorkspaceStore,
} from '@/store/useWorkspaceStore';
import { workspaceApi } from '@/lib/api';
import { buildProjectRouteWithBranch, buildReadiness, extractWorkspacePage } from '@/core/selectors';
import { useTranslation } from 'react-i18next';
import { getStageCheckMessage, getStageStatusLabel } from '@/core/stageProgressText';

export function LeftNav() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const ir = useWorkspaceStore(s => s.ir);
  const branchRef = useWorkspaceStore(s => s.branchRef);
  const activePage = useWorkspaceStore(s => s.activePage);
  const [collapsed, setCollapsed] = useState(false);
  const [hasCompiledPrototype, setHasCompiledPrototype] = useState(false);
  const stageProgress = useWorkspaceStore(s => s.stageProgress);
  const readinessScore = buildReadiness(ir, stageProgress).overallScore;
  const locationPage = extractWorkspacePage(location.pathname);
  const resolvedActivePage = locationPage || activePage;

  useEffect(() => {
    let cancelled = false;
    const projectId = ir?.projectId;
    if (!projectId) {
      setHasCompiledPrototype(false);
      return;
    }

    workspaceApi.getLatestPrototypePreview(projectId)
      .then((res) => {
        if (!cancelled) {
          const isCompiled = Boolean(
            res &&
            !('detail' in res) &&
            res.prototypeId &&
            res.message !== 'prototype_preview_not_found' &&
            res.status !== 'failed' &&
            res.status !== 'generating'
          );
          setHasCompiledPrototype(isCompiled);
        }
      })
      .catch(() => {
        if (!cancelled) setHasCompiledPrototype(false);
      });

    return () => {
      cancelled = true;
    };
  }, [ir?.projectId, branchRef]);

  const handleNavClick = (
    event: React.MouseEvent<HTMLAnchorElement>,
    page: string,
    disabled: boolean,
  ) => {
    if (!disabled) return;
    event.preventDefault();
    if (!stageProgress?.stages) return;

    const previousStageByPage: Record<string, string> = {
      '/flow': 'what',
      '/scope': 'how',
    };
    const transitionByStage: Record<string, 'enter_how' | 'enter_scope' | 'enter_preview'> = {
      what: 'enter_how',
      how: 'enter_scope',
      scope: 'enter_preview',
    };
    const previousStageKey = previousStageByPage[page];
    const previousStage = stageProgress.stages.find(
      (stage: any) => stage.stage === previousStageKey,
    );
    if (!previousStage) return;

    if (previousStage.statusCode === 'ready_to_advance') {
      useWorkspaceStore.getState().requestStageTransition(
        transitionByStage[previousStageKey],
        { navigate },
      );
      return;
    }

    const fallbackReason = previousStageKey
      ? t('nav.lockReason.fillRules', {
          stage: previousStageKey === 'what' ? 'What' : 'How',
        })
      : t('nav.lockReason.generic');
    const reason = getStageCheckMessage(previousStage.failedChecks?.[0], t) || fallbackReason;
    useWorkspaceStore.getState().setError(reason);
  };

  const getCounts = (path: string) => {
    if (path === '/overview') {
      return {
        issueCount: ir?.issueCount || 0,
        hasBlockingSlot: ir?.statusCode === 'needs_attention',
        statusCode: ir?.statusCode || 'not_started',
        statusLabel: ir?.status || t('home.projectStatus.not_started'),
        disabled: false,
        disabledReason: '',
      };
    }

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
          const disabled = !item.unlocked;
          const issueCount = disabled ? 0 : (item.blockingFindings ? item.blockingFindings.length : 0);
          const hasBlockingSlot = disabled ? false : item.statusCode === 'blocked';

          let disabledReason = '';
          if (disabled) {
            if (stageKey === 'how') {
              const whatItem = stageProgress.stages.find((s: any) => s.stage === 'what');
              if (whatItem && !whatItem.unlocked) {
                disabledReason = t('nav.lockReason.unlockFirst', { stage: t('nav.stageName.what') });
              } else {
                disabledReason = t('nav.lockReason.fillRules', { stage: t('nav.stageName.what') });
              }
            } else if (stageKey === 'scope') {
              const howItem = stageProgress.stages.find((s: any) => s.stage === 'how');
              if (howItem && !howItem.unlocked) {
                disabledReason = t('nav.lockReason.unlockFirst', { stage: t('nav.stageName.how') });
              } else {
                disabledReason = t('nav.lockReason.fillRules', { stage: t('nav.stageName.how') });
              }
            }
          }

          return {
            issueCount,
            hasBlockingSlot,
            statusCode: item.statusCode,
            statusLabel: getStageStatusLabel(item, t),
            disabled,
            disabledReason
          };
        }
      } else if (path === '/preview') {
        const whatStage = stageProgress?.stages?.find((s: any) => s.stage === 'what');
        const howStage = stageProgress?.stages?.find((s: any) => s.stage === 'how');
        const scopeStage = stageProgress?.stages?.find((s: any) => s.stage === 'scope');

        const isWhatDone = Boolean(
          whatStage
            ? whatStage.unlocked && (whatStage.statusCode === 'ready' || whatStage.statusCode === 'ready_to_advance' || whatStage.content_complete || ((ir?.actors || []).length > 0 && (ir?.features || []).length > 0))
            : ((ir?.actors || []).length > 0 && (ir?.features || []).length > 0)
        );

        const isHowDone = Boolean(
          howStage
            ? howStage.unlocked && (howStage.statusCode === 'ready' || howStage.statusCode === 'ready_to_advance' || howStage.content_complete || ((ir?.flows || []).length > 0 && (ir?.businessObjects || []).length > 0))
            : ((ir?.flows || []).length > 0 && (ir?.businessObjects || []).length > 0)
        );

        const isScopeDone = Boolean(
          scopeStage
            ? scopeStage.unlocked && (scopeStage.statusCode === 'ready' || scopeStage.statusCode === 'ready_to_advance' || scopeStage.content_complete || (ir?.features || []).some((f: any) => f.scope !== null && f.scope !== undefined))
            : (ir?.features || []).some((f: any) => f.scope !== null && f.scope !== undefined)
        );

        const isAllDone = isWhatDone && isHowDone && isScopeDone;

        if (!isAllDone) {
          return {
            issueCount: 0,
            hasBlockingSlot: false,
            statusCode: 'shadow_available',
            statusLabel: t('nav.status.shadow_available'),
            disabled: false,
            disabledReason: ''
          };
        }

        return {
          issueCount: 0,
          hasBlockingSlot: false,
          statusCode: hasCompiledPrototype ? 'ready' : 'in_progress',
          statusLabel: hasCompiledPrototype ? t('nav.status.ready') : t('nav.status.in_progress'),
          disabled: false,
          disabledReason: ''
        };
      } else if (path === '/repo') {
        // 版本控制入口不依赖阶段解锁，始终可用。
        return {
          issueCount: 0,
          hasBlockingSlot: false,
          statusCode: 'overview_ready',
          statusLabel: t('nav.status.playable'),
          disabled: false,
          disabledReason: ''
        };
      }
      return {
        issueCount: 0,
        hasBlockingSlot: false,
        statusCode: 'locked',
        statusLabel: t('shell.loading'),
        disabled: true,
        disabledReason: t('shell.loadingBackup')
      };
    }

    return {
      issueCount: 0,
      hasBlockingSlot: false,
      statusCode: 'locked',
      statusLabel: t('shell.loading'),
      disabled: true,
      disabledReason: t('shell.loadingBackup'),
    };
  };

  const whatStage = stageProgress?.stages?.find((s: any) => s.stage === 'what');
  const howStage = stageProgress?.stages?.find((s: any) => s.stage === 'how');
  const scopeStage = stageProgress?.stages?.find((s: any) => s.stage === 'scope');

  const isWhatComplete = Boolean(
    whatStage
      ? whatStage.unlocked && (whatStage.statusCode === 'ready' || whatStage.statusCode === 'ready_to_advance' || whatStage.content_complete || ((ir?.actors || []).length > 0 && (ir?.features || []).length > 0))
      : ((ir?.actors || []).length > 0 && (ir?.features || []).length > 0)
  );

  const isHowComplete = Boolean(
    howStage
      ? howStage.unlocked && (howStage.statusCode === 'ready' || howStage.statusCode === 'ready_to_advance' || howStage.content_complete || ((ir?.flows || []).length > 0 && (ir?.businessObjects || []).length > 0))
      : ((ir?.flows || []).length > 0 && (ir?.businessObjects || []).length > 0)
  );

  const isScopeComplete = Boolean(
    scopeStage
      ? scopeStage.unlocked && (scopeStage.statusCode === 'ready' || scopeStage.statusCode === 'ready_to_advance' || scopeStage.content_complete || (ir?.features || []).some((f: any) => f.scope !== null && f.scope !== undefined))
      : (ir?.features || []).some((f: any) => f.scope !== null && f.scope !== undefined)
  );

  const isAllComplete = isWhatComplete && isHowComplete && isScopeComplete;

  const NavItems = [
    { page: '/overview' as const, label: t('nav.overview'), icon: LayoutDashboard },
    { page: '/what' as const, label: t('nav.what'), icon: Target },
    { page: '/flow' as const, label: t('nav.flow'), icon: Activity },
    { page: '/scope' as const, label: t('nav.scope'), icon: CheckSquare },
    { page: '/preview' as const, label: isAllComplete ? t('nav.preview') : t('nav.shadowPreview'), icon: Eye },
  ];

  return (
    <nav className={cn(
      "bg-white/85 backdrop-blur-xl border-r border-slate-200/80 flex flex-col shrink-0 min-h-screen transition-all duration-300 relative select-none",
      collapsed ? "w-16" : "w-64"
    )}>
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-3 top-[calc(50%+2rem)] -translate-y-1/2 bg-white border border-slate-200 rounded-full w-6 h-6 flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-300 shadow-sm hover:shadow z-20 transition-all cursor-pointer"
      >
        {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
      </button>

      <div className={cn("h-16 border-b border-slate-200/70 flex flex-shrink-0 items-center transition-all", collapsed ? "justify-center px-0" : "px-6 gap-3")}>
        <img src={`${import.meta.env.BASE_URL}plume-gradient.svg`} alt="Plume" className="w-7 h-7 shrink-0" />
        {!collapsed && <span className="font-bold text-lg tracking-tight italic text-slate-800">{t('nav.title')}</span>}
      </div>
      <div className={cn("flex-1 space-y-1 overflow-y-auto overflow-x-hidden", collapsed ? "p-2" : "p-4")}>
        {NavItems.map((item) => {
          const isActive = resolvedActivePage === item.page;
          const Icon = item.icon;
          const { issueCount, hasBlockingSlot, statusCode, statusLabel, disabled, disabledReason } = getCounts(item.page);
          const to = buildProjectRouteWithBranch(ir?.projectId, item.page, branchRef);
          const statusKey = item.page === '/overview'
            ? `home.projectStatus.${statusCode}`
            : `nav.status.${statusCode}`;

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
                    statusCode === 'ready' || statusCode === 'real_ready' || statusCode === 'converged' || statusCode === 'ready_to_advance' ? "bg-emerald-50 text-emerald-700 border-emerald-100" :
                    statusCode === 'shadow_available' ? "bg-indigo-50 text-indigo-700 border-indigo-100" :
                    statusCode === 'needs_attention' || statusCode === 'has_issues' ? "bg-rose-50 text-rose-700 border-rose-100" :
                    statusCode === 'in_progress' || statusCode === 'scope_pending' ? "bg-amber-50 text-amber-700 border-amber-100" :
                    statusCode === 'not_started' ? "bg-slate-50 text-slate-500 border-slate-200" :
                    statusCode === 'locked' ? "bg-slate-100/70 text-slate-400 border-slate-200/50" :
                    "bg-slate-100 text-slate-500 border-slate-200"
                  )}>
                    {t(statusKey) === statusKey ? statusLabel : t(statusKey)}
                  </span>
                </div>
              </div>

              <div className="pl-6 min-h-[14px] flex items-center">
                {disabled ? (
                  <span className="text-[10px] text-slate-400 font-medium leading-tight">
                    {disabledReason}
                  </span>
                ) : (issueCount > 0 || hasBlockingSlot) ? (
                  <span className="text-[10px] text-slate-400 font-medium whitespace-nowrap truncate">
                    {item.page === '/preview' ? (
                      t(statusKey) === statusKey ? statusLabel : t(statusKey)
                    ) : (
                      <>
                        {issueCount > 0 && t('nav.pendingIssues', { count: issueCount })}
                        {issueCount > 0 && hasBlockingSlot && ' / '}
                        {hasBlockingSlot && t('nav.blockingSuggestions')}
                      </>
                    )}
                  </span>
                ) : null}
              </div>
            </div>
          );

          return (
            <Link
              key={item.page}
              to={disabled ? '#' : to}
              onClick={(event) => handleNavClick(event, item.page, disabled)}
              className={cn(
                "flex items-center rounded-xl transition-all duration-200 relative block",
                collapsed ? "p-3 justify-center" : "p-3",
                disabled
                  ? "opacity-50 grayscale bg-slate-50/20 hover:bg-slate-100/40 cursor-not-allowed"
                  : isActive
                  ? "bg-indigo-50/90 text-indigo-700 font-bold shadow-2xs before:absolute before:left-0 before:top-2.5 before:bottom-2.5 before:w-1 before:bg-indigo-600 before:rounded-r-full"
                  : "hover:bg-slate-100/70 text-slate-600 hover:text-slate-900"
              )}
            >
              {InnerContent}
            </Link>
          );
        })}
      </div>

      {/* 独立版本控制/需求仓库入口 */}
      <div className={cn("border-t border-slate-200/70", collapsed ? "p-2" : "p-3")}>
        <Link
          to={buildProjectRouteWithBranch(ir?.projectId, '/repo', branchRef)}
          className={cn(
            "flex items-center rounded-xl transition-all font-medium text-xs",
            collapsed ? "p-3 justify-center" : "px-3 py-2.5 gap-2.5",
            resolvedActivePage === '/repo'
              ? "bg-indigo-50/90 text-indigo-700 font-bold border border-indigo-200/60 shadow-2xs"
              : "text-slate-600 hover:bg-slate-100/70 border border-transparent hover:text-slate-900"
          )}
          title={t('nav.repo')}
        >
          <GitBranch className={cn("shrink-0", collapsed ? "h-5 w-5" : "h-4 w-4 text-indigo-600")} />
          {!collapsed && (
            <div className="flex items-center justify-between w-full min-w-0">
              <span className="truncate font-semibold">{t('nav.repo')}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-mono truncate max-w-[80px]" title={branchRef}>
                {branchRef}
              </span>
            </div>
          )}
        </Link>
      </div>

      {!collapsed && (
        <div className="p-4 border-t border-slate-200/70 shrink-0">
          <div className="bg-slate-50/80 backdrop-blur-xs rounded-xl p-3 border border-slate-200/70">
            <div className="text-xs text-slate-500 mb-1.5 font-medium">{t('nav.maturityLabel')}</div>
            <div className="w-full bg-slate-200/80 h-2 rounded-full overflow-hidden">
              <div className="bg-gradient-to-r from-indigo-500 to-indigo-600 h-2 rounded-full transition-all duration-500" style={{ width: String(readinessScore) + '%' }}></div>
            </div>
            <div className="text-xs text-right mt-1.5 font-mono font-bold text-indigo-700">{readinessScore}%</div>
          </div>
        </div>
      )}
    </nav>
  );
}
