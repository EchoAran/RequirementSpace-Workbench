import { useState } from 'react';
import { NodeKindToText } from '@/core/schema';
import { StatusBadge } from './StatusBadge';

interface DragItem {
  id: string;
  title: string;
  kind?: string;
  status?: string;
  scopeStatus?: string;
  parentModuleName?: string;
  scope?: {
    kind: 'scope';
    scopeId: number;
    scopeStatus: string;
    reason: string;
    positiveSummary: string | null;
    negativeSummary: string | null;
    positivePictureBase64: string | null;
    negativePictureBase64: string | null;
  };
}

interface ColumnProps {
  columnKey: string;
  title: string;
  items: DragItem[];
  moveTargets: Array<{ key: string; label: string; danger?: boolean }>;
  highlightTarget?: string | null;
  selectedTarget?: string | null;
  onItemClick: (item: DragItem) => void;
  onMoveItem: (itemId: string, targetKey: string) => void;
  onAddItem?: (columnKey: string) => void;
}

export function RangeKanbanColumn({ columnKey, title, items, moveTargets, highlightTarget, selectedTarget, onItemClick, onMoveItem, onAddItem }: ColumnProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [activeKanoItem, setActiveKanoItem] = useState<DragItem | null>(null);

  // Heuristic to get original AI recommended status based on generated summaries
  const getOriginalAiRecommendation = (item: DragItem) => {
    if (!item.scope) return null;
    const { positiveSummary, negativeSummary } = item.scope;
    if (positiveSummary && !negativeSummary) return '本期';
    if (negativeSummary && !positiveSummary) return '暂缓';
    return null;
  };

  const currentColumnLabel = columnKey === 'current' ? '本期' : columnKey === 'postponed' ? '暂缓' : '排除';

  return (
    <div 
      onDragOver={(e) => e.preventDefault()}
      onDragEnter={() => setIsDragOver(true)}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsDragOver(false);
        const itemId = e.dataTransfer.getData('itemId');
        const source = e.dataTransfer.getData('sourceColumn');
        if (columnKey === 'undecided' && source && source !== 'undecided') {
          return;
        }
        if (itemId && source !== columnKey) {
          onMoveItem(itemId, columnKey);
        }
      }}
      className={`rounded-xl p-3 flex flex-col gap-3 min-h-[450px] transition-all border-2 ${
        isDragOver 
          ? 'border-dashed border-indigo-400 bg-indigo-50/40 animate-pulse shadow-inner' 
          : 'border-transparent bg-slate-100/50'
      }`}
    >
      <h4 className="font-bold text-slate-700 text-sm flex justify-between items-center px-1">
        {title}
        <span className="bg-slate-200/80 text-slate-600 text-xs px-2.5 py-0.5 rounded-full font-bold">{items.length}</span>
      </h4>
      
      <div className="space-y-3">
        {items.map(item => {
          const originalAiRec = getOriginalAiRecommendation(item);
          const isOverridden = originalAiRec && originalAiRec !== currentColumnLabel;

          return (
            <div
              key={item.id}
              id={`scope-${item.id}`}
              onClick={() => onItemClick(item)}
              draggable={true}
              onDragStart={(e) => {
                e.dataTransfer.setData('itemId', item.id);
                e.dataTransfer.setData('sourceColumn', columnKey);
              }}
              className={`group bg-white rounded-xl p-4 shadow-[0_1px_3px_rgba(0,0,0,0.05)] border cursor-grab active:cursor-grabbing transition-all select-none ${
                selectedTarget === item.id 
                  ? 'ring-2 ring-indigo-500 border-transparent shadow-md' 
                  : 'border-slate-200/80 hover:border-indigo-300 hover:shadow-md'
              } ${highlightTarget === item.id ? 'ring-2 ring-amber-400' : ''}`}
            >
              <div className="mb-2 flex flex-wrap gap-1">
                {item.parentModuleName && (
                  <span className="inline-block text-[10px] bg-indigo-50/60 text-indigo-600 font-extrabold px-2 py-0.5 rounded shadow-sm border border-indigo-100/20">
                    模块: {item.parentModuleName}
                  </span>
                )}
              </div>
              
              <div className="flex justify-between items-start gap-2 relative">
                <h5 className={`text-sm font-bold leading-snug ${
                  columnKey === 'exclude' ? 'line-through text-slate-400' : 'text-slate-900'
                }`}>
                  {item.title}
                </h5>
              </div>

              {item.scope && (
                item.scope.positiveSummary ||
                item.scope.negativeSummary ||
                item.scope.positivePictureBase64 ||
                item.scope.negativePictureBase64
              ) && (
                <div className="mt-2.5 flex flex-col gap-2">
                  {isOverridden && (
                    <span className="inline-flex items-center gap-1 text-[10px] bg-amber-50 border border-amber-100 text-amber-700 font-extrabold px-2 py-0.5 rounded w-fit select-none">
                      ⚠️ 已手动覆盖 AI 原推荐 ({originalAiRec})
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setActiveKanoItem(item);
                    }}
                    className="w-full py-1.5 px-3 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-[10px] font-extrabold transition-colors border border-indigo-100/50 flex items-center justify-center gap-1 shadow-sm select-none"
                  >
                    📊 查看 Kano 分析评估
                  </button>
                </div>
              )}
              
              <div className="mt-3 pt-3 border-t border-slate-100 flex flex-wrap gap-1.5 items-center justify-between">
                <div className="w-full flex justify-between items-center">
                  {item.status ? <StatusBadge status={item.status} /> : <span />}
                  {item.kind && <span className="text-[10px] text-slate-400 italic">{NodeKindToText[item.kind as keyof typeof NodeKindToText] || item.kind}</span>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      
      {/* Kano Modal Pop-up */}
      {activeKanoItem && activeKanoItem.scope && (
        <div 
          className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4 select-none animate-in fade-in duration-200"
          onClick={() => setActiveKanoItem(null)}
        >
          <div 
            className="bg-white/95 border border-slate-200 shadow-2xl max-w-3xl w-full flex flex-col rounded-3xl animate-in zoom-in-95 duration-200 max-h-[85vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="p-6 pb-4 border-b border-slate-100 bg-slate-50/50 shrink-0 flex justify-between items-start">
              <div>
                <h3 className="font-extrabold text-sm text-slate-800 flex items-center gap-2">
                  <span>📊</span> Kano 智能决策分析报告：{activeKanoItem.title}
                </h3>
                {activeKanoItem.parentModuleName && (
                  <p className="text-[10px] text-indigo-600 font-bold mt-1">所属模块：{activeKanoItem.parentModuleName}</p>
                )}
              </div>
              <button 
                type="button"
                onClick={() => setActiveKanoItem(null)}
                className="text-slate-400 hover:text-slate-600 bg-white border border-slate-200 hover:bg-slate-50 shadow-sm w-6 h-6 rounded-full flex items-center justify-center transition-all text-xs font-bold"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6 text-xs text-slate-600 leading-normal">
              {/* Row 1: Positive and Negative Summaries */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {activeKanoItem.scope.positiveSummary && (
                  <div className="bg-emerald-50/30 border border-emerald-100 rounded-2xl p-4 flex flex-col gap-2">
                    <span className="font-extrabold text-emerald-800 flex items-center gap-1 text-xs uppercase tracking-wider">
                      💡 有该功能时的用户感受
                    </span>
                    <div className="text-slate-700 bg-white/70 border border-emerald-100/50 p-3 rounded-xl italic leading-relaxed">
                      "{activeKanoItem.scope.positiveSummary}"
                    </div>
                  </div>
                )}

                {activeKanoItem.scope.negativeSummary && (
                  <div className="bg-rose-50/30 border border-rose-100 rounded-2xl p-4 flex flex-col gap-2">
                    <span className="font-extrabold text-rose-800 flex items-center gap-1 text-xs uppercase tracking-wider">
                      ⚠️ 缺少该功能时的用户感受
                    </span>
                    <div className="text-slate-700 bg-white/70 border border-rose-100/50 p-3 rounded-xl italic leading-relaxed">
                      "{activeKanoItem.scope.negativeSummary}"
                    </div>
                  </div>
                )}
              </div>

              {/* Row 2: Kano Pictures */}
              {(activeKanoItem.scope.positivePictureBase64 || activeKanoItem.scope.negativePictureBase64) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-slate-100">
                  {activeKanoItem.scope.positivePictureBase64 && (
                    <div className="space-y-2">
                      <span className="font-extrabold text-indigo-700 flex items-center gap-1 text-xs">
                        📊 有该功能时的体验影响图
                      </span>
                      <div className="border border-slate-200 rounded-2xl overflow-hidden bg-white max-h-[300px] flex items-center justify-center p-3 shadow-md">
                        <img 
                          src={`data:image/png;base64,${activeKanoItem.scope.positivePictureBase64}`} 
                          alt="AI Positive Chart" 
                          className="max-h-full max-w-full object-contain"
                        />
                      </div>
                    </div>
                  )}

                  {activeKanoItem.scope.negativePictureBase64 && (
                    <div className="space-y-2">
                      <span className="font-extrabold text-slate-700 flex items-center gap-1 text-xs">
                        📉 缺少该功能时的体验影响图
                      </span>
                      <div className="border border-slate-200 rounded-2xl overflow-hidden bg-white max-h-[300px] flex items-center justify-center p-3 shadow-md">
                        <img 
                          src={`data:image/png;base64,${activeKanoItem.scope.negativePictureBase64}`} 
                          alt="AI Negative Chart" 
                          className="max-h-full max-w-full object-contain"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Decision Reason Details */}
              {activeKanoItem.scope.reason && (
                <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 space-y-1.5">
                  <span className="font-extrabold text-slate-700 text-[10px] uppercase tracking-wider block">决策依据与论证</span>
                  <p className="text-slate-600 font-medium leading-relaxed">{activeKanoItem.scope.reason}</p>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-6 pt-4 border-t border-slate-100 flex justify-end bg-slate-50/30 shrink-0">
              <button
                type="button"
                onClick={() => setActiveKanoItem(null)}
                className="px-5 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-xl transition-colors shadow-sm font-semibold"
              >
                关闭报告
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
