import type { TFunction } from 'i18next';

export interface MessageInterpolation {
  key: string;
  values: Record<string, string | number>;
}

export function resolveLocalizedMessage(
  t: TFunction,
  message: string | null,
  interpolation: MessageInterpolation | null = null,
): string {
  if (!message) return '';
  return interpolation?.key === message
    ? t(message, interpolation.values)
    : t(message);
}

export function taskStatusTitleKey(message: string | null): string {
  const key = message?.toLowerCase() ?? '';
  if (key.includes('draft')) return 'app.generatingDraft';
  if (key.includes('diagnos') || key.includes('analysis')) return 'app.rediagnosing';
  if (key.includes('fix') || key.includes('repair')) return 'app.generatingFix';
  if (key.includes('ai') || key.includes('generat') || key.includes('slotfill')) return 'app.aiTaskRunning';
  return 'app.taskRunning';
}
