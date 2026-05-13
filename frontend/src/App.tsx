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
      <GlobalToast />
    </BrowserRouter>
  );
}
