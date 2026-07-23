import type { TFunction } from 'i18next';
import type { Finding } from './schema';

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
  const title = t(titleKey);
  const description = t(descriptionKey);
  return {
    title: title === titleKey ? finding.title : title,
    description: description === descriptionKey ? finding.description : description,
  };
}
