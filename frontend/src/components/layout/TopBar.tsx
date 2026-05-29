import { useLocation, useNavigate } from 'react-router-dom';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { extractWorkspacePage } from '@/core/selectors';

const getSubtitle = (path: string) => {
  switch (extractWorkspacePage(path)) {
    case '/overview': return '概览';
    case '/what': return '目标、能力、任务、角色收敛';
    case '/flow': return '流程、规则、异常、状态变化';
    case '/scope': return '范围边界与生成条件';
    case '/preview': return '验证与生成前检查';
    default: return '概览';
  }
};

export function TopBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { exitWorkspace, ir } = useWorkspaceStore();

  return (
    <>
      <header className="h-16 flex-shrink-0 border-b border-slate-200 bg-white flex items-center px-6 z-10 sticky top-0">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => {
              exitWorkspace();
              navigate('/home');
            }}
            className="text-xs text-slate-500 hover:text-slate-800 transition-colors mr-2 flex items-center gap-1 font-medium"
          >← 返回</button>
          <div className="h-4 w-[1px] bg-slate-300"></div>
          <h1 className="text-lg font-bold text-slate-800">{ir?.projectName || (ir as any)?.name || '需求探索项目'}</h1>
          <div className="h-4 w-[1px] bg-slate-300"></div>
          <span className="text-sm text-slate-500 italic">{getSubtitle(location.pathname)}</span>
        </div>
      </header>

    </>
  );
}
