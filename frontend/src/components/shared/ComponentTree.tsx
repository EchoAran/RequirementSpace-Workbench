import { useTranslation } from 'react-i18next';
import { RequirementNode, RequirementLink } from '@/core/schema';
import { ArrowRight, Box, Component, Container, LayoutDashboard } from 'lucide-react';

interface ComponentTreeProps {
  nodes: Record<string, RequirementNode>;
  links: RequirementLink[];
  actorId: string;
  onSelectNode: (node: RequirementNode) => void;
  selectedNodeId?: string;
}

export function ComponentTree({ nodes, links, actorId, onSelectNode, selectedNodeId }: ComponentTreeProps) {
  const { t } = useTranslation();
  // Find all screens for this actor
  const actorScreens = links
    .filter(l => l.targetId === actorId && l.type === 'accessible_by' && (nodes[l.sourceId]?.kind as string) === 'screen')
    .map(l => nodes[l.sourceId]);

  const getChildren = (parentId: string) => {
    return links
      .filter(l => l.sourceId === parentId && l.type === 'contains')
      .map(l => nodes[l.targetId])
      .filter(Boolean);
  };

  const renderTree = (node: RequirementNode, depth: number = 0) => {
    const children = getChildren((node as any).id);
    const isSelected = selectedNodeId === (node as any).id;
    
    return (
      <div key={(node as any).id} className="">
        <div 
          onClick={() => onSelectNode(node)}
          className={`flex items-center gap-2 py-1.5 px-2 rounded-lg cursor-pointer transition-colors ${isSelected ? 'bg-indigo-50 text-indigo-700 font-medium' : 'hover:bg-slate-50 text-slate-600'}`}
          style={{ paddingLeft: `${depth * 1.5 + 0.5}rem` }}
        >
          {(node.kind as string) === 'screen' ? <LayoutDashboard className="w-4 h-4 shrink-0 text-sky-500" /> : <Component className="w-3.5 h-3.5 shrink-0 text-slate-400" />}
          <span className="text-sm">{(node as any).title} {(node.kind as string) === 'screen' && <span className="text-xs text-slate-400 italic font-normal ml-2">{t('componentTree.pageBadge')}</span>}</span>
        </div>
        {children.length > 0 && (
          <div className="mt-1 flex flex-col space-y-0.5 border-l border-slate-100 ml-4">
            {children.map(child => renderTree(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {actorScreens.map(screen => (
        <div key={screen.id} className="bg-white border text-slate-700 border-slate-200 rounded-xl p-4 shadow-sm">
          {renderTree(screen)}
        </div>
      ))}
      {actorScreens.length === 0 && (
        <div className="text-center py-8 text-slate-400 text-sm italic">
          {t('componentTree.emptyTip')}
        </div>
      )}
    </div>
  );
}