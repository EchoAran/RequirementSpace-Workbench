import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@/store/useAuthStore';
import { workspaceApi } from '@/lib/api';
import { DEFAULT_UI_LOCALE } from '@/i18n';
import {
  getGenerationStrategyPresentation,
  isBuiltinGenerationStrategy,
} from '@/core/generationStrategyPresentation';
import { 
  Database, 
  Cpu, 
  Sliders, 
  Globe, 
  Key, 
  Cpu as CpuIcon, 
  Save, 
  Activity, 
  Trash2, 
  Edit, 
  ArrowLeft,
  Sparkles,
  UploadCloud,
  File,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  Clock,
  XCircle,
  Plus,
  ArrowUp,
  ArrowDown,
  Info
} from 'lucide-react';

interface StrategyItem {
  id: string;
  is_builtin?: boolean;
  label: string;
  description: string;
  instruction: string;
  generation_types: string[];
  enabled: boolean;
  order: number;
}

export function ProjectConfiguration() {
  const { t, i18n } = useTranslation();
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const activeTab = searchParams.get('tab') || 'ai-strategies';

  const {
    ir,
    projectDocuments,
    isUploadingDocument,
    loadProjectDocuments,
    uploadProjectDocument,
    deleteProjectDocument,
    retryProjectDocument,
    toggleDocumentAI,
    projectConfiguration,
    isLoadingProjectConfiguration,
    isSavingGenerationStrategies,
    fetchProjectConfiguration,
    updateProjectGenerationStrategies,
    deleteProjectGenerationStrategies,
    updateProjectKnowledgeConfig,
    updateProjectConfiguration,
  } = useWorkspaceStore();

  const { user } = useAuthStore();
  const [projectMembers, setProjectMembers] = useState<any[]>([]);
  const [contentLocale, setContentLocale] = useState<string>('');
  const [isSavingLocale, setIsSavingLocale] = useState(false);

  const projectName = ir?.projectName || t('common.currentProject');

  // ----------------------------------------------------
  // Shared States / Effects
  // ----------------------------------------------------
  useEffect(() => {
    if (projectId && activeTab === 'knowledge') {
      void loadProjectDocuments();
    }
  }, [projectId, activeTab, loadProjectDocuments]);

  useEffect(() => {
    if (projectId) {
      workspaceApi.listProjectMembers(projectId).then(setProjectMembers).catch(console.error);
    }
  }, [projectId]);

  useEffect(() => {
    if (projectConfiguration) {
      setContentLocale(projectConfiguration.contentLocale || projectConfiguration.content_locale || '');
    }
  }, [projectConfiguration]);

  const currentUserMember = projectMembers.find(m => m.userId === user?.id);
  const isProjectAdmin = currentUserMember?.role === 'owner' || currentUserMember?.role === 'admin';

  const handleSaveLocale = async () => {
    if (!projectId) return;
    setIsSavingLocale(true);
    try {
      await updateProjectConfiguration(projectId, { content_locale: contentLocale || null });
      setConfigSuccess(t('projectConfig.contentLanguage.saveSuccess'));
      setTimeout(() => setConfigSuccess(null), 3000);
    } catch (err) {
      console.error(err);
      setConfigError(t('projectConfig.contentLanguage.saveError'));
      setTimeout(() => setConfigError(null), 3000);
    } finally {
      setIsSavingLocale(false);
    }
  };

  const handleTabChange = (tab: string) => {
    setSearchParams({ tab });
  };

  // ----------------------------------------------------
  // Tab 1: AI Generation Strategy States & Handlers
  // ----------------------------------------------------
  const [customStrategyEnabled, setCustomStrategyEnabled] = useState(true);
  const [candidateCount, setCandidateCount] = useState<number>(2);
  const [strategies, setStrategies] = useState<StrategyItem[]>([]);
  const [knowledgeEnabled, setKnowledgeEnabled] = useState(true);
  const [configError, setConfigError] = useState<string | null>(null);
  const [configSuccess, setConfigSuccess] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({
    label: '',
    description: '',
    instruction: '',
  });
  const [editFormErrors, setEditFormErrors] = useState<{
    label?: string;
    description?: string;
    instruction?: string;
  }>({});

  useEffect(() => {
    if (projectId) {
      void fetchProjectConfiguration(projectId);
    }
  }, [projectId, fetchProjectConfiguration]);

  useEffect(() => {
    if (projectConfiguration) {
      setCustomStrategyEnabled(projectConfiguration.generation_strategy.enabled);
      setCandidateCount(projectConfiguration.generation_strategy.candidate_count);
      setStrategies(projectConfiguration.generation_strategy.strategies);
      setKnowledgeEnabled(projectConfiguration.knowledge.enabled);
    }
  }, [projectConfiguration]);

  const handleToggleStrategy = (id: string) => {
    setStrategies(prev => {
      const updated = prev.map(s => s.id === id ? { ...s, enabled: !s.enabled } : s);
      const enabledCount = updated.filter(s => s.enabled).length;
      if (candidateCount > enabledCount) {
        setCandidateCount(Math.max(1, enabledCount));
      }
      return updated;
    });
  };

  const handleMoveStrategy = (index: number, direction: 'up' | 'down') => {
    if (direction === 'up' && index === 0) return;
    if (direction === 'down' && index === strategies.length - 1) return;
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    const updated = [...strategies];
    const temp = updated[index];
    updated[index] = updated[targetIndex];
    updated[targetIndex] = temp;
    setStrategies(updated.map((s, idx) => ({ ...s, order: idx })));
  };

  const handleToggleKnowledgeEnabled = async () => {
    if (!projectId) return;
    const newValue = !knowledgeEnabled;
    setKnowledgeEnabled(newValue);
    try {
      await updateProjectKnowledgeConfig(projectId, { enabled: newValue });
    } catch (err) {
      console.error('Failed to update project knowledge config:', err);
      setKnowledgeEnabled(!newValue);
      alert(t('projectConfig.strategies.kbSwitchError'));
    }
  };

  const handleSaveStrategies = async () => {
    if (!projectId) return;
    setConfigError(null);
    setConfigSuccess(null);
    try {
      await updateProjectGenerationStrategies(projectId, {
        enabled: customStrategyEnabled,
        candidate_count: candidateCount,
        strategies
      });
      setConfigSuccess(t('projectConfig.strategies.saveSuccess'));
    } catch (err: any) {
      console.error('Failed to save strategy configs:', err);
      const detail = err.response?.data?.detail || err.message || t('common.unknownError');
      const errMsgMap: Record<string, string> = {
        'insufficient_enabled_strategies': t('projectConfig.strategies.errorsMap.insufficient_enabled_strategies'),
        'too_many_enabled_strategies': t('projectConfig.strategies.errorsMap.too_many_enabled_strategies'),
        'duplicate_strategy_id': t('projectConfig.strategies.errorsMap.duplicate_strategy_id'),
        'control_characters_detected': t('projectConfig.strategies.errorsMap.control_characters_detected'),
        'strategy_prompt_injection_detected': t('projectConfig.strategies.errorsMap.strategy_prompt_injection_detected')
      };
      setConfigError(`${t('projectConfig.strategies.saveError')}：${errMsgMap[detail] || detail}`);
    }
  };

  const handleResetStrategies = async () => {
    if (!projectId) return;
    if (!confirm(t('projectConfig.strategies.resetConfirm'))) return;
    setConfigError(null);
    setConfigSuccess(null);
    try {
      await deleteProjectGenerationStrategies(projectId);
      setConfigSuccess(t('projectConfig.strategies.resetSuccess'));
    } catch (err: any) {
      console.error('Failed to reset strategy configs:', err);
      setConfigError(`${t('projectConfig.strategies.saveError')}：${err.message || t('common.unknownError')}`);
    }
  };

  const startEdit = (strategy: StrategyItem) => {
    const presentation = getGenerationStrategyPresentation(strategy, t);
    setEditingId(strategy.id);
    setEditFormErrors({});
    setEditForm({
      label: presentation.label,
      description: presentation.description,
      instruction: presentation.instruction,
    });
  };

  const saveEdit = (id: string) => {
    // Local validation
    const errors: { label?: string; description?: string; instruction?: string } = {};
    const labelLen = editForm.label.trim().length;
    const descLen = editForm.description.trim().length;
    const instrLen = editForm.instruction.trim().length;
    if (labelLen < 2) errors.label = t('projectConfig.strategies.errors.labelMin');
    if (labelLen > 20) errors.label = t('projectConfig.strategies.errors.labelMax');
    if (descLen > 120) errors.description = t('projectConfig.strategies.errors.descMax');
    if (instrLen < 20) errors.instruction = t('projectConfig.strategies.errors.instrMin');
    if (instrLen > 800) errors.instruction = t('projectConfig.strategies.errors.instrMax');

    if (Object.keys(errors).length > 0) {
      setEditFormErrors(errors);
      return;
    }
    setEditFormErrors({});
    setStrategies(prev => prev.map(s => s.id === id ? { ...s, ...editForm, is_builtin: false } : s));
    setEditingId(null);
  };

  const handleAddCustomStrategy = () => {
    const newId = `custom_${Date.now()}`;
    const newStrategy: StrategyItem = {
      id: newId,
      is_builtin: false,
      label: t('projectConfig.strategies.placeholders.label'),
      description: t('projectConfig.strategies.placeholders.desc'),
      instruction: t('projectConfig.strategies.placeholders.instr'),
      generation_types: ['project_creation', 'actor', 'feature', 'scenario', 'flow', 'scope', 'acceptance_criteria'],
      enabled: true,
      order: strategies.length
    };
    setStrategies(prev => [...prev, newStrategy]);
  };

  const handleDeleteStrategy = (id: string) => {
    setStrategies(prev => {
      const updated = prev.filter(s => s.id !== id);
      return updated.map((s, idx) => ({ ...s, order: idx }));
    });
  };

  // ----------------------------------------------------
  // Tab 2: Project Knowledge Base States & Handlers (Ported)
  // ----------------------------------------------------
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [deleteTargetName, setDeleteTargetName] = useState<string | null>(null);

  // Polling for processing documents
  const docStatusesKey = projectDocuments.map((d) => `${d.public_id}:${d.status}`).join(',');
  useEffect(() => {
    if (!projectId || activeTab !== 'knowledge') return;

    const hasProcessing = projectDocuments.some(
      (doc) => doc.status === 'uploaded' || doc.status === 'converting'
    );
    if (!hasProcessing) return;

    const timer = setInterval(() => {
      void loadProjectDocuments();
    }, 3000);

    return () => clearInterval(timer);
  }, [projectId, activeTab, docStatusesKey, loadProjectDocuments]);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      for (let i = 0; i < e.dataTransfer.files.length; i++) {
        await uploadProjectDocument(e.dataTransfer.files[i]);
      }
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      for (let i = 0; i < e.target.files.length; i++) {
        await uploadProjectDocument(e.target.files[i]);
      }
    }
  };

  const confirmDelete = (docId: string, filename: string) => {
    setDeleteTargetId(docId);
    setDeleteTargetName(filename);
  };

  const handleDeleteDoc = async () => {
    if (deleteTargetId) {
      await deleteProjectDocument(deleteTargetId);
      setDeleteTargetId(null);
      setDeleteTargetName(null);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
    return d.toLocaleDateString(i18n.language || DEFAULT_UI_LOCALE, {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateStr;
    }
  };

  // ----------------------------------------------------
  // Tab 3: Team LLM Config States & Handlers (Ported)
  // ----------------------------------------------------
  const [projectLLMConfig, setProjectLLMConfig] = useState<any | null>(null);
  const [projectApiUrl, setProjectApiUrl] = useState('');
  const [projectApiKey, setProjectApiKey] = useState('');
  const [projectModelName, setProjectModelName] = useState('');
  const [isEditingLLM, setIsEditingLLM] = useState(false);
  const [isTestingLLM, setIsTestingLLM] = useState(false);
  const [llmTestResult, setLlmTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [llmIsLoading, setLlmIsLoading] = useState(true);
  const [llmActionError, setLlmActionError] = useState<string | null>(null);
  const [llmActionSuccess, setLlmActionSuccess] = useState<string | null>(null);

  const fetchProjectLLMConfig = async () => {
    if (!projectId) return;
    setLlmIsLoading(true);
    try {
      const data = await workspaceApi.getProjectLLMConfig(projectId);
      setProjectLLMConfig(data);
      if (data?.configured) {
        setProjectApiUrl(data.apiUrl || '');
        setProjectModelName(data.modelName || '');
        setProjectApiKey('');
        setIsEditingLLM(false);
      } else {
        setProjectApiUrl('');
        setProjectModelName('');
        setProjectApiKey('');
        setIsEditingLLM(true);
      }
    } catch (err) {
      console.error('Failed to fetch project LLM config:', err);
    } finally {
      setLlmIsLoading(false);
    }
  };

  useEffect(() => {
    if (projectId && activeTab === 'llm') {
      void fetchProjectLLMConfig();
    }
  }, [projectId, activeTab]);

  const handleTestLLM = async () => {
    if (!projectId) return;
    setIsTestingLLM(true);
    setLlmTestResult(null);
    try {
      let res;
      if (isEditingLLM) {
        res = await workspaceApi.testProjectLLMConfig(projectId, {
          api_url: projectApiUrl,
          model_name: projectModelName,
          api_key: projectApiKey || '',
        });
      } else {
        res = await workspaceApi.testProjectLLMConfig(projectId, {
          api_url: projectLLMConfig?.apiUrl || '',
          api_key: '',
          model_name: projectLLMConfig?.modelName || '',
        });
      }

      if (res.success) {
        setLlmTestResult({ success: true, message: t('projectConfig.llmConfig.connectionSuccessDetail') });
      } else {
        setLlmTestResult({ success: false, message: res.error_detail || res.message || t('projectConfig.llmConfig.connectionFailedDetail') });
      }
    } catch (err: any) {
      setLlmTestResult({ success: false, message: err?.message || t('projectConfig.llmConfig.connectionException') });
    } finally {
      setIsTestingLLM(false);
    }
  };

  const handleSaveLLM = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectId) return;
    setLlmActionError(null);
    setLlmActionSuccess(null);
    try {
      const updated = await workspaceApi.updateProjectLLMConfig(projectId, {
        api_url: projectApiUrl,
        model_name: projectModelName,
        api_key: projectApiKey || '',
      });
      setProjectLLMConfig(updated);
      setProjectApiUrl(updated.apiUrl || updated.api_url || '');
      setProjectModelName(updated.modelName || updated.model_name || '');
      setProjectApiKey('');
      setIsEditingLLM(false);
      setLlmActionSuccess(t('projectConfig.llmConfig.saveSuccess'));
      setTimeout(() => setLlmActionSuccess(null), 3000);
    } catch (err: any) {
      setLlmActionError(err?.response?.data?.detail || err?.message || t('projectConfig.llmConfig.saveError'));
    }
  };

  const handleDeleteLLM = async () => {
    if (!projectId) return;
    const confirm = window.confirm(t('projectConfig.llmConfig.clearConfirm'));
    if (!confirm) return;

    setLlmActionError(null);
    setLlmActionSuccess(null);
    try {
      await workspaceApi.deleteProjectLLMConfig(projectId);
      setProjectLLMConfig(null);
      setProjectApiUrl('');
      setProjectModelName('');
      setProjectApiKey('');
      setIsEditingLLM(true);
      setLlmActionSuccess(t('projectConfig.llmConfig.clearSuccess'));
      setTimeout(() => setLlmActionSuccess(null), 3000);
    } catch (err: any) {
      setLlmActionError(err?.message || t('projectConfig.llmConfig.clearError'));
    }
  };

  // ----------------------------------------------------
  // Statistics for Knowledge Base
  // ----------------------------------------------------
  const totalSize = projectDocuments.reduce((acc, doc) => acc + doc.file_size, 0);
  const sizePercentage = Math.min((totalSize / (100 * 1024 * 1024)) * 100, 100);
  const activeDocsCount = projectDocuments.filter(d => d.status === 'ready' && d.ai_enabled).length;

  return (
    <div className="flex-1 min-h-screen bg-slate-50 flex flex-col font-sans p-6 overflow-y-auto">
      <div className="max-w-5xl mx-auto w-full space-y-6">
        
        {/* Breadcrumb / Header */}
        <div className="flex flex-col gap-2">
          <button 
            onClick={() => navigate(`/projects/${projectId}/overview`)}
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 font-bold w-fit cursor-pointer bg-transparent border-0"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            {t('nav.backToProjectOverview')}
          </button>
          <div>
            <h1 className="text-xl font-black text-slate-800 tracking-tight flex items-center gap-2">
              {t('projectConfig.title', { projectName })}
            </h1>
            <p className="text-xs text-slate-500 mt-1">
              {t('projectConfig.subtitle')}
            </p>
          </div>
        </div>

        {/* Tab switcher */}
        <div className="flex border-b border-slate-200 pb-px gap-6">
          <button
            onClick={() => handleTabChange('ai-strategies')}
            className={`pb-2.5 px-1 text-xs font-bold border-b-2 transition-all cursor-pointer flex items-center gap-1.5 bg-transparent ${
              activeTab === 'ai-strategies'
                ? 'border-indigo-600 text-indigo-600 font-extrabold'
                : 'border-transparent text-slate-400 hover:text-slate-650'
            }`}
          >
            <Sliders className="w-4 h-4" />
            {t('projectConfig.aiStrategies')}
          </button>
          <button
            onClick={() => handleTabChange('knowledge')}
            className={`pb-2.5 px-1 text-xs font-bold border-b-2 transition-all cursor-pointer flex items-center gap-1.5 bg-transparent ${
              activeTab === 'knowledge'
                ? 'border-indigo-600 text-indigo-600 font-extrabold'
                : 'border-transparent text-slate-400 hover:text-slate-655'
            }`}
          >
            <Database className="w-4 h-4" />
            {t('projectConfig.knowledge')}
          </button>
          <button
            onClick={() => handleTabChange('llm')}
            className={`pb-2.5 px-1 text-xs font-bold border-b-2 transition-all cursor-pointer flex items-center gap-1.5 bg-transparent ${
              activeTab === 'llm'
                ? 'border-indigo-600 text-indigo-600 font-extrabold'
                : 'border-transparent text-slate-400 hover:text-slate-655'
            }`}
          >
            <CpuIcon className="w-4 h-4" />
            {t('projectConfig.llm')}
          </button>
        </div>

        {/* TAB 1: AI GENERATION STRATEGY */}
        {activeTab === 'ai-strategies' && (
          <div className="space-y-6 animate-in fade-in duration-150">
            {/* Warning / Note banner */}
            <div className="p-4 bg-indigo-50 border border-indigo-100 text-indigo-950 rounded-2xl flex items-start gap-3">
              <Info className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <div className="text-xs font-bold text-indigo-800">{t('projectConfig.panelTitle')}</div>
                <div className="text-[11px] leading-relaxed text-slate-600">
                  {t('projectConfig.panelSubtitle')}
                </div>
              </div>
            </div>

            {/* Total Switch Card */}
            <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex items-center justify-between gap-6">
              <div className="space-y-1">
                <div className="text-sm font-extrabold text-slate-800 flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-indigo-500" />
                  {t('projectConfig.switchTitle')}
                </div>
                <p className="text-xs text-slate-400 leading-normal">
                  {t('projectConfig.switchSubtitle')}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setCustomStrategyEnabled(!customStrategyEnabled)}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out outline-none ${
                  customStrategyEnabled ? 'bg-indigo-600' : 'bg-slate-200'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    customStrategyEnabled ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>

            {/* AI Project Content Language Settings Card */}
            <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-4">
              <div className="space-y-1">
                <div className="text-sm font-extrabold text-slate-800">
                  {t('projectConfig.contentLanguage.title')}
                </div>
                <p className="text-xs text-slate-400 leading-normal">
                  {t('projectConfig.contentLanguage.subtitle')}
                </p>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center gap-4 max-w-lg">
                <div className="flex-1 space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    {t('projectConfig.contentLanguage.label')}
                  </label>
                  <select
                    value={contentLocale || ''}
                    onChange={(e) => setContentLocale(e.target.value)}
                    disabled={!isProjectAdmin}
                    className="w-full text-xs text-slate-700 border border-slate-200 rounded-xl px-3.5 py-2.5 bg-white focus:outline-none focus:border-indigo-500 appearance-none transition-colors"
                  >
                    <option value="">{t('projectConfig.contentLanguage.followUserPreference')}</option>
                    <option value="zh-CN">{t('projectConfig.contentLanguage.zh')}</option>
                    <option value="en-US">{t('projectConfig.contentLanguage.en')}</option>
                  </select>
                </div>
                <button
                  type="button"
                  onClick={handleSaveLocale}
                  disabled={!isProjectAdmin || isSavingLocale}
                  className="sm:self-end px-5 py-2.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-xl active:scale-[0.99] transition-colors disabled:opacity-50 cursor-pointer border-0"
                >
                  {isSavingLocale ? t('projectConfig.contentLanguage.saving') : t('projectConfig.contentLanguage.saveBtn')}
                </button>
              </div>

              {!isProjectAdmin && (
                <p className="text-[10px] text-rose-500 font-semibold">
                  {t('projectConfig.contentLanguage.permissionWarning')}
                </p>
              )}
            </div>

            {/* Success/Error Banners */}
            {configSuccess && (
              <div className="p-4 rounded-2xl border bg-emerald-50 border-emerald-100 text-emerald-950 text-xs flex items-start gap-3 animate-in slide-in-from-top-2 duration-200">
                <CheckCircle className="w-4 h-4 text-emerald-650 mt-0.5 shrink-0" />
                <div className="space-y-1">
                  <div className="font-bold text-emerald-800">{t('projectConfig.successTitle')}</div>
                  <p className="leading-relaxed font-medium">{configSuccess}</p>
                </div>
              </div>
            )}
            {configError && (
              <div className="p-4 rounded-2xl border bg-rose-50 border-rose-100 text-rose-950 text-xs flex items-start gap-3 animate-in slide-in-from-top-2 duration-200">
                <AlertTriangle className="w-4 h-4 text-rose-650 mt-0.5 shrink-0" />
                <div className="space-y-1">
                  <div className="font-bold text-rose-800">{t('projectConfig.failTitle')}</div>
                  <p className="leading-relaxed font-medium">{configError}</p>
                </div>
              </div>
            )}

            <div className={!customStrategyEnabled ? 'opacity-50 pointer-events-none select-none relative' : ''}>
              {!customStrategyEnabled && (
                <div className="absolute inset-0 bg-slate-100/10 z-10 rounded-2xl cursor-not-allowed" title={t('projectConfig.strategies.pleaseEnableSwitch')} />
              )}
              {/* Config inputs */}
              <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-6">
                <div className="space-y-2">
                  <h3 className="text-sm font-extrabold text-slate-800">{t('projectConfig.strategies.candidateParamsTitle')}</h3>
                  <p className="text-xs text-slate-400 leading-normal">
                    t('projectConfig.strategies.candidateParamsDesc'){t('projectKnowledge.tableHeader.status')}。
                  </p>
                </div>

                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6 pb-6 border-b border-slate-100">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">
                      {t('projectConfig.strategies.candidateCountLabel')}
                    </label>
                    <div className="flex items-center gap-2">
                      {[1, 2, 3, 4, 5].map((num) => {
                        const enabledStrategiesCount = strategies.filter(s => s.enabled).length;
                        const disabled = num > enabledStrategiesCount;
                        return (
                          <button
                            key={num}
                            type="button"
                            disabled={disabled}
                            onClick={() => setCandidateCount(num)}
                            className={`w-10 h-10 rounded-xl text-xs font-bold transition-all border flex items-center justify-center ${
                              disabled 
                                ? 'opacity-40 cursor-not-allowed bg-slate-50 text-slate-350 border-slate-200/50' 
                                : candidateCount === num
                                  ? 'bg-indigo-600 border-indigo-650 text-white font-black shadow'
                                  : 'bg-white border-slate-200 text-slate-655 hover:bg-slate-50 cursor-pointer'
                            }`}
                          >
                            {num}
                          </button>
                        );
                      })}
                    </div>
                    {strategies.filter(s => s.enabled).length < 5 && (
                      <span className="text-[10px] text-slate-400 block">
                        {t('projectConfig.strategies.increaseCandidateCountHelp')}
                      </span>
                    )}
                  </div>
                </div>

                {/* Strategies management list */}
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <h3 className="text-xs font-black text-slate-400 uppercase tracking-wider">
                      {t('projectConfig.strategies.strategiesListTitle')}
                    </h3>
                    <button
                      type="button"
                      onClick={handleAddCustomStrategy}
                      className="flex items-center gap-1 text-[11px] font-bold text-indigo-600 hover:text-indigo-700 bg-indigo-50 hover:bg-indigo-100/80 px-2.5 py-1 rounded-lg transition-colors cursor-pointer border-0"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      {t('projectConfig.strategies.addCustomStrategyBtn')}
                    </button>
                  </div>

                  <div className="divide-y divide-slate-100 border border-slate-200 rounded-2xl overflow-hidden bg-white">
                    {strategies.map((strategy, index) => {
                      const isEditing = editingId === strategy.id;
                      const isBuiltin = isBuiltinGenerationStrategy(strategy);
                      const presentation = getGenerationStrategyPresentation(strategy, t);

                      return (
                        <div 
                          key={strategy.id} 
                          className={`p-4 flex flex-col items-stretch gap-4 transition-colors ${
                            strategy.enabled ? 'bg-white' : 'bg-slate-50/60 opacity-75'
                          }`}
                        >
                          {isEditing ? (
                            <div className="space-y-3 p-1">
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <div className="space-y-1">
                                  <label className="text-[10px] font-bold text-slate-400 uppercase">{t('projectConfig.strategies.strategyNameLabel')}</label>
                                  <input 
                                    id="edit-form-label"
                                    type="text" 
                                    className={`w-full text-xs font-bold text-slate-800 border rounded-xl px-3 py-2 outline-none focus:ring-1 focus:ring-indigo-500 ${editFormErrors.label ? 'border-red-400 focus:ring-red-400' : 'border-slate-200'}`}
                                    value={editForm.label}
                                    onChange={e => setEditForm(prev => ({ ...prev, label: e.target.value }))}
                                  />
                                  {editFormErrors.label && (
                                    <p className="text-[10px] text-red-500 mt-0.5">{editFormErrors.label}</p>
                                  )}
                                </div>
                                <div className="space-y-1">
                                  <label className="text-[10px] font-bold text-slate-400 uppercase">{t('projectConfig.strategies.strategyDescLabel')}</label>
                                  <input 
                                    id="edit-form-description"
                                    type="text" 
                                    className={`w-full text-xs font-medium text-slate-700 border rounded-xl px-3 py-2 outline-none focus:ring-1 focus:ring-indigo-500 ${editFormErrors.description ? 'border-red-400 focus:ring-red-400' : 'border-slate-200'}`}
                                    value={editForm.description}
                                    onChange={e => setEditForm(prev => ({ ...prev, description: e.target.value }))}
                                  />
                                  {editFormErrors.description && (
                                    <p className="text-[10px] text-red-500 mt-0.5">{editFormErrors.description}</p>
                                  )}
                                </div>
                              </div>
                              <div className="space-y-1">
                                <label className="text-[10px] font-bold text-slate-400 uppercase">{t('projectConfig.strategies.strategyPromptLabel')}</label>
                                <textarea 
                                  id="edit-form-instruction"
                                  className={`w-full h-20 text-xs font-mono text-slate-655 border rounded-xl px-3 py-2 outline-none focus:ring-1 focus:ring-indigo-500 resize-none ${editFormErrors.instruction ? 'border-red-400 focus:ring-red-400' : 'border-slate-200'}`}
                                  value={editForm.instruction}
                                  onChange={e => setEditForm(prev => ({ ...prev, instruction: e.target.value }))}
                                />
                                {editFormErrors.instruction && (
                                  <p className="text-[10px] text-red-500 mt-0.5">{editFormErrors.instruction}</p>
                                )}
                              </div>
                              <div className="flex gap-2 justify-end">
                                <button 
                                  type="button" 
                                  onClick={() => saveEdit(strategy.id)}
                                  className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-[10px] font-bold hover:bg-indigo-700 transition-colors cursor-pointer border-0"
                                >
                                  {t('projectConfig.strategies.confirmBtn')}
                                </button>
                                <button 
                                  type="button" 
                                  onClick={() => setEditingId(null)}
                                  className="px-3 py-1.5 bg-slate-50 border border-slate-200 text-slate-650 rounded-lg text-[10px] font-bold hover:bg-slate-100 transition-colors cursor-pointer"
                                >
                                  {t('projectConfig.llmConfig.cancelBtn')}
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                              <div className="space-y-1 overflow-hidden flex-1">
                                <div className="flex items-center gap-2">
                                  <span className="text-xs font-extrabold text-slate-800">{presentation.label}</span>
                                  {isBuiltin ? (
                                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-slate-500 scale-95 origin-left whitespace-nowrap">{t('projectConfig.strategies.builtinBadge')}</span>
                                  ) : (
                                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-indigo-50 border border-indigo-100 text-indigo-650 scale-95 origin-left whitespace-nowrap">{t('projectConfig.strategies.customBadge')}</span>
                                  )}
                                </div>
                                <p className="text-xs text-slate-500 leading-normal truncate" title={presentation.description}>
                                  {presentation.description}
                                </p>
                                <div className="text-[10px] text-slate-400 bg-slate-50 p-2 rounded-lg border border-slate-100/60 mt-1 max-w-2xl font-mono leading-relaxed">
                                  <span className="font-bold text-slate-500 text-[9px] block mb-0.5">{t('projectConfig.strategies.promptLabelColon')}</span>
                                  {presentation.instruction}
                                </div>
                              </div>

                              <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                                {/* Edit and delete for custom strategies */}
                                <div className="flex gap-1 mr-1">
                                  <button
                                    type="button"
                                    onClick={() => startEdit(strategy)}
                                    title={t('projectConfig.strategies.editStrategyTooltip')}
                                    className="p-1.5 bg-slate-50 text-slate-500 hover:text-indigo-650 hover:bg-indigo-50 rounded-lg transition-colors cursor-pointer border-0"
                                  >
                                    <Edit className="w-3.5 h-3.5" />
                                  </button>
                                  {!isBuiltin && (
                                    <button
                                      type="button"
                                      onClick={() => handleDeleteStrategy(strategy.id)}
                                      title={t('projectConfig.strategies.deleteStrategyTooltip')}
                                      className="p-1.5 bg-slate-50 text-slate-500 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer border-0"
                                    >
                                      <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                  )}
                                </div>

                                {/* Order adjustment */}
                                <div className="flex border border-slate-200 rounded-lg overflow-hidden shrink-0">
                                  <button
                                    type="button"
                                    disabled={index === 0}
                                    onClick={() => handleMoveStrategy(index, 'up')}
                                    className="p-1.5 bg-white text-slate-400 hover:text-slate-650 disabled:opacity-30 disabled:hover:text-slate-400 cursor-pointer border-0 border-r border-slate-150"
                                  >
                                    <ArrowUp className="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    type="button"
                                    disabled={index === strategies.length - 1}
                                    onClick={() => handleMoveStrategy(index, 'down')}
                                    className="p-1.5 bg-white text-slate-400 hover:text-slate-655 disabled:opacity-30 disabled:hover:text-slate-400 cursor-pointer border-0"
                                  >
                                    <ArrowDown className="w-3.5 h-3.5" />
                                  </button>
                                </div>

                                {/* Toggle switch */}
                                <button
                                  type="button"
                                  onClick={() => handleToggleStrategy(strategy.id)}
                                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out outline-none shrink-0 ${
                                    strategy.enabled ? 'bg-indigo-600' : 'bg-slate-200'
                                  }`}
                                >
                                  <span
                                    className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                                      strategy.enabled ? 'translate-x-4' : 'translate-x-0'
                                    }`}
                                  />
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom action bar */}
            <div className="flex items-center gap-3 pt-4">
              <button
                type="button"
                onClick={handleSaveStrategies}
                disabled={isSavingGenerationStrategies}
                className="px-5 py-2.5 bg-indigo-600 text-white text-xs font-bold rounded-xl hover:bg-indigo-700 active:scale-[0.99] transition-colors flex items-center gap-1.5 shadow-md shadow-indigo-650/10 cursor-pointer border-0"
              >
                <Save className="w-3.5 h-3.5" />
                {t('projectConfig.strategies.saveStrategies')}
              </button>
              <button
                type="button"
                onClick={handleResetStrategies}
                disabled={isSavingGenerationStrategies}
                className="px-5 py-2.5 border border-slate-200 bg-white text-slate-655 text-xs font-bold rounded-xl hover:bg-slate-50 active:scale-[0.99] transition-colors cursor-pointer shadow-sm"
              >
                {t('projectConfig.strategies.resetToDefault')}
              </button>
            </div>
          </div>
        )}

        {/* TAB 2: PROJECT KNOWLEDGE BASE */}
        {activeTab === 'knowledge' && (
          <div className="space-y-6 animate-in fade-in duration-150">
            {/* Total Switch Card */}
            <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex items-center justify-between gap-6 animate-in fade-in duration-150">
              <div className="space-y-1">
                <div className="text-sm font-extrabold text-slate-800 flex items-center gap-2">
                  <Database className="w-4 h-4 text-indigo-500" />
                  {t('projectConfig.strategies.kbSwitchLabel')}
                </div>
                <p className="text-xs text-slate-400 leading-normal">
                  {t('projectConfig.strategies.kbSwitchDesc')}
                </p>
              </div>
              <button
                type="button"
                onClick={handleToggleKnowledgeEnabled}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out outline-none ${
                  knowledgeEnabled ? 'bg-indigo-600' : 'bg-slate-200'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    knowledgeEnabled ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>

            <div className={!knowledgeEnabled ? 'space-y-6 opacity-75' : 'space-y-6'}>
              {/* Dashboard Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                {/* Card 1: Documents count */}
                <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col justify-between">
                  <span className="text-xs font-bold text-slate-500 tracking-wide">{t('projectKnowledge.docTotalCountLabel')}</span>
                  <div className="flex items-baseline gap-2 mt-2">
                    <span className="text-3xl font-black text-slate-800">{projectDocuments.length}</span>
                    <span className="text-xs text-slate-400">{t('projectKnowledge.uploadedCountLabel')}</span>
                  </div>
                  <div className="text-[10px] text-slate-400 mt-2">{t('projectKnowledge.unreadyFailedNotice')}</div>
                </div>

                {/* Card 2: Space occupied */}
                <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col justify-between">
                  <span className="text-xs font-bold text-slate-500 tracking-wide">{t('projectKnowledge.storageUsed')}</span>
                  <div className="mt-2">
                    <div className="flex items-baseline gap-2">
                      <span className="text-3xl font-black text-slate-800">{formatBytes(totalSize)}</span>
                      <span className="text-xs text-slate-400">/ 100 MB</span>
                    </div>
                    <div className="w-full bg-slate-100 h-2 rounded-full mt-2 overflow-hidden">
                      <div 
                        className="bg-indigo-500 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${sizePercentage}%` }}
                      />
                    </div>
                  </div>
                  <div className="text-[10px] text-slate-400 mt-2">{t('projectKnowledge.maxFileSizeNotice')}</div>
                </div>

                {/* Card 3: AI reference status */}
                <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col justify-between">
                  <span className="text-xs font-bold text-slate-500 tracking-wide">{t('projectKnowledge.aiSearchEnabledLabel')}</span>
                  <div className="flex items-baseline gap-2 mt-2">
                    <span className="text-3xl font-black text-emerald-600">{activeDocsCount}</span>
                    <span className="text-xs text-slate-400">{t('projectKnowledge.readyDocsLabel')}</span>
                  </div>
                  <div className="text-[10px] text-slate-400 mt-2 flex items-center gap-1">
                    <Sparkles className="w-3 h-3 text-indigo-500 shrink-0" />
                    <span>{t('projectKnowledge.aiSearchNotice')}</span>
                  </div>
                </div>
              </div>

              {/* Upload Container */}
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden p-6 space-y-4">
                <div
                  onDragEnter={handleDrag}
                  onDragOver={handleDrag}
                  onDragLeave={handleDrag}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-200 flex flex-col items-center justify-center gap-2.5 ${
                    dragActive 
                      ? 'border-indigo-500 bg-indigo-50/50' 
                      : 'border-slate-200 bg-slate-50/50 hover:bg-slate-50 hover:border-slate-300'
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    onChange={handleFileChange}
                    className="hidden"
                    accept=".txt,.md,.pdf,.docx,.xlsx"
                  />
                  {isUploadingDocument ? (
                    <RefreshCw className="w-10 h-10 text-indigo-500 animate-spin" />
                  ) : (
                    <UploadCloud className="w-10 h-10 text-slate-400" />
                  )}
                  <div className="space-y-1">
                    <div className="text-sm font-bold text-slate-700">
                      {isUploadingDocument ? t('projectKnowledge.uploadingText') : t('projectKnowledge.dragDropNotice')}
                    </div>
                    <div className="text-xs text-slate-400">
                      {t('projectKnowledge.supportedFormats')}
                    </div>
                  </div>
                </div>
              </div>



            {/* Documents Table */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
                <span className="text-xs font-bold text-slate-700 tracking-wide">{t('projectKnowledge.uploadedListTitle')}</span>
                <span className="text-[10px] text-slate-400">{t('projectKnowledge.totalDocsCount', { count: projectDocuments.length })}</span>
              </div>

              {projectDocuments.length === 0 ? (
                <div className="p-12 text-center text-slate-400 space-y-2">
                  <File className="w-8 h-8 mx-auto text-slate-300" />
                  <div className="text-xs font-bold">{t('projectKnowledge.status.unready')}</div>
                  <div className="text-[10px] max-w-xs mx-auto leading-normal">
                    {t('projectKnowledge.pageSubtitle')}
                  </div>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-slate-100 text-slate-400 font-bold uppercase tracking-wider text-[10px] bg-slate-50/20">
                        <th className="py-3 px-6">{t('projectKnowledge.tableHeader.file')}</th>
                        <th className="py-3 px-4">{t('projectKnowledge.tableHeader.status')}</th>
                        <th className="py-3 px-4">{t('projectKnowledge.tableHeader.size')}</th>
                        <th className="py-3 px-4">{t('projectKnowledge.tableHeader.uploadedTime')}</th>
                        <th className="py-3 px-4 text-center">{t('projectKnowledge.tableHeader.joinAI')}</th>
                        <th className="py-3 px-6 text-right">{t('projectKnowledge.tableHeader.actions')}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {projectDocuments.map((doc) => {
                        const isReady = doc.status === 'ready';
                        const isProcessing = doc.status === 'uploaded' || doc.status === 'converting';
                        const isFailed = doc.status === 'failed';

                        return (
                          <tr key={doc.public_id} className="hover:bg-slate-50/80 transition-colors">
                            <td className="py-4 px-6 flex items-center gap-3 overflow-hidden min-w-[200px]">
                              <File className="w-4 h-4 text-slate-400 shrink-0" />
                              <div className="overflow-hidden">
                                <div className="font-semibold text-slate-700 truncate" title={doc.original_filename}>
                                  {doc.original_filename}
                                </div>
                              </div>
                            </td>

                            <td className="py-4 px-4 whitespace-nowrap">
                              {isReady && (
                                <span className="inline-flex items-center gap-1.5 bg-emerald-50 text-emerald-700 font-bold border border-emerald-100 px-2.5 py-0.5 rounded-lg text-[10px]">
                                  <CheckCircle className="w-3 h-3 text-emerald-600" />
                                  {t('projectKnowledge.status.ready')}
                                </span>
                              )}

                              {isProcessing && (
                                <span className="inline-flex items-center gap-1.5 bg-amber-50 text-amber-700 font-bold border border-amber-100 px-2.5 py-0.5 rounded-lg text-[10px] animate-pulse">
                                  <Clock className="w-3 h-3 text-amber-500 animate-spin" />
                                  {t('projectKnowledge.status.converting')}
                                </span>
                              )}

                              {isFailed && (
                                <span 
                                  className="inline-flex items-center gap-1.5 bg-rose-50 text-rose-700 font-bold border border-rose-100 px-2.5 py-0.5 rounded-lg text-[10px] cursor-help"
                                  title={doc.error_message || t('projectKnowledge.status.failedTooltip')}
                                >
                                  <XCircle className="w-3 h-3 text-rose-500" />
                                  {t('projectKnowledge.status.failed')}
                                </span>
                              )}
                            </td>

                            <td className="py-4 px-4 text-slate-500 font-medium whitespace-nowrap">
                              {formatBytes(doc.file_size)}
                            </td>

                            <td className="py-4 px-4 text-slate-400 font-medium whitespace-nowrap">
                              {formatDate(doc.created_at)}
                            </td>

                            <td className="py-4 px-4 text-center">
                              {isReady ? (
                                <button
                                  type="button"
                                  onClick={() => void toggleDocumentAI(doc.public_id, !doc.ai_enabled)}
                                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out outline-none ${
                                    doc.ai_enabled ? 'bg-indigo-600' : 'bg-slate-200'
                                  }`}
                                >
                                  <span
                                    className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                                      doc.ai_enabled ? 'translate-x-4' : 'translate-x-0'
                                    }`}
                                  />
                                </button>
                              ) : (
                                <span className="text-[10px] text-slate-300">{t('projectKnowledge.status.unready')}</span>
                              )}
                            </td>

                            <td className="py-4 px-6 text-right whitespace-nowrap">
                              <div className="flex items-center justify-end gap-1.5">
                                {isFailed && (
                                  <button
                                    type="button"
                                    onClick={() => void retryProjectDocument(doc.public_id)}
                                    className="p-1.5 hover:bg-slate-100 text-slate-400 hover:text-indigo-600 rounded-lg transition-colors border-0 bg-transparent"
                                    title={t('projectKnowledge.actionTooltip.retry')}
                                  >
                                    <RefreshCw className="w-4 h-4" />
                                  </button>
                                )}
                                <button
                                  type="button"
                                  onClick={() => confirmDelete(doc.public_id, doc.original_filename)}
                                  className="p-1.5 hover:bg-slate-100 text-slate-400 hover:text-rose-600 rounded-lg transition-colors border-0 bg-transparent"
                                  title={t('projectKnowledge.actionTooltip.delete')}
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

        {/* TAB 3: TEAM LLM CONFIG */}
        {activeTab === 'llm' && (
          <div className="space-y-6 animate-in fade-in duration-150">
            <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-6">
              
              {/* Warnings & Success banners */}
              {llmActionSuccess && (
                <div className="p-3 bg-emerald-50 border border-emerald-100 text-emerald-800 text-xs font-semibold rounded-xl flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-emerald-600" />
                  <span>{llmActionSuccess}</span>
                </div>
              )}

              {llmActionError && (
                <div className="p-3 bg-rose-50 border border-rose-100 text-rose-600 text-xs font-semibold rounded-xl flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-500" />
                  <span>{llmActionError}</span>
                </div>
              )}

              {/* Loader */}
              {llmIsLoading ? (
                <div className="flex flex-col items-center justify-center py-10 space-y-3">
                  <RefreshCw className="h-8 w-8 text-indigo-500 animate-spin" />
                  <span className="text-xs text-slate-400 font-medium">{t('projectConfig.llmConfig.loading')}</span>
                </div>
              ) : (
                <>
                  {/* Current config view */}
                  {!isEditingLLM && projectLLMConfig?.configured && (
                    <div className="space-y-5">
                      <div className="p-4 bg-emerald-50 border border-emerald-100 text-emerald-950 rounded-2xl space-y-3">
                        <h3 className="text-sm font-bold flex items-center gap-1.5 text-emerald-800">
                          <CheckCircle className="w-4 h-4 text-emerald-600" />
                          {t('projectConfig.llmConfig.successNotice')}
                        </h3>
                        <p className="text-xs leading-relaxed text-slate-655 font-medium">
                          {t('projectConfig.llmConfig.description')}
                        </p>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 bg-slate-50 p-5 border border-slate-100 rounded-2xl text-xs font-medium">
                        <div className="space-y-1">
                          <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block">{t('projectConfig.llmConfig.apiBaseUrlLabel')}</span>
                          <span className="font-extrabold text-slate-700 truncate block">{projectLLMConfig.apiUrl}</span>
                        </div>
                        <div className="space-y-1">
                          <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block">{t('projectConfig.llmConfig.modelNameLabel')}</span>
                          <span className="font-extrabold text-slate-700 block">{projectLLMConfig.modelName}</span>
                        </div>
                        <div className="space-y-1">
                          <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block">{t('projectConfig.llmConfig.apiKeyLabel')}</span>
                          <span className="font-extrabold text-slate-700">••••••••{projectLLMConfig.apiKeyLast4}</span>
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-3 pt-2">
                        <button
                          type="button"
                          onClick={handleTestLLM}
                          disabled={isTestingLLM}
                          className="px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 active:scale-[0.99] transition-all disabled:opacity-50 flex items-center gap-1.5 cursor-pointer border-0"
                        >
                          {isTestingLLM ? (
                            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <>
                              <Activity className="w-3.5 h-3.5" />
                              {t('projectConfig.llmConfig.testBtn')}
                            </>
                          )}
                        </button>
                        <button
                          type="button"
                          onClick={() => setIsEditingLLM(true)}
                          className="px-4 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 active:scale-[0.99] transition-all flex items-center gap-1.5 cursor-pointer shadow-sm"
                        >
                          <Edit className="w-3.5 h-3.5" />
                          {t('projectConfig.llmConfig.editBtn')}
                        </button>
                        <button
                          type="button"
                          onClick={handleDeleteLLM}
                          className="px-4 py-2 border border-rose-200 bg-rose-50 text-rose-600 text-xs font-bold rounded-xl hover:bg-rose-100 active:scale-[0.99] transition-all flex items-center gap-1.5 ml-auto cursor-pointer"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          {t('projectConfig.llmConfig.clearConfigBtn')}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Form for creation or editing */}
                  {(isEditingLLM || !projectLLMConfig?.configured) && (
                    <form onSubmit={handleSaveLLM} className="space-y-5">
                      <div className="p-4 bg-indigo-50/50 border border-indigo-100 text-indigo-900 rounded-2xl text-xs leading-relaxed">
                        {t('projectConfig.llmConfig.configHelpText')}
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">
                            {t('projectConfig.llmConfig.apiBaseUrlLabelRequired')} <span className="text-rose-500">*</span>
                          </label>
                          <div className="relative">
                            <Globe className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                            <input
                              type="url"
                              placeholder="https://api.openai.com/v1"
                              value={projectApiUrl}
                              onChange={(e) => setProjectApiUrl(e.target.value)}
                              className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800 font-bold transition-all"
                              required
                            />
                          </div>
                        </div>

                        <div className="space-y-1.5">
                          <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">
                            {t('projectConfig.llmConfig.modelNameLabel')} <span className="text-rose-500">*</span>
                          </label>
                          <div className="relative">
                            <Sliders className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                            <input
                              type="text"
                              placeholder="gpt-4o / gemini-1.5-pro"
                              value={projectModelName}
                              onChange={(e) => setProjectModelName(e.target.value)}
                              className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800 font-bold transition-all"
                              required
                            />
                          </div>
                        </div>

                        <div className="space-y-1.5 sm:col-span-2">
                          <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">
                            {t('projectConfig.llmConfig.apiKeyLabelRequired')} <span className="text-rose-500">*</span>
                          </label>
                          <div className="relative">
                            <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                            <input
                              type="password"
                              placeholder={projectLLMConfig?.configured ? t('projectConfig.llmConfig.placeholderModifyKey') : t('projectConfig.llmConfig.placeholderEnterKey')}
                              value={projectApiKey}
                              onChange={(e) => setProjectApiKey(e.target.value)}
                              className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800 font-bold transition-all"
                              required={!projectLLMConfig?.configured}
                            />
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 pt-2">
                        <button
                          type="submit"
                          className="px-5 py-2.5 bg-indigo-600 text-white text-xs font-bold rounded-xl hover:bg-indigo-700 active:scale-[0.99] transition-colors flex items-center gap-1.5 shadow-md shadow-indigo-650/10 cursor-pointer border-0"
                        >
                          <Save className="w-3.5 h-3.5" />
                          {t('projectConfig.llmConfig.saveBtn')}
                        </button>
                        <button
                          type="button"
                          onClick={handleTestLLM}
                          disabled={isTestingLLM}
                          className="px-5 py-2.5 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 active:scale-[0.99] transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm"
                        >
                          {isTestingLLM ? (
                            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <>
                              <Activity className="w-3.5 h-3.5" />
                              {t('projectConfig.llmConfig.testBtn')}
                            </>
                          )}
                        </button>
                        {projectLLMConfig?.configured && (
                          <button
                            type="button"
                            onClick={() => {
                              setIsEditingLLM(false);
                              setProjectApiUrl(projectLLMConfig.apiUrl || '');
                              setProjectModelName(projectLLMConfig.modelName || '');
                              setProjectApiKey('');
                              setLlmTestResult(null);
                            }}
                            className="px-5 py-2.5 border border-slate-200 bg-white text-slate-655 text-xs font-bold rounded-xl hover:bg-slate-50 active:scale-[0.99] transition-colors ml-auto cursor-pointer shadow-sm"
                          >
                            {t('projectConfig.llmConfig.cancelBtn')}
                          </button>
                        )}
                      </div>
                    </form>
                  )}
                </>
              )}

              {/* Connection test result banner */}
              {llmTestResult && (
                <div
                  className={`p-4 rounded-2xl border text-xs flex items-start gap-3 animate-in slide-in-from-top-2 duration-200 ${
                    llmTestResult.success
                      ? 'bg-emerald-50 border-emerald-100 text-emerald-950'
                      : 'bg-rose-50 border-rose-100 text-rose-950'
                  }`}
                >
                  <div className={`p-1 rounded-lg shrink-0 ${llmTestResult.success ? 'bg-emerald-100 text-emerald-600' : 'bg-rose-100 text-rose-600'}`}>
                    {llmTestResult.success ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                  </div>
                  <div className="space-y-1">
                    <div className="font-bold">{llmTestResult.success ? t('projectConfig.llmConfig.connectionSuccess') : t('projectConfig.llmConfig.connectionFailed')}</div>
                    <p className="leading-relaxed font-medium">{llmTestResult.message}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

      </div>

      {/* Delete Confirmation Modal for Knowledge base */}
      {deleteTargetId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-2xl max-w-sm w-full space-y-4 animate-in zoom-in-95 duration-150">
            <div className="flex gap-3 items-start">
              <div className="p-2.5 bg-rose-50 rounded-2xl border border-rose-100 text-rose-600 shrink-0">
                <Trash2 className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-black text-slate-800">{t('projectKnowledge.deleteModal.title')}</h3>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {t('projectKnowledge.deleteModal.confirmPrefix')} <span className="font-semibold text-slate-700">"{deleteTargetName}"</span> {t('projectKnowledge.deleteModal.confirmSuffix')}
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => {
                  setDeleteTargetId(null);
                  setDeleteTargetName(null);
                }}
                className="px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
              >
                {t('projectConfig.llmConfig.cancelBtn')}
              </button>
              <button
                type="button"
                onClick={handleDeleteDoc}
                className="px-4 py-2 bg-rose-600 text-white rounded-xl text-xs font-bold hover:bg-rose-700 shadow-md shadow-rose-100 transition-colors cursor-pointer"
              >
                {t('projectKnowledge.deleteModal.confirmBtn')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
