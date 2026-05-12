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
import { useEffect } from 'react';

function RouterStateSync() {
  const location = useLocation();
  const setActivePage = useWorkspaceStore(state => state.setActivePage);

  useEffect(() => {
    setActivePage(location.pathname as WorkspacePage);
  }, [location.pathname, setActivePage]);

  return null;
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
    </BrowserRouter>
  );
}
