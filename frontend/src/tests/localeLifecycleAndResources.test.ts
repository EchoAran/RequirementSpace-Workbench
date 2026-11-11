import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import enUS from '../locales/en-US.json';
import zhCN from '../locales/zh-CN.json';
import {
  applyUiLocale,
  DEFAULT_UI_LOCALE,
  detectSystemLocale,
  normalizeUiLocale,
  resetUiLocale,
} from '../i18n';
import { resolveLocalizedMessage, taskStatusTitleKey } from '../core/localizedMessage';
import { getFindingText } from '../core/findingText';
import { getStageCheckMessage, getStageStatusLabel } from '../core/stageProgressText';
import i18n from '../i18n';


function flattenKeys(value: unknown, prefix = ''): Set<string> {
  const result = new Set<string>();
  if (!value || typeof value !== 'object' || Array.isArray(value)) return result;
  for (const [key, child] of Object.entries(value)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (child && typeof child === 'object' && !Array.isArray(child)) {
      flattenKeys(child, fullKey).forEach(item => result.add(item));
    } else {
      result.add(fullKey);
    }
  }
  return result;
}


function sourceFiles(root: string): string[] {
  return fs.readdirSync(root, { withFileTypes: true }).flatMap(entry => {
    const fullPath = path.join(root, entry.name);
    if (entry.isDirectory()) {
      return entry.name === 'tests' || entry.name === 'locales' ? [] : sourceFiles(fullPath);
    }
    return /\.(ts|tsx)$/.test(entry.name) ? [fullPath] : [];
  });
}


describe('UI locale lifecycle and resource contracts', () => {
  it('normalizes untrusted locale values and synchronizes document state', async () => {
    expect(normalizeUiLocale('fr-FR')).toBe(DEFAULT_UI_LOCALE);
    await applyUiLocale('en-US');
    expect(localStorage.getItem('ui_locale')).toBe('en-US');
    expect(document.documentElement.lang).toBe('en-US');
    expect(document.title).toBe('Requirement Workspace');

    await applyUiLocale('zh-CN');
    expect(localStorage.getItem('ui_locale')).toBe('zh-CN');
    expect(document.documentElement.lang).toBe('zh-CN');
    expect(document.title).toBe('需求空间工作台');

    await resetUiLocale();
    expect(localStorage.getItem('ui_locale')).toBe(detectSystemLocale());
    expect(document.documentElement.lang).toBe(detectSystemLocale());
    const expectedTitle = detectSystemLocale().startsWith('zh') ? '需求空间工作台' : 'Requirement Workspace';
    expect(document.title).toBe(expectedTitle);
  });

  it('detects system locale based on navigator language', () => {
    const originalLanguage = navigator.language;
    const originalLanguages = navigator.languages;
    try {
      Object.defineProperty(navigator, 'languages', { value: ['en-US'], configurable: true });
      Object.defineProperty(navigator, 'language', { value: 'en-US', configurable: true });
      expect(detectSystemLocale()).toBe('en-US');
      Object.defineProperty(navigator, 'languages', { value: ['zh-CN'], configurable: true });
      Object.defineProperty(navigator, 'language', { value: 'zh-CN', configurable: true });
      expect(detectSystemLocale()).toBe('zh-CN');
    } finally {
      Object.defineProperty(navigator, 'language', { value: originalLanguage, configurable: true });
      Object.defineProperty(navigator, 'languages', { value: originalLanguages, configurable: true });
    }
  });

  it('keeps Chinese and English resource keys symmetric', () => {
    expect([...flattenKeys(enUS)].sort()).toEqual([...flattenKeys(zhCN)].sort());
  });

  it('keeps line breaks in plain-text translations free of HTML markup', () => {
    expect(JSON.stringify(enUS)).not.toMatch(/<br\s*\/?>/i);
    expect(JSON.stringify(zhCN)).not.toMatch(/<br\s*\/?>/i);
    expect(enUS.addObjectDialog.chatTip).toContain('\n');
    expect(zhCN.addObjectDialog.chatTip).toContain('\n');
  });

  it('defines every literal translation key used by production source', () => {
    const resourceKeys = flattenKeys(enUS);
    const missing = new Set<string>();
    const keyPattern = /(?:\bt|\bi18n\.t)\(\s*['"]([^'"]+)['"]/g;
    for (const file of sourceFiles(path.resolve(process.cwd(), 'src'))) {
      const source = fs.readFileSync(file, 'utf8');
      for (const match of source.matchAll(keyPattern)) {
        if (!match[1].endsWith('.') && !resourceKeys.has(match[1])) missing.add(match[1]);
      }
    }
    expect([...missing].sort()).toEqual([]);
  });

  it('defines every stable store message token used by production source', () => {
    const resourceKeys = flattenKeys(enUS);
    const missing = new Set<string>();
    const tokenPattern = /['"](store\.[A-Za-z0-9_.]+)['"]/g;
    for (const file of sourceFiles(path.resolve(process.cwd(), 'src'))) {
      const source = fs.readFileSync(file, 'utf8');
      for (const match of source.matchAll(tokenPattern)) {
        if (!resourceKeys.has(match[1])) missing.add(match[1]);
      }
    }
    expect([...missing].sort()).toEqual([]);
  });

  it('translates stable message keys with interpolation and classifies by key', () => {
    const t = ((key: string, values?: Record<string, string | number>) =>
      key === 'store.actor.createSuccess'
        ? `Actor created: ${values?.name}`
        : key) as any;
    expect(resolveLocalizedMessage(t, 'store.actor.createSuccess', {
      key: 'store.actor.createSuccess',
      values: { name: 'Operator' },
    })).toBe('Actor created: Operator');
    expect(taskStatusTitleKey('store.feature.regeneratingDraft')).toBe('app.generatingDraft');
    expect(taskStatusTitleKey('store.finding.runningDiagnosis')).toBe('app.rediagnosing');
  });

  it('localizes stage-progress codes and prefers i18n dictionary for findings with backend fallback', async () => {
    await applyUiLocale('en-US');
    expect(getFindingText({
      code: 'STAGE_LOCKED',
      title: '阶段尚未解锁',
      description: '请先完成上一阶段',
    }, i18n.t)).toEqual({
      title: 'Stage Not Unlocked',
      description: 'Complete and confirm the previous stage before entering this stage.',
    });
    expect(getFindingText({
      code: 'GENERATE_SCENARIOS',
      title: '生成场景',
      description: '当前项目还没有场景，建议为功能与参与者生成场景。',
    }, i18n.t)).toEqual({
      title: 'Generate Scenarios',
      description: 'There are no scenarios in the project yet. It is recommended to generate scenarios for features and actors.',
    });
    expect(getFindingText({
      code: 'UNKNOWN_CUSTOM_CODE',
      title: '自定义标题',
      description: '自定义描述',
    }, i18n.t)).toEqual({
      title: '自定义标题',
      description: '自定义描述',
    });
    expect(getStageStatusLabel({ statusCode: 'analysis_running', statusLabel: '分析中' }, i18n.t))
      .toBe('AI Analysis in Progress');
    expect(getStageCheckMessage({ code: 'invalid_step_actor', message: '角色无效' }, i18n.t))
      .toBe('Some flow steps reference invalid actors.');
    await applyUiLocale('zh-CN');
  });
});
