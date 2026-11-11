import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import zhCN from './locales/zh-CN.json';
import enUS from './locales/en-US.json';

export const DEFAULT_UI_LOCALE = 'zh-CN' as const;
const UI_LOCALES = ['zh-CN', 'en-US'] as const;
export type UiLocale = typeof UI_LOCALES[number];

export function detectSystemLocale(): UiLocale {
  if (typeof navigator !== 'undefined') {
    const candidateLanguages = navigator.languages?.length
      ? navigator.languages
      : (navigator.language ? [navigator.language] : []);
    for (const lang of candidateLanguages) {
      if (!lang) continue;
      const lower = lang.toLowerCase();
      if (lower.startsWith('zh')) {
        return 'zh-CN';
      }
      if (lower.startsWith('en')) {
        return 'en-US';
      }
    }
    if (candidateLanguages.length > 0) {
      return 'en-US';
    }
  }
  return DEFAULT_UI_LOCALE;
}

export function normalizeUiLocale(value: unknown, fallback?: UiLocale): UiLocale {
  if (UI_LOCALES.includes(value as UiLocale)) {
    return value as UiLocale;
  }
  return fallback ?? DEFAULT_UI_LOCALE;
}

export function resolveInitialLocale(): UiLocale {
  const cached = localStorage.getItem('ui_locale');
  if (cached && UI_LOCALES.includes(cached as UiLocale)) {
    return cached as UiLocale;
  }
  return detectSystemLocale();
}

export function syncDocumentTitle(locale?: string): void {
  const currentLocale = locale || i18n.language || resolveInitialLocale();
  const fallback = currentLocale.startsWith('zh') ? '需求空间工作台' : 'Requirement Workspace';
  const title = (i18n.isInitialized && i18n.t('nav.title', { lng: currentLocale })) || fallback;
  if (typeof document !== 'undefined') {
    document.title = title;
  }
}

const cachedLocale = resolveInitialLocale();

i18n
  .use(initReactI18next)
  .init({
    resources: {
      'zh-CN': { translation: zhCN },
      'en-US': { translation: enUS }
    },
    lng: cachedLocale,
    fallbackLng: 'zh-CN',
    interpolation: {
      escapeValue: false // react already safes from xss
    }
  });

document.documentElement.lang = cachedLocale;
syncDocumentTitle(cachedLocale);

i18n.on('languageChanged', (lng) => {
  document.documentElement.lang = lng;
  syncDocumentTitle(lng);
});

export async function applyUiLocale(value: unknown): Promise<UiLocale> {
  const locale = normalizeUiLocale(value, detectSystemLocale());
  localStorage.setItem('ui_locale', locale);
  document.documentElement.lang = locale;
  await i18n.changeLanguage(locale);
  syncDocumentTitle(locale);
  return locale;
}

export async function resetUiLocale(): Promise<void> {
  await applyUiLocale(detectSystemLocale());
}

export default i18n;

