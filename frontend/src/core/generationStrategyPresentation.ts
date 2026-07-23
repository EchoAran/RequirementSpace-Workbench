import type { i18n as I18n } from 'i18next';

type Translate = (key: string, options?: Record<string, unknown>) => string;

export interface GenerationStrategyPresentationInput {
  id: string;
  is_builtin?: boolean;
  label: string;
  description?: string;
  instruction: string;
}

const BUILTIN_STRATEGY_IDS = new Set([
  'balanced',
  'comprehensive',
  'minimal',
  'risk_averse',
  'workflow_first',
]);

const strategyKey = (id: string, field: 'label' | 'description' | 'instruction') =>
  `projectConfig.strategies.builtin.${id}.${field}`;

export const isBuiltinGenerationStrategy = (strategy: GenerationStrategyPresentationInput) =>
  strategy.is_builtin === true && BUILTIN_STRATEGY_IDS.has(strategy.id);

export const getGenerationStrategyPresentation = (
  strategy: GenerationStrategyPresentationInput,
  t: Translate,
) => {
  if (!isBuiltinGenerationStrategy(strategy)) {
    return {
      label: strategy.label,
      description: strategy.description || '',
      instruction: strategy.instruction,
    };
  }
  return {
    label: t(strategyKey(strategy.id, 'label')),
    description: t(strategyKey(strategy.id, 'description')),
    instruction: t(strategyKey(strategy.id, 'instruction')),
  };
};

export const getChoiceGenerationStrategyLabel = (
  strategyId: string | undefined,
  rawLabel: string | undefined,
  fallback: string,
  i18n: I18n,
) => {
  if (!strategyId || !BUILTIN_STRATEGY_IDS.has(strategyId)) return rawLabel?.trim() || fallback;
  const labelKey = strategyKey(strategyId, 'label');
  const knownLabels = ['zh-CN', 'en-US'].map((lng) => i18n.t(labelKey, { lng }));
  if (!rawLabel?.trim() || knownLabels.includes(rawLabel)) return i18n.t(labelKey);
  return rawLabel;
};
