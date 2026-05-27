import { useLocation, useNavigate } from 'react-router-dom';
import { useWorkspaceStore, selectIssues, selectFlowSteps, selectActors } from '@/store/useWorkspaceStore';

const getSubtitle = (path: string) => {
  switch (path) {
    case '/': return '概览';
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
  const { exitWorkspace, ir, error } = useWorkspaceStore();
  const issues = useWorkspaceStore(selectIssues);
  const actors = useWorkspaceStore(selectActors);
  const flowSteps = useWorkspaceStore(selectFlowSteps);

  // We consider open high severity issues as blocking
  const blockingItems = issues.filter(i => i.status === 'open' && i.severity === 'high');
  const unresolvedIssues = issues.filter(g => g.status === 'open');
  // Additionally, ensure minimal readiness: at least one actor and one flow step
  const minReady = actors.length > 0 && flowSteps.length > 0;
  
  const isReady = minReady && blockingItems.length === 0 && unresolvedIssues.length === 0;

  return (
    <>
      <header className="h-16 flex-shrink-0 border-b border-slate-200 bg-white flex items-center justify-between px-6 z-10 sticky top-0">
        <div className="flex items-center gap-4">
          <button 
            onClick={exitWorkspace}
            className="text-xs text-slate-500 hover:text-slate-800 transition-colors mr-2 flex items-center gap-1 font-medium"
          >← 返回</button>
          <div className="h-4 w-[1px] bg-slate-300"></div>
          <h1 className="text-lg font-bold text-slate-800">{ir?.projectName || (ir as any)?.name || '需求探索项目'}</h1>
          <div className="h-4 w-[1px] bg-slate-300"></div>
          <span className="text-sm text-slate-500 italic">{getSubtitle(location.pathname)}</span>
        </div>

        <div className="flex items-center gap-3">
          {/* Primary Button */}
          {location.pathname === '/preview' ? (
            <button 
              onClick={() => navigate('/what')}
              className="px-4 py-1.5 text-sm font-medium rounded-lg transition-colors shadow-sm bg-slate-100 text-slate-600 hover:bg-slate-200"
            >
              返回检查
            </button>
          ) : (
            <button 
              disabled={!isReady}
              onClick={() => {
                if (isReady) navigate('/preview');
              }}
              className={`px-4 py-1.5 text-sm font-medium rounded-lg transition-colors shadow-sm ${
                isReady 
                  ? 'bg-indigo-600 text-white shadow-indigo-200 hover:bg-indigo-700' 
                  : 'bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200'
              }`}
            >
              {isReady ? '去预览并生成' : '生成前检查未通过'}
            </button>
          )}
        </div>
      </header>

      {error && (
        <div className="fixed bottom-4 right-4 z-50 bg-rose-50 text-rose-700 border border-rose-200 px-4 py-2 rounded-lg shadow-sm text-sm">
          {error}
        </div>
      )}
    </>
  );
}
