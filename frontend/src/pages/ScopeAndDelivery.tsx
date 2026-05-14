import { RangeKanbanColumn } from '@/components/shared/RangeKanbanColumn';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { ImpactPreview, ImpactGroup } from '@/components/shared/ImpactPreview';
import { 
  useWorkspaceStore, 
  selectScopeItems, 
  selectGoals, 
  selectActors,
  selectLinks
} from '@/store/useWorkspaceStore';
import { buildScopeImpact, groupScopeItems } from '@/domain/ir/selectors';

export function ScopeAndDelivery() {
  const { 
    selectedObject, highlightTarget,
    setSelectedObject, moveScopeItem, ir, runDiagnosis, applyPatch
  } = useWorkspaceStore();
  
  const scopeItems = useWorkspaceStore(selectScopeItems);
  const goals = useWorkspaceStore(selectGoals);
  const actors = useWorkspaceStore(selectActors);
  const links = useWorkspaceStore(selectLinks);

  const grouped = ir ? groupScopeItems(ir) : { inScope: [], deferred: [], dependencies: [], outOfScope: [], excluded: [] };
  const inScope = grouped.inScope.length ? grouped.inScope : scopeItems.filter(i => i.scopeStatus === 'in_scope');
  const deferred = grouped.deferred.length ? grouped.deferred : scopeItems.filter(i => i.scopeStatus === 'deferred');
  const dependencies = grouped.dependencies.length ? grouped.dependencies : scopeItems.filter(i => i.scopeStatus === 'external_dependency');
  const outOfScope = grouped.outOfScope.length ? grouped.outOfScope : scopeItems.filter(i => i.scopeStatus === 'out_of_scope');
  const excluded = grouped.excluded.length ? grouped.excluded : Object.values(ir?.nodes || {}).filter((n: any) => n.status === 'excluded');

  // Calculate dynamic impact preview if an item is selected
  let impactGroups: ImpactGroup[] = [];
  if (selectedObject && !selectedObject.choices && !selectedObject.gap && ir) {
    const objId = selectedObject.id;
    const impact = buildScopeImpact(ir, objId);
    if (impact.flows.length > 0) {
      impactGroups.push({
        type: 'process',
        title: `影响 ${impact.flows.length} 个流程/步骤`,
        items: impact.flows.map((id) => ir.nodes[id]?.title || id),
      });
    }
    if (impact.objects.length > 0) {
      impactGroups.push({
        type: 'info',
        title: `影响 ${impact.objects.length} 个业务对象`,
        items: impact.objects.map((id) => ir.nodes[id]?.title || id),
      });
    }
    if (impact.screens.length > 0) {
      impactGroups.push({
        type: 'page',
        title: `影响 ${impact.screens.length} 个页面`,
        items: impact.screens.map((id) => ir.nodes[id]?.title || id),
      });
    }
    if (impact.flows.length > 0 || impact.objects.length > 0 || impact.screens.length > 0) {
      impactGroups.push({
        type: 'gap_add',
        title: '潜在断层风险',
        items: [`若移除该节点，将影响以上关联项的引用一致性`],
      });
    }
  }

  const createScopeItem = async (columnTitle: string) => {
    const scopeStatus =
      columnTitle === '本期包含'
        ? 'in_scope'
        : columnTitle === '本期暂不处理'
          ? 'deferred'
          : columnTitle === '外部依赖'
            ? 'external_dependency'
            : columnTitle === '范围外'
              ? 'out_of_scope'
              : undefined;

    const id = `sc_${(globalThis.crypto && 'randomUUID' in globalThis.crypto) ? (globalThis.crypto as any).randomUUID() : String(Date.now())}`;
    const workspaceId = useWorkspaceStore.getState().ir?.id;
    await applyPatch({
      addNodes: [
        {
          id,
          kind: 'capability',
          title: '新范围项',
          description: '',
          status: columnTitle === '明确排除' ? 'excluded' : 'needs_confirmation',
          confidence: 0.6,
          scopeStatus: scopeStatus as any,
          source: { type: 'user', text: '手动添加范围项' },
          priority: 'P1',
        } as any,
      ],
    } as any);

    const namespacedId = workspaceId ? `${workspaceId}__${id}` : id;
    const created = useWorkspaceStore.getState().ir?.nodes?.[namespacedId];
    if (created) setSelectedObject(created as any);
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
                  title="本期包含" 
                  items={inScope} 
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id}
                  onItemClick={setSelectedObject}
                  onMoveItem={moveScopeItem}
                  onAddItem={(column) => createScopeItem(column)}
                />
                <RangeKanbanColumn 
                  title="本期暂不处理" 
                  items={deferred} 
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id}
                  onItemClick={setSelectedObject}
                  onMoveItem={moveScopeItem}
                  onAddItem={(column) => createScopeItem(column)}
                />
                <RangeKanbanColumn 
                  title="外部依赖" 
                  items={dependencies} 
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id}
                  onItemClick={setSelectedObject}
                  onMoveItem={moveScopeItem}
                  onAddItem={(column) => createScopeItem(column)}
                />
                <RangeKanbanColumn 
                  title="范围外" 
                  items={outOfScope} 
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id}
                  onItemClick={setSelectedObject}
                  onMoveItem={moveScopeItem}
                  onAddItem={(column) => createScopeItem(column)}
                />
                <RangeKanbanColumn 
                  title="明确排除" 
                  items={excluded} 
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id}
                  onItemClick={setSelectedObject}
                  onMoveItem={moveScopeItem}
                  onAddItem={(column) => createScopeItem(column)}
                />
             </div>
          </section>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <section className="flex flex-col md:col-span-2">
              <h3 className="text-lg font-bold text-slate-900 mb-4">范围调整影响</h3>
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
