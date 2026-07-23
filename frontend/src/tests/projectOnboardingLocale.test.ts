import { describe, expect, it } from 'vitest';
import enUS from '@/locales/en-US.json';
import zhCN from '@/locales/zh-CN.json';

const onboardingKeys = [
  'backToHome', 'title', 'processingDraft', 'processingDraftDesc', 'projectNameLabel',
  'projectNamePlaceholder', 'projectDescLabel', 'projectDescPlaceholder', 'promptLabel',
  'promptPlaceholder', 'kbTitle', 'kbNotice', 'kbDragging', 'kbDragDrop', 'kbStatusReady',
  'kbStatusProcessing', 'kbStatusFailed', 'kbRetryTitle', 'kbDeleteTitle', 'btnTalk',
  'btnCreateBlank', 'btnGenerateAIChoiceTooltip', 'btnGenerateAIChoice', 'draftConfirmLabel',
  'warningModal.title', 'warningModal.desc', 'warningModal.wait', 'warningModal.proceed',
];

const valueAt = (source: Record<string, any>, path: string) =>
  path.split('.').reduce<any>((value, key) => value?.[key], source);

describe('project onboarding locale resources', () => {
  it.each(onboardingKeys)('defines onboarding.%s in both locales', (key) => {
    expect(valueAt(enUS.onboarding, key)).toEqual(expect.any(String));
    expect(valueAt(zhCN.onboarding, key)).toEqual(expect.any(String));
  });
});
