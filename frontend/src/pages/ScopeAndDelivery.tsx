import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { RangeKanbanColumn } from '@/components/shared/RangeKanbanColumn';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { ImpactPreview, ImpactGroup } from '@/components/shared/ImpactPreview';
import { workspaceApi } from '@/lib/api';
import { Sparkles, Check, X, RefreshCw, CheckSquare } from 'lucide-react';
import { 
  useWorkspaceStore, 
  selectScopeItems
} from '@/store/useWorkspaceStore';
import { groupScopeItems } from '@/core/selectors';

const SCOPE_COLUMNS = [
  { key: 'in_scope', label: '本期包含' },
  { key: 'deferred', label: '暂缓处理' },
  { key: 'excluded', label: '已排除', danger: true },
] as const;

export function ScopeAndDelivery() {
  const navigate = useNavigate();
  const { 
    selectedObject, highlightTarget,
    setSelectedObject, ir, updateScope, addFeature,
    generateScope, confirmScope, discardDraft,
    activeDraft, activeDraftType, isGenerating, isLoading
  } = useWorkspaceStore();
  
  const scopeItems = useWorkspaceStore(selectScopeItems);
  const [impactGroups, setImpactGroups] = useState<ImpactGroup[]>([]);
  const [pendingMove, setPendingMove] = useState<{ itemId: string; targetKey: string } | null>(null);
  const [pendingMoveLabel, setPendingMoveLabel] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Group items based on our three-column status mapping
  const grouped = ir ? groupScopeItems(ir) : { inScope: [], deferred: [], excluded: [] };
  const inScope = grouped.inScope;
  const deferred = grouped.deferred;
  const excluded = grouped.excluded;

  const totalLeafs = inScope.length + deferred.length + excluded.length;
  const isScopeComplete = totalLeafs > 0;

  if (!isScopeComplete) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 bg-slate-50 min-h-[80vh] w-full">
        <div className="max-w-md w-full bg-white rounded-3xl p-8 border border-slate-200 shadow-lg text-center space-y-6 animate-in fade-in duration-300">
          <div className="mx-auto w-16 h-16 rounded-2xl bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-500 shadow-sm animate-pulse">
            <CheckSquare className="w-8 h-8" />
          </div>
          <div className="space-y-2">
            <h3 className="text-lg font-black text-slate-900 tracking-tight">范围决策前置依赖未满足</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              交付范围的划分 (Scope) 是针对核心特征树中的<b>三级具体功能点 (叶子节点)</b> 进行本期、暂缓或排除边界决策的。
            </p>
            <p className="text-xs text-slate-400 leading-relaxed bg-slate-50 p-3 rounded-xl border border-slate-100/60">
              当前项目树中尚未包含任何三级叶子节点，交付范围板将处于空白。请先前往 <b>“要做什么 (What)”</b> 页面中至少为功能模块添加一个具体功能点。
            </p>
          </div>
          <button
            onClick={() => navigate('/what')}
            className="w-full py-2.5 px-4 rounded-xl bg-slate-900 text-white text-xs font-bold hover:bg-slate-800 transition-colors shadow-sm"
          >
            → 前往 What 阶段完善特征树结构
          </button>
        </div>
      </div>
    );
  }

  const buildImpactGroups = (resp: any): ImpactGroup[] => {
    const groups: ImpactGroup[] = [];
    if (resp.affected_scenarios_count > 0) {
      groups.push({
        type: 'info',
        title: `影响 ${resp.affected_scenarios_count} 个验收场景 (User Story)`,
        items: [`关联的典型用户场景将会相应归档或恢复`]
      });
    }
    if (resp.affected_flows_count > 0) {
      groups.push({
        type: 'process',
        title: `涉及 ${resp.affected_flows_count} 个业务流程`,
        items: [`泳道图中的对应执行节点将发生启用状态转变`]
      });
    }
    if (resp.affected_objects_count > 0) {
      groups.push({
        type: 'info',
        title: `影响 ${resp.affected_objects_count} 个业务数据对象`,
        items: [`数据实体的字段及其在关系中的生命周期被改变`]
      });
    }
    return groups;
  };

  const createScopeItem = async (columnKey: string) => {
    const scopeStatus = columnKey === 'deferred' ? '暂缓' : columnKey === 'excluded' ? '排除' : '本期';
    const tempName = `手动功能项-${Math.floor(1000 + Math.random() * 9000)}`;
    
    // Add feature node (default to '本期' containing empty scope)
    await addFeature(tempName, '手动创建的功能模块，可用作产品迭代边界规划。', null);
    
    // Find the feature by name in state and update its scope status if not '本期'
    const space = useWorkspaceStore.getState().ir;
    const created = space?.features.find(f => f.featureName === tempName);
    if (created) {
      if (scopeStatus !== '本期') {
        await updateScope(created.featureId, { scopeStatus });
      }
      setSelectedObject(created);
    }
  };

  const previewScopeMove = async (itemId: string, targetKey: string) => {
    if (!ir?.projectId) return;
    try {
      const resp = await workspaceApi.impactPreview(ir.projectId);
      setPendingMove({ itemId, targetKey });
      setPendingMoveLabel(SCOPE_COLUMNS.find((column) => column.key === targetKey)?.label || targetKey);
      setImpactGroups(buildImpactGroups(resp));
      setPreviewError(null);
    } catch (error) {
      setPreviewError(error instanceof Error ? error.message : '影响分析失败');
    }
  };

  const applyPendingMove = async () => {
    if (!pendingMove) return;
    const { itemId, targetKey } = pendingMove;
    const numId = parseInt(itemId, 10);
    const scopeStatus = targetKey === 'deferred' ? '暂缓' : targetKey === 'excluded' ? '排除' : '本期';
    
    await updateScope(numId, { scopeStatus });
    setPendingMove(null);
    setPendingMoveLabel(null);
    setImpactGroups([]);
  };

  const isWorking = isGenerating || isLoading;

  return (
    <div className="flex-1 flex w-full relative">
      <div className="flex-1 p-6 pb-24 overflow-y-auto">
        <div className="max-w-[1200px] mx-auto space-y-8 animate-in fade-in">
          
          {/* AI Scope Draft Preview Banner */}
          {activeDraft && activeDraftType === 'scope' && (
            <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-6 border border-amber-200/80 shadow-md animate-in slide-in-from-top-4 duration-500 space-y-4">
              <div className="flex justify-between items-start">
                <div className="flex items-center gap-2">
                  <span className="p-1.5 bg-amber-100 text-amber-700 rounded-lg shrink-0">
                    <Sparkles className="w-5 h-5 animate-pulse" />
                  </span>
                  <div>
                    <h3 className="text-base font-bold text-slate-900">AI 推荐的 Kano 范围决策已生成</h3>
                    <p className="text-xs text-slate-500 mt-0.5">AI 基于系统复杂度与业务优先级自动进行了过滤与分析。</p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={confirmScope}
                    disabled={isWorking}
                    className="flex items-center gap-1.5 px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50"
                  >
                    <Check className="w-3.5 h-3.5" />
                    采纳并合并推荐
                  </button>
                  <button
                    onClick={discardDraft}
                    disabled={isWorking}
                    className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                  >
                    <X className="w-3.5 h-3.5" />
                    放弃
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-200/60">
                {activeDraft.scopes?.map((sc: any, idx: number) => (
                  <div key={idx} className="bg-white/80 p-4 rounded-xl border border-slate-200/50 flex flex-col justify-between">
                    <div>
                      <div className="flex justify-between items-center mb-1.5">
                        <h4 className="font-bold text-slate-800 text-xs">{sc.feature_name}</h4>
                        <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${
                          sc.scope_status === '本期'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-100'
                            : sc.scope_status === '暂缓'
                            ? 'bg-sky-50 text-sky-700 border border-sky-100'
                            : 'bg-rose-50 text-rose-700 border border-rose-100'
                        }`}>{sc.scope_status}</span>
                      </div>
                      <p className="text-[11px] text-slate-500 leading-relaxed mb-3">{sc.reason}</p>
                    </div>
                    {sc.positive_summary && (
                      <div className="text-[10px] text-slate-600 bg-slate-50 p-2 rounded-lg border border-slate-100 font-medium">
                        💡 {sc.positive_summary}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <section className="bg-white rounded-3xl p-8 border border-slate-200 shadow-md">
             <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4 mb-8">
               <div>
                  <h2 className="text-xl font-black text-slate-900 tracking-tight mb-2">范围决策板</h2>
                  <p className="text-xs text-slate-500">将识别到的各类功能模块拖动或变更到不同的交付栏位，作为敏捷规划底座。</p>
               </div>
               <button
                 onClick={generateScope}
                 disabled={isWorking}
                 className="flex items-center gap-1.5 text-xs bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold px-4 py-2.5 rounded-xl border border-indigo-100/80 transition-colors shadow-sm disabled:opacity-50"
               >
                 <RefreshCw className={`w-3.5 h-3.5 ${isWorking ? 'animate-spin' : ''}`} />
                 AI 自动划分范围
               </button>
             </div>

             <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                <RangeKanbanColumn 
                  columnKey="in_scope"
                  title="本期包含" 
                  items={inScope} 
                  moveTargets={SCOPE_COLUMNS.map((column) => ({ key: column.key, label: column.label, danger: column.key === 'excluded' }))}
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id?.toString()}
                  onItemClick={(item) => setSelectedObject(item)}
                  onMoveItem={previewScopeMove}
                  onAddItem={createScopeItem}
                />
                <RangeKanbanColumn 
                  columnKey="deferred"
                  title="暂缓处理" 
                  items={deferred} 
                  moveTargets={SCOPE_COLUMNS.map((column) => ({ key: column.key, label: column.label, danger: column.key === 'excluded' }))}
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id?.toString()}
                  onItemClick={(item) => setSelectedObject(item)}
                  onMoveItem={previewScopeMove}
                  onAddItem={createScopeItem}
                />
                <RangeKanbanColumn 
                  columnKey="excluded"
                  title="已排除" 
                  items={excluded} 
                  moveTargets={SCOPE_COLUMNS.map((column) => ({ key: column.key, label: column.label, danger: column.key === 'excluded' }))}
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id?.toString()}
                  onItemClick={(item) => setSelectedObject(item)}
                  onMoveItem={previewScopeMove}
                  onAddItem={createScopeItem}
                />
             </div>
          </section>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <section className="flex flex-col md:col-span-2 bg-white rounded-3xl p-8 border border-slate-200 shadow-md">
              <h3 className="text-base font-black text-slate-900 mb-4 tracking-tight">范围调整影响分析</h3>
              
              {pendingMoveLabel && (
                <div className="mb-6 rounded-2xl border border-sky-100 bg-sky-50/60 p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                  <div>
                    <div className="text-sm font-bold text-sky-900">范围影响评估生成完毕</div>
                    <div className="text-xs text-sky-700 mt-1">确认移动后将变更该功能的交付栏位为：{pendingMoveLabel}。</div>
                  </div>
                  <div className="flex items-center gap-2 self-end shrink-0">
                    <button
                      type="button"
                      onClick={() => { setPendingMove(null); setPendingMoveLabel(null); setImpactGroups([]); }}
                      className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50 transition-colors"
                    >
                      取消
                    </button>
                    <button
                      type="button"
                      onClick={applyPendingMove}
                      className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold text-white hover:bg-slate-800 transition-colors shadow-sm"
                    >
                      确认移动
                    </button>
                  </div>
                </div>
              )}
              
              {previewError && <div className="mb-4 text-xs text-rose-600 font-medium">{previewError}</div>}
              
              <div className="flex-1 min-h-[150px]">
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
