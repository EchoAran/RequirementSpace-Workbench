import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { extractWorkspacePage } from '@/core/selectors';
import { useAuthStore } from '@/store/useAuthStore';
import { Settings, LogOut, User, Shield, Users, ClipboardList, Clock, Bell, ArrowLeft } from 'lucide-react';
import ProjectMembersModal from '../project/ProjectMembersModal';
import { TaskDecisionModal } from '../shared/TaskDecisionModal';
import { workspaceApi } from '@/lib/api';
import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { getCollaborationTaskTitle, getNotificationPresentation } from '@/core/collaborationPresentation';



export function TopBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { exitWorkspace, ir } = useWorkspaceStore();
  const { user, logout } = useAuthStore();
  const { t, i18n } = useTranslation();

  const getSubtitleKey = (path: string) => {
    switch (extractWorkspacePage(path)) {
      case '/overview': return 'topbar.subtitle.overview';
      case '/what': return 'topbar.subtitle.what';
      case '/flow': return 'topbar.subtitle.flow';
      case '/scope': return 'topbar.subtitle.scope';
      case '/preview': return 'topbar.subtitle.preview';
      default: return 'topbar.subtitle.overview';
    }
  };
  
  // Store tasks state
  const userTasks = useWorkspaceStore((state) => state.userTasks);
  const loadMyTasks = useWorkspaceStore((state) => state.loadMyTasks);
  const refreshWorkspace = useWorkspaceStore((state) => state.refreshWorkspace);
  const loadConfirmationSummary = useWorkspaceStore((state) => state.loadConfirmationSummary);

  const [showMembers, setShowMembers] = useState(false);
  const [showTasksPopover, setShowTasksPopover] = useState(false);
  const [activePopoverTask, setActivePopoverTask] = useState<any | null>(null);

  const [notifications, setNotifications] = useState<any[]>([]);
  const [showNotifications, setShowNotifications] = useState(false);

  const loadNotifications = useCallback(async () => {
    try {
      const data = await workspaceApi.listNotifications();
      setNotifications(data);
    } catch (err) {
      console.error('Failed to load notifications:', err);
    }
  }, []);

  useEffect(() => {
    const refreshCollaboration = () => {
      void loadMyTasks?.({ status: 'open', limit: 5, role: 'assignee' });
      void loadNotifications();
    };
    refreshCollaboration();
    const interval = setInterval(refreshCollaboration, 10000);
    return () => clearInterval(interval);
  }, [loadMyTasks, loadNotifications]);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const handleMarkAllRead = async () => {
    try {
      await workspaceApi.markNotificationsRead();
      await loadNotifications();
    } catch (err) {
      console.error(err);
    }
  };

  const handleTaskDecided = async () => {
    const activeProjId = activePopoverTask?.projectSummary?.projectId || ir?.projectId;
    setActivePopoverTask(null);
    if (typeof loadMyTasks === 'function') {
      await loadMyTasks({ status: 'open', limit: 5, role: 'assignee' });
    }
    if (activeProjId) {
      if (typeof loadConfirmationSummary === 'function') {
        await loadConfirmationSummary(activeProjId);
      }
      if (typeof refreshWorkspace === 'function') {
        await refreshWorkspace();
      }
    }
  };

  const openTasksCount = (userTasks || []).length;
  const unreadCount = notifications.filter((n: any) => !n.readAt).length;

  return (
    <header className="h-16 flex-shrink-0 border-b border-slate-200 bg-white flex items-center justify-between px-6 z-15 sticky top-0">
      <div className="flex items-center gap-4">
        <button 
          onClick={() => {
            exitWorkspace();
            navigate('/home');
          }}
          className="text-xs text-slate-500 hover:text-slate-800 transition-colors mr-2 flex items-center gap-1 font-medium cursor-pointer"
        ><ArrowLeft className="h-3.5 w-3.5" /> {t('nav.back')}</button>
        <div className="h-4 w-[1px] bg-slate-300"></div>
        <h1 className="text-lg font-bold text-slate-800">{ir?.projectName || (ir as any)?.name || t('home.unnamedProject')}</h1>
        <div className="h-4 w-[1px] bg-slate-300"></div>
        <span className="text-sm text-slate-500 italic">{t(getSubtitleKey(location.pathname))}</span>
      </div>

      <div className="flex items-center gap-4 relative">
        {/* User Badge */}
        <div className="flex items-center gap-2 bg-slate-50 border border-slate-100 px-3 py-1.5 rounded-full text-xs font-bold text-slate-700">
          {user?.role === 'admin' ? (
            <Shield className="w-3.5 h-3.5 text-indigo-600" />
          ) : (
            <User className="w-3.5 h-3.5 text-slate-500" />
          )}
          <span className="max-w-[120px] truncate">{user?.email}</span>
        </div>

        {/* My Tasks Badge and Popover */}
        <div className="relative">
          <button
            onClick={() => {
              void loadMyTasks?.({ status: 'open', limit: 5, role: 'assignee' });
              setShowTasksPopover(!showTasksPopover);
              setShowNotifications(false);
            }}
            className={`p-2 border rounded-xl shadow-sm transition-all relative cursor-pointer ${
              showTasksPopover 
                ? 'border-indigo-500 bg-indigo-50 text-indigo-600' 
                : 'border-slate-200 bg-white text-slate-500 hover:text-indigo-600 hover:border-indigo-200'
            }`}
            title={t('topbar.todoListTriggerTitle')}
          >
            <ClipboardList className="w-4 h-4" />
            {openTasksCount > 0 && (
              <span className="absolute -top-1.5 -right-1.5 bg-rose-500 text-white rounded-full text-[9px] font-black h-4 min-w-[16px] px-1 flex items-center justify-center border-2 border-white animate-pulse">
                {openTasksCount}
              </span>
            )}
          </button>

          {/* Popover checklist */}
          {showTasksPopover && (
            <div className="absolute right-0 mt-2 w-80 bg-white border border-slate-200 rounded-2xl shadow-xl z-50 overflow-hidden flex flex-col max-h-96">
              <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-800">{t('topbar.todoListTitle')}</span>
                <span className="text-[10px] font-bold text-slate-400 bg-white border border-slate-150 px-2 py-0.5 rounded-full">
                  {t('topbar.todoListCount', { count: openTasksCount })}
                </span>
              </div>

              <div className="flex-1 overflow-y-auto divide-y divide-slate-100 max-h-72">
                {openTasksCount === 0 ? (
                  <div className="py-10 text-center text-slate-400 text-xs">
                    {t('topbar.todoListEmpty')}
                  </div>
                ) : (
                  userTasks.map((wrapper: any) => {
                    const task = wrapper.task;
                    const project = wrapper.projectSummary;
                    const target = wrapper.targetSummary;
                    const creator = wrapper.creatorSummary;
                    const kindKey = `nodeKind.${target.nodeKind}`;
                    const translatedKind = t(kindKey);
                    const kindLabel = translatedKind === kindKey ? target.nodeKind || t('nodeKind.unknown') : translatedKind;

                    return (
                      <div 
                        key={task.id} 
                        className="p-3.5 hover:bg-slate-50 transition-colors flex flex-col gap-2 cursor-pointer"
                        onClick={() => {
                          setActivePopoverTask(wrapper);
                          setShowTasksPopover(false);
                        }}
                      >
                        <div className="flex items-center justify-between text-[10px] font-bold text-slate-400">
                          <span className="text-indigo-600 truncate max-w-[150px]">{project.projectName}</span>
                          <span className={`px-1.5 py-0.5 rounded-full shrink-0 ${
                            task.priority === 'high' 
                              ? 'bg-rose-50 text-rose-600' 
                              : task.priority === 'medium'
                              ? 'bg-amber-50 text-amber-600'
                              : 'bg-slate-100 text-slate-600'
                          }`}>
                            {task.priority === 'high' ? t('topbar.priority.high') : task.priority === 'medium' ? t('topbar.priority.medium') : t('topbar.priority.low')}
                          </span>
                        </div>
                        
                        <div className="text-xs font-bold text-slate-800 line-clamp-1">
                          {getCollaborationTaskTitle(task, t)}
                        </div>

                        <div className="text-[10px] text-slate-500 bg-slate-50 rounded px-2 py-1 flex items-center justify-between">
                          <span className="font-semibold truncate max-w-[180px]">{target.nodeName || t('topbar.unspecified')}</span>
                          <span className="text-[9px] text-slate-400 uppercase tracking-wider shrink-0">{kindLabel}</span>
                        </div>

                        <div className="flex items-center justify-between text-[9px] text-slate-400">
                          <span>{t('topbar.initiatedBy', { email: creator.email })}</span>
                          <span className="flex items-center gap-0.5">
                            <Clock className="w-3 h-3 text-slate-400" />
                      <span>{new Date(task.createdAt).toLocaleString(i18n.language)}</span>
                          </span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>

        {/* Notifications Center Badge and Popover */}
        <div className="relative">
          <button
            onClick={() => {
              setShowNotifications(!showNotifications);
              setShowTasksPopover(false);
            }}
            className={`p-2 border rounded-xl shadow-sm transition-all relative cursor-pointer ${
              showNotifications 
                ? 'border-indigo-500 bg-indigo-50 text-indigo-600' 
                : 'border-slate-200 bg-white text-slate-500 hover:text-indigo-600 hover:border-indigo-200'
            }`}
            title={t('topbar.notificationsCenter')}
          >
            <Bell className="w-4 h-4" />
            {unreadCount > 0 && (
              <span className="absolute -top-1.5 -right-1.5 bg-rose-500 text-white rounded-full text-[9px] font-black h-4 min-w-[16px] px-1 flex items-center justify-center border-2 border-white animate-pulse">
                {unreadCount}
              </span>
            )}
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 bg-white border border-slate-200 rounded-2xl shadow-xl z-50 overflow-hidden flex flex-col max-h-96">
              <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-800">{t('topbar.notificationCenterTitle')}</span>
                {unreadCount > 0 && (
                  <button
                    onClick={handleMarkAllRead}
                    className="text-[10px] text-indigo-600 hover:text-indigo-800 font-semibold cursor-pointer"
                  >
                    {t('topbar.markAllRead')}
                  </button>
                )}
              </div>

              <div className="flex-1 overflow-y-auto divide-y divide-slate-100 max-h-72">
                {notifications.length === 0 ? (
                  <div className="py-10 text-center text-slate-400 text-xs">
                    {t('topbar.noNotifications')}
                  </div>
                ) : (
                  notifications.map((n: any) => {
                    const presentation = getNotificationPresentation(n, t);
                    return (
                    <div 
                      key={n.id} 
                      className={`p-3.5 hover:bg-slate-50 transition-colors flex flex-col gap-1.5 relative ${
                        !n.readAt ? 'bg-indigo-50/10' : ''
                      }`}
                    >
                      {!n.readAt && (
                        <span className="absolute top-4 right-4 w-2 h-2 bg-indigo-600 rounded-full"></span>
                      )}
                      <div className="text-xs font-bold text-slate-800 pr-4">
                        {presentation.title}
                      </div>
                      <div className="text-[11px] text-slate-500 leading-normal">
                        {presentation.body}
                      </div>
                      <div className="text-[9px] text-slate-400 flex items-center gap-1 mt-0.5">
                        <Clock className="w-3 h-3 text-slate-400" />
                    <span>{new Date(n.createdAt).toLocaleString(i18n.language)}</span>
                      </div>
                    </div>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        {ir && (
          <button
            onClick={() => setShowMembers(true)}
            className="p-2 border border-slate-200 bg-white rounded-xl text-slate-500 hover:text-indigo-600 hover:border-indigo-200 shadow-sm transition-all cursor-pointer"
            title={t('topbar.projectMembers')}
          >
            <Users className="w-4 h-4" />
          </button>
        )}

        <button
          onClick={() => navigate('/settings')}
          className="p-2 border border-slate-200 bg-white rounded-xl text-slate-500 hover:text-indigo-600 hover:border-indigo-200 shadow-sm transition-all cursor-pointer"
          title={t('topbar.accountSettings')}
        >
          <Settings className="w-4 h-4" />
        </button>

        <button
          onClick={handleLogout}
          className="p-2 border border-slate-200 bg-white rounded-xl text-slate-500 hover:text-rose-600 hover:border-rose-200 shadow-sm transition-all cursor-pointer"
          title={t('topbar.logout')}
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
      
      {showMembers && ir && user && (
        <ProjectMembersModal
          projectId={ir.projectId || ir.id || ''}
          currentUserId={user.id}
          onClose={() => setShowMembers(false)}
        />
      )}

      {/* Decision task Modal */}
      {activePopoverTask && (
        <TaskDecisionModal
          task={activePopoverTask.task}
          projectId={activePopoverTask.projectSummary.projectId}
          onClose={() => setActivePopoverTask(null)}
          onDecided={handleTaskDecided}
        />
      )}
    </header>
  );
}

export default TopBar;
