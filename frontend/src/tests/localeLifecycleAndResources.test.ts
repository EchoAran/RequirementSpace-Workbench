import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import enUS from '../locales/en-US.json';
import zhCN from '../locales/zh-CN.json';
import {
  applyUiLocale,
  DEFAULT_UI_LOCALE,
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

    await resetUiLocale();
    expect(localStorage.getItem('ui_locale')).toBe(DEFAULT_UI_LOCALE);
    expect(document.documentElement.lang).toBe(DEFAULT_UI_LOCALE);
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

  it('localizes backend finding and stage-progress codes without using server text', async () => {
    await applyUiLocale('en-US');
    expect(getFindingText({
      code: 'STAGE_LOCKED',
      title: '阶段尚未解锁',
      description: '请先完成上一阶段',
    }, i18n.t)).toEqual({
      title: 'Stage Not Unlocked',
      description: 'Complete and confirm the previous stage before entering this stage.',
    });
    expect(getStageStatusLabel({ statusCode: 'analysis_running', statusLabel: '分析中' }, i18n.t))
      .toBe('AI Analysis in Progress');
    expect(getStageCheckMessage({ code: 'invalid_step_actor', message: '角色无效' }, i18n.t))
      .toBe('Some flow steps reference invalid actors.');
    await resetUiLocale();
  });
});
