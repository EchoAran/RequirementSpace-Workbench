import { GapCard } from '@/components/shared/GapCard';
import { ReadinessChecklist } from '@/components/shared/ReadinessChecklist';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { CandidateCard } from '@/components/shared/CandidateCard';
import { 
  useWorkspaceStore, 
  selectGoals, 
  selectIssues, 
  selectCandidates, 
  selectTasks, 
  selectCapabilities, 
  selectActors, 
  selectFlowSteps 
} from '@/store/useWorkspaceStore';

export function Overview() {
  const { 
    setSelectedObject, acceptCandidate, deferObject, excludeObject, generateCandidate 
  } = useWorkspaceStore();
  
  const goals = useWorkspaceStore(selectGoals);
  const gaps = useWorkspaceStore(selectIssues);
  const candidates = useWorkspaceStore(selectCandidates);
  const tasks = useWorkspaceStore(selectTasks);
  const capabilities = useWorkspaceStore(selectCapabilities);
  const actors = useWorkspaceStore(selectActors);
  const flowSteps = useWorkspaceStore(selectFlowSteps);
  const ir = useWorkspaceStore(state => state.ir);

  const highRiskGaps = gaps.filter(g => g.severity === 'high' && g.status === 'open');
  
  // Calculate Coverage
  const calculateCoverage = (nodes: any[]) => {
    if (nodes.length === 0) return 0;
    const confirmed = nodes.filter(n => n.status === 'confirmed').length;
    return Math.floor((confirmed / nodes.length) * 100);
  };

  const goalScore = goals.length > 0 ? calculateCoverage(goals) : 0;
  const actorScore = actors.length > 0 ? calculateCoverage(actors) : 0;
  const flowScore = flowSteps.length > 0 ? calculateCoverage(flowSteps) : 0;
  const screens = ir ? Object.values(ir.nodes).filter(n => n.kind === 'screen') : [];
  const uiScore = screens.length > 0 ? calculateCoverage(screens) : 0;
  const dataObjects = ir ? Object.values(ir.nodes).filter(n => n.kind === 'business_object') : [];
  const dataScore = dataObjects.length > 0 ? calculateCoverage(dataObjects) : 0;

  const readinessScore = Math.floor((goalScore + actorScore + flowScore + uiScore + dataScore) / 5);

  const openChoiceGroupsCount = ir?.choiceGroups ? Object.values(ir.choiceGroups).filter(cg => cg.status === 'open').length : 0;
  const openSlotsCount = openChoiceGroupsCount; // Approximating slot with choice group

  // Build the Decision Queue
  const decisionQueueItems: any[] = [];
  
  if (ir?.choiceGroups) {
    Object.values(ir.choiceGroups).forEach(cg => {
      if (cg.status === 'open') {
        const slotName = ir.slots?.[cg.slotId]?.name || `Slot: ${cg.slotId}`;
        decisionQueueItems.push({
          id: cg.id,
          title: slotName,
          description: `有 ${cg.choices.length} 个候选方案待确认`,
          kind: 'slot',
          status: 'needs_confirmation',
          original: cg
        });
      }
    });
  }

  gaps.filter(g => g.status === 'open' && g.severity !== 'high').forEach(gap => {
     decisionQueueItems.push({
       id: gap.id,
       title: gap.title,
       description: gap.description,
       kind: 'issue',
       status: 'needs_confirmation',
       original: gap
     });
  });

  const decisionQueue = decisionQueueItems.slice(0, 5);

  const recentCandidates = candidates.filter(c => c.status === 'candidate').slice(0, 3);
  
  const allObjects = [...goals, ...capabilities, ...tasks, ...actors, ...flowSteps, ...candidates];
  const confirmedCount = allObjects.filter(o => o.status === 'confirmed').length;
  const aiCount = allObjects.filter(o => o.status === 'ai_assumption').length;
  const pendingCount = decisionQueueItems.length;
  
  const readinessItems = [
    { title: `目标覆盖度 ${goalScore}%`, status: goalScore > 80 ? 'ready' : 'error' },
    { title: `角色闭环 ${actorScore}%`, status: actorScore > 80 ? 'ready' : 'error' },
    { title: `流程闭环 ${flowScore}%`, status: flowScore > 80 ? 'ready' : 'error' },
    { title: `数据映射 ${dataScore}%`, status: dataScore > 80 ? 'ready' : 'error' },
    { title: `UI页面交互 ${uiScore}%`, status: uiScore > 80 ? 'ready' : 'error' }
  ];

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
                    {readinessScore}%
                  </p>
                </div>
                <div className="h-10 w-[1px] bg-slate-100"></div>
                <div className="flex gap-4">
                  <div className="flex flex-col">
                    <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1 mt-1">阻塞问题</p>
                    <span className="text-rose-600 text-lg font-bold font-mono">{String(highRiskGaps.length).padStart(2, '0')}</span>
                  </div>
                  <div className="flex flex-col">
                    <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1 mt-1">待决策Slot</p>
                    <span className="text-amber-600 text-lg font-bold font-mono">{String(openSlotsCount).padStart(2, '0')}</span>
                  </div>
                  <div className="flex flex-col">
                    <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1 mt-1">开放候选组</p>
                    <span className="text-blue-600 text-lg font-bold font-mono">{String(openChoiceGroupsCount).padStart(2, '0')}</span>
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                <span className="px-2.5 py-1 bg-green-50 text-green-700 text-xs font-bold rounded-full border border-green-200">目标 {goalScore}%</span>
                <span className="px-2.5 py-1 bg-amber-50 text-amber-700 text-xs font-bold rounded-full border border-amber-200">角色 {actorScore}%</span>
                <span className="px-2.5 py-1 bg-blue-50 text-blue-700 text-xs font-bold rounded-full border border-blue-200">流程 {flowScore}%</span>
                <span className="px-2.5 py-1 bg-indigo-50 text-indigo-700 text-xs font-bold rounded-full border border-indigo-200">数据 {dataScore}%</span>
                <span className="px-2.5 py-1 bg-purple-50 text-purple-700 text-xs font-bold rounded-full border border-purple-200">UI {uiScore}%</span>
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
                    onClick={() => setSelectedObject(item.original || item)}
                    className="cursor-pointer bg-white p-4 rounded-xl border border-slate-200 shadow-sm hover:border-indigo-300 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] px-2 py-0.5 bg-slate-100 text-slate-500 rounded uppercase font-bold tracking-wider">{(item as any).kind || '待办'}</span>
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
                <ReadinessChecklist title="维度覆盖率" items={readinessItems.map(item => ({ label: item.title, checked: item.status === 'ready', type: item.status === 'error' ? 'blocking' : item.status === 'warning' ? 'info' : undefined }))} />
              </div>
            </div>

            {/* Middle Column: High Risk & AI Candidates */}
            <div className="col-span-8 flex flex-col gap-4">
              <div className="space-y-3">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1">高优先级缺口</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {highRiskGaps.map(gap => (
                    <GapCard 
                      key={gap.id} 
                      gap={gap as any} 
                      onClick={() => setSelectedObject(gap as any)}
                      onGenerate={(gap) => generateCandidate(gap.id)}
                      onDefer={(gap) => deferObject(gap.id)}
                    />
                  ))}
                  {highRiskGaps.length === 0 && (
                    <div className="bg-white rounded-2xl p-4 border border-slate-200 border-dashed flex items-center justify-center col-span-2">
                      <p className="text-xs text-slate-400 py-6 italic">暂无高风险缺口</p>
                    </div>
                  )}
                </div>
              </div>

              <div className="pt-2 space-y-3">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1 italic">最近候选方案</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {recentCandidates.map(c => (
                    <CandidateCard 
                      key={c.id} 
                      candidate={c as any} 
                      onAccept={() => acceptCandidate(c.id)}
                      onRewrite={() => {}}
                      onReject={() => excludeObject(c.id)}
                    />
                  ))}
                  {recentCandidates.length === 0 && (
                     <div className="bg-white rounded-2xl p-4 border border-slate-200 border-dashed flex items-center justify-center">
                       <p className="text-xs text-slate-400 py-6 italic">等待新的 AI 分析结果...</p>
                     </div>
                  )}
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
