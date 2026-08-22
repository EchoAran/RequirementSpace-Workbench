import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';
import { useTranslation } from 'react-i18next';
import { Loader2 } from 'lucide-react';

interface GuestGuardProps {
  children: React.ReactNode;
}

export function GuestGuard({ children }: GuestGuardProps) {
  const { t } = useTranslation();
  const { isAuthenticated, isInitializing } = useAuthStore();

  if (isInitializing) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-slate-50 p-6 relative overflow-hidden font-sans">
        {/* Ambient background glow */}
        <div className="absolute -right-24 -top-24 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -left-24 -bottom-24 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="max-w-md w-full bg-white/95 backdrop-blur-md rounded-3xl p-8 border border-slate-200/80 shadow-2xl text-center space-y-6 animate-in fade-in zoom-in-95 duration-200 relative z-10">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 border border-indigo-100 shadow-sm">
            <Loader2 className="h-7 w-7 animate-spin text-indigo-600" />
          </div>
          <div className="space-y-2">
            <h3 className="text-base font-black text-slate-900 tracking-tight">{t('auth.guard.loadingSession')}</h3>
            <p className="text-xs text-slate-500 font-medium leading-relaxed">
              {t('auth.guard.loadingSessionGuestDesc')}
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/home" replace />;
  }

  return <>{children}</>;
}

