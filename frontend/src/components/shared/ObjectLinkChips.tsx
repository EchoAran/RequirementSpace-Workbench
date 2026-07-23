import { FileText, Database, User, Activity, Layout } from 'lucide-react';
import { cn } from '@/lib/utils';

export type ObjectType = 'goal' | 'actor' | 'flow' | 'data' | 'page' | 'task';

interface ObjectLinkChipsProps {
  objects: { id: string; name: string; type: ObjectType }[];
  onClick?: (id: string) => void;
  className?: string;
}

const IconMap: Record<ObjectType, any> = {
  'goal': Activity,
  'actor': User,
  'flow': Layout,
  'data': Database,
  'page': Layout,
  'task': FileText,
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
