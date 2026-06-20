import type { Finding, Stage } from '@/core/schema';

export type FindingProjection = 'goal' | 'role' | 'system' | 'data' | 'ui';

export const findingTargetIds = (finding: Finding): string[] => {
  const targetId = finding.target?.targetId ?? finding.target?.target_id;
  return targetId === undefined || targetId === null ? [] : [String(targetId)];
};

export const findingProjection = (finding: Finding): FindingProjection => {
  if (finding.stage === 'how') return 'system';
  if (finding.stage === 'scope') return 'data';
  if (finding.stage === 'preview') return 'ui';
  return 'role';
};

export const findingStage = (finding: Finding): Stage | null => {
  return finding.stage === 'what' || finding.stage === 'how' || finding.stage === 'scope'
    ? finding.stage
    : null;
};

export const findingSeverityLabel = (finding: Finding): 'high' | 'medium' | 'low' => {
  if (finding.severity === 'blocking') return 'high';
  if (finding.severity === 'warning') return 'medium';
  return 'low';
};

export const isCountableFinding = (finding: Finding): boolean => {
  if (finding.type !== 'issue' || finding.severity === 'info') return false;
  return ![
    'ACTOR_WITHOUT_FEATURE',
    'DUPLICATE_SCENARIO_NAME',
    'BUSINESS_OBJECT_WITHOUT_USAGE',
    'BUSINESS_OBJECT_WITHOUT_ATTRIBUTES',
  ].includes(finding.code);
};
