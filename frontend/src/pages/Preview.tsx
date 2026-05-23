import { useState, useMemo } from 'react';
import { FlowStepCard } from '@/components/shared/FlowStepCard';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { FileDown, RefreshCw, CheckCircle2, Play, Check, X, Sparkles, Eye, CheckSquare, LayoutDashboard } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { buildPreviewCheckpoints, buildRolePages, buildStepDetail, buildSystemProjection, projectionPath } from '@/core/selectors';
import { 
  useWorkspaceStore, 
  selectSelectedObject,
  normalizeRequirementSpace
} from '@/store/useWorkspaceStore';
import { workspaceApi } from '@/lib/api';

export function Preview() {
  const { 
    setSelectedObject,
    setHighlightTarget,
    highlightTarget
  } = useWorkspaceStore();
  const navigate = useNavigate();
  
  const ir = useWorkspaceStore(s => s.ir);
  const selectedObject = useWorkspaceStore(selectSelectedObject);
  
  // State for AI simulation
  const [isForceGenerated, setIsForceGenerated] = useState(false);

  const isWhatComplete = (ir?.actors || []).length > 0 && (ir?.features || []).length > 0;
  const isHowComplete = (ir?.flows || []).length > 0 && (ir?.businessObjects || []).length > 0;
  const isScopeComplete = (ir?.features || []).some(f => f.scope !== null);
  const isPreviewReady = isWhatComplete && isHowComplete && isScopeComplete;

  // AI draft simulation logic
  const draftIr = useMemo(() => {
    if (isPreviewReady || !isForceGenerated || !ir) return ir;
    
    const cloned = JSON.parse(JSON.stringify(ir));
    
    // 1. Simulate Actors if empty
    if ((cloned.actors || []).length === 0) {
      cloned.actors = [
        {
          kind: 'actor',
          actorId: 9001,
          actorName: '仿真业务主管',
          actorDescription: 'AI 仿真预推演的角色：负责系统决策与业务流关键节点审批。'
        },
        {
          kind: 'actor',
          actorId: 9002,
          actorName: '仿真前台操作员',
          actorDescription: 'AI 仿真推演的角色：负责终端数据的录入与初始指令的发起。'
        }
      ];
    }
    
    // 2. Simulate Features if empty
    if ((cloned.features || []).length === 0) {
      cloned.features = [
        {
          kind: 'feature',
          featureId: 9101,
          featureName: 'AI 仿真运作主控板',
          featureDescription: '仿真大屏，实时监测业务流数据与状态流转。',
          actorIds: [9001, 9002],
          parentId: null,
          childrenIds: [9102, 9103],
          scenarios: [],
          scope: { kind: 'scope', scopeId: 9201, scopeStatus: '本期', reason: '仿真模块范围。', positiveSummary: null, negativeSummary: null, positivePictureBase64: null, negativePictureBase64: null }
        },
        {
          kind: 'feature',
          featureId: 9102,
          featureName: '仿真数据扫码录入',
          featureDescription: '支持扫码和条码识别入库登记。',
          actorIds: [9002],
          parentId: 9101,
          childrenIds: [],
          scenarios: [
            {
              scenarioId: 9501,
              scenarioName: '条码扫描并解析提交',
              scenarioContent: '作为一个 仿真前台操作员，我希望能够使用扫码头扫描物品条码，系统应在 0.5s 内解析出条码信息并自动带入调拨单，以便提高录入效率。',
              actorId: 9002,
              featureId: 9102,
              acceptanceCriteria: [
                { criterionId: 9511, criterionContent: '解析时间小于 500ms' },
                { criterionId: 9512, criterionContent: '条码不合法时给出清晰警告提示' }
              ]
            }
          ],
          scope: { kind: 'scope', scopeId: 9202, scopeStatus: '本期', reason: '仿真功能范围。', positiveSummary: null, negativeSummary: null, positivePictureBase64: null, negativePictureBase64: null }
        },
        {
          kind: 'feature',
          featureId: 9103,
          featureName: '协同预警快速审批流',
          featureDescription: '实现财务和主管双向审批业务流。',
          actorIds: [9001],
          parentId: 9101,
          childrenIds: [],
          scenarios: [
            {
              scenarioId: 9502,
              scenarioName: '大额调拨预警并双签审批',
              scenarioContent: '作为一个 仿真业务主管，我希望在大额调拨单提交时系统弹出橙色高亮预警，并要求财务与主管双向数字签名，以规避业务合规风险。',
              actorId: 9001,
              featureId: 9103,
              acceptanceCriteria: [
                { criterionId: 9521, criterionContent: '超出 10 万调拨单必须双签' },
                { criterionId: 9522, criterionContent: '双签过程中自动留存数字指纹' }
              ]
            }
          ],
          scope: { kind: 'scope', scopeId: 9203, scopeStatus: '本期', reason: '仿真功能范围。', positiveSummary: null, negativeSummary: null, positivePictureBase64: null, negativePictureBase64: null }
        }
      ];
    }

    cloned.features.forEach((f: any) => {
      if (!f.scope) {
        f.scope = {
          kind: 'scope',
          scopeId: Math.floor(Math.random() * 9000),
          scopeStatus: '本期',
          reason: 'AI 仿真推演的默认范围决定。',
          positiveSummary: null,
          negativeSummary: null,
          positivePictureBase64: null,
          negativePictureBase64: null
        };
      }
      // Add mock scenarios if the user has feature nodes but no scenarios
      if (f.parentId !== null && (!f.scenarios || f.scenarios.length === 0)) {
        f.scenarios = [
          {
            scenarioId: Math.floor(Math.random() * 90000) + 10000,
            scenarioName: `正常执行 ${f.featureName} 流程`,
            scenarioContent: `作为系统参与角色，我希望在交互界面上顺利操作并执行 ${f.featureName}，系统应给出正确的成功提示。`,
            actorId: (f.actorIds || [])[0] || 9001,
            featureId: f.featureId,
            acceptanceCriteria: [
              { criterionId: Math.floor(Math.random() * 90000) + 10000, criterionContent: '提交后系统数据能够持久化，并展示成功提醒。' }
            ]
          }
        ];
      }
    });
    
    // 3. Simulate Business Objects if empty
    if ((cloned.businessObjects || []).length === 0) {
      cloned.businessObjects = [
        {
          kind: 'business_object',
          businessObjectId: 9301,
          businessObjectName: '仿真业务实体 (SimulatedCard)',
          businessObjectDescription: 'AI 仿真推演的实体：存储全生命周期元数据与状态变化。',
          businessObjectAttributes: [
            { kind: 'business_object_attribute', businessObjectAttributeId: 9311, businessObjectAttributeName: 'simulatedCode', businessObjectAttributeDescription: '唯一标识条码', businessObjectAttributeType: 'String', businessObjectAttributeExample: 'SIM-2026-99' },
            { kind: 'business_object_attribute', businessObjectAttributeId: 9312, businessObjectAttributeName: 'lifecycleStatus', businessObjectAttributeDescription: '生命周期状态', businessObjectAttributeType: 'Enum', businessObjectAttributeExample: '进行中' }
          ]
        }
      ];
    }
    
    // 4. Simulate Flows if empty
    if ((cloned.flows || []).length === 0) {
      const actId1 = cloned.actors[0].actorId;
      const actId2 = cloned.actors[1]?.actorId || actId1;
      const boId = cloned.businessObjects[0].businessObjectId;

      cloned.flows = [
        {
          kind: 'flow',
          flowId: 9401,
          flowName: 'AI 仿真调拨与审批验证主流程',
          flowDescription: '从登记、主管初审到系统自动流转状态完结 of the demo process.',
          featureIds: [9102, 9103],
          flowSteps: [
            {
              kind: 'flow_step',
              stepId: 9411,
              stepName: '前台提交业务录入申请',
              stepDescription: '操作员选择仿真业务卡片并提交，申请初始审批。',
              stepType: 'actorAction',
              actorIds: [actId2],
              inputBusinessObjectIds: [boId],
              outputBusinessObjectIds: [],
              nextStepIds: [9412]
            },
            {
              kind: 'flow_step',
              stepId: 9412,
              stepName: '仿真业务主管审批决策',
              stepDescription: '主管在线评估申请，做出通过 or 驳回的决策。',
              stepType: 'judgment',
              actorIds: [actId1],
              inputBusinessObjectIds: [boId],
              outputBusinessObjectIds: [],
              nextStepIds: [9413]
            },
            {
              kind: 'flow_step',
              stepId: 9413,
              stepName: '系统确认并变更状态',
              stepDescription: '系统自动将卡片的 lifecycleStatus 修改为已生效，完成最终过账。',
              stepType: 'systemAction',
              actorIds: [],
              inputBusinessObjectIds: [],
              outputBusinessObjectIds: [boId],
              nextStepIds: []
            }
          ]
        }
      ];
    }
    
    return normalizeRequirementSpace(cloned);
  }, [ir, isPreviewReady, isForceGenerated]);

  // Read compatible lists from draftIr
  const flowSteps = useMemo(() => draftIr?.flowStepsCompatible || [], [draftIr]);
  const issues = useMemo(() => draftIr?.issuesCompatible || [], [draftIr]);
  const actors = useMemo(() => draftIr?.actorsCompatible || [], [draftIr]);

  const [activeRoleIndex, setActiveRoleIndex] = useState(0);
  const activeRole = actors[activeRoleIndex];
  const [exportState, setExportState] = useState<'idle' | 'exporting' | 'success'>('idle');

  // Persistence action for force-generated simulation
  const mergeForceGeneratedToProject = async () => {
    if (!ir) return;
    try {
      const normalized = normalizeRequirementSpace(draftIr);
      useWorkspaceStore.setState({ ir: normalized });
      if (normalized) {
        await workspaceApi.save(normalized);
      }
      useWorkspaceStore.setState({ lastActionMessage: 'AI 仿真推演的全部资产已成功采纳合并至项目正式数据空间！' });
      setIsForceGenerated(false);
    } catch (e) {
      useWorkspaceStore.setState({ error: '合并推演数据失败' });
    }
  };

  const discardForceGenerated = () => {
    setIsForceGenerated(false);
    useWorkspaceStore.setState({ lastActionMessage: '已舍弃本次 AI 临时推演仿真草稿。' });
  };

  const handleExport = async (format: 'json' | 'markdown') => {
    setExportState('exporting');
    try {
      if (!draftIr?.projectId) return;
      if (format === 'markdown') {
        const md = await workspaceApi.exportMarkdown(draftIr.projectId);
        const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${draftIr.projectName || draftIr.projectId || 'requirement-space'}.md`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        setExportState('success');
        setTimeout(() => setExportState('idle'), 1500);
        return;
      }

      const data = await workspaceApi.exportJson(draftIr.projectId);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${data.projectName || data.projectId || 'requirement-space'}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setExportState('success');
      setTimeout(() => setExportState('idle'), 1500);
    } catch {
      setExportState('idle');
    }
  };

  // Calculate screens dynamically based on draftIr
  const pages = useMemo(() => {
    if (!draftIr || !activeRole) return [];
    return buildRolePages(draftIr, activeRole.id);
  }, [activeRole, draftIr]);
  const checkpoints = useMemo(() => buildPreviewCheckpoints(draftIr), [draftIr]);

  const unresolvedIssues = issues.filter(g => g.status === 'open');
  const system = useMemo(() => buildSystemProjection(draftIr), [draftIr]);

  const exportAuditLog = async () => {
    if (!draftIr) return;
    setExportState('exporting');
    try {
      const blob = new Blob([JSON.stringify((draftIr as any).audit || [], null, 2)], { type: 'application/json;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${draftIr.projectName || draftIr.projectId || 'requirement-space'}-audit.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setExportState('success');
      setTimeout(() => setExportState('idle'), 1500);
    } catch {
      setExportState('idle');
    }
  };

  const jumpToProjection = (projection: any) => {
    return navigate(projectionPath(projection));
  };

  if (!isPreviewReady && !isForceGenerated) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 bg-slate-50 min-h-[85vh] w-full">
        <div className="max-w-2xl w-full bg-white rounded-3xl p-8 border border-slate-200 shadow-xl space-y-8 animate-in fade-in duration-300">
          <div className="text-center space-y-2">
            <div className="mx-auto w-14 h-14 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shadow-sm animate-pulse mb-3">
              <Eye className="w-7 h-7" />
            </div>
            <h3 className="text-xl font-black text-slate-900 tracking-tight">快速原型方案预览预核对</h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              原型方案预览是融合角色、业务流和范围边界的总成呈现。系统检测到您的需求建模尚未完全收敛，存在未完成维度：
            </p>
          </div>

          {/* Checks checklist */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className={`rounded-2xl border p-4 flex flex-col gap-3 transition-colors ${isWhatComplete ? 'border-emerald-200 bg-emerald-50/20' : 'border-amber-200 bg-amber-50/20'}`}>
              <div className="flex justify-between items-center">
                <span className="text-xs font-bold text-slate-900">What 角色与功能</span>
                <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${isWhatComplete ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                  {isWhatComplete ? '已就绪' : '待补充'}
                </span>
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                包含系统核心参与角色与三层能力树建模。
              </p>
              {!isWhatComplete && (
                <button
                  onClick={() => navigate('/what')}
                  className="mt-auto text-[10px] text-indigo-600 hover:text-indigo-700 font-bold text-left"
                >
                  前往建模角色与能力 &rarr;
                </button>
              )}
            </div>

            <div className={`rounded-2xl border p-4 flex flex-col gap-3 transition-colors ${isHowComplete ? 'border-emerald-200 bg-emerald-50/20' : 'border-amber-200 bg-amber-50/20'}`}>
              <div className="flex justify-between items-center">
                <span className="text-xs font-bold text-slate-900">How 流程与数据</span>
                <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${isHowComplete ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                  {isHowComplete ? '已就绪' : '待补充'}
                </span>
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                包含业务步骤流程及底层数据实体属性建模。
              </p>
              {!isHowComplete && (
                <button
                  onClick={() => navigate('/flow')}
                  className="mt-auto text-[10px] text-indigo-600 hover:text-indigo-700 font-bold text-left"
                >
                  前往建模流程与数据 &rarr;
                </button>
              )}
            </div>

            <div className={`rounded-2xl border p-4 flex flex-col gap-3 transition-colors ${isScopeComplete ? 'border-emerald-200 bg-emerald-50/20' : 'border-amber-200 bg-amber-50/20'}`}>
              <div className="flex justify-between items-center">
                <span className="text-xs font-bold text-slate-900">Scope 交付范围决策</span>
                <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${isScopeComplete ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                  {isScopeComplete ? '已就绪' : '待补充'}
                </span>
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                至少对系统内的一项功能叶子节点标记了交付决策。
              </p>
              {!isScopeComplete && (
                <button
                  onClick={() => navigate('/scope')}
                  className="mt-auto text-[10px] text-indigo-600 hover:text-indigo-700 font-bold text-left"
                >
                  前往划分交付范围 &rarr;
                </button>
              )}
            </div>
          </div>

          <div className="border-t border-slate-100 pt-6 flex flex-col sm:flex-row gap-4 items-center justify-between">
            <div className="text-left space-y-0.5">
              <div className="text-xs font-bold text-slate-700">想直接模拟预览交互原型？</div>
              <div className="text-[10px] text-slate-400">系统能够使用 AI 临时补全缺失的业务流和角色进行仿真演示。</div>
            </div>
            <button
              onClick={() => setIsForceGenerated(true)}
              className="w-full sm:w-auto py-2.5 px-6 rounded-xl bg-slate-900 text-white text-xs font-bold hover:bg-slate-800 transition-colors shadow-sm flex items-center justify-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5" />
              ✨ AI 智能推演并模拟预览 (强行生成)
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex w-full relative">
      <div className="flex-1 p-6 pb-24 overflow-y-auto">
        <div className="max-w-[1200px] mx-auto space-y-8 animate-in fade-in flex flex-col">
          
          {/* AI Simulation Temporary Draft Warning Banner */}
          {isForceGenerated && !isPreviewReady && (
            <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-6 border border-amber-200 shadow-md animate-in slide-in-from-top-4 duration-500 space-y-4">
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div className="flex items-center gap-2.5">
                  <span className="p-1.5 bg-amber-100 text-amber-700 rounded-lg shrink-0">
                    <Sparkles className="w-5 h-5 animate-pulse" />
                  </span>
                  <div>
                    <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                      AI 智能仿真预推演草稿激活
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">检测到当前项目在 What/How/Scope 维度有未定义元素。已在前端沙箱中动态补全以供评估。</p>
                  </div>
                </div>
                <div className="flex gap-2 shrink-0 w-full md:w-auto">
                  <button
                    onClick={mergeForceGeneratedToProject}
                    className="flex-1 md:flex-none flex items-center justify-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl transition-colors shadow-sm"
                  >
                    <Check className="w-3.5 h-3.5" />
                    采纳并合并至项目正式数据
                  </button>
                  <button
                    onClick={discardForceGenerated}
                    className="flex-1 md:flex-none flex items-center justify-center gap-1.5 px-3 py-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 text-xs font-bold rounded-xl transition-colors"
                  >
                    <X className="w-3.5 h-3.5" />
                    舍弃临时推演
                  </button>
                </div>
              </div>
              <p className="text-[11px] text-amber-800 bg-amber-100/40 p-3 rounded-xl border border-amber-100/60 leading-relaxed font-medium">
                说明：仿真推演的数据（如角色“仿真业务主管”、流程“AI 仿真业务调拨与审批验证主流程”等）目前<b>仅在沙箱内存中临时有效</b>。除非您点击上方的“采纳并合并”，否则一旦您刷新页面或点击“舍弃推演”，这些临时数据将被即刻清空，绝不污染您既有的正式需求空间底账。
              </p>
            </div>
          )}

          {/* Solution Preview and Assets Export bar */}
          <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col lg:flex-row justify-between lg:items-center gap-6 animate-in fade-in duration-300">
            <div className="space-y-1">
              <h2 className="text-xl font-black text-slate-900 tracking-tight flex items-center gap-2">
                <LayoutDashboard className="w-5 h-5 text-indigo-500 shrink-0" />
                业务方案预览与资产导出
              </h2>
              <p className="text-xs text-slate-500 leading-relaxed max-w-2xl font-medium">
                在此可全盘预览由 What (角色与特征) &rarr; How (流程与数据) &rarr; Scope (交付范围) 自动融成型的一致性成果，并可打包下载为方案资产。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={() => handleExport('markdown')}
                disabled={exportState === 'exporting'}
                className="px-4 py-2.5 rounded-xl border border-slate-200 text-slate-700 text-xs font-bold hover:bg-slate-50 hover:border-slate-300 transition-colors bg-white flex items-center gap-1.5 shadow-sm"
              >
                <FileDown className="w-3.5 h-3.5 text-indigo-500" />
                导出 Markdown 需求方案书
              </button>
              <button 
                onClick={() => handleExport('json')}
                disabled={exportState === 'exporting'}
                className="px-4 py-2.5 rounded-xl border border-slate-200 text-slate-700 text-xs font-bold hover:bg-slate-50 hover:border-slate-300 transition-colors bg-white flex items-center gap-1.5 shadow-sm"
              >
                {exportState === 'idle' && (
                  <>
                    <FileDown className="w-3.5 h-3.5 text-emerald-500" /> 
                    导出 JSON 数据模型
                  </>
                )}
                {exportState === 'exporting' && <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> 正在生成</>}
                {exportState === 'success' && <><CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> 已导出</>}
              </button>
              <button
                onClick={() => void exportAuditLog()}
                disabled={exportState === 'exporting'}
                className="px-4 py-2.5 rounded-xl border border-slate-200 text-slate-700 text-xs font-bold hover:bg-slate-50 hover:border-slate-300 transition-colors bg-white flex items-center gap-1.5 shadow-sm"
              >
                <CheckSquare className="w-3.5 h-3.5 text-sky-500" />
                导出审计日志 (Audit)
              </button>
            </div>
          </section>

          <div className="flex flex-col gap-8">
            <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
              <h3 className="font-bold text-slate-900 mb-4">进入实现前 Checkpoints</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                {checkpoints.map((checkpoint) => (
                  <div key={checkpoint.id} className={`rounded-xl border p-4 ${checkpoint.passed ? 'border-emerald-200 bg-emerald-50/50' : 'border-amber-200 bg-amber-50/50'}`}>
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-bold text-slate-900">{checkpoint.title}</div>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${checkpoint.passed ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                        {checkpoint.passed ? '通过' : '待补齐'}
                      </span>
                    </div>
                    <div className="mt-3 space-y-2">
                      {checkpoint.checks.map((check) => (
                        <button
                          key={check.label}
                          type="button"
                          onClick={() => jumpToProjection(checkpoint.projection)}
                          className="w-full text-left rounded-lg bg-white/80 border border-white px-3 py-2 text-xs text-slate-700 hover:border-slate-300 transition-colors"
                        >
                          <span className={`mr-2 inline-block w-2 h-2 rounded-full ${check.passed ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
                          {check.label}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm relative overflow-x-auto w-full">
              <h3 className="font-bold text-slate-900 mb-6">系统流程连贯性概览 (主线泳道)</h3>
              
              <div className="flex min-w-[800px] gap-4">
                {system.swimlanes.map((lane) => (
                  <div key={lane} className="flex-1 border bg-slate-50/50 border-slate-100 rounded-xl flex flex-col min-h-[400px]">
                    <div className="p-3 border-b border-slate-100 bg-white rounded-t-xl shrink-0">
                       <h3 className="text-xs font-bold text-center text-slate-600">{lane}</h3>
                    </div>
                    <div className="flex-1 p-3 space-y-4 relative isolate">
                       {system.getStepsBySwimlane(lane).map(step => {
                        const nextSteps = system.getNextStepTitles(step.id);
                        const excSteps = system.getExceptionStepTitles(step.id);
                        const linkedSlots = system.getStepSlots(step.id);
                        const stepDetail = buildStepDetail(draftIr, step.id);
                        
                        return (
                          <div key={step.id} className="relative z-10 w-full" onClick={() => setSelectedObject(step)}>
                            <div className={`
                              rounded-xl transition-all cursor-pointer shadow-sm
                              ${selectedObject?.id === step.id ? 'ring-2 ring-indigo-500 ring-offset-2 border-transparent' : 'border border-transparent hover:border-indigo-300'}
                              ${highlightTarget === step.id ? 'ring-2 ring-amber-400' : ''}
                            `}>
                              <FlowStepCard 
                                name={step.title}
                                type={step.stepType}
                                actor={lane}
                                status={step.status}
                                inputs={stepDetail.inputs}
                                outputs={stepDetail.outputs}
                                rules={stepDetail.rules}
                                stateChanges={stepDetail.stateChanges}
                                relatedPages={stepDetail.relatedPages}
                                relatedIssueCount={stepDetail.relatedIssueIds.length}
                                relatedChoiceCount={stepDetail.relatedChoiceIds.length}
                                nextSteps={nextSteps.length > 0 ? nextSteps : undefined}
                                exceptionSteps={excSteps.length > 0 ? excSteps : undefined}
                                slots={linkedSlots}
                                active={selectedObject?.id === step.id}
                                onClick={() => setSelectedObject(step)}
                                onSlotClick={(slotId) => {
                                  const slot = draftIr?.slots?.[slotId];
                                  if (slot) setSelectedObject(slot);
                                }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm flex-1 animate-in fade-in duration-350">
              <div className="border-b border-slate-200 pb-4 mb-6 flex flex-col sm:flex-row justify-between sm:items-center gap-4">
                <div>
                  <h3 className="text-base font-black text-slate-900 tracking-tight flex items-center gap-2">
                    <span className="w-1.5 h-4 bg-sky-500 rounded-full inline-block"></span>
                    交互原型与功能页面预览
                  </h3>
                  <p className="text-[11px] text-slate-400 mt-0.5 leading-normal font-medium">
                    根据 What 阶段建立的能力树叶子节点，为每个业务执行角色自动生成对应的标准高保真界面原型。
                  </p>
                </div>
                
                {/* Active Role selection Dropdown */}
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs text-slate-500 font-bold">视角执行角色:</span>
                  <select
                    value={activeRoleIndex}
                    onChange={(e) => setActiveRoleIndex(parseInt(e.target.value, 10))}
                    className="px-3 py-1.5 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-xl text-xs font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all shadow-sm cursor-pointer min-w-[160px]"
                  >
                    {actors.map((actor, idx) => (
                      <option key={actor.id} value={idx}>
                        👤 {actor.title}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              
              <div className="pt-2">
                {activeRole && (
                  <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2">
                    {pages.length === 0 ? (
                      <div className="text-center py-16 border border-dashed border-slate-200 rounded-3xl bg-slate-50/50 space-y-3">
                        <div className="mx-auto w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center text-slate-400">
                          <Eye className="w-6 h-6" />
                        </div>
                        <div className="text-sm font-bold text-slate-700">当前角色下暂未绑定具体功能叶子节点</div>
                        <div className="text-xs text-slate-400 max-w-sm mx-auto">
                          页面模型由角色所涉及的叶子功能能力点（Leaf Capabilities）自动生成。请先在 "要做什么" 阶段为当前角色绑定叶子功能点并设定涉及的执行者。
                        </div>
                      </div>
                    ) : (
                      pages.map((p) => (
                        <div key={p.id} className="bg-slate-900/5 rounded-3xl p-1 border border-slate-200 shadow-lg overflow-hidden bg-white">
                          {/* Browser Window Mockup Header */}
                          <div className="bg-slate-50 border-b border-slate-200 px-4 py-3 flex items-center gap-3">
                            {/* Window control dots */}
                            <div className="flex gap-1.5 shrink-0">
                              <span className="w-3 h-3 rounded-full bg-rose-400 inline-block"></span>
                              <span className="w-3 h-3 rounded-full bg-amber-400 inline-block"></span>
                              <span className="w-3 h-3 rounded-full bg-emerald-400 inline-block"></span>
                            </div>
                            {/* Address Bar */}
                            <div className="flex-1 bg-white border border-slate-200/80 rounded-lg px-3 py-1 text-[11px] text-slate-400 font-mono flex items-center gap-1.5 shadow-inner">
                              <span className="text-slate-300">https://</span>
                              <span className="text-slate-700 font-medium">workbench.ai</span>
                              <span className="text-slate-400">/projects/{draftIr?.projectId || 'current'}/screens/{p.id}</span>
                            </div>
                            {/* Extra Info Label */}
                            <div className="text-[10px] bg-sky-50 text-sky-700 px-2 py-0.5 rounded-md font-bold uppercase tracking-wider shrink-0 border border-sky-100">
                              {activeRole.title} 专属页面
                            </div>
                          </div>

                          {/* Page Contents */}
                          <div className="p-6 space-y-6">
                            {/* Title & Description of feature interface */}
                            <div className="border-b border-slate-100 pb-5">
                              <h4 className="text-sm font-black text-slate-900 flex items-center gap-2">
                                <span className="w-2.5 h-2.5 rounded-full bg-sky-500"></span>
                                {p.name}
                              </h4>
                              <p className="text-xs text-slate-500 mt-1.5 leading-relaxed font-medium">
                                {p.desc}
                              </p>
                            </div>

                            {/* Gorgeous Double-Column Layout */}
                            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                              
                              {/* Left Column: 可执行操作场景 (User Story) */}
                              <div className="lg:col-span-7 space-y-4">
                                <div className="flex items-center gap-2 px-1">
                                  <span className="p-1 bg-indigo-50 text-indigo-600 rounded-lg">
                                    <Sparkles className="w-3.5 h-3.5" />
                                  </span>
                                  <span className="text-xs font-bold text-slate-700 uppercase tracking-widest">
                                    可执行操作场景 (User Story)
                                  </span>
                                </div>

                                {p.scenarios.length === 0 ? (
                                  <div className="bg-slate-50/50 rounded-2xl p-6 border border-dashed border-slate-200 text-xs text-slate-400 italic text-center">
                                    当前能力叶子节点暂无关联的用户场景，原型界面操作仅可作为通用能力处理。
                                  </div>
                                ) : (
                                  <div className="space-y-4">
                                    {p.scenarios.map((s: any) => (
                                      <div key={s.scenarioId} className="bg-gradient-to-br from-white to-slate-50/40 rounded-2xl p-5 border border-slate-200/80 shadow-sm space-y-3.5 hover:border-slate-300 transition-all">
                                        <div className="flex justify-between items-start gap-2">
                                          <h5 className="font-bold text-slate-900 text-xs tracking-wide">{s.scenarioName}</h5>
                                          <span className="text-[9px] bg-emerald-50 text-emerald-700 font-extrabold px-1.5 py-0.5 rounded border border-emerald-100/50 shrink-0">
                                            已就绪
                                          </span>
                                        </div>

                                        <p className="text-[11px] text-slate-600 leading-relaxed bg-white border border-slate-100 p-2.5 rounded-xl shadow-inner italic font-medium">
                                          "{s.scenarioContent}"
                                        </p>

                                        {/* Acceptance Criteria in user stories */}
                                        <div className="space-y-2 pt-1">
                                          <div className="text-[9px] text-slate-400 font-bold uppercase tracking-wider">验收标准 (Acceptance Criteria)</div>
                                          {(s.acceptanceCriteria || []).length === 0 ? (
                                            <div className="text-[10px] text-slate-400 italic bg-white p-2 rounded-lg border border-dashed border-slate-150">暂无具体验收指标。</div>
                                          ) : (
                                            <div className="grid grid-cols-1 gap-1.5">
                                              {(s.acceptanceCriteria || []).map((ac: any, idx: number) => (
                                                <div key={ac.criterionId || idx} className="flex items-start gap-2 text-[11px] text-slate-600 bg-white p-2 rounded-lg border border-slate-100 shadow-sm">
                                                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0 mt-1.5"></span>
                                                  <span className="leading-relaxed">{ac.criterionContent}</span>
                                                </div>
                                              ))}
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>

                              {/* Right Column: 界面操作触发流程步骤 */}
                              <div className="lg:col-span-5 space-y-4">
                                <div className="flex items-center gap-2 px-1">
                                  <span className="p-1 bg-sky-50 text-sky-600 rounded-lg">
                                    <Play className="w-3.5 h-3.5" />
                                  </span>
                                  <span className="text-xs font-bold text-slate-700 uppercase tracking-widest">
                                    界面操作触发流程步骤
                                  </span>
                                </div>

                                <div className="bg-slate-50/60 rounded-2xl p-5 border border-slate-200/80 shadow-inner space-y-4">
                                  <div className="text-[10px] text-slate-400 leading-relaxed font-medium">
                                    在流程泳道中，当前页面承担了以下具体步骤的交互触达职责：
                                  </div>
                                  <div className="relative pl-6 space-y-6 before:absolute before:left-[11px] before:top-2 before:bottom-2 before:w-0.5 before:border-l-2 before:border-dashed before:border-slate-300">
                                    {p.relatedSteps.map((stepName: string, idx: number) => (
                                      <div key={idx} className="relative group">
                                        {/* Bullet circle */}
                                        <div className="absolute -left-[20px] top-1.5 w-2.5 h-2.5 rounded-full bg-white border-2 border-sky-500 group-hover:bg-sky-500 transition-colors z-10 shadow-sm"></div>
                                        <div className="bg-white rounded-xl p-3 border border-slate-200/60 shadow-sm space-y-1">
                                          <div className="text-[11px] font-extrabold text-slate-800 tracking-wide">{stepName}</div>
                                          <div className="text-[10px] text-slate-400 leading-normal font-medium">
                                            触发角色: {activeRole.title}
                                          </div>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </div>

                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            </section>
          </div>

        </div>
      </div>

      <RightObjectPanel />
    </div>
  );
}
