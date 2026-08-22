import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { useRef } from 'react';
import { useModalDialog } from '@/lib/useModalDialog';
import { AlertTriangle } from 'lucide-react';

/**
 * 全局分支切换守卫弹窗：所有切换来源（顶部选择器、仓库列表、浏览器 URL 变化）
 * 在存在未保存编辑时统一收敛到这里。确认"放弃并切换"会清空 editDirty、通知各页面
 * 关闭编辑弹窗，然后导航到目标分支；取消则保留原分支与编辑状态。
 */
export function BranchSwitchConfirmDialog() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const pendingBranchRef = useWorkspaceStore((s) => s.pendingBranchRef);
  const dialogRef = useRef<HTMLDivElement>(null);
  const isOpen = Boolean(pendingBranchRef);
  const cancel = () => {
    useWorkspaceStore.getState().setPendingBranchRef(null);
  };
  useModalDialog(isOpen, cancel, dialogRef);

  if (!pendingBranchRef) return null;

  const navigateToBranch = (ref: string) => {
    const params = new URLSearchParams(location.search);
    params.set('branch', ref);
    navigate(`${location.pathname}?${params.toString()}`);
  };

  const confirmDiscard = () => {
    const target = pendingBranchRef;
    useWorkspaceStore.getState().discardPendingEdits();
    navigateToBranch(target);
  };

  return (
    <div
      ref={dialogRef}
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
      aria-label={t('versionControl.discardConfirmTitle')}
    >
      <div className="w-full max-w-md rounded-3xl border border-slate-200/80 bg-white shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="flex items-start gap-3.5 border-b border-slate-100 bg-gradient-to-r from-amber-50/80 to-rose-50/50 p-6">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-100 text-amber-700 shadow-sm shrink-0">
            <AlertTriangle className="h-5 w-5" />
          </span>
          <div className="space-y-1 text-left">
            <h3 className="text-base font-black text-slate-900 tracking-tight">{t('versionControl.discardConfirmTitle')}</h3>
            <p className="text-xs text-slate-500 font-medium leading-relaxed">{t('versionControl.discardConfirmMessage')}</p>
          </div>
        </div>

        <div className="p-6 space-y-3">
          <div className="rounded-2xl border border-slate-100 bg-slate-50/80 p-3.5 text-xs text-slate-500">
            <span className="font-bold text-slate-700 block mb-1">{t('versionControl.commitDialog.expectedHead')}</span>
            <span className="font-mono text-slate-600 bg-white px-2 py-0.5 rounded-lg border border-slate-200 inline-block">{pendingBranchRef}</span>
          </div>
        </div>

        <div className="flex justify-end gap-2.5 border-t border-slate-100 bg-slate-50/60 p-5">
          <button
            type="button"
            onClick={cancel}
            className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-600 hover:bg-slate-50 transition-all cursor-pointer"
          >
            {t('versionControl.discardCancel')}
          </button>
          <button
            type="button"
            onClick={confirmDiscard}
            className="rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-bold text-white shadow-md hover:bg-indigo-700 active:scale-95 transition-all cursor-pointer"
          >
            {t('versionControl.discardConfirm')}
          </button>
        </div>
      </div>
    </div>
  );
}
