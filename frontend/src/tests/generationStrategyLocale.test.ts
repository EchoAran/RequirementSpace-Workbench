import { beforeEach, describe, expect, it } from 'vitest';
import i18n from '../i18n';
import {
  getChoiceGenerationStrategyLabel,
  getGenerationStrategyPresentation,
} from '../core/generationStrategyPresentation';

describe('generation strategy localization', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en-US');
  });

  it('localizes built-in strategy fields', () => {
    const presentation = getGenerationStrategyPresentation({
      id: 'balanced',
      is_builtin: true,
      label: '均衡版',
      description: '中文描述',
      instruction: '中文系统指令',
    }, i18n.t);

    expect(presentation.label).toBe('Balanced');
    expect(presentation.description).toContain('Balance functional completeness');
    expect(presentation.instruction).toContain('core business actors');
  });

  it('preserves user-authored strategy fields verbatim', () => {
    const presentation = getGenerationStrategyPresentation({
      id: 'custom_1',
      is_builtin: false,
      label: '我的策略',
      description: '用户输入的描述',
      instruction: '用户输入的策略指令保持原样',
    }, i18n.t);

    expect(presentation).toEqual({
      label: '我的策略',
      description: '用户输入的描述',
      instruction: '用户输入的策略指令保持原样',
    });
  });

  it('does not translate an unknown strategy even when its flag is invalid', () => {
    const presentation = getGenerationStrategyPresentation({
      id: 'custom_1',
      is_builtin: true,
      label: 'My custom strategy',
      description: 'Custom description',
      instruction: 'Custom instruction',
    }, i18n.t);

    expect(presentation.label).toBe('My custom strategy');
  });

  it('localizes stored built-in labels but preserves edited labels', () => {
    expect(getChoiceGenerationStrategyLabel('balanced', '均衡版', 'Plan 1', i18n)).toBe('Balanced');
    expect(getChoiceGenerationStrategyLabel('balanced', '我的均衡策略', 'Plan 1', i18n)).toBe('我的均衡策略');
  });
});
