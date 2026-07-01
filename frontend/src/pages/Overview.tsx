import { IssueCard } from '@/components/shared/IssueCard';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { ChoiceCard } from '@/components/shared/ChoiceCard';
import { ChoiceGroupPreviewModal } from '@/components/shared/ChoiceGroupPreviewModal';
import { StaleChoiceDialog } from '@/components/shared/StaleChoiceDialog';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { useNavigate } from 'react-router-dom';
import { ConfirmationWorkspace } from '@/components/collaboration/ConfirmationWorkspace';
import { useState, useCallback, useMemo } from 'react';
import { buildOverviewModel, buildPageHealth, buildProjectRoute, projectionPath } from '@/core/selectors';
import {
  useWorkspaceStore,
  selectChoices
} from '@/store/useWorkspaceStore';
import { RefreshCw } from 'lucide-react';
import { NodeKindToRoute, NodeKindToText } from '@/core/schema';
import { findingProjection } from '@/core/findingPresentation';

const auditActionTypeLabels: Record<string, string> = {
  update_confirmation_status: '更新确认状态',
  batch_update_confirmation_status: '批量更新确认状态',
  update_user_requirements: '更新用户需求',
  refine_user_requirements: 'AI 精炼用户需求',
  create_actor: '新增参与者',
  update_actor: '更新参与者',
  delete_actor: '删除参与者',
  create_feature: '新增功能',
  update_feature: '更新功能',
  delete_feature: '删除功能',
  create_scenario: '新增场景',
  update_scenario: '更新场景',
  delete_scenario: '删除场景',
  create_acceptance_criterion: '新增验收标准',
  update_acceptance_criterion: '更新验收标准',
  delete_acceptance_criterion: '删除验收标准',
  update_scope: '更新范围决策',
  skip_kano: '跳过 Kano 分析',
  create_business_object: '新增业务对象',
  update_business_object: '更新业务对象',
  delete_business_object: '删除业务对象',
  create_business_object_attribute: '新增对象属性',
  update_business_object_attribute: '更新对象属性',
  delete_business_object_attribute: '删除对象属性',
  create_flow: '新增业务流',
  update_flow: '更新业务流',
  delete_flow: '删除业务流',
  create_flow_step: '新增流程步骤',
  update_flow_step: '更新流程步骤',
  delete_flow_step: '删除流程步骤',
  create_choice_group: '生成方案组',
  accept_choice: '采纳方案',
  reject_choice: '拒绝方案',
  discard_choice_group: '丢弃方案组',
  regenerate_choice_group: '重新生成方案组',
  create_task: '创建任务',
  task_created: '创建任务',
  approve_task: '审批通过',
  task_approved: '审批通过',
  reject_task: '审批驳回',
  task_rejected: '审批驳回',
  task_superseded: '任务已冲销',
  create_confirmation_task: '创建确认任务',
  update_confirmation_task: '更新确认任务',
  complete_confirmation_task: '完成确认任务',
  supersede_confirmation_task: '替换确认任务',
  unlock_stage_gate: '解锁阶段门',
  commit_shadow_draft: '提交影子草稿',
  discard_shadow_draft: '丢弃影子草稿',
  regenerate_shadow_draft: '重新生成影子草稿',
  member_added: '成员加入',
  member_removed: '成员移除',
  member_role_updated: '成员角色更新',
  member_invitation_accepted: '成员邀请接受',
  member_invitation_declined: '成员邀请拒绝',
  member_invitation_revoked: '成员邀请撤销',
};

const getAuditActionTypeLabel = (actionType: string) => auditActionTypeLabels[actionType] || actionType;

export function Overview() {
  const {
    setSelectedObject,
    acceptChoice,
    rejectChoice,
    executeFindingIssueResolution,
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
                    {nextSlot ? (
                      <button
                        type="button"
                        onClick={() => {
                          if (activeSuggestionEntry) {
                            navigate(buildProjectRoute(ir?.projectId, activeSuggestionEntry.route));
                          }
                        }}
                        className="w-full rounded-2xl border border-slate-200 bg-white p-4 text-left transition-all hover:border-indigo-300 hover:shadow-md hover:-translate-y-0.5 cursor-pointer"
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
