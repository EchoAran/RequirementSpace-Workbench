import { useState } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { Mail, Lock, ArrowRight, Sparkles } from 'lucide-react';

export function Login() {
  const login = useAuthStore(state => state.login);
  const error = useAuthStore(state => state.error);
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    const emailTrim = email.trim();
    if (!emailTrim || !password) {
      setValidationError('邮箱和密码不能为空');
      return;
    }

    if (password.length < 8) {
      setValidationError('密码长度至少为 8 位');
      return;
    }

    setIsSubmitting(true);
    try {
      await login({ email: emailTrim, password });
      const from = (location.state as any)?.from?.pathname || '/home';
      navigate(from, { replace: true });
    } catch (err: any) {
      // Error handled by store
    } finally {
      setIsSubmitting(false);
    }
  };

  const currentError = validationError || error;

  return (
    <div className="min-h-screen w-full bg-slate-50 flex flex-col font-sans selection:bg-indigo-100 relative overflow-hidden items-center justify-center p-4">
      {/* Ambient background glow */}
      <div className="absolute -right-24 -top-24 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl" />
      <div className="absolute -left-24 -bottom-24 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl" />

      {/* Main card */}
      <div className="max-w-md w-full bg-white border border-slate-200/60 rounded-3xl p-8 shadow-2xl relative z-10 space-y-8 backdrop-blur-md bg-white/95">
        {/* Header/Logo */}
        <div className="text-center space-y-3">
          <div className="mx-auto w-12 h-12 bg-indigo-50 border border-indigo-100 rounded-2xl flex items-center justify-center shadow-sm">
            <img src="/plume-gradient.svg" alt="Plume" className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h1 className="text-2xl font-black bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 bg-clip-text text-transparent tracking-tight">
              登录需求空间工作台
            </h1>
            <p className="text-xs text-slate-500 font-medium leading-relaxed">
              探索 AI 驱动的无缝产品需求生命周期管理
            </p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          {currentError && (
            <div className="text-xs font-bold text-rose-600 bg-rose-50 border border-rose-100 rounded-xl p-3 shadow-inner">
              {currentError === 'invalid_credentials' ? '邮箱或密码错误，请重新输入' : 
               currentError === 'account_disabled' ? '账户已被停用，请联系管理员' : currentError}
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">
              电子邮箱
            </label>
            <div className="relative">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="email"
                placeholder="name@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isSubmitting}
                className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800 font-bold transition-all"
                required
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">
              安全密码
            </label>
            <div className="relative">
              <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="password"
                placeholder="请输入密码"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isSubmitting}
                className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800 font-bold transition-all"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-3 bg-indigo-600 text-white text-xs font-bold rounded-xl hover:bg-indigo-700 active:scale-[0.99] disabled:opacity-75 disabled:pointer-events-none transition-all flex items-center justify-center gap-1.5 shadow-md shadow-indigo-600/10 cursor-pointer"
          >
            {isSubmitting ? (
              <span className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
            ) : (
              <>
                进入工作区
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </form>

        {/* Footer */}
        <div className="border-t border-slate-100 pt-6 text-center">
          <p className="text-xs text-slate-500 font-medium">
            还没有账户？{' '}
            <Link
              to="/register"
              className="text-indigo-600 font-bold hover:text-indigo-700 hover:underline transition-colors"
            >
              免费注册
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
export default Login;
