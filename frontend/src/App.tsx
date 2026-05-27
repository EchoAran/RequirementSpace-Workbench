import { BrowserRouter, Routes, Route, useLocation, Navigate } from 'react-router-dom';
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

function RouterStateSync() {
  const location = useLocation();
  const setActivePage = useWorkspaceStore(state => state.setActivePage);

  useEffect(() => {
    setActivePage(location.pathname as WorkspacePage);
  }, [location.pathname, setActivePage]);

  return null;
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
  const isLoading = useWorkspaceStore((s) => s.isLoading);
  const lastActionMessage = useWorkspaceStore((s) => s.lastActionMessage);

  if (!isGenerating && !isLoading) return null;

  const message = lastActionMessage || (isGenerating ? 'AI 正在执行任务，请稍候...' : '任务正在处理中，请稍候...');

  return (
    <>
      {isGenerating && (
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
      )}

      {!isGenerating && isLoading && (
        <div className="fixed top-4 right-4 z-[75] max-w-sm rounded-2xl border border-slate-200 bg-white/95 shadow-xl px-4 py-3 flex items-start gap-3">
          <div className="mt-0.5 h-5 w-5 rounded-full border-2 border-slate-200 border-t-indigo-600 animate-spin shrink-0" />
          <div className="min-w-0">
            <div className="text-[10px] font-black tracking-[0.2em] text-slate-500">任务处理中</div>
            <div className="text-xs font-bold text-slate-800 leading-relaxed break-words">{message}</div>
          </div>
        </div>
      )}
    </>
  );
}

export function App() {
  const { currentSystemView } = useWorkspaceStore();

  if (currentSystemView === 'home') return <Home />;
  if (currentSystemView === 'onboarding') return <ProjectOnboarding />;

  return (
    <BrowserRouter>
      <RouterStateSync />
      <Layout>
        <div className="flex-1 flex w-full relative">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/what" element={<WhatToDo />} />
            <Route path="/flow" element={<HowItWorks />} />
            <Route path="/scope" element={<ScopeAndDelivery />} />
            <Route path="/preview" element={<Preview />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <ScopedAIBar />
        </div>
      </Layout>
      <GlobalTaskStatus />
      <GlobalToast />
    </BrowserRouter>
  );
}
