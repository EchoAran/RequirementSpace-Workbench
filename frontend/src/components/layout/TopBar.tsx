import { useState } from 'react';
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
  const { initialPrompt, exitWorkspace, startAIOnboarding, runDiagnosis, ir, error } = useWorkspaceStore();
  const issues = useWorkspaceStore(selectIssues);
  const actors = useWorkspaceStore(selectActors);
  const flowSteps = useWorkspaceStore(selectFlowSteps);
  const [showPrompt, setShowPrompt] = useState(false);
  const [showMoreMenu, setShowMoreMenu] = useState(false);
  const [showRegenerateConfirm, setShowRegenerateConfirm] = useState(false);

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
          <h1 className="text-lg font-bold text-slate-800 cursor-pointer hover:text-indigo-600 transition-colors" onClick={() => setShowPrompt(true)}>项目：{ir?.projectName || (ir as any)?.name || '需求探索项目'}</h1>
          <div className="h-4 w-[1px] bg-slate-300"></div>
          <span className="text-sm text-slate-500 italic">{getSubtitle(location.pathname)}</span>
        </div>

        <div className="flex items-center gap-3">
          {/* More Menu */}
          <div className="relative">
            <button 
              onClick={() => setShowMoreMenu(!showMoreMenu)}
              className="px-3 py-1.5 text-sm font-medium text-slate-600 border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors flex items-center gap-1 z-50 relative"
            >
              更多 <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
            </button>
            
            {showMoreMenu && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowMoreMenu(false)}></div>
                <div className="absolute right-0 mt-2 w-48 bg-white rounded-xl shadow-lg border border-slate-100 py-1 z-50">
                  <button 
                    onClick={() => { setShowMoreMenu(false); setShowPrompt(true); }}
                    className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                  >查看起点</button>
                  <button 
                    onClick={async () => {
                      setShowMoreMenu(false);
                      await runDiagnosis({ trigger: 'global_check' });
                    }}
                    className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                  >全局检查</button>
                </div>
              </>
            )}
          </div>

          <div className="w-px h-5 bg-slate-200 mx-1"></div>

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

      {/* Show Prompt Modal inside TopBar */}
      {showPrompt && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0" onClick={() => setShowPrompt(false)}></div>
          <div className="bg-white rounded-2xl shadow-xl w-[500px] p-6 relative z-10">
            <h3 className="text-lg font-bold text-slate-800 mb-2">原始应用诉求</h3>
            <p className="text-sm text-slate-500 mb-4">这是构建此需求空间的结构化起点</p>
            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-sm text-slate-700 mb-6 min-h-[100px]">
              {initialPrompt}
            </div>
            <div className="flex justify-end items-center gap-3">
              <button 
                onClick={() => { setShowPrompt(false); setShowRegenerateConfirm(true); }} 
                className="text-indigo-600 text-sm font-bold border border-indigo-100 hover:bg-indigo-50 px-4 py-2 rounded-lg transition-colors"
              >重新生成起点</button>
              <button onClick={() => setShowPrompt(false)} className="bg-slate-900 text-white px-5 py-2 text-sm font-bold rounded-xl hover:bg-slate-800 transition-colors">关闭</button>
            </div>
          </div>
        </div>
      )}

      {/* Regenerate Confirm Modal */}
      {showRegenerateConfirm && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0" onClick={() => setShowRegenerateConfirm(false)}></div>
          <div className="bg-white rounded-2xl shadow-xl w-[400px] p-6 relative z-10">
            <div className="w-12 h-12 bg-rose-100 text-rose-600 rounded-full flex items-center justify-center mb-4">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
              </svg>
            </div>
            <h3 className="text-xl font-bold text-slate-900 mb-2">生成新的工作区起点</h3>
            <p className="text-sm text-slate-500 mb-6 leading-relaxed">
              这会基于当前原始诉求重新初始化一个新的工作区，并切换到新结果；不会原地覆盖当前工作区。是否继续？
            </p>
            <div className="flex justify-end gap-3">
              <button 
                onClick={() => setShowRegenerateConfirm(false)}
                className="px-4 py-2 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
              >取消</button>
              <button 
                onClick={async () => {
                  setShowRegenerateConfirm(false);
                  await startAIOnboarding(initialPrompt);
                }}
                className="px-4 py-2 text-sm font-medium text-white bg-rose-600 hover:bg-rose-700 rounded-lg transition-colors shadow-sm shadow-rose-200"
              >确认生成新工作区</button>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="fixed bottom-4 right-4 z-50 bg-rose-50 text-rose-700 border border-rose-200 px-4 py-2 rounded-lg shadow-sm text-sm">
          {error}
        </div>
      )}
    </>
  );
}
