import { IssueCard } from '@/components/shared/IssueCard';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { ChoiceCard } from '@/components/shared/ChoiceCard';
import { ChoiceGroupPreviewModal } from '@/components/shared/ChoiceGroupPreviewModal';
import { StaleChoiceDialog } from '@/components/shared/StaleChoiceDialog';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { useNavigate } from 'react-router-dom';
import { ConfirmationWorkspace } from '@/components/collaboration/ConfirmationWorkspace';
import { useState, useCallback, useEffect, useMemo } from 'react';
import { buildOverviewModel, buildProjectRoute, projectionPath } from '@/core/selectors';
import {
  useWorkspaceStore,
  selectChoices
} from '@/store/useWorkspaceStore';
import { Cpu, Database, RefreshCw, Sliders } from 'lucide-react';
import { NodeKindToRoute } from '@/core/schema';
import { findingProjection } from '@/core/findingPresentation';
import { getAuditActionTypeLabel, getAuditSummary } from '@/core/auditActionLabels';
import { useTranslation } from 'react-i18next';
import { getFindingText } from '@/core/findingText';
import { workspaceApi } from '@/lib/api';

export function Overview() {
  const { t, i18n } = useTranslation();
  const {
    setSelectedObject,
    acceptChoice,
    rejectChoice,
    executeFindingIssueResolution,
    expandSlot,
    updateIssueAttributes,
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
  const stageProgress = useWorkspaceStore((s) => s.stageProgress);
  const backendFindingsLoaded = useWorkspaceStore((s) => s.backendFindingsLoaded);
  const [hasGeneratedPrototype, setHasGeneratedPrototype] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!ir?.projectId) {
      setHasGeneratedPrototype(false);
      return;
    }

    void workspaceApi.getLatestPrototypePreview(ir.projectId)
      .then((preview) => {
        if (!cancelled) setHasGeneratedPrototype(Boolean(preview?.prototypeId));
      })
      .catch(() => {
        if (!cancelled) setHasGeneratedPrototype(false);
      });

    return () => {
      cancelled = true;
    };
  }, [ir?.projectId]);

  const baseOverview = buildOverviewModel(ir, auditLogs, stageProgress);
  const readinessDimensions = baseOverview.readiness.dimensions.map((dimension) => (
    dimension.kind === 'ui'
      ? { ...dimension, score: hasGeneratedPrototype ? 100 : 0, checked: hasGeneratedPrototype }
      : dimension
  ));
  const overview = {
    ...baseOverview,
    readiness: {
      ...baseOverview.readiness,
      dimensions: readinessDimensions,
      overallScore: Math.floor(readinessDimensions.reduce((sum, dimension) => sum + dimension.score, 0) / readinessDimensions.length),
    },
  };
  const openIssues = overview.openIssues;
  const highRiskIssues = overview.highRiskIssues;
  const decisionQueue = overview.decisionQueue;
  const recentChoices = overview.recentChoices.length ? overview.recentChoices : choices.filter((c: any) => c.status === 'candidate').slice(0, 3);
  const findingsByView = useWorkspaceStore((s) => s.findingsByView);
  const isLoading = useWorkspaceStore((s) => s.isLoading);
  const backendNextAction = (findingsByView?.next_action || []).find((f) => !!f);
  const projectConfiguration = useWorkspaceStore((s) => s.projectConfiguration);
  const fetchProjectConfiguration = useWorkspaceStore((s) => s.fetchProjectConfiguration);

  useEffect(() => {
    if (ir?.projectId && typeof fetchProjectConfiguration === 'function') {
      void fetchProjectConfiguration(ir.projectId);
    }
  }, [ir?.projectId, fetchProjectConfiguration]);

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
    goal: t('overview.projections.goal'),
    role: t('overview.projections.role'),
    system: t('overview.projections.system'),
    data: t('overview.projections.data'),
    ui: t('overview.projections.ui'),
  };

  const queueKindLabel: Record<string, string> = {
    choiceGroup: t('overview.queueKind.choiceGroup'),
  };

  const projectStatusCode = ir?.statusCode || 'in_progress';
  const headlineTone = projectStatusCode === 'converged'
    ? {
        title: t('overview.headlines.converged'),
        badgeClass: 'border-emerald-200 bg-emerald-50 text-emerald-700',
      }
    : projectStatusCode === 'not_started'
      ? {
          title: t('overview.headlines.notStarted'),
          badgeClass: 'border-slate-200 bg-slate-50 text-slate-700',
        }
      : projectStatusCode === 'needs_attention' || projectStatusCode === 'has_issues'
        ? {
            title: t('overview.headlines.hasIssues'),
            badgeClass: 'border-rose-200 bg-rose-50 text-rose-700',
          }
        : {
            title: t('overview.headlines.inProgress'),
            badgeClass: 'border-sky-200 bg-sky-50 text-sky-700',
          };

  const headlineStats = [
    {
      label: t('overview.stats.coverage'),
      value: `${overview.readiness.overallScore}%`,
      tone: 'text-indigo-700',
    },
    {
      label: t('overview.stats.pendingIssues'),
      value: String(openIssues.length).padStart(2, '0'),
      tone: 'text-rose-600',
    },
    {
      label: t('overview.stats.pendingChoices'),
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
      title: t('overview.config.aiStrategies'),
      icon: Sliders,
      summary: generationStrategy?.source === 'project' ? t('overview.config.projectCustomStrategy') : t('overview.config.systemDefaultStrategy'),
      meta: t('overview.config.strategiesMeta', { count: generationStrategy?.candidate_count ?? 2, strategyCount: (generationStrategy?.strategies || []).filter((s: any) => s.enabled).length || 2 }),
    },
    {
      key: 'knowledge',
      title: t('overview.config.knowledgeBase'),
      icon: Database,
      summary: t('overview.config.documentCount', { count: knowledgeSummary?.document_count ?? 0 }),
      meta: t('overview.config.knowledgeMeta', { ready: knowledgeSummary?.ai_enabled_count ?? 0, processing: knowledgeSummary?.processing_count ?? 0, failed: knowledgeSummary?.failed_count ?? 0 }),
    },
    {
      key: 'llm',
      title: t('overview.config.projectLLM'),
      icon: Cpu,
      summary: llmSummary?.configured ? t('overview.config.llmConfigured') : t('overview.config.llmFallback', { source: llmSummary?.source === 'personal' ? t('overview.config.personalConfig') : t('overview.config.systemConfig') }),
      meta: llmSummary?.configured ? (llmSummary?.model_name || 'Project Model') : (llmSummary?.model_name || t('overview.config.currentSource', { source: llmSummary?.source || 'system' })),
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
                <h2 className="text-lg font-black text-slate-900">{t('overview.sections.configTitle')}</h2>
                <p className="mt-1 text-xs font-medium text-slate-500">{t('overview.sections.configSubtitle')}</p>
              </div>
              <button
                type="button"
                onClick={() => ir?.projectId && navigate(`/projects/${ir.projectId}/configuration`)}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 shadow-sm transition-colors hover:bg-slate-50"
              >
                {t('overview.sections.configBtn')}
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
              <section className="h-[760px] shrink-0 rounded-[28px] border border-slate-200 bg-white shadow-sm flex flex-col overflow-hidden">
                <div className="flex items-center justify-between gap-4 px-6 py-5 border-b border-slate-100 shrink-0">
                  <h2 className="text-lg font-black text-slate-900">{t('overview.sections.issuesTitle')}</h2>
                  {highRiskIssues.length > 0 && (
                    <span className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-[11px] font-bold text-rose-700">
                      {t('overview.sections.highRisk', { count: highRiskIssues.length })}
                    </span>
                  )}
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto p-6">
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
                        <p className="text-sm text-slate-400">{t('overview.sections.noIssues')}</p>
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
                    <div className="text-lg font-black text-slate-900">{t('overview.sections.statusTitle')}</div>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-bold text-slate-600">
                      {t('overview.sections.itemsCount', { count: decisionQueue.length + overview.openSlotsCount })}
                    </span>
                  </div>
                </div>

                <div className="px-6 py-5 border-b border-slate-100 bg-slate-50/30 shrink-0">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-bold text-slate-900">{t('overview.sections.nextSuggestionTitle')}</div>
                  </div>

                  <div className="mt-4">
                    {backendFindingsLoaded && backendNextAction ? (
                      <button
                        type="button"
                        disabled={isLoading}
                        onClick={() => void startFindingSuggestion(backendNextAction, { navigate })}
                        className="w-full rounded-2xl border border-slate-200 bg-white p-4 text-left transition-all hover:border-indigo-300 hover:shadow-md hover:-translate-y-0.5 cursor-pointer disabled:opacity-50"
                      >
                        <div className="mt-2 text-sm font-bold text-slate-900">
              {getFindingText(backendNextAction, t).title || t('overview.sections.continueSuggestion')}
                        </div>
                        <div className="mt-2 max-h-[12vh] overflow-y-auto pr-1 text-xs leading-relaxed text-slate-500">
              {getFindingText(backendNextAction, t).description}
                        </div>
                      </button>
                    ) : null}
                  </div>
                </div>

                <div className="flex-1 flex flex-col px-6 py-5 overflow-hidden">
                  <div className="flex items-center justify-between gap-3 mb-4">
                    <div className="text-sm font-bold text-slate-900">{t('overview.sections.pendingChoicesTitle')}</div>
                    <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] font-bold text-sky-700">
                      {t('overview.sections.groupsCount', { count: decisionQueue.length })}
                    </span>
                  </div>

                  <div className="flex-1 overflow-y-auto pr-1 space-y-3">
                    {decisionQueue.length === 0 && (
                      <div className="rounded-2xl bg-slate-50 px-4 py-5 text-sm text-slate-400">
                        {t('overview.sections.noPendingChoices')}
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
                            {queueKindLabel[(item as any).kind] || t('overview.queueKind.unknown')}
                          </span>
                          <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                            {t('overview.sections.pendingChoiceBadge')}
                          </span>
                        </div>
                        <div className="mt-2 text-sm font-bold text-slate-900">
                          {t(item.titleKey, {
                            ...item.titleParams,
                            type: item.titleParams?.typeKey ? t(String(item.titleParams.typeKey)) : undefined,
                          })}
                        </div>
                        <div className="mt-1 text-xs leading-relaxed text-slate-500 line-clamp-2">
                          {t(item.descriptionKey || 'overview.decisionQueue.description', {
                            ...item.descriptionParams,
                            type: item.descriptionParams?.typeKey ? t(String(item.descriptionParams.typeKey)) : undefined,
                          })}
                        </div>
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
                  <h2 className="text-lg font-black text-slate-900">{t('overview.sections.recentChoicesTitle')}</h2>
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
                        <p className="text-sm text-slate-400">{t('overview.sections.waitingAI')}</p>
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
                    <h2 className="text-lg font-black text-slate-900">{t('overview.sections.recentAuditsTitle')}</h2>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-bold text-slate-600">
                      {t('overview.sections.auditsCount', { count: filteredAuditOperations.length, total: auditLogs.length })}
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
                        {t('overview.sections.allAudits')}
                      </button>
                      {auditActionTypes.map((actionType) => {
                        const checked = selectedAuditActionTypes.includes(actionType);
                        const actionLabel = getAuditActionTypeLabel(actionType, i18n.language);
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
                      {t('overview.sections.noAudits')}
                    </div>
                  )}
                  {filteredAuditOperations.map((operation) => (
                    <div key={operation.id} className="min-h-[72px] rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-xs font-black text-slate-500" title={operation.actionType}>
                          {getAuditActionTypeLabel(operation.actionType, i18n.language)}
                        </span>
                          <span className="text-[11px] text-slate-400">{new Date(operation.timestamp).toLocaleString(i18n.language)}</span>
                      </div>
                      <div className="mt-2 text-sm font-semibold text-slate-900">{getAuditSummary(operation, i18n.language)}</div>
                      <div className="mt-1 flex items-center justify-between gap-2 text-xs text-slate-500">
                        <span>{t('overview.sections.auditsAffected', { count: operation.targetIds?.length || 0 })}</span>
                        {operation.actorType && (
                          <span className="text-slate-400">
                            {t('overview.sections.auditsActorLabel')}
                            <span className="font-semibold text-slate-600">
                              {operation.actorEmail || (operation.actorType === 'system' ? t('overview.sections.system') : t('overview.sections.unknown'))}
                            </span>
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
