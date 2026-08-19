import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { useRef } from 'react';
import { useModalDialog } from '@/lib/useModalDialog';

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
    <div ref={dialogRef} className="fixed inset-0 z-[1000] flex items-center justify-center bg-slate-900/60 p-4" role="dialog" aria-modal="true" aria-label={t('versionControl.discardConfirmTitle')}>
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl">
        <h3 className="text-base font-bold text-slate-800">{t('versionControl.discardConfirmTitle')}</h3>
        <p className="mt-2 text-sm text-slate-600">{t('versionControl.discardConfirmMessage')}</p>
        <p className="mt-1 text-xs text-slate-400">
          {t('versionControl.commitDialog.expectedHead')}: {pendingBranchRef}
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={cancel}
            className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            {t('versionControl.discardCancel')}
          </button>
          <button
            type="button"
            onClick={confirmDiscard}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            {t('versionControl.discardConfirm')}
          </button>
        </div>
      </div>
    </div>
  );
}
