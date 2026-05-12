import { useState, useEffect } from 'react';
import { useWorkspaceStore, selectSelectedObject, selectCurrentPage } from '@/store/useWorkspaceStore';
import { ProjectionKind } from '@/types';

const Modes = ['展开 Slot', '生成候选', '检查一致性', '局部改写', '解释影响'];

type AIScope =
  | { kind: 'workspace'; label: string }
  | { kind: 'projection'; projection: ProjectionKind; label: string }
  | { kind: 'node'; nodeId: string; label: string }
  | { kind: 'slot'; slotId: string; label: string }
  | { kind: 'issue'; issueId: string; label: string }
  | { kind: 'choiceGroup'; choiceGroupId: string; label: string };

export function ScopedAIBar() {
  const { generateCandidate, generateGap, ir, runDiagnosis, openSlot } = useWorkspaceStore();
  const selectedObject: any = useWorkspaceStore(selectSelectedObject);
  const currentPage = useWorkspaceStore(selectCurrentPage);
  
  // Build scopes array based on context
  const getScopes = (): AIScope[] => {
    const scopes: AIScope[] = [];

    // Base scope
    scopes.push({ kind: 'workspace', label: '全局 (Workspace)' });

    // Current page implies a projection scope
    if (currentPage === '/') scopes.unshift({ kind: 'projection', projection: 'goal', label: '投影: 概览' });
    if (currentPage === '/what') scopes.unshift({ kind: 'projection', projection: 'goal', label: '投影: 目标与角色' });
    if (currentPage === '/flow') scopes.unshift({ kind: 'projection', projection: 'system', label: '投影: 流程与规则' });
    if (currentPage === '/scope') scopes.unshift({ kind: 'projection', projection: 'data', label: '投影: 范围与边界' });
    if (currentPage === '/preview') scopes.unshift({ kind: 'projection', projection: 'ui', label: '投影: 方案预览' });

    // Object specific scope
    if (selectedObject) {
      const isNode = ir?.nodes?.[selectedObject.id];
      const isIssue = selectedObject.severity !== undefined;
      const isChoiceGroup = selectedObject.choices !== undefined;
      const isSlot = selectedObject.arity !== undefined;

      const title = selectedObject.title || selectedObject.name || selectedObject.id;

      if (isChoiceGroup) {
        scopes.unshift({ kind: 'choiceGroup', choiceGroupId: selectedObject.id, label: `ChoiceGroup: ${title}` });
      } else if (isSlot) {
        scopes.unshift({ kind: 'slot', slotId: selectedObject.id, label: `Slot: ${title}` });
      } else if (isIssue) {
        scopes.unshift({ kind: 'issue', issueId: selectedObject.id, label: `Issue: ${title}` });
      } else if (isNode) {
        scopes.unshift({ kind: 'node', nodeId: selectedObject.id, label: `节点: ${title}` });
      } else {
         scopes.unshift({ kind: 'node', nodeId: selectedObject.id, label: `对象: ${title}` });
      }
    }
    
    return scopes;
  };

  const currentScopes = getScopes();
  const [selectedScopeIndex, setSelectedScopeIndex] = useState(0);
  const scope = currentScopes[selectedScopeIndex] || currentScopes[0];
  const [mode, setMode] = useState(Modes[0]);
  const [input, setInput] = useState('');

  // Auto-update scope when selection changes
  useEffect(() => {
    setSelectedScopeIndex(0);
  }, [selectedObject, currentPage]);

  const placeholderText = scope.kind === 'workspace' 
    ? `输入对当前应用全局的调整...`
    : `针对 ${scope.label} 操作...`;

  const handleSubmit = async () => {
    if (!input.trim() && mode !== '生成候选' && mode !== '检查一致性') return;

    if (mode === '展开 Slot' || mode === '生成候选' || mode === '局部改写') {
      if (scope.kind === 'slot') {
        openSlot(scope.slotId);
      } else {
        await generateCandidate(selectedObject?.id || '');
      }
    } else if (mode === '检查一致性') {
      await generateGap(selectedObject?.id || '');
    } else if (mode === '解释影响') {
      await runDiagnosis({ action: 'explain_impact', scope, input });
    }
    
    setInput('');
  };

  return (
    <div className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-40 transition-all duration-300 ${selectedObject ? 'w-[min(620px,calc(100vw-2rem))]' : 'w-[min(760px,calc(100vw-2rem))]'}`}>
      <div className="bg-slate-900 rounded-2xl p-2 shadow-2xl flex items-center gap-2 border border-slate-700">
        
        {/* Scope Selector */}
        <select 
          value={selectedScopeIndex} 
          onChange={e => setSelectedScopeIndex(Number(e.target.value))}
          className="bg-slate-800 text-slate-300 text-xs font-bold px-3 py-2 rounded-xl border-none ring-0 focus:ring-1 focus:ring-indigo-500 outline-none cursor-pointer max-w-[150px] truncate"
        >
          {currentScopes.map((s, idx) => <option key={idx} value={idx}>{s.label}</option>)}
        </select>

        {/* Input */}
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={placeholderText}
          className="flex-1 bg-transparent border-none text-white text-sm focus:ring-0 focus:outline-none px-2 placeholder:text-slate-500"
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
        />

        {/* Mode Selector */}
        <select 
          value={mode} 
          onChange={e => setMode(e.target.value)}
          className="bg-slate-800 text-slate-400 text-xs px-2 py-2 rounded-xl border-none outline-none cursor-pointer"
        >
          {Modes.map(m => <option key={m} value={m}>{m}</option>)}
        </select>

        {/* Submit */}
        <button 
          onClick={handleSubmit} 
          className="px-6 py-2 bg-indigo-600 border border-indigo-500 text-white font-bold rounded-xl text-sm hover:bg-indigo-500 hover:border-indigo-400 transition-colors shadow-[0_0_15px_rgba(79,70,229,0.3)]"
        >
          发起提案
        </button>
      </div>
    </div>
  );
}
