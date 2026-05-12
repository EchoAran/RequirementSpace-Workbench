import { useState, useMemo } from 'react';
import { ReadinessChecklist } from '@/components/shared/ReadinessChecklist';
import { GapCard } from '@/components/shared/GapCard';
import { FlowStepCard } from '@/components/shared/FlowStepCard';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { ComponentTree } from '@/components/shared/ComponentTree';
import { LayoutDashboard, FileDown, RefreshCw, CheckCircle2, Play } from 'lucide-react';
import { 
  useWorkspaceStore, 
  selectFlowSteps, 
  selectIssues, 
  selectActors, 
  selectSelectedObject,
  selectGoals,
  selectLinks
} from '@/store/useWorkspaceStore';
import { workspaceApi } from '@/lib/api';

export function Preview() {
  const { 
    setSelectedObject, generateCandidate, deferObject, setHighlightTarget
  } = useWorkspaceStore();
  
  const flowSteps = useWorkspaceStore(selectFlowSteps);
  const gaps = useWorkspaceStore(selectIssues);
  const actors = useWorkspaceStore(selectActors);
  const selectedObject = useWorkspaceStore(selectSelectedObject);
  const goals = useWorkspaceStore(selectGoals);
  const links = useWorkspaceStore(selectLinks);
  const ir = useWorkspaceStore(s => s.ir);

  const [activeRoleIndex, setActiveRoleIndex] = useState(0);
  const activeRole = actors[activeRoleIndex];
  const [viewMode, setViewMode] = useState<'prototype' | 'tree' | 'playback'>('prototype');
  const [exportState, setExportState] = useState<'idle' | 'exporting' | 'success'>('idle');

  const handleExport = async () => {
    setExportState('exporting');
    try {
      if (!ir?.id) return;
      const data = await workspaceApi.exportWorkspace(ir.id);
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
    
    // find screens assigned to activeRole via reads
    const screenLinks = links.filter(l => l.targetId === activeRole.id && l.type === 'reads');
    const screenIds = screenLinks.map(l => l.sourceId);
    
    return screenIds.map(id => {
      const screenNode = ir.nodes[id];
      if (!screenNode) return null;
      
      // ui components displayed on this screen
      const childLinks = links.filter(l => l.targetId === id && l.type === 'displayed_on');
      const childIds = childLinks.map(l => l.sourceId);
      
      // components acting as actions
      const actions = childIds.filter(cid => ir.nodes[cid]?.title.includes('Button') || ir.nodes[cid]?.title.includes('Action'));
      
      // related steps
      const relatedStepLinks = childIds.flatMap(cid => links.filter(l => l.sourceId === cid && l.type === 'triggered_by'));
      const relatedStepIds = [...new Set(relatedStepLinks.map(l => l.targetId))];
      
      // related gaps
      const relatedGapsToScreen = gaps.filter(g => g.relatedNodeIds.includes(id) || childIds.some(cid => g.relatedNodeIds.includes(cid)));

      return {
        id,
        name: screenNode.title,
        desc: screenNode.description || '无描述',
        actions: actions.map(a => ir.nodes[a]?.title || a),
        relatedSteps: relatedStepIds.map(s => ir.nodes[s]?.title || s),
        relatedGaps: relatedGapsToScreen.map(g => g.title)
      };
    }).filter(Boolean);
  }, [activeRole, ir, links, gaps]);

  const unresolvedGaps = gaps.filter(g => g.status === 'open');
  const blockingGaps = unresolvedGaps.filter(g => g.severity === 'high');
  const warningGaps = unresolvedGaps.filter(g => g.severity === 'medium');

  const readinessItems = [
    { title: '核心目标', status: goals.some((g: any) => g.status === 'confirmed') ? 'ready' : 'error' },
    { title: '角色权限闭环', status: actors.length > 0 ? 'ready' : 'error' },
    { title: '流程无致命断层', status: gaps.some(g => g.category === 'flow_gap' && g.status === 'open' && g.severity === 'high') ? 'error' : 'ready' }
  ];

  const blockingItems = readinessItems.filter(i => i.status === 'error');
  const isReady = blockingItems.length === 0 && blockingGaps.length === 0;

  return (
    <div className="flex-1 flex w-full relative">
      <div className="flex-1 p-6 pb-24 overflow-y-auto">
        <div className="max-w-[1200px] mx-auto space-y-8 animate-in fade-in flex flex-col">
          
          <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col md:flex-row justify-between items-center gap-6">
            <div>
              <h2 className="text-2xl font-bold text-slate-900 mb-2">生成方案就绪确认</h2>
              <p className="text-sm text-slate-600">在正式触发代码生成前，核对整体流程、各视角原型及待确认缺口。</p>
            </div>
            <div className="flex items-center gap-3">
              <button 
                onClick={handleExport}
                disabled={exportState === 'exporting'}
                className="px-5 py-2.5 rounded-xl border border-slate-200 text-slate-700 font-medium hover:bg-slate-50 transition-colors bg-white flex items-center gap-2"
                title={unresolvedGaps.length > 0 ? `可导出草案，但仍有 ${unresolvedGaps.length} 个待确认问题` : '导出需求文档'}
              >
                {exportState === 'idle' && <><FileDown className="w-4 h-4" /> 导出需求</>}
                {exportState === 'exporting' && <><RefreshCw className="w-4 h-4 animate-spin" /> 正在生成</>}
                {exportState === 'success' && <><CheckCircle2 className="w-4 h-4 text-emerald-500" /> 已导出</>}
              </button>
              <button
                disabled={!isReady || exportState === 'exporting'}
                onClick={handleExport}
                className={`px-5 py-2.5 rounded-xl font-medium transition-colors ${isReady ? 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm' : 'bg-slate-300 text-white cursor-not-allowed'} disabled:opacity-50`}
              >
                生成应用草案
              </button>
            </div>
          </section>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            <div className="lg:col-span-8 flex flex-col gap-8">
              {/* Top Left: System Flow Preview */}
              <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <h3 className="font-bold text-slate-900 mb-4">系统流程连贯性概览</h3>
                <div className="flex overflow-x-auto pb-4 gap-4">
                  {flowSteps.map((step, idx) => (
                    <div key={step.id} className="min-w-[280px] shrink-0 flex flex-col">
                      <div className="flex items-center gap-2 mb-2 px-1">
                        <div className="w-5 h-5 rounded bg-slate-100 text-slate-500 flex items-center justify-center text-[10px] font-bold">{idx + 1}</div>
                        <span className="text-[10px] font-bold text-slate-400 uppercase">{step.actor}</span>
                      </div>
                      <div 
                        onClick={() => setSelectedObject(step)}
                        className={`cursor-pointer rounded-xl transition-all border ${selectedObject?.id === step.id ? 'border-indigo-500 ring-2 ring-indigo-100' : 'border-transparent'}`}
                      >
                         <FlowStepCard 
                           name={step.title}
                           type={step.stepType}
                           actor={step.actor}
                           status={step.status}
                           inputs={step.input}
                           outputs={step.output}
                           active={selectedObject?.id === step.id} 
                           onClick={() => setSelectedObject(step)} 
                         />
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              {/* Bottom Left: Role View Prototype */}
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
                              {p?.relatedGaps && p.relatedGaps.length > 0 && (
                                 <div className="text-[11px] text-rose-600 line-clamp-1"><span className="text-rose-400 font-medium mr-1.5 border border-rose-100 bg-rose-50 rounded px-1 shadow-sm">缺口</span>{p.relatedGaps.join(', ')}</div>
                              )}
                              {(!p?.relatedSteps || p.relatedSteps.length === 0) && (!p?.relatedGaps || p.relatedGaps.length === 0) && <span className="text-[11px] text-slate-400 italic">暂无关联项</span>}
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
                    <div className="text-center py-12 border-2 border-dashed border-slate-200 rounded-xl animate-in fade-in text-slate-500">
                      <Play className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p className="font-medium">连贯性回放开发中</p>
                      <p className="text-xs mt-1 opacity-70">将根据 FlowStep 自动串联界面流转</p>
                    </div>
                  )}
                </div>
              </section>
            </div>
            
            {/* Right side: Checking & Gaps */}
            <div className="lg:col-span-4 flex flex-col gap-8">
              <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm h-full">
                <h3 className="font-bold text-slate-900 mb-4">生成前检查</h3>
                <div className="mb-6">
                  <ReadinessChecklist title="必须解决的条件 (阻塞点)" items={readinessItems.map(item => ({ label: item.title, checked: item.status === 'ready', type: item.status === 'error' ? 'blocking' : item.status === 'warning' ? 'info' : undefined }))} />
                  {(!isReady) && <p className="text-[11px] text-red-500 mt-2 px-1">必须修复阻塞问题并处理所有高风险缺口，生成操作才会激活。</p>}
                  
                  {isReady && warningGaps.length > 0 && (
                    <div className="mt-3 p-3 bg-amber-50 rounded-xl border border-amber-200 flex items-start gap-2">
                       <span className="text-xs text-amber-700">允许带风险生成：有 {warningGaps.length} 个非阻塞缺口，系统将在代码中生成 TODO。</span>
                    </div>
                  )}
                </div>

                <div className="pt-6 border-t border-slate-100">
                    <h3 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
                      遗留缺口项
                      {unresolvedGaps.length > 0 && <span className={`text-xs px-2 py-0.5 rounded-full ${blockingGaps.length > 0 ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>{unresolvedGaps.length}</span>}
                    </h3>
                    {unresolvedGaps.length === 0 && <p className="text-xs text-slate-500 italic">所有缺口均已处理或暂缓。</p>}
                    <div className="space-y-3">
                      {unresolvedGaps.map(gap => (
                        <GapCard 
                          key={gap.id}
                          gap={gap as any}
                          onClick={() => {
                            setSelectedObject(gap as any);
                            if (gap.relatedNodeIds[0]) setHighlightTarget(gap.relatedNodeIds[0]);
                          }}
                          onGenerate={() => generateCandidate(gap.id)}
                          onDefer={() => deferObject(gap.id)}
                        />
                      ))}
                    </div>
                </div>
              </section>
            </div>

          </div>

        </div>
      </div>

      <RightObjectPanel />
    </div>
  );
}
