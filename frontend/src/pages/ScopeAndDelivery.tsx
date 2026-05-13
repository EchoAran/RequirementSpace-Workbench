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

export function ScopeAndDelivery() {
  const { 
    selectedObject, highlightTarget,
    setSelectedObject, moveScopeItem, ir, runDiagnosis, applyPatch
  } = useWorkspaceStore();
  
  const scopeItems = useWorkspaceStore(selectScopeItems);
  const goals = useWorkspaceStore(selectGoals);
  const actors = useWorkspaceStore(selectActors);
  const links = useWorkspaceStore(selectLinks);

  const inScope = scopeItems.filter(i => i.scopeStatus === 'in_scope');
  const deferred = scopeItems.filter(i => i.scopeStatus === 'deferred');
  const dependencies = scopeItems.filter(i => i.scopeStatus === 'external_dependency');
  const excluded = scopeItems.filter(i => i.scopeStatus === 'excluded');

  // Calculate dynamic impact preview if an item is selected
  let impactGroups: ImpactGroup[] = [];
  if (selectedObject && !selectedObject.choices && !selectedObject.gap && ir) {
    const objId = selectedObject.id;
    
    // Find downstream dependencies (where this object is the source or target of links)
    const relatedLinks = links.filter(l => l.sourceId === objId || l.targetId === objId);
    
    if (relatedLinks.length > 0) {
      const affectedFlowIds = relatedLinks.map(l => l.sourceId === objId ? l.targetId : l.sourceId)
                                          .filter(id => ir.nodes[id]?.kind === 'flow_step' || ir.nodes[id]?.kind === 'flow');
      
      const affectedObjIds = relatedLinks.map(l => l.sourceId === objId ? l.targetId : l.sourceId)
                                         .filter(id => ir.nodes[id]?.kind === 'business_object');
      
      const affectedScreenIds = relatedLinks.map(l => l.sourceId === objId ? l.targetId : l.sourceId)
                                           .filter(id => ir.nodes[id]?.kind === 'screen');
      
      // Filter unique
      const uniqFlows = [...new Set(affectedFlowIds)];
      const uniqObjs = [...new Set(affectedObjIds)];
      const uniqScreens = [...new Set(affectedScreenIds)];

      if (uniqFlows.length > 0) {
        impactGroups.push({
          type: 'process',
          title: `影响 ${uniqFlows.length} 个流程/步骤`,
          items: uniqFlows.map(id => ir.nodes[id]?.title || id)
        });
      }

      if (uniqObjs.length > 0) {
        impactGroups.push({
          type: 'info',
          title: `影响 ${uniqObjs.length} 个业务对象`,
          items: uniqObjs.map(id => ir.nodes[id]?.title || id)
        });
      }

      if (uniqScreens.length > 0) {
        impactGroups.push({
          type: 'page',
          title: `影响 ${uniqScreens.length} 个页面`,
          items: uniqScreens.map(id => ir.nodes[id]?.title || id)
        });
      }

      impactGroups.push({
        type: 'gap_add',
        title: '潜在断层风险',
        items: [`若移除该节点，将影响以上关联项的引用一致性`]
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
            : 'excluded';

    const id = `sc_${(globalThis.crypto && 'randomUUID' in globalThis.crypto) ? (globalThis.crypto as any).randomUUID() : String(Date.now())}`;
    await applyPatch({
      addNodes: [
        {
          id,
          kind: 'capability',
          title: '新范围项',
          description: '',
          status: 'needs_confirmation',
          confidence: 0.6,
          scopeStatus,
          source: { type: 'user', text: '手动添加范围项' },
          priority: 'P1',
        } as any,
      ],
    } as any);

    const created = useWorkspaceStore.getState().ir?.nodes?.[id];
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
                 onClick={() => runDiagnosis({ trigger: 'scope_recommendation' })}
                 className="text-sm bg-sky-50 text-sky-600 font-medium px-4 py-2 rounded-xl border border-sky-100 hover:bg-sky-100 transition-colors"
               >
                 自动推荐范围
               </button>
             </div>

             <div className="grid grid-cols-1 xl:grid-cols-4 gap-4 overflow-x-auto">
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
