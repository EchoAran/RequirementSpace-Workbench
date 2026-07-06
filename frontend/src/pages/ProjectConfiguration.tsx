import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { workspaceApi } from '@/lib/api';
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
  label: string;
  description: string;
  instruction: string;
  generation_types: string[];
  enabled: boolean;
  order: number;
}

export function ProjectConfiguration() {
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
  } = useWorkspaceStore();

  const projectName = ir?.projectName || '当前项目';

  // ----------------------------------------------------
  // Shared States / Effects
  // ----------------------------------------------------
  useEffect(() => {
    if (projectId && activeTab === 'knowledge') {
      void loadProjectDocuments();
    }
  }, [projectId, activeTab, loadProjectDocuments]);

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
      alert('更新知识库总开关失败，请重试');
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
      setConfigSuccess('生成策略配置已保存成功！');
    } catch (err: any) {
      console.error('Failed to save strategy configs:', err);
      const detail = err.response?.data?.detail || err.message || '未知错误';
      const errMsgMap: Record<string, string> = {
        'insufficient_enabled_strategies': '启用策略数不足以支持当前的候选方案生成数',
        'too_many_enabled_strategies': '启用的自定义策略数量超过了上限 5 个',
        'duplicate_strategy_id': '策略 ID 重复，请检查列表项目',
        'control_characters_detected': '策略提示词包含非法的控制字符，请重新输入',
        'strategy_prompt_injection_detected': '提示词内容触发了高风险安全策略拦截，禁止覆盖输出格式或忽略历史系统提示'
      };
      setConfigError(`保存策略配置失败：${errMsgMap[detail] || detail}`);
    }
  };

  const handleResetStrategies = async () => {
    if (!projectId) return;
    if (!confirm('确定要恢复系统默认的策略配置吗？恢复后将丢失您在此项目中的所有自定义策略修改。')) return;
    setConfigError(null);
    setConfigSuccess(null);
    try {
      await deleteProjectGenerationStrategies(projectId);
      setConfigSuccess('生成策略已成功重置为系统默认配置！');
    } catch (err: any) {
      console.error('Failed to reset strategy configs:', err);
      setConfigError(`重置配置失败：${err.message || '未知错误'}`);
    }
  };

  const startEdit = (strategy: StrategyItem) => {
    setEditingId(strategy.id);
    setEditFormErrors({});
    setEditForm({
      label: strategy.label,
      description: strategy.description,
      instruction: strategy.instruction,
    });
  };

  const saveEdit = (id: string) => {
    // Local validation
    const errors: { label?: string; description?: string; instruction?: string } = {};
    const labelLen = editForm.label.trim().length;
    const descLen = editForm.description.trim().length;
    const instrLen = editForm.instruction.trim().length;
    if (labelLen < 2) errors.label = '策略名称至少 2 个字符';
    if (labelLen > 20) errors.label = '策略名称不超过 20 个字符';
    if (descLen > 120) errors.description = '策略描述不超过 120 个字符';
    if (instrLen < 20) errors.instruction = '生成侧重点至少 20 个字符';
    if (instrLen > 800) errors.instruction = '生成侧重点不超过 800 个字符';

    if (Object.keys(errors).length > 0) {
      setEditFormErrors(errors);
      return;
    }
    setEditFormErrors({});
    setStrategies(prev => prev.map(s => s.id === id ? { ...s, ...editForm } : s));
    setEditingId(null);
  };

  const handleAddCustomStrategy = () => {
    const newId = `custom_${Date.now()}`;
    const newStrategy: StrategyItem = {
      id: newId,
      label: '自定义生成策略',
      description: '在此修改描述。',
      instruction: '在生成本项目的候选方案时，请重点关注以下业务逻辑要求（必须大于 20 字）。',
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
      return d.toLocaleDateString('zh-CN', {
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
        setLlmTestResult({ success: true, message: '连接测试成功！项目的 LLM 通道一切正常。' });
      } else {
        setLlmTestResult({ success: false, message: res.error_detail || res.message || '连接测试失败，请检查参数设置。' });
      }
    } catch (err: any) {
      setLlmTestResult({ success: false, message: err?.message || '网络连接或服务端异常。' });
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
      setLlmActionSuccess('项目项目 LLM 配置已成功更新！');
      setTimeout(() => setLlmActionSuccess(null), 3000);
    } catch (err: any) {
      setLlmActionError(err?.response?.data?.detail || err?.message || '保存配置失败，请检查参数格式。');
    }
  };

  const handleDeleteLLM = async () => {
    if (!projectId) return;
    const confirm = window.confirm('确定要清除项目的项目 LLM 配置吗？清除后将恢复使用个人配置或系统配置。');
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
      setLlmActionSuccess('项目 LLM 配置已成功清除。');
      setTimeout(() => setLlmActionSuccess(null), 3000);
    } catch (err: any) {
      setLlmActionError(err?.message || '清除配置失败。');
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
            返回项目概览
          </button>
          <div>
            <h1 className="text-xl font-black text-slate-800 tracking-tight flex items-center gap-2">
              项目配置 — {projectName}
            </h1>
            <p className="text-xs text-slate-500 mt-1">
              管理当前项目内特定的 AI 生成侧重策略、参考知识库文档以及专属的大语言模型通道参数。
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
            AI 生成策略
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
            项目知识库
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
            项目 LLM 配置
          </button>
        </div>

        {/* TAB 1: AI GENERATION STRATEGY */}
        {activeTab === 'ai-strategies' && (
          <div className="space-y-6 animate-in fade-in duration-150">
            {/* Warning / Note banner */}
            <div className="p-4 bg-indigo-50 border border-indigo-100 text-indigo-950 rounded-2xl flex items-start gap-3">
              <Info className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <div className="text-xs font-bold text-indigo-800">生成策略控制面板</div>
                <div className="text-[11px] leading-relaxed text-slate-600">
                  可针对当前项目单独开启或关闭某些特定生成方向，并调整并发生成的候选方案总数。自定义策略及排序对 LLM 生成偏好的约束已全面支持。
                </div>
              </div>
            </div>

            {/* Total Switch Card */}
            <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex items-center justify-between gap-6">
              <div className="space-y-1">
                <div className="text-sm font-extrabold text-slate-800 flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-indigo-500" />
                  自定义生成策略总开关
                </div>
                <p className="text-xs text-slate-400 leading-normal">
                  开启后，项目生成候选将遵守下方配置的候选方案参数和排序后的策略指令。关闭后，将完全回退至系统内置默认策略。
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

            {/* Success/Error Banners */}
            {configSuccess && (
              <div className="p-4 rounded-2xl border bg-emerald-50 border-emerald-100 text-emerald-950 text-xs flex items-start gap-3 animate-in slide-in-from-top-2 duration-200">
                <CheckCircle className="w-4 h-4 text-emerald-650 mt-0.5 shrink-0" />
                <div className="space-y-1">
                  <div className="font-bold text-emerald-800">保存成功</div>
                  <p className="leading-relaxed font-medium">{configSuccess}</p>
                </div>
              </div>
            )}
            {configError && (
              <div className="p-4 rounded-2xl border bg-rose-50 border-rose-100 text-rose-950 text-xs flex items-start gap-3 animate-in slide-in-from-top-2 duration-200">
                <AlertTriangle className="w-4 h-4 text-rose-650 mt-0.5 shrink-0" />
                <div className="space-y-1">
                  <div className="font-bold text-rose-800">操作失败</div>
                  <p className="leading-relaxed font-medium">{configError}</p>
                </div>
              </div>
            )}

            <div className={!customStrategyEnabled ? 'opacity-50 pointer-events-none select-none relative' : ''}>
              {!customStrategyEnabled && (
                <div className="absolute inset-0 bg-slate-100/10 z-10 rounded-2xl cursor-not-allowed" title="请先开启自定义生成策略总开关" />
              )}
              {/* Config inputs */}
              <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-6">
                <div className="space-y-2">
                  <h3 className="text-sm font-extrabold text-slate-800">候选方案生成参数</h3>
                  <p className="text-xs text-slate-400 leading-normal">
                    多候选方案生成时的候选总数上限与首选项。配置生成 N 个候选时，必须至少有 N 个生成策略处于“启用”状态。
                  </p>
                </div>

                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6 pb-6 border-b border-slate-100">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">
                      候选方案数量 (Candidate Count)
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
                        增加候选数量上限需先在下方启用对应的策略项。
                      </span>
                    )}
                  </div>
                </div>

                {/* Strategies management list */}
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <h3 className="text-xs font-black text-slate-400 uppercase tracking-wider">
                      生成策略列表 (已按优先级排序)
                    </h3>
                    <button
                      type="button"
                      onClick={handleAddCustomStrategy}
                      className="flex items-center gap-1 text-[11px] font-bold text-indigo-600 hover:text-indigo-700 bg-indigo-50 hover:bg-indigo-100/80 px-2.5 py-1 rounded-lg transition-colors cursor-pointer border-0"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      新增自定义策略
                    </button>
                  </div>

                  <div className="divide-y divide-slate-100 border border-slate-200 rounded-2xl overflow-hidden bg-white">
                    {strategies.map((strategy, index) => {
                      const isEditing = editingId === strategy.id;
                      const isBuiltin = strategy.id === 'balanced' || strategy.id === 'comprehensive' || strategy.id === 'minimal' || strategy.id === 'risk_averse' || strategy.id === 'workflow_first';

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
                                  <label className="text-[10px] font-bold text-slate-400 uppercase">策略名称</label>
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
                                  <label className="text-[10px] font-bold text-slate-400 uppercase">策略描述</label>
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
                                <label className="text-[10px] font-bold text-slate-400 uppercase">Prompt 指令 / 侧重点 (长度限制 20-800)</label>
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
                                  确定
                                </button>
                                <button 
                                  type="button" 
                                  onClick={() => setEditingId(null)}
                                  className="px-3 py-1.5 bg-slate-50 border border-slate-200 text-slate-650 rounded-lg text-[10px] font-bold hover:bg-slate-100 transition-colors cursor-pointer"
                                >
                                  取消
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                              <div className="space-y-1 overflow-hidden flex-1">
                                <div className="flex items-center gap-2">
                                  <span className="text-xs font-extrabold text-slate-800">{strategy.label}</span>
                                  {isBuiltin ? (
                                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-slate-500 scale-95 origin-left whitespace-nowrap">系统默认</span>
                                  ) : (
                                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-indigo-50 border border-indigo-100 text-indigo-650 scale-95 origin-left whitespace-nowrap">自定义</span>
                                  )}
                                </div>
                                <p className="text-xs text-slate-500 leading-normal truncate" title={strategy.description}>
                                  {strategy.description}
                                </p>
                                <div className="text-[10px] text-slate-400 bg-slate-50 p-2 rounded-lg border border-slate-100/60 mt-1 max-w-2xl font-mono leading-relaxed">
                                  <span className="font-bold text-slate-500 text-[9px] block mb-0.5">Prompt 指令：</span>
                                  {strategy.instruction}
                                </div>
                              </div>

                              <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                                {/* Edit and delete for custom strategies */}
                                <div className="flex gap-1 mr-1">
                                  <button
                                    type="button"
                                    onClick={() => startEdit(strategy)}
                                    title="编辑策略"
                                    className="p-1.5 bg-slate-50 text-slate-500 hover:text-indigo-650 hover:bg-indigo-50 rounded-lg transition-colors cursor-pointer border-0"
                                  >
                                    <Edit className="w-3.5 h-3.5" />
                                  </button>
                                  {!isBuiltin && (
                                    <button
                                      type="button"
                                      onClick={() => handleDeleteStrategy(strategy.id)}
                                      title="删除自定义策略"
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
                保存策略配置
              </button>
              <button
                type="button"
                onClick={handleResetStrategies}
                disabled={isSavingGenerationStrategies}
                className="px-5 py-2.5 border border-slate-200 bg-white text-slate-655 text-xs font-bold rounded-xl hover:bg-slate-50 active:scale-[0.99] transition-colors cursor-pointer shadow-sm"
              >
                恢复系统默认设置
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
                  项目知识库总开关
                </div>
                <p className="text-xs text-slate-400 leading-normal">
                  开启后，AI 在生成候选和回答问题时会结合已就绪的本地文件进行检索（RAG）。关闭后将不注入任何知识库内容。
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
                  <span className="text-xs font-bold text-slate-500 tracking-wide">文档总数</span>
                  <div className="flex items-baseline gap-2 mt-2">
                    <span className="text-3xl font-black text-slate-800">{projectDocuments.length}</span>
                    <span className="text-xs text-slate-400">个已上传文档</span>
                  </div>
                  <div className="text-[10px] text-slate-400 mt-2">包含未就绪以及转换失败的文档</div>
                </div>

                {/* Card 2: Space occupied */}
                <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col justify-between">
                  <span className="text-xs font-bold text-slate-500 tracking-wide">已用存储空间</span>
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
                  <div className="text-[10px] text-slate-400 mt-2">单文件最大支持 20MB</div>
                </div>

                {/* Card 3: AI reference status */}
                <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col justify-between">
                  <span className="text-xs font-bold text-slate-500 tracking-wide">已启用 AI 检索</span>
                  <div className="flex items-baseline gap-2 mt-2">
                    <span className="text-3xl font-black text-emerald-600">{activeDocsCount}</span>
                    <span className="text-xs text-slate-400">个就绪文档</span>
                  </div>
                  <div className="text-[10px] text-slate-400 mt-2 flex items-center gap-1">
                    <Sparkles className="w-3 h-3 text-indigo-500 shrink-0" />
                    <span>可在对话和单对象编辑/新增中被 AI 检索参考</span>
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
                      {isUploadingDocument ? '正在上传文档，请稍等...' : '拖拽文件到这里，或点击上传'}
                    </div>
                    <div className="text-xs text-slate-400">
                      支持 .txt, .md, .pdf, .docx, .xlsx 格式文件
                    </div>
                  </div>
                </div>
              </div>



            {/* Documents Table */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
                <span className="text-xs font-bold text-slate-700 tracking-wide">上传文档管理列表</span>
                <span className="text-[10px] text-slate-400">总共 {projectDocuments.length} 个文档</span>
              </div>

              {projectDocuments.length === 0 ? (
                <div className="p-12 text-center text-slate-400 space-y-2">
                  <File className="w-8 h-8 mx-auto text-slate-300" />
                  <div className="text-xs font-bold">暂无知识库参考文档</div>
                  <div className="text-[10px] max-w-xs mx-auto leading-normal">
                    上传业务文档以使后续 AI 生成的建议能更贴合您已有的产品规格。
                  </div>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-slate-100 text-slate-400 font-bold uppercase tracking-wider text-[10px] bg-slate-50/20">
                        <th className="py-3 px-6">文件名</th>
                        <th className="py-3 px-4">状态</th>
                        <th className="py-3 px-4">大小</th>
                        <th className="py-3 px-4">上传时间</th>
                        <th className="py-3 px-4 text-center">参与 AI 检索</th>
                        <th className="py-3 px-6 text-right">操作</th>
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
                                  可用于 AI
                                </span>
                              )}

                              {isProcessing && (
                                <span className="inline-flex items-center gap-1.5 bg-amber-50 text-amber-700 font-bold border border-amber-100 px-2.5 py-0.5 rounded-lg text-[10px] animate-pulse">
                                  <Clock className="w-3 h-3 text-amber-500 animate-spin" />
                                  解析转换中
                                </span>
                              )}

                              {isFailed && (
                                <span 
                                  className="inline-flex items-center gap-1.5 bg-rose-50 text-rose-700 font-bold border border-rose-100 px-2.5 py-0.5 rounded-lg text-[10px] cursor-help"
                                  title={doc.error_message || '转换未知错误，请重试'}
                                >
                                  <XCircle className="w-3 h-3 text-rose-500" />
                                  转换失败
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
                                <span className="text-[10px] text-slate-300">尚未就绪</span>
                              )}
                            </td>

                            <td className="py-4 px-6 text-right whitespace-nowrap">
                              <div className="flex items-center justify-end gap-1.5">
                                {isFailed && (
                                  <button
                                    type="button"
                                    onClick={() => void retryProjectDocument(doc.public_id)}
                                    className="p-1.5 hover:bg-slate-100 text-slate-400 hover:text-indigo-600 rounded-lg transition-colors border-0 bg-transparent"
                                    title="重试解析转换"
                                  >
                                    <RefreshCw className="w-4 h-4" />
                                  </button>
                                )}
                                <button
                                  type="button"
                                  onClick={() => confirmDelete(doc.public_id, doc.original_filename)}
                                  className="p-1.5 hover:bg-slate-100 text-slate-400 hover:text-rose-600 rounded-lg transition-colors border-0 bg-transparent"
                                  title="删除文档"
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
                  <span className="text-xs text-slate-400 font-medium">正在拉取团队模型配置...</span>
                </div>
              ) : (
                <>
                  {/* Current config view */}
                  {!isEditingLLM && projectLLMConfig?.configured && (
                    <div className="space-y-5">
                      <div className="p-4 bg-emerald-50 border border-emerald-100 text-emerald-950 rounded-2xl space-y-3">
                        <h3 className="text-sm font-bold flex items-center gap-1.5 text-emerald-800">
                          <CheckCircle className="w-4 h-4 text-emerald-600" />
                          项目专属项目大模型已成功挂载
                        </h3>
                        <p className="text-xs leading-relaxed text-slate-655 font-medium">
                          当前工作区正在使用该项目专属的 LLM 策略。所有 AI 诊断、重推演、候选方案生成都将自动定向使用本模型。项目模型配置优先级高于您的个人模型配置。
                        </p>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 bg-slate-50 p-5 border border-slate-100 rounded-2xl text-xs font-medium">
                        <div className="space-y-1">
                          <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block">接口地址 (API Base URL)</span>
                          <span className="font-extrabold text-slate-700 truncate block">{projectLLMConfig.apiUrl}</span>
                        </div>
                        <div className="space-y-1">
                          <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block">大模型名称 (Model Name)</span>
                          <span className="font-extrabold text-slate-700 block">{projectLLMConfig.modelName}</span>
                        </div>
                        <div className="space-y-1">
                          <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block">API Key 密文</span>
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
                              测试连通性
                            </>
                          )}
                        </button>
                        <button
                          type="button"
                          onClick={() => setIsEditingLLM(true)}
                          className="px-4 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 active:scale-[0.99] transition-all flex items-center gap-1.5 cursor-pointer shadow-sm"
                        >
                          <Edit className="w-3.5 h-3.5" />
                          修改配置
                        </button>
                        <button
                          type="button"
                          onClick={handleDeleteLLM}
                          className="px-4 py-2 border border-rose-200 bg-rose-50 text-rose-600 text-xs font-bold rounded-xl hover:bg-rose-100 active:scale-[0.99] transition-all flex items-center gap-1.5 ml-auto cursor-pointer"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          清除配置
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Form for creation or editing */}
                  {(isEditingLLM || !projectLLMConfig?.configured) && (
                    <form onSubmit={handleSaveLLM} className="space-y-5">
                      <div className="p-4 bg-indigo-50/50 border border-indigo-100 text-indigo-900 rounded-2xl text-xs leading-relaxed">
                        项目 LLM 配置可保障您项目模型连接的专有权，协同编辑和草稿生成将优先调用此参数，满足企业审计与合规要求。
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
                            大模型名称 (Model Name) <span className="text-rose-500">*</span>
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
                            项目共享密钥 (API Key) <span className="text-rose-500">*</span>
                          </label>
                          <div className="relative">
                            <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                            <input
                              type="password"
                              placeholder={projectLLMConfig?.configured ? '未更改（输入新 Key 替换）' : '请输入密钥 API Key'}
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
                          保存配置
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
                              测试通道连通性
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
                            取消
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
                    <div className="font-bold">{llmTestResult.success ? '连接测试通过' : '连接测试失败'}</div>
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
                <h3 className="text-sm font-black text-slate-800">确认删除文档？</h3>
                <p className="text-xs text-slate-500 leading-relaxed">
                  您确定要删除文档 <span className="font-semibold text-slate-700">“{deleteTargetName}”</span> 吗？删除后此文件将从项目中清除，AI 无法再参考其内容。此操作不可逆。
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
                取消
              </button>
              <button
                type="button"
                onClick={handleDeleteDoc}
                className="px-4 py-2 bg-rose-600 text-white rounded-xl text-xs font-bold hover:bg-rose-700 shadow-md shadow-rose-100 transition-colors cursor-pointer"
              >
                彻底删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
