import { useState, type MouseEvent } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { 
  useWorkspaceStore, 
  selectGoals, 
  selectTasks, 
  selectActors, 
} from '@/store/useWorkspaceStore';
import {
  buildGoalBranchItems,
  buildTaskFootprint,
  getChildCapabilities,
  getRootCapabilities,
  getTasksForCapability as selectTasksForCapability,
  selectPerformerTitle,
} from '@/domain/ir/selectors';

export function WhatToDo() {
  const { 
    setSelectedObject, highlightTarget, selectedObject, ir, createSlotFromIssue, expandSlot, openSlot
  } = useWorkspaceStore();
  
  const goals = useWorkspaceStore(selectGoals);
  const tasks = useWorkspaceStore(selectTasks);
  const actors = useWorkspaceStore(selectActors);

  const mainGoal = goals[0];
  const rootCapabilities = getRootCapabilities(ir as any) as any[];
  const branchItems = buildGoalBranchItems(ir);
  
  const [expandedCaps, setExpandedCaps] = useState<Record<string, boolean>>({});

  const toggleCap = (e: MouseEvent, id: string) => {
    e.stopPropagation();
    setExpandedCaps(prev => ({ ...prev, [id]: !prev[id] }));
  };

  // Helper to get connected tasks for a capability
  const getTasksForCapability = (capId: string) => {
    return selectTasksForCapability(ir as any, capId) as any;
  };

  const handleIssueBranch = async (issueId: string) => {
    const slotId = await createSlotFromIssue(issueId);
    if (slotId) await expandSlot(slotId);
  };

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
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1 mb-3">核心能力</h3>
                <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                  <div className="font-bold text-slate-800 mb-4 pb-2 border-b border-slate-100">{mainGoal?.title || '核心系统'}</div>
                  
                  <div className="space-y-4 pl-4 border-l-2 border-indigo-100 ml-2">
                    {rootCapabilities.map(cap => {
                      const children = getChildCapabilities(ir as any, cap.id) as any[];
                      const capTasks = getTasksForCapability(cap.id);
                      return (
                        <div key={cap.id} className="relative">
                          <div className="absolute w-4 h-px bg-indigo-100 -left-4 top-4"></div>
                          
                          <div 
                            onClick={() => setSelectedObject(cap)}
                            className={`rounded-xl p-4 cursor-pointer transition-colors mb-2 ${selectedObject?.id === cap.id ? 'bg-indigo-50 border-2 border-indigo-500' : 'bg-slate-50 border border-slate-200 hover:border-indigo-300'}`}
                          >
                            <div className="flex items-center justify-between mb-3 border-b border-slate-200/60 pb-2">
                              <div className="flex items-center gap-2">
                                {children.length > 0 && (
                                  <button onClick={(e) => toggleCap(e, cap.id)} className="p-0.5 hover:bg-slate-200 rounded text-slate-500 transition-colors">
                                    {expandedCaps[cap.id] !== false ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                                  </button>
                                )}
                                <span className="text-[10px] bg-slate-200 text-slate-600 font-bold px-1.5 rounded">{cap.priority || 'P1'}</span>
                                <h4 className="font-bold text-slate-800 text-sm">{cap.title}</h4>
                              </div>
                              <div className="flex items-center gap-2">
                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${cap.scopeStatus === 'in_scope' ? 'bg-emerald-100 text-emerald-700' : cap.scopeStatus === 'out_of_scope' ? 'bg-slate-200 text-slate-500' : 'bg-amber-100 text-amber-700'}`}>
                                  {cap.scopeStatus === 'in_scope' ? '本期包含' : cap.scopeStatus === 'out_of_scope' ? '已排除' : cap.scopeStatus === 'deferred' ? '暂缓' : '待确认范围'}
                                </span>
                                <StatusBadge status={cap.status} />
                              </div>
                            </div>
                            
                            <div className="space-y-1.5 text-[11px] text-slate-600 mb-3 ml-7">
                              <div className="flex"><span className="text-slate-400 w-16 shrink-0">服务目标</span><span className="font-medium text-slate-700">{cap.description?.split('。')[0] || '提升效率'}</span></div>
                              <div className="flex"><span className="text-slate-400 w-16 shrink-0">成功标准</span><span>{cap.description?.split('。')[1] || '无明确指标'}</span></div>
                            </div>
                            
                            <div className="flex flex-wrap gap-2 text-[10px] font-medium border-t border-slate-100 pt-2 ml-7">
                              {capTasks.length > 0 && <span className="bg-indigo-100/50 text-indigo-700 px-1.5 py-0.5 rounded border border-indigo-100">{capTasks.length} 个关键任务</span>}
                              <span className="bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded border border-blue-100">{Math.max(1, capTasks.length)} 涉及角色</span>
                              <span className="bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded border border-emerald-100">{capTasks.length * 2} 关联页面</span>
                              <span className="bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded border border-purple-100">{Math.max(1, capTasks.length)} 数据对象</span>
                              <span className="bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded border border-amber-100">0 开放Slot</span>
                            </div>
                          </div>
                          
                          {(children.length > 0 && expandedCaps[cap.id] !== false) && (
                            <div className="pl-6 space-y-2 mt-2 relative">
                              <div className="absolute w-px h-full bg-slate-100 left-3 top-0"></div>
                              {children.map(child => (
                                <div 
                                  key={child.id} 
                                  onClick={() => setSelectedObject(child)}
                                  className={`relative flex flex-col justify-center rounded-lg py-2.5 px-3 cursor-pointer group transition-colors ${selectedObject?.id === child.id ? 'bg-indigo-50 border-2 border-indigo-500 z-10' : 'bg-white border border-slate-100 hover:border-indigo-200'}`}
                                >
                                  <div className="absolute w-3 h-px bg-slate-100 -left-3 top-4"></div>
                                  <div className="flex items-center justify-between mb-1">
                                    <div className="flex items-center gap-2">
                                      <span className="text-[9px] bg-slate-100 text-slate-500 font-bold px-1 rounded">{child.priority || 'P1'}</span>
                                      <span className="text-xs font-bold text-slate-700 group-hover:text-indigo-700 transition-colors">{child.title}</span>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                      <span className={`text-[9px] font-bold px-1 py-0.5 rounded ${child.scopeStatus === 'in_scope' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                                        {child.scopeStatus === 'in_scope' ? '本期包含' : '待定'}
                                      </span>
                                      <StatusBadge status={child.status} className="scale-75 origin-right" />
                                    </div>
                                  </div>
                                  <div className="text-[10px] text-slate-500 line-clamp-1 ml-7">{child.description}</div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </section>

              <section>
                 <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1 mb-3">用例与任务映射</h3>
                 <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                   {tasks.map(t => {
                     const footprint = buildTaskFootprint(ir as any, t.id);
                     
                     return (
                     <div key={t.id} onClick={() => setSelectedObject(t)} className={`bg-white rounded-xl p-4 cursor-pointer transition-all flex flex-col ${selectedObject?.id === t.id ? 'ring-2 ring-indigo-500 border-transparent shadow-md' : 'border border-slate-200 hover:border-indigo-300 shadow-sm'} ${highlightTarget === t.id ? 'ring-2 ring-amber-400' : ''}`}>
                       <div className="flex justify-between items-start mb-2">
                         <h4 className="font-bold text-slate-800 text-sm tracking-wide">{t.title}</h4>
                         <StatusBadge status={t.status} className="scale-90 origin-right" />
                       </div>
                       <div className="space-y-1.5 text-xs mb-3 flex-1">
                         <div className="flex gap-2">
                           <span className="text-slate-400 w-12 text-[10px] uppercase font-bold mt-0.5">执行者</span>
                          <span className="font-bold text-slate-700 bg-slate-100 px-1 rounded text-[11px]">{selectPerformerTitle(ir as any, t.id) || '未指派'}</span>
                         </div>
                         <div className="flex gap-2 text-[11px]">
                           <span className="text-slate-400 w-12 text-[10px] uppercase font-bold shrink-0">期望结果</span>
                          <span className="text-slate-600 line-clamp-2">{t.outcome || '待补充'}</span>
                         </div>
                       </div>
                       
                       {/* Contextual footprint of the task */}
                       <div className="flex flex-col gap-1 border-t border-slate-100 pt-2 mt-auto">
                         <div className="flex items-center gap-1.5 text-[10px]">
                           <span className="w-12 text-slate-400 font-bold">实现链路:</span>
                           <span className="text-indigo-600 font-medium bg-indigo-50 px-1.5 rounded">{footprint.flowStepCount} 个流程步骤</span>
                         </div>
                         <div className="flex items-center gap-1.5 text-[10px]">
                           <span className="w-12 text-slate-400 font-bold">操作数据:</span>
                           <span className="text-blue-600 font-medium bg-blue-50 px-1.5 rounded">{footprint.objectCount} 个对象</span>
                         </div>
                         <div className="flex items-center gap-1.5 text-[10px]">
                           <span className="w-12 text-slate-400 font-bold">入口页面:</span>
                           <span className="text-emerald-600 font-medium bg-emerald-50 px-1.5 rounded">{footprint.screenCount} 个页面</span>
                         </div>
                       </div>
                     </div>
                   )})}
                 </div>
              </section>

              <section>
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1 mb-3">关键业务分岔</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {branchItems.length === 0 && (
                    <div className="bg-white rounded-2xl p-6 border border-dashed border-slate-200 text-xs text-slate-400 italic">
                      当前没有需要在“要做什么”阶段处理的关键分岔。
                    </div>
                  )}
                  {branchItems.map((item) => {
                    if (item.kind === 'issue') {
                      return (
                        <div key={item.issue.id} className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-rose-500">Issue</span>
                            <span className="text-[10px] text-slate-400">{item.projection}</span>
                          </div>
                          <h4 className="mt-2 text-sm font-bold text-slate-800">{item.issue.title}</h4>
                          <p className="mt-1 text-xs text-slate-500 line-clamp-2">{item.issue.description}</p>
                          <div className="mt-4 flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => void handleIssueBranch(item.issue.id)}
                              className="flex-1 rounded-lg bg-slate-900 px-3 py-2 text-xs font-bold text-white hover:bg-slate-800 transition-colors"
                            >
                              创建 Slot
                            </button>
                            <button
                              type="button"
                              onClick={() => setSelectedObject(item.issue)}
                              className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
                            >
                              查看
                            </button>
                          </div>
                        </div>
                      );
                    }

                    if (item.kind === 'slot') {
                      return (
                        <div key={item.slot.id} className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-amber-500">Slot</span>
                            <span className="text-[10px] text-slate-400">{item.slot.status}</span>
                          </div>
                          <h4 className="mt-2 text-sm font-bold text-slate-800">{item.slot.name}</h4>
                          <p className="mt-1 text-xs text-slate-500 line-clamp-2">{item.slot.description || '待系统展开为可选方案'}</p>
                          <div className="mt-4 flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => void expandSlot(item.slot.id)}
                              className="flex-1 rounded-lg bg-slate-900 px-3 py-2 text-xs font-bold text-white hover:bg-slate-800 transition-colors"
                            >
                              展开 Slot
                            </button>
                            <button
                              type="button"
                              onClick={() => openSlot(item.slot.id)}
                              className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
                            >
                              查看
                            </button>
                          </div>
                        </div>
                      );
                    }

                    return (
                      <div key={item.choiceGroup.id} className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-blue-500">ChoiceGroup</span>
                          <span className="text-[10px] text-slate-400">{item.choiceGroup.choices.length} 个 Choice</span>
                        </div>
                        <h4 className="mt-2 text-sm font-bold text-slate-800">
                          {ir?.slots[item.choiceGroup.slotId]?.name || item.choiceGroup.id}
                        </h4>
                        <p className="mt-1 text-xs text-slate-500 line-clamp-2">确认该分岔后，会同步更新目标、任务与后续流程细节。</p>
                        <div className="mt-4 flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => setSelectedObject(item.choiceGroup)}
                            className="flex-1 rounded-lg bg-slate-900 px-3 py-2 text-xs font-bold text-white hover:bg-slate-800 transition-colors"
                          >
                            打开 ChoiceGroup
                          </button>
                          <button
                            type="button"
                            onClick={() => openSlot(item.choiceGroup.slotId)}
                            className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
                          >
                            查看 Slot
                          </button>
                        </div>
                      </div>
                    );
                  })}
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
