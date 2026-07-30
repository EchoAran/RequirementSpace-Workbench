import i18n from '@/i18n';
import type { NodeKind } from './schema';

export const NodeKindToText: Record<NodeKind, string> = new Proxy({} as Record<NodeKind, string>, {
  get: (_target, kind: string) => i18n.t(`nodeKind.${kind}`),
});

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
