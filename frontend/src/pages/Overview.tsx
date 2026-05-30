import { IssueCard } from '@/components/shared/IssueCard';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { ChoiceCard } from '@/components/shared/ChoiceCard';
import { ChoiceGroupPreviewModal } from '@/components/shared/ChoiceGroupPreviewModal';
import { StaleChoiceDialog } from '@/components/shared/StaleChoiceDialog';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { useNavigate } from 'react-router-dom';
import { useState, useCallback } from 'react';
import { workspaceApi } from '@/lib/api';
import { buildOverviewModel, buildPageHealth, buildProjectRoute, projectionPath } from '@/core/selectors';
import {
  useWorkspaceStore,
  selectChoices
} from '@/store/useWorkspaceStore';
import { RefreshCw } from 'lucide-react';
import { NodeKindToRoute, NodeKindToText } from '@/core/schema';

export function Overview() {
  const {
    setSelectedObject,
    acceptChoice,
    rejectChoice,
    createSlotFromIssue,
    expandSlot,
    updateIssueAttributes,
    refreshWorkspace,
    // Phase 5b: Choice group
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
  const recentChoices = overview.recentChoices.length ? overview.recentChoices : choices.filter(c => c.status === 'candidate').slice(0, 3);
  const stageHealths = [
    { stage: 'what', label: 'What', route: '/what' as const, health: buildPageHealth(ir, '/what') },
    { stage: 'how', label: 'How', route: '/flow' as const, health: buildPageHealth(ir, '/flow') },
    { stage: 'scope', label: 'Scope', route: '/scope' as const, health: buildPageHealth(ir, '/scope') },
  ];
  const activeStageHealth = stageHealths.find((item) => !item.health.disabled);
  const activeSuggestionEntry = stageHealths.find((item) => item.health.nextSlot);
  const nextSlot = activeSuggestionEntry?.health.nextSlot;

  // 账本批量选择状态
  const [selectedLedgerIds, setSelectedLedgerIds] = useState<Set<string>>(new Set());
  const [previewChoiceId, setPreviewChoiceId] = useState<string | number | null>(null);

  const toggleLedgerItem = useCallback((id: string) => {
    setSelectedLedgerIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const toggleSelectAllLedger = useCallback(() => {
    if (selectedLedgerIds.size === overview.aiAssumptionLedger.length) {
      setSelectedLedgerIds(new Set());
    } else {
      setSelectedLedgerIds(new Set(overview.aiAssumptionLedger.map((i: any) => i.id)));
    }
  }, [overview.aiAssumptionLedger, selectedLedgerIds]);

  const batchUpdateLedgerStatus = useCallback(async (status: string) => {
    if (!ir?.projectId || selectedLedgerIds.size === 0) return;
    const nodes = overview.aiAssumptionLedger
      .filter((item: any) => selectedLedgerIds.has(item.id))
      .map((item: any) => ({ node_kind: item.kind, node_id: item.nodeId }));
    try {
      await workspaceApi.batchUpdateNodeConfirmationStatus(ir.projectId, nodes, status);
      setSelectedLedgerIds(new Set());
      await refreshWorkspace();
    } catch (err) {
      console.error('Batch update failed:', err);
    }
  }, [ir?.projectId, overview.aiAssumptionLedger, selectedLedgerIds, refreshWorkspace]);

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
    deferOnboardingChoiceGroup();
  }, [deferOnboardingChoiceGroup]);

  const openIssueFlow = async (issueId: string) => {
    const slotId = await createSlotFromIssue(issueId);
    if (slotId) {
      await expandSlot(slotId);
    }
  };

  const readinessItems = overview.readiness.dimensions.map((d) => ({
    label: `${d.title} ${d.score}%`,
    checked: d.checked,
    type: d.checked ? undefined : ('blocking' as 'blocking'),
  }));

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

  const headlineTone =
    overview.openSlotsCount > 0
      ? {
          title: '当前存在阻塞卡点',
          badgeClass: 'border-amber-200 bg-amber-50 text-amber-700',
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

  return (
    <div className="flex-1 flex w-full relative">
      <div className="flex-1 overflow-y-auto bg-slate-50/70 p-6 pb-24 w-full">
        <div className="mx-auto max-w-[1320px] animate-in fade-in duration-500">
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

          <section className="mt-5 overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm">
            <div className="grid grid-cols-12">
              <div className="col-span-12 border-b border-slate-200 xl:col-span-8 xl:border-b-0 xl:border-r">
                <div className="flex items-start justify-between gap-4 px-6 py-5">
                  <h2 className="text-lg font-black text-slate-900">待处理问题</h2>
                  {highRiskIssues.length > 0 && (
                    <span className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-[11px] font-bold text-rose-700">
                      高风险 {highRiskIssues.length}
                    </span>
                  )}
                </div>
                <div className="px-6 pb-6">
                  <div className="grid max-h-[68vh] grid-cols-1 gap-4 overflow-y-auto pr-1 md:grid-cols-2">
                    {openIssues.map(issue => (
                      <IssueCard
                        key={issue.id}
                        issue={issue as any}
                        onClick={() => { setSelectedObject(issue as any); jumpToProjection((issue as any).suggestedProjection); }}
                        onCreateSlot={(nextIssue) => void openIssueFlow(nextIssue.id)}
                        onIgnore={(nextIssue) => void updateIssueAttributes(nextIssue.id, { status: 'ignored' })}
                      />
                    ))}
                    {openIssues.length === 0 && (
                      <div className="col-span-full flex min-h-[220px] items-center justify-center rounded-[22px] border border-dashed border-slate-200 bg-slate-50/70">
                        <p className="text-sm text-slate-400">暂无待处理问题</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="col-span-12 xl:col-span-4">
                <div className="flex h-full max-h-[68vh] flex-col overflow-hidden">
                <div className="px-6 py-5">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-lg font-black text-slate-900">当前推进状态</div>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-bold text-slate-600">
                      {decisionQueue.length + overview.openSlotsCount} 项
                    </span>
                  </div>
                </div>

                <div className="border-t border-slate-100 px-6 py-5">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-bold text-slate-900">下一步建议</div>
                  </div>

                  <div className="mt-4">
                    {nextSlot ? (
                      <button
                        type="button"
                        onClick={() => {
                          if (activeSuggestionEntry) {
                            navigate(buildProjectRoute(ir?.projectId, activeSuggestionEntry.route));
                          }
                        }}
                        className="w-full rounded-2xl border border-slate-200 bg-slate-50/80 p-4 text-left transition-colors hover:border-indigo-300 hover:bg-indigo-50/40"
                      >
                        <div className="mt-3 text-sm font-bold text-slate-900">
                          {nextSlot.actions.manual?.label || nextSlot.actions.ai?.label || '继续处理当前建议'}
                        </div>
                        <div className="mt-2 max-h-[18vh] overflow-y-auto pr-1 text-xs leading-relaxed text-slate-500">
                          {nextSlot.description}
                        </div>
                      </button>
                    ) : (
                      <div className="rounded-2xl bg-slate-50 px-4 py-5 text-sm text-slate-400">
                        当前没有建议。
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex min-h-0 flex-1 flex-col border-t border-slate-100 px-6 py-5">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-bold text-slate-900">待决策方案</div>
                    <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] font-bold text-sky-700">
                      {decisionQueue.length} 组
                    </span>
                  </div>

                  <div className="mt-4 min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
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
                        className="w-full rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-left transition-colors hover:border-sky-300 hover:bg-sky-50/60"
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
                </div>
              </div>
            </div>

            <div className="grid grid-cols-12 border-t border-slate-200">
              <div className="col-span-12 border-b border-slate-200 xl:col-span-4 xl:border-b-0 xl:border-r">
                <div className="px-6 py-5">
                  <h2 className="text-lg font-black text-slate-900">结构覆盖检查</h2>
                </div>
                <div className="space-y-3 px-6 pb-6">
                  {readinessItems.map((item) => (
                    <div
                      key={item.label}
                      className={`rounded-2xl border px-4 py-3 ${
                        item.checked ? 'border-emerald-100 bg-emerald-50/60' : 'border-slate-200 bg-slate-50/70'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className={`text-sm font-semibold ${item.checked ? 'text-emerald-800' : 'text-slate-800'}`}>
                          {item.label}
                        </div>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          item.checked ? 'bg-white text-emerald-700' : 'bg-white text-slate-500'
                        }`}>
                          {item.checked ? '已达标' : '待补齐'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="col-span-12 xl:col-span-8">
                <div className="flex flex-col gap-4 border-b border-slate-100 px-6 py-5 md:flex-row md:items-end md:justify-between">
                  <div>
                    <h2 className="text-lg font-black text-slate-900">
                      AI 推测待确认
                      {overview.aiAssumptionLedger.length > 0 && (
                        <span className="ml-2 text-sm font-bold text-slate-400">{overview.aiAssumptionLedger.length}</span>
                      )}
                    </h2>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {overview.aiAssumptionLedger.length > 0 && (
                      <button
                        type="button"
                        onClick={toggleSelectAllLedger}
                        className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-600 transition-colors hover:bg-slate-50"
                      >
                        {selectedLedgerIds.size === overview.aiAssumptionLedger.length ? '取消全选' : '全选'}
                      </button>
                    )}
                    {selectedLedgerIds.size > 0 && (
                      <>
                        <button
                          type="button"
                          onClick={() => batchUpdateLedgerStatus('confirmed')}
                          className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-700 transition-colors hover:bg-emerald-100"
                        >
                          全部确认 ({selectedLedgerIds.size})
                        </button>
                        <button
                          type="button"
                          onClick={() => batchUpdateLedgerStatus('needs_confirmation')}
                          className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-bold text-amber-700 transition-colors hover:bg-amber-100"
                        >
                          标记待确认 ({selectedLedgerIds.size})
                        </button>
                      </>
                    )}
                  </div>
                </div>

                <div className="px-6 py-5">
                  <div className="max-h-[58vh] min-h-[32vh] space-y-2 overflow-y-auto pr-1 scrollbar-thin">
                    {overview.aiAssumptionLedger.length === 0 && (
                      <div className="flex min-h-[220px] items-center justify-center rounded-[22px] border border-dashed border-slate-200 bg-slate-50/70">
                        <p className="text-sm text-slate-400">
                          {(ir?.actors?.length || ir?.features?.length || ir?.businessObjects?.length || ir?.flows?.length)
                            ? '所有节点已确认，暂无待确认条目'
                            : '当前没有 AI 推测节点'}
                        </p>
                      </div>
                    )}
                    {overview.aiAssumptionLedger.map((item: any) => {
                      const routeFn = NodeKindToRoute[item.kind];
                      const isSelected = selectedLedgerIds.has(item.id);
                      return (
                        <div
                          key={item.id}
                          className={`rounded-2xl border transition-colors ${
                            isSelected ? 'border-indigo-300 bg-indigo-50/50' : 'border-slate-200 bg-slate-50/70 hover:border-indigo-300'
                          }`}
                        >
                          <button
                            type="button"
                            onClick={(e) => {
                              if (e.shiftKey || e.ctrlKey || e.metaKey) {
                                toggleLedgerItem(item.id);
                                return;
                              }
                              if (routeFn && ir?.projectId) {
                                navigate(`${routeFn(ir.projectId)}?highlight=${item.kind}-${item.nodeId}`);
                              }
                            }}
                            onContextMenu={(e) => { e.preventDefault(); toggleLedgerItem(item.id); }}
                            className="w-full px-4 py-3 text-left"
                          >
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                              <div className="flex min-w-0 items-start gap-3">
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={() => toggleLedgerItem(item.id)}
                                  onClick={(e) => e.stopPropagation()}
                                  className="mt-1 h-3.5 w-3.5 shrink-0 cursor-pointer rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                                />
                                <div className="min-w-0">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <StatusBadge status={item.status || 'ai_assumption'} />
                                    <span className="text-[11px] font-medium text-slate-400">
                                      {NodeKindToText[item.kind as keyof typeof NodeKindToText] || item.kind}
                                    </span>
                                  </div>
                                  <div className="mt-2 text-sm font-bold text-slate-900">{item.title}</div>
                                  <div className="mt-1 text-xs leading-relaxed text-slate-500 line-clamp-2">{item.source}</div>
                                </div>
                              </div>
                              <div className="text-[11px] font-medium text-slate-400">点击定位</div>
                            </div>
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-12 border-t border-slate-200">
              <div className="col-span-12 border-b border-slate-200 xl:col-span-6 xl:border-b-0 xl:border-r">
                <div className="px-6 py-5">
                  <h2 className="text-lg font-black text-slate-900">最近生成方案</h2>
                </div>
                <div className="px-6 pb-6">
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    {recentChoices.map(c => (
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

              </div>

              <div className="col-span-12 xl:col-span-6">
                <div className="px-6 py-5">
                  <h2 className="text-lg font-black text-slate-900">最近变更记录</h2>
                </div>
                <div className="space-y-2 px-6 pb-6">
                  {overview.recentAuditOperations.length === 0 && (
                    <div className="rounded-2xl bg-slate-50 px-4 py-5 text-sm text-slate-400">
                      尚无变更记录。
                    </div>
                  )}
                  {overview.recentAuditOperations.map((operation) => (
                    <div key={operation.id} className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">
                          {operation.actionType}
                        </span>
                        <span className="text-[11px] text-slate-400">{new Date(operation.timestamp).toLocaleString()}</span>
                      </div>
                      <div className="mt-2 text-sm font-semibold text-slate-900">{operation.summary || '应用变更'}</div>
                      <div className="mt-1 text-xs text-slate-500">影响 {operation.targetIds?.length || 0} 个对象</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>

      <RightObjectPanel />

      {/* Phase 5b: Choice group preview modal */}
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

      {/* Phase 5b: Stale choice dialog (UX-5) */}
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
