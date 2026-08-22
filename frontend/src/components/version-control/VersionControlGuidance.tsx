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
  badge?: string;
}

const VC_RULES_CARDS: GuidanceCard[] = [
  {
    key: 'baselineMeaning',
    icon: GitCommitHorizontal,
    titleKey: 'versionControl.guide.baselineMeaning.title',
    bodyKey: 'versionControl.guide.baselineMeaning.body',
    badge: '基线快照',
  },
  {
    key: 'whenToBranch',
    icon: GitBranch,
    titleKey: 'versionControl.guide.whenToBranch.title',
    bodyKey: 'versionControl.guide.whenToBranch.body',
    badge: '分支策略',
  },
  {
    key: 'mainProtection',
    icon: ShieldCheck,
    titleKey: 'versionControl.guide.mainProtection.title',
    bodyKey: 'versionControl.guide.mainProtection.body',
    badge: '安全保护',
  },
  {
    key: 'mrApproval',
    icon: GitPullRequest,
    titleKey: 'versionControl.guide.mrApproval.title',
    bodyKey: 'versionControl.guide.mrApproval.body',
    badge: '合并评审',
  },
  {
    key: 'unsupportedGitFeatures',
    icon: CircleSlash2,
    titleKey: 'versionControl.guide.unsupportedGitFeatures.title',
    bodyKey: 'versionControl.guide.unsupportedGitFeatures.body',
    badge: '特性差异',
  },
];

const VC_TIPS_CARDS = [
  {
    key: 'revertTip',
    icon: RotateCcw,
    title: '版本回滚技巧',
    body: '在提交历史中选中任意历史节点，点击“回滚到此提交”，系统将在当前分支生成反向提交并精准还原所有规约实体，历史记录完整可溯。',
    badge: '新功能',
  },
  {
    key: 'stageEvolution',
    icon: Layers,
    title: '规约阶段流转',
    body: '各分支独立推进 What (参与者/功能) → Flow (流程编排) → Scope (范围验收)。完成全部前置阶段后即可编译交互原型。',
    badge: '生命周期',
  },
  {
    key: 'semanticMerge',
    icon: GitPullRequest,
    title: '语义三方合并',
    body: '合并基于语义实体属性级别进行 Diff 与 Merge；发生冲突时可逐项选择保留源分支或目标分支，无需手写代码解决冲突。',
    badge: '智能冲突处理',
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
                💡 协作知识库
              </span>
            </div>
            {collapsed && (
              <p className="text-[11px] text-slate-400 mt-0.5 line-clamp-1">
                点击展开基线快照、分支策略、MR 评审及版本回滚等核心操作秘籍...
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-bold text-indigo-600 hover:bg-indigo-100/50 transition-colors"
          >
            <span>{collapsed ? '展开指南' : '收起'}</span>
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
              📖 核心协同规则
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
              🚀 实用技巧与回滚
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
                      {card.badge && (
                        <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[9px] font-bold text-slate-500">
                          {card.badge}
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
                        <p className="text-xs font-bold text-slate-800">{card.title}</p>
                      </div>
                      <span className="rounded-md bg-amber-100/70 px-1.5 py-0.5 text-[9px] font-bold text-amber-800">
                        {card.badge}
                      </span>
                    </div>
                    <p className="text-[11px] leading-relaxed text-slate-500 group-hover:text-slate-600 transition-colors">
                      {card.body}
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
