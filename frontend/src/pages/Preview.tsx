import { useEffect, useMemo, useState } from 'react';
import {
  CheckSquare,
  ExternalLink,
  Eye,
  FileDown,
  LayoutDashboard,
  MonitorPlay,
  RefreshCw,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { FlowStepCard } from '@/components/shared/FlowStepCard';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import {
  buildRolePages,
  buildStepDetail,
  buildSystemProjection,
  projectionPath,
} from '@/core/selectors';
import { selectSelectedObject, useWorkspaceStore } from '@/store/useWorkspaceStore';
import { workspaceApi } from '@/lib/api';

type PrototypePreview = {
  prototypeId: number;
  projectId: number;
  html: string;
  javascript: string;
  css: string;
  pages?: PrototypePage[];
  source: string;
  status: string;
  createdAt?: string;
  updatedAt?: string;
};

type PrototypePage = {
  pageId: string;
  roleId: number;
  roleName: string;
  featureId: number;
  featureName: string;
  html: string;
  javascript: string;
  css: string;
  source: string;
  status: string;
};

type PrototypeState = 'idle' | 'loading' | 'ready' | 'error';

export function Preview() {
  const {
    setSelectedObject,
    setHighlightTarget,
    highlightTarget,
  } = useWorkspaceStore();
  const navigate = useNavigate();

  const ir = useWorkspaceStore((state) => state.ir);
  const auditLogs = useWorkspaceStore((state) => state.auditLogs);
  const selectedObject = useWorkspaceStore(selectSelectedObject);
  
  const [activeRoleIndex, setActiveRoleIndex] = useState(0);
  const [exportState, setExportState] = useState<'idle' | 'exporting' | 'success'>('idle');
  const [prototype, setPrototype] = useState<PrototypePreview | null>(null);
  const [prototypeState, setPrototypeState] = useState<PrototypeState>('idle');
  const [prototypeError, setPrototypeError] = useState<string | null>(null);
  const [activePrototypePageId, setActivePrototypePageId] = useState<string>('');

  const [selectedFlowId, setSelectedFlowId] = useState<number | null>(null);

  const isWhatComplete = (ir?.actors || []).length > 0 && (ir?.features || []).length > 0;
  const isHowComplete = (ir?.flows || []).length > 0 && (ir?.businessObjects || []).length > 0;
  const isScopeComplete = (ir?.features || []).some((feature) => feature.scope !== null);
  const isPreviewReady = isWhatComplete && isHowComplete && isScopeComplete;

  const actors = useMemo(() => ir?.actorsCompatible || [], [ir]);
  const issues = useMemo(() => ir?.issuesCompatible || [], [ir]);
  const activeRole = actors[activeRoleIndex];
  
  const pages = useMemo(() => {
    if (!ir || !activeRole) return [];
    return buildRolePages(ir, activeRole.id);
  }, [activeRole, ir]);

  const unresolvedIssues = issues.filter((issue: any) => issue.status === 'open');
  const system = useMemo(() => buildSystemProjection(ir), [ir]);
  
  const rolePrototypePages = useMemo(() => {
    if (!prototype?.pages?.length || !activeRole) return [];
    return prototype.pages.filter((page) => String(page.roleId) === String(activeRole.id));
  }, [activeRole, prototype]);

  const activePrototypePage = useMemo(() => {
    if (!prototype) return null;
    return (
      rolePrototypePages.find((page) => page.pageId === activePrototypePageId) ||
      rolePrototypePages[0] ||
      prototype.pages?.[0] ||
      null
    );
  }, [activePrototypePageId, prototype, rolePrototypePages]);

  const prototypeSrcDoc = useMemo(
    () => (prototype ? composePrototypeSrcDoc(activePrototypePage || prototype) : ''),
    [activePrototypePage, prototype],
  );

  const flows = useMemo(() => ir?.flows || [], [ir]);

  const activeFlow = useMemo(() => {
    return flows.find((f) => f.flowId === selectedFlowId) || flows[0] || null;
  }, [flows, selectedFlowId]);

  const activeFlowSteps = useMemo(() => {
    if (!activeFlow) return [];
    return activeFlow.flowSteps || [];
  }, [activeFlow]);

  // Initialize selected flow ID
  useEffect(() => {
    if (flows.length > 0 && selectedFlowId === null) {
      setSelectedFlowId(flows[0].flowId);
    }
  }, [flows, selectedFlowId]);

  useEffect(() => {
    if (rolePrototypePages.length === 0) {
      setActivePrototypePageId('');
      return;
    }
    if (!rolePrototypePages.some((page) => page.pageId === activePrototypePageId)) {
      setActivePrototypePageId(rolePrototypePages[0].pageId);
    }
  }, [activePrototypePageId, rolePrototypePages]);

  // Load latest prototype preview
  useEffect(() => {
    let cancelled = false;
    const projectId = ir?.projectId;
    if (!projectId || !isPreviewReady) {
      setPrototype(null);
      setPrototypeState('idle');
      setPrototypeError(null);
      return;
    }

    setPrototypeState('loading');
    workspaceApi.getLatestPrototypePreview(projectId)
      .then((result) => {
        if (cancelled) return;
        if (result?.message === 'prototype_preview_not_found' || !result?.html) {
          setPrototype(null);
          setPrototypeState('idle');
          setPrototypeError(null);
          return;
        }
        setPrototype(result);
        setPrototypeState('ready');
        setPrototypeError(null);
      })
      .catch(() => {
        if (cancelled) return;
        setPrototype(null);
        setPrototypeState('idle');
        setPrototypeError(null);
      });

    return () => {
      cancelled = true;
    };
  }, [ir?.projectId, isPreviewReady]);

  const handleExport = async (format: 'json' | 'markdown') => {
    if (!ir?.projectId) return;
    setExportState('exporting');
    try {
      if (format === 'markdown') {
        const md = await workspaceApi.exportMarkdown(ir.projectId);
        downloadFile(`${ir.projectName || ir.projectId || 'requirement-space'}.md`, md, 'text/markdown;charset=utf-8');
      } else {
        const data = await workspaceApi.exportJson(ir.projectId);
        downloadFile(`${data.projectName || data.projectId || 'requirement-space'}.json`, JSON.stringify(data, null, 2), 'application/json;charset=utf-8');
      }
      setExportState('success');
      setTimeout(() => setExportState('idle'), 1500);
    } catch {
      setExportState('idle');
    }
  };

  const exportAuditLog = async () => {
    if (!ir) return;
    setExportState('exporting');
    try {
      downloadFile(
        `${ir.projectName || ir.projectId || 'requirement-space'}-audit.json`,
        JSON.stringify(auditLogs || [], null, 2),
        'application/json;charset=utf-8',
      );
      setExportState('success');
      setTimeout(() => setExportState('idle'), 1500);
    } catch {
      setExportState('idle');
    }
  };

  const generatePrototype = async () => {
    if (!ir?.projectId) return;
    setPrototypeState('loading');
    setPrototypeError(null);
    try {
      const result = await workspaceApi.generatePrototypePreview(ir.projectId, true);
      setPrototype(result);
      setPrototypeState('ready');
    } catch (error) {
      setPrototypeState('error');
      setPrototypeError(error instanceof Error ? error.message : '界面原型推演失败');
    }
  };

  const openPrototypeInWindow = () => {
    if (!prototypeSrcDoc) return;
    const blob = new Blob([prototypeSrcDoc], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank', 'noopener,noreferrer');
    window.setTimeout(() => URL.revokeObjectURL(url), 10000);
  };

  if (!isPreviewReady) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 bg-slate-50 min-h-[85vh] w-full">
        <div className="max-w-2xl w-full bg-white rounded-3xl p-8 border border-slate-200 shadow-xl space-y-8 animate-in fade-in duration-300">
          <div className="text-center space-y-2">
            <div className="mx-auto w-14 h-14 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-650 shadow-sm mb-3">
              <Eye className="w-7 h-7 animate-pulse" />
            </div>
            <h3 className="text-xl font-black text-slate-900 tracking-tight">业务原型与资产大屏未就绪</h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
              请根据高一致性建模范式，先完善以下三个阶段的规约建模，才能推演并直接预览可运行原型。
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <ReadinessCard
              title="What"
              ready={isWhatComplete}
              description="需要至少定义一个参与者角色与系统功能特征树。"
              onClick={() => navigate('/what')}
            />
            <ReadinessCard
              title="How"
              ready={isHowComplete}
              description="需要至少定义一个业务流程步骤及相关的数据实体对象。"
              onClick={() => navigate('/flow')}
            />
            <ReadinessCard
              title="Scope"
              ready={isScopeComplete}
              description="需要对至少一个三级叶子节点做出本期、暂缓或排除决策。"
              onClick={() => navigate('/scope')}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex w-full relative">
      <div className="flex-1 p-6 pb-24 overflow-y-auto w-full">
        <div className="max-w-[1240px] mx-auto space-y-8 animate-in fade-in flex flex-col">
          
          {/* Header Banner */}
          <section className="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm flex flex-col lg:flex-row justify-between lg:items-center gap-6">
            <div className="space-y-1">
              <h2 className="text-xl font-black text-slate-900 tracking-tight flex items-center gap-2">
                <LayoutDashboard className="w-5 h-5 text-indigo-650 shrink-0" />
                系统交付原型与模型资产导出
              </h2>
              <p className="text-xs text-slate-400 leading-relaxed max-w-2xl font-medium">
                一键在线审查在需求阶段推演生成的交互式角色原型，或导出标准需求规格书与全套需求工程资产。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <ExportButton label="导出 Markdown 需求规格书" onClick={() => void handleExport('markdown')} disabled={exportState === 'exporting'} />
              <ExportButton label="导出标准 JSON 资产" onClick={() => void handleExport('json')} disabled={exportState === 'exporting'} />
              <button
                onClick={() => void exportAuditLog()}
                disabled={exportState === 'exporting'}
                className="px-4 py-2.5 rounded-xl border border-slate-200 text-slate-700 text-xs font-bold hover:bg-slate-50 hover:border-slate-300 transition-colors bg-white flex items-center gap-1.5 shadow-sm disabled:opacity-60 font-semibold"
              >
                <CheckSquare className="w-3.5 h-3.5 text-sky-500" />
                导出操作审计日志
              </button>
            </div>
          </section>

          {/* Integrated Side-by-Side Interactive Prototype & Blueprints Panel */}
          <section className="bg-white rounded-3xl border border-slate-200 shadow-md overflow-hidden">
            <div className="border-b border-slate-200 px-6 py-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-slate-50/50">
              <div className="space-y-1">
                <h3 className="text-base font-black text-slate-900 tracking-tight flex items-center gap-2">
                  <MonitorPlay className="w-5 h-5 text-teal-650" />
                  可交互角色原型与规格说明 (Interactive Role Prototype & Specification)
                </h3>
                <div className="text-[11px] text-slate-450 font-medium leading-none">
                  {prototype
                    ? `推演生成自：${activePrototypePage?.source || prototype.source} · 原型版本：#${prototype.prototypeId} · 页面数：${prototype.pages?.length || 1}`
                    : '当前工作区尚未生成高保真交互式原型，请点击右侧按钮推演生成。'}
                </div>
              </div>
              
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={openPrototypeInWindow}
                  disabled={!prototypeSrcDoc || prototypeState === 'loading'}
                  className="px-3.5 py-2 rounded-xl border border-slate-200 text-slate-750 text-xs font-bold hover:bg-slate-50 transition-colors bg-white flex items-center gap-1.5 disabled:opacity-50 shadow-sm"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  独立窗口打开原型
                </button>
                <button
                  type="button"
                  onClick={() => void generatePrototype()}
                  disabled={prototypeState === 'loading'}
                  className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition-colors flex items-center gap-1.5 disabled:opacity-60 shadow-md"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${prototypeState === 'loading' ? 'animate-spin' : ''}`} />
                  {prototype ? '重新推演界面' : '智能生成原型'}
                </button>
              </div>
            </div>

            {/* Viewport Split Screen */}
            <div className="grid grid-cols-1 lg:grid-cols-12 border-t border-slate-100">
              
              {/* Left Column: Interactive Prototype Simulator */}
              <div className="lg:col-span-7 bg-slate-100/50 p-6 border-r border-slate-200 flex flex-col justify-center">
                <div className="bg-white border border-slate-250 rounded-2xl shadow-xl overflow-hidden flex flex-col h-[740px]">
                  <div className="h-10 px-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between shrink-0">
                    <div className="flex gap-1.5 items-center">
                      <span className="w-2.5 h-2.5 rounded-full bg-rose-400 inline-block" />
                      <span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block" />
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block" />
                      <span className="ml-3 text-[11px] text-slate-400 font-mono select-none truncate">
                        /projects/{ir?.projectId || 'current'}/roles/{activeRole?.title || 'role'}/{activePrototypePage?.featureName || 'prototype'}
                      </span>
                    </div>
                    <span className="text-[9px] bg-slate-200 border border-slate-350 text-slate-500 px-2 py-0.5 rounded font-mono font-bold select-none">
                      PROTOTYPE SIMULATION
                    </span>
                  </div>
                  {rolePrototypePages.length > 0 && (
                    <div className="shrink-0 border-b border-slate-200 bg-white px-3 py-2 flex flex-wrap gap-2">
                      {rolePrototypePages.map((page) => (
                        <button
                          key={page.pageId}
                          type="button"
                          onClick={() => setActivePrototypePageId(page.pageId)}
                          className={`px-3 py-1.5 rounded-lg text-[11px] font-bold border transition-colors ${
                            activePrototypePage?.pageId === page.pageId
                              ? 'bg-teal-50 text-teal-700 border-teal-200'
                              : 'bg-slate-50 text-slate-500 border-slate-200 hover:text-slate-700'
                          }`}
                        >
                          {page.featureName}
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="flex-1 bg-white relative">
                    {prototypeState === 'loading' ? (
                      <PrototypePlaceholder label="正在按角色生成原型：后端会找到每个角色关联的功能点，并发调用当前配置的生成后端；Skill 模式下每个功能点会用用户需求和该功能点场景验收标准生成页面。" />
                    ) : prototypeState === 'error' ? (
                      <PrototypePlaceholder label={prototypeError || '原型推演拼装失败，请保证特征树与流程完整性。'} tone="error" />
                    ) : prototype ? (
                      <iframe
                        key={prototype.prototypeId}
                        title={`${activeRole?.title || ir?.projectName || 'Project'} prototype`}
                        srcDoc={prototypeSrcDoc}
                        sandbox="allow-scripts"
                        className="w-full h-full border-0 bg-white"
                      />
                    ) : (
                      <PrototypePlaceholder label="当前项目还没有原型。点击右上角“智能生成原型”后才会开始生成。" />
                    )}
                  </div>
                </div>
              </div>

              {/* Right Column: Dynamic Role Blueprint Specifications */}
              <div className="lg:col-span-5 p-6 overflow-y-auto max-h-[788px] space-y-6 flex flex-col">
                <div className="border-b border-slate-100 pb-3 flex items-center justify-between shrink-0">
                  <h4 className="text-xs font-bold text-slate-450 uppercase tracking-widest flex items-center gap-1">
                    📖 角色界面与交互规格说明
                  </h4>
                  <span className="text-[9px] bg-indigo-50 border border-indigo-100 text-indigo-700 font-extrabold px-2 py-0.5 rounded">
                    共 {pages.length} 个页面定义
                  </span>
                </div>

                {/* Role Tabs inside Specification container */}
                <div className="flex flex-wrap items-center gap-1.5 shrink-0 bg-slate-50 p-1.5 rounded-xl border border-slate-200">
                  {actors.map((actor: any, idx: number) => (
                    <button
                      key={actor.id}
                      type="button"
                      onClick={() => setActiveRoleIndex(idx)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                        activeRoleIndex === idx 
                          ? 'bg-white text-indigo-650 shadow-sm border border-indigo-100/50' 
                          : 'text-slate-500 hover:text-slate-700'
                      }`}
                    >
                      👤 {actor.title}
                    </button>
                  ))}
                </div>

                <div className="flex-1 space-y-6">
                  {pages.length === 0 ? (
                    <div className="text-center py-24 border border-dashed border-slate-200 rounded-2xl bg-slate-50/50 space-y-3">
                      <div className="mx-auto w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center text-slate-400">
                        <Eye className="w-5 h-5" />
                      </div>
                      <div className="text-xs font-extrabold text-slate-700">该角色暂无关联页面预览</div>
                      <div className="text-[11px] text-slate-400 max-w-xs mx-auto leading-relaxed">
                        请先在 What 阶段为角色勾选关联具体的功能点，或在 How 阶段配置该角色协作的步骤节点。
                      </div>
                    </div>
                  ) : (
                    pages.map((page) => (
                      <div key={page.id} className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4 hover:border-slate-350 transition-colors">
                        <div className="border-b border-slate-100 pb-3">
                          <h5 className="font-extrabold text-slate-800 text-xs flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                            {page.name}
                          </h5>
                          <p className="text-[11px] text-slate-500 mt-1 leading-relaxed font-medium">{page.desc}</p>
                        </div>
                        
                        <div className="space-y-4">
                          <div>
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-2">本期验收场景 (AC)</span>
                            {page.scenarios.length === 0 ? (
                              <span className="text-[11px] text-slate-400 italic block bg-slate-50 p-2.5 rounded-xl border border-slate-100">暂无关联的交付场景。</span>
                            ) : (
                              <div className="space-y-2.5">
                                {page.scenarios.map((scenario: any) => (
                                  <div
                                    key={scenario.scenarioId}
                                    onClick={() => setSelectedObject({ ...scenario, kind: 'scenario' })}
                                    className="w-full text-left bg-slate-50 border border-slate-200 rounded-xl p-3 space-y-2 hover:border-indigo-300 transition-all cursor-pointer"
                                  >
                                    <h6 className="font-bold text-slate-800 text-[11px] truncate">{scenario.scenarioName}</h6>
                                    <p className="text-[10px] text-slate-550 leading-relaxed bg-white border border-slate-100 p-2 rounded-lg italic">
                                      "{scenario.scenarioContent}"
                                    </p>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>

                          <div>
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-2">执行系统步骤</span>
                            <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 space-y-2">
                              {page.relatedSteps.length === 0 ? (
                                <span className="text-[11px] text-slate-400 italic">暂无步骤关联。</span>
                              ) : (
                                page.relatedSteps.map((stepName: string, idx: number) => (
                                  <div key={`${stepName}-${idx}`} className="bg-white rounded-lg p-2.5 border border-slate-150 shadow-sm flex items-center justify-between">
                                    <span className="text-[10px] font-bold text-slate-700 truncate">{stepName}</span>
                                    <span className="text-[8px] bg-indigo-50 border border-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded font-extrabold shrink-0">
                                      角色发起
                                    </span>
                                  </div>
                                ))
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </section>

          {/* Active Issues Alert */}
          {unresolvedIssues.length > 0 && (
            <section className="bg-amber-50 rounded-2xl border border-amber-250 p-5 shadow-sm">
              <h3 className="font-bold text-amber-900 mb-1.5 flex items-center gap-1.5 text-xs">
                <span>⚠️ 发现未闭环的系统设计 Issue ({unresolvedIssues.length} 项)</span>
              </h3>
              <p className="text-[11px] text-amber-800 leading-relaxed font-medium">
                工作区目前包含未决的业务冲突或流程空白，建议在最终导出产品规格说明前，返回“做什么”和“如何工作”页面修复这些问题。
              </p>
            </section>
          )}

          {/* End-to-End Business Flow Chronological Timelines */}
          <section className="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm relative w-full">
            <div className="mb-6 border-b border-slate-100 pb-4">
              <h3 className="text-base font-extrabold text-slate-900 mb-1">全链路端到端业务流时序图 (End-to-End Flow Timelines)</h3>
              <p className="text-xs text-slate-400 uppercase tracking-widest font-bold">Chronological sequence of all business flow operations</p>
            </div>
            
            {/* Flow Switcher Tabs */}
            <div className="flex flex-wrap gap-2 mb-6 border-b border-slate-100 pb-4">
              {flows.map((flow) => (
                <button
                  key={flow.flowId}
                  type="button"
                  onClick={() => setSelectedFlowId(flow.flowId)}
                  className={`px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-sm ${
                    selectedFlowId === flow.flowId 
                      ? 'bg-slate-900 text-white shadow-indigo-100' 
                      : 'bg-slate-50 text-slate-655 hover:bg-slate-100 border border-slate-200/60'
                  }`}
                >
                  🌊 {flow.flowName}
                </button>
              ))}
            </div>

            {/* Switchable flow chronological view */}
            <div className="w-full bg-slate-50 border border-slate-200 rounded-2xl flex flex-col min-h-[360px] p-6 shadow-inner">
              <div className="p-4 bg-white border border-slate-200 rounded-t-2xl flex items-center justify-between shrink-0 mb-6 shadow-sm">
                <h4 className="text-xs font-extrabold text-slate-800 flex items-center gap-1.5 uppercase tracking-wider">
                  <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-pulse"></span>
                  正在审阅业务流时序：{activeFlow?.flowName}
                </h4>
                <span className="text-[10px] bg-slate-50 border border-slate-200 text-slate-450 px-2.5 py-0.5 rounded font-bold">
                  端到端全链路时序
                </span>
              </div>
              
              <div className="flex-1 w-full max-w-3xl mx-auto">
                {activeFlowSteps.length === 0 ? (
                  <div className="text-center py-20 text-xs text-slate-400 italic">
                    当前业务流程暂无任何步骤定义。
                  </div>
                ) : (
                  <div className="relative pl-8 border-l-2 border-indigo-150 space-y-8 py-2">
                    {activeFlowSteps.map((step, idx) => {
                      const stepDetail = buildStepDetail(ir, step.stepId);
                      const performerId = (step.actorIds || [])[0];
                      const performer = (ir?.actors || []).find((a) => a.actorId === performerId);
                      const actorName = performer ? performer.actorName : '系统自动';

                      const nextSteps = (step.nextStepIds || [])
                        .map((nid) => activeFlowSteps.find((s) => s.stepId === nid)?.stepName)
                        .filter(Boolean) as string[];

                      const stepSlots: any[] = [];
                      if (ir?.perceptionSlot && ir.perceptionSlot.perceptionJobId === step.stepId) {
                        stepSlots.push({
                          id: ir.perceptionSlot.perceptionSlotId.toString(),
                          title: ir.perceptionSlot.perceptionKind,
                          choiceCount: 0,
                          status: 'empty'
                        });
                      }

                      const isActive = selectedObject?.id === step.stepId.toString() || (highlightTarget !== null && highlightTarget.toString() === step.stepId.toString());

                      return (
                        <div key={step.stepId} className="relative">
                          {/* Timeline dot */}
                          <div className={`absolute -left-[44px] top-4 w-7 h-7 rounded-full border-4 flex items-center justify-center text-[10px] font-black transition-all ${
                            isActive
                              ? 'bg-indigo-650 border-indigo-200 text-white shadow-md shadow-indigo-600/20'
                              : 'bg-white border-indigo-100 text-slate-400'
                          }`}>
                            {idx + 1}
                          </div>

                          <FlowStepCard
                            name={step.stepName}
                            type={step.stepType === 'actorAction' ? '用户动作' : step.stepType === 'systemAction' ? '系统动作' : '条件分支'}
                            actor={actorName}
                            status={step.status || 'confirmed'}
                            inputs={stepDetail.inputs}
                            outputs={stepDetail.outputs}
                            rules={stepDetail.rules}
                            stateChanges={stepDetail.stateChanges}
                            relatedPages={stepDetail.relatedPages}
                            relatedIssueCount={stepDetail.relatedIssueIds.length}
                            relatedChoiceCount={stepDetail.relatedChoiceIds.length}
                            nextSteps={nextSteps.length > 0 ? nextSteps : undefined}
                            exceptionSteps={undefined}
                            slots={stepSlots}
                            active={isActive}
                            onClick={() => {
                              setSelectedObject({
                                ...step,
                                id: step.stepId.toString(),
                                title: step.stepName,
                                description: step.stepDescription,
                                status: step.status || 'confirmed',
                                kind: 'flow_step'
                              });
                              setHighlightTarget(step.stepId.toString());
                            }}
                            onSlotClick={(slotId) => {
                              if (ir?.perceptionSlot && ir.perceptionSlot.perceptionSlotId.toString() === slotId) {
                                setSelectedObject(ir.perceptionSlot);
                              }
                            }}
                          />
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </section>

        </div>
      </div>

      <RightObjectPanel />
    </div>
  );
}

function PrototypePlaceholder({
  label,
  tone = 'neutral',
}: {
  label: string;
  tone?: 'neutral' | 'error';
}) {
  return (
    <div className={`h-full flex items-center justify-center text-xs font-bold leading-normal p-8 text-center ${tone === 'error' ? 'text-rose-600 bg-rose-50' : 'text-slate-400 bg-white'}`}>
      {label}
    </div>
  );
}

function ReadinessCard({
  title,
  ready,
  description,
  onClick,
}: {
  title: string;
  ready: boolean;
  description: string;
  onClick: () => void;
}) {
  return (
    <div className={`rounded-2xl border p-5 flex flex-col gap-3.5 transition-colors shadow-sm ${ready ? 'border-emerald-200 bg-emerald-50/20' : 'border-amber-200 bg-amber-50/20'}`}>
      <div className="flex justify-between items-center leading-none">
        <span className="text-xs font-bold text-slate-800">{title === 'What' ? '要做什么 (What)' : title === 'How' ? '如何工作 (How)' : '划分范围 (Scope)'}</span>
        <span className={`text-[8px] font-extrabold px-1.5 py-0.5 rounded border uppercase tracking-wider ${ready ? 'bg-emerald-50 border-emerald-100 text-emerald-800' : 'bg-amber-50 border-amber-100 text-amber-800'}`}>
          {ready ? '已就绪' : '待完善'}
        </span>
      </div>
      <p className="text-[11px] text-slate-500 leading-relaxed font-medium">{description}</p>
      {!ready && (
        <button onClick={onClick} className="mt-auto text-[10px] text-indigo-600 hover:text-indigo-800 font-bold text-left flex items-center gap-0.5 transition-colors">
          立即前往完善 &rarr;
        </button>
      )}
    </div>
  );
}

function ExportButton({
  label,
  onClick,
  disabled,
}: {
  label: string;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="px-4 py-2.5 rounded-xl border border-slate-200 text-slate-700 text-xs font-bold hover:bg-slate-50 hover:border-slate-350 transition-colors bg-white flex items-center gap-1.5 shadow-sm disabled:opacity-60 font-semibold"
    >
      <FileDown className="w-3.5 h-3.5 text-indigo-500" />
      {label}
    </button>
  );
}

function composePrototypeSrcDoc(prototype: PrototypePreview | PrototypePage) {
  const css = prototype.css ? `<style>${prototype.css}</style>` : '';
  const javascript = prototype.javascript
    ? `<script>${prototype.javascript.replace(/<\/script/gi, '<\\/script')}</script>`
    : '';
  let html = prototype.html || '<!doctype html><html><head></head><body></body></html>';

  if (css) {
    html = html.includes('</head>')
      ? html.replace('</head>', `${css}</head>`)
      : `${css}${html}`;
  }

  if (javascript) {
    html = html.includes('</body>')
      ? html.replace('</body>', `${javascript}</body>`)
      : `${html}${javascript}`;
  }

  return html;
}

function downloadFile(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
