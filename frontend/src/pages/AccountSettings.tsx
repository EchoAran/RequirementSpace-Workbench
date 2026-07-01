import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { accountApi, LLMConfigResponse } from '../lib/accountApi';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { workspaceApi } from '../lib/api';
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
} from 'lucide-react';

export function AccountSettings() {
  const user = useAuthStore(state => state.user);
  const navigate = useNavigate();

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
  const projectId = ir?.projectId;
  const projectName = ir?.projectName;

  const [activeTab, setActiveTab] = useState<'personal' | 'project'>('personal');

  // Project LLM states
  const [projectConfig, setProjectConfig] = useState<any | null>(null);
  const [projectApiUrl, setProjectApiUrl] = useState('');
  const [projectApiKey, setProjectApiKey] = useState('');
  const [projectModelName, setProjectModelName] = useState('');
  const [isEditingProject, setIsEditingProject] = useState(false);
  const [isTestingProject, setIsTestingProject] = useState(false);
  const [projectTestResult, setProjectTestResult] = useState<{ success: boolean; message: string } | null>(null);

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
      setActionError(err.message || '获取配置信息失败');
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
    if (projectId) {
      void fetchProjectConfig();
    }
  }, [projectId]);

  const handleSaveProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectId) return;
    setActionError(null);
    setActionSuccess(null);

    const cleanUrl = projectApiUrl.trim();
    const cleanKey = projectApiKey.trim();
    const cleanModel = projectModelName.trim();

    if (!cleanUrl || !cleanKey || !cleanModel) {
      setActionError('配置字段不能为空');
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
      setActionSuccess('项目连接配置已成功保存');
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err: any) {
      setActionError(err?.response?.data?.detail || err.message || '保存项目连接配置失败');
    }
  };

  const handleDeleteProject = async () => {
    if (!projectId) return;
    const confirm = window.confirm('确定要清除项目的团队 LLM 配置吗？清除后将恢复使用个人配置或系统配置。');
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
      setActionSuccess('项目连接配置已成功清除');
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err: any) {
      setActionError(err?.response?.data?.detail || err.message || '清除项目连接配置失败');
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
          setProjectTestResult({ success: false, message: '请完整填写连接配置后再测试' });
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
        setProjectTestResult({ success: true, message: '连接成功！项目的 LLM 连接一切正常。' });
      } else {
        setProjectTestResult({
          success: false,
          message: `连接失败: ${res.error_detail || '无法成功调用上游模型，请检查服务配置。'}`
        });
      }
    } catch (err: any) {
      setProjectTestResult({
        success: false,
        message: `网络错误: ${err.message || '连接失败，请检查 URL 可访问性。'}`
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
          setTestResult({ success: false, message: '请完整填写连接配置（API 根地址、API Key 和模型名称）后再测试' });
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
        setTestResult({ success: true, message: '连接成功！您的 LLM 连接一切正常。' });
      } else {
        setTestResult({
          success: false,
          message: `连接失败: ${res.error_detail || '无法成功调用上游模型，请检查服务配置。'}`
        });
      }
    } catch (err: any) {
      setTestResult({
        success: false,
        message: `网络错误: ${err.message || '连接失败，请检查 URL 可访问性。'}`
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
      setActionError('配置字段不能为空');
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
      setActionSuccess('连接配置已成功保存');
      const timer = setTimeout(() => setActionSuccess(null), 3000);
      return () => clearTimeout(timer);
    } catch (err: any) {
      setActionError(err.message || '保存连接配置失败');
    }
  };

  const handleDelete = async () => {
    const confirm = window.confirm('确定要清除您的个人 LLM 配置吗？清除后您将无法进行 AI 场景生成，必须重新配置。');
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
      setActionSuccess('配置已成功清除');
    } catch (err: any) {
      setActionError(err.message || '清除配置失败');
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
          返回首页
        </button>
        <div className="h-4 w-[1px] bg-slate-200 mx-4" />
        <span className="font-extrabold text-sm text-slate-800 tracking-tight">账户设置与 LLM 配置</span>
      </header>

      {/* Main Container */}
      <main className="flex-1 w-full max-w-4xl mx-auto px-4 sm:px-6 py-8 relative z-10 space-y-6">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">账户与服务配置</h1>
          <p className="text-xs text-slate-500 font-medium mt-1">
            配置您的用户属性及大语言模型 API 连接以解锁智能推演。
          </p>
        </div>

        {actionError && (
          <div className="text-xs font-bold text-rose-600 bg-rose-50 border border-rose-100 rounded-xl p-3 shadow-inner">
            {actionError === 'admin_cannot_configure_personal_llm' ? '管理员不可配置个人配置' : actionError}
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
              <h2 className="text-sm font-extrabold text-slate-800">个人基本信息</h2>
              <p className="text-[10px] text-slate-400 font-medium">当前登录账户的身份信息</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 text-sm">
            <div className="space-y-1 bg-slate-50 border border-slate-100 p-4 rounded-2xl">
              <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">邮箱地址</span>
              <span className="font-extrabold text-slate-800">{user?.email}</span>
            </div>
            <div className="space-y-1 bg-slate-50 border border-slate-100 p-4 rounded-2xl flex flex-col justify-between">
              <div>
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">账户角色</span>
                <span className="font-extrabold text-slate-800 flex items-center gap-1.5 mt-0.5">
                  {user?.role === 'admin' ? (
                    <>
                      <Shield className="w-4 h-4 text-indigo-600" />
                      管理员用户
                    </>
                  ) : (
                    <>
                      <User className="w-4 h-4 text-slate-500" />
                      普通用户
                    </>
                  )}
                </span>
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
              <h2 className="text-sm font-extrabold text-slate-800">大语言模型配置 (LLM Connection)</h2>
              <p className="text-[10px] text-slate-400 font-medium">AI 功能的数据通道与认证参数</p>
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
                个人 LLM 配置
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
                项目团队配置 ({projectName})
              </button>
            </div>
          )}

          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-10 space-y-3">
              <div className="h-8 w-8 rounded-full border-4 border-slate-100 border-t-indigo-600 animate-spin" />
              <span className="text-xs text-slate-400 font-medium">正在拉取配置详情...</span>
            </div>
          ) : activeTab === 'personal' ? (
            /* PERSONAL TAB */
            user?.role === 'admin' ? (
              /* Admin view (Read-only) */
              <div className="space-y-6">
                <div className="p-4 rounded-2xl bg-indigo-50/50 border border-indigo-100 text-indigo-950 space-y-3">
                  <h3 className="text-sm font-bold flex items-center gap-1.5">
                    <Shield className="w-4 h-4 text-indigo-600" />
                    已挂载服务端共享 LLM 配置
                  </h3>
                  <p className="text-xs leading-relaxed text-slate-600">
                    由于您是以<strong>管理员</strong>身份登录 of，系统将直接默认读取服务器环境配置文件（`.env`）中配置的共享大语言模型 API 资源，您无需手动在此配置个人 API 信息。
                  </p>
                </div>

                <div className="flex items-center gap-4 bg-slate-50 p-4 border border-slate-100 rounded-2xl">
                  <div className="flex items-center gap-2">
                    <div className={`h-2.5 w-2.5 rounded-full ${config?.configured ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
                    <span className="text-xs font-bold text-slate-700">
                      服务端连接状态：{config?.configured ? '已就绪' : '未就绪 (请检查服务端 env)'}
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
                          测试通道连通性
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
                        <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block mb-1">API 根地址</span>
                        <span className="font-extrabold text-slate-800 break-all">{config.api_url}</span>
                      </div>
                      <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                        <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block mb-1">模型名称</span>
                        <span className="font-extrabold text-slate-800 break-all">{config.model_name}</span>
                      </div>
                      <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                        <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block mb-1">API Key 密文</span>
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
                            测试连通性
                          </>
                        )}
                      </button>
                      <button
                        onClick={() => setIsEditing(true)}
                        className="px-4 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 active:scale-[0.99] transition-all flex items-center gap-1.5 cursor-pointer shadow-sm"
                      >
                        <Edit className="w-3.5 h-3.5" />
                        修改配置
                      </button>
                      <button
                        onClick={() => handleDelete()}
                        className="px-4 py-2 border border-rose-200 bg-rose-50 text-rose-600 text-xs font-bold rounded-xl hover:bg-rose-100 active:scale-[0.99] transition-all flex items-center gap-1.5 ml-auto cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        清除配置
                      </button>
                    </div>
                  </div>
                )}

                {showEditForm && (
                  /* Config editing/creation form */
                  <form onSubmit={handleSave} className="space-y-5">
                    <div className="p-4 bg-amber-50/50 border border-amber-100 text-amber-900 rounded-2xl text-xs leading-relaxed">
                      普通用户账号必须自主提供 OpenAI-compatible 协议的 AI 连接地址及 API Key 才可执行智能推演。个人 API 凭证将使用您的独立密钥加密存储在数据库中，不会共享。
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">
                          API 根地址 (API Base URL) <span className="text-rose-500">*</span>
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
                          大模型名称 (Model Name) <span className="text-rose-500">*</span>
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
                          认证密钥 (API Key) <span className="text-rose-500">*</span>
                        </label>
                        <div className="relative">
                          <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                          <input
                            type="password"
                            placeholder={config?.configured ? '未更改（请输入新 Key 替换）' : '请输入 API Key'}
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
                        保存配置
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
                            测试连通性
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
                          取消
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
              {!isEditingProject && projectConfig?.configured && (
                /* Config overview state */
                <div className="space-y-5">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-medium">
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                      <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block mb-1">API 根地址</span>
                      <span className="font-extrabold text-slate-800 break-all">{projectConfig.apiUrl}</span>
                    </div>
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                      <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block mb-1">模型名称</span>
                      <span className="font-extrabold text-slate-800 break-all">{projectConfig.modelName}</span>
                    </div>
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                      <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block mb-1">API Key 密文</span>
                      <span className="font-extrabold text-slate-800">••••••••{projectConfig.apiKeyLast4}</span>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-3 pt-2">
                    <button
                      onClick={() => handleTestProject()}
                      disabled={isTestingProject}
                      className="px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 active:scale-[0.99] transition-all disabled:opacity-50 flex items-center gap-1.5 cursor-pointer"
                    >
                      {isTestingProject ? (
                        <span className="h-3.5 w-3.5 rounded-full border-2 border-slate-400 border-t-white animate-spin" />
                      ) : (
                        <>
                          <Activity className="w-3.5 h-3.5" />
                          测试连通性
                        </>
                      )}
                    </button>
                    <button
                      onClick={() => setIsEditingProject(true)}
                      className="px-4 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 active:scale-[0.99] transition-all flex items-center gap-1.5 cursor-pointer shadow-sm"
                    >
                      <Edit className="w-3.5 h-3.5" />
                      修改配置
                    </button>
                    <button
                      onClick={() => handleDeleteProject()}
                      className="px-4 py-2 border border-rose-200 bg-rose-50 text-rose-600 text-xs font-bold rounded-xl hover:bg-rose-100 active:scale-[0.99] transition-all flex items-center gap-1.5 ml-auto cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      清除配置
                    </button>
                  </div>
                </div>
              )}

              {(!projectConfig?.configured || isEditingProject) && (
                /* Config editing/creation form */
                <form onSubmit={handleSaveProject} className="space-y-5">
                  <div className="p-4 bg-indigo-50/50 border border-indigo-100 text-indigo-900 rounded-2xl text-xs leading-relaxed">
                    项目团队 LLM 配置将由项目所有者/管理员统一维护，项目内的协同编辑、AI 建议生成将优先选用项目专属通道，保障团队模型的隔离性与数据合规。
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">
                        API 根地址 (API Base URL) <span className="text-rose-500">*</span>
                      </label>
                      <div className="relative">
                        <Globe className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <input
                          type="url"
                          placeholder="https://api.openai.com"
                          value={projectApiUrl}
                          onChange={(e) => setProjectApiUrl(e.target.value)}
                          className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800 font-bold transition-all"
                          required
                        />
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">
                        大模型名称 (Model Name) <span className="text-rose-500">*</span>
                      </label>
                      <div className="relative">
                        <Cpu className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <input
                          type="text"
                          placeholder="gpt-4o"
                          value={projectModelName}
                          onChange={(e) => setProjectModelName(e.target.value)}
                          className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800 font-bold transition-all"
                          required
                        />
                      </div>
                    </div>

                    <div className="space-y-1.5 sm:col-span-2">
                      <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">
                        项目共享密钥 (API Key) <span className="text-rose-500">*</span>
                      </label>
                      <div className="relative">
                        <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <input
                          type="password"
                          placeholder={projectConfig?.configured ? '未更改（请输入新 Key 替换）' : '请输入项目共享 API Key'}
                          value={projectApiKey}
                          onChange={(e) => setProjectApiKey(e.target.value)}
                          className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800 font-bold transition-all"
                          required={!projectConfig?.configured}
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
                      保存项目配置
                    </button>
                    <button
                      type="button"
                      onClick={() => handleTestProject()}
                      disabled={isTestingProject}
                      className="px-5 py-2.5 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 active:scale-[0.99] transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm"
                    >
                      {isTestingProject ? (
                        <span className="h-3.5 w-3.5 rounded-full border-2 border-slate-200 border-t-indigo-600 animate-spin" />
                      ) : (
                        <>
                          <Activity className="w-3.5 h-3.5" />
                          测试连通性
                        </>
                      )}
                    </button>
                    {projectConfig?.configured && (
                      <button
                        type="button"
                        onClick={() => {
                          setIsEditingProject(false);
                          setProjectApiUrl(projectConfig.apiUrl || '');
                          setProjectModelName(projectConfig.modelName || '');
                          setProjectApiKey('');
                          setProjectTestResult(null);
                        }}
                        className="px-5 py-2.5 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 active:scale-[0.99] transition-colors ml-auto cursor-pointer shadow-sm"
                      >
                        取消
                      </button>
                    )}
                  </div>
                </form>
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
                <span className="font-bold">{(activeTab === 'personal' ? testResult!.success : projectTestResult!.success) ? '测试通过' : '测试失败'}</span>
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
