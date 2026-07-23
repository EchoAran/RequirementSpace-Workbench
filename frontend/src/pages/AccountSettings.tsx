import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { accountApi, LLMConfigResponse } from '../lib/accountApi';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { workspaceApi } from '../lib/api';
import { authApi } from '../lib/authApi';
import { useTranslation } from 'react-i18next';
import { applyUiLocale, normalizeUiLocale, type UiLocale } from '../i18n';
import {
  ArrowLeft,
  User,
  Cpu,
  CheckCircle,
  XCircle,
  Trash2,
  Edit,
  Shield,
  Activity,
  Save,
  Globe,
  Key,
  Languages
} from 'lucide-react';

export function AccountSettings() {
  const user = useAuthStore(state => state.user);
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [config, setConfig] = useState<LLMConfigResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);

  // Form states
  const [apiUrl, setApiUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [modelName, setModelName] = useState('');

  // Test states
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const ir = useWorkspaceStore(state => state.ir);
  const workspaces = useWorkspaceStore(state => state.workspaces);
  const loadWorkspaces = useWorkspaceStore(state => state.loadWorkspaces);
  const projectId = ir?.projectId;
  const projectName = ir?.projectName;

  const [activeTab, setActiveTab] = useState<'personal' | 'project'>('personal');
  const [projectConfigSummaries, setProjectConfigSummaries] = useState<Record<string, any>>({});
  const [isLoadingProjectIndex, setIsLoadingProjectIndex] = useState(false);

  // Project LLM states
  const [projectConfig, setProjectConfig] = useState<any | null>(null);
  const [projectApiUrl, setProjectApiUrl] = useState('');
  const [projectApiKey, setProjectApiKey] = useState('');
  const [projectModelName, setProjectModelName] = useState('');
  const [isEditingProject, setIsEditingProject] = useState(false);
  const [isTestingProject, setIsTestingProject] = useState(false);
  const [projectTestResult, setProjectTestResult] = useState<{ success: boolean; message: string } | null>(null);

  // Preferred locale state
  const [selectedLocale, setSelectedLocale] = useState<UiLocale>(
    normalizeUiLocale(user?.preferredLocale ?? user?.preferred_locale),
  );
  const [isSavingLocale, setIsSavingLocale] = useState(false);

  useEffect(() => {
    if (user?.preferredLocale || user?.preferred_locale) {
      setSelectedLocale(normalizeUiLocale(user.preferredLocale ?? user.preferred_locale));
    }
  }, [user]);

  const handleLocaleChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newLocale = normalizeUiLocale(e.target.value);
    const oldLocale = selectedLocale;
    setSelectedLocale(newLocale);
    setIsSavingLocale(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      await authApi.updatePreferences({ preferred_locale: newLocale });
      // Update store user state
      if (user) {
        useAuthStore.setState({
          user: {
            ...user,
            preferred_locale: newLocale,
            preferredLocale: newLocale
          }
        });
      }
      await applyUiLocale(newLocale);
      setActionSuccess(t('settings.interfaceLanguage.saveSuccess'));
    } catch (err: any) {
      console.error(err);
      setSelectedLocale(oldLocale);
      setActionError(t('settings.interfaceLanguage.saveError'));
    } finally {
      setIsSavingLocale(false);
    }
  };

  const fetchConfig = async () => {
    setIsLoading(true);
    setActionError(null);
    try {
      const data = await accountApi.getLLMConfig();
      setConfig(data);
      if (data.configured && data.source === 'personal') {
        setApiUrl(data.api_url || '');
        setModelName(data.model_name || '');
      } else {
        setApiUrl('');
        setModelName('');
      }
      setApiKey(''); // Never fill password fields
    } catch (err: any) {
      setActionError(err.message || t('settings.account.fetchFailed'));
    } finally {
      setIsLoading(false);
    }
  };

  const fetchProjectConfig = async () => {
    if (!projectId) return;
    try {
      const data = await workspaceApi.getProjectLLMConfig(projectId);
      setProjectConfig(data);
      if (data.configured) {
        setProjectApiUrl(data.apiUrl || '');
        setProjectModelName(data.modelName || '');
      } else {
        setProjectApiUrl('');
        setProjectModelName('');
      }
      setProjectApiKey('');
    } catch (err: any) {
      console.error(err);
    }
  };

  useEffect(() => {
    void fetchConfig();
    void loadWorkspaces();
    if (projectId) {
      void fetchProjectConfig();
    }
  }, [projectId, loadWorkspaces]);

  useEffect(() => {
    if (activeTab !== 'project' || workspaces.length === 0) return;

    let cancelled = false;
    const fetchSummaries = async () => {
      setIsLoadingProjectIndex(true);
      try {
        const entries = await Promise.all(
          workspaces.map(async (project) => {
            try {
              const config = await workspaceApi.getProjectConfiguration(project.id);
              return [project.id, config] as const;
            } catch {
              return [project.id, null] as const;
            }
          })
        );
        if (!cancelled) {
          setProjectConfigSummaries(Object.fromEntries(entries));
        }
      } finally {
        if (!cancelled) {
          setIsLoadingProjectIndex(false);
        }
      }
    };

    void fetchSummaries();
    return () => {
      cancelled = true;
    };
  }, [activeTab, workspaces]);

  const sortedProjectConfigItems = useMemo(() => {
    return [...workspaces].sort((a, b) => {
      if (a.id === projectId) return -1;
      if (b.id === projectId) return 1;
      return a.updatedAt < b.updatedAt ? 1 : -1;
    });
  }, [projectId, workspaces]);

  const handleSaveProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectId) return;
    setActionError(null);
    setActionSuccess(null);

    const cleanUrl = projectApiUrl.trim();
    const cleanKey = projectApiKey.trim();
    const cleanModel = projectModelName.trim();

    if (!cleanUrl || !cleanKey || !cleanModel) {
      setActionError(t('settings.account.fieldsRequired'));
      return;
    }

    try {
      const updated = await workspaceApi.updateProjectLLMConfig(projectId, {
        api_url: cleanUrl,
        api_key: cleanKey,
        model_name: cleanModel,
      });
      setProjectConfig({
        configured: updated.configured,
        apiUrl: updated.apiUrl,
        modelName: updated.modelName,
        apiKeyLast4: updated.apiKeyLast4,
      });
      setIsEditingProject(false);
      setProjectApiKey('');
      setProjectTestResult(null);
      setActionSuccess(t('settings.account.projectSaved'));
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err: any) {
      setActionError(err?.response?.data?.detail || err.message || t('settings.account.projectSaveFailed'));
    }
  };

  const handleDeleteProject = async () => {
    if (!projectId) return;
    const confirm = window.confirm(t('settings.account.clearProjectConfirm'));
    if (!confirm) return;

    setActionError(null);
    setActionSuccess(null);
    try {
      await workspaceApi.deleteProjectLLMConfig(projectId);
      setProjectConfig({
        configured: false,
        apiUrl: null,
        modelName: null,
        apiKeyLast4: null,
      });
      setProjectApiUrl('');
      setProjectModelName('');
      setProjectApiKey('');
      setProjectTestResult(null);
      setActionSuccess(t('settings.account.projectCleared'));
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err: any) {
      setActionError(err?.response?.data?.detail || err.message || t('settings.account.projectClearFailed'));
    }
  };

  const handleTestProject = async (e?: React.MouseEvent) => {
    if (e) e.preventDefault();
    if (!projectId) return;
    setIsTestingProject(true);
    setProjectTestResult(null);
    try {
      let res;
      if (isEditingProject || !projectConfig?.configured) {
        if (!projectApiUrl.trim() || !projectApiKey.trim() || !projectModelName.trim()) {
      setProjectTestResult({ success: false, message: t('settings.account.completeConfigurationFirst') });
          setIsTestingProject(false);
          return;
        }
        res = await workspaceApi.testProjectLLMConfig(projectId, {
          api_url: projectApiUrl.trim(),
          api_key: projectApiKey.trim(),
          model_name: projectModelName.trim(),
        });
      } else {
        res = await workspaceApi.testProjectLLMConfig(projectId, {
          api_url: projectConfig.apiUrl,
          api_key: "",
          model_name: projectConfig.modelName,
        });
      }

      if (res.success) {
      setProjectTestResult({ success: true, message: t('settings.account.projectConnectionSucceeded') });
      } else {
        setProjectTestResult({
          success: false,
        message: t('settings.account.connectionFailed', { error: res.error_detail || t('settings.account.upstreamUnavailable') })
        });
      }
    } catch (err: any) {
      setProjectTestResult({
        success: false,
        message: t('settings.account.networkError', { error: err.message || t('settings.account.urlUnavailable') })
      });
    } finally {
      setIsTestingProject(false);
    }
  };

  const handleTest = async (e?: React.MouseEvent) => {
    if (e) e.preventDefault();
    setIsTesting(true);
    setTestResult(null);
    try {
      const isPersonal = user?.role === 'user';
      let res;
      if (isPersonal && (isEditing || !config?.configured)) {
        // Test with form fields
        if (!apiUrl.trim() || !apiKey.trim() || !modelName.trim()) {
      setTestResult({ success: false, message: t('settings.account.completePersonalConfigurationFirst') });
          return;
        }
        res = await accountApi.testLLMConfig({
          api_url: apiUrl.trim(),
          api_key: apiKey.trim(),
          model_name: modelName.trim(),
        });
      } else {
        // Test with saved configurations (personal or server)
        res = await accountApi.testLLMConfig();
      }

      if (res.success) {
      setTestResult({ success: true, message: t('settings.account.personalConnectionSucceeded') });
      } else {
        setTestResult({
          success: false,
        message: t('settings.account.connectionFailed', { error: res.error_detail || t('settings.account.upstreamUnavailable') })
        });
      }
    } catch (err: any) {
      setTestResult({
        success: false,
        message: t('settings.account.networkError', { error: err.message || t('settings.account.urlUnavailable') })
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionError(null);
    setActionSuccess(null);

    const cleanUrl = apiUrl.trim();
    const cleanKey = apiKey.trim();
    const cleanModel = modelName.trim();

    if (!cleanUrl || !cleanKey || !cleanModel) {
      setActionError(t('settings.account.fieldsRequired'));
      return;
    }

    try {
      const updated = await accountApi.updateLLMConfig({
        api_url: cleanUrl,
        api_key: cleanKey,
        model_name: cleanModel,
      });
      setConfig(updated);
      setIsEditing(false);
      setApiKey('');
      setTestResult(null);
      setActionSuccess(t('settings.account.personalSaved'));
      const timer = setTimeout(() => setActionSuccess(null), 3000);
      return () => clearTimeout(timer);
    } catch (err: any) {
      setActionError(err.message || t('settings.account.personalSaveFailed'));
    }
  };

  const handleDelete = async () => {
    const confirm = window.confirm(t('settings.account.clearPersonalConfirm'));
    if (!confirm) return;

    setActionError(null);
    setActionSuccess(null);
    try {
      await accountApi.deleteLLMConfig();
      setConfig({
        configured: false,
        source: null,
        api_url: null,
        model_name: null,
        api_key_last4: null,
      });
      setApiUrl('');
      setApiKey('');
      setModelName('');
      setTestResult(null);
      setActionSuccess(t('settings.account.personalCleared'));
    } catch (err: any) {
      setActionError(err.message || t('settings.account.personalClearFailed'));
    }
  };

  const showEditForm = isEditing || !config?.configured;

  return (
    <div className="flex-1 min-h-[100dvh] bg-slate-50 flex flex-col font-sans selection:bg-indigo-100 relative overflow-hidden">
      {/* Background Decor */}
      <div className="absolute -right-32 -top-32 w-[35rem] h-[35rem] bg-indigo-500/5 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -left-32 -bottom-32 w-[35rem] h-[35rem] bg-indigo-500/5 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <header className="h-16 border-b border-slate-200/50 bg-white/70 backdrop-blur-xl flex items-center px-6 sm:px-8 shrink-0 sticky top-0 z-20 shadow-sm">
        <button
          onClick={() => navigate('/home')}
          className="flex items-center gap-2 text-slate-500 hover:text-indigo-600 transition-colors text-xs font-bold cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          {t('settings.account.backHome')}
        </button>
        <div className="h-4 w-[1px] bg-slate-200 mx-4" />
          <span className="font-extrabold text-sm text-slate-800 tracking-tight">{t('settings.account.navigationTitle')}</span>
      </header>

      {/* Main Container */}
      <main className="flex-1 w-full max-w-4xl mx-auto px-4 sm:px-6 py-8 relative z-10 space-y-6">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">{t('settings.account.pageTitle')}</h1>
          <p className="text-xs text-slate-500 font-medium mt-1">
            {t('settings.account.pageDescription')}
          </p>
        </div>

        {actionError && (
          <div className="text-xs font-bold text-rose-600 bg-rose-50 border border-rose-100 rounded-xl p-3 shadow-inner">
            {actionError === 'admin_cannot_configure_personal_llm' ? t('settings.account.adminCannotConfigure') : actionError}
          </div>
        )}

        {actionSuccess && (
          <div className="text-xs font-bold text-emerald-600 bg-emerald-50 border border-emerald-100 rounded-xl p-3 shadow-inner">
            {actionSuccess}
          </div>
        )}

        {/* 1. Account Info Section */}
        <section className="bg-white rounded-3xl border border-slate-200/60 p-6 sm:p-7 shadow-lg space-y-6">
          <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
            <div className="w-10 h-10 bg-indigo-50 border border-indigo-100 rounded-xl flex items-center justify-center text-indigo-600 shadow-sm">
              <User className="w-5 h-5" />
            </div>
            <div>
          <h2 className="text-sm font-extrabold text-slate-800">{t('settings.account.personalInfo')}</h2>
          <p className="text-[10px] text-slate-400 font-medium">{t('settings.account.personalInfoDescription')}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 text-sm">
            <div className="space-y-1 bg-slate-50 border border-slate-100 p-4 rounded-2xl">
              <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">{t('settings.account.email')}</span>
              <span className="font-extrabold text-slate-800">{user?.email}</span>
            </div>
            <div className="space-y-1 bg-slate-50 border border-slate-100 p-4 rounded-2xl flex flex-col justify-between">
              <div>
              <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">{t('settings.account.role')}</span>
                <span className="font-extrabold text-slate-800 flex items-center gap-1.5 mt-0.5">
                  {user?.role === 'admin' ? (
                    <>
                      <Shield className="w-4 h-4 text-indigo-600" />
                {t('settings.account.adminUser')}
                    </>
                  ) : (
                    <>
                      <User className="w-4 h-4 text-slate-500" />
                {t('settings.account.standardUser')}
                    </>
                  )}
                </span>
              </div>
            </div>
            <div className="space-y-1 bg-slate-50 border border-slate-100 p-4 rounded-2xl flex flex-col justify-between">
              <div>
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-1">
                  {t('settings.interfaceLanguage.title')}
                </span>
                <div className="relative mt-1">
                  <select
                    value={selectedLocale}
                    onChange={handleLocaleChange}
                    disabled={isSavingLocale}
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs font-bold text-slate-700 outline-none focus:ring-2 focus:ring-indigo-500 transition-all cursor-pointer disabled:opacity-50"
                  >
                    <option value="zh-CN">{t('settings.interfaceLanguage.zh')}</option>
                    <option value="en-US">{t('settings.interfaceLanguage.en')}</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 2. LLM Config Section */}
        <section className="bg-white rounded-3xl border border-slate-200/60 p-6 sm:p-7 shadow-lg space-y-6">
          <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
            <div className="w-10 h-10 bg-indigo-50 border border-indigo-100 rounded-xl flex items-center justify-center text-indigo-600 shadow-sm">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-extrabold text-slate-800">{t('settings.title')}</h2>
              <p className="text-[10px] text-slate-400 font-medium">{t('settings.subtitle')}</p>
            </div>
          </div>

          {projectId && (
            <div className="flex border-b border-slate-100 pb-3 mb-4 gap-4">
              <button
                onClick={() => {
                  setActiveTab('personal');
                  setTestResult(null);
                  setProjectTestResult(null);
                }}
                className={`pb-2 px-1 text-xs font-bold border-b-2 transition-all cursor-pointer ${
                  activeTab === 'personal'
                    ? 'border-indigo-600 text-indigo-600 font-extrabold'
                    : 'border-transparent text-slate-400 hover:text-slate-600'
                }`}
              >
                {t('settings.personalTab')}
              </button>
              <button
                onClick={() => {
                  setActiveTab('project');
                  setTestResult(null);
                  setProjectTestResult(null);
                }}
                className={`pb-2 px-1 text-xs font-bold border-b-2 transition-all cursor-pointer ${
                  activeTab === 'project'
                    ? 'border-indigo-600 text-indigo-600 font-extrabold'
                    : 'border-transparent text-slate-400 hover:text-slate-600'
                }`}
              >
                {t('settings.projectTab')}
              </button>
            </div>
          )}

          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-10 space-y-3">
              <div className="h-8 w-8 rounded-full border-4 border-slate-100 border-t-indigo-600 animate-spin" />
            <span className="text-xs text-slate-400 font-medium">{t('settings.account.loadingConfiguration')}</span>
            </div>
          ) : activeTab === 'personal' ? (
            /* PERSONAL TAB */
            user?.role === 'admin' ? (
              /* Admin view (Read-only) */
              <div className="space-y-6">
                <div className="p-4 rounded-2xl bg-indigo-50/50 border border-indigo-100 text-indigo-950 space-y-3">
                  <h3 className="text-sm font-bold flex items-center gap-1.5">
                    <Shield className="w-4 h-4 text-indigo-600" />
              {t('settings.account.serverConfigurationTitle')}
                  </h3>
                  <p className="text-xs leading-relaxed text-slate-600">
              {t('settings.account.serverConfigurationDescription')}
                  </p>
                </div>

                <div className="flex items-center gap-4 bg-slate-50 p-4 border border-slate-100 rounded-2xl">
                  <div className="flex items-center gap-2">
                    <div className={`h-2.5 w-2.5 rounded-full ${config?.configured ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
                    <span className="text-xs font-bold text-slate-700">
              {t('settings.account.serverConnectionStatus', { status: config?.configured ? t('settings.account.ready') : t('settings.account.notReady') })}
                    </span>
                  </div>
                  {config?.configured && (
                    <button
                      onClick={() => handleTest()}
                      disabled={isTesting}
                      className="ml-auto px-4 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 active:scale-[0.99] transition-all disabled:opacity-50 flex items-center gap-1.5 cursor-pointer shadow-sm"
                    >
                      {isTesting ? (
                        <span className="h-3.5 w-3.5 rounded-full border-2 border-slate-200 border-t-indigo-600 animate-spin" />
                      ) : (
                        <>
                          <Activity className="w-3.5 h-3.5" />
                {t('settings.account.testConnection')}
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            ) : (
              /* Regular User view (Editable) */
              <div className="space-y-6">
                {!showEditForm && config?.configured && (
                  /* Config overview state */
                  <div className="space-y-5">
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-medium">
                      <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block mb-1">{t('settings.account.apiBaseUrl')}</span>
                        <span className="font-extrabold text-slate-800 break-all">{config.api_url}</span>
                      </div>
                      <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block mb-1">{t('settings.account.modelName')}</span>
                        <span className="font-extrabold text-slate-800 break-all">{config.model_name}</span>
                      </div>
                      <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block mb-1">{t('settings.account.apiKeyCiphertext')}</span>
                        <span className="font-extrabold text-slate-800">••••••••{config.api_key_last4}</span>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-3 pt-2">
                      <button
                        onClick={() => handleTest()}
                        disabled={isTesting}
                        className="px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 active:scale-[0.99] transition-all disabled:opacity-50 flex items-center gap-1.5 cursor-pointer"
                      >
                        {isTesting ? (
                          <span className="h-3.5 w-3.5 rounded-full border-2 border-slate-400 border-t-white animate-spin" />
                        ) : (
                          <>
                            <Activity className="w-3.5 h-3.5" />
                {t('settings.account.testConnection')}
                          </>
                        )}
                      </button>
                      <button
                        onClick={() => setIsEditing(true)}
                        className="px-4 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 active:scale-[0.99] transition-all flex items-center gap-1.5 cursor-pointer shadow-sm"
                      >
                        <Edit className="w-3.5 h-3.5" />
                {t('settings.account.editConfiguration')}
                      </button>
                      <button
                        onClick={() => handleDelete()}
                        className="px-4 py-2 border border-rose-200 bg-rose-50 text-rose-600 text-xs font-bold rounded-xl hover:bg-rose-100 active:scale-[0.99] transition-all flex items-center gap-1.5 ml-auto cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                {t('settings.account.clearConfiguration')}
                      </button>
                    </div>
                  </div>
                )}

                {showEditForm && (
                  /* Config editing/creation form */
                  <form onSubmit={handleSave} className="space-y-5">
                    <div className="p-4 bg-amber-50/50 border border-amber-100 text-amber-900 rounded-2xl text-xs leading-relaxed">
                      {t('settings.account.personalConfigurationDescription')}
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">
                          {t('settings.account.apiBaseUrl')} <span className="text-rose-500">*</span>
                        </label>
                        <div className="relative">
                          <Globe className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                          <input
                            type="url"
                            placeholder="https://api.openai.com"
                            value={apiUrl}
                            onChange={(e) => setApiUrl(e.target.value)}
                            className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800 font-bold transition-all"
                            required
                          />
                        </div>
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">
                          {t('settings.account.modelName')} <span className="text-rose-500">*</span>
                        </label>
                        <div className="relative">
                          <Cpu className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                          <input
                            type="text"
                            placeholder="gpt-4o"
                            value={modelName}
                            onChange={(e) => setModelName(e.target.value)}
                            className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800 font-bold transition-all"
                            required
                          />
                        </div>
                      </div>

                      <div className="space-y-1.5 sm:col-span-2">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">
                          {t('settings.account.apiKey')} <span className="text-rose-500">*</span>
                        </label>
                        <div className="relative">
                          <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                          <input
                            type="password"
                            placeholder={config?.configured ? t('settings.account.apiKeyUnchanged') : t('settings.account.apiKeyPlaceholder')}
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800 font-bold transition-all"
                            required={!config?.configured}
                          />
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 pt-2">
                      <button
                        type="submit"
                        className="px-5 py-2.5 bg-indigo-600 text-white text-xs font-bold rounded-xl hover:bg-indigo-700 active:scale-[0.99] transition-colors flex items-center gap-1.5 shadow-md shadow-indigo-600/10 cursor-pointer"
                      >
                        <Save className="w-3.5 h-3.5" />
                        {t('settings.account.saveConfiguration')}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleTest()}
                        disabled={isTesting}
                        className="px-5 py-2.5 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 active:scale-[0.99] transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm"
                      >
                        {isTesting ? (
                          <span className="h-3.5 w-3.5 rounded-full border-2 border-slate-200 border-t-indigo-600 animate-spin" />
                        ) : (
                          <>
                            <Activity className="w-3.5 h-3.5" />
                            {t('settings.account.testConnection')}
                          </>
                        )}
                      </button>
                      {config?.configured && (
                        <button
                          type="button"
                          onClick={() => {
                            setIsEditing(false);
                            setApiUrl(config.api_url || '');
                            setModelName(config.model_name || '');
                            setApiKey('');
                            setTestResult(null);
                          }}
                          className="px-5 py-2.5 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 active:scale-[0.99] transition-colors ml-auto cursor-pointer shadow-sm"
                        >
                          {t('common.cancel')}
                        </button>
                      )}
                    </div>
                  </form>
                )}
              </div>
            )
          ) : (
            /* PROJECT TAB */
            <div className="space-y-6">
              <div className="p-4 bg-indigo-50/50 border border-indigo-100 text-indigo-900 rounded-2xl text-xs leading-relaxed">
                {t('settings.account.projectIndexDescription')}
              </div>

              {isLoadingProjectIndex ? (
                <div className="flex flex-col items-center justify-center py-10 space-y-3">
                  <div className="h-8 w-8 rounded-full border-4 border-slate-100 border-t-indigo-600 animate-spin" />
                  <span className="text-xs text-slate-400 font-medium">{t('settings.account.loadingProjectIndex')}</span>
                </div>
              ) : sortedProjectConfigItems.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center text-xs font-medium text-slate-400">
                  {t('settings.account.noManageableProjects')}
                </div>
              ) : (
                <div className="space-y-3">
                  {sortedProjectConfigItems.map((project) => {
                    const config = projectConfigSummaries[project.id];
                    const strategy = config?.generation_strategy;
                    const knowledge = config?.knowledge;
                    const llm = config?.llm;
                    const enabledStrategies = (strategy?.strategies || []).filter((item: any) => item.enabled).length;
                    const isCurrent = project.id === projectId;

                    return (
                      <div
                        key={project.id}
                        className={`rounded-2xl border p-4 transition-colors ${
                          isCurrent ? 'border-indigo-200 bg-indigo-50/40' : 'border-slate-200 bg-white'
                        }`}
                      >
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <h3 className="text-sm font-black text-slate-800">{project.name}</h3>
                              {isCurrent && (
                                <span className="rounded-full border border-indigo-200 bg-white px-2 py-0.5 text-[10px] font-black text-indigo-700">
                                   {t('settings.account.currentProject')}
                                </span>
                              )}
                            </div>
                            <p className="mt-1 line-clamp-2 text-xs font-medium leading-relaxed text-slate-500">
                               {project.description || project.idea || t('settings.account.noProjectDescription')}
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => navigate(`/projects/${project.id}/configuration`)}
                            className="shrink-0 rounded-xl bg-indigo-600 px-3 py-2 text-xs font-bold text-white shadow-sm transition-colors hover:bg-indigo-700"
                          >
                             {t('settings.account.openConfiguration')}
                          </button>
                        </div>

                        <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
                          <div className="rounded-xl border border-slate-100 bg-white p-3 text-xs">
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-black text-slate-400">{t('settings.account.generationStrategy')}</span>
                              <span className="font-bold text-slate-600">{strategy?.source === 'project' ? t('settings.account.projectCustom') : t('settings.account.systemDefault')}</span>
                            </div>
                            <div className="mt-2 font-extrabold text-slate-800">
                              {t('settings.account.strategySummary', { candidates: strategy?.candidate_count ?? 2, enabled: enabledStrategies || 2 })}
                            </div>
                            <button
                              type="button"
                              onClick={() => navigate(`/projects/${project.id}/configuration?tab=ai-strategies`)}
                              className="mt-3 text-[11px] font-bold text-indigo-600 hover:text-indigo-700"
                            >
                              {t('settings.account.viewStrategy')}
                            </button>
                          </div>

                          <div className="rounded-xl border border-slate-100 bg-white p-3 text-xs">
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-black text-slate-400">{t('settings.account.projectKnowledge')}</span>
                              <span className={`font-bold ${knowledge?.enabled === false ? 'text-slate-400' : 'text-slate-600'}`}>
                                {knowledge?.enabled === false ? t('settings.account.disabled') : t('settings.account.enabled')}
                              </span>
                            </div>
                            <div className="mt-2 font-extrabold text-slate-800">
                              {t('settings.account.knowledgeSummary', { documents: knowledge?.document_count ?? 0, aiEnabled: knowledge?.ai_enabled_count ?? 0 })}
                            </div>
                            <div className="mt-1 text-[11px] font-medium text-slate-400">
                              {t('settings.account.knowledgeProcessingSummary', { processing: knowledge?.processing_count ?? 0, failed: knowledge?.failed_count ?? 0 })}
                            </div>
                            <button
                              type="button"
                              onClick={() => navigate(`/projects/${project.id}/configuration?tab=knowledge`)}
                              className="mt-3 text-[11px] font-bold text-indigo-600 hover:text-indigo-700"
                            >
                              {t('settings.account.viewKnowledge')}
                            </button>
                          </div>

                          <div className="rounded-xl border border-slate-100 bg-white p-3 text-xs">
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-black text-slate-400">{t('settings.account.projectLlm')}</span>
                              <span className={`font-bold ${llm?.configured ? 'text-emerald-700' : 'text-slate-500'}`}>
                                {llm?.configured ? t('settings.account.projectConfigured') : t('settings.account.projectNotConfigured')}
                              </span>
                            </div>
                            <div className="mt-2 font-extrabold text-slate-800">
                               {llm?.configured ? (llm?.model_name || t('settings.account.projectModel')) : t('settings.account.fallbackTo', { source: llm?.source === 'personal' ? t('settings.account.personalConfiguration') : t('settings.account.systemConfiguration') })}
                            </div>
                            <div className="mt-1 text-[11px] font-medium text-slate-400">
                               {t('settings.account.effectiveModel', { model: llm?.model_name || '-' })}
                            </div>
                            <button
                              type="button"
                              onClick={() => navigate(`/projects/${project.id}/configuration?tab=llm`)}
                              className="mt-3 text-[11px] font-bold text-indigo-600 hover:text-indigo-700"
                            >
                              {t('settings.account.viewProjectLlm')}
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Test results banner */}
          {((activeTab === 'personal' && testResult) || (activeTab === 'project' && projectTestResult)) && (
            <div
              className={`p-4 rounded-2xl border text-xs flex items-start gap-3 animate-in slide-in-from-top-2 duration-200 ${
                (activeTab === 'personal' ? testResult!.success : projectTestResult!.success)
                  ? 'bg-emerald-50 border-emerald-100 text-emerald-950'
                  : 'bg-rose-50 border-rose-100 text-rose-950'
              }`}
            >
              {(activeTab === 'personal' ? testResult!.success : projectTestResult!.success) ? (
                <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              ) : (
                <XCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              )}
              <div className="space-y-1">
                <span className="font-bold">{(activeTab === 'personal' ? testResult!.success : projectTestResult!.success) ? t('settings.account.testPassed') : t('settings.account.testFailed')}</span>
                <p className="leading-relaxed text-slate-600">{(activeTab === 'personal' ? testResult!.message : projectTestResult!.message)}</p>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
export default AccountSettings;
