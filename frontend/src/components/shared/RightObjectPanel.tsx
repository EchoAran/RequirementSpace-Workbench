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
    runDiagnosis, markNodeStatus, setNodeScope, createIssue, addChoiceToGroup, applyPatch, updateIssueAttributes, updateChoiceAttributes
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

  const [editingStructured, setEditingStructured] = useState(true);
  const [structuredDraft, setStructuredDraft] = useState<Record<string, any>>({});

  const [editingIssueDetails, setEditingIssueDetails] = useState(true);
  const [issueDraft, setIssueDraft] = useState<Record<string, any>>({});

  const [choiceDraft, setChoiceDraft] = useState<Record<string, any>>({});
  const [showFlowStepActions, setShowFlowStepActions] = useState(false);

  const allNodes = Object.values(ir?.nodes || {}) as any[];
  const nodesByKind = (kind: string) => allNodes.filter((n) => n.kind === kind);

  const buildStructuredDraft = (obj: any) => {
    if (!obj) return {};
    if (obj.arity !== undefined) {
      return {
        name: obj.name || obj.title || '',
        description: obj.description || '',
        expectedKinds: obj.expectedKinds || [],
        arity: obj.arity || 'many',
        status: obj.status || 'empty',
        choiceGroupId: obj.choiceGroupId || null,
        context: obj.context || { projectionHints: [], relatedNodeIds: [] },
      };
    }
    if (obj.kind) {
      const kind = obj.kind as string;
      if (kind === 'goal') return { successCriteria: obj.successCriteria || [] };
      if (kind === 'capability') return { priority: obj.priority || '', parentId: obj.parentId || '', acceptanceNotes: obj.acceptanceNotes || [] };
      if (kind === 'actor') return { roleType: obj.roleType || 'primary_user', responsibilities: obj.responsibilities || [], permissions: obj.permissions || [] };
      if (kind === 'task') return { actorId: obj.actorId || '', capabilityId: obj.capabilityId || '', owner: obj.owner || '', outcome: obj.outcome || '', result: obj.result || '' };
      if (kind === 'flow') return { trigger: obj.trigger || '', mainObjectId: obj.mainObjectId || '' };
      if (kind === 'flow_step') {
        return {
          flowId: obj.flowId || '',
          actorId: obj.actorId || '',
          inputObjectIds: obj.inputObjectIds || [],
          outputObjectIds: obj.outputObjectIds || [],
          ruleIds: obj.ruleIds || [],
        };
      }
      if (kind === 'rule') return { ruleType: obj.ruleType || 'condition', expression: obj.expression || '', naturalLanguage: obj.naturalLanguage || '' };
      if (kind === 'business_object') return { ownerActorId: obj.ownerActorId || '', fieldIds: obj.fieldIds || [], stateMachineId: obj.stateMachineId || '' };
      if (kind === 'field') return { objectId: obj.objectId || '', fieldType: obj.fieldType || 'text', required: obj.required ?? false, valueSource: obj.valueSource || 'user_input' };
      if (kind === 'state_machine') return { objectId: obj.objectId || '', stateIds: obj.stateIds || [], transitionIds: obj.transitionIds || [] };
      if (kind === 'object_state') return { objectId: obj.objectId || '' };
      if (kind === 'state_transition') return { fromStateId: obj.fromStateId || '', toStateId: obj.toStateId || '', triggerStepId: obj.triggerStepId || '', ruleIds: obj.ruleIds || [] };
      if (kind === 'screen') return { actorIds: obj.actorIds || [], purpose: obj.purpose || '', route: obj.route || '', rootComponentId: obj.rootComponentId || '' };
      if (kind === 'ui_component') return { componentType: obj.componentType || 'button', childIds: obj.childIds || [], dataBindingIds: obj.dataBindingIds || [], actionBindingIds: obj.actionBindingIds || [] };
    }
    return {};
  };

  const buildIssueDraft = (obj: any) => {
    if (!obj || obj.severity === undefined) return {};
    return {
      title: obj.title || '',
      description: obj.description || '',
      severity: obj.severity || 'medium',
      category: obj.category || 'missing',
      relatedNodeIds: obj.relatedNodeIds || [],
      suggestedProjection: obj.suggestedProjection || 'goal',
      suggestedAction: obj.suggestedAction || '',
      status: obj.status || 'open',
    };
  };

  const buildChoiceDraft = (obj: any) => {
    if (!obj || obj.rationale === undefined || obj.proposedNodeIds === undefined) return {};
    return {
      title: obj.title || '',
      rationale: obj.rationale || '',
      status: obj.status || 'candidate',
    };
  };

  // Update input values when selection changes
  useEffect(() => {
    if (selectedObject) {
      setEditTitleValue(selectedObject.title || selectedObject.name || '');
      setEditDescValue(selectedObject.description || '');
      setEditingTitle(false);
      setEditingDesc(false);
      setEditingStructured(true);
      setEditingIssueDetails(true);
      setStructuredDraft(buildStructuredDraft(selectedObject));
      setIssueDraft(buildIssueDraft(selectedObject));
      setChoiceDraft(buildChoiceDraft(selectedObject));
      setShowFlowStepActions(false);
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
          className={cn(
            "bg-white border border-slate-200 rounded-full w-6 h-6 flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-300 shadow-sm hover:shadow z-20 transition-all",
            collapsed
              ? "fixed right-3 top-[calc(50vh+2rem)] -translate-y-1/2"
              : "absolute -left-3 top-1/2 -translate-y-1/2"
          )}
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
  const isChoice = selectedObject.rationale !== undefined && selectedObject.proposedNodeIds !== undefined;

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
    } else if (isChoice) {
      nodeChoices = Object.values(ir.choiceGroups).filter((cg: any) => (cg.choices || []).some((c: any) => c.id === selectedObject.id));
    } else if (isChoiceGroup) {
      nodeChoices = [selectedObject];
    } else if (isSlot) {
      openSlots = [selectedObject];
      if (selectedObject.choiceGroupId) {
        nodeChoices = ir.choiceGroups[selectedObject.choiceGroupId] ? [ir.choiceGroups[selectedObject.choiceGroupId]] : [];
      }
    }
  }

  const commitStructuredPartial = async (partial: Record<string, any>) => {
    if (!selectedObject?.id) return;
    if (isSlot) {
      await applyPatch({ updateSlots: [{ id: selectedObject.id, ...partial }] } as any);
      return;
    }
    await updateNodeAttributes(selectedObject.id, partial);
  };

  const updateStructuredField = (key: string, value: any) => {
    setStructuredDraft((prev) => ({ ...prev, [key]: value }));
  };

  const addStructuredListItem = (key: string, value: string) => {
    if (!value) return;
    setStructuredDraft((prev) => {
      const current = Array.isArray(prev[key]) ? (prev[key] as string[]) : [];
      const next = Array.from(new Set([...current, value]));
      void commitStructuredPartial({ [key]: next });
      return { ...prev, [key]: next };
    });
  };

  const removeStructuredListItem = (key: string, value: string) => {
    setStructuredDraft((prev) => {
      const current = Array.isArray(prev[key]) ? (prev[key] as string[]) : [];
      const next = current.filter((x) => x !== value);
      void commitStructuredPartial({ [key]: next });
      return { ...prev, [key]: next };
    });
  };

  const commitStructuredField = async (key: string, value: any) => {
    await commitStructuredPartial({ [key]: value });
  };

  const updateIssueField = (key: string, value: any) => {
    setIssueDraft((prev) => ({ ...prev, [key]: value }));
  };

  const addIssueRelatedNode = (id: string) => {
    if (!id) return;
    setIssueDraft((prev) => {
      const current = Array.isArray(prev.relatedNodeIds) ? (prev.relatedNodeIds as string[]) : [];
      const next = Array.from(new Set([...current, id]));
      void updateIssueAttributes(selectedObject.id, { relatedNodeIds: next } as any);
      return { ...prev, relatedNodeIds: next };
    });
  };

  const removeIssueRelatedNode = (id: string) => {
    setIssueDraft((prev) => {
      const current = Array.isArray(prev.relatedNodeIds) ? (prev.relatedNodeIds as string[]) : [];
      const next = current.filter((x) => x !== id);
      void updateIssueAttributes(selectedObject.id, { relatedNodeIds: next } as any);
      return { ...prev, relatedNodeIds: next };
    });
  };

  const commitIssueField = async (key: string, value: any) => {
    if (!selectedObject?.id) return;
    await updateIssueAttributes(selectedObject.id, { [key]: value } as any);
  };

  const updateChoiceField = (key: string, value: any) => {
    setChoiceDraft((prev) => ({ ...prev, [key]: value }));
  };

  const commitChoiceField = async (key: string, value: any) => {
    if (!selectedObject?.id) return;
    await updateChoiceAttributes(selectedObject.id, { [key]: value } as any);
  };

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

    if (selectedObject.scopeStatus) {
      return (
        <>
           <button onClick={() => setNodeScope(selectedObject.id, 'in_scope')} className="col-span-2 py-2 bg-indigo-600 text-white rounded-lg text-xs font-bold w-full hover:bg-indigo-700 transition shadow-sm">移入本期</button>
           <button onClick={() => setNodeScope(selectedObject.id, 'deferred')} className="col-span-2 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">本期暂不处理</button>
           <button onClick={() => setNodeScope(selectedObject.id, 'external_dependency')} className="col-span-1 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">外部依赖</button>
           <button onClick={() => setNodeScope(selectedObject.id, 'excluded')} className="col-span-1 py-2 border border-rose-100 text-rose-500 rounded-lg text-xs font-bold hover:bg-rose-50 transition shadow-sm bg-white">排除</button>
        </>
      );
    }

    if (selectedObject.kind === 'flow_step') {
      return (
        <>
          <button onClick={() => generateCandidate(selectedObject.id)} className="col-span-2 py-2 bg-slate-900 text-white rounded-lg text-xs font-bold w-full hover:bg-slate-800 transition shadow-sm">展开异常分支</button>
          <button onClick={() => setShowFlowStepActions(true)} className="col-span-2 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition shadow-sm bg-white">更多动作</button>

          {showFlowStepActions && (
            <>
              <div className="fixed inset-0 z-[55]" onClick={() => setShowFlowStepActions(false)} />
              <div className="absolute left-4 right-4 bottom-full mb-3 z-[56] bg-white border border-slate-200 rounded-2xl shadow-lg p-2">
                <button
                  onClick={() => {
                    setShowFlowStepActions(false);
                    createIssue({ title: `补充规则：${selectedObject.title}`, description: '为该流程步骤补充明确的业务规则。', severity: 'medium', category: 'rule_gap', relatedNodeIds: [selectedObject.id], suggestedProjection: 'system', suggestedAction: '补充业务规则' });
                  }}
                  className="w-full text-left px-3 py-2 rounded-xl hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center justify-between text-sm font-bold text-slate-800">
                    <span>补充规则</span>
                    <span className="text-[10px] text-slate-400 font-bold">创建缺口</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">为该步骤补齐判断条件、校验、权限等规则</div>
                </button>

                <button
                  onClick={() => {
                    setShowFlowStepActions(false);
                    createIssue({ title: `绑定业务对象：${selectedObject.title}`, description: '为该步骤补充读写的业务对象定义与字段。', severity: 'medium', category: 'data_gap', relatedNodeIds: [selectedObject.id], suggestedProjection: 'data', suggestedAction: '绑定业务对象' });
                  }}
                  className="w-full text-left px-3 py-2 rounded-xl hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center justify-between text-sm font-bold text-slate-800">
                    <span>绑定业务对象</span>
                    <span className="text-[10px] text-slate-400 font-bold">创建缺口</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">补齐该步骤的输入/输出对象与字段</div>
                </button>

                <button
                  onClick={() => {
                    setShowFlowStepActions(false);
                    createIssue({ title: `生成 UI 入口：${selectedObject.title}`, description: '为该步骤补充界面入口或交互组件。', severity: 'medium', category: 'ui_gap', relatedNodeIds: [selectedObject.id], suggestedProjection: 'ui', suggestedAction: '生成 UI 入口' });
                  }}
                  className="w-full text-left px-3 py-2 rounded-xl hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center justify-between text-sm font-bold text-slate-800">
                    <span>生成 UI 入口</span>
                    <span className="text-[10px] text-slate-400 font-bold">创建缺口</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">补齐界面入口、组件绑定与跳转</div>
                </button>

                <div className="h-px bg-slate-100 my-1" />

                <button
                  onClick={() => {
                    setShowFlowStepActions(false);
                    markNodeStatus(selectedObject.id, 'needs_confirmation');
                  }}
                  className="w-full text-left px-3 py-2 rounded-xl hover:bg-amber-50 transition-colors"
                >
                  <div className="flex items-center justify-between text-sm font-bold text-slate-800">
                    <span>标记待确认</span>
                    <span className="text-[10px] text-amber-600 font-bold">节点状态</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">提示该步骤仍需人工确认或补充</div>
                </button>
              </div>
            </>
          )}
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

    return (
      <>
        <button onClick={() => markNodeStatus(selectedObject.id, 'needs_confirmation')} className="col-span-2 py-2 border border-amber-200 text-amber-600 rounded-lg text-xs font-bold hover:bg-amber-50 transition shadow-sm bg-white">标记待确认</button>
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
          className={cn(
            "bg-white border border-slate-200 rounded-full w-6 h-6 flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-300 shadow-sm hover:shadow z-20 transition-all",
            collapsed
              ? "fixed right-3 top-[calc(50vh+2rem)] -translate-y-1/2"
              : "absolute -left-3 top-1/2 -translate-y-1/2"
          )}
        >
          {collapsed ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>

        <div className={cn("flex flex-col h-full overflow-y-auto w-full", collapsed && "invisible")}>
      <div className="p-5 border-b border-slate-200 relative shrink-0">
        <button onClick={() => setSelectedObject(null)} className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 bg-slate-50 hover:bg-slate-100 rounded-full w-6 h-6 flex items-center justify-center font-bold transition-colors">
          &times;
        </button>
        <h2 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-4 italic">处理面板</h2>
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
          ) : isChoice ? (
            <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-[10px] font-bold rounded uppercase tracking-wider">候选方案</span>
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

        {(isNode || isSlot) && Object.keys(structuredDraft || {}).length > 0 && (
          <section>
            {editingStructured && isSlot && (
              <div className="space-y-3 text-xs">
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">名称</div>
                  <input
                    value={structuredDraft.name || ''}
                    onChange={(e) => updateStructuredField('name', e.target.value)}
                    onBlur={() => void commitStructuredField('name', structuredDraft.name || '')}
                    className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700"
                  />
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">描述</div>
                  <textarea
                    value={structuredDraft.description || ''}
                    onChange={(e) => updateStructuredField('description', e.target.value)}
                    onBlur={() => void commitStructuredField('description', structuredDraft.description || '')}
                    className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700 min-h-[60px]"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <div className="text-[10px] font-bold text-slate-400 uppercase">数量约束</div>
                    <select
                      value={structuredDraft.arity || 'many'}
                      onChange={(e) => {
                        updateStructuredField('arity', e.target.value);
                        void commitStructuredField('arity', e.target.value);
                      }}
                      className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700"
                    >
                      <option value="one">单个</option>
                      <option value="many">多个</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <div className="text-[10px] font-bold text-slate-400 uppercase">状态</div>
                    <select
                      value={structuredDraft.status || 'empty'}
                      onChange={(e) => {
                        updateStructuredField('status', e.target.value);
                        void commitStructuredField('status', e.target.value);
                      }}
                      className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700"
                    >
                      <option value="empty">空缺</option>
                      <option value="expanding">展开中</option>
                      <option value="filled">已填充</option>
                      <option value="deferred">暂缓</option>
                    </select>
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">期望类型</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(structuredDraft.expectedKinds || []).map((k: string) => (
                      <button
                        key={k}
                        onClick={() => removeStructuredListItem('expectedKinds', k)}
                        className="text-[10px] px-2 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-rose-200 hover:text-rose-600 transition-colors"
                      >
                        {k} ×
                      </button>
                    ))}
                  </div>
                  <select
                    value=""
                    onChange={(e) => {
                      const v = e.target.value;
                      (e.target as HTMLSelectElement).value = '';
                      if (v) addStructuredListItem('expectedKinds', v);
                    }}
                    className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700"
                  >
                    <option value="">添加期望类型…</option>
                    <option value="rule">规则 rule</option>
                    <option value="flow_step">流程步骤 flow_step</option>
                    <option value="state_transition">状态流转 state_transition</option>
                    <option value="ui_component">UI 组件 ui_component</option>
                    <option value="business_object">业务对象 business_object</option>
                  </select>
                </div>
              </div>
            )}

            {editingStructured && isNode && selectedObject.kind === 'goal' && (
              <div className="space-y-3 text-xs">
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">成功标准</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(structuredDraft.successCriteria || []).map((x: string) => (
                      <button
                        key={x}
                        onClick={() => removeStructuredListItem('successCriteria', x)}
                        className="text-[10px] px-2 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-rose-200 hover:text-rose-600 transition-colors"
                      >
                        {x} ×
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={() => {
                      const v = globalThis.prompt('新增成功标准');
                      if (v) addStructuredListItem('successCriteria', v.trim());
                    }}
                    className="text-[10px] px-2 py-1 rounded bg-slate-900 text-white hover:bg-slate-800 transition-colors"
                  >
                    添加标准
                  </button>
                </div>
              </div>
            )}

            {editingStructured && isNode && selectedObject.kind === 'capability' && (
              <div className="space-y-3 text-xs">
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <div className="text-[10px] font-bold text-slate-400 uppercase">优先级</div>
                    <input
                      value={structuredDraft.priority || ''}
                      onChange={(e) => updateStructuredField('priority', e.target.value)}
                      onBlur={() => void commitStructuredField('priority', structuredDraft.priority || '')}
                      className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700"
                    />
                  </div>
                  <div className="space-y-1">
                    <div className="text-[10px] font-bold text-slate-400 uppercase">父能力</div>
                    <select
                      value={structuredDraft.parentId || ''}
                      onChange={(e) => {
                        updateStructuredField('parentId', e.target.value);
                        void commitStructuredField('parentId', e.target.value);
                      }}
                      className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700"
                    >
                      <option value="">—</option>
                      {nodesByKind('capability').map((n) => (
                        <option key={n.id} value={n.id}>{n.title}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">验收要点</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(structuredDraft.acceptanceNotes || []).map((x: string) => (
                      <button
                        key={x}
                        onClick={() => removeStructuredListItem('acceptanceNotes', x)}
                        className="text-[10px] px-2 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-rose-200 hover:text-rose-600 transition-colors"
                      >
                        {x} ×
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={() => {
                      const v = globalThis.prompt('新增验收要点');
                      if (v) addStructuredListItem('acceptanceNotes', v.trim());
                    }}
                    className="text-[10px] px-2 py-1 rounded bg-slate-900 text-white hover:bg-slate-800 transition-colors"
                  >
                    添加要点
                  </button>
                </div>
              </div>
            )}

            {editingStructured && isNode && selectedObject.kind === 'actor' && (
              <div className="space-y-3 text-xs">
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">角色类型</div>
                  <select
                    value={structuredDraft.roleType || 'primary_user'}
                    onChange={(e) => {
                      updateStructuredField('roleType', e.target.value);
                      void commitStructuredField('roleType', e.target.value);
                    }}
                    className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700"
                  >
                    <option value="primary_user">主用户</option>
                    <option value="operator">操作员</option>
                    <option value="approver">审批者</option>
                    <option value="admin">管理员</option>
                    <option value="external">外部</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">职责</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(structuredDraft.responsibilities || []).map((x: string) => (
                      <button key={x} onClick={() => removeStructuredListItem('responsibilities', x)} className="text-[10px] px-2 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-rose-200 hover:text-rose-600 transition-colors">{x} ×</button>
                    ))}
                  </div>
                  <button onClick={() => { const v = globalThis.prompt('新增职责'); if (v) addStructuredListItem('responsibilities', v.trim()); }} className="text-[10px] px-2 py-1 rounded bg-slate-900 text-white hover:bg-slate-800 transition-colors">添加职责</button>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">权限</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(structuredDraft.permissions || []).map((x: string) => (
                      <button key={x} onClick={() => removeStructuredListItem('permissions', x)} className="text-[10px] px-2 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-rose-200 hover:text-rose-600 transition-colors">{x} ×</button>
                    ))}
                  </div>
                  <button onClick={() => { const v = globalThis.prompt('新增权限'); if (v) addStructuredListItem('permissions', v.trim()); }} className="text-[10px] px-2 py-1 rounded bg-slate-900 text-white hover:bg-slate-800 transition-colors">添加权限</button>
                </div>
              </div>
            )}

            {editingStructured && isNode && selectedObject.kind === 'task' && (
              <div className="space-y-3 text-xs">
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">执行角色</div>
                  <select value={structuredDraft.actorId || ''} onChange={(e) => { updateStructuredField('actorId', e.target.value); void commitStructuredField('actorId', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">—</option>
                    {nodesByKind('actor').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">关联能力</div>
                  <select value={structuredDraft.capabilityId || ''} onChange={(e) => { updateStructuredField('capabilityId', e.target.value); void commitStructuredField('capabilityId', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">—</option>
                    {nodesByKind('capability').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <div className="text-[10px] font-bold text-slate-400 uppercase">负责人</div>
                    <input value={structuredDraft.owner || ''} onChange={(e) => updateStructuredField('owner', e.target.value)} onBlur={() => void commitStructuredField('owner', structuredDraft.owner || '')} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700" />
                  </div>
                  <div className="space-y-1">
                    <div className="text-[10px] font-bold text-slate-400 uppercase">预期结果</div>
                    <input value={structuredDraft.outcome || ''} onChange={(e) => updateStructuredField('outcome', e.target.value)} onBlur={() => void commitStructuredField('outcome', structuredDraft.outcome || '')} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700" />
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">补充说明</div>
                  <textarea value={structuredDraft.result || ''} onChange={(e) => updateStructuredField('result', e.target.value)} onBlur={() => void commitStructuredField('result', structuredDraft.result || '')} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700 min-h-[50px]" />
                </div>
              </div>
            )}

            {editingStructured && isNode && selectedObject.kind === 'business_object' && (
              <div className="space-y-3 text-xs">
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">数据负责人</div>
                  <select value={structuredDraft.ownerActorId || ''} onChange={(e) => { updateStructuredField('ownerActorId', e.target.value); void commitStructuredField('ownerActorId', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">—</option>
                    {nodesByKind('actor').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">字段列表</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(structuredDraft.fieldIds || []).map((id: string) => (
                      <button key={id} onClick={() => removeStructuredListItem('fieldIds', id)} className="text-[10px] px-2 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-rose-200 hover:text-rose-600 transition-colors">{ir?.nodes?.[id]?.title || id} ×</button>
                    ))}
                  </div>
                  <select
                    defaultValue=""
                    onChange={(e) => { const v = e.target.value; (e.target as HTMLSelectElement).value = ''; addStructuredListItem('fieldIds', v); }}
                    className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700"
                  >
                    <option value="">添加字段…</option>
                    {nodesByKind('field').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">状态机</div>
                  <select value={structuredDraft.stateMachineId || ''} onChange={(e) => { updateStructuredField('stateMachineId', e.target.value); void commitStructuredField('stateMachineId', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">—</option>
                    {nodesByKind('state_machine').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
              </div>
            )}

            {editingStructured && isNode && selectedObject.kind === 'field' && (
              <div className="space-y-3 text-xs">
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">所属对象</div>
                  <select value={structuredDraft.objectId || ''} onChange={(e) => { updateStructuredField('objectId', e.target.value); void commitStructuredField('objectId', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">—</option>
                    {nodesByKind('business_object').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <div className="text-[10px] font-bold text-slate-400 uppercase">字段类型</div>
                    <select value={structuredDraft.fieldType || 'text'} onChange={(e) => { updateStructuredField('fieldType', e.target.value); void commitStructuredField('fieldType', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                      <option value="text">文本</option>
                      <option value="number">数字</option>
                      <option value="date">日期</option>
                      <option value="boolean">布尔</option>
                      <option value="enum">枚举</option>
                      <option value="file">文件</option>
                      <option value="reference">引用</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <div className="text-[10px] font-bold text-slate-400 uppercase">值来源</div>
                    <select value={structuredDraft.valueSource || 'user_input'} onChange={(e) => { updateStructuredField('valueSource', e.target.value); void commitStructuredField('valueSource', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                      <option value="user_input">用户输入</option>
                      <option value="system_generated">系统生成</option>
                      <option value="external">外部</option>
                    </select>
                  </div>
                </div>
                <label className="flex items-center gap-2 text-xs text-slate-700">
                  <input type="checkbox" checked={!!structuredDraft.required} onChange={(e) => { updateStructuredField('required', e.target.checked); void commitStructuredField('required', e.target.checked); }} />
                  必填
                </label>
              </div>
            )}

            {editingStructured && isNode && selectedObject.kind === 'screen' && (
              <div className="space-y-3 text-xs">
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">路由</div>
                  <input value={structuredDraft.route || ''} onChange={(e) => updateStructuredField('route', e.target.value)} onBlur={() => void commitStructuredField('route', structuredDraft.route || '')} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700" />
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">页面目的</div>
                  <textarea value={structuredDraft.purpose || ''} onChange={(e) => updateStructuredField('purpose', e.target.value)} onBlur={() => void commitStructuredField('purpose', structuredDraft.purpose || '')} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700 min-h-[50px]" />
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">可用角色</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(structuredDraft.actorIds || []).map((id: string) => (
                      <button key={id} onClick={() => removeStructuredListItem('actorIds', id)} className="text-[10px] px-2 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-rose-200 hover:text-rose-600 transition-colors">{ir?.nodes?.[id]?.title || id} ×</button>
                    ))}
                  </div>
                  <select defaultValue="" onChange={(e) => { const v = e.target.value; (e.target as HTMLSelectElement).value = ''; addStructuredListItem('actorIds', v); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">添加角色…</option>
                    {nodesByKind('actor').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">根组件</div>
                  <select value={structuredDraft.rootComponentId || ''} onChange={(e) => { updateStructuredField('rootComponentId', e.target.value); void commitStructuredField('rootComponentId', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">—</option>
                    {nodesByKind('ui_component').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
              </div>
            )}

            {editingStructured && isNode && selectedObject.kind === 'ui_component' && (
              <div className="space-y-3 text-xs">
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">组件类型</div>
                  <select value={structuredDraft.componentType || 'button'} onChange={(e) => { updateStructuredField('componentType', e.target.value); void commitStructuredField('componentType', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="form">表单</option>
                    <option value="table">表格</option>
                    <option value="detail">详情</option>
                    <option value="list">列表</option>
                    <option value="button">按钮</option>
                    <option value="field">字段</option>
                    <option value="status_badge">状态标签</option>
                    <option value="dialog">弹窗</option>
                    <option value="navigation">导航</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">子组件</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(structuredDraft.childIds || []).map((id: string) => (
                      <button key={id} onClick={() => removeStructuredListItem('childIds', id)} className="text-[10px] px-2 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-rose-200 hover:text-rose-600 transition-colors">{ir?.nodes?.[id]?.title || id} ×</button>
                    ))}
                  </div>
                  <select defaultValue="" onChange={(e) => { const v = e.target.value; (e.target as HTMLSelectElement).value = ''; addStructuredListItem('childIds', v); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">添加子组件…</option>
                    {nodesByKind('ui_component').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">字段绑定</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(structuredDraft.dataBindingIds || []).map((id: string) => (
                      <button key={id} onClick={() => removeStructuredListItem('dataBindingIds', id)} className="text-[10px] px-2 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-rose-200 hover:text-rose-600 transition-colors">{ir?.nodes?.[id]?.title || id} ×</button>
                    ))}
                  </div>
                  <select defaultValue="" onChange={(e) => { const v = e.target.value; (e.target as HTMLSelectElement).value = ''; addStructuredListItem('dataBindingIds', v); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">添加字段绑定…</option>
                    {nodesByKind('field').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">动作绑定</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(structuredDraft.actionBindingIds || []).map((id: string) => (
                      <button key={id} onClick={() => removeStructuredListItem('actionBindingIds', id)} className="text-[10px] px-2 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-rose-200 hover:text-rose-600 transition-colors">{ir?.nodes?.[id]?.title || id} ×</button>
                    ))}
                  </div>
                  <select defaultValue="" onChange={(e) => { const v = e.target.value; (e.target as HTMLSelectElement).value = ''; addStructuredListItem('actionBindingIds', v); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">添加动作绑定…</option>
                    {nodesByKind('flow_step').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
              </div>
            )}

            {editingStructured && isNode && selectedObject.kind === 'flow' && (
              <div className="space-y-3 text-xs">
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">触发条件</div>
                  <input value={structuredDraft.trigger || ''} onChange={(e) => updateStructuredField('trigger', e.target.value)} onBlur={() => void commitStructuredField('trigger', structuredDraft.trigger || '')} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700" />
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">主业务对象</div>
                  <select value={structuredDraft.mainObjectId || ''} onChange={(e) => { updateStructuredField('mainObjectId', e.target.value); void commitStructuredField('mainObjectId', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">—</option>
                    {nodesByKind('business_object').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
              </div>
            )}

            {editingStructured && isNode && selectedObject.kind === 'flow_step' && (
              <div className="space-y-3 text-xs">
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">所属流程</div>
                  <select value={structuredDraft.flowId || ''} onChange={(e) => { updateStructuredField('flowId', e.target.value); void commitStructuredField('flowId', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">—</option>
                    {nodesByKind('flow').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">执行角色</div>
                  <select value={structuredDraft.actorId || ''} onChange={(e) => { updateStructuredField('actorId', e.target.value); void commitStructuredField('actorId', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">—</option>
                    {nodesByKind('actor').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">输入对象</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(structuredDraft.inputObjectIds || []).map((id: string) => (
                      <button key={id} onClick={() => removeStructuredListItem('inputObjectIds', id)} className="text-[10px] px-2 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-rose-200 hover:text-rose-600 transition-colors">{ir?.nodes?.[id]?.title || id} ×</button>
                    ))}
                  </div>
                  <select defaultValue="" onChange={(e) => { const v = e.target.value; (e.target as HTMLSelectElement).value = ''; addStructuredListItem('inputObjectIds', v); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">添加输入对象…</option>
                    {nodesByKind('business_object').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">输出对象</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(structuredDraft.outputObjectIds || []).map((id: string) => (
                      <button key={id} onClick={() => removeStructuredListItem('outputObjectIds', id)} className="text-[10px] px-2 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-rose-200 hover:text-rose-600 transition-colors">{ir?.nodes?.[id]?.title || id} ×</button>
                    ))}
                  </div>
                  <select defaultValue="" onChange={(e) => { const v = e.target.value; (e.target as HTMLSelectElement).value = ''; addStructuredListItem('outputObjectIds', v); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">添加输出对象…</option>
                    {nodesByKind('business_object').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">关联规则</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(structuredDraft.ruleIds || []).map((id: string) => (
                      <button key={id} onClick={() => removeStructuredListItem('ruleIds', id)} className="text-[10px] px-2 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-rose-200 hover:text-rose-600 transition-colors">{ir?.nodes?.[id]?.title || id} ×</button>
                    ))}
                  </div>
                  <select defaultValue="" onChange={(e) => { const v = e.target.value; (e.target as HTMLSelectElement).value = ''; addStructuredListItem('ruleIds', v); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">添加规则…</option>
                    {nodesByKind('rule').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
              </div>
            )}

            {editingStructured && isNode && selectedObject.kind === 'rule' && (
              <div className="space-y-3 text-xs">
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">规则类型</div>
                  <select value={structuredDraft.ruleType || 'condition'} onChange={(e) => { updateStructuredField('ruleType', e.target.value); void commitStructuredField('ruleType', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="condition">条件</option>
                    <option value="validation">校验</option>
                    <option value="permission">权限</option>
                    <option value="business_policy">策略</option>
                    <option value="calculation">计算</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">自然语言</div>
                  <textarea value={structuredDraft.naturalLanguage || ''} onChange={(e) => updateStructuredField('naturalLanguage', e.target.value)} onBlur={() => void commitStructuredField('naturalLanguage', structuredDraft.naturalLanguage || '')} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700 min-h-[60px]" />
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">表达式</div>
                  <input value={structuredDraft.expression || ''} onChange={(e) => updateStructuredField('expression', e.target.value)} onBlur={() => void commitStructuredField('expression', structuredDraft.expression || '')} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700" />
                </div>
              </div>
            )}

            {editingStructured && isNode && selectedObject.kind === 'state_machine' && (
              <div className="space-y-3 text-xs">
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">所属对象</div>
                  <select value={structuredDraft.objectId || ''} onChange={(e) => { updateStructuredField('objectId', e.target.value); void commitStructuredField('objectId', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">—</option>
                    {nodesByKind('business_object').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">状态集合</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(structuredDraft.stateIds || []).map((id: string) => (
                      <button key={id} onClick={() => removeStructuredListItem('stateIds', id)} className="text-[10px] px-2 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-rose-200 hover:text-rose-600 transition-colors">{ir?.nodes?.[id]?.title || id} ×</button>
                    ))}
                  </div>
                  <select defaultValue="" onChange={(e) => { const v = e.target.value; (e.target as HTMLSelectElement).value = ''; addStructuredListItem('stateIds', v); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">添加状态…</option>
                    {nodesByKind('object_state').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">流转集合</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(structuredDraft.transitionIds || []).map((id: string) => (
                      <button key={id} onClick={() => removeStructuredListItem('transitionIds', id)} className="text-[10px] px-2 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-rose-200 hover:text-rose-600 transition-colors">{ir?.nodes?.[id]?.title || id} ×</button>
                    ))}
                  </div>
                  <select defaultValue="" onChange={(e) => { const v = e.target.value; (e.target as HTMLSelectElement).value = ''; addStructuredListItem('transitionIds', v); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">添加流转…</option>
                    {nodesByKind('state_transition').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
              </div>
            )}

            {editingStructured && isNode && selectedObject.kind === 'object_state' && (
              <div className="space-y-3 text-xs">
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">所属对象</div>
                  <select value={structuredDraft.objectId || ''} onChange={(e) => { updateStructuredField('objectId', e.target.value); void commitStructuredField('objectId', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">—</option>
                    {nodesByKind('business_object').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
              </div>
            )}

            {editingStructured && isNode && selectedObject.kind === 'state_transition' && (
              <div className="space-y-3 text-xs">
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <div className="text-[10px] font-bold text-slate-400 uppercase">起始状态</div>
                    <select value={structuredDraft.fromStateId || ''} onChange={(e) => { updateStructuredField('fromStateId', e.target.value); void commitStructuredField('fromStateId', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                      <option value="">—</option>
                      {nodesByKind('object_state').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <div className="text-[10px] font-bold text-slate-400 uppercase">目标状态</div>
                    <select value={structuredDraft.toStateId || ''} onChange={(e) => { updateStructuredField('toStateId', e.target.value); void commitStructuredField('toStateId', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                      <option value="">—</option>
                      {nodesByKind('object_state').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                    </select>
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">触发步骤</div>
                  <select value={structuredDraft.triggerStepId || ''} onChange={(e) => { updateStructuredField('triggerStepId', e.target.value); void commitStructuredField('triggerStepId', e.target.value); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">—</option>
                    {nodesByKind('flow_step').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">约束规则</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(structuredDraft.ruleIds || []).map((id: string) => (
                      <button key={id} onClick={() => removeStructuredListItem('ruleIds', id)} className="text-[10px] px-2 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-rose-200 hover:text-rose-600 transition-colors">{ir?.nodes?.[id]?.title || id} ×</button>
                    ))}
                  </div>
                  <select defaultValue="" onChange={(e) => { const v = e.target.value; (e.target as HTMLSelectElement).value = ''; addStructuredListItem('ruleIds', v); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                    <option value="">添加规则…</option>
                    {nodesByKind('rule').map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                  </select>
                </div>
              </div>
            )}
          </section>
        )}

        {isIssue && Object.keys(issueDraft || {}).length > 0 && (
          <section>
            <div className="space-y-3 text-xs">
              <div className="space-y-1">
                <div className="text-[10px] font-bold text-slate-400 uppercase">标题</div>
                <input
                  value={issueDraft.title || ''}
                  onChange={(e) => updateIssueField('title', e.target.value)}
                  onBlur={() => void commitIssueField('title', issueDraft.title || '')}
                  className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700"
                />
              </div>
              <div className="space-y-1">
                <div className="text-[10px] font-bold text-slate-400 uppercase">描述</div>
                <textarea
                  value={issueDraft.description || ''}
                  onChange={(e) => updateIssueField('description', e.target.value)}
                  onBlur={() => void commitIssueField('description', issueDraft.description || '')}
                  className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700 min-h-[60px]"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">严重级别</div>
                  <select
                    value={issueDraft.severity || 'medium'}
                    onChange={(e) => { updateIssueField('severity', e.target.value); void commitIssueField('severity', e.target.value); }}
                    className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700"
                  >
                    <option value="low">低</option>
                    <option value="medium">中</option>
                    <option value="high">高</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">状态</div>
                  <select
                    value={issueDraft.status || 'open'}
                    onChange={(e) => { updateIssueField('status', e.target.value); void commitIssueField('status', e.target.value); }}
                    className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700"
                  >
                    <option value="open">未解决</option>
                    <option value="resolved">已解决</option>
                    <option value="ignored">已暂缓</option>
                  </select>
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-[10px] font-bold text-slate-400 uppercase">类别</div>
                <input
                  value={issueDraft.category || ''}
                  onChange={(e) => updateIssueField('category', e.target.value)}
                  onBlur={() => void commitIssueField('category', issueDraft.category || '')}
                  className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700"
                />
              </div>
              <div className="space-y-1">
                <div className="text-[10px] font-bold text-slate-400 uppercase">建议投影</div>
                <select
                  value={issueDraft.suggestedProjection || 'goal'}
                  onChange={(e) => { updateIssueField('suggestedProjection', e.target.value); void commitIssueField('suggestedProjection', e.target.value); }}
                  className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700"
                >
                  <option value="goal">目标</option>
                  <option value="role">角色</option>
                  <option value="system">系统</option>
                  <option value="data">数据</option>
                  <option value="ui">UI</option>
                </select>
              </div>
              <div className="space-y-1">
                <div className="text-[10px] font-bold text-slate-400 uppercase">建议动作</div>
                <input
                  value={issueDraft.suggestedAction || ''}
                  onChange={(e) => updateIssueField('suggestedAction', e.target.value)}
                  onBlur={() => void commitIssueField('suggestedAction', issueDraft.suggestedAction || '')}
                  className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700"
                />
              </div>
              <div className="space-y-1">
                <div className="text-[10px] font-bold text-slate-400 uppercase">关联节点</div>
                <div className="flex flex-wrap gap-1.5">
                  {(issueDraft.relatedNodeIds || []).map((id: string) => (
                    <button key={id} onClick={() => removeIssueRelatedNode(id)} className="text-[10px] px-2 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-rose-200 hover:text-rose-600 transition-colors">{ir?.nodes?.[id]?.title || id} ×</button>
                  ))}
                </div>
                <select defaultValue="" onChange={(e) => { const v = e.target.value; (e.target as HTMLSelectElement).value = ''; addIssueRelatedNode(v); }} className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700">
                  <option value="">添加关联节点…</option>
                  {allNodes.map((n) => (<option key={n.id} value={n.id}>{n.title}</option>))}
                </select>
              </div>
            </div>
          </section>
        )}

        {isChoice && Object.keys(choiceDraft || {}).length > 0 && (
          <section>
            <div className="space-y-3 text-xs">
              <div className="space-y-1">
                <div className="text-[10px] font-bold text-slate-400 uppercase">标题</div>
                <input
                  value={choiceDraft.title || ''}
                  onChange={(e) => updateChoiceField('title', e.target.value)}
                  onBlur={() => void commitChoiceField('title', choiceDraft.title || '')}
                  className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700"
                />
              </div>

              <div className="space-y-1">
                <div className="text-[10px] font-bold text-slate-400 uppercase">生成理由</div>
                <textarea
                  value={choiceDraft.rationale || ''}
                  onChange={(e) => updateChoiceField('rationale', e.target.value)}
                  onBlur={() => void commitChoiceField('rationale', choiceDraft.rationale || '')}
                  className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700 min-h-[70px]"
                />
              </div>

              <div className="space-y-1">
                <div className="text-[10px] font-bold text-slate-400 uppercase">状态</div>
                <select
                  value={choiceDraft.status || 'candidate'}
                  onChange={(e) => {
                    updateChoiceField('status', e.target.value);
                    void commitChoiceField('status', e.target.value);
                  }}
                  className="w-full px-2 py-1.5 rounded border border-slate-200 bg-white text-slate-700"
                >
                  <option value="candidate">候选</option>
                  <option value="selected">已采纳</option>
                  <option value="rejected">已拒绝</option>
                  <option value="archived">已归档</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="bg-slate-50 border border-slate-200 rounded p-2">
                  <div className="text-[10px] font-bold text-slate-400 uppercase mb-1">新增节点</div>
                  <div className="text-xs font-bold text-slate-700">{Array.isArray((selectedObject as any).proposedNodeIds) ? (selectedObject as any).proposedNodeIds.length : 0}</div>
                </div>
                <div className="bg-slate-50 border border-slate-200 rounded p-2">
                  <div className="text-[10px] font-bold text-slate-400 uppercase mb-1">新增关联</div>
                  <div className="text-xs font-bold text-slate-700">{Array.isArray((selectedObject as any).proposedLinkIds) ? (selectedObject as any).proposedLinkIds.length : 0}</div>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* 状态与置信度 */}
        <section>
          <h3 className="text-[10px] font-bold text-slate-400 uppercase mb-3">状态与置信度</h3>
          <div className="space-y-2 text-xs text-slate-600">
            <div className="flex justify-between items-center">
              <span className="text-slate-400">状态</span>
              <StatusBadge status={selectedObject.status} />
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-400">置信度</span>
              <span className="font-medium">{selectedObject.confidence != null ? `${Math.round(selectedObject.confidence * 100)}%` : '—'}</span>
            </div>
            <div className="flex justify-between items-center"><span className="text-slate-400">来源类型</span><span className="font-medium bg-slate-100 px-1.5 rounded">{SourceTypeToText[selectedObject.source?.type || ''] || selectedObject.source?.type || '未知'}</span></div>
            <div className="flex justify-between items-start mt-1">
              <span className="text-slate-400 w-16 shrink-0 text-left">来源内容</span>
              <span className="text-[10px] bg-slate-50 p-1.5 rounded text-slate-500 border border-slate-100 text-right">{selectedObject.source?.text || '—'}</span>
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
                      onAccept={(choice) => acceptCandidate(choice.id)}
                      onRewrite={(choice) => setSelectedObject(choice)}
                      onReject={(choice) => excludeObject(choice.id)}
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

      <div className="p-5 border-t border-slate-200 grid grid-cols-2 gap-2 mt-auto shrink-0 bg-slate-50/50 relative">
        {renderBottomActions()}
      </div>
     </div>
    </aside>
  );
}

