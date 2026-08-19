import { useTranslation } from 'react-i18next';
import { GitBranch, GitCommitHorizontal, ShieldCheck, GitPullRequest, CircleSlash2 } from 'lucide-react';

interface GuidanceCard {
  key: string;
  icon: React.ComponentType<{ className?: string }>;
  titleKey: string;
  bodyKey: string;
}

const CARDS: GuidanceCard[] = [
  { key: 'baselineMeaning', icon: GitCommitHorizontal, titleKey: 'versionControl.guide.baselineMeaning.title', bodyKey: 'versionControl.guide.baselineMeaning.body' },
  { key: 'whenToBranch', icon: GitBranch, titleKey: 'versionControl.guide.whenToBranch.title', bodyKey: 'versionControl.guide.whenToBranch.body' },
  { key: 'mainProtection', icon: ShieldCheck, titleKey: 'versionControl.guide.mainProtection.title', bodyKey: 'versionControl.guide.mainProtection.body' },
  { key: 'mrApproval', icon: GitPullRequest, titleKey: 'versionControl.guide.mrApproval.title', bodyKey: 'versionControl.guide.mrApproval.body' },
  { key: 'unsupportedGitFeatures', icon: CircleSlash2, titleKey: 'versionControl.guide.unsupportedGitFeatures.title', bodyKey: 'versionControl.guide.unsupportedGitFeatures.body' },
];

/**
 * 版本控制引导卡片（阶段 7）。
 * 展示基线含义、何时建分支、main 保护、MR 审批与不支持的 Git 功能，帮助团队理解版本管理规则。
 */
export function VersionControlGuidance() {
  const { t } = useTranslation();
  return (
    <div className="rounded-2xl border border-indigo-100 border-l-4 border-l-indigo-500 bg-white p-4 shadow-sm">
      <p className="mb-3 text-xs font-black text-slate-700">{t('versionControl.guide.title')}</p>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {CARDS.map((card) => {
          const Icon = card.icon;
          return (
            <div key={card.key} className="rounded-xl border border-slate-100 bg-slate-50/50 p-3">
              <div className="flex items-center gap-1.5">
                <Icon className="h-3.5 w-3.5 text-indigo-600" />
                <p className="text-xs font-bold text-slate-800">{t(card.titleKey)}</p>
              </div>
              <p className="mt-1.5 text-[11px] leading-relaxed text-slate-500">{t(card.bodyKey)}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
