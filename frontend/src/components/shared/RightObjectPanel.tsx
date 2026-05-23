import React, { useState, useEffect } from 'react';
import { Choice, ChoiceGroup, Issue, Proposal, RequirementSpaceIR, RequirementSlot } from '@/core/schema';
import { selectSelectedObject, useWorkspaceStore } from '@/store/useWorkspaceStore';
import { ChoiceGroupPanel } from '../right-panel/ChoiceGroupPanel';
import { ChoicePanel } from '../right-panel/ChoicePanel';
import { IssuePanel } from '../right-panel/IssuePanel';
import { NodePanel } from '../right-panel/NodePanel';
import { PanelShell } from '../right-panel/shared';
import { ProposalPanel } from '../right-panel/ProposalPanel';
import { SlotPanel } from '../right-panel/SlotPanel';
import { ChevronLeft, ChevronRight } from 'lucide-react';

const findChoiceById = (ir: RequirementSpaceIR | null, choiceId: string | null): Choice | null => {
  if (!ir || !choiceId) return null;
  for (const group of Object.values(ir.choiceGroups || {})) {
    const choice = (group.choices || []).find((item) => item.id === choiceId);
    if (choice) return choice;
  }
  return null;
};

export function RightObjectPanel() {
  const ir = useWorkspaceStore((state) => state.ir);
  const selectedObject: any = useWorkspaceStore(selectSelectedObject);

  // Local storage persistence for premium user experience
  const [width, setWidth] = useState(() => {
    const saved = localStorage.getItem('right-panel-width');
    return saved ? parseInt(saved, 10) : 360;
  });
  const [collapsed, setCollapsed] = useState(() => {
    const saved = localStorage.getItem('right-panel-collapsed');
    return saved === 'true';
  });

  const [isResizing, setIsResizing] = useState(false);

  const handleWidthChange = (newWidth: number) => {
    const clamped = Math.max(300, Math.min(600, newWidth));
    setWidth(clamped);
    localStorage.setItem('right-panel-width', clamped.toString());
  };

  const handleCollapsedChange = (newCollapsed: boolean) => {
    setCollapsed(newCollapsed);
    localStorage.setItem('right-panel-collapsed', newCollapsed.toString());
  };

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      // The panel is on the right, so as mouse X increases (moves right), width decreases
      const newWidth = window.innerWidth - e.clientX;
      handleWidthChange(newWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  if (!ir) return null;

  const renderContent = () => {
    if (!selectedObject) {
      return (
        <PanelShell title="选择一个对象" subtitle="Inspector">
          <div className="text-sm text-slate-500 leading-relaxed">
            右侧面板统一审阅和编辑 Node、Issue、Slot、ChoiceGroup、Choice、Proposal。
          </div>
        </PanelShell>
      );
    }

    // Adapt to cases where selectedObject has perceptionSlotId instead of id (like Slots)
    const objId = selectedObject.id || selectedObject.perceptionSlotId?.toString();

    if (objId) {
      if (ir.nodes && ir.nodes[objId]) {
        return <NodePanel node={ir.nodes[objId]} ir={ir} />;
      }
      if (ir.issues && ir.issues[objId]) {
        return <IssuePanel issue={ir.issues[objId] as Issue} ir={ir} />;
      }
      if (ir.slots && ir.slots[objId]) {
        return <SlotPanel slot={ir.slots[objId] as RequirementSlot} ir={ir} />;
      }
      if (ir.choiceGroups && ir.choiceGroups[objId]) {
        return <ChoiceGroupPanel choiceGroup={ir.choiceGroups[objId] as ChoiceGroup} ir={ir} />;
      }
      if (ir.proposals && ir.proposals[objId]) {
        return <ProposalPanel proposal={ir.proposals[objId] as Proposal} ir={ir} />;
      }

      const choice = findChoiceById(ir, objId);
      if (choice) {
        return <ChoicePanel choice={choice} ir={ir} />;
      }
    }

    return (
      <PanelShell title={selectedObject.title || selectedObject.name || selectedObject.id || '未知对象'} subtitle="Inspector">
        <pre className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 overflow-auto">
          {JSON.stringify(selectedObject, null, 2)}
        </pre>
      </PanelShell>
    );
  };

  return (
    <div
      className={`relative shrink-0 transition-all duration-300 flex bg-white ${
        collapsed ? '' : 'border-l border-slate-200'
      }`}
      style={{
        width: collapsed ? '0px' : `${width}px`,
      }}
    >
      {/* Resizing Handle */}
      {!collapsed && (
        <div
          onMouseDown={(e) => {
            e.preventDefault();
            setIsResizing(true);
          }}
          className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-indigo-500/20 active:bg-indigo-500 transition-colors z-30"
          style={{ transform: 'translateX(-50%)' }}
        />
      )}

      {/* Collapse/Expand Toggle Button aligned with LeftNav collapse button */}
      <button
        onClick={() => handleCollapsedChange(!collapsed)}
        className="absolute -translate-y-1/2 bg-white border border-slate-200 rounded-full w-6 h-6 flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-300 shadow-sm hover:shadow z-40 transition-all"
        style={{ 
          top: 'calc(50vh - 2rem)',
          left: collapsed ? '-36px' : '-12px'
        }}
        title={collapsed ? '展开面板' : '折叠面板'}
      >
        {collapsed ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
      </button>

      {/* Actual Panel Content */}
      <div className="w-full h-full overflow-hidden bg-white">
        {renderContent()}
      </div>
    </div>
  );
}
