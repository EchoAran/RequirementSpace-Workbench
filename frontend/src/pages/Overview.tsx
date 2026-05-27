import { IssueCard } from '@/components/shared/IssueCard';
import { ReadinessChecklist } from '@/components/shared/ReadinessChecklist';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { ChoiceCard } from '@/components/shared/ChoiceCard';
import { useNavigate } from 'react-router-dom';
import { buildOverviewModel, projectionPath } from '@/core/selectors';
import { 
  useWorkspaceStore, 
  selectChoices 
} from '@/store/useWorkspaceStore';
import { NodeKindToText } from '@/core/schema';

export function Overview() {
  const { 
    setSelectedObject,
    acceptChoice,
    rejectChoice,
    createSlotFromIssue,
    expandSlot,
    updateIssueAttributes,
  } = useWorkspaceStore();
  const navigate = useNavigate();
  
  const choices = useWorkspaceStore(selectChoices);
  const ir = useWorkspaceStore(state => state.ir);
  const auditLogs = useWorkspaceStore(state => state.auditLogs);

  const overview = buildOverviewModel(ir, auditLogs);
  const highRiskIssues = overview.highRiskIssues;
  const decisionQueue = overview.decisionQueue;
  const recentChoices = overview.recentChoices.length ? overview.recentChoices : choices.filter(c => c.status === 'candidate').slice(0, 3);

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
    return navigate(projectionPath(projection));
  };

  const projectionLabel: Record<string, string> = {
    goal: '目标',
    role: '角色',
    system: '流程',
    data: '数据',
    ui: '界面',
  };

  const queueKindLabel: Record<string, string> = {
    issue: 'Issue',
    slot: '槽位',
    choiceGroup: 'ChoiceGroup',
    proposal: '提案',
  };

  return (
    <div className="flex-1 flex w-full relative">
      <div className="flex-1 p-6 pb-24 overflow-y-auto w-full">
        <div className="max-w-[1240px] mx-auto animate-in fade-in duration-500">
          
          <div className="grid grid-cols-12 gap-4 h-full content-start">
            
            {/* Summary Card */}
            <div className="col-span-12 bg-white rounded-2xl border border-slate-200 p-4 flex items-center justify-between shadow-sm">
              <div className="flex items-center gap-6">
                <div>
                  <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">整体成熟度</p>
                  <p className="text-xl font-bold text-indigo-600 font-mono">
                    {overview.readiness.overallScore}%
                  </p>
                </div>
                <div className="h-10 w-[1px] bg-slate-100"></div>
                <div className="flex gap-4">
                  <div className="flex flex-col">
                    <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1 mt-1">阻塞 Issue</p>
                    <span className="text-rose-600 text-lg font-bold font-mono">{String(highRiskIssues.length).padStart(2, '0')}</span>
                  </div>
                  <div className="flex flex-col">
                    <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1 mt-1">待处理 Slot</p>
                    <span className="text-amber-600 text-lg font-bold font-mono">{String(overview.openSlotsCount).padStart(2, '0')}</span>
                  </div>
                  <div className="flex flex-col">
                    <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1 mt-1">开放 ChoiceGroup</p>
                    <span className="text-blue-600 text-lg font-bold font-mono">{String(overview.openChoiceGroupsCount).padStart(2, '0')}</span>
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                {overview.readiness.dimensions.map((d) => (
                  <span key={d.kind} className="px-2.5 py-1 bg-slate-50 text-slate-700 text-xs font-bold rounded-full border border-slate-200">
                    {(projectionLabel[d.kind] || d.kind) + ' ' + d.score + '%'}
                  </span>
                ))}
              </div>
            </div>

            {/* Left Column: Decision Queue */}
            <div className="col-span-4 space-y-3">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1">方案决策队列</h3>
              
              <div className="space-y-3">
                {decisionQueue.length === 0 && <p className="text-xs text-slate-400 italic">当前没有待确认或假设项。</p>}
                {decisionQueue.map(item => (
                  <div 
                    key={item.id} 
                    onClick={() => { 
                      const obj = item.original || item;
                      setSelectedObject(obj);
                      if ((item as any).kind === 'issue' && (obj as any).suggestedProjection) {
                        jumpToProjection((obj as any).suggestedProjection);
                      } else if ((item as any).kind === 'slot' && (obj as any).ownerProjection) {
                        jumpToProjection((obj as any).ownerProjection);
                      } else if ((item as any).kind === 'proposal') {
                        const projection = ((obj as any).scope?.projection as any) || 'goal';
                        jumpToProjection(projection);
                      }
                    }}
                    className="cursor-pointer bg-white p-4 rounded-xl border border-slate-200 shadow-sm hover:border-indigo-300 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] px-2 py-0.5 bg-slate-100 text-slate-500 rounded uppercase font-bold tracking-wider">{queueKindLabel[(item as any).kind] || '待办'}</span>
                      <span className={`px-1.5 py-0.5 text-[10px] font-black rounded bg-amber-50 text-amber-600`}>
                        待决策
                      </span>
                    </div>
                    <h4 className="font-bold text-slate-800 text-sm mb-1">{item.title}</h4>
                    <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">{item.description}</p>
                  </div>
                ))}
              </div>

              <div className="mt-6 pt-4 border-t border-slate-200 border-dashed">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1 mb-3">多维闭环诊断</h3>
                <ReadinessChecklist title="维度覆盖率" items={readinessItems} />
              </div>

              <div className="mt-6 pt-4 border-t border-slate-200 border-dashed">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1 mb-3">最近 Audit</h3>
                <div className="space-y-2">
                  {overview.recentAuditOperations.length === 0 && (
                    <p className="text-xs text-slate-400 italic">尚无审计记录。</p>
                  )}
                  {overview.recentAuditOperations.map((operation) => (
                    <div key={operation.id} className="rounded-xl border border-slate-200 bg-white p-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          {operation.actionType}
                        </span>
                        <span className="text-[10px] text-slate-400">{new Date(operation.timestamp).toLocaleString()}</span>
                      </div>
                      <div className="mt-1 text-sm font-medium text-slate-800">{operation.summary || '应用变更'}</div>
                      <div className="mt-1 text-xs text-slate-500">影响 {operation.targetIds?.length || 0} 个对象</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Middle Column: High Risk Issues & Recent Choices */}
            <div className="col-span-5 flex flex-col gap-4">
              <div className="space-y-3">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1">高优先级 Issue</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {highRiskIssues.map(issue => (
                    <IssueCard
                      key={issue.id}
                      issue={issue as any}
                      onClick={() => { setSelectedObject(issue as any); jumpToProjection((issue as any).suggestedProjection); }}
                      onCreateSlot={(nextIssue) => void openIssueFlow(nextIssue.id)}
                      onIgnore={(nextIssue) => void updateIssueAttributes(nextIssue.id, { status: 'ignored' })}
                    />
                  ))}
                  {highRiskIssues.length === 0 && (
                    <div className="bg-white rounded-2xl p-4 border border-slate-200 border-dashed flex items-center justify-center col-span-2">
                      <p className="text-xs text-slate-400 py-6 italic">暂无高风险 Issue</p>
                    </div>
                  )}
                </div>
              </div>

              <div className="pt-2 space-y-3">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1 italic">最近 Choice</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {recentChoices.map(c => (
                    <ChoiceCard
                      key={c.id} 
                      choice={c as any}
                      onAccept={(choice) => acceptChoice(choice.id)}
                      onRewrite={(choice) => useWorkspaceStore.getState().setSelectedObject(choice)}
                      onReject={(choice) => rejectChoice(choice.id)}
                    />
                  ))}
                  {recentChoices.length === 0 && (
                     <div className="bg-white rounded-2xl p-4 border border-slate-200 border-dashed flex items-center justify-center">
                       <p className="text-xs text-slate-400 py-6 italic">等待新的 AI 分析结果...</p>
                     </div>
                  )}
                </div>
              </div>
            </div>

            <div className="col-span-3 flex flex-col gap-4">
              <div className="space-y-3">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1">AI 假设账本</h3>
                <div className="space-y-3">
                  {overview.aiAssumptionLedger.length === 0 && (
                    <div className="bg-white rounded-2xl p-4 border border-slate-200 border-dashed flex items-center justify-center">
                      <p className="text-xs text-slate-400 py-6 italic">当前没有 AI 假设节点</p>
                    </div>
                  )}
                  {overview.aiAssumptionLedger.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => {
                        const node = (ir as any)?.nodes?.[item.id];
                        if (node) {
                          setSelectedObject(node);
                          jumpToProjection(node.kind === 'screen' || node.kind === 'ui_component' ? 'ui' : node.kind === 'flow' || node.kind === 'flow_step' || node.kind === 'rule' ? 'system' : node.kind === 'business_object' || node.kind === 'field' || node.kind === 'state_machine' || node.kind === 'object_state' || node.kind === 'state_transition' ? 'data' : 'goal');
                        }
                      }}
                      className="w-full text-left rounded-xl border border-slate-200 bg-white p-4 hover:border-indigo-300 transition-colors"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-amber-600">AI Assumption</span>
                        <span className="text-[10px] text-slate-400">{NodeKindToText[item.kind] || item.kind}</span>
                      </div>
                      <div className="mt-1 text-sm font-medium text-slate-800">{item.title}</div>
                      <div className="mt-1 text-xs text-slate-500 line-clamp-2">{item.source}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>

      <RightObjectPanel />
    </div>
  );
}
