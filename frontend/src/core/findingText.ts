import type { TFunction } from 'i18next';
import type { Finding } from './schema';
import i18n from '@/i18n';

export function getFindingText(
  finding: Pick<Finding, 'code' | 'title' | 'description'>,
  t: TFunction,
): { title: string; description: string } {
  const code = finding.code.endsWith('_PERCEPTION_RUNNING')
    ? 'PERCEPTION_RUNNING'
    : finding.code.endsWith('_PERCEPTION_FAILED')
      ? 'PERCEPTION_FAILED'
      : finding.code;
  const titleKey = `findingText.${code}.title`;
  const descriptionKey = `findingText.${code}.description`;
  const localizedTitle = t(titleKey);
  const localizedDescription = t(descriptionKey);

  const hasLocalizedTitle = localizedTitle !== titleKey && localizedTitle.trim().length > 0;
  const hasLocalizedDescription = localizedDescription !== descriptionKey && localizedDescription.trim().length > 0;

  const isEnglish = (i18n.resolvedLanguage || i18n.language || '').toLowerCase().startsWith('en')
    || (typeof document !== 'undefined' && document.documentElement.lang.toLowerCase().startsWith('en'));

  if (isEnglish) {
    return {
      title: hasLocalizedTitle ? localizedTitle : (finding.title || ''),
      description: hasLocalizedDescription ? localizedDescription : (finding.description || ''),
    };
  }

  return {
    title: finding.title || (hasLocalizedTitle ? localizedTitle : ''),
    description: finding.description || (hasLocalizedDescription ? localizedDescription : ''),
  };
}
