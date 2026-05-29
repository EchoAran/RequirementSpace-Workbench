import { BrowserRouter, Routes, Route, useLocation, Navigate, useNavigate, Outlet, useParams } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { ScopedAIBar } from './components/shared/ScopedAIBar';
import { Overview } from './pages/Overview';
import { WhatToDo } from './pages/WhatToDo';
import { HowItWorks } from './pages/HowItWorks';
import { ScopeAndDelivery } from './pages/ScopeAndDelivery';
import { Preview } from './pages/Preview';
import { ProjectOnboarding } from './pages/ProjectOnboarding';
import { Home } from './pages/Home';
import { useWorkspaceStore, WorkspacePage } from './store/useWorkspaceStore';
import { useEffect, useState } from 'react';
import { buildProjectRoute, extractWorkspacePage, getGuardRedirect } from './core/selectors';

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
  const numericProjectId = projectId ? Number(projectId) : NaN;
  const workspacePage = extractWorkspacePage(location.pathname);

  useEffect(() => {
    if (!projectId || Number.isNaN(numericProjectId)) return;
    if (ir?.projectId === numericProjectId) return;
    void openWorkspace(projectId);
  }, [projectId, numericProjectId, ir?.projectId, openWorkspace]);

  useEffect(() => {
    if (ir?.projectId !== numericProjectId) return;
    if (!workspacePage) return;
    setActivePage(workspacePage);
  }, [ir?.projectId, numericProjectId, workspacePage, setActivePage]);

  if (!projectId || Number.isNaN(numericProjectId)) {
    return <Navigate to="/home" replace />;
  }

  if (ir?.projectId !== numericProjectId) {
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

function GlobalToast() {
  const message = useWorkspaceStore((s) => s.lastActionMessage);
  const error = useWorkspaceStore((s) => s.error);
  const [visibleMessage, setVisibleMessage] = useState<string | null>(null);
  const [visibleError, setVisibleError] = useState<string | null>(null);

  useEffect(() => {
    if (!message) return;
    setVisibleMessage(message);
    const t = window.setTimeout(() => setVisibleMessage(null), 2200);
    return () => window.clearTimeout(t);
  }, [message]);

  useEffect(() => {
    if (!error) return;
    setVisibleError(error);
    const t = window.setTimeout(() => setVisibleError(null), 4000);
    return () => window.clearTimeout(t);
  }, [error]);

  if (!visibleMessage && !visibleError) return null;

  return (
    <div className="fixed left-1/2 -translate-x-1/2 bottom-6 z-[60] space-y-2 pointer-events-none">
      {visibleError && (
        <div className="pointer-events-none px-4 py-2 rounded-xl border border-rose-200 bg-rose-50 text-rose-700 text-xs font-bold shadow-sm">
          {visibleError}
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
  const lastActionMessage = useWorkspaceStore((s) => s.lastActionMessage);

  if (!isGenerating) return null;

  const message = lastActionMessage || 'AI 正在执行任务，请稍候...';

  return (
    <div className="fixed inset-0 z-[80] bg-slate-950/35 backdrop-blur-sm flex items-center justify-center p-6">
      <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white/95 shadow-2xl p-8 text-center space-y-5">
        <div className="mx-auto relative flex h-16 w-16 items-center justify-center">
          <div className="h-16 w-16 rounded-full border-4 border-indigo-100 border-t-indigo-600 animate-spin" />
        </div>
        <div className="space-y-2">
          <div className="text-xs font-black tracking-[0.2em] text-indigo-600">AI 任务执行中</div>
          <div className="text-sm font-bold text-slate-900 leading-relaxed">{message}</div>
          <div className="text-xs text-slate-500 leading-relaxed">
            页面会在任务完成后自动刷新当前结果，您无需重复点击按钮。
          </div>
        </div>
      </div>
    </div>
  );
}

function StageRouteGuard({ children, stage }: { children: React.ReactNode; stage: 'flow' | 'scope' }) {
  const ir = useWorkspaceStore((s) => s.ir);
  const setError = useWorkspaceStore((s) => s.setError);
  const navigate = useNavigate();

  const path = stage === 'flow' ? '/flow' : '/scope';
  const redirect = getGuardRedirect(path, ir);

  useEffect(() => {
    if (redirect) {
      setError(redirect.errorToast);
      navigate(buildProjectRoute(ir?.projectId, redirect.targetRoute as WorkspacePage), { replace: true });
    }
  }, [redirect, setError, navigate, ir?.projectId]);

  if (redirect) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 bg-slate-50 min-h-[80vh] w-full">
        <div className="max-w-md w-full bg-white rounded-3xl p-8 border border-slate-200 shadow-xl text-center space-y-5 animate-in fade-in duration-300">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-rose-50 text-rose-500 text-xl font-bold animate-pulse">
            ⚠️
          </div>
          <div className="space-y-2">
            <h3 className="text-sm font-black text-slate-800 tracking-tight">页面阶段尚未解锁</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              您访问的阶段由于前置建模依赖未完成，目前仍处于锁定状态。
            </p>
            <p className="text-[10px] text-slate-400 font-bold leading-normal bg-slate-50 p-2.5 rounded-xl border border-slate-100">
              系统正在自动为您返回上一就绪阶段，请稍候...
            </p>
          </div>
          <div className="pt-2">
            <div className="mx-auto h-4 w-4 rounded-full border-2 border-slate-200 border-t-rose-500 animate-spin" />
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

export function App() {
  return (
    <BrowserRouter>
      <RouterStateSync />
      <Routes>
        <Route path="/" element={<Navigate to="/home" replace />} />
        <Route path="/home" element={<Home />} />
        <Route path="/onboarding" element={<ProjectOnboarding />} />
        <Route path="/projects/:projectId" element={<ProjectRouteBootstrap />}>
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<Overview />} />
          <Route path="what" element={<WhatToDo />} />
          <Route
            path="flow"
            element={
              <StageRouteGuard stage="flow">
                <HowItWorks />
              </StageRouteGuard>
            }
          />
          <Route
            path="scope"
            element={
              <StageRouteGuard stage="scope">
                <ScopeAndDelivery />
              </StageRouteGuard>
            }
          />
          <Route path="preview" element={<Preview />} />
        </Route>
        <Route path="/overview" element={<LegacyWorkspaceRedirect page="/overview" />} />
        <Route path="/what" element={<LegacyWorkspaceRedirect page="/what" />} />
        <Route path="/flow" element={<LegacyWorkspaceRedirect page="/flow" />} />
        <Route path="/scope" element={<LegacyWorkspaceRedirect page="/scope" />} />
        <Route path="/preview" element={<LegacyWorkspaceRedirect page="/preview" />} />
        <Route path="*" element={<Navigate to="/home" replace />} />
      </Routes>
      <GlobalTaskStatus />
      <GlobalToast />
    </BrowserRouter>
  );
}
