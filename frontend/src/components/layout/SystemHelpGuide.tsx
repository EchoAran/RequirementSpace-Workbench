import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { gsap } from 'gsap';
import {
  HelpCircle,
  X,
  ChevronRight,
  GitBranch,
  RotateCcw,
  GitPullRequest,
  Layers,
  Sparkles,
  CheckCircle2,
  Workflow,
  Target,
  Users,
  Search,
  Eye,
  Shield,
  HelpCircle as QuestionIcon,
} from 'lucide-react';
import { extractWorkspacePage } from '@/core/selectors';
import { cn } from '@/lib/utils';

interface SectionConfig {
  id: string;
  category: 'workflow' | 'version_control' | 'collaboration';
  icon: React.ComponentType<{ className?: string }>;
  pagePaths: string[];
}

const SECTION_CONFIGS: SectionConfig[] = [
  { id: 'lifecycle', category: 'workflow', icon: Layers, pagePaths: ['/overview'] },
  { id: 'guidance', category: 'workflow', icon: Search, pagePaths: [] },
  { id: 'ai_assistant', category: 'workflow', icon: Sparkles, pagePaths: [] },
  { id: 'what', category: 'workflow', icon: Users, pagePaths: ['/what'] },
  { id: 'flow', category: 'workflow', icon: Workflow, pagePaths: ['/flow'] },
  { id: 'scope', category: 'workflow', icon: Target, pagePaths: ['/scope'] },
  { id: 'preview', category: 'workflow', icon: Eye, pagePaths: ['/preview'] },
  { id: 'branching', category: 'version_control', icon: GitBranch, pagePaths: ['/repo'] },
  { id: 'commit_revert', category: 'version_control', icon: RotateCcw, pagePaths: ['/repo'] },
  { id: 'merge_request', category: 'version_control', icon: GitPullRequest, pagePaths: ['/repo'] },
  { id: 'collaboration', category: 'collaboration', icon: Shield, pagePaths: ['/settings'] },
];

export function SystemHelpGuide() {
  const { t } = useTranslation();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [activeId, setActiveId] = useState<string>('lifecycle');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<'all' | 'workflow' | 'version_control' | 'collaboration'>('all');

  const containerRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const drawerRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  // 感知当前页面上下文并智能推荐对应章节
  useEffect(() => {
    const page = extractWorkspacePage(location.pathname);
    const matched = SECTION_CONFIGS.find((cfg) => cfg.pagePaths.includes(page));
    if (matched) {
      setActiveId(matched.id);
    }
  }, [location.pathname]);

  // GSAP 进出场平滑动效
  useEffect(() => {
    if (open) {
      if (overlayRef.current && drawerRef.current) {
        gsap.killTweensOf([overlayRef.current, drawerRef.current]);
        gsap.fromTo(
          overlayRef.current,
          { opacity: 0 },
          { opacity: 1, duration: 0.25, ease: 'power2.out' }
        );
        gsap.fromTo(
          drawerRef.current,
          { y: -30, opacity: 0, scale: 0.98 },
          { y: 0, opacity: 1, scale: 1, duration: 0.35, ease: 'back.out(1.2)' }
        );
      }
    }
  }, [open]);

  // 切换内容区域时的平滑过渡动画
  useEffect(() => {
    if (contentRef.current && open) {
      gsap.fromTo(
        contentRef.current.children,
        { y: 14, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.25, stagger: 0.04, ease: 'power2.out' }
      );
    }
  }, [activeId, open]);

  // 构建国际化章节数据
  const sections = SECTION_CONFIGS.map((cfg) => {
    const prefix = `systemGuide.sections.${cfg.id}`;
    const rawHighlights = t(`${prefix}.highlights`, { returnObjects: true });
    const rawSteps = t(`${prefix}.steps`, { returnObjects: true });
    const rawFaqs = t(`${prefix}.faqs`, { returnObjects: true });

    return {
      id: cfg.id,
      category: cfg.category,
      icon: cfg.icon,
      title: t(`${prefix}.title`),
      badge: t(`${prefix}.badge`),
      summary: t(`${prefix}.summary`),
      highlights: Array.isArray(rawHighlights) ? (rawHighlights as { title: string; desc: string }[]) : [],
      steps: Array.isArray(rawSteps) ? (rawSteps as { step: number; title: string; desc: string }[]) : [],
      faqs: Array.isArray(rawFaqs) ? (rawFaqs as { q: string; a: string }[]) : [],
    };
  });

  const activeSection = sections.find((s) => s.id === activeId) || sections[0];

  const filteredSections = sections.filter((s) => {
    if (selectedCategory !== 'all' && s.category !== selectedCategory) return false;
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      s.title.toLowerCase().includes(q) ||
      s.summary.toLowerCase().includes(q) ||
      s.highlights.some((h) => h.title.toLowerCase().includes(q) || h.desc.toLowerCase().includes(q)) ||
      s.steps.some((st) => st.title.toLowerCase().includes(q) || st.desc.toLowerCase().includes(q)) ||
      s.faqs.some((f) => f.q.toLowerCase().includes(q) || f.a.toLowerCase().includes(q))
    );
  });

  const handleClose = () => {
    if (overlayRef.current && drawerRef.current) {
      gsap.to(overlayRef.current, { opacity: 0, duration: 0.2, ease: 'power2.in' });
      gsap.to(drawerRef.current, {
        y: -20,
        opacity: 0,
        scale: 0.98,
        duration: 0.2,
        ease: 'power2.in',
        onComplete: () => setOpen(false),
      });
    } else {
      setOpen(false);
    }
  };

  return (
    <>
      {/* 顶部栏触发按钮（WeUI Style） */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          'group relative inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-bold transition-all duration-200 cursor-pointer shadow-2xs select-none',
          open
            ? 'border-indigo-500 bg-indigo-50 text-indigo-700 shadow-sm'
            : 'border-slate-200 bg-white text-slate-600 hover:border-indigo-300 hover:bg-indigo-50/40 hover:text-indigo-600'
        )}
        title={t('systemGuide.title')}
      >
        <HelpCircle className="h-3.5 w-3.5 text-indigo-600 transition-transform duration-200 group-hover:scale-110" />
        <span>{t('systemGuide.trigger')}</span>
        <span className="ml-0.5 rounded-md bg-indigo-100/70 px-1.5 py-0.2 text-[10px] font-semibold text-indigo-700">
          {t('systemGuide.manualBadge')}
        </span>
      </button>

      {/* 全屏 Help 弹层与抽屉面板 */}
      {open && typeof document !== 'undefined' && createPortal(
        <div ref={containerRef} className="fixed inset-0 z-[100] flex items-start justify-center p-4 sm:p-6 md:p-10">
          {/* 高斯模糊背景遮罩 */}
          <div
            ref={overlayRef}
            onClick={handleClose}
            className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs transition-opacity"
          />

          {/* 主面板：WeUI Panel / Modal 精致卡片 */}
          <div
            ref={drawerRef}
            className="relative z-10 flex h-[88vh] max-h-[820px] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-2xl"
          >
            {/* Header 导航栏 */}
            <div className="flex h-15 shrink-0 items-center justify-between border-b border-slate-100 bg-slate-50/80 px-6">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-2xs">
                  <Sparkles className="h-4 w-4" />
                </div>
                <div>
                  <h2 className="text-sm font-black text-slate-800 leading-tight">
                    {t('systemGuide.title')}
                  </h2>
                  <p className="text-[11px] text-slate-500 font-medium">
                    {t('systemGuide.subtitle')}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                {/* 搜索过滤栏 */}
                <div className="relative hidden sm:block">
                  <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder={t('systemGuide.searchPlaceholder')}
                    className="h-8 w-56 rounded-xl border border-slate-200 bg-white pl-8 pr-3 text-xs text-slate-700 placeholder-slate-400 focus:border-indigo-500 focus:outline-none"
                  />
                </div>

                <button
                  type="button"
                  onClick={handleClose}
                  aria-label="Close"
                  className="rounded-xl p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors cursor-pointer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* 主体两栏结构 */}
            <div className="flex flex-1 min-h-0 overflow-hidden">
              {/* 左侧导航列表（WeUI Cells Style） */}
              <div className="w-64 shrink-0 border-r border-slate-100 bg-slate-50/40 p-3 overflow-y-auto space-y-2">
                {/* 类别筛选 Tab */}
                <div className="flex items-center gap-1 rounded-xl bg-slate-100/80 p-1 mb-2">
                  <button
                    type="button"
                    onClick={() => setSelectedCategory('all')}
                    className={cn(
                      'flex-1 rounded-lg py-1 text-[10px] font-bold transition-all cursor-pointer text-center',
                      selectedCategory === 'all'
                        ? 'bg-white text-slate-900 shadow-2xs'
                        : 'text-slate-500 hover:text-slate-800'
                    )}
                  >
                    全部
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedCategory('workflow')}
                    className={cn(
                      'flex-1 rounded-lg py-1 text-[10px] font-bold transition-all cursor-pointer text-center',
                      selectedCategory === 'workflow'
                        ? 'bg-white text-slate-900 shadow-2xs'
                        : 'text-slate-500 hover:text-slate-800'
                    )}
                  >
                    规约
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedCategory('version_control')}
                    className={cn(
                      'flex-1 rounded-lg py-1 text-[10px] font-bold transition-all cursor-pointer text-center',
                      selectedCategory === 'version_control'
                        ? 'bg-white text-slate-900 shadow-2xs'
                        : 'text-slate-500 hover:text-slate-800'
                    )}
                  >
                    版本
                  </button>
                </div>

                <div className="px-2 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                  {t('systemGuide.directoryTitle')} ({filteredSections.length})
                </div>

                {filteredSections.length === 0 ? (
                  <div className="px-3 py-6 text-center text-xs text-slate-400">
                    {t('systemGuide.noResults')}
                  </div>
                ) : (
                  filteredSections.map((section) => {
                    const Icon = section.icon;
                    const isActive = section.id === activeId;
                    return (
                      <button
                        key={section.id}
                        type="button"
                        onClick={() => setActiveId(section.id)}
                        className={cn(
                          'group flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-xs font-bold transition-all cursor-pointer',
                          isActive
                            ? 'bg-indigo-600 text-white shadow-xs'
                            : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'
                        )}
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          <Icon
                            className={cn(
                              'h-4 w-4 shrink-0',
                              isActive ? 'text-white' : 'text-indigo-600 group-hover:text-indigo-700'
                            )}
                          />
                          <span className="truncate">{section.title}</span>
                        </div>
                        <ChevronRight
                          className={cn(
                            'h-3.5 w-3.5 shrink-0 opacity-0 transition-all',
                            isActive ? 'opacity-100 translate-x-0.5' : 'group-hover:opacity-40'
                          )}
                        />
                      </button>
                    );
                  })
                )}
              </div>

              {/* 右侧内容展现区（WeUI Card / Detail Style） */}
              <div className="flex-1 overflow-y-auto p-6 md:p-8">
                <div ref={contentRef} className="max-w-3xl space-y-6">
                  {/* 顶部标题与摘要卡片 */}
                  <div className="rounded-2xl border border-indigo-100 bg-gradient-to-br from-indigo-50/40 via-white to-slate-50/30 p-5 shadow-2xs">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="rounded-md bg-indigo-600 px-2 py-0.5 text-[10px] font-bold text-white uppercase tracking-wider">
                        {t(`systemGuide.categories.${activeSection.category}`)}
                      </span>
                      <span className="rounded-md bg-indigo-100/80 px-2 py-0.5 text-[10px] font-bold text-indigo-700">
                        {activeSection.badge}
                      </span>
                      <h3 className="text-base font-black text-slate-900 ml-1">{activeSection.title}</h3>
                    </div>
                    <p className="text-xs text-slate-600 leading-relaxed">{activeSection.summary}</p>
                  </div>

                  {/* 核心特性与原则（WeUI Cells Grid） */}
                  {activeSection.highlights.length > 0 && (
                    <div>
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
                        {t('systemGuide.designAndRationale')}
                      </h4>
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                        {activeSection.highlights.map((h, i) => (
                          <div
                            key={i}
                            className="rounded-xl border border-slate-200/70 bg-white p-4 shadow-2xs hover:border-indigo-200 transition-colors"
                          >
                            <div className="flex items-center gap-1.5 mb-1.5 text-slate-900 font-bold text-xs">
                              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                              <span>{h.title}</span>
                            </div>
                            <p className="text-[11px] text-slate-500 leading-relaxed pl-5">{h.desc}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 推荐步骤（若存在） */}
                  {activeSection.steps.length > 0 && (
                    <div>
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
                        {t('systemGuide.workflowSteps')}
                      </h4>
                      <div className="space-y-2.5">
                        {activeSection.steps.map((st) => (
                          <div
                            key={st.step}
                            className="flex items-start gap-3 rounded-xl border border-slate-100 bg-slate-50/60 p-3.5 text-xs"
                          >
                            <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-[10px] font-black text-white shadow-2xs">
                              {st.step}
                            </div>
                            <div>
                              <div className="font-bold text-slate-800">{st.title}</div>
                              <div className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">{st.desc}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 常见问题与解答（FAQ） */}
                  {activeSection.faqs.length > 0 && (
                    <div className="rounded-2xl border border-slate-200/80 bg-slate-50/40 p-5 space-y-3.5">
                      <h4 className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                        <QuestionIcon className="h-3.5 w-3.5 text-indigo-600" />
                        <span>{t('systemGuide.faqTitle')}</span>
                      </h4>
                      <div className="space-y-3">
                        {activeSection.faqs.map((f, idx) => (
                          <div key={idx} className="rounded-xl bg-white border border-slate-100 p-3.5 text-xs space-y-1">
                            <p className="font-bold text-indigo-800">Q: {f.q}</p>
                            <p className="text-[11px] text-slate-600 leading-relaxed pl-4">{f.a}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
