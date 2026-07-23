import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import zhCN from './locales/zh-CN.json';
import enUS from './locales/en-US.json';

export const DEFAULT_UI_LOCALE = 'zh-CN' as const;
export const UI_LOCALES = ['zh-CN', 'en-US'] as const;
export type UiLocale = typeof UI_LOCALES[number];

export function normalizeUiLocale(value: unknown): UiLocale {
  return UI_LOCALES.includes(value as UiLocale) ? value as UiLocale : DEFAULT_UI_LOCALE;
}

const cachedLocale = normalizeUiLocale(localStorage.getItem('ui_locale'));

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

export async function applyUiLocale(value: unknown): Promise<UiLocale> {
  const locale = normalizeUiLocale(value);
  localStorage.setItem('ui_locale', locale);
  document.documentElement.lang = locale;
  await i18n.changeLanguage(locale);
  return locale;
}

export async function resetUiLocale(): Promise<void> {
  await applyUiLocale(DEFAULT_UI_LOCALE);
}

export default i18n;
