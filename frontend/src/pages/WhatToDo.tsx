import { useState, type MouseEvent } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { 
  useWorkspaceStore, 
  selectGoals, 
  selectActors, 
} from '@/store/useWorkspaceStore';
import {
  getChildCapabilities,
  getRootCapabilities,
} from '@/core/selectors';

export function WhatToDo() {
  const { 
    setSelectedObject, highlightTarget, selectedObject, ir
  } = useWorkspaceStore();
  
  const goals = useWorkspaceStore(selectGoals);
  const actors = useWorkspaceStore(selectActors);

  const mainGoal = goals[0];
  const rootCapabilities = getRootCapabilities(ir as any) as any[];
  
  const [expandedCaps, setExpandedCaps] = useState<Record<string, boolean>>({});

  const toggleCap = (e: MouseEvent, id: string) => {
    e.stopPropagation();
    setExpandedCaps(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const getActorName = (actorId: number) => {
    const actor = (ir?.actors || []).find(a => a.actorId === actorId);
    return actor ? actor.actorName : '系统';
  };

  const allFeatures = ir?.features || [];
  const allScenarios = allFeatures.flatMap(f => (f.scenarios || []).map(s => ({
    ...s,
    featureName: f.featureName,
  })));

  return (
    <div className="flex-1 flex w-full relative">
      <div className="flex-1 p-6 pb-24 overflow-y-auto w-full">
        <div className="max-w-[1240px] mx-auto animate-in fade-in duration-500">
          
          <div className="grid grid-cols-12 gap-6 h-full content-start">
            
            {/* Goal Section */}
            <section className="col-span-12 bg-white rounded-2xl border border-slate-200 p-6 flex flex-col md:flex-row items-start md:items-center justify-between shadow-sm gap-6">
              <div className="flex-1">
                 <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-2">应用目标与成功标准</p>
                 <p className="text-slate-800 font-medium mb-3">主目标：{mainGoal?.title || '定义核心应用目标'}</p>
                 <ul className="space-y-2">
                   <li className="flex items-center gap-2 text-sm text-slate-600">
                      <StatusBadge status={mainGoal?.status || 'needs_confirmation'} />
                      <span className="font-bold text-slate-700">成效标准：</span>
                      <span>{mainGoal?.description || '待补充量化标准'}</span>
                   </li>
                 </ul>
              </div>
            </section>

            {/* Tree and other main sections */}
            <div className="col-span-12 space-y-6">
              
              {/* Roles Section */}
              <section>
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1 mb-3">角色定义</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {actors.map(actor => (
                    <div 
                      key={actor.id} 
                      onClick={() => setSelectedObject(actor)}
                      className={`bg-white rounded-xl p-4 border transition-all cursor-pointer flex flex-col gap-3 ${selectedObject?.id === actor.id ? 'ring-2 ring-indigo-500 border-transparent shadow-md' : 'border-slate-200 hover:border-indigo-300 shadow-sm'}`}
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600 font-bold border border-indigo-100">
                            {actor.title.charAt(0)}
                          </div>
                          <div>
                            <h4 className="font-bold text-slate-800 text-sm tracking-wide">{actor.title}</h4>
                            <span className="text-[10px] text-slate-400">
                              {actor.scopeStatus === 'in_scope'
                                ? '本期覆盖'
                                : actor.scopeStatus === 'external_dependency'
                                  ? '外部依赖'
                                  : actor.scopeStatus === 'deferred'
                                    ? '暂缓'
                                    : actor.status === 'excluded' || actor.scopeStatus === 'out_of_scope'
                                      ? '不在范围'
                                      : '待确认范围'}
                            </span>
                          </div>
                        </div>
                        <StatusBadge status={actor.status} className="scale-90 origin-right" />
                      </div>
                      <div className="text-xs text-slate-600 line-clamp-2">
                        {actor.description || '无具体描述'}
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              {/* Tree Section */}
              <section>
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1 mb-3">核心能力特征树</h3>
                <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                  
                  {/* Layer 1: System Root Header */}
                  <div className="bg-gradient-to-r from-indigo-50/80 to-sky-50/80 backdrop-blur-sm text-slate-800 rounded-2xl p-5 mb-6 flex justify-between items-center shadow-sm border border-indigo-100">
                    <div>
                      <h4 className="font-extrabold text-base text-slate-900 tracking-wide flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-pulse"></span>
                        系统建模根节点: {ir?.projectName || '核心系统'}
                      </h4>
                      <p className="text-xs text-slate-500 mt-1.5 max-w-xl font-medium">{ir?.projectDescription || '主系统业务空间与架构模型总揽。'}</p>
                    </div>
                    <span className="text-[10px] bg-white text-indigo-600 border border-indigo-150 px-2.5 py-1 rounded-lg font-bold shrink-0 shadow-sm">
                      ROOT SYSTEM
                    </span>
                  </div>

                  <div className="space-y-4 pl-4 border-l-2 border-indigo-100 ml-2">
                    {rootCapabilities.map(cap => {
                      const children = getChildCapabilities(ir as any, cap.id) as any[];
                      return (
                        <div key={cap.id} className="relative">
                          <div className="absolute w-4 h-px bg-indigo-100 -left-4 top-5"></div>
                          
                          {/* Layer 2: Functional Module (Branch Node) */}
                          <div 
                            onClick={() => setSelectedObject(cap)}
                            className={`rounded-xl p-4 cursor-pointer transition-colors mb-2 bg-slate-50 border ${selectedObject?.id === cap.id ? 'bg-indigo-50 border-2 border-indigo-500 shadow-sm' : 'border-slate-200 hover:border-indigo-300'}`}
                          >
                            <div className="flex items-center justify-between pb-2 border-b border-slate-200/60 mb-2">
                              <div className="flex items-center gap-2">
                                {children.length > 0 && (
                                  <button onClick={(e) => toggleCap(e, cap.id)} className="p-0.5 hover:bg-slate-200 rounded text-slate-500 transition-colors">
                                    {expandedCaps[cap.id] !== false ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                                  </button>
                                )}
                                <h4 className="font-bold text-slate-800 text-sm flex items-center gap-1.5">
                                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400"></span>
                                  功能模块: {cap.title}
                                </h4>
                              </div>
                              <StatusBadge status={cap.status} />
                            </div>
                            
                            <p className="text-xs text-slate-500 ml-6 leading-relaxed mb-2">
                              {cap.description || '暂无该模块的功能说明'}
                            </p>
                            
                            <div className="flex flex-wrap gap-2 text-[10px] font-medium ml-6">
                              <span className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded border border-slate-200">
                                包含 {children.length} 个具体子功能点
                              </span>
                            </div>
                          </div>
                          
                          {/* Layer 3: Leaf Nodes (Specific Features) */}
                          {(children.length > 0 && expandedCaps[cap.id] !== false) && (
                            <div className="pl-6 space-y-2 mt-2 relative">
                              <div className="absolute w-px h-full bg-slate-100 left-3 top-0"></div>
                              {children.map(child => {
                                const featObj = (ir?.features || []).find(f => f.featureId.toString() === child.id || f.featureId === child.featureId);
                                const capScenarios = featObj?.scenarios || [];
                                const capActors = featObj?.actorIds || [];
                                const capAcCount = capScenarios.reduce((acc: number, s: any) => acc + (s.acceptanceCriteria?.length || 0), 0);

                                return (
                                  <div 
                                    key={child.id} 
                                    onClick={(e) => { e.stopPropagation(); setSelectedObject(child); }}
                                    className={`relative flex flex-col justify-center rounded-xl p-4 cursor-pointer group transition-all mb-2 border ${selectedObject?.id === child.id ? 'bg-indigo-50 border-2 border-indigo-500 z-10 shadow-sm' : 'bg-white border-slate-200 hover:border-indigo-300 hover:shadow-sm'}`}
                                  >
                                    <div className="absolute w-3 h-px bg-slate-100 -left-3 top-6"></div>
                                    <div className="flex items-center justify-between mb-2">
                                      <h5 className="text-xs font-bold text-slate-800 group-hover:text-indigo-700 transition-colors flex items-center gap-1.5">
                                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                                        具体功能点: {child.title}
                                      </h5>
                                      <StatusBadge status={child.status} className="scale-75 origin-right" />
                                    </div>
                                    <div className="text-[11px] text-slate-500 line-clamp-2 ml-4 leading-relaxed mb-3">
                                      {child.description || '暂无功能点描述'}
                                    </div>

                                    {/* Leaf capability rich metadata badges */}
                                    <div className="flex flex-wrap gap-1.5 text-[9px] font-bold ml-4">
                                      <span className="bg-indigo-50 border border-indigo-100 text-indigo-700 px-2 py-0.5 rounded-md shadow-sm">
                                        {capScenarios.length} 个成功场景
                                      </span>
                                      <span className="bg-purple-50 border border-purple-100 text-purple-700 px-2 py-0.5 rounded-md shadow-sm">
                                        {capAcCount} 个验收标准
                                      </span>
                                      <span className="bg-blue-50 border border-blue-100 text-blue-700 px-2 py-0.5 rounded-md shadow-sm">
                                        {Math.max(1, capActors.length)} 涉及角色
                                      </span>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </section>

              {/* Scenarios & Acceptance Criteria Section with Intelligent Linkage Filter */}
              <section>
                 {(() => {
                   const selectedFeatureId = selectedObject?.featureId || (selectedObject?.kind === 'feature' ? parseInt(selectedObject.id, 10) : null);
                   const isLeafSelected = selectedObject?.kind === 'feature' && selectedObject?.parentId !== null;
                   
                   const displayedScenarios = (isLeafSelected && selectedFeatureId)
                     ? allScenarios.filter(s => s.featureId === selectedFeatureId)
                     : allScenarios;

                   return (
                     <>
                       <div className="flex justify-between items-center mb-3 px-1">
                         <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                           成功场景与验收标准 (User Story & AC)
                         </h3>
                         {isLeafSelected && (
                           <button 
                             onClick={() => setSelectedObject(null)}
                             className="text-[10px] bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-600 px-2 py-0.5 rounded-md font-bold transition-all shadow-sm"
                           >
                             显示全部场景（当前过滤展示 {displayedScenarios.length} / {allScenarios.length} 项）
                           </button>
                         )}
                       </div>

                       {isLeafSelected && (
                         <div className="mb-4 bg-indigo-50/50 border border-indigo-100 rounded-xl p-3 text-xs text-indigo-700 flex justify-between items-center shadow-sm">
                           <div>
                             已自动筛选具体功能点 <span className="font-extrabold font-mono bg-white border border-indigo-200 px-1.5 py-0.5 rounded text-indigo-800">“{selectedObject.title}”</span> 下的成功场景（共计 {displayedScenarios.length} 个）。
                           </div>
                         </div>
                       )}

                       {displayedScenarios.length === 0 && (
                         <div className="bg-white rounded-2xl p-8 border border-dashed border-slate-200 text-sm text-slate-400 italic text-center">
                           该节点下暂无关联的成功场景与验收标准。
                         </div>
                       )}

                       <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                         {displayedScenarios.map(s => (
                           <div 
                             key={s.scenarioId} 
                             onClick={() => setSelectedObject(s)} 
                             className={`bg-white rounded-2xl p-6 cursor-pointer transition-all flex flex-col gap-4 border ${selectedObject?.id === s.scenarioId.toString() || selectedObject?.scenarioId === s.scenarioId ? 'ring-2 ring-indigo-500 border-transparent shadow-md' : 'border-slate-200 hover:border-indigo-300 shadow-sm'}`}
                           >
                             <div className="flex justify-between items-start">
                               <div className="space-y-1">
                                 <h4 className="font-bold text-slate-800 text-sm tracking-wide">{s.scenarioName}</h4>
                                 <div className="flex flex-wrap gap-1.5 items-center">
                                   <span className="text-[9px] bg-slate-100 text-slate-500 font-bold px-2 py-0.5 rounded-md">
                                     功能: {s.featureName}
                                   </span>
                                   <span className="text-[9px] bg-indigo-50 text-indigo-600 font-bold px-2 py-0.5 rounded-md">
                                     执行者: {getActorName(s.actorId)}
                                   </span>
                                 </div>
                               </div>
                             </div>
                             
                             <p className="text-xs text-slate-600 leading-relaxed bg-slate-50 p-3 rounded-xl border border-slate-100 font-medium">
                               "{s.scenarioContent}"
                             </p>
                             
                             {/* Acceptance Criteria */}
                             <div className="space-y-2 mt-2">
                               <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">验收标准 (Acceptance Criteria)</div>
                               {(s.acceptanceCriteria || []).length === 0 ? (
                                 <div className="text-xs text-slate-400 italic bg-slate-50 p-2.5 rounded-lg border border-dashed border-slate-200/60">暂无具体验收标准。</div>
                               ) : (
                                 <div className="space-y-2">
                                   {(s.acceptanceCriteria || []).map((ac, idx) => (
                                     <div key={ac.criterionId || idx} className="flex items-start gap-2 text-xs text-slate-600 bg-emerald-50/20 p-2 rounded-lg border border-emerald-100/30">
                                       <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0 mt-1.5"></span>
                                       <span className="leading-normal">{ac.criterionContent}</span>
                                     </div>
                                   ))}
                                 </div>
                               )}
                             </div>
                           </div>
                         ))}
                       </div>
                     </>
                   );
                 })()}
               </section>
            </div>
          </div>
        </div>
      </div>
      
      <RightObjectPanel />
    </div>
  );
}
