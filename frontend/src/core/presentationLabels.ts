import i18n from '@/i18n';
import type { FlowStepType, NodeKind, PerceptionKindType } from './schema';

export const NodeKindToText: Record<NodeKind, string> = new Proxy({} as Record<NodeKind, string>, {
  get: (_target, kind: string) => i18n.t(`nodeKind.${kind}`),
});

export const FlowStepTypeToText: Record<FlowStepType, string> = new Proxy({} as Record<FlowStepType, string>, {
  get: (_target, kind: string) => i18n.t(`flowStepType.${kind}`),
});

const perceptionKeys: Record<PerceptionKindType, string> = {
  '角色结点': 'missing_actor',
  '功能模块结点': 'missing_module',
  '功能叶子结点': 'missing_leaf',
  '场景结点': 'missing_scenario',
  '成功标准结点': 'missing_ac',
  '流程主结点': 'missing_flow',
  '流程步骤结点': 'missing_step',
};

export const PerceptionKindToText: Record<PerceptionKindType, string> = new Proxy(
  {} as Record<PerceptionKindType, string>,
  { get: (_target, kind: PerceptionKindType) => i18n.t(`perceptionKind.${perceptionKeys[kind]}`) },
);

export const NodeStatusToText: Record<string, string> = new Proxy({}, {
  get: (_target, status: string) => i18n.t(`nodeStatus.${status}`),
});

export const ScopeStatusToText: Record<string, string> = new Proxy({}, {
  get: (_target, status: string) => i18n.t(`scopeStatus.${status}`),
  ownKeys: () => [
    'current', 'postponed', 'exclude', 'in_scope', 'deferred',
    'external_dependency', 'out_of_scope', 'excluded',
  ],
  getOwnPropertyDescriptor: () => ({ enumerable: true, configurable: true }),
});

export function getScopeStatusText(status: unknown): string {
  const key = String(status ?? '').trim();
  if (!key) return '';
  return ScopeStatusToText[key] || ScopeStatusToText[key.toLowerCase()] || key;
}
