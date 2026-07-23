import type { TFunction } from 'i18next';

export function getStageStatusLabel(item: any, t: TFunction): string {
  const key = `stageProgress.status.${item?.statusCode || 'in_progress'}`;
  const value = t(key);
  return value === key ? item?.statusLabel || '' : value;
}

export function getStageCheckMessage(check: any, t: TFunction): string {
  if (!check) return '';
  const key = `stageProgress.checks.${check.code}`;
  const value = t(key);
  return value === key ? check.message || '' : value;
}

export function getStageNextActionLabel(action: any, t: TFunction): string {
  if (!action) return '';
  const kind = action.kind === 'stage_transition' ? 'request_transition' : action.kind || 'none';
  const key = `stageProgress.actions.${kind}`;
  const value = t(key);
  return value === key ? action.label || '' : value;
}
