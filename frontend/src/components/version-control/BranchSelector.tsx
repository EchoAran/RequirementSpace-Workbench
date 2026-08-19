import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { GitBranch, Lock, Plus, Search } from 'lucide-react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { cn } from '@/lib/utils';

/**
 * 顶部栏分支选择器：展示当前分支、受保护标识，并支持搜索/切换/新建分支。
 * 切换分支通过更新 URL ?branch= 触发全局分支同步，不在此处直接改数据。
 */
export function BranchSelector() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const branches = useWorkspaceStore((s) => s.branches);
  const currentBranch = useWorkspaceStore((s) => s.currentBranch);
  const branchLoading = useWorkspaceStore((s) => s.branchLoading);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(-1);
  const boxRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const selectorButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open]);

  // 打开时聚焦搜索框并重置高亮索引；Escape 关闭并归还焦点到触发按钮。
  useEffect(() => {
    if (!open) return;
    setActiveIndex(-1);
    searchRef.current?.focus();
  }, [open]);

  // 键盘导航：ArrowDown/ArrowUp 移动高亮，Enter 选择，Escape 关闭并归还焦点。
  // 挂载在打开的下拉容器上，使焦点位于搜索框时按键也能冒泡触发。
  const handleListKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setOpen(false);
      selectorButtonRef.current?.focus();
      return;
    }
    if (filtered.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % filtered.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => (i <= 0 ? filtered.length - 1 : i - 1));
    } else if (e.key === 'Enter') {
      const idx = activeIndex >= 0 ? activeIndex : 0;
      if (filtered[idx]) switchTo(filtered[idx].public_id);
    }
  };

  const filtered = useMemo(() => {
    const list = branches || [];
    const q = query.trim().toLowerCase();
    return q ? list.filter((b) => b.name.toLowerCase().includes(q)) : list;
  }, [branches, query]);

  const requestBranchSwitch = useWorkspaceStore((s) => s.requestBranchSwitch);

  const doSwitch = (publicId: string) => {
    const params = new URLSearchParams(location.search);
    params.set('branch', publicId);
    navigate(`${location.pathname}?${params.toString()}`);
  };

  // 统一切换守卫：存在未保存编辑或生成中时由全局弹窗确认，否则直接导航。
  const switchTo = (publicId: string) => {
    setOpen(false);
    if (requestBranchSwitch(publicId)) {
      doSwitch(publicId);
    }
  };

  const goCreateBranch = () => {
    setOpen(false);
    const params = new URLSearchParams(location.search);
    params.set('new_branch', '1');
    navigate(`/projects/${useWorkspaceStore.getState().ir?.projectId || ''}/repo?${params.toString()}`);
  };

  const protectedBranch = currentBranch?.is_protected || currentBranch?.name === 'main';

  return (
    <div ref={boxRef} className="relative flex-shrink-0">
      <button
        type="button"
        ref={selectorButtonRef}
        data-testid="branch-selector-button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={t('versionControl.branchSelector.label')}
        className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm text-slate-700 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
      >
        <GitBranch className="h-4 w-4 text-indigo-600" />
        <span className="max-w-[9rem] truncate font-medium">
          {branchLoading ? t('shell.loading') : currentBranch?.name || 'main'}
        </span>
        {protectedBranch && (
          <span className="inline-flex items-center gap-0.5 rounded bg-amber-100 px-1 text-[10px] font-semibold text-amber-700">
            <Lock className="h-3 w-3" />
            {t('versionControl.branchSelector.protected')}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-[60] mt-1.5 w-72 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg" onKeyDown={handleListKeyDown}>
          <div className="flex items-center gap-2 border-b border-slate-100 px-3 py-2">
            <Search className="h-4 w-4 text-slate-400" />
            <input
              ref={searchRef}
              value={query}
              onChange={(e) => { setQuery(e.target.value); setActiveIndex(-1); }}
              placeholder={t('versionControl.branchSelector.searchPlaceholder')}
              className="w-full bg-transparent text-sm outline-none placeholder:text-slate-400"
              aria-label={t('versionControl.branchSelector.searchPlaceholder')}
              role="combobox"
              aria-expanded={open}
              aria-controls="branch-option-list"
              aria-activedescendant={activeIndex >= 0 && filtered[activeIndex] ? `branch-option-${activeIndex}` : undefined}
              aria-autocomplete="list"
            />
          </div>
          <ul id="branch-option-list" role="listbox" aria-label={t('versionControl.branchSelector.label')} className="max-h-72 overflow-y-auto py-1">
            {filtered.map((branch, idx) => {
              const active = branch.public_id === currentBranch?.public_id;
              const isProtected = branch.is_protected || branch.name === 'main';
              return (
                <li key={branch.public_id} role="none">
                  <button
                    type="button"
                    role="option"
                    id={`branch-option-${idx}`}
                    aria-selected={active}
                    onClick={() => switchTo(branch.public_id)}
                    onMouseEnter={() => setActiveIndex(idx)}
                    className={cn(
                      'flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-indigo-50 focus:outline-none focus-visible:bg-indigo-50',
                      (active || idx === activeIndex) && 'bg-indigo-50 text-indigo-700'
                    )}
                  >
                    <GitBranch className="h-3.5 w-3.5 text-slate-400" />
                    <span className="flex-1 truncate font-medium">{branch.name}</span>
                    {isProtected && <Lock className="h-3 w-3 text-amber-500" />}
                    {active && <span className="h-2 w-2 rounded-full bg-indigo-500" />}
                  </button>
                </li>
              );
            })}
            {filtered.length === 0 && (
              <li className="px-3 py-2 text-sm text-slate-400">
                {t('versionControl.branchSelector.noBranches')}
              </li>
            )}
          </ul>
          <div className="border-t border-slate-100 p-1">
            <button
              type="button"
              onClick={goCreateBranch}
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-indigo-600 hover:bg-indigo-50 focus:outline-none focus-visible:bg-indigo-50"
            >
              <Plus className="h-4 w-4" />
              {t('versionControl.branchSelector.createBranch')}
            </button>
          </div>
        </div>
      )}

    </div>
  );
}
