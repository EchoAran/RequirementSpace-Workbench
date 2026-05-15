import { useState, useMemo } from 'react';
import { IssueCard } from '@/components/shared/IssueCard';
import { FlowStepCard } from '@/components/shared/FlowStepCard';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { ComponentTree } from '@/components/shared/ComponentTree';
import { LayoutDashboard, FileDown, RefreshCw, CheckCircle2, Play } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { buildPlaybackForActor, buildPreviewCheckpoints, buildRolePages, buildStepDetail, projectionPath, selectAllProposals, selectAllSlots, selectPerformerTitle } from '@/domain/ir/selectors';
import { 
  useWorkspaceStore, 
  selectFlowSteps, 
  selectIssues, 
  selectActors, 
  selectSelectedObject,
  selectLinks
} from '@/store/useWorkspaceStore';
import { workspaceApi } from '@/lib/api';

export function Preview() {
  const { 
    setSelectedObject,
    createSlotFromIssue,
    expandSlot,
    updateIssueAttributes,
    setHighlightTarget
  } = useWorkspaceStore();
  const navigate = useNavigate();
  
  const flowSteps = useWorkspaceStore(selectFlowSteps);
  const issues = useWorkspaceStore(selectIssues);
  const actors = useWorkspaceStore(selectActors);
  const selectedObject = useWorkspaceStore(selectSelectedObject);
  const links = useWorkspaceStore(selectLinks);
  const ir = useWorkspaceStore(s => s.ir);

  const [activeRoleIndex, setActiveRoleIndex] = useState(0);
  const activeRole = actors[activeRoleIndex];
  const [viewMode, setViewMode] = useState<'prototype' | 'tree' | 'playback'>('prototype');
  const [exportState, setExportState] = useState<'idle' | 'exporting' | 'success'>('idle');

  const handleExport = async (format: 'json' | 'markdown') => {
    setExportState('exporting');
    try {
      if (!ir?.id) return;
      if (format === 'markdown') {
        const md = await workspaceApi.exportMarkdown(ir.id);
        const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${ir.name || ir.id || 'requirement-space'}.md`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        setExportState('success');
        setTimeout(() => setExportState('idle'), 1500);
        return;
      }

      const data = await workspaceApi.exportJson(ir.id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${data.name || data.id || 'requirement-space'}.json`;
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

  // Calculate screens dynamically
  const pages = useMemo(() => {
    if (!ir || !activeRole) return [];
    return buildRolePages(ir, activeRole.id);
  }, [activeRole, ir]);
  const checkpoints = useMemo(() => buildPreviewCheckpoints(ir), [ir]);
  const playback = useMemo(() => buildPlaybackForActor(ir, activeRole?.id || null), [activeRole, ir]);

  const unresolvedIssues = issues.filter(g => g.status === 'open');
  const blockingIssues = unresolvedIssues.filter(g => g.severity === 'high');
  const pendingSlots = useMemo(() => selectAllSlots(ir).filter((slot) => slot.status === 'empty' || slot.status === 'candidate_ready'), [ir]);
  const pendingProposals = useMemo(() => selectAllProposals(ir).filter((proposal) => proposal.status === 'candidate' || proposal.status === 'draft'), [ir]);

  const openIssueFlow = async (issueId: string) => {
    const slotId = await createSlotFromIssue(issueId);
    if (slotId) {
      await expandSlot(slotId);
    }
  };

  const exportAuditLog = async () => {
    if (!ir) return;
    setExportState('exporting');
    try {
      const blob = new Blob([JSON.stringify(ir.audit, null, 2)], { type: 'application/json;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${ir.name || ir.id || 'requirement-space'}-audit.json`;
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

  return (
    <div className="flex-1 flex w-full relative">
      <div className="flex-1 p-6 pb-24 overflow-y-auto">
        <div className="max-w-[1200px] mx-auto space-y-8 animate-in fade-in flex flex-col">
          
          <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col md:flex-row justify-between items-center gap-6">
            <div>
              <h2 className="text-2xl font-bold text-slate-900 mb-2">生成方案就绪确认</h2>
              <p className="text-sm text-slate-600">在正式触发代码生成前，核对整体流程、各视角原型及待确认 Issue。</p>
            </div>
            <div className="flex items-center gap-3">
              <button 
                onClick={() => handleExport('json')}
                disabled={exportState === 'exporting'}
                className="px-5 py-2.5 rounded-xl border border-slate-200 text-slate-700 font-medium hover:bg-slate-50 transition-colors bg-white flex items-center gap-2"
                title={unresolvedIssues.length > 0 ? `可导出 JSON 草案，但仍有 ${unresolvedIssues.length} 个待确认问题` : '导出 JSON 草案'}
              >
                {exportState === 'idle' && <><FileDown className="w-4 h-4" /> 导出 JSON 草案</>}
                {exportState === 'exporting' && <><RefreshCw className="w-4 h-4 animate-spin" /> 正在生成</>}
                {exportState === 'success' && <><CheckCircle2 className="w-4 h-4 text-emerald-500" /> 已导出</>}
              </button>
              <button
                onClick={() => handleExport('markdown')}
                disabled={exportState === 'exporting'}
                className="px-4 py-2.5 rounded-xl border border-slate-200 text-slate-700 font-medium hover:bg-slate-50 transition-colors bg-white"
              >
                导出 Markdown
              </button>
              <button
                onClick={() => void exportAuditLog()}
                disabled={exportState === 'exporting'}
                className="px-4 py-2.5 rounded-xl border border-slate-200 text-slate-700 font-medium hover:bg-slate-50 transition-colors bg-white"
              >
                导出 Audit
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

            <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
              <h3 className="font-bold text-slate-900 mb-4">系统流程连贯性概览</h3>
              <div className="flex overflow-x-auto pb-4 gap-4">
                {flowSteps.map((step, idx) => (
                  <div key={step.id} className="min-w-[280px] shrink-0 flex flex-col">
                    <div className="flex items-center gap-2 mb-2 px-1">
                      <div className="w-5 h-5 rounded bg-slate-100 text-slate-500 flex items-center justify-center text-[10px] font-bold">{idx + 1}</div>
                      <span className="text-[10px] font-bold text-slate-400 uppercase">{selectPerformerTitle(ir as any, step.id) || '—'}</span>
                    </div>
                    {(() => {
                      const stepDetail = buildStepDetail(ir, step.id);
                      return (
                    <div 
                      onClick={() => setSelectedObject(step)}
                      className={`cursor-pointer rounded-xl transition-all border ${selectedObject?.id === step.id ? 'border-indigo-500 ring-2 ring-indigo-100' : 'border-transparent'}`}
                    >
                      <FlowStepCard 
                        name={step.title}
                        type={step.stepType}
                        actor={selectPerformerTitle(ir as any, step.id) || '—'}
                        status={step.status}
                        inputs={stepDetail.inputs}
                        outputs={stepDetail.outputs}
                        rules={stepDetail.rules}
                        stateChanges={stepDetail.stateChanges}
                        relatedPages={stepDetail.relatedPages}
                        relatedIssueCount={stepDetail.relatedIssueIds.length}
                        relatedChoiceCount={stepDetail.relatedChoiceIds.length}
                        active={selectedObject?.id === step.id} 
                        onClick={() => setSelectedObject(step)} 
                      />
                    </div>
                      );
                    })()}
                  </div>
                ))}
              </div>
            </section>

            <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm flex-1">
              <div className="flex items-center justify-between border-b border-slate-200 mb-6">
                <h3 className="font-bold text-slate-900 pb-4">基于角色视角的界面模型</h3>
                <div className="flex bg-slate-100 p-1 rounded-lg mb-2">
                  <button onClick={() => setViewMode('prototype')} className={`px-3 py-1 text-xs font-bold rounded-md ${viewMode === 'prototype' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:bg-slate-200'}`}>角色原型</button>
                  <button onClick={() => setViewMode('tree')} className={`px-3 py-1 text-xs font-bold rounded-md flex items-center gap-1 ${viewMode === 'tree' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:bg-slate-200'}`}>组件树视图</button>
                  <button onClick={() => setViewMode('playback')} className={`px-3 py-1 text-xs font-bold rounded-md flex items-center gap-1 ${viewMode === 'playback' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:bg-slate-200'}`}>流程回放</button>
                </div>
              </div>
              
              <div className="border-b border-slate-200">
                <nav className="-mb-px flex space-x-6 px-1">
                  {actors.map((actor, idx) => (
                    <button
                      key={actor.id}
                      onClick={() => setActiveRoleIndex(idx)}
                      className={`
                        whitespace-nowrap pb-3 pt-2 px-1 text-sm font-medium border-b-2 transition-colors
                        ${activeRoleIndex === idx 
                          ? 'border-sky-500 text-sky-600' 
                          : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700'}
                      `}
                    >
                      {actor.title}
                    </button>
                  ))}
                </nav>
              </div>
              
              <div className="pt-6">
                {viewMode === 'prototype' && (
                  <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2">
                  <p className="text-sm font-medium text-slate-600 mb-2">该角色可用页面:</p>
                  {pages.map(p => (
                    <div key={p?.id || p?.name} 
                         onClick={() => { if(p?.id) setSelectedObject(ir?.nodes[p.id]) }}
                         className={`border border-slate-200 rounded-xl p-4 bg-slate-50/50 cursor-pointer transition-all ${selectedObject?.id === p?.id ? 'ring-2 ring-indigo-500' : 'hover:border-slate-300 hover:bg-slate-50'}`}>
                      <h4 className="font-semibold text-slate-800 flex items-center gap-2 mb-1">
                        <LayoutDashboard className="w-4 h-4 text-sky-500" />
                        {p?.name}
                      </h4>
                      <p className="text-xs text-slate-500 mb-3">{p?.desc}</p>
                      
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-3 pt-3 border-t border-slate-200/60">
                        <div>
                          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">可执行动作</div>
                          <div className="flex gap-1.5 flex-wrap text-[11px]">
                            {p?.actions && p.actions.length > 0 ? p.actions.map(a => <span key={a} className="bg-white border border-slate-200 px-2 py-0.5 rounded text-slate-600 shadow-sm">{a}</span>) : <span className="text-slate-400 italic">暂无</span>}
                          </div>
                        </div>
                        <div>
                          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">关联项</div>
                          <div className="flex flex-col gap-1.5">
                            {p?.relatedSteps && p.relatedSteps.length > 0 && (
                               <div className="text-[11px] text-slate-600 line-clamp-1"><span className="text-slate-400 font-medium mr-1.5 border border-slate-200 bg-white rounded px-1 shadow-sm">流程</span>{p.relatedSteps.join(', ')}</div>
                            )}
                            {p?.relatedIssues && p.relatedIssues.length > 0 && (
                               <div className="text-[11px] text-rose-600 line-clamp-1"><span className="text-rose-400 font-medium mr-1.5 border border-rose-100 bg-rose-50 rounded px-1 shadow-sm">Issue</span>{p.relatedIssues.join(', ')}</div>
                            )}
                            {(!p?.relatedSteps || p.relatedSteps.length === 0) && (!p?.relatedIssues || p.relatedIssues.length === 0) && <span className="text-[11px] text-slate-400 italic">暂无关联项</span>}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                  </div>
                )}

                {viewMode === 'tree' && activeRole && (
                  <div className="animate-in fade-in slide-in-from-bottom-2">
                    <ComponentTree 
                      nodes={ir?.nodes || {}} 
                      links={links} 
                      actorId={activeRole.id} 
                      onSelectNode={(node) => setSelectedObject(node)}
                      selectedNodeId={selectedObject?.id}
                    />
                  </div>
                )}

                {viewMode === 'playback' && (
                  <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2">
                    {playback.length === 0 && (
                      <div className="text-center py-12 border-2 border-dashed border-slate-200 rounded-xl text-slate-500">
                        <Play className="w-8 h-8 mx-auto mb-2 opacity-50" />
                        <p className="font-medium">当前角色暂无可回放界面流</p>
                        <p className="text-xs mt-1 opacity-70">将根据组件触发的 `invokes_step` 关系自动串联</p>
                      </div>
                    )}
                    {playback.map((item, index) => (
                      <div key={item.screenId} className="rounded-xl border border-slate-200 bg-slate-50/50 p-4">
                        <div className="flex items-center justify-between gap-2">
                          <div>
                            <div className="text-sm font-bold text-slate-900">{index + 1}. {item.screenTitle}</div>
                            <div className="text-xs text-slate-500 mt-1">基于 `ui_component` 到 `flow_step` 的 `invokes_step` 关系推导的页面回放</div>
                          </div>
                          <button
                            type="button"
                            onClick={() => setSelectedObject(ir?.nodes[item.screenId] || null)}
                            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                          >
                            查看页面
                          </button>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {item.stepTitles.length === 0 && <span className="text-xs text-slate-400 italic">未绑定流程步骤</span>}
                          {item.stepTitles.map((title) => (
                            <span key={title} className="rounded-full bg-white border border-slate-200 px-3 py-1 text-xs text-slate-700">
                              {title}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>

            <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
              <h3 className="font-bold text-slate-900 mb-4">进入实现前剩余对象</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="rounded-xl border border-slate-200 p-4 bg-slate-50/50">
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-400">Open Issues</div>
                  <div className="mt-2 text-2xl font-bold text-rose-600">{unresolvedIssues.length}</div>
                </div>
                <div className="rounded-xl border border-slate-200 p-4 bg-slate-50/50">
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-400">Pending Slots</div>
                  <div className="mt-2 text-2xl font-bold text-amber-600">{pendingSlots.length}</div>
                </div>
                <div className="rounded-xl border border-slate-200 p-4 bg-slate-50/50">
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-400">Pending Proposals</div>
                  <div className="mt-2 text-2xl font-bold text-violet-600">{pendingProposals.length}</div>
                </div>
              </div>
            </section>

            <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
              <h3 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
                遗留 Issue
                {unresolvedIssues.length > 0 && <span className={`text-xs px-2 py-0.5 rounded-full ${blockingIssues.length > 0 ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>{unresolvedIssues.length}</span>}
              </h3>
              {unresolvedIssues.length === 0 && <p className="text-xs text-slate-500 italic">所有 Issue 均已处理或忽略。</p>}
              <div className="space-y-3">
                {unresolvedIssues.map(issue => (
                  <IssueCard
                    key={issue.id}
                    issue={issue as any}
                    onClick={() => {
                      setSelectedObject(issue as any);
                      if (issue.relatedNodeIds[0]) setHighlightTarget(issue.relatedNodeIds[0]);
                      if ((issue as any).suggestedProjection) jumpToProjection((issue as any).suggestedProjection);
                    }}
                    onCreateSlot={() => void openIssueFlow(issue.id)}
                    onIgnore={() => void updateIssueAttributes(issue.id, { status: 'ignored' })}
                  />
                ))}
              </div>
            </section>
          </div>

        </div>
      </div>

      <RightObjectPanel />
    </div>
  );
}
