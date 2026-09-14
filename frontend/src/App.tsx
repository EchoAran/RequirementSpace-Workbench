import { BrowserRouter, Routes, Route, useLocation, Navigate, useNavigate, Outlet, useParams } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { ScopedAIBar } from './components/shared/ScopedAIBar';
import { GenerationConflictDialog } from './components/shared/GenerationConflictDialog';
import GateCheckModal from './components/shared/GateCheckModal';
import { useWorkspaceStore, getFriendlyErrorMessage } from './store/useWorkspaceStore';
import { Suspense, lazy, useEffect, useState } from 'react';
import { buildProjectRouteWithBranch, extractWorkspacePage } from './core/selectors';
import { useAuthStore } from './store/useAuthStore';
import { AuthGuard } from './components/auth/AuthGuard';
import { GuestGuard } from './components/auth/GuestGuard';
import { Lock, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { resolveLocalizedMessage, taskStatusTitleKey } from './core/localizedMessage';
import { getStageCheckMessage } from './core/stageProgressText';
import { BranchSwitchConfirmDialog } from './components/version-control/BranchSwitchConfirmDialog';
import { CreateBranchDialog } from './components/version-control/CreateBranchDialog';

const Overview = lazy(() => import('./pages/Overview').then((module) => ({ default: module.Overview })));
const WhatToDo = lazy(() => import('./pages/WhatToDo').then((module) => ({ default: module.WhatToDo })));
const HowItWorks = lazy(() => import('./pages/HowItWorks').then((module) => ({ default: module.HowItWorks })));
const ScopeAndDelivery = lazy(() => import('./pages/ScopeAndDelivery').then((module) => ({ default: module.ScopeAndDelivery })));
const Preview = lazy(() => import('./pages/Preview').then((module) => ({ default: module.Preview })));
const Repository = lazy(() => import('./pages/Repository').then((module) => ({ default: module.Repository })));
const ProjectOnboarding = lazy(() => import('./pages/ProjectOnboarding').then((module) => ({ default: module.ProjectOnboarding })));
const Home = lazy(() => import('./pages/Home').then((module) => ({ default: module.Home })));
const Login = lazy(() => import('./pages/Login').then((module) => ({ default: module.Login })));
const Register = lazy(() => import('./pages/Register').then((module) => ({ default: module.Register })));
const AccountSettings = lazy(() => import('./pages/AccountSettings').then((module) => ({ default: module.AccountSettings })));
const ProjectConfiguration = lazy(() => import('./pages/ProjectConfiguration').then((module) => ({ default: module.ProjectConfiguration })));

function RouteFallback() {
  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-slate-50 p-6">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 border border-indigo-100 shadow-sm">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
      </div>
    </div>
  );
}

function LazyRoute({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<RouteFallback />}>{children}</Suspense>;
}

function RouterStateSync() {
  const location = useLocation();
  const setActivePage = useWorkspaceStore(state => state.setActivePage);
  const setSystemView = useWorkspaceStore(state => state.setSystemView);

  useEffect(() => {
    const pathname = location.pathname;

    if (pathname === '/home') {
      setSystemView('home');
      setActivePage('/overview');
      return;
    }

    if (pathname === '/onboarding') {
      setSystemView('onboarding');
      setActivePage('/overview');
      return;
    }

    const workspacePage = extractWorkspacePage(pathname);
    if (workspacePage) {
      setSystemView('workspace');
      setActivePage(workspacePage);
      return;
    }

    setSystemView('home');
    setActivePage('/overview');
  }, [location.pathname, setActivePage, setSystemView]);

  return null;
}

function ProjectRouteBootstrap() {
  const { t } = useTranslation();
  const { projectId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const openWorkspace = useWorkspaceStore((s) => s.openWorkspace);
  const switchBranch = useWorkspaceStore((s) => s.switchBranch);
  const branchRef = useWorkspaceStore((s) => s.branchRef);
  const ir = useWorkspaceStore((s) => s.ir);
  const isLoading = useWorkspaceStore((s) => s.isLoading);
  const error = useWorkspaceStore((s) => s.error);
  const setActivePage = useWorkspaceStore((s) => s.setActivePage);
  const workspacePage = extractWorkspacePage(location.pathname);
  const urlBranch = new URLSearchParams(location.search).get('branch') || 'main';

  // 初始加载：项目尚未打开时以 URL 分支打开工作区。
  useEffect(() => {
    if (!projectId) return;
    if (ir?.projectId === projectId) return;
    void openWorkspace(projectId, urlBranch);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, ir?.projectId, openWorkspace]);

  // 分支 URL 同步：地址栏 branch 变化时切换分支，保证刷新/复制链接仍打开同一分支。
  // 浏览器前进/后退或手工改 URL 也走这里：若存在未保存编辑，先回退 URL 并弹统一确认。
  const editDirty = useWorkspaceStore((s) => s.editDirty);
  const pendingBranchRef = useWorkspaceStore((s) => s.pendingBranchRef);
  const setPendingBranchRef = useWorkspaceStore((s) => s.setPendingBranchRef);
  useEffect(() => {
    if (ir?.projectId !== projectId) return;
    if (urlBranch === branchRef) return;
    if (editDirty && pendingBranchRef !== urlBranch) {
      // 未保存编辑 + 未经确认的 URL 变化：回退到当前分支并等待确认。
      setPendingBranchRef(urlBranch);
      navigate(`?branch=${encodeURIComponent(branchRef)}`, { replace: true });
      return;
    }
    if (pendingBranchRef === urlBranch) {
      setPendingBranchRef(null);
    }
    void switchBranch(urlBranch);
  }, [urlBranch, branchRef, pendingBranchRef, editDirty, projectId, ir?.projectId, switchBranch, setPendingBranchRef, navigate]);

  useEffect(() => {
    if (ir?.projectId !== projectId) return;
    if (!workspacePage) return;
    setActivePage(workspacePage);
  }, [ir?.projectId, projectId, workspacePage, setActivePage]);

  if (!projectId) {
    return <Navigate to="/home" replace />;
  }

  if (ir?.projectId !== projectId) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 bg-slate-50 min-h-screen w-full relative overflow-hidden font-sans">
        {/* Ambient background glow */}
        <div className="absolute -right-24 -top-24 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -left-24 -bottom-24 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="max-w-md w-full bg-white/95 backdrop-blur-md rounded-3xl p-8 border border-slate-200/80 shadow-2xl text-center space-y-6 animate-in zoom-in-95 duration-200 relative z-10">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 border border-indigo-100 shadow-sm">
            <Loader2 className="h-7 w-7 animate-spin text-indigo-600" />
          </div>
          <div className="space-y-2">
            <h3 className="text-base font-black text-slate-900 tracking-tight">{t('shell.loading')}</h3>
            <p className="text-xs text-slate-500 font-medium leading-relaxed">
              {isLoading ? t('shell.loadingProgress') : (error || t('shell.loadingBackup'))}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return <WorkspaceShell />;
}

function WorkspaceShell() {
  const { t } = useTranslation();
  const ir = useWorkspaceStore((s) => s.ir);
  const currentBranch = useWorkspaceStore((s) => s.currentBranch);
  const canWrite = useWorkspaceStore((s) => s.workspaceCanWrite());
  const isProtected = Boolean(currentBranch?.is_protected || currentBranch?.name === 'main');
  const isReadOnly = !canWrite;
  const [showCreateBranch, setShowCreateBranch] = useState(false);
  const navigate = useNavigate();

  if (!ir) {
    return <Navigate to="/home" replace />;
  }

  return (
    <Layout>
      <div className="flex-1 flex flex-col w-full relative min-h-0">
        {isReadOnly && (
          <div className="flex items-center justify-between border-b border-indigo-100 bg-indigo-50/90 px-4 py-2 text-xs text-indigo-900 shadow-xs">
            <div className="flex items-center gap-2">
              <Lock className="h-3.5 w-3.5 text-indigo-600 shrink-0" />
              <span>
                {isProtected
                  ? t('versionControl.protectedBranchBanner', '您正在查看受保护的 main 分支（只读模式）。如需进行结构变更或编辑模型，请从此版本创建新分支。')
                  : t('versionControl.viewerReadOnlyBanner', '您当前对本项目仅具备只读权限，无法执行修改或提交操作。')}
              </span>
            </div>
            {isProtected && (
              <button
                type="button"
                onClick={() => setShowCreateBranch(true)}
                className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-indigo-700 shadow-xs cursor-pointer"
              >
                {t('versionControl.createBranchFromHere', '从此版本创建分支')}
              </button>
            )}
          </div>
        )}
        <div className="flex-1 flex w-full relative min-h-0">
          <Outlet />
          <ScopedAIBar />
        </div>
      </div>
      <CreateBranchDialog
        open={showCreateBranch}
        onClose={() => setShowCreateBranch(false)}
        sourceCommitPublicId={currentBranch?.head_commit_public_id}
        onCreated={(branchPublicId) => {
          if (ir.projectId) {
            navigate(`/projects/${ir.projectId}/overview?branch=${encodeURIComponent(branchPublicId)}`);
          }
        }}
      />
    </Layout>
  );
}

export function GlobalToast() {
  const { t } = useTranslation();
  const message = useWorkspaceStore((s) => s.lastActionMessageToken);
  const messageInterpolation = useWorkspaceStore((s) => s.lastActionMessageTokenInterpolation);
  const error = useWorkspaceStore((s) => s.error);
  const setError = useWorkspaceStore((s) => s.setError);
  const navigate = useNavigate();
  const [visibleMessage, setVisibleMessage] = useState<string | null>(null);
  const [visibleError, setVisibleError] = useState<string | null>(null);
  const [rawError, setRawError] = useState<string | null>(null);

  useEffect(() => {
    if (!message) return;
    setVisibleMessage(resolveLocalizedMessage(t, message, messageInterpolation));
    const timer = window.setTimeout(() => setVisibleMessage(null), 2200);
    return () => window.clearTimeout(timer);
  }, [message, messageInterpolation, t]);

  useEffect(() => {
    if (!error) return;
    setRawError(error);
    const friendly = getFriendlyErrorMessage(error);
    setVisibleError(t(friendly));
    const timer = window.setTimeout(() => {
      setVisibleError(null);
      setRawError(null);
      setError(null);
    }, 6000); // Give users slightly more time to read and click if it is an error
    return () => window.clearTimeout(timer);
  }, [error, setError, t]);

  if (!visibleMessage && !visibleError) return null;

  const isLlmRequired = rawError === 'llm_config_required' || error === 'llm_config_required';

  return (
    <div className="fixed left-1/2 -translate-x-1/2 bottom-6 z-[60] space-y-2 pointer-events-none">
      {visibleError && (
        <div 
          onClick={() => {
            if (isLlmRequired) {
              const projectId = useWorkspaceStore.getState().ir?.projectId;
              navigate(projectId ? `/projects/${projectId}/configuration?tab=llm` : '/settings');
              setError(null);
              setVisibleError(null);
              setRawError(null);
            }
          }}
          className={`pointer-events-auto px-4 py-2.5 rounded-xl border border-rose-200 bg-rose-50 text-rose-700 text-xs font-bold shadow-lg flex items-center gap-2.5 transition-all duration-200 ${
            isLlmRequired 
              ? 'cursor-pointer hover:bg-rose-100 hover:shadow-xl active:scale-[0.99] border-rose-300' 
              : ''
          }`}
        >
          <span>{visibleError}</span>
          {isLlmRequired && (
            <span className="bg-rose-600 hover:bg-rose-700 text-white text-[9px] font-black px-2.5 py-1 rounded-lg uppercase tracking-wider shadow-sm transition-all shrink-0">
              {t('app.goToSettings')}
            </span>
          )}
        </div>
      )}
      {visibleMessage && (
        <div className="pointer-events-none px-4 py-2 rounded-xl border border-slate-200 bg-white text-slate-700 text-xs font-bold shadow-sm">
          {visibleMessage}
        </div>
      )}
    </div>
  );
}

function GlobalTaskStatus() {
  const { t } = useTranslation();
  const isGenerating = useWorkspaceStore((s) => s.isGenerating);
  const isGeneratingChoices = useWorkspaceStore((s) => s.isGeneratingChoices);
  const lastActionMessageToken = useWorkspaceStore((s) => s.lastActionMessageToken);
  const messageInterpolation = useWorkspaceStore((s) => s.lastActionMessageTokenInterpolation);

  if (!isGenerating || isGeneratingChoices) return null;

  const message = lastActionMessageToken
    ? resolveLocalizedMessage(t, lastActionMessageToken, messageInterpolation)
    : t('app.operationPending');
  const title = t(taskStatusTitleKey(lastActionMessageToken));

  return (
    <div className="fixed inset-0 z-[80] bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-6 animate-in fade-in duration-200">
      <div className="w-full max-w-md rounded-3xl border border-slate-200/80 bg-white/95 backdrop-blur-md shadow-2xl p-8 text-center space-y-6 animate-in zoom-in-95 duration-200">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 border border-indigo-100 shadow-sm">
          <Loader2 className="h-7 w-7 animate-spin text-indigo-600" />
        </div>
        <div className="space-y-2">
          <div className="text-xs font-black tracking-[0.2em] text-indigo-600 uppercase font-mono">{title}</div>
          <div className="text-sm font-bold text-slate-900 leading-relaxed">{message}</div>
          <div className="text-xs text-slate-500 font-medium leading-relaxed bg-slate-50 p-3 rounded-2xl border border-slate-100">
            {t('app.autoRefreshNotice')}
          </div>
        </div>
      </div>
    </div>
  );
}

function GlobalGenerationConflictDialog() {
  const { t } = useTranslation();
  const pendingGenerationConflict = useWorkspaceStore((s) => s.pendingGenerationConflict);
  const dismissPendingGenerationConflict = useWorkspaceStore((s) => s.dismissPendingGenerationConflict);
  const confirmPendingGenerationConflict = useWorkspaceStore((s) => s.confirmPendingGenerationConflict);
  const isGeneratingChoices = useWorkspaceStore((s) => s.isGeneratingChoices);

  return (
    <GenerationConflictDialog
      isOpen={!!pendingGenerationConflict}
      generationLabel={pendingGenerationConflict?.existingGroupLabel ? t(pendingGenerationConflict.existingGroupLabel) : t('choiceGroupPreview.candidateFallback')}
      isWorking={isGeneratingChoices}
      onClose={dismissPendingGenerationConflict}
      onConfirm={() => void confirmPendingGenerationConflict()}
    />
  );
}

function StageRouteGuard({ children, stage }: { children: React.ReactNode; stage: 'flow' | 'scope' }) {
  const { t } = useTranslation();
  const ir = useWorkspaceStore((s) => s.ir);
  const navigate = useNavigate();

  const stageProgress = useWorkspaceStore((s) => s.stageProgress);
  const isLoading = useWorkspaceStore((s) => s.isLoading);

  if (!stageProgress) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 bg-slate-50 min-h-[80vh] w-full animate-in fade-in duration-300">
        <div className="max-w-md w-full bg-white rounded-[28px] p-8 border border-slate-200 shadow-xl text-center space-y-4">
          <div className="mx-auto h-8 w-8 rounded-full border-4 border-slate-200 border-t-indigo-500 animate-spin" />
          <p className="text-xs text-slate-500 font-medium">{t('app.loadingStageProgress')}</p>
        </div>
      </div>
    );
  }

  const whatStage = stageProgress.stages.find((s: any) => s.stage === 'what');
  const howStage = stageProgress.stages.find((s: any) => s.stage === 'how');
  const scopeStage = stageProgress.stages.find((s: any) => s.stage === 'scope');

  let isUnlocked = false;
  let prevStage: any = null;
  let prevStageKey: 'what' | 'how' = 'what';
  let prevStageRoute = '/what';
  let targetAction: 'enter_how' | 'enter_scope' = 'enter_how';
  let stageNameLabel = '';

  if (stage === 'flow') {
    isUnlocked = howStage ? howStage.unlocked : false;
    prevStage = whatStage;
    prevStageKey = 'what';
    prevStageRoute = '/what';
    targetAction = 'enter_how';
    stageNameLabel = t('nav.flow');
  } else if (stage === 'scope') {
    isUnlocked = scopeStage ? scopeStage.unlocked : false;
    prevStage = howStage;
    prevStageKey = 'how';
    prevStageRoute = '/flow';
    targetAction = 'enter_scope';
    stageNameLabel = t('nav.scope');
  }

  if (isUnlocked) {
    return <>{children}</>;
  }

  const prevReady = prevStage?.statusCode === 'ready_to_advance';
  const blockReason = getStageCheckMessage(prevStage?.failedChecks?.[0], t) || (
    prevStageKey === 'what'
      ? t('app.blockReasonWhat')
      : t('app.blockReasonHow')
  );

  const handleTransition = () => {
    useWorkspaceStore.getState().requestStageTransition(targetAction, { navigate });
  };

  const handleGoBack = () => {
    const branchRef = useWorkspaceStore.getState().currentBranch?.public_id || useWorkspaceStore.getState().currentBranch?.name;
    navigate(buildProjectRouteWithBranch(ir?.projectId, prevStageRoute as any, branchRef));
  };

  return (
    <div className="flex-1 flex items-center justify-center p-6 bg-slate-50 min-h-[80vh] w-full">
      <div className="max-w-md w-full bg-white rounded-3xl p-8 border border-slate-200 shadow-xl text-center space-y-6 animate-in fade-in duration-300">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-indigo-50 text-indigo-500 text-xl font-bold">
                <Lock className="h-4 w-4" />
        </div>
        <div className="space-y-2">
          <h3 className="text-base font-black text-slate-800 tracking-tight">
            {t('app.stageNotUnlocked', { stage: stageNameLabel })}
          </h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            {t('app.stageLockedDesc')}
          </p>
          <div className="text-left bg-slate-50 p-4 rounded-2xl border border-slate-100 space-y-1">
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">{t('app.blockReasonLabel')}</span>
            <p className="text-xs text-slate-700 leading-relaxed font-medium">
              {blockReason}
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-2 pt-2">
          {prevReady && (
            <button
              onClick={handleTransition}
              disabled={isLoading}
              className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-2xl text-xs font-bold transition-all shadow-sm hover:shadow disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? t('app.submittingUnlock') : t('app.applyUnlock')}
            </button>
          )}
          <button
            onClick={handleGoBack}
            className="w-full py-3 px-4 border border-slate-200 hover:border-slate-300 text-slate-600 rounded-2xl text-xs font-bold transition-all bg-white hover:bg-slate-50"
          >
            {t('app.goBackToReadyStage')}
          </button>
        </div>
      </div>
    </div>
  );
}

export function App() {
  const checkAuth = useAuthStore((s) => s.checkAuth);

  useEffect(() => {
    void checkAuth();
  }, [checkAuth]);

  // 根据 Vite base 自动匹配基准路由路径（去除末尾斜杠）
  const basename = import.meta.env.BASE_URL.replace(/\/$/, '');

  return (
    <BrowserRouter basename={basename}>
      <RouterStateSync />
      <Routes>
        <Route path="/" element={<Navigate to="/home" replace />} />
        
        {/* Guest only routes */}
        <Route path="/login" element={<GuestGuard><LazyRoute><Login /></LazyRoute></GuestGuard>} />
        <Route path="/register" element={<GuestGuard><LazyRoute><Register /></LazyRoute></GuestGuard>} />
        
        {/* Protected routes */}
        <Route path="/home" element={<AuthGuard><LazyRoute><Home /></LazyRoute></AuthGuard>} />
        <Route path="/settings" element={<AuthGuard><LazyRoute><AccountSettings /></LazyRoute></AuthGuard>} />
        <Route path="/onboarding" element={<AuthGuard><LazyRoute><ProjectOnboarding /></LazyRoute></AuthGuard>} />
        
        <Route path="/projects/:projectId" element={<AuthGuard><ProjectRouteBootstrap /></AuthGuard>}>
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<LazyRoute><Overview /></LazyRoute>} />
          <Route path="what" element={<LazyRoute><WhatToDo /></LazyRoute>} />
          <Route
            path="flow"
            element={
              <StageRouteGuard stage="flow">
                <LazyRoute><HowItWorks /></LazyRoute>
              </StageRouteGuard>
            }
          />
          <Route
            path="scope"
            element={
              <StageRouteGuard stage="scope">
                <LazyRoute><ScopeAndDelivery /></LazyRoute>
              </StageRouteGuard>
            }
          />
          <Route path="preview" element={<LazyRoute><Preview /></LazyRoute>} />
          <Route path="repo" element={<LazyRoute><Repository /></LazyRoute>} />
          <Route path="configuration" element={<LazyRoute><ProjectConfiguration /></LazyRoute>} />
        </Route>
        
        
        <Route path="*" element={<Navigate to="/home" replace />} />
      </Routes>
      <GlobalGenerationConflictDialog />
      <GateCheckModal />
      <GlobalTaskStatus />
      <GlobalToast />
      <BranchSwitchConfirmDialog />
    </BrowserRouter>
  );
}
