import { NodeKindToText } from '@/types';
import { StatusBadge } from './StatusBadge';

interface DragItem {
  id: string;
  title: string;
  kind?: string;
  status: string;
  scopeStatus?: string;
}

interface ColumnProps {
  title: string;
  items: DragItem[];
  highlightTarget?: string | null;
  selectedTarget?: string | null;
  onItemClick: (item: DragItem) => void;
  onMoveItem: (itemId: string, targetCol: any) => void;
  onAddItem?: (column: string) => void;
}

export function RangeKanbanColumn({ title, items, highlightTarget, selectedTarget, onItemClick, onMoveItem, onAddItem }: ColumnProps) {
  return (
    <div className="bg-slate-100/50 rounded-xl p-3 flex flex-col gap-3 min-h-[400px]">
      <h4 className="font-medium text-slate-700 text-sm flex justify-between items-center px-1">
        {title}
        <span className="bg-slate-200 text-slate-600 text-xs px-2 py-0.5 rounded-full">{items.length}</span>
      </h4>
      <div className="space-y-3">
        {items.map(item => (
          <div 
            key={item.id} 
            onClick={() => onItemClick(item)}
            className={`group bg-white rounded-lg p-3 shadow-[0_1px_2px_rgba(0,0,0,0.05)] border cursor-pointer transition-all ${selectedTarget === item.id ? 'ring-2 ring-indigo-500 border-transparent shadow-md' : 'border-slate-200 hover:border-indigo-300'} ${highlightTarget === item.id ? 'ring-2 ring-amber-400' : ''}`}
          >
            <div className="flex justify-between items-start mb-3 gap-2 relative">
              <h5 className={`text-sm font-medium leading-tight pr-6 ${item.scopeStatus === 'excluded' ? 'line-through text-slate-400' : 'text-slate-900'}`}>{item.title}</h5>
              <div className="absolute right-0 top-0 opacity-100 flex flex-col gap-1 z-10 group-hover:opacity-100">
                <div className="relative group/menu">
                  <button className="text-slate-400 hover:text-indigo-600 bg-slate-50 hover:bg-indigo-50 rounded p-1 transition-colors">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg>
                  </button>
                  <div className="absolute right-0 top-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg w-28 py-1 hidden group-hover/menu:block z-50">
                    <div className="px-2 py-1 text-[10px] text-slate-400 font-bold uppercase tracking-wider">移动至</div>
                    {!title.includes('本期包含') && (
                      <button onClick={(e) => { e.stopPropagation(); onMoveItem(item.id, '本期包含'); }} className="w-full text-left px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 hover:text-indigo-600 transition-colors">本期包含</button>
                    )}
                    {!title.includes('暂缓处理') && (
                      <button onClick={(e) => { e.stopPropagation(); onMoveItem(item.id, '暂缓处理'); }} className="w-full text-left px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 hover:text-indigo-600 transition-colors">暂缓处理</button>
                    )}
                    {!title.includes('外部依赖') && (
                      <button onClick={(e) => { e.stopPropagation(); onMoveItem(item.id, '外部依赖'); }} className="w-full text-left px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 hover:text-indigo-600 transition-colors">外部依赖</button>
                    )}
                    {!title.includes('已排除') && (
                      <button onClick={(e) => { e.stopPropagation(); onMoveItem(item.id, '已排除'); }} className="w-full text-left px-3 py-1.5 text-xs text-rose-600 hover:bg-rose-50 transition-colors">已排除</button>
                    )}
                  </div>
                </div>
              </div>
            </div>
            
            <div className="mt-3 pt-3 border-t border-slate-100 flex flex-wrap gap-1.5 items-center justify-between">
              <div className="w-full flex justify-between items-center"><StatusBadge status={item.status} /> {item.kind && <span className="text-[10px] text-slate-400 italic">{NodeKindToText[item.kind] || item.kind}</span>}</div>
            </div>
          </div>
        ))}
      </div>
      <button
        onClick={() => onAddItem?.(title)}
        className="mt-auto flex items-center justify-center py-2 text-sm text-slate-500 border border-dashed border-slate-300 rounded-lg hover:border-slate-400 hover:text-slate-600 hover:bg-slate-50 transition-colors"
      >
        + 添加项
      </button>
    </div>
  )
}
