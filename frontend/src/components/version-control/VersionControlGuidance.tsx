import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  GitBranch,
  GitCommitHorizontal,
  ShieldCheck,
  GitPullRequest,
  CircleSlash2,
  ChevronDown,
  Sparkles,
  RotateCcw,
  Layers,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface GuidanceCard {
  key: string;
  icon: React.ComponentType<{ className?: string }>;
  titleKey: string;
  bodyKey: string;
  badgeKey?: string;
}

const VC_RULES_CARDS: GuidanceCard[] = [
  {
    key: 'baselineMeaning',
    icon: GitCommitHorizontal,
    titleKey: 'versionControl.guide.baselineMeaning.title',
    bodyKey: 'versionControl.guide.baselineMeaning.body',
    badgeKey: 'versionControl.guide.badges.snapshot',
  },
  {
    key: 'whenToBranch',
    icon: GitBranch,
    titleKey: 'versionControl.guide.whenToBranch.title',
    bodyKey: 'versionControl.guide.whenToBranch.body',
    badgeKey: 'versionControl.guide.badges.branchPolicy',
  },
  {
    key: 'mainProtection',
    icon: ShieldCheck,
    titleKey: 'versionControl.guide.mainProtection.title',
    bodyKey: 'versionControl.guide.mainProtection.body',
    badgeKey: 'versionControl.guide.badges.security',
  },
  {
    key: 'mrApproval',
    icon: GitPullRequest,
    titleKey: 'versionControl.guide.mrApproval.title',
    bodyKey: 'versionControl.guide.mrApproval.body',
    badgeKey: 'versionControl.guide.badges.mrReview',
  },
  {
    key: 'unsupportedGitFeatures',
    icon: CircleSlash2,
    titleKey: 'versionControl.guide.unsupportedGitFeatures.title',
    bodyKey: 'versionControl.guide.unsupportedGitFeatures.body',
    badgeKey: 'versionControl.guide.badges.differences',
  },
];

const VC_TIPS_CARDS: GuidanceCard[] = [
  {
    key: 'revertTip',
    icon: RotateCcw,
    titleKey: 'versionControl.guide.tips.revert.title',
    bodyKey: 'versionControl.guide.tips.revert.body',
    badgeKey: 'versionControl.guide.badges.newFeature',
  },
  {
    key: 'stageEvolution',
    icon: Layers,
    titleKey: 'versionControl.guide.tips.stages.title',
    bodyKey: 'versionControl.guide.tips.stages.body',
    badgeKey: 'versionControl.guide.badges.lifecycle',
  },
  {
    key: 'semanticMerge',
    icon: GitPullRequest,
    titleKey: 'versionControl.guide.tips.merge.title',
    bodyKey: 'versionControl.guide.tips.merge.body',
    badgeKey: 'versionControl.guide.badges.conflictResolution',
  },
];

const STORAGE_KEY = 'vc_guidance_collapsed';

/**
 * 趣味交互式版本控制与工作流指南组件。
 * 支持记忆折叠/展开、分类标签页切换与生动图文卡片。
 */
export function VersionControlGuidance({ className }: { className?: string }) {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true';
    } catch {
      return false;
    }
  });
  const [activeTab, setActiveTab] = useState<'rules' | 'tips'>('rules');

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(STORAGE_KEY, String(next));
      } catch {}
      return next;
    });
  };

  return (
    <div
      className={cn(
        'rounded-2xl border border-indigo-100 bg-gradient-to-r from-white via-indigo-50/20 to-white shadow-xs transition-all duration-200 overflow-hidden',
        className
      )}
    >
      {/* 头部栏（始终可见，支持一键收放） */}
      <div
        onClick={toggleCollapsed}
        className="flex items-center justify-between px-4 py-3 cursor-pointer select-none hover:bg-indigo-50/40 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-2xs">
            <Sparkles className="h-3.5 w-3.5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-black text-slate-800">
                {t('versionControl.guide.title', '版本控制与规约协同指南')}
              </span>
              <span className="rounded-full bg-indigo-100/80 px-2 py-0.5 text-[10px] font-bold text-indigo-700">
                💡 {t('versionControl.guide.knowledgeBase', '协作知识库')}
              </span>
            </div>
            {collapsed && (
              <p className="text-[11px] text-slate-400 mt-0.5 line-clamp-1">
                {t('versionControl.guide.collapsedHint', '点击展开基线快照、分支策略、MR 评审及版本回滚等核心操作秘籍...')}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-bold text-indigo-600 hover:bg-indigo-100/50 transition-colors"
          >
            <span>{collapsed ? t('versionControl.guide.expand', '展开指南') : t('versionControl.guide.collapse', '收起')}</span>
            <ChevronDown
              className={cn(
                'h-4 w-4 transition-transform duration-200',
                !collapsed && 'rotate-180'
              )}
            />
          </button>
        </div>
      </div>

      {/* 展开的趣味图文内容区 */}
      {!collapsed && (
        <div className="border-t border-indigo-100/70 p-4 space-y-4 animate-in fade-in duration-150">
          {/* 子分类标签 */}
          <div className="flex items-center gap-1.5 border-b border-slate-100 pb-2.5">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setActiveTab('rules');
              }}
              className={cn(
                'rounded-lg px-3 py-1 text-xs font-bold transition-colors cursor-pointer',
                activeTab === 'rules'
                  ? 'bg-indigo-600 text-white shadow-2xs'
                  : 'text-slate-600 hover:bg-slate-100'
              )}
            >
              {t('versionControl.guide.tabs.rules', '📖 核心协同规则')}
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setActiveTab('tips');
              }}
              className={cn(
                'rounded-lg px-3 py-1 text-xs font-bold transition-colors cursor-pointer',
                activeTab === 'tips'
                  ? 'bg-indigo-600 text-white shadow-2xs'
                  : 'text-slate-600 hover:bg-slate-100'
              )}
            >
              {t('versionControl.guide.tabs.tips', '🚀 实用技巧与回滚')}
            </button>
          </div>

          {/* 卡片栅格 */}
          {activeTab === 'rules' ? (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {VC_RULES_CARDS.map((card) => {
                const Icon = card.icon;
                return (
                  <div
                    key={card.key}
                    className="group relative rounded-xl border border-slate-200/70 bg-white/80 p-3.5 shadow-2xs hover:border-indigo-300 hover:shadow-sm transition-all"
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-1.5">
                        <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                          <Icon className="h-3.5 w-3.5" />
                        </div>
                        <p className="text-xs font-bold text-slate-800">{t(card.titleKey)}</p>
                      </div>
                      {card.badgeKey && (
                        <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[9px] font-bold text-slate-500">
                          {t(card.badgeKey)}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] leading-relaxed text-slate-500 group-hover:text-slate-600 transition-colors">
                      {t(card.bodyKey)}
                    </p>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              {VC_TIPS_CARDS.map((card) => {
                const Icon = card.icon;
                return (
                  <div
                    key={card.key}
                    className="group relative rounded-xl border border-slate-200/70 bg-white/80 p-3.5 shadow-2xs hover:border-indigo-300 hover:shadow-sm transition-all"
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-1.5">
                        <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-amber-50 text-amber-600 group-hover:bg-amber-600 group-hover:text-white transition-colors">
                          <Icon className="h-3.5 w-3.5" />
                        </div>
                        <p className="text-xs font-bold text-slate-800">{t(card.titleKey)}</p>
                      </div>
                      {card.badgeKey && (
                        <span className="rounded-md bg-amber-100/70 px-1.5 py-0.5 text-[9px] font-bold text-amber-800">
                          {t(card.badgeKey)}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] leading-relaxed text-slate-500 group-hover:text-slate-600 transition-colors">
                      {t(card.bodyKey)}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
