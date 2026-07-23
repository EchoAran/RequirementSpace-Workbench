import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { Mail, Lock, Key, ArrowRight, ShieldAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export function Register() {
  const { t } = useTranslation();
  const register = useAuthStore(state => state.register);
  const error = useAuthStore(state => state.error);
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [showInviteField, setShowInviteField] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    const emailTrim = email.trim();
    if (!emailTrim || !password || !confirmPassword) {
      setValidationError(t('auth.register.fieldsRequired'));
      return;
    }

    if (password.length < 8) {
      setValidationError(t('auth.register.passwordLength'));
      return;
    }

    if (password !== confirmPassword) {
      setValidationError(t('auth.register.passwordsMismatch'));
      return;
    }

    setIsSubmitting(true);
    try {
      await register({
        email: emailTrim,
        password,
        invite_code: showInviteField && inviteCode.trim() ? inviteCode.trim() : undefined,
      });
      navigate('/home');
    } catch (err: any) {
      // Error is caught and set in store
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
      <div className="max-w-md w-full bg-white border border-slate-200/60 rounded-3xl p-8 shadow-2xl relative z-10 space-y-7 backdrop-blur-md bg-white/95">
        {/* Header/Logo */}
        <div className="text-center space-y-3">
          <div className="mx-auto w-12 h-12 bg-indigo-50 border border-indigo-100 rounded-2xl flex items-center justify-center shadow-sm">
            <img src={`${import.meta.env.BASE_URL}plume-gradient.svg`} alt="Plume" className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h1 className="text-2xl font-black bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 bg-clip-text text-transparent tracking-tight">
              {t('auth.register.title')}
            </h1>
            <p className="text-xs text-slate-500 font-medium leading-relaxed">
              {t('auth.register.subtitle')}
            </p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {currentError && (
            <div className="text-xs font-bold text-rose-600 bg-rose-50 border border-rose-100 rounded-xl p-3 shadow-inner">
              {currentError === 'email_already_registered' ? t('auth.register.emailAlreadyRegistered') :
               currentError === 'invalid_invite_code' ? t('auth.register.invalidInviteCode') :
               currentError === 'register_failed' ? t('auth.register.registerFailed') : currentError}
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">
              {t('auth.register.emailLabel')} <span className="text-rose-500">*</span>
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
              {t('auth.register.passwordLabel')} <span className="text-rose-500">*</span> {t('auth.register.passwordRule')}
            </label>
            <div className="relative">
              <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="password"
                placeholder={t('auth.register.passwordPlaceholder')}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isSubmitting}
                className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800 font-bold transition-all"
                required
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">
              {t('auth.register.confirmPasswordLabel')} <span className="text-rose-500">*</span>
            </label>
            <div className="relative">
              <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="password"
                placeholder={t('auth.register.confirmPasswordPlaceholder')}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={isSubmitting}
                className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800 font-bold transition-all"
                required
              />
            </div>
          </div>

          {/* Toggle admin invitation code */}
          <div className="pt-2">
            <button
              type="button"
              onClick={() => {
                setShowInviteField(!showInviteField);
                setInviteCode('');
              }}
              disabled={isSubmitting}
              className="inline-flex items-center gap-1.5 text-xs text-indigo-600 font-bold hover:text-indigo-700 hover:underline transition-all cursor-pointer"
            >
              <Key className="w-3.5 h-3.5" />
              {showInviteField ? t('auth.register.userRegister') : t('auth.register.inviteCodeRegister')}
            </button>
          </div>

          {showInviteField && (
            <div className="space-y-1.5 animate-in slide-in-from-top-2 duration-200">
              <div className="flex items-center gap-1.5 text-[10px] font-black text-slate-400 uppercase tracking-widest">
                <span>{t('auth.register.inviteCodeLabel')}</span>
                <span className="text-rose-500">*</span>
                <span className="normal-case font-medium text-slate-400 flex items-center gap-1 ml-auto">
                  <ShieldAlert className="w-3 h-3 text-indigo-500" />
                  {t('auth.register.inviteCodeNotice')}
                </span>
              </div>
              <div className="relative">
                <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder={t('auth.register.inviteCodePlaceholder')}
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value)}
                  disabled={isSubmitting}
                  className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800 font-bold transition-all"
                  required={showInviteField}
                />
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-3 bg-indigo-600 text-white text-xs font-bold rounded-xl hover:bg-indigo-700 active:scale-[0.99] disabled:opacity-75 disabled:pointer-events-none transition-all flex items-center justify-center gap-1.5 shadow-md shadow-indigo-600/10 mt-2 cursor-pointer"
          >
            {isSubmitting ? (
              <span className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
            ) : (
              <>
                {t('auth.register.submit')}
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </form>

        {/* Footer */}
        <div className="border-t border-slate-100 pt-6 text-center">
          <p className="text-xs text-slate-500 font-medium">
            {t('auth.register.hasAccount')}{' '}
            <Link
              to="/login"
              className="text-indigo-600 font-bold hover:text-indigo-700 hover:underline transition-colors"
            >
              {t('auth.register.loginLink')}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
export default Register;
