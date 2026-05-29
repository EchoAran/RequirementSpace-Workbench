import { useEffect, useMemo, useState } from 'react';
import {
  CheckSquare,
  ExternalLink,
  Eye,
  FileDown,
  LayoutDashboard,
  MonitorPlay,
  RefreshCw,
  Sparkles,
  User,
  Folder,
  Workflow,
  BookOpen,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { FlowStepCard } from '@/components/shared/FlowStepCard';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import {
  buildProjectRoute,
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
  shadowDraftId?: string;
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

  const activeShadowDraft = useWorkspaceStore((state) => state.activeShadowDraft);
  const prepareShadowDraft = useWorkspaceStore((state) => state.prepareShadowDraft);
  const getShadowDraft = useWorkspaceStore((state) => state.getShadowDraft);
  const discardShadowDraft = useWorkspaceStore((state) => state.discardShadowDraft);
  const commitShadowDraft = useWorkspaceStore((state) => state.commitShadowDraft);
  const regenerateShadowDraft = useWorkspaceStore((state) => state.regenerateShadowDraft);

  const [activeRoleIndex, setActiveRoleIndex] = useState(0);
  const [exportState, setExportState] = useState<'idle' | 'exporting' | 'success'>('idle');
  const [prototype, setPrototype] = useState<PrototypePreview | null>(null);
  const [prototypeState, setPrototypeState] = useState<PrototypeState>('idle');
  const [prototypeError, setPrototypeError] = useState<string | null>(null);
  const [activePrototypePageId, setActivePrototypePageId] = useState<string>('');
  const [selectedFlowId, setSelectedFlowId] = useState<number | null>(null);

  const [feedbackText, setFeedbackText] = useState('');
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isDraftInitializing, setIsDraftInitializing] = useState(true);

  // Auto trigger shadow draft preparation on load
  useEffect(() => {
    let cancelled = false;
    const projectId = ir?.projectId;
    if (!projectId) {
      setIsDraftInitializing(false);
      return;
    }

    setIsDraftInitializing(true);
    prepareShadowDraft()
      .then(() => {
        if (!cancelled) {
          setIsDraftInitializing(false);
        }
      })
      .catch((err) => {
        console.error('Failed to prepare shadow preview:', err);
        if (!cancelled) {
          setIsDraftInitializing(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [ir?.projectId]);

  // Unified Polling Driver for activeShadowDraft when status is generating
  useEffect(() => {
    if (activeShadowDraft?.source !== 'shadow_project' || activeShadowDraft?.status !== 'generating' || !activeShadowDraft?.draftId) {
      return;
    }

    let cancelled = false;
    const draftId = activeShadowDraft.draftId;

    const timer = setInterval(() => {
      if (cancelled) return;
      getShadowDraft(draftId)
        .then((updated) => {
          if (cancelled) return;
          if (updated.status === 'ready' || updated.status === 'failed') {
            clearInterval(timer);
          }
        })
        .catch(() => {
          clearInterval(timer);
        });
    }, 2000);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [activeShadowDraft?.status, activeShadowDraft?.draftId]);

  // Set prototype state and values based on activeShadowDraft
  useEffect(() => {
    if (!activeShadowDraft) {
      setPrototype(null);
      setPrototypeState('idle');
      return;
    }

    if (activeShadowDraft.source === 'real_project') {
      setPrototype(activeShadowDraft.prototypePreview);
      setPrototypeState('ready');
      setPrototypeError(null);
    } else {
      const status = activeShadowDraft.status;
      if (status === 'generating') {
        setPrototype(null);
        setPrototypeState('loading');
        setPrototypeError(null);
      } else if (status === 'ready') {
        setPrototype(activeShadowDraft.prototypePreview);
        setPrototypeState('ready');
        setPrototypeError(null);
      } else if (status === 'failed') {
        setPrototype(null);
        setPrototypeState('error');
        setPrototypeError('影子方案推演失败，可能由于部分关键关系断裂。你可以刷新工作区或点击重新推演。');
      } else {
        setPrototype(null);
        setPrototypeState('idle');
      }
    }
  }, [activeShadowDraft]);

  // Dynamic substitution of ir with virtual requirement space during shadow ready status
  const spaceToUse = useMemo(() => {
    if (activeShadowDraft?.source === 'shadow_project' && activeShadowDraft.status === 'ready' && activeShadowDraft.shadowSnapshotJson) {
      const snap = activeShadowDraft.shadowSnapshotJson;
      return {
        projectId: snap.project_id || snap.projectId || ir?.projectId,
        projectName: snap.project_name || snap.projectName || snap.name || ir?.projectName,
        projectDescription: snap.project_description || snap.projectDescription || snap.description || ir?.projectDescription,
        userRequirements: snap.user_requirements || snap.userRequirements || ir?.userRequirements,
        actors: snap.actors?.map((a: any) => ({
          actorId: a.actorId || a.id || a.actor_id,
          actorName: a.actorName || a.name || a.actor_name,
          actorDescription: a.actorDescription || a.description || a.actor_description
        })) || [],
        actorsCompatible: snap.actors?.map((a: any) => ({
          id: (a.actorId || a.id || a.actor_id)?.toString(),
          title: a.actorName || a.name || a.actor_name,
          desc: a.actorDescription || a.description || a.actor_description
        })) || [],
        features: snap.features?.map((f: any) => ({
          featureId: f.featureId || f.id || f.feature_id,
          featureName: f.featureName || f.name || f.feature_name,
          featureDescription: f.featureDescription || f.description || f.feature_description,
          actorIds: f.actorIds || f.actor_ids || [],
          parentId: f.parentId || f.parent_id,
          childrenIds: f.childrenIds || f.children_ids || [],
          scenarios: f.scenarios?.map((s: any) => ({
            scenarioId: s.scenarioId || s.id || s.scenario_id,
            scenarioName: s.scenarioName || s.name || s.scenario_name,
            scenarioContent: s.scenarioContent || s.content || s.scenario_content,
            featureId: s.featureId || s.feature_id,
            actorId: s.actorId || s.actor_id,
            acceptanceCriteria: (s.acceptance_criteria || s.acceptanceCriteria)?.map((ac: any) => ({
              criterionId: ac.criterionId || ac.id || ac.criterion_id,
              criterionContent: ac.criterionContent || ac.content || ac.criterion_content,
              position: ac.position
            })) || []
          })) || [],
          scope: f.scope ? {
            scopeId: f.scope.scopeId || f.scope.id || f.scope.scope_id,
            scopeStatus: f.scope.scopeStatus || f.scope.scope_status || f.scope.status,
            reason: f.scope.reason,
            kanoCategory: f.scope.kanoCategory || f.scope.kano_category,
            kanoCategoryName: f.scope.kanoCategoryName || f.scope.kano_category_name
          } : null
        })) || [],
        businessObjects: snap.business_objects?.map((bo: any) => ({
          businessObjectId: bo.businessObjectId || bo.id || bo.business_object_id,
          businessObjectName: bo.businessObjectName || bo.name || bo.business_object_name,
          businessObjectDescription: bo.businessObjectDescription || bo.description || bo.business_object_description,
          businessObjectAttributes: (bo.business_object_attributes || bo.businessObjectAttributes)?.map((attr: any) => ({
            businessObjectAttributeId: attr.businessObjectAttributeId || attr.id || attr.business_object_attribute_id,
            businessObjectAttributeName: attr.businessObjectAttributeName || attr.name || attr.business_object_attribute_name,
            businessObjectAttributeDescription: attr.businessObjectAttributeDescription || attr.description || attr.business_object_attribute_description,
            businessObjectAttributeType: attr.businessObjectAttributeType || attr.data_type || attr.business_object_attribute_type,
            businessObjectAttributeExample: attr.businessObjectAttributeExample || attr.example || attr.business_object_attribute_example
          })) || []
        })) || [],
        flows: snap.flows?.map((fl: any) => ({
          flowId: fl.flowId || fl.id || fl.flow_id,
          flowName: fl.flowName || fl.name || fl.flow_name,
          flowDescription: fl.flowDescription || fl.description || fl.flow_description,
          featureIds: fl.featureIds || fl.feature_ids || [],
          flowSteps: (fl.flow_steps || fl.flowSteps)?.map((step: any) => ({
            stepId: step.stepId || step.id || step.step_id,
            stepName: step.stepName || step.name || step.step_name,
            stepDescription: step.stepDescription || step.description || step.step_description,
            stepType: step.stepType || step.step_type || step.stepType,
            position: step.position,
            actorIds: step.actorIds || step.actor_ids || [],
            inputBusinessObjectIds: step.inputBusinessObjectIds || step.input_business_object_ids || [],
            outputBusinessObjectIds: step.outputBusinessObjectIds || step.output_business_object_ids || [],
            nextStepIds: step.nextStepIds || step.next_step_ids || []
          })) || []
        })) || [],
        issuesCompatible: [],
        perceptionSlot: null
      };
    }
    return ir;
  }, [ir, activeShadowDraft]);

  const isWhatComplete = (spaceToUse?.actors || []).length > 0 && (spaceToUse?.features || []).length > 0;
  const isHowComplete = (spaceToUse?.flows || []).length > 0 && (spaceToUse?.businessObjects || []).length > 0;
  const isScopeComplete = (spaceToUse?.features || []).some((feature) => feature.scope !== null);
  const isPreviewReady = isWhatComplete && isHowComplete && isScopeComplete;

  const actors = useMemo(() => spaceToUse?.actorsCompatible || [], [spaceToUse]);
  const issues = useMemo(() => spaceToUse?.issuesCompatible || [], [spaceToUse]);
  const activeRole = actors[activeRoleIndex];
  
  const pages = useMemo(() => {
    if (!spaceToUse || !activeRole) return [];
    return buildRolePages(spaceToUse as any, activeRole.id);
  }, [activeRole, spaceToUse]);

  const unresolvedIssues = issues.filter((issue: any) => issue.status === 'open');
  const system = useMemo(() => buildSystemProjection(spaceToUse as any), [spaceToUse]);
  
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

  const flows = useMemo(() => spaceToUse?.flows || [], [spaceToUse]);

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

  const handleExport = async (format: 'json' | 'markdown') => {
    if (!spaceToUse?.projectId) return;
    setExportState('exporting');
    try {
      if (format === 'markdown') {
        const md = await workspaceApi.exportMarkdown(spaceToUse.projectId);
        downloadFile(`${spaceToUse.projectName || spaceToUse.projectId || 'requirement-space'}.md`, md, 'text/markdown;charset=utf-8');
      } else {
        const data = await workspaceApi.exportJson(spaceToUse.projectId);
        downloadFile(`${data.projectName || data.projectId || 'requirement-space'}.json`, JSON.stringify(data, null, 2), 'application/json;charset=utf-8');
      }
      setExportState('success');
      setTimeout(() => setExportState('idle'), 1500);
    } catch {
      setExportState('idle');
    }
  };

  const exportAuditLog = async () => {
    if (!spaceToUse) return;
    setExportState('exporting');
    try {
      downloadFile(
        `${spaceToUse.projectName || spaceToUse.projectId || 'requirement-space'}-audit.json`,
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
    if (!spaceToUse?.projectId) return;
    setPrototypeState('loading');
    setPrototypeError(null);
    try {
      const result = await workspaceApi.generatePrototypePreview(spaceToUse.projectId, true);
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

  const handleRegenerate = async () => {
    if (!activeShadowDraft?.draftId) return;
    try {
      await regenerateShadowDraft(activeShadowDraft.draftId, feedbackText);
      setFeedbackText('');
      showToast('影子草稿已发起重新推演，请耐心等待。');
    } catch (err) {
      showToast('重新推演失败：' + (err instanceof Error ? err.message : String(err)));
    }
  };

  const handleDiscard = async () => {
    if (!activeShadowDraft?.draftId) return;
    if (!window.confirm('您确定要舍弃当前的影子草稿吗？此操作不会对您现有的项目数据造成任何修改。')) return;
    try {
      await discardShadowDraft(activeShadowDraft.draftId);
      showToast('影子草稿已舍弃。');
      navigate(buildProjectRoute(spaceToUse?.projectId || ir?.projectId, '/overview'));
    } catch (err) {
      showToast('舍弃影子草稿失败：' + (err instanceof Error ? err.message : String(err)));
    }
  };

  const handleCommit = async () => {
    if (!activeShadowDraft?.draftId) return;
    if (!window.confirm('采纳后，影子沙盒中的所有 AI 补充对象（包括角色、叶子功能、场景、验收标准、时序步骤、Kano交付范围等）将一次性事务性写入正式项目中，以完全闭环所有设计。确定采纳吗？')) return;
    try {
      await commitShadowDraft(activeShadowDraft.draftId);
      showToast('🎉 影子沙盒已成功合并！所有规约已闭环并生成正式 prototype。');
    } catch (err) {
      if (err instanceof Error && err.message.includes('shadow_draft_conflict')) {
        showToast('❌ 合并冲突：在影子草稿推演期间，该项目的真实规约已被其他修改更改，请刷新后重新推演。');
      } else {
        showToast('采纳影子草稿失败：' + (err instanceof Error ? err.message : String(err)));
      }
    }
  };

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  if (isDraftInitializing) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 bg-slate-50 min-h-[85vh] w-full">
        <div className="flex flex-col items-center justify-center space-y-4">
          <div className="w-12 h-12 rounded-full border-4 border-slate-200 border-t-indigo-650 animate-spin" />
          <p className="text-xs font-bold text-slate-500">正在安全加载影子推演沙盒...</p>
        </div>
      </div>
    );
  }

  if (!isPreviewReady && activeShadowDraft?.source !== 'shadow_project') {
    return (
      <div className="flex-1 flex items-center justify-center p-6 bg-slate-50 min-h-[85vh] w-full">
        <div className="max-w-2xl w-full bg-white rounded-3xl p-8 border border-slate-200 shadow-xl space-y-8 animate-in fade-in duration-300">
          <div className="text-center space-y-2">
            <div className="mx-auto w-14 h-14 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shadow-sm mb-3">
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
              onClick={() => navigate(buildProjectRoute(spaceToUse?.projectId || ir?.projectId, '/what'))}
            />
            <ReadinessCard
              title="How"
              ready={isHowComplete}
              description="需要至少定义一个业务流程步骤及相关的数据实体对象。"
              onClick={() => navigate(buildProjectRoute(spaceToUse?.projectId || ir?.projectId, '/flow'))}
            />
            <ReadinessCard
              title="Scope"
              ready={isScopeComplete}
              description="需要对至少一个三级叶子节点做出本期、暂缓或排除决策。"
              onClick={() => navigate(buildProjectRoute(spaceToUse?.projectId || ir?.projectId, '/scope'))}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex w-full relative">
      {/* Toast Alert overlay */}
      {toastMessage && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50 bg-slate-900 text-white border border-slate-700 px-5 py-3 rounded-2xl shadow-2xl flex items-center gap-2.5 text-xs font-bold animate-in fade-in slide-in-from-top-4 duration-300">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-ping inline-block" />
          <span>{toastMessage}</span>
        </div>
      )}

      <div className="flex-1 p-6 pb-24 overflow-y-auto w-full">
        <div className="max-w-[1240px] mx-auto space-y-8 animate-in fade-in flex flex-col">
          
          {/* Header Banner */}
          <section className="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm flex flex-col lg:flex-row justify-between lg:items-center gap-6">
            <div className="space-y-1">
              <h2 className="text-xl font-black text-slate-900 tracking-tight flex items-center gap-2">
                <LayoutDashboard className="w-5 h-5 text-indigo-600 shrink-0" />
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

          {/* Shadow Sandbox Banner */}
          {activeShadowDraft?.source === 'shadow_project' && activeShadowDraft.status === 'ready' && (
            <div className="rounded-3xl border border-indigo-100 bg-gradient-to-br from-indigo-50 via-white to-slate-50 p-5 shadow-sm animate-in slide-in-from-top duration-300">
              <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                <div className="space-y-3">
                  <div className="inline-flex items-center gap-2 rounded-full border border-indigo-100 bg-white px-3 py-1 text-[10px] font-extrabold uppercase tracking-[0.18em] text-indigo-700 shadow-sm">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                    AI 影子收敛预览
                  </div>
                  <div className="space-y-1.5">
                    <h3 className="text-sm font-black tracking-tight text-slate-900">
                      规约尚未完全收敛，当前为您生成了可安全预览的影子方案
                    </h3>
                    <p className="text-xs leading-relaxed text-slate-500">
                      这是一份 AI 补充后的沙盒草稿，用于提前预览补全后的原型与结构，不会直接覆盖正式项目。
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-xs font-medium text-slate-600">
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 shadow-sm">
                      <User className="w-3 h-3 text-indigo-500 shrink-0" />
                      +{activeShadowDraft.shadowSummary?.actors || 0} 角色
                    </span>
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 shadow-sm">
                      <Folder className="w-3 h-3 text-indigo-500 shrink-0" />
                      +{activeShadowDraft.shadowSummary?.features || 0} 功能
                    </span>
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 shadow-sm">
                      <Workflow className="w-3 h-3 text-indigo-500 shrink-0" />
                      +{activeShadowDraft.shadowSummary?.flows || 0} 业务流
                    </span>
                    <span className="inline-flex items-center rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1 text-emerald-700 shadow-sm">
                      Kano 范围已评估
                    </span>
                  </div>
                </div>

                <div className="flex w-full flex-col gap-2.5 lg:w-auto lg:min-w-[380px]">
                  <div className="flex overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                    <input
                      type="text"
                      placeholder="输入调整意见，例如：增加管理员审核..."
                      value={feedbackText}
                      onChange={(e) => setFeedbackText(e.target.value)}
                      className="flex-1 border-0 bg-transparent px-3 py-2 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={handleRegenerate}
                      className="border-l border-slate-200 bg-slate-50 px-3 py-2 text-xs font-bold text-slate-700 transition-colors hover:bg-slate-100"
                    >
                      重新推演
                    </button>
                  </div>
                  <div className="flex flex-wrap items-center justify-end gap-2.5">
                    <button
                      type="button"
                      onClick={handleDiscard}
                      className="px-3.5 py-2 rounded-xl border border-slate-200 bg-white text-slate-600 text-xs font-bold hover:bg-slate-50 transition-colors shadow-sm"
                    >
                      舍弃影子草稿
                    </button>
                    <button
                      type="button"
                      onClick={handleCommit}
                      className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-black hover:bg-indigo-700 transition-colors shadow-sm"
                    >
                      采纳并合入正式项目
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Integrated Side-by-Side Interactive Prototype & Blueprints Panel */}
          <section className="bg-white rounded-3xl border border-slate-200 shadow-md overflow-hidden">
            <div className="border-b border-slate-200 px-6 py-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-slate-50/50">
              <div>
                <h3 className="text-base font-black text-slate-900 tracking-tight flex items-center gap-2">
                  <MonitorPlay className="w-5 h-5 text-teal-600" />
                  快速原型
                </h3>
              </div>
              
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={openPrototypeInWindow}
                  disabled={!prototypeSrcDoc || prototypeState === 'loading'}
                  className="px-3.5 py-2 rounded-xl border border-slate-200 text-slate-700 text-xs font-bold hover:bg-slate-50 transition-colors bg-white flex items-center gap-1.5 disabled:opacity-50 shadow-sm"
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
                <div className="bg-white border border-slate-200 rounded-2xl shadow-xl overflow-hidden flex flex-col h-[740px]">
                  <div className="h-10 px-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between shrink-0">
                    <div className="flex gap-1.5 items-center">
                      <span className="w-2.5 h-2.5 rounded-full bg-rose-400 inline-block" />
                      <span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block" />
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block" />
                      <span className="ml-3 text-xs text-slate-400 font-mono select-none truncate">
                        /projects/{spaceToUse?.projectId || 'current'}/roles/{activeRole?.title || 'role'}/{activePrototypePage?.featureName || 'prototype'}
                      </span>
                    </div>
                    <span className="text-[10px] bg-slate-200 border border-slate-300 text-slate-500 px-2 py-0.5 rounded font-mono font-bold select-none">
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
                          className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-colors ${
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
                  <div className="flex-1 bg-white relative animate-in fade-in">
                    {prototypeState === 'loading' ? (
                      <div className="h-full flex flex-col items-center justify-center p-8 text-center bg-slate-50 space-y-4">
                        <div className="w-12 h-12 rounded-full border-4 border-slate-200 border-t-indigo-650 animate-spin" />
                        <h4 className="text-xs font-black text-slate-800 tracking-wide select-none">
                          <span className="flex items-center gap-1.5 justify-center"><Sparkles className="w-4 h-4 text-indigo-500 animate-pulse shrink-0" /> AI 正在推演影子沙盒与界面原型...</span>
                        </h4>
                        <p className="text-xs text-slate-500 max-w-sm leading-relaxed font-medium">
                          检测到部分规约尚未收敛（有未满足的What/How/Scope阶段硬规则）。
                          系统正在影子收敛推演算法下，自动为您编排补充结构缺漏并生成全套高保真可运行原型，请稍候。
                        </p>
                      </div>
                    ) : prototypeState === 'error' ? (
                      <PrototypePlaceholder label={prototypeError || '原型推演拼装失败，请保证特征树与流程完整性。'} tone="error" />
                    ) : prototype ? (
                      <iframe
                        key={prototype.shadowDraftId || prototype.prototypeId}
                        title={`${activeRole?.title || spaceToUse?.projectName || 'Project'} prototype`}
                        srcDoc={prototypeSrcDoc}
                        sandbox="allow-scripts"
                        className="w-full h-full border-0 bg-white"
                      />
                    ) : (
                      <PrototypePlaceholder label="当前项目还没有原型。影子草稿加载中..." />
                    )}
                  </div>
                </div>
              </div>

              {/* Right Column: Dynamic Role Blueprint Specifications */}
              <div className="lg:col-span-5 p-6 overflow-y-auto max-h-[788px] space-y-6 flex flex-col">
                <div className="border-b border-slate-100 pb-3 flex items-center justify-between shrink-0">
                  <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1">
                    <span className="flex items-center gap-1.5"><BookOpen className="w-4 h-4 text-slate-500 shrink-0" /> 角色界面与交互规格说明</span>
                  </h4>
                  <span className="text-[10px] bg-indigo-50 border border-indigo-100 text-indigo-700 font-extrabold px-2 py-0.5 rounded">
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
                          ? 'bg-white text-indigo-600 shadow-sm border border-indigo-100/50' 
                          : 'text-slate-500 hover:text-slate-700'
                      }`}
                    >
                      <span className="flex items-center gap-1"><User className="w-3.5 h-3.5 text-indigo-500 shrink-0" /> {actor.title}</span>
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
                      <div className="text-xs text-slate-400 max-w-xs mx-auto leading-relaxed">
                        请先在 What 阶段为角色勾选关联具体的功能点，或在 How 阶段配置该角色协作的步骤节点。
                      </div>
                    </div>
                  ) : (
                    pages.map((page) => (
                      <div key={page.id} className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4 hover:border-slate-300 transition-colors">
                        <div className="border-b border-slate-100 pb-3">
                          <h5 className="font-extrabold text-slate-800 text-xs flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                            {page.name}
                          </h5>
                          <p className="text-xs text-slate-500 mt-1 leading-relaxed font-medium">{page.desc}</p>
                        </div>
                        
                        <div className="space-y-4">
                          <div>
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-2">本期验收场景 (AC)</span>
                            {page.scenarios.length === 0 ? (
                              <span className="text-xs text-slate-400 italic block bg-slate-50 p-2.5 rounded-xl border border-slate-100">暂无关联的交付场景。</span>
                            ) : (
                              <div className="space-y-2.5">
                                {page.scenarios.map((scenario: any) => (
                                  <div
                                    key={scenario.scenarioId}
                                    onClick={() => setSelectedObject({ ...scenario, kind: 'scenario' })}
                                    className="w-full text-left bg-slate-50 border border-slate-200 rounded-xl p-3 space-y-2 hover:border-indigo-300 transition-all cursor-pointer"
                                  >
                                    <h6 className="font-bold text-slate-800 text-xs truncate">{scenario.scenarioName}</h6>
                                    <p className="text-[10px] text-slate-500 leading-relaxed bg-white border border-slate-100 p-2 rounded-lg italic">
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
                                <span className="text-xs text-slate-400 italic">暂无步骤关联。</span>
                              ) : (
                                page.relatedSteps.map((stepName: string, idx: number) => (
                                  <div key={`${stepName}-${idx}`} className="bg-white rounded-lg p-2.5 border border-slate-200/50 shadow-sm flex items-center justify-between">
                                    <span className="text-[10px] font-bold text-slate-700 truncate">{stepName}</span>
                                    <span className="text-[10px] bg-indigo-50 border border-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded font-extrabold shrink-0">
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
            <section className="bg-amber-50 rounded-2xl border border-amber-200 p-5 shadow-sm">
              <h3 className="font-bold text-amber-900 mb-1.5 flex items-center gap-1.5 text-xs">
                <span>⚠️ 发现未闭环的系统设计 Issue ({unresolvedIssues.length} 项)</span>
              </h3>
              <p className="text-xs text-amber-800 leading-relaxed font-medium">
                工作区目前包含未决的业务冲突或流程空白，建议在最终导出产品规格说明前，返回“做什么”和“如何工作”页面修复这些问题。
              </p>
            </section>
          )}

          {/* End-to-End Business Flow Chronological Timelines */}
          <section className="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm relative w-full">
            <div className="mb-6 border-b border-slate-100 pb-4">
              <h3 className="text-base font-extrabold text-slate-900">业务流时序图</h3>
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
                      : 'bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200/60'
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
              </div>
              
              <div className="flex-1 w-full max-w-3xl mx-auto">
                {activeFlowSteps.length === 0 ? (
                  <div className="text-center py-20 text-xs text-slate-400 italic">
                    当前业务流程暂无任何步骤定义。
                  </div>
                ) : (
                  <div className="relative pl-8 border-l-2 border-indigo-200 space-y-8 py-2">
                    {activeFlowSteps.map((step, idx) => {
                      const stepDetail = buildStepDetail(spaceToUse as any, step.stepId);
                      const performerId = (step.actorIds || [])[0];
                      const performer = (spaceToUse?.actors || []).find((a) => a.actorId === performerId);
                      const actorName = performer ? performer.actorName : '系统自动';

                      const nextSteps = (step.nextStepIds || [])
                        .map((nid) => activeFlowSteps.find((s) => s.stepId === nid)?.stepName)
                        .filter(Boolean) as string[];

                      const stepSlots: any[] = [];
                      if (spaceToUse?.perceptionSlot && spaceToUse.perceptionSlot.perceptionJobId === step.stepId) {
                        stepSlots.push({
                          id: spaceToUse.perceptionSlot.perceptionSlotId.toString(),
                          title: spaceToUse.perceptionSlot.perceptionKind,
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
                              ? 'bg-indigo-600 border-indigo-200 text-white shadow-md shadow-indigo-600/20'
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
                              if (spaceToUse?.perceptionSlot && spaceToUse.perceptionSlot.perceptionSlotId.toString() === slotId) {
                                setSelectedObject(spaceToUse.perceptionSlot);
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
        <span className={`text-[10px] font-extrabold px-1.5 py-0.5 rounded border uppercase tracking-wider ${ready ? 'bg-emerald-50 border-emerald-100 text-emerald-800' : 'bg-amber-50 border-amber-100 text-amber-800'}`}>
          {ready ? '已就绪' : '待完善'}
        </span>
      </div>
      <p className="text-xs text-slate-500 leading-relaxed font-medium">{description}</p>
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
      className="px-4 py-2.5 rounded-xl border border-slate-200 text-slate-700 text-xs font-bold hover:bg-slate-50 hover:border-slate-300 transition-colors bg-white flex items-center gap-1.5 shadow-sm disabled:opacity-60 font-semibold"
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
