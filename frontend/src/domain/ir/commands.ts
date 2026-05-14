import type { GraphPatch, LinkType, NodeStatus, ScopeStatus } from '@/types';

export const patchSetNodeStatus = (id: string, status: NodeStatus): GraphPatch => ({
  updateNodes: [{ id, status } as any],
});

export const patchSetNodeScope = (id: string, scopeStatus: ScopeStatus): GraphPatch => ({
  updateNodes: [{ id, scopeStatus } as any],
});

export const patchLink = (link: { id: string; sourceId: string; targetId: string; type: LinkType }): GraphPatch => ({
  addLinks: [
    {
      ...link,
      status: 'active',
      source: { type: 'user' },
    } as any,
  ],
});

