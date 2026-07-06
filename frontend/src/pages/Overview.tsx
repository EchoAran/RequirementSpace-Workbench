import { IssueCard } from '@/components/shared/IssueCard';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { ChoiceCard } from '@/components/shared/ChoiceCard';
import { ChoiceGroupPreviewModal } from '@/components/shared/ChoiceGroupPreviewModal';
import { StaleChoiceDialog } from '@/components/shared/StaleChoiceDialog';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { useNavigate } from 'react-router-dom';
import { ConfirmationWorkspace } from '@/components/collaboration/ConfirmationWorkspace';
import { useState, useCallback, useEffect, useMemo } from 'react';
import { buildOverviewModel, buildPageHealth, buildProjectRoute, projectionPath } from '@/core/selectors';
import {
  useWorkspaceStore,
  selectChoices
} from '@/store/useWorkspaceStore';
import { Cpu, Database, RefreshCw, Sliders } from 'lucide-react';
import { NodeKindToRoute, NodeKindToText, Finding } from '@/core/schema';
import { findingProjection } from '@/core/findingPresentation';
import { getAuditActionTypeLabel } from '@/core/auditActionLabels';

export function Overview() {
  const {
    setSelectedObject,
    acceptChoice,
    rejectChoice,
    executeFindingIssueResolution,
    expandSlot,
    updateIssueAttributes,
    refreshWorkspace,
    requestStageTransition,
    startFindingSuggestion,
    activeChoiceGroup,
    isGeneratingChoices,
    choiceGroupGenerationProgress,
    activeStaleChoice,
    clearStaleChoice,
    regenerateChoiceGroup,
    deferOnboardingChoiceGroup,
    discardChoiceGroup,
    backendChoiceGroups,
  } = useWorkspaceStore();
  const navigate = useNavigate();

  const choices = useWorkspaceStore(selectChoices);
  const ir = useWorkspaceStore(state => state.ir);
  const auditLogs = useWorkspaceStore(state => state.auditLogs);

  const overview = buildOverviewModel(ir, auditLogs);
  const openIssues = overview.openIssues;
  const highRiskIssues = overview.highRiskIssues;
  const decisionQueue = overview.decisionQueue;
  const recentChoices = overview.recentChoices.length ? overview.recentChoices : choices.filter((c: any) => c.status === 'candidate').slice(0, 3);
  const stageHealths = [
    { stage: 'what', label: 'What', route: '/what' as const, health: buildPageHealth(ir, '/what') },
    { stage: 'how', label: 'How', route: '/flow' as const, health: buildPageHealth(ir, '/flow') },
    { stage: 'scope', label: 'Scope', route: '/scope' as const, health: buildPageHealth(ir, '/scope') },
  ];
  const activeStageHealth = stageHealths.find((item) => !item.health.disabled);
  const activeSuggestionEntry = stageHealths.find((item) => item.health.nextSlot);
  const nextSlot = activeSuggestionEntry?.health.nextSlot;

  // Use backend findings next_action as primary suggestion source
  const findingsByView = useWorkspaceStore((s) => s.findingsByView);
  const isLoading = useWorkspaceStore((s) => s.isLoading);
  const backendNextAction = (findingsByView?.next_action || []).find((f) => !!f);
  const stageProgress = useWorkspaceStore((s) => s.stageProgress);
  const projectConfiguration = useWorkspaceStore((s) => s.projectConfiguration);
  const fetchProjectConfiguration = useWorkspaceStore((s) => s.fetchProjectConfiguration);

  useEffect(() => {
    if (ir?.projectId && typeof fetchProjectConfiguration === 'function') {
      void fetchProjectConfiguration(ir.projectId);
    }
  }, [ir?.projectId, fetchProjectConfiguration]);

  const activeProgressStage = stageProgress?.stages?.find((s: any) => s.statusCode !== 'ready');
  const progressNextAction = activeProgressStage?.nextAction || activeProgressStage?.next_action;

  const handleProgressAction = useCallback(() => {
    if (!activeProgressStage || !progressNextAction) return;
    const kind = progressNextAction.kind;
    const stage = activeProgressStage.stage;

    const actionMap: Record<string, string> = {
      'what': 'enter_how',
      'how': 'enter_scope',
      'scope': 'enter_preview'
    };

    const dummyFinding: Finding = {
      findingId: `overview:${kind}:${stage}`,
      type: 'next_suggestion',
      stage: stage as any,
      code: stage === 'what' ? 'ENTER_HOW' : stage === 'how' ? 'ENTER_SCOPE' : 'ENTER_PREVIEW',
      severity: 'info',
      title: progressNextAction.label || '继续处理',
      description: activeProgressStage.statusLabel || '',
      blockingScope: 'none',
      metadata: {
        action: {
          kind,
          transition_action: progressNextAction.transitionAction || progressNextAction.transition_action || actionMap[stage],
          route: progressNextAction.route
        }
      }
    };
    void startFindingSuggestion(dummyFinding, { navigate });
  }, [activeProgressStage, progressNextAction, startFindingSuggestion, navigate, ir?.projectId]);

  const [previewChoiceId, setPreviewChoiceId] = useState<string | number | null>(null);
  const [selectedAuditActionTypes, setSelectedAuditActionTypes] = useState<string[]>([]);

  const auditActionTypes = useMemo(() => {
    return Array.from(new Set(auditLogs.map((log: any) => log.actionType).filter(Boolean))).sort();
  }, [auditLogs]);

  const filteredAuditOperations = useMemo(() => {
    const selectedTypes = new Set(selectedAuditActionTypes);
    return [...auditLogs]
      .sort((a: any, b: any) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .filter((operation: any) => selectedTypes.size === 0 || selectedTypes.has(operation.actionType));
  }, [auditLogs, selectedAuditActionTypes]);

  const toggleAuditActionType = useCallback((actionType: string) => {
    setSelectedAuditActionTypes((current) =>
      current.includes(actionType)
        ? current.filter((item) => item !== actionType)
        : [...current, actionType]
    );
  }, []);

  const openChoiceGroupPreview = useCallback((group: any, choiceId?: string | number | null) => {
    if (!group) return;
    setPreviewChoiceId(choiceId ?? null);
    useWorkspaceStore.setState({ activeChoiceGroup: group });
  }, []);

  const handlePreviewChoice = useCallback((choice: any) => {
    const groupId = choice.choiceGroupId ?? choice.choice_group_id;
    const groupFromRecord = groupId !== undefined && groupId !== null
      ? backendChoiceGroups?.[String(groupId)]
      : null;
    const matchedGroup = groupFromRecord || Object.values(backendChoiceGroups || {}).find((group: any) => {
      if (groupId !== undefined && groupId !== null && String(group.id) === String(groupId)) {
        return true;
      }
      return (group.choices || []).some((candidate: any) => String(candidate.id) === String(choice.id));
    });

    if (matchedGroup) {
      openChoiceGroupPreview(matchedGroup, choice.id);
    }
  }, [backendChoiceGroups, openChoiceGroupPreview]);

  const handleDeferChoiceGroupPreview = useCallback(() => {
    setPreviewChoiceId(null);
    useWorkspaceStore.setState({ activeChoiceGroup: null });
  }, []);

  const openIssueFlow = async (issueId: string) => {
    const slotId = await executeFindingIssueResolution(issueId);
    if (slotId) {
      await expandSlot(slotId);
    }
  };

  const jumpToProjection = (projection: any) => {
    return navigate(buildProjectRoute(ir?.projectId, projectionPath(projection)));
  };

  const projectionLabel: Record<string, string> = {
    goal: '目标',
    role: '角色',
    system: '流程',
    data: '数据',
    ui: '界面',
  };

  const queueKindLabel: Record<string, string> = {
    choiceGroup: '方案选择',
  };

  let headlineTone = {
    title: '当前模型已基本收敛',
    badgeClass: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  };

  if (stageProgress && stageProgress.stages) {
    if (activeProgressStage) {
      if (activeProgressStage.statusCode === 'not_started' || activeProgressStage.statusCode === 'unlocked_not_started') {
        headlineTone = {
          title: '当前模型尚未开始构建',
          badgeClass: 'border-slate-200 bg-slate-50 text-slate-700',
        };
      } else if (activeProgressStage.statusCode === 'ready_to_advance') {
        headlineTone = {
          title: '前置阶段建模就绪，可推进',
          badgeClass: 'border-amber-200 bg-amber-50 text-amber-700',
        };
      } else if (activeProgressStage.statusCode === 'blocked') {
        headlineTone = {
          title: '当前存在阻塞卡点',
          badgeClass: 'border-rose-200 bg-rose-50 text-rose-700',
        };
      } else {
        headlineTone = {
          title: '当前模型仍在持续完善',
          badgeClass: 'border-sky-200 bg-sky-50 text-sky-700',
        };
      }
    }
  } else {
    headlineTone =
      overview.openSlotsCount > 0
        ? {
            title: '当前存在阻塞卡点',
            badgeClass: 'border-rose-200 bg-rose-50 text-rose-700',
          }
        : openIssues.length > 0
          ? {
              title: '当前仍有待处理问题',
              badgeClass: 'border-rose-200 bg-rose-50 text-rose-700',
            }
          : activeStageHealth?.health.statusCode === 'not_started'
            ? {
                title: '当前模型尚未开始构建',
                badgeClass: 'border-slate-200 bg-slate-50 text-slate-700',
              }
            : activeStageHealth && activeStageHealth.health.statusCode !== 'ready'
              ? {
                  title: '当前模型仍在持续完善',
                  badgeClass: 'border-sky-200 bg-sky-50 text-sky-700',
                }
              : {
                  title: '当前模型已基本收敛',
                  badgeClass: 'border-emerald-200 bg-emerald-50 text-emerald-700',
                };
  }

  const headlineStats = [
    {
      label: '建模覆盖率',
      value: `${overview.readiness.overallScore}%`,
      tone: 'text-indigo-700',
    },
    {
      label: '待处理问题',
      value: String(openIssues.length).padStart(2, '0'),
      tone: 'text-rose-600',
    },
    {
      label: '待决策方案组',
      value: String(overview.openChoiceGroupsCount).padStart(2, '0'),
      tone: 'text-sky-700',
    },
  ];
  const generationStrategy = projectConfiguration?.generation_strategy;
  const knowledgeSummary = projectConfiguration?.knowledge;
  const llmSummary = projectConfiguration?.llm;
  const configCards = [
    {
      key: 'ai-strategies',
      title: 'AI 生成策略',
      icon: Sliders,
      summary: generationStrategy?.source === 'project' ? '项目自定义策略' : '系统默认策略',
      meta: `${generationStrategy?.candidate_count ?? 2} 个候选 · ${(generationStrategy?.strategies || []).filter((s: any) => s.enabled).length || 2} 个启用策略`,
    },
    {
      key: 'knowledge',
      title: '项目知识库',
      icon: Database,
      summary: `${knowledgeSummary?.document_count ?? 0} 个文档`,
      meta: `${knowledgeSummary?.ai_enabled_count ?? 0} 个可用于 AI · ${knowledgeSummary?.processing_count ?? 0} 个处理中 · ${knowledgeSummary?.failed_count ?? 0} 个失败`,
    },
    {
      key: 'llm',
      title: '项目 LLM',
      icon: Cpu,
      summary: llmSummary?.configured ? '已配置项目 LLM' : `项目未配置，回退到${llmSummary?.source === 'personal' ? '个人配置' : '系统配置'}`,
      meta: llmSummary?.configured ? (llmSummary?.model_name || '项目模型') : (llmSummary?.model_name || `当前来源：${llmSummary?.source || 'system'}`),
    },
  ];

  return (
    <div className="flex-1 flex w-full relative">
      <div className="flex-1 overflow-y-auto bg-slate-50/70 p-6 pb-24 w-full">
        <div className="mx-auto max-w-[1320px] animate-in fade-in duration-500 flex flex-col gap-6">
          <section className="rounded-[28px] border border-slate-200 bg-gradient-to-br from-white via-white to-slate-50 px-6 py-6 shadow-sm">
            <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
              <div className="max-w-3xl">
                <div className="flex flex-wrap items-center gap-3">
                  <h1 className="text-2xl font-black tracking-tight text-slate-900">{headlineTone.title}</h1>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {overview.readiness.dimensions.map((d) => (
                    <span
                      key={d.kind}
                      className={`inline-flex rounded-full border px-3 py-1 text-xs font-bold ${
                        d.checked
                          ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                          : 'border-slate-200 bg-white text-slate-600'
                      }`}
                    >
                      {(projectionLabel[d.kind] || d.kind) + ' ' + d.score + '%'}
                    </span>
                  ))}
                </div>
              </div>

              <div className="overflow-hidden rounded-[24px] border border-slate-200 bg-white/85 xl:min-w-[420px]">
                <div className="grid grid-cols-1 divide-y divide-slate-100 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
                  {headlineStats.map((item) => (
                    <div key={item.label} className="px-5 py-4">
                      <div className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">{item.label}</div>
                      <div className={`mt-2 text-2xl font-black tracking-tight ${item.tone}`}>{item.value}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-[28px] border border-slate-200 bg-white px-6 py-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-black text-slate-900">项目配置</h2>
                <p className="mt-1 text-xs font-medium text-slate-500">管理当前项目的 AI 策略、参考资料和团队模型连接。</p>
              </div>
              <button
                type="button"
                onClick={() => ir?.projectId && navigate(`/projects/${ir.projectId}/configuration`)}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 shadow-sm transition-colors hover:bg-slate-50"
              >
                打开配置
              </button>
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              {configCards.map((card) => {
                const Icon = card.icon;
                return (
                  <button
                    key={card.key}
                    type="button"
                    onClick={() => ir?.projectId && navigate(`/projects/${ir.projectId}/configuration?tab=${card.key}`)}
                    className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-left transition-all hover:border-indigo-200 hover:bg-white hover:shadow-sm"
                  >
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4 text-indigo-600" />
                      <span className="text-sm font-black text-slate-900">{card.title}</span>
                    </div>
                    <div className="mt-3 text-sm font-bold text-slate-700">{card.summary}</div>
                    <div className="mt-1 text-xs font-medium leading-relaxed text-slate-500">{card.meta}</div>
                  </button>
                );
              })}
            </div>
          </section>

          <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
            <div className="xl:col-span-8 flex flex-col">
              <section className="flex-1 rounded-[28px] border border-slate-200 bg-white shadow-sm flex flex-col overflow-hidden h-[600px]">
                <div className="flex items-center justify-between gap-4 px-6 py-5 border-b border-slate-100 shrink-0">
                  <h2 className="text-lg font-black text-slate-900">待处理问题</h2>
                  {highRiskIssues.length > 0 && (
                    <span className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-[11px] font-bold text-rose-700">
                      高风险 {highRiskIssues.length}
                    </span>
                  )}
                </div>
                <div className="p-6 overflow-y-auto flex-1">
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    {openIssues.map(issue => (
                      <IssueCard
                        key={issue.findingId}
                        issue={issue as any}
                        onClick={() => { setSelectedObject(issue); jumpToProjection(findingProjection(issue)); }}
                        onCreateSlot={(nextIssue) => void openIssueFlow(nextIssue.findingId)}
                        onIgnore={(nextIssue) => void updateIssueAttributes(nextIssue.findingId, { status: 'ignored' })}
                      />
                    ))}
                    {openIssues.length === 0 && (
                      <div className="col-span-full flex min-h-[220px] items-center justify-center rounded-[22px] border border-dashed border-slate-200 bg-slate-50/70">
                        <p className="text-sm text-slate-400">暂无待处理问题</p>
                      </div>
                    )}
                  </div>
                </div>
              </section>
            </div>

            <div className="xl:col-span-4 flex flex-col">
              <section className="flex-1 rounded-[28px] border border-slate-200 bg-white shadow-sm flex flex-col overflow-hidden h-[600px]">
                <div className="px-6 py-5 border-b border-slate-100 shrink-0">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-lg font-black text-slate-900">当前推进状态</div>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-bold text-slate-600">
                      {decisionQueue.length + overview.openSlotsCount} 项
                    </span>
                  </div>
                </div>

                <div className="px-6 py-5 border-b border-slate-100 bg-slate-50/30 shrink-0">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-bold text-slate-900">下一步建议</div>
                  </div>

                  <div className="mt-4">
                    {stageProgress && stageProgress.stages ? (
                      progressNextAction && progressNextAction.kind !== 'none' ? (
                        <button
                          type="button"
                          disabled={isLoading}
                          onClick={handleProgressAction}
                          className="w-full rounded-2xl border border-slate-200 bg-white p-4 text-left transition-all hover:border-indigo-300 hover:shadow-md hover:-translate-y-0.5 cursor-pointer disabled:opacity-50"
                        >
                          <div className="mt-2 text-sm font-bold text-slate-900">
                            {progressNextAction.label || '继续处理当前建议'}
                          </div>
                          <div className="mt-2 max-h-[12vh] overflow-y-auto pr-1 text-xs leading-relaxed text-slate-500">
                            {activeProgressStage.statusLabel}：{activeProgressStage.failedChecks?.[0]?.message || '请前往对应页面进行处理'}
                          </div>
                        </button>
                      ) : (
                        <div className="rounded-2xl bg-white border border-slate-200 px-4 py-5 text-sm text-slate-400">
                          当前所有开发阶段均已完成！
                        </div>
                      )
                    ) : backendNextAction ? (
                      <button
                        type="button"
                        disabled={isLoading}
                        onClick={() => void startFindingSuggestion(backendNextAction, { navigate })}
                        className="w-full rounded-2xl border border-slate-200 bg-white p-4 text-left transition-all hover:border-indigo-300 hover:shadow-md hover:-translate-y-0.5 cursor-pointer disabled:opacity-50"
                      >
                        <div className="mt-2 text-sm font-bold text-slate-900">
                          {backendNextAction.title || '继续处理当前建议'}
                        </div>
                        <div className="mt-2 max-h-[12vh] overflow-y-auto pr-1 text-xs leading-relaxed text-slate-500">
                          {backendNextAction.description}
                        </div>
                      </button>
                    ) : nextSlot ? (
                      <button
                        type="button"
                        disabled={isLoading}
                        onClick={() => {
                          if (nextSlot?.kind === 'stage_gate_transition_confirm') {
                            const stage = nextSlot.stage;
                            const dummyFinding: Finding = {
                              findingId: `overview:stage_transition:${stage}`,
                              type: 'next_suggestion',
                              stage: stage as any,
                              code: stage === 'what' ? 'ENTER_HOW' : 'ENTER_SCOPE',
                              severity: 'info',
                              title: stage === 'what' ? '进入 How 阶段' : '进入 Scope 阶段',
                              description: nextSlot.description || '',
                              blockingScope: 'none',
                              metadata: {
                                action: {
                                  kind: 'stage_transition',
                                  transition_action: stage === 'what' ? 'enter_how' : 'enter_scope'
                                }
                              }
                            };
                            void startFindingSuggestion(dummyFinding, { navigate });
                          } else if (activeSuggestionEntry) {
                            const dummyFinding: Finding = {
                              findingId: `overview:navigate:${activeSuggestionEntry.stage}`,
                              type: 'next_suggestion',
                              stage: activeSuggestionEntry.stage as any,
                              code: 'NAVIGATE_TO_STAGE',
                              severity: 'info',
                              title: '前往对应阶段',
                              description: nextSlot.description || '',
                              blockingScope: 'none',
                              metadata: {
                                action: {
                                  kind: 'navigate',
                                  route: buildProjectRoute(ir?.projectId, activeSuggestionEntry.route)
                                }
                              }
                            };
                            void startFindingSuggestion(dummyFinding, { navigate });
                          }
                        }}
                        className="w-full rounded-2xl border border-slate-200 bg-white p-4 text-left transition-all hover:border-indigo-300 hover:shadow-md hover:-translate-y-0.5 cursor-pointer disabled:opacity-50"
                      >
                        <div className="mt-2 text-sm font-bold text-slate-900">
                          {nextSlot.actions.manual?.label || nextSlot.actions.ai?.label || '继续处理当前建议'}
                        </div>
                        <div className="mt-2 max-h-[12vh] overflow-y-auto pr-1 text-xs leading-relaxed text-slate-500">
                          {nextSlot.description}
                        </div>
                      </button>
                    ) : (
                      <div className="rounded-2xl bg-white border border-slate-200 px-4 py-5 text-sm text-slate-400">
                        当前没有建议。
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex-1 flex flex-col px-6 py-5 overflow-hidden">
                  <div className="flex items-center justify-between gap-3 mb-4">
                    <div className="text-sm font-bold text-slate-900">待决策方案</div>
                    <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] font-bold text-sky-700">
                      {decisionQueue.length} 组
                    </span>
                  </div>

                  <div className="flex-1 overflow-y-auto pr-1 space-y-3">
                    {decisionQueue.length === 0 && (
                      <div className="rounded-2xl bg-slate-50 px-4 py-5 text-sm text-slate-400">
                        当前没有待决策方案。
                      </div>
                    )}
                    {decisionQueue.map(item => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => {
                          openChoiceGroupPreview(item.original || item);
                        }}
                        className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left transition-all hover:border-sky-300 hover:shadow-md hover:-translate-y-0.5 cursor-pointer"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">
                            {queueKindLabel[(item as any).kind] || '待办'}
                          </span>
                          <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                            待决策
                          </span>
                        </div>
                        <div className="mt-2 text-sm font-bold text-slate-900">{item.title}</div>
                        <div className="mt-1 text-xs leading-relaxed text-slate-500 line-clamp-2">{item.description}</div>
                      </button>
                    ))}
                  </div>
                </div>
              </section>
            </div>
          </div>

          <section className="rounded-[28px] border border-slate-200 bg-white shadow-sm overflow-hidden">
             <ConfirmationWorkspace />
          </section>

          <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
            <div className="xl:col-span-6 flex flex-col">
              <section className="flex-1 rounded-[28px] border border-slate-200 bg-white shadow-sm flex flex-col overflow-hidden">
                <div className="px-6 py-5 border-b border-slate-100 shrink-0">
                  <h2 className="text-lg font-black text-slate-900">最近生成方案</h2>
                </div>
                <div className="flex-1 p-6 overflow-y-auto">
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    {recentChoices.map((c: any) => (
                      <ChoiceCard
                        key={c.id}
                        choice={c as any}
                        onAccept={(choice) => acceptChoice(choice.id)}
                        onPreview={handlePreviewChoice}
                        onRewrite={(choice) => useWorkspaceStore.getState().setSelectedObject(choice)}
                        onReject={(choice) => rejectChoice(choice.id)}
                      />
                    ))}
                    {recentChoices.length === 0 && (
                      <div className="col-span-full flex min-h-[220px] items-center justify-center rounded-[22px] border border-dashed border-slate-200 bg-slate-50/70">
                        <p className="text-sm text-slate-400">等待新的 AI 分析结果...</p>
                      </div>
                    )}
                  </div>
                </div>
              </section>
            </div>

            <div className="xl:col-span-6 flex flex-col">
              <section className="flex-1 rounded-[28px] border border-slate-200 bg-white shadow-sm flex flex-col overflow-hidden">
                <div className="px-6 py-5 border-b border-slate-100 shrink-0">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h2 className="text-lg font-black text-slate-900">最近变更记录</h2>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-bold text-slate-600">
                      {filteredAuditOperations.length}/{auditLogs.length} 条
                    </span>
                  </div>
                  {auditActionTypes.length > 1 && (
                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setSelectedAuditActionTypes([])}
                        className={`rounded-full border px-3 py-1 text-xs font-bold transition-colors ${
                          selectedAuditActionTypes.length === 0
                            ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
                            : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300'
                        }`}
                      >
                        全部
                      </button>
                      {auditActionTypes.map((actionType) => {
                        const checked = selectedAuditActionTypes.includes(actionType);
                        const actionLabel = getAuditActionTypeLabel(actionType);
                        return (
                          <label
                            key={actionType}
                            className={`inline-flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1 text-xs font-bold transition-colors ${
                              checked
                                ? 'border-sky-200 bg-sky-50 text-sky-700'
                                : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300'
                            }`}
                          >
                            <input
                              type="checkbox"
                              className="h-3 w-3 accent-sky-600"
                              checked={checked}
                              onChange={() => toggleAuditActionType(actionType)}
                            />
                            <span title={actionType}>{actionLabel}</span>
                          </label>
                        );
                      })}
                    </div>
                  )}
                </div>
                <div className="h-[540px] overflow-y-auto p-6 space-y-3">
                  {filteredAuditOperations.length === 0 && (
                    <div className="rounded-2xl bg-slate-50 px-4 py-5 text-sm text-slate-400">
                      尚无变更记录。
                    </div>
                  )}
                  {filteredAuditOperations.map((operation) => (
                    <div key={operation.id} className="min-h-[72px] rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-xs font-black text-slate-500" title={operation.actionType}>
                          {getAuditActionTypeLabel(operation.actionType)}
                        </span>
                        <span className="text-[11px] text-slate-400">{new Date(operation.timestamp).toLocaleString()}</span>
                      </div>
                      <div className="mt-2 text-sm font-semibold text-slate-900">{operation.summary || '应用变更'}</div>
                      <div className="mt-1 flex items-center justify-between gap-2 text-xs text-slate-500">
                        <span>影响 {operation.targetIds?.length || 0} 个对象</span>
                        {operation.actorType && (
                          <span className="text-slate-400">
                            操作者: <span className="font-semibold text-slate-600">{operation.actorEmail || (operation.actorType === 'system' ? '系统' : '未知')}</span>
                            {operation.actorType === 'ai' && (
                              <span className="ml-1 inline-flex items-center rounded-md bg-indigo-50 px-1.5 py-0.5 text-[10px] font-bold text-indigo-600 ring-1 ring-inset ring-indigo-500/10">
                                AI
                              </span>
                            )}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          </div>
        </div>
      </div>

      <RightObjectPanel />

      <ChoiceGroupPreviewModal
        group={activeChoiceGroup}
        isWorking={isGeneratingChoices}
        isGeneratingChoices={isGeneratingChoices}
        generationProgress={choiceGroupGenerationProgress}
        initialChoiceId={previewChoiceId}
        onAccept={async (choiceId) => {
          await acceptChoice(choiceId);
          setPreviewChoiceId(null);
        }}
        onDiscard={async () => {
          if (activeChoiceGroup) {
            const gId = typeof activeChoiceGroup.id === 'string' ? parseInt(activeChoiceGroup.id, 10) : activeChoiceGroup.id;
            await discardChoiceGroup(gId);
          }
          setPreviewChoiceId(null);
        }}
        onDefer={handleDeferChoiceGroupPreview}
      />

      <StaleChoiceDialog
        isOpen={!!activeStaleChoice}
        staleReason={activeStaleChoice?.staleReason || ''}
        onForceAccept={async () => {
          if (!activeStaleChoice) return;
          await acceptChoice(String(activeStaleChoice.choiceId), true);
          clearStaleChoice();
        }}
        onRegenerate={async () => {
          if (!activeStaleChoice) return;
          await regenerateChoiceGroup(activeStaleChoice.choiceId);
          clearStaleChoice();
        }}
        onCancel={clearStaleChoice}
      />
    </div>
  );
}
