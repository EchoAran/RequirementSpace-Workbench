import { useEffect, useMemo, useState } from 'react';
import { ProjectionKind, Proposal } from '@/types';
import { selectCurrentPage, selectSelectedObject, useWorkspaceStore } from '@/store/useWorkspaceStore';

type AIScope =
  | { kind: 'workspace'; label: string }
  | { kind: 'projection'; projection: ProjectionKind; label: string }
  | { kind: 'node'; nodeId: string; label: string }
  | { kind: 'slot'; slotId: string; label: string }
  | { kind: 'issue'; issueId: string; label: string }
  | { kind: 'choice'; choiceId: string; label: string }
  | { kind: 'proposal'; proposalId: string; label: string; proposal: Proposal };

type AIIntent = 'diagnose' | 'create_slot' | 'expand_slot' | 'rewrite' | 'explain_impact';

const INTENT_LABELS: Record<AIIntent, string> = {
  diagnose: '诊断',
  create_slot: '创建 Slot',
  expand_slot: '展开 Slot',
  rewrite: '改写',
  explain_impact: '解释影响',
};

const pageToProjection = (page: string): ProjectionKind => {
  if (page === '/flow') return 'system';
  if (page === '/scope') return 'data';
  if (page === '/preview') return 'ui';
  if (page === '/' || page === '/what') return 'goal';
  return 'goal';
};

export function ScopedAIBar() {
  const {
    ir,
    isLoading,
    lastActionMessage,
    runDiagnosis,
    createSlotFromIssue,
    expandSlot,
    rewrite,
    explainImpact,
  } = useWorkspaceStore();
  const selectedObject: any = useWorkspaceStore(selectSelectedObject);
  const currentPage = useWorkspaceStore(selectCurrentPage);

  const scopes = useMemo(() => {
    const nextScopes: AIScope[] = [
      { kind: 'projection', projection: pageToProjection(currentPage), label: '当前投影' },
      { kind: 'workspace', label: '整个工作区' },
    ];

    if (!selectedObject) return nextScopes;
    const title = selectedObject.title || selectedObject.name || selectedObject.id;

    if (ir?.issues?.[selectedObject.id]) {
      nextScopes.unshift({ kind: 'issue', issueId: selectedObject.id, label: `Issue: ${title}` });
    } else if (ir?.slots?.[selectedObject.id]) {
      nextScopes.unshift({ kind: 'slot', slotId: selectedObject.id, label: `Slot: ${title}` });
    } else if (ir?.proposals?.[selectedObject.id]) {
      nextScopes.unshift({
        kind: 'proposal',
        proposalId: selectedObject.id,
        label: `Proposal: ${title}`,
        proposal: ir.proposals[selectedObject.id],
      });
    } else if (selectedObject.patch && selectedObject.rationale) {
      nextScopes.unshift({ kind: 'choice', choiceId: selectedObject.id, label: `Choice: ${title}` });
    } else if (ir?.nodes?.[selectedObject.id]) {
      nextScopes.unshift({ kind: 'node', nodeId: selectedObject.id, label: `节点: ${title}` });
    }

    return nextScopes;
  }, [currentPage, ir, selectedObject]);

  const [selectedScopeIndex, setSelectedScopeIndex] = useState(0);
  const [intent, setIntent] = useState<AIIntent>('diagnose');
  const [instruction, setInstruction] = useState('');

  useEffect(() => {
    setSelectedScopeIndex(0);
    setIntent('diagnose');
  }, [selectedObject, currentPage]);

  const scope = scopes[selectedScopeIndex] || scopes[0];

  const availableIntents = useMemo(() => {
    const intents: AIIntent[] = ['diagnose', 'create_slot', 'expand_slot', 'rewrite', 'explain_impact'];
    return intents.filter((item) => {
      if (item === 'create_slot') return scope.kind === 'issue';
      if (item === 'expand_slot') return scope.kind === 'slot';
      if (item === 'explain_impact') {
        return scope.kind === 'choice' || scope.kind === 'proposal';
      }
      return true;
    });
  }, [scope.kind]);

  useEffect(() => {
    if (!availableIntents.includes(intent)) {
      setIntent(availableIntents[0] || 'diagnose');
    }
  }, [availableIntents, intent]);

  const placeholder =
    intent === 'rewrite'
      ? scope.kind === 'workspace'
        ? '输入改写指令，例如：补全目标与验收标准'
        : `输入针对 ${scope.label} 的改写指令`
      : '当前动作无需额外输入';

  const handleSubmit = async () => {
    if (intent === 'rewrite' && !instruction.trim()) return;

    if (intent === 'diagnose') {
      await runDiagnosis(scope.kind === 'workspace' ? { trigger: 'manual' } : scope);
    } else if (intent === 'create_slot' && scope.kind === 'issue') {
      const slotId = await createSlotFromIssue(scope.issueId);
      if (slotId) {
        await expandSlot(slotId);
      }
    } else if (intent === 'expand_slot' && scope.kind === 'slot') {
      await expandSlot(scope.slotId);
    } else if (intent === 'rewrite') {
      await rewrite(scope, instruction);
    } else if (intent === 'explain_impact') {
      if (scope.kind === 'choice') {
        await explainImpact(scope, undefined, scope.choiceId);
      } else if (scope.kind === 'proposal') {
        await explainImpact(scope, scope.proposal.patch);
      }
    }

    setInstruction('');
  };

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 w-[min(860px,calc(100vw-2rem))]">
      <div className="bg-slate-900 rounded-2xl p-3 shadow-2xl border border-slate-700 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={selectedScopeIndex}
            onChange={(e) => setSelectedScopeIndex(Number(e.target.value))}
            className="bg-slate-800 text-slate-200 text-xs font-bold px-3 py-2 rounded-xl outline-none cursor-pointer"
          >
            {scopes.map((item, index) => (
              <option key={`${item.kind}-${index}`} value={index}>
                {item.label}
              </option>
            ))}
          </select>

          {availableIntents.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setIntent(item)}
              className={`px-3 py-2 rounded-xl text-xs font-bold transition-colors ${
                intent === item
                  ? 'bg-indigo-600 text-white border border-indigo-500'
                  : 'bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700'
              }`}
            >
              {INTENT_LABELS[item]}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <input
            type="text"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            disabled={intent !== 'rewrite'}
            placeholder={placeholder}
            className="flex-1 bg-slate-800 text-white text-sm rounded-xl px-4 py-2.5 placeholder:text-slate-500 outline-none disabled:opacity-60"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                void handleSubmit();
              }
            }}
          />
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={isLoading || (intent === 'rewrite' && !instruction.trim())}
            className="px-5 py-2.5 bg-indigo-600 border border-indigo-500 text-white font-bold rounded-xl text-sm hover:bg-indigo-500 transition-colors disabled:opacity-60"
          >
            {isLoading ? '执行中...' : '执行'}
          </button>
        </div>

        <div className="text-xs text-slate-400 min-h-[18px]">
          {lastActionMessage || `当前将对 ${scope.label} 执行 ${INTENT_LABELS[intent]}`}
        </div>
      </div>
    </div>
  );
}
