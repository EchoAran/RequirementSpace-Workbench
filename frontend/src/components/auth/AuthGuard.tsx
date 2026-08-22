import React, { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';
import { useTranslation } from 'react-i18next';
import { WifiOff, RefreshCw, Loader2, LogIn, AlertCircle } from 'lucide-react';

interface AuthGuardProps {
  children: React.ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const { t } = useTranslation();
  const { isAuthenticated, isInitializing, sessionUnavailable, checkAuth, clearAuth } = useAuthStore();
  const location = useLocation();
  const navigate = useNavigate();
  const [isRetrying, setIsRetrying] = useState(false);

  const handleRetry = async () => {
    setIsRetrying(true);
    try {
      await checkAuth();
    } finally {
      setIsRetrying(false);
    }
  };

  const handleClearAndGoLogin = () => {
    clearAuth();
    navigate('/login', { replace: true });
  };

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
              {t('auth.guard.loadingSessionDesc')}
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (sessionUnavailable) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-slate-50 p-6 relative overflow-hidden font-sans">
        {/* Ambient background glow */}
        <div className="absolute -right-24 -top-24 w-96 h-96 bg-rose-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -left-24 -bottom-24 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="max-w-lg w-full bg-white border border-slate-200/80 rounded-3xl shadow-2xl overflow-hidden relative z-10 animate-in fade-in zoom-in-95 duration-200">
          {/* Header */}
          <div className="border-b border-slate-100 bg-gradient-to-r from-rose-50/80 via-amber-50/40 to-slate-50/50 p-6 flex items-start gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-rose-100 text-rose-600 border border-rose-200/60 shadow-sm shrink-0">
              <WifiOff className="h-6 w-6" />
            </div>
            <div className="space-y-1 text-left">
              <h3 className="text-base font-black text-slate-900 tracking-tight">
                {t('versionControl.sessionUnavailableTitle', '无法连接到服务器')}
              </h3>
              <p className="text-xs text-slate-500 font-medium leading-relaxed">
                {t('versionControl.sessionUnavailableDesc', '网络连接异常或服务暂不可用，我们已为您保留当前会话状态。')}
              </p>
            </div>
          </div>

          {/* Content */}
          <div className="p-6 space-y-4 text-left">
            <div className="rounded-2xl border border-rose-100 bg-rose-50/70 p-4 space-y-1.5">
              <div className="flex items-center gap-2 text-xs font-bold text-rose-800">
                <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
                <span>{t('auth.guard.connectionDiagnoseTitle', '服务未响应或已断开')}</span>
              </div>
              <p className="text-xs text-rose-700/90 leading-relaxed font-medium pl-6">
                {t('auth.guard.connectionDiagnoseDesc', '前端无法与后端 API 建立通信，可能由于后端服务未启动或网络环境受阻。')}
              </p>
            </div>

            <div className="rounded-2xl border border-slate-100 bg-slate-50/80 p-4 text-xs text-slate-500 font-medium space-y-2">
              <div className="font-bold text-slate-700">{t('auth.guard.troubleshootTitle', '排查建议：')}</div>
              <ul className="space-y-1 text-[11px] text-slate-500 list-disc list-inside">
                <li>{t('auth.guard.troubleshootBackend', '确认后端服务（uvicorn / FastAPI）是否已正常启动')}</li>
                <li>{t('auth.guard.troubleshootPort', '检查 Vite 反向代理或后端监听端口（默认 8000）是否正确')}</li>
                <li>{t('auth.guard.troubleshootNetwork', '检查本地网络连接、代理或防火墙配置')}</li>
              </ul>
            </div>
          </div>

          {/* Actions Footer */}
          <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/60 p-6">
            <button
              type="button"
              onClick={handleClearAndGoLogin}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-600 shadow-xs hover:bg-slate-50 transition-all cursor-pointer"
            >
              <LogIn className="h-3.5 w-3.5" />
              <span>{t('auth.guard.backToLogin', '返回登录')}</span>
            </button>
            <button
              type="button"
              onClick={handleRetry}
              disabled={isRetrying}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-bold text-white shadow-md hover:bg-indigo-700 active:scale-95 transition-all cursor-pointer disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isRetrying ? 'animate-spin' : ''}`} />
              <span>{isRetrying ? t('auth.guard.retrying', '正在重试...') : t('versionControl.retryConnect', '重试连接')}</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

