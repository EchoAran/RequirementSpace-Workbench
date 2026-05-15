import { FileText, GitBranch, MessageSquare, CheckSquare, Info } from 'lucide-react';

export interface ImpactGroup {
  type: 'process' | 'page' | 'gap_add' | 'gap_resolve' | 'info';
  title: string;
  items: string[];
}

export function ImpactPreview({ impacts }: { impacts: ImpactGroup[] }) {
  if (!impacts || impacts.length === 0) {
    return (
      <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 h-full flex items-center justify-center">
        <p className="text-xs text-slate-400 italic">选择范围动作后查看 GraphPatch 影响预览</p>
      </div>
    );
  }

  const getIcon = (type: string) => {
    switch (type) {
      case 'process': return <GitBranch className="w-3.5 h-3.5 text-slate-500" />;
      case 'page': return <FileText className="w-3.5 h-3.5 text-slate-500" />;
      case 'gap_add': return <MessageSquare className="w-3.5 h-3.5 text-slate-500" />;
      case 'gap_resolve': return <CheckSquare className="w-3.5 h-3.5 text-slate-500" />;
      default: return <Info className="w-3.5 h-3.5 text-slate-400" />;
    }
  };

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-4">Patch 影响预览</h4>
      <div className="space-y-4">
        {impacts.map((group, idx) => (
          <div key={idx} className="space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700">
              {getIcon(group.type)}
              <span>{group.title}</span>
            </div>
            <ul className="space-y-1.5 pl-6">
              {group.items.map((item, i) => (
                <li key={i} className="text-xs text-slate-600 flex items-start gap-1.5">
                  <span className="w-1 h-1 rounded-full bg-slate-300 mt-1.5 shrink-0"></span>
                  <span className="leading-relaxed">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
