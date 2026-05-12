import { FileText, Database, User, Activity, Layout } from 'lucide-react';
import { cn } from '@/lib/utils';

export type ObjectType = '目标' | '角色' | '流程' | '数据' | '页面' | '任务';

interface ObjectLinkChipsProps {
  objects: { id: string; name: string; type: ObjectType }[];
  onClick?: (id: string) => void;
  className?: string;
}

const IconMap: Record<ObjectType, any> = {
  '目标': Activity,
  '角色': User,
  '流程': Layout,
  '数据': Database,
  '页面': Layout,
  '任务': FileText,
};

export function ObjectLinkChips({ objects, onClick, className }: ObjectLinkChipsProps) {
  return (
    <div className={cn("flex flex-wrap gap-2", className)}>
      {objects.map((obj) => {
        const Icon = IconMap[obj.type] || FileText;
        return (
          <button
            key={obj.id}
            onClick={() => onClick?.(obj.id)}
            className="px-2 py-1 bg-slate-50 text-slate-600 text-[10px] font-medium border border-slate-200 rounded-md hover:bg-slate-100 inline-flex items-center gap-1.5 transition-colors italic"
          >
            <Icon className="h-3 w-3 opacity-50" />
            {obj.name}
          </button>
        );
      })}
    </div>
  );
}
