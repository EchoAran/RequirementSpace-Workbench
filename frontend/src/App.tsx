import { BrowserRouter, Routes, Route, useLocation, Navigate, useNavigate, Outlet, useParams } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { ScopedAIBar } from './components/shared/ScopedAIBar';
import { GenerationConflictDialog } from './components/shared/GenerationConflictDialog';
import GateCheckModal from './components/shared/GateCheckModal';
import { useWorkspaceStore, WorkspacePage, getFriendlyErrorMessage } from './store/useWorkspaceStore';
import { Suspense, lazy, useEffect, useState } from 'react';
import { buildProjectRoute, extractWorkspacePage, getGuardRedirect } from './core/selectors';
import { useAuthStore } from './store/useAuthStore';
import { AuthGuard } from './components/auth/AuthGuard';
import { GuestGuard } from './components/auth/GuestGuard';

const Overview = lazy(() => import('./pages/Overview').then((module) => ({ default: module.Overview })));
const WhatToDo = lazy(() => import('./pages/WhatToDo').then((module) => ({ default: module.WhatToDo })));
const HowItWorks = lazy(() => import('./pages/HowItWorks').then((module) => ({ default: module.HowItWorks })));
const ScopeAndDelivery = lazy(() => import('./pages/ScopeAndDelivery').then((module) => ({ default: module.ScopeAndDelivery })));
const Preview = lazy(() => import('./pages/Preview').then((module) => ({ default: module.Preview })));
const ProjectOnboarding = lazy(() => import('./pages/ProjectOnboarding').then((module) => ({ default: module.ProjectOnboarding })));
const Home = lazy(() => import('./pages/Home').then((module) => ({ default: module.Home })));
const Login = lazy(() => import('./pages/Login').then((module) => ({ default: module.Login })));
const Register = lazy(() => import('./pages/Register').then((module) => ({ default: module.Register })));
const AccountSettings = lazy(() => import('./pages/AccountSettings').then((module) => ({ default: module.AccountSettings })));
const ProjectConfiguration = lazy(() => import('./pages/ProjectConfiguration').then((module) => ({ default: module.ProjectConfiguration })));

function RouteFallback() {
  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-slate-50 p-6">
      <div className="h-10 w-10 rounded-full border-4 border-slate-100 border-t-indigo-600 animate-spin" />
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
  const { projectId } = useParams();
  const location = useLocation();
  const openWorkspace = useWorkspaceStore((s) => s.openWorkspace);
  const ir = useWorkspaceStore((s) => s.ir);
  const isLoading = useWorkspaceStore((s) => s.isLoading);
  const error = useWorkspaceStore((s) => s.error);
  const setActivePage = useWorkspaceStore((s) => s.setActivePage);
  const workspacePage = extractWorkspacePage(location.pathname);

  useEffect(() => {
    if (!projectId) return;
    if (ir?.projectId === projectId) return;
    void openWorkspace(projectId);
  }, [projectId, ir?.projectId, openWorkspace]);

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
      <div className="flex-1 flex items-center justify-center p-6 bg-slate-50 min-h-screen w-full">
        <div className="max-w-md w-full bg-white rounded-3xl p-8 border border-slate-200 shadow-xl text-center space-y-5">
          <div className="mx-auto h-10 w-10 rounded-full border-4 border-slate-100 border-t-indigo-600 animate-spin" />
          <div className="space-y-2">
            <h3 className="text-sm font-black text-slate-800 tracking-tight">正在载入项目工作区</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              {isLoading ? '正在根据地址恢复项目上下文，请稍候...' : (error || '正在准备项目数据...')}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return <WorkspaceShell />;
}

function WorkspaceShell() {
  const ir = useWorkspaceStore((s) => s.ir);

  if (!ir) {
    return <Navigate to="/home" replace />;
  }

  return (
    <Layout>
      <div className="flex-1 flex w-full relative">
        <Outlet />
        <ScopedAIBar />
      </div>
    </Layout>
  );
}

function LegacyWorkspaceRedirect({ page }: { page: WorkspacePage }) {
  const ir = useWorkspaceStore((s) => s.ir);

  if (!ir?.projectId) {
    return <Navigate to="/home" replace />;
  }

  return <Navigate to={buildProjectRoute(ir.projectId, page)} replace />;
}

function LegacyProjectKnowledgeRedirect() {
  const { projectId } = useParams();
  if (!projectId) {
    return <Navigate to="/home" replace />;
  }
  return <Navigate to={`/projects/${projectId}/configuration?tab=knowledge`} replace />;
}

export function GlobalToast() {
  const message = useWorkspaceStore((s) => s.lastActionMessage);
  const error = useWorkspaceStore((s) => s.error);
  const setError = useWorkspaceStore((s) => s.setError);
  const navigate = useNavigate();
  const [visibleMessage, setVisibleMessage] = useState<string | null>(null);
  const [visibleError, setVisibleError] = useState<string | null>(null);
  const [rawError, setRawError] = useState<string | null>(null);

  useEffect(() => {
    if (!message) return;
    setVisibleMessage(message);
    const t = window.setTimeout(() => setVisibleMessage(null), 2200);
    return () => window.clearTimeout(t);
  }, [message]);

  useEffect(() => {
    if (!error) return;
    setRawError(error);
    const friendly = getFriendlyErrorMessage(error);
    setVisibleError(friendly);
    const t = window.setTimeout(() => {
      setVisibleError(null);
      setRawError(null);
      setError(null);
    }, 6000); // Give users slightly more time to read and click if it is an error
    return () => window.clearTimeout(t);
  }, [error, setError]);

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
              前往设置
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
  const isGenerating = useWorkspaceStore((s) => s.isGenerating);
  const isGeneratingChoices = useWorkspaceStore((s) => s.isGeneratingChoices);
  const lastActionMessage = useWorkspaceStore((s) => s.lastActionMessage);

  if (!isGenerating || isGeneratingChoices) return null;

  const message = lastActionMessage || '正在执行操作，请稍候...';

  let title = '任务执行中';
  if (message.includes('生成') && message.includes('草稿')) {
    title = '正在生成草稿';
  } else if (message.includes('诊断') || message.includes('分析') || message.includes('重新诊断')) {
    title = '正在重新诊断';
  } else if (message.includes('修复') || message.includes('AI 正在生成修复')) {
    title = 'AI 正在生成修复方案';
  } else if (message.includes('AI') || message.includes('智能') || message.includes('推演')) {
    title = 'AI 任务执行中';
  }

  return (
    <div className="fixed inset-0 z-[80] bg-slate-950/35 backdrop-blur-sm flex items-center justify-center p-6">
      <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white/95 shadow-2xl p-8 text-center space-y-5">
        <div className="mx-auto relative flex h-16 w-16 items-center justify-center">
          <div className="h-16 w-16 rounded-full border-4 border-indigo-100 border-t-indigo-600 animate-spin" />
        </div>
        <div className="space-y-2">
          <div className="text-xs font-black tracking-[0.2em] text-indigo-600">{title}</div>
          <div className="text-sm font-bold text-slate-900 leading-relaxed">{message}</div>
          <div className="text-xs text-slate-500 leading-relaxed">
            页面会在任务完成后自动刷新当前结果，您无需重复点击按钮。
          </div>
        </div>
      </div>
    </div>
  );
}

function GlobalGenerationConflictDialog() {
  const pendingGenerationConflict = useWorkspaceStore((s) => s.pendingGenerationConflict);
  const dismissPendingGenerationConflict = useWorkspaceStore((s) => s.dismissPendingGenerationConflict);
  const confirmPendingGenerationConflict = useWorkspaceStore((s) => s.confirmPendingGenerationConflict);
  const isGeneratingChoices = useWorkspaceStore((s) => s.isGeneratingChoices);

  return (
    <GenerationConflictDialog
      isOpen={!!pendingGenerationConflict}
      generationLabel={pendingGenerationConflict?.existingGroupLabel || '候选'}
      isWorking={isGeneratingChoices}
      onClose={dismissPendingGenerationConflict}
      onConfirm={() => void confirmPendingGenerationConflict()}
    />
  );
}

function StageRouteGuard({ children, stage }: { children: React.ReactNode; stage: 'flow' | 'scope' }) {
  const ir = useWorkspaceStore((s) => s.ir);
  const setError = useWorkspaceStore((s) => s.setError);
  const gateFindings = useWorkspaceStore((s) => s.findingsByView.gate || []);
  const snoozedGateFindingIds = useWorkspaceStore((s) => s.snoozedGateFindingIds || {});
  const navigate = useNavigate();

  const projectId = ir?.projectId;
  const path = stage === 'flow' ? '/flow' : '/scope';
  const action = stage === 'flow' ? 'enter_how' : 'enter_scope';

  const getGateFindingContextHash = (finding: any): string => {
    if (!finding || !finding.metadata) return '';
    if (finding.metadata.missing_pairs) {
      const pairs = [...finding.metadata.missing_pairs];
      pairs.sort((a: any, b: any) => {
        const keyA = `${a.feature_id}:${a.actor_id}`;
        const keyB = `${b.feature_id}:${b.actor_id}`;
        return keyA.localeCompare(keyB);
      });
      return JSON.stringify(pairs);
    }
    if (finding.metadata.missing_features) {
      const features = [...finding.metadata.missing_features];
      features.sort((a: any, b: any) => (a.feature_id || 0) - (b.feature_id || 0));
      return JSON.stringify(features);
    }
    return '';
  };

  const activeBlockingGates = projectId
    ? gateFindings.filter((finding) => {
        let isBlocking = false;
        if (action === "enter_how") {
          isBlocking = (finding.stage === "what" && finding.blockingScope === "stage_transition");
        } else if (action === "enter_scope") {
          isBlocking = (finding.stage === "how" && finding.blockingScope === "stage_transition");
        }
        if (!isBlocking) return false;

        const key = `${projectId}:${action}:${finding.findingId}`;
        const storedHash = snoozedGateFindingIds[key];
        if (!storedHash) return true;
        return storedHash !== getGateFindingContextHash(finding);
      })
    : [];

  const stageProgress = useWorkspaceStore((s) => s.stageProgress);
  const isLoading = useWorkspaceStore((s) => s.isLoading);

  if (!stageProgress) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 bg-slate-50 min-h-[80vh] w-full animate-in fade-in duration-300">
        <div className="max-w-md w-full bg-white rounded-[28px] p-8 border border-slate-200 shadow-xl text-center space-y-4">
          <div className="mx-auto h-8 w-8 rounded-full border-4 border-slate-200 border-t-indigo-500 animate-spin" />
          <p className="text-xs text-slate-500 font-medium">正在加载阶段状态，请稍候...</p>
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
    stageNameLabel = '怎么运作 (How)';
  } else if (stage === 'scope') {
    isUnlocked = scopeStage ? scopeStage.unlocked : false;
    prevStage = howStage;
    prevStageKey = 'how';
    prevStageRoute = '/flow';
    targetAction = 'enter_scope';
    stageNameLabel = '范围与交付 (Scope)';
  }

  if (isUnlocked) {
    return <>{children}</>;
  }

  const prevReady = prevStage?.statusCode === 'ready_to_advance';
  const blockReason = prevStage?.failedChecks?.[0]?.message || (
    prevStageKey === 'what' 
      ? '需先补齐 What 阶段的所有核心建模规则' 
      : '需先补齐 How 阶段的核心规则'
  );

  const handleTransition = () => {
    useWorkspaceStore.getState().requestStageTransition(targetAction, { navigate });
  };

  const handleGoBack = () => {
    navigate(buildProjectRoute(ir?.projectId, prevStageRoute as any));
  };

  return (
    <div className="flex-1 flex items-center justify-center p-6 bg-slate-50 min-h-[80vh] w-full">
      <div className="max-w-md w-full bg-white rounded-3xl p-8 border border-slate-200 shadow-xl text-center space-y-6 animate-in fade-in duration-300">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-indigo-50 text-indigo-500 text-xl font-bold">
          🔒
        </div>
        <div className="space-y-2">
          <h3 className="text-base font-black text-slate-800 tracking-tight">{stageNameLabel} 阶段尚未解锁</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            您访问的阶段由于前置建模依赖未完成，目前仍处于锁定状态。
          </p>
          <div className="text-left bg-slate-50 p-4 rounded-2xl border border-slate-100 space-y-1">
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">阻碍进入原因：</span>
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
              {isLoading ? '正在提交解锁...' : '申请解锁并进入该阶段'}
            </button>
          )}
          <button
            onClick={handleGoBack}
            className="w-full py-3 px-4 border border-slate-200 hover:border-slate-300 text-slate-600 rounded-2xl text-xs font-bold transition-all bg-white hover:bg-slate-50"
          >
            返回上一就绪阶段
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
          <Route path="knowledge" element={<LegacyProjectKnowledgeRedirect />} />
          <Route path="configuration" element={<LazyRoute><ProjectConfiguration /></LazyRoute>} />
        </Route>
        
        {/* Legacy redirects wrapped in AuthGuard */}
        <Route path="/overview" element={<AuthGuard><LegacyWorkspaceRedirect page="/overview" /></AuthGuard>} />
        <Route path="/knowledge" element={<AuthGuard><LegacyWorkspaceRedirect page="/knowledge" /></AuthGuard>} />
        <Route path="/what" element={<AuthGuard><LegacyWorkspaceRedirect page="/what" /></AuthGuard>} />
        <Route path="/flow" element={<AuthGuard><LegacyWorkspaceRedirect page="/flow" /></AuthGuard>} />
        <Route path="/scope" element={<AuthGuard><LegacyWorkspaceRedirect page="/scope" /></AuthGuard>} />
        <Route path="/preview" element={<AuthGuard><LegacyWorkspaceRedirect page="/preview" /></AuthGuard>} />
        
        <Route path="*" element={<Navigate to="/home" replace />} />
      </Routes>
      <GlobalGenerationConflictDialog />
      <GateCheckModal />
      <GlobalTaskStatus />
      <GlobalToast />
    </BrowserRouter>
  );
}
