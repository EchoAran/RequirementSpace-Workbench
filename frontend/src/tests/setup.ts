import { afterEach, beforeEach, vi } from 'vitest';

if (typeof localStorage !== 'undefined') {
  localStorage.setItem('ui_locale', 'zh-CN');
}
if (typeof document !== 'undefined') {
  document.documentElement.lang = 'zh-CN';
}
if (typeof navigator !== 'undefined') {
  Object.defineProperty(navigator, 'language', { value: 'zh-CN', configurable: true });
  Object.defineProperty(navigator, 'languages', { value: ['zh-CN'], configurable: true });
}

const defaultFetch = vi.fn(async () =>
  new Response(JSON.stringify({}), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
);

vi.stubGlobal('fetch', defaultFetch);

vi.mock('react-i18next', () => {
  const fs = require('fs');
  const path = require('path');
  const zhCN = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../locales/zh-CN.json'), 'utf8'));
  const enUS = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../locales/en-US.json'), 'utf8'));
  let locale = 'zh-CN';
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('ui_locale', 'zh-CN');
  }
  if (typeof document !== 'undefined') {
    document.documentElement.lang = 'zh-CN';
  }
  if (typeof navigator !== 'undefined') {
    Object.defineProperty(navigator, 'language', { value: 'zh-CN', configurable: true });
    Object.defineProperty(navigator, 'languages', { value: ['zh-CN'], configurable: true });
  }

  return {
    initReactI18next: {
      type: '3rdParty',
      init: vi.fn(),
    },
    useTranslation: () => ({
      t: (key: string, options?: any) => {
        const parts = key.split('.');
        const activeLocale = (typeof localStorage !== 'undefined' ? localStorage.getItem('ui_locale') : null) || locale || 'zh-CN';
        let current: any = activeLocale === 'en-US' ? enUS : zhCN;
        for (const part of parts) {
          if (current && typeof current === 'object') {
            current = current[part];
          } else {
            current = undefined;
            break;
          }
        }
        if (options?.returnObjects && current !== undefined) {
          return current;
        }

        if (typeof current === 'string') {
          let val = current;
          if (options) {
            for (const [k, v] of Object.entries(options)) {
              val = val.replace(new RegExp(`{{\\s*${k}\\s*}}`, 'g'), String(v));
            }
          }
          return val;
        }
        return key;
      },
      i18n: {
        changeLanguage: vi.fn(async (nextLocale: string) => {
          locale = nextLocale;
          if (typeof localStorage !== 'undefined') {
            localStorage.setItem('ui_locale', nextLocale);
          }
          if (typeof document !== 'undefined') {
            document.documentElement.lang = nextLocale;
          }
          return true;
        }),
        get language() {
          return (typeof localStorage !== 'undefined' ? localStorage.getItem('ui_locale') : null) || locale || 'zh-CN';
        },
      },
    }),
  };
});

afterEach(() => {
  defaultFetch.mockClear();
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('ui_locale', 'zh-CN');
  }
  if (typeof document !== 'undefined') {
    document.documentElement.lang = 'zh-CN';
  }
  if (typeof navigator !== 'undefined') {
    Object.defineProperty(navigator, 'language', { value: 'zh-CN', configurable: true });
    Object.defineProperty(navigator, 'languages', { value: ['zh-CN'], configurable: true });
  }
});
