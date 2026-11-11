import { beforeEach, describe, expect, it } from 'vitest';
import i18n from '../i18n';
import { getChoicePresentation } from '../core/choicePresentation';

describe('choice card presentation by UI locale', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en-US');
  });

  it('replaces localized system wrappers without translating project content', () => {
    const presentation = getChoicePresentation({
      draftType: 'actor',
      strategyId: 'balanced',
      strategyLabel: '均衡版',
      title: '均衡版 — 3 名参与者',
      rationale: '按均衡版策略生成的参与者列表',
    }, i18n.t, i18n);

    expect(presentation).toEqual({
      title: 'Actor Scheme — Balanced',
      rationale: 'Generated using the Balanced strategy.',
    });
  });

  it('preserves a user-authored strategy label', () => {
    const presentation = getChoicePresentation({
      draftType: 'feature',
      strategyId: 'custom_1',
      strategyLabel: '我的策略',
      title: '旧系统标题',
      rationale: '旧系统依据',
    }, i18n.t, i18n);

    expect(presentation.title).toBe('Feature Tree Scheme — 我的策略');
    expect(presentation.rationale).toBe('Generated using the 我的策略 strategy.');
  });

  it('preserves domain rationale for non-generation choices', () => {
    const presentation = getChoicePresentation({
      title: 'Resolve checkout conflict',
      rationale: '保留项目内容语言中的业务解释',
    }, i18n.t, i18n);

    expect(presentation.rationale).toBe('保留项目内容语言中的业务解释');
  });
});
