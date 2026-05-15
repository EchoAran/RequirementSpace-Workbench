import { useState } from 'react';
import { RangeKanbanColumn } from '@/components/shared/RangeKanbanColumn';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { ImpactPreview, ImpactGroup } from '@/components/shared/ImpactPreview';
import { workspaceApi } from '@/lib/api';
import { GraphPatch } from '@/types';
import { 
  useWorkspaceStore, 
  selectScopeItems
} from '@/store/useWorkspaceStore';
import { formatImpactPreview, groupScopeItems } from '@/domain/ir/selectors';

const SCOPE_COLUMNS = [
  { key: 'in_scope', label: '本期包含' },
  { key: 'deferred', label: '暂缓处理' },
  { key: 'external_dependency', label: '外部依赖' },
  { key: 'out_of_scope', label: '范围外' },
  { key: 'excluded', label: '已排除', danger: true },
] as const;

export function ScopeAndDelivery() {
  const { 
    selectedObject, highlightTarget,
    setSelectedObject, ir, runDiagnosis, applyPatch
  } = useWorkspaceStore();
  
  const scopeItems = useWorkspaceStore(selectScopeItems);
  const [impactGroups, setImpactGroups] = useState<ImpactGroup[]>([]);
  const [pendingPatch, setPendingPatch] = useState<GraphPatch | null>(null);
  const [pendingMoveLabel, setPendingMoveLabel] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const grouped = ir ? groupScopeItems(ir) : { inScope: [], deferred: [], dependencies: [], outOfScope: [], excluded: [] };
  const inScope = grouped.inScope.length ? grouped.inScope : scopeItems.filter(i => i.scopeStatus === 'in_scope');
  const deferred = grouped.deferred.length ? grouped.deferred : scopeItems.filter(i => i.scopeStatus === 'deferred');
  const dependencies = grouped.dependencies.length ? grouped.dependencies : scopeItems.filter(i => i.scopeStatus === 'external_dependency');
  const outOfScope = grouped.outOfScope.length ? grouped.outOfScope : scopeItems.filter(i => i.scopeStatus === 'out_of_scope');
  const excluded = grouped.excluded.length ? grouped.excluded : Object.values(ir?.nodes || {}).filter((n: any) => n.status === 'excluded');

  const buildImpactGroups = (impact: ReturnType<typeof formatImpactPreview>, rawImpact: any): ImpactGroup[] => {
    const groups: ImpactGroup[] = [];
    if (impact.goals.length > 0) groups.push({ type: 'info', title: `影响 ${impact.goals.length} 个目标`, items: impact.goals });
    if (impact.flows.length > 0) groups.push({ type: 'process', title: `影响 ${impact.flows.length} 个流程`, items: impact.flows });
    if (impact.objects.length > 0) groups.push({ type: 'info', title: `影响 ${impact.objects.length} 个对象`, items: impact.objects });
    if (impact.screens.length > 0) groups.push({ type: 'page', title: `影响 ${impact.screens.length} 个页面`, items: impact.screens });
    if ((rawImpact?.newIssues || []).length > 0) {
      groups.push({
        type: 'gap_add',
        title: `将新增 ${(rawImpact.newIssues || []).length} 个 Issue`,
        items: (rawImpact.newIssues || []).map((id: string) => ir?.issues[id]?.title || id),
      });
    }
    return groups;
  };

  const createScopeItem = async (columnKey: string) => {
    const scopeStatus = columnKey === 'excluded' ? undefined : columnKey;

    const id = `sc_${(globalThis.crypto && 'randomUUID' in globalThis.crypto) ? (globalThis.crypto as any).randomUUID() : String(Date.now())}`;
    await applyPatch({
      addNodes: [
        {
          id,
          kind: 'capability',
          title: '新范围项',
          description: '',
          status: columnKey === 'excluded' ? 'excluded' : 'needs_confirmation',
          confidence: 0.6,
          scopeStatus: scopeStatus as any,
          source: { type: 'user', text: '手动添加范围项' },
          priority: 'high',
        } as any,
      ],
    } as any);

    const created = useWorkspaceStore.getState().ir?.nodes?.[id];
    if (created) setSelectedObject(created as any);
  };

  const buildScopePatch = (itemId: string, targetKey: string): GraphPatch => {
    const patch: GraphPatch = {
      updateNodes: [
        {
          id: itemId,
          status: targetKey === 'excluded' ? 'excluded' : 'needs_confirmation',
          scopeStatus: targetKey === 'excluded' ? undefined : (targetKey as any),
        },
      ],
    };
    return patch;
  };

  const previewScopeMove = async (itemId: string, targetKey: string) => {
    if (!ir?.id) return;
    const patch = buildScopePatch(itemId, targetKey);
    const resp = await workspaceApi.impactPreview(ir.id, { patch });
    const formatted = formatImpactPreview(ir, resp.impactPreview);
    setPendingPatch(patch);
    setPendingMoveLabel(SCOPE_COLUMNS.find((column) => column.key === targetKey)?.label || targetKey);
    setImpactGroups(buildImpactGroups(formatted, resp.impactPreview));
    setPreviewError(null);
  };

  const handleScopeMove = async (itemId: string, targetKey: string) => {
    try {
      await previewScopeMove(itemId, targetKey);
    } catch (error) {
      setPreviewError(error instanceof Error ? error.message : '影响预览失败');
    }
  };

  const applyPendingMove = async () => {
    if (!pendingPatch) return;
    await applyPatch(pendingPatch);
    setPendingPatch(null);
    setPendingMoveLabel(null);
  };

  return (
    <div className="flex-1 flex w-full relative">
      <div className="flex-1 p-6 pb-24 overflow-y-auto">
        <div className="max-w-[1200px] mx-auto space-y-8 animate-in fade-in">
          
          <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
             <div className="flex justify-between items-start mb-6">
               <div>
                  <h2 className="text-xl font-bold text-slate-900 mb-2">范围决策板</h2>
                  <p className="text-sm text-slate-500">将识别到的各类能力、流程细节、边界功能分别拖入不同的范畴栏位。</p>
               </div>
               <button
                 onClick={() => runDiagnosis({ trigger: 'scope_recommendation', page: '/scope' })}
                 className="text-sm bg-sky-50 text-sky-600 font-medium px-4 py-2 rounded-xl border border-sky-100 hover:bg-sky-100 transition-colors"
               >
                 自动推荐范围
               </button>
             </div>

             <div className="grid grid-cols-1 xl:grid-cols-5 gap-4 overflow-x-auto">
                <RangeKanbanColumn 
                  columnKey="in_scope"
                  title="本期包含" 
                  items={inScope} 
                  moveTargets={SCOPE_COLUMNS.map((column) => ({ key: column.key, label: column.label, danger: column.key === 'excluded' }))}
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id}
                  onItemClick={setSelectedObject}
                  onMoveItem={handleScopeMove}
                  onAddItem={(column) => createScopeItem(column)}
                />
                <RangeKanbanColumn 
                  columnKey="deferred"
                  title="暂缓处理" 
                  items={deferred} 
                  moveTargets={SCOPE_COLUMNS.map((column) => ({ key: column.key, label: column.label, danger: column.key === 'excluded' }))}
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id}
                  onItemClick={setSelectedObject}
                  onMoveItem={handleScopeMove}
                  onAddItem={(column) => createScopeItem(column)}
                />
                <RangeKanbanColumn 
                  columnKey="external_dependency"
                  title="外部依赖" 
                  items={dependencies} 
                  moveTargets={SCOPE_COLUMNS.map((column) => ({ key: column.key, label: column.label, danger: column.key === 'excluded' }))}
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id}
                  onItemClick={setSelectedObject}
                  onMoveItem={handleScopeMove}
                  onAddItem={(column) => createScopeItem(column)}
                />
                <RangeKanbanColumn 
                  columnKey="out_of_scope"
                  title="范围外" 
                  items={outOfScope} 
                  moveTargets={SCOPE_COLUMNS.map((column) => ({ key: column.key, label: column.label, danger: column.key === 'excluded' }))}
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id}
                  onItemClick={setSelectedObject}
                  onMoveItem={handleScopeMove}
                  onAddItem={(column) => createScopeItem(column)}
                />
                <RangeKanbanColumn 
                  columnKey="excluded"
                  title="已排除" 
                  items={excluded} 
                  moveTargets={SCOPE_COLUMNS.map((column) => ({ key: column.key, label: column.label, danger: column.key === 'excluded' }))}
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id}
                  onItemClick={setSelectedObject}
                  onMoveItem={handleScopeMove}
                  onAddItem={(column) => createScopeItem(column)}
                />
             </div>
          </section>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <section className="flex flex-col md:col-span-2">
              <h3 className="text-lg font-bold text-slate-900 mb-4">范围调整影响</h3>
              {pendingMoveLabel && (
                <div className="mb-4 rounded-xl border border-sky-200 bg-sky-50 p-4 flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-sky-900">已生成移动 Patch 预览</div>
                    <div className="text-xs text-sky-700 mt-1">目标列：{pendingMoveLabel}。确认后将写入审计记录。</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => { setPendingPatch(null); setPendingMoveLabel(null); setImpactGroups([]); }}
                      className="rounded-lg border border-sky-200 bg-white px-3 py-2 text-sm font-medium text-sky-700 hover:bg-sky-50"
                    >
                      取消
                    </button>
                    <button
                      type="button"
                      onClick={() => void applyPendingMove()}
                      className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800"
                    >
                      应用 Patch
                    </button>
                  </div>
                </div>
              )}
              {previewError && <div className="mb-4 text-sm text-rose-600">{previewError}</div>}
              <div className="flex-1">
                <ImpactPreview impacts={impactGroups} />
              </div>
            </section>
          </div>

        </div>
      </div>
      
      <RightObjectPanel />
    </div>
  );
}
