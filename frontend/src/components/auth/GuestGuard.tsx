import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';
import { useTranslation } from 'react-i18next';

interface GuestGuardProps {
  children: React.ReactNode;
}

export function GuestGuard({ children }: GuestGuardProps) {
  const { t } = useTranslation();
  const { isAuthenticated, isInitializing } = useAuthStore();

  if (isInitializing) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-slate-50/50 dark:bg-slate-900/50 backdrop-blur-md">
        <div className="max-w-md w-full mx-4 bg-white/80 dark:bg-slate-800/80 rounded-3xl p-8 border border-slate-200/50 dark:border-slate-700/50 shadow-2xl text-center space-y-6">
          <div className="relative mx-auto h-12 w-12">
            <div className="absolute inset-0 rounded-full border-4 border-slate-100 dark:border-slate-800" />
            <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-indigo-600 dark:border-t-indigo-400 animate-spin" />
          </div>
          <div className="space-y-2">
            <h3 className="text-sm font-black text-slate-800 dark:text-slate-200 tracking-tight">{t('auth.guard.loadingSession')}</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
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
export default GuestGuard;
