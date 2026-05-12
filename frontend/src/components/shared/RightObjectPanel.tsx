import { useState, useRef, useEffect, type KeyboardEvent } from 'react';
import { ChevronLeft, ChevronRight, Edit2, Check, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { BaseNode, RequirementNode, Issue, ChoiceGroup, RequirementSlot, LinkType, NodeKindToText, SourceTypeToText } from '@/types';
import { StatusBadge } from './StatusBadge';
import { CandidateCard } from './CandidateCard';
import { 
  useWorkspaceStore, 
  selectGoals, 
  selectCapabilities, 
  selectTasks, 
  selectActors, 
  selectFlowSteps, 
  selectScopeItems, 
  selectIssues, 
  selectCandidates,
  selectSelectedObject
} from '@/store/useWorkspaceStore';
import { useLocation } from 'react-router-dom';

const LINK_LABELS: Record<string, { in: string; out: string }> = {
  realizes: { in: '承载了', out: '服务于 (实现)' },
  supports: { in: '来源于 (支撑)', out: '支撑了' },
  performed_by: { in: '执行了', out: '由...执行' },
  owns: { in: '归属于', out: '负责人' },
  precedes: { in: '后置于', out: '前置于' },
  branches_to: { in: '流转自', out: '流转至' },
  guards: { in: '受约束于', out: '作为约束' },
  reads: { in: '被读取', out: '查看/读取' },
  writes: { in: '被更新', out: '触发更新' },
  changes_state: { in: '状态被改变', out: '改变状态' },
  displayed_on: { in: '展示了', out: '显示于' },
  triggered_by: { in: '触发自', out: '由...触发' },
  depends_on: { in: '被依赖', out: '依赖于' },
  diagnoses: { in: '被诊断', out: '作为原因评估' }
};

export function RightObjectPanel() {
  const { 
    setSelectedObject, 
    generateCandidate, acceptCandidate, deferObject, excludeObject, ir, updateNodeAttributes,
    runDiagnosis, markNodeStatus, setNodeScope, createIssue, addChoiceToGroup
  } = useWorkspaceStore();
  
  const selectedObject: any = useWorkspaceStore(selectSelectedObject);
  const gaps = useWorkspaceStore(selectIssues);
  
  const goals = useWorkspaceStore(selectGoals);
  const capabilities = useWorkspaceStore(selectCapabilities);
  const tasks = useWorkspaceStore(selectTasks);
  const actors = useWorkspaceStore(selectActors);
  const flowSteps = useWorkspaceStore(selectFlowSteps);
  const scopeItems = useWorkspaceStore(selectScopeItems);
  
  const location = useLocation();

  const [width, setWidth] = useState(320);
  const [collapsed, setCollapsed] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const isResizingRef = useRef(false);
  
  const [editingTitle, setEditingTitle] = useState(false);
  const [editTitleValue, setEditTitleValue] = useState('');
  
  const [editingDesc, setEditingDesc] = useState(false);
  const [editDescValue, setEditDescValue] = useState('');

  // Update input values when selection changes
  useEffect(() => {
    if (selectedObject) {
      setEditTitleValue(selectedObject.title || selectedObject.name || '');
      setEditDescValue(selectedObject.description || '');
      setEditingTitle(false);
      setEditingDesc(false);
    }
  }, [selectedObject]);

  const handleSaveTitle = () => {
    if (editTitleValue.trim() && selectedObject?.id) {
      updateNodeAttributes(selectedObject.id, { 
        title: editTitleValue.trim(), 
        name: editTitleValue.trim() 
      });
    }
    setEditingTitle(false);
  };

  const handleSaveDesc = () => {
    if (selectedObject?.id) {
      updateNodeAttributes(selectedObject.id, { 
        description: editDescValue.trim() 
      });
    }
    setEditingDesc(false);
  };

  const handleKeyDown = (e: KeyboardEvent, saveAction: () => void, cancelAction: () => void) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      saveAction();
    } else if (e.key === 'Escape') {
      cancelAction();
    }
  };

  useEffect(() => {
    isResizingRef.current = isResizing;
    if (isResizing) {
       document.body.style.cursor = 'col-resize';
       document.body.style.userSelect = 'none';
    } else {
       document.body.style.cursor = '';
       document.body.style.userSelect = '';
    }
  }, [isResizing]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizingRef.current) return;
      const newWidth = document.body.clientWidth - e.clientX;
      if (newWidth > 200 && newWidth < 800) {
        setWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  if (!selectedObject) {
    let pendingItems: any[] = [];
    let highRiskGaps: any[] = [];
    let pageName = '';

    if (location.pathname === '/what') {
      pageName = '核心模型';
      const items = [...goals, ...capabilities, ...tasks, ...actors];
      pendingItems = items.filter(i => i.status === 'needs_confirmation' || i.status === 'ai_assumption');
      highRiskGaps = gaps.filter(g => g.severity === 'high' && g.relatedNodeIds.some(ao => items.some(i => i.id === ao)));
    } else if (location.pathname === '/flow') {
      pageName = '主干流程';
      pendingItems = flowSteps.filter(s => s.status === 'needs_confirmation' || s.status === 'ai_assumption');
      highRiskGaps = gaps.filter(g => g.severity === 'high' && g.relatedNodeIds.some(ao => flowSteps.some(i => i.id === ao)));
    } else if (location.pathname === '/scope') {
      pageName = '范围外与依赖';
      pendingItems = scopeItems.filter((s: any) => s.status === 'needs_confirmation' || s.status === 'ai_assumption');
      highRiskGaps = gaps.filter(g => g.severity === 'high' && g.relatedNodeIds.some(ao => scopeItems.some(i => i.id === ao)));
    } else {
      pageName = '工作台全局';
      const rawItems = [...goals, ...capabilities, ...tasks, ...actors, ...flowSteps, ...scopeItems];
      const items = Array.from(new Map(rawItems.map(i => [i.id, i])).values());
      pendingItems = items.filter(i => i.status === 'needs_confirmation' || i.status === 'ai_assumption');
      highRiskGaps = gaps.filter(g => g.severity === 'high');
    }

    return (
      <aside 
        className={cn("flex h-full flex-col bg-white border-l border-slate-200 shrink-0 shadow-sm relative", !isResizing && "transition-all duration-300")} 
        style={{ width: collapsed ? 0 : width }}
      >
        {!collapsed && (
          <div 
            className="absolute -left-1 top-0 bottom-0 w-2 cursor-col-resize z-50 group hover:bg-indigo-500/10"
            onMouseDown={() => setIsResizing(true)}
          >
            <div className="absolute left-0.5 top-0 bottom-0 w-[1px] bg-indigo-500 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        )}

        <button 
          onClick={() => setCollapsed(!collapsed)}
          className={cn("absolute top-1/2 -translate-y-1/2 bg-white border border-slate-200 rounded-full w-6 h-6 flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-300 shadow-sm hover:shadow z-20 transition-all", collapsed ? "-left-3" : "-left-3")}
        >
          {collapsed ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>

        <div className={cn("flex flex-col h-full overflow-hidden w-full", collapsed && "invisible")}>
          <div className="p-5 border-b border-slate-200 shrink-0">
            <h2 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-1 italic">当前处理面板</h2>
            <p className="font-bold text-lg text-slate-800">{pageName !== '工作台全局' ? `${pageName}页待处理项` : '全局待处理项'}</p>
          </div>
          
          <div className="flex-1 p-5 space-y-6 overflow-y-auto">
          {pendingItems.length > 0 ? (
            <section>
              <h3 className="text-[10px] font-bold text-slate-400 uppercase mb-3 px-1">待确认/需干预项 ({pendingItems.length})</h3>
              <div className="space-y-2 text-sm">
                {pendingItems.map(item => (
                  <div key={item.id} onClick={() => setSelectedObject(item)} className="bg-slate-50 p-3 rounded-xl border border-slate-200 flex justify-between items-center cursor-pointer hover:border-indigo-300 hover:bg-indigo-50/50 transition-colors">
                    <span className="text-xs font-medium text-slate-600 line-clamp-1 flex-1 mr-2">{item.title}</span>
                    <StatusBadge status={item.status} className="shrink-0" />
                  </div>
                ))}
              </div>
            </section>
          ) : (
            <section>
              <h3 className="text-[10px] font-bold text-slate-400 uppercase mb-3 px-1">当前无待确认项</h3>
            </section>
          )}

          {highRiskGaps.length > 0 && (
            <section>
              <h3 className="text-[10px] font-bold text-rose-400 uppercase tracking-widest mb-3 flex items-center gap-1 px-1">
                <div className="w-1.5 h-1.5 rounded-full bg-rose-500"></div>高优先级缺口 ({highRiskGaps.length})
              </h3>
              {highRiskGaps.map(gap => (
                <div key={gap.id} className="bg-rose-50/50 rounded-xl border border-rose-100 p-3 mb-2 cursor-pointer hover:bg-rose-50 hover:border-rose-200 transition" onClick={() => setSelectedObject(gap)}>
                  <p className="font-bold text-rose-800 text-sm mb-1 line-clamp-1">{gap.title}</p>
                  <p className="text-[10px] text-rose-600/80 line-clamp-2">{gap.description}</p>
                </div>
              ))}
            </section>
          )}
        </div>

          <div className="p-5 border-t border-slate-200 grid grid-cols-1 gap-2 mt-auto shrink-0 bg-slate-50/50">
            <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">建议下一步操作</p>
            <button onClick={() => pendingItems[0] && setSelectedObject(pendingItems[0])} className="py-2 bg-slate-900 text-white rounded-lg text-xs font-bold w-full hover:bg-slate-800 transition shadow-sm">选择一个待处理项</button>
            <button onClick={() => runDiagnosis({ page: location.pathname })} className="py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold w-full hover:bg-slate-50 transition shadow-sm bg-white">检查当前页面</button>
            <button onClick={() => runDiagnosis({ trigger: 'next_step' })} className="py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold w-full hover:bg-slate-50 transition shadow-sm bg-white">生成下一步建议</button>
          </div>
        </div>
      </aside>
    );
  }

  const isNode = ir?.nodes?.[selectedObject.id] !== undefined;
  const isIssue = selectedObject.severity !== undefined;
  const isChoiceGroup = selectedObject.choices !== undefined;
  const isSlot = selectedObject.arity !== undefined;

  let incomingLinks: any[] = [];
  let outgoingLinks: any[] = [];
  let relatedIssues: any[] = [];
  let openSlots: any[] = [];
  let nodeChoices: any[] = [];

  if (ir) {
    if (isNode) {
      incomingLinks = ir.links.filter(l => l.targetId === selectedObject.id);
      outgoingLinks = ir.links.filter(l => l.sourceId === selectedObject.id);
      relatedIssues = Object.values(ir.issues).filter(i => i.relatedNodeIds.includes(selectedObject.id));
      openSlots = Object.values(ir.slots).filter(s => s.ownerNodeId === selectedObject.id);
      nodeChoices = Object.values(ir.choiceGroups).filter(cg => openSlots.some(s => s.id === cg.slotId));
    } else if (isIssue) {
      relatedIssues = [selectedObject];
    } else if (isChoiceGroup) {
      nodeChoices = [selectedObject];
    } else if (isSlot) {
      openSlots = [selectedObject];
      if (selectedObject.choiceGroupId) {
        nodeChoices = ir.choiceGroups[selectedObject.choiceGroupId] ? [ir.choiceGroups[selectedObject.choiceGroupId]] : [];
      }
    }
  }

  // Helper to determine bottom actions based on object type
  const renderBottomActions = () => {
    if (isChoiceGroup || isSlot) {
      return (
        <>
          <button
            onClick={() => {
              const choiceGroupId = isChoiceGroup
                ? selectedObject.id
                : selectedObject.choiceGroupId || (ir?.slots?.[selectedObject.id]?.choiceGroupId ?? null);
              if (!choiceGroupId) return;
              addChoiceToGroup(choiceGroupId, { title: '新增候选方案', rationale: '' });
            }}
            className="col-span-2 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white"
          >
            补充新方案
          </button>
        </>
      );
    }

    if (isIssue) {
      return (
        <>
          <button onClick={() => generateCandidate(selectedObject.id)} className="col-span-2 py-2 bg-slate-900 text-white rounded-lg text-xs font-bold w-full hover:bg-slate-800 transition shadow-sm">针对缺口生成方案</button>
          <button onClick={() => deferObject(selectedObject.id)} className="col-span-2 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">暂缓处理</button>
        </>
      );
    }

    if (selectedObject.kind === 'flow_step') {
      return (
        <>
          <button onClick={() => generateCandidate(selectedObject.id)} className="col-span-2 py-2 bg-slate-900 text-white rounded-lg text-xs font-bold w-full hover:bg-slate-800 transition shadow-sm">展开异常分支</button>
          <button onClick={() => createIssue({ title: `补充规则：${selectedObject.title}`, description: '为该流程步骤补充明确的业务规则。', severity: 'medium', category: 'rule_gap', relatedNodeIds: [selectedObject.id], suggestedProjection: 'system', suggestedAction: '补充业务规则' })} className="col-span-1 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">补充规则</button>
          <button onClick={() => createIssue({ title: `绑定业务对象：${selectedObject.title}`, description: '为该步骤补充读写的业务对象定义与字段。', severity: 'medium', category: 'data_gap', relatedNodeIds: [selectedObject.id], suggestedProjection: 'data', suggestedAction: '绑定业务对象' })} className="col-span-1 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">绑定业务对象</button>
          <button onClick={() => createIssue({ title: `生成 UI 入口：${selectedObject.title}`, description: '为该步骤补充界面入口或交互组件。', severity: 'medium', category: 'ui_gap', relatedNodeIds: [selectedObject.id], suggestedProjection: 'ui', suggestedAction: '生成 UI 入口' })} className="col-span-1 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">生成 UI 入口</button>
          <button onClick={() => markNodeStatus(selectedObject.id, 'needs_confirmation')} className="col-span-1 py-2 border border-amber-200 text-amber-600 rounded-lg text-xs font-bold hover:bg-amber-50 transition shadow-sm bg-white">标记待确认</button>
          <button onClick={() => deferObject(selectedObject.id)} className="col-span-2 py-2 border border-rose-100 text-rose-500 rounded-lg text-xs font-bold hover:bg-rose-50 transition shadow-sm bg-white">移出本期</button>
        </>
      );
    }

    if (selectedObject.kind === 'business_object') {
      return (
        <>
          <button onClick={() => createIssue({ title: `补充字段：${selectedObject.title}`, description: '为业务对象补充字段列表与含义。', severity: 'medium', category: 'data_gap', relatedNodeIds: [selectedObject.id], suggestedProjection: 'data', suggestedAction: '补充字段' })} className="col-span-1 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">补充字段</button>
          <button onClick={() => createIssue({ title: `生成状态机：${selectedObject.title}`, description: '为业务对象补充状态、流转与触发条件。', severity: 'medium', category: 'data_gap', relatedNodeIds: [selectedObject.id], suggestedProjection: 'data', suggestedAction: '生成状态机' })} className="col-span-1 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">生成状态机</button>
          <button onClick={() => createIssue({ title: `检查流程读写：${selectedObject.title}`, description: '检查流程步骤对该对象的 reads/writes/changing_state 链路。', severity: 'low', category: 'rule_gap', relatedNodeIds: [selectedObject.id], suggestedProjection: 'system', suggestedAction: '检查读写链路' })} className="col-span-1 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">检查流程读写</button>
          <button onClick={() => createIssue({ title: `生成关联页面：${selectedObject.title}`, description: '为业务对象补充关键页面/视图与交互入口。', severity: 'medium', category: 'ui_gap', relatedNodeIds: [selectedObject.id], suggestedProjection: 'ui', suggestedAction: '生成关联页面' })} className="col-span-1 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">生成关联页面</button>
        </>
      );
    }

    if (selectedObject.kind === 'ui_component') {
      return (
        <>
          <button onClick={() => createIssue({ title: `绑定字段：${selectedObject.title}`, description: '将组件与业务字段建立绑定关系。', severity: 'low', category: 'ui_gap', relatedNodeIds: [selectedObject.id], suggestedProjection: 'ui', suggestedAction: '绑定字段' })} className="col-span-1 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">绑定字段</button>
          <button onClick={() => createIssue({ title: `绑定动作：${selectedObject.title}`, description: '将组件与可执行动作/流程步骤建立绑定关系。', severity: 'low', category: 'ui_gap', relatedNodeIds: [selectedObject.id], suggestedProjection: 'ui', suggestedAction: '绑定动作' })} className="col-span-1 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">绑定动作</button>
          <button onClick={() => createIssue({ title: `生成替代组件：${selectedObject.title}`, description: '为该组件生成替代方案并放入候选决策。', severity: 'low', category: 'ui_gap', relatedNodeIds: [selectedObject.id], suggestedProjection: 'ui', suggestedAction: '生成替代组件' })} className="col-span-1 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">生成替代组件</button>
          <button onClick={() => createIssue({ title: `检查可达性：${selectedObject.title}`, description: '检查该组件在角色视角下是否可达、是否缺少入口。', severity: 'low', category: 'ui_gap', relatedNodeIds: [selectedObject.id], suggestedProjection: 'ui', suggestedAction: '检查可达性' })} className="col-span-1 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">检查可达性</button>
        </>
      );
    }

    if (selectedObject.scopeStatus) {
      return (
        <>
           <button onClick={() => setNodeScope(selectedObject.id, 'in_scope')} className="col-span-2 py-2 bg-indigo-600 text-white rounded-lg text-xs font-bold w-full hover:bg-indigo-700 transition shadow-sm">移入本期</button>
           <button onClick={() => deferObject(selectedObject.id)} className="col-span-2 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">暂缓</button>
           <button onClick={() => setNodeScope(selectedObject.id, 'dependency')} className="col-span-1 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">外部依赖</button>
           <button onClick={() => excludeObject(selectedObject.id)} className="col-span-1 py-2 border border-rose-100 text-rose-500 rounded-lg text-xs font-bold hover:bg-rose-50 transition shadow-sm bg-white">排除</button>
        </>
      );
    }

    return (
      <>
        <button onClick={() => setEditingDesc(true)} className="col-span-1 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">编辑</button>
        <button onClick={() => markNodeStatus(selectedObject.id, 'needs_confirmation')} className="col-span-1 py-2 border border-amber-200 text-amber-600 rounded-lg text-xs font-bold hover:bg-amber-50 transition shadow-sm bg-white">标记待确认</button>
      </>
    );
  };

  return (
      <aside 
        className={cn("flex h-full flex-col bg-white border-l border-slate-200 shrink-0 shadow-sm relative", !isResizing && "transition-all duration-300")} 
        style={{ width: collapsed ? 0 : width }}
      >
        {!collapsed && (
          <div 
            className="absolute -left-1 top-0 bottom-0 w-2 cursor-col-resize z-50 group hover:bg-indigo-500/10"
            onMouseDown={() => setIsResizing(true)}
          >
            <div className="absolute left-0.5 top-0 bottom-0 w-[1px] bg-indigo-500 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        )}

        <button 
          onClick={() => setCollapsed(!collapsed)}
          className={cn("absolute top-1/2 -translate-y-1/2 bg-white border border-slate-200 rounded-full w-6 h-6 flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-300 shadow-sm hover:shadow z-20 transition-all", collapsed ? "-left-3" : "-left-3")}
        >
          {collapsed ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>

        <div className={cn("flex flex-col h-full overflow-y-auto w-full", collapsed && "invisible")}>
      <div className="p-5 border-b border-slate-200 relative shrink-0">
        <button onClick={() => setSelectedObject(null)} className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 bg-slate-50 hover:bg-slate-100 rounded-full w-6 h-6 flex items-center justify-center font-bold transition-colors">
          &times;
        </button>
        <h2 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-4 italic">节点检查器 (IR)</h2>
        <div className="flex items-center gap-2 mb-2 pr-6">
          <div className="w-3 h-3 rounded-full bg-indigo-500 shrink-0"></div>
          {editingTitle ? (
            <div className="flex items-center gap-1 w-full bg-slate-50 border border-indigo-300 rounded p-1">
              <input 
                type="text" 
                value={editTitleValue}
                onChange={e => setEditTitleValue(e.target.value)}
                onKeyDown={e => handleKeyDown(e, handleSaveTitle, () => setEditingTitle(false))}
                className="font-bold text-lg text-slate-800 leading-tight bg-transparent border-none outline-none flex-1 w-full"
                autoFocus
                placeholder="节点名称..."
              />
              <button 
                onClick={handleSaveTitle}
                className="p-1 text-green-600 hover:bg-green-100 rounded transition-colors"
                title="保存 (Enter)"
              ><Check className="w-4 h-4" /></button>
              <button 
                onClick={() => setEditingTitle(false)}
                className="p-1 text-slate-500 hover:bg-slate-200 rounded transition-colors"
                title="取消 (Esc)"
              ><X className="w-4 h-4" /></button>
            </div>
          ) : (
            <div className="group flex items-center gap-2 max-w-full">
              <span className="font-bold text-lg text-slate-800 leading-tight">
                {selectedObject.title || selectedObject.name || '未命名节点'}
              </span>
              <button 
                onClick={() => setEditingTitle(true)}
                className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-all shrink-0"
              >
                <Edit2 className="w-3 h-3" />
              </button>
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isChoiceGroup ? (
            <span className="px-2 py-0.5 bg-purple-100 text-purple-700 text-[10px] font-bold rounded uppercase tracking-wider">Candidate Group</span>
          ) : isSlot ? (
            <span className="px-2 py-0.5 bg-purple-100 text-purple-700 text-[10px] font-bold rounded uppercase tracking-wider">Slot (未决策)</span>
          ) : isIssue ? (
            <span className="px-2 py-0.5 bg-rose-100 text-rose-700 text-[10px] font-bold rounded uppercase tracking-wider">Issue</span>
          ) : (
            <span className="px-2 py-0.5 bg-slate-100 text-slate-600 text-[10px] font-bold rounded uppercase tracking-wider">
              {NodeKindToText[selectedObject.kind] || selectedObject.kind}
            </span>
          )}
          <StatusBadge status={selectedObject.status} />
        </div>
      </div>

      <div className="flex-1 overflow-auto p-5 space-y-6">
        {/* 基础信息 */}
        {selectedObject.description !== undefined && (
          <section>
            <div className="flex items-center justify-between mb-2 group">
               <h3 className="text-[10px] font-bold text-slate-400 uppercase">基础信息</h3>
               {!editingDesc && (
                 <button 
                   onClick={() => setEditingDesc(true)}
                   className="opacity-0 group-hover:opacity-100 text-[9px] flex items-center gap-1 text-indigo-500 hover:bg-indigo-50 px-1.5 py-0.5 rounded transition-all"
                 >
                   <Edit2 className="w-2.5 h-2.5" /> 编辑
                 </button>
               )}
            </div>
            
            {editingDesc ? (
               <div className="bg-slate-50 border border-indigo-300 rounded p-1">
                 <textarea
                   value={editDescValue}
                   onChange={e => setEditDescValue(e.target.value)}
                   onKeyDown={e => handleKeyDown(e, handleSaveDesc, () => setEditingDesc(false))}
                   className="text-xs text-slate-700 leading-relaxed bg-transparent border-none outline-none w-full min-h-[80px] resize-y p-1"
                   autoFocus
                   placeholder="添加描述..."
                 />
                 <div className="flex justify-end gap-1 mt-1 border-t border-slate-200 pt-1">
                   <button 
                     onClick={() => setEditingDesc(false)}
                     className="text-[10px] px-2 py-1 text-slate-500 hover:bg-slate-200 rounded font-medium transition-colors"
                   >
                     取消
                   </button>
                   <button 
                     onClick={handleSaveDesc}
                     className="text-[10px] px-2 py-1 text-white bg-indigo-500 hover:bg-indigo-600 rounded font-medium transition-colors"
                   >
                     保存
                   </button>
                 </div>
               </div>
            ) : (
               <p 
                 onClick={() => setEditingDesc(true)}
                 className={cn(
                   "text-xs leading-relaxed bg-slate-50 p-2 rounded border border-slate-100 cursor-text hover:border-indigo-200 hover:bg-indigo-50/30 transition-colors",
                   !selectedObject.description ? "text-slate-400 italic" : "text-slate-700"
                 )}
               >
                 {selectedObject.description || '暂无描述信息，点击添加...'}
               </p>
            )}
          </section>
        )}

        {/* 状态与置信度 */}
        <section>
          <h3 className="text-[10px] font-bold text-slate-400 uppercase mb-3">状态与置信度</h3>
          <div className="space-y-2 text-xs text-slate-600">
            <div className="flex justify-between items-center"><span className="text-slate-400">状态</span><StatusBadge status={selectedObject.status} /></div>
            <div className="flex justify-between items-center"><span className="text-slate-400">置信度</span><span className="font-medium">{selectedObject.confidence != null ? selectedObject.confidence : 'N/A'}</span></div>
            <div className="flex justify-between items-center"><span className="text-slate-400">来源</span><span className="font-medium bg-slate-100 px-1.5 rounded">{SourceTypeToText[selectedObject.source?.type || ''] || selectedObject.source?.type || '未知'}</span></div>
            <div className="flex justify-between items-start mt-1">
              <span className="text-slate-400 w-16 shrink-0 text-left">溯源</span>
              <span className="text-[10px] bg-slate-50 p-1.5 rounded text-slate-500 border border-slate-100 text-right">{selectedObject.source?.text || '系统初始化生成'}</span>
            </div>
          </div>
        </section>

        {/* Slot 与候选 */}
        {(openSlots.length > 0 || nodeChoices.length > 0) && (
          <section>
            <h3 className="text-[10px] font-bold text-slate-400 uppercase mb-3">Slot 与候选</h3>
            <div className="space-y-4">
              {openSlots.map(slot => (
                <div key={slot.id} className="text-xs">
                  <div className="flex justify-between font-medium text-slate-700 mb-1">
                     <span>{slot.name} (Slot)</span>
                     <span className="text-[10px] bg-purple-50 text-purple-600 px-1 rounded">
                       {slot.status === 'empty' ? '空缺' : slot.status === 'expanding' ? '展开中' : slot.status === 'filled' ? '已填充' : slot.status === 'deferred' ? '暂缓' : slot.status}
                     </span>
                  </div>
                  {slot.description && <p className="text-[10px] text-slate-500 mb-2">{slot.description}</p>}
                </div>
              ))}

              {nodeChoices.map(cg => (
                <div key={cg.id} className="space-y-2 border-t border-slate-100 pt-2">
                  <div className="text-xs font-bold text-slate-600 mb-2">可选项 ({cg.choices.length}) :</div>
                  {cg.choices.map((c: any) => (
                    <CandidateCard 
                      key={c.id} 
                      candidate={c}
                      onAccept={() => acceptCandidate(c.id)}
                      onRewrite={() => {}}
                      onReject={() => excludeObject(c.id)}
                    />
                  ))}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* 跨视角链接 */}
        {(!isIssue && !isChoiceGroup && !isSlot && (incomingLinks.length > 0 || outgoingLinks.length > 0)) && (
          <section>
            <h3 className="text-[10px] font-bold text-slate-400 uppercase mb-3">跨视角链接</h3>
            <div className="space-y-2">
              {outgoingLinks.map(l => {
                const target = ir?.nodes[l.targetId];
                if (!target) return null;
                return (
                  <div key={l.id} className="flex flex-col gap-0.5 text-xs border border-slate-100 rounded p-2 bg-slate-50">
                    <span className="text-slate-400 font-bold text-[10px]">{LINK_LABELS[l.type]?.out || l.type}</span>
                    <div className="flex items-center gap-1.5 cursor-pointer text-indigo-600 hover:text-indigo-800 transition-colors" onClick={() => setSelectedObject(target)}>
                      <div className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                      <span className="font-medium">{target.title}</span>
                      <span className="text-[9px] text-slate-400 ml-auto border border-slate-200 px-1 rounded">{NodeKindToText[target.kind] || target.kind}</span>
                    </div>
                  </div>
                );
              })}
              
              {incomingLinks.map(l => {
                const source = ir?.nodes[l.sourceId];
                if (!source) return null;
                return (
                  <div key={l.id} className="flex flex-col gap-0.5 text-xs border border-slate-100 rounded p-2 bg-slate-50">
                    <span className="text-slate-400 font-bold text-[10px]">{LINK_LABELS[l.type]?.in || l.type}</span>
                    <div className="flex items-center gap-1.5 cursor-pointer text-indigo-600 hover:text-indigo-800 transition-colors" onClick={() => setSelectedObject(source)}>
                      <div className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                      <span className="font-medium">{source.title}</span>
                      <span className="text-[9px] text-slate-400 ml-auto border border-slate-200 px-1 rounded">{NodeKindToText[source.kind] || source.kind}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Issue 与影响 */}
        {relatedIssues.length > 0 && (
          <section className="bg-rose-50/50 p-3 rounded-xl border border-rose-100">
            <h3 className="text-[10px] font-bold text-rose-600 uppercase mb-2">关联 Issue ({relatedIssues.length})</h3>
            <div className="space-y-2">
              {relatedIssues.map(issue => (
                <div key={issue.id} className="text-xs text-rose-800 p-2 bg-white rounded border border-rose-100 cursor-pointer shadow-sm hover:border-rose-300" onClick={() => setSelectedObject(issue)}>
                  <div className="font-bold flex justify-between">
                    <span>{issue.title}</span>
                    <span className="px-1 text-[9px] bg-rose-100 text-rose-600 rounded">{issue.severity}</span>
                  </div>
                  <p className="mt-1 opacity-80">{issue.description}</p>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>

      <div className="p-5 border-t border-slate-200 grid grid-cols-2 gap-2 mt-auto shrink-0 bg-slate-50/50">
        {renderBottomActions()}
      </div>
     </div>
    </aside>
  );
}

