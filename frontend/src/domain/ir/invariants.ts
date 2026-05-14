import type { RequirementSpaceIR } from '@/types';
import { isLinkAllowed } from './linkRules';

export type InvariantViolation = {
  code: string;
  message: string;
  details?: Record<string, unknown>;
};

export const validateInvariants = (ir: RequirementSpaceIR): InvariantViolation[] => {
  const violations: InvariantViolation[] = [];
  const nodes = ir.nodes || {};
  const nodeIds = new Set(Object.keys(nodes));

  for (const l of ir.links || []) {
    if (!nodeIds.has(l.sourceId)) {
      violations.push({ code: 'LINK_SOURCE_MISSING', message: `Link ${l.id} sourceId 不存在`, details: { linkId: l.id } });
      continue;
    }
    if (!nodeIds.has(l.targetId)) {
      violations.push({ code: 'LINK_TARGET_MISSING', message: `Link ${l.id} targetId 不存在`, details: { linkId: l.id } });
      continue;
    }
    const sk = nodes[l.sourceId]?.kind;
    const tk = nodes[l.targetId]?.kind;
    if (sk && tk && !isLinkAllowed(l.type as any, sk as any, tk as any)) {
      violations.push({
        code: 'LINK_KIND_MISMATCH',
        message: `Link ${l.id} 不允许 ${sk} -> ${tk} (${l.type})`,
        details: { linkId: l.id, type: l.type, sourceKind: sk, targetKind: tk },
      });
    }
  }

  for (const n of Object.values(nodes)) {
    if ((n as any).scopeStatus === 'excluded') {
      violations.push({ code: 'SCOPE_EXCLUDED', message: `Node ${n.id} scopeStatus=excluded 不允许，应使用 status=excluded` });
    }
  }

  return violations;
};

