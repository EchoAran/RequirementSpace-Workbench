import type { i18n as I18n } from 'i18next';
import { getChoiceGenerationStrategyLabel } from './generationStrategyPresentation';

type Translate = (key: string, options?: Record<string, unknown>) => string;

const choiceTypeKeys: Record<string, string> = {
  project: 'overview.decisionQueue.types.projectCreation',
  project_creation: 'overview.decisionQueue.types.projectCreation',
  actor: 'overview.decisionQueue.types.actor',
  feature: 'overview.decisionQueue.types.feature',
  flow: 'overview.decisionQueue.types.flow',
  scenario: 'overview.decisionQueue.types.scenario',
  scenario_generation: 'overview.decisionQueue.types.scenario',
  acceptance_criteria: 'overview.decisionQueue.types.acceptanceCriteria',
  acceptance_criteria_generation: 'overview.decisionQueue.types.acceptanceCriteria',
  ac: 'overview.decisionQueue.types.acceptanceCriteria',
  scope: 'overview.decisionQueue.types.scope',
};

const getChoiceTypeKey = (choice: any) => {
  const rawType = choice?.draftType ?? choice?.draft_type ?? choice?.generationType ?? choice?.generation_type;
  return choiceTypeKeys[String(rawType || '').toLowerCase()];
};

export const getChoiceTypeLabel = (choice: any, t: Translate) => {
  const key = getChoiceTypeKey(choice);
  return key ? t(key) : '';
};

export const getChoicePresentation = (choice: any, t: Translate, i18n: I18n) => {
  const type = getChoiceTypeLabel(choice, t);
  if (!type) {
    return {
      title: choice?.title || t('choiceCard.untitled'),
      rationale: choice?.rationale || t('panel.noDescription'),
    };
  }

  const strategy = getChoiceGenerationStrategyLabel(
    choice?.strategyId ?? choice?.strategy_id,
    choice?.strategyLabel ?? choice?.strategy_label,
    t('choiceCard.defaultStrategy'),
    i18n,
  );
  return {
    title: t('choiceCard.generatedTitle', { type, strategy }),
    rationale: t('choiceCard.generatedRationale', { strategy }),
  };
};
