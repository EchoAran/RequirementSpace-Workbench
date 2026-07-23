import { useEffect, useMemo, useState } from 'react';
import { useWorkspaceStore, getFriendlyErrorMessage } from '@/store/useWorkspaceStore';
import { AppWindow, ArrowRight, Clock, Edit, Plus, Trash2, Sparkles, Settings, LogOut, User, Shield } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { buildProjectRoute } from '@/core/selectors';
import { workspaceApi } from '@/lib/api';
import { useAuthStore } from '@/store/useAuthStore';
import { useTranslation } from 'react-i18next';

export function Home() {
  const { t } = useTranslation();
  const {
    loadWorkspaces,
    workspaces,
    isLoading,
    error,
    updateProject,
    deleteProject,
    openOnboardingChoiceGroups,
    loadOpenOnboardingChoiceGroups,
    recoverOnboardingChoiceGroup,
    discardOnboardingChoiceGroup,
  } = useWorkspaceStore();
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const [editingProject, setEditingProject] = useState<any | null>(null);
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');

  useEffect(() => {
    void loadWorkspaces();
    void loadOpenOnboardingChoiceGroups();
  }, [loadWorkspaces, loadOpenOnboardingChoiceGroups]);

  const handleRecoverGroup = async (groupId: string) => {
    await recoverOnboardingChoiceGroup(groupId);
    navigate('/onboarding');
  };

  const handleDiscardGroup = async (groupId: string) => {
    try {
      await workspaceApi.discardProjectCreationChoiceGroup(groupId);
      await loadOpenOnboardingChoiceGroups();
    } catch { /* silently fail */ }
  };

  // Format timestamp (createdAt is a float Unix timestamp)
  const formatGroupTime = (ts?: number) => {
    if (!ts) return '';
    const diffMs = Date.now() - ts * 1000;
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return t('home.time.justGenerated');
    if (mins < 60) return t('home.time.minutesAgo', { count: mins });
    return t('home.time.hoursAgo', { count: Math.floor(mins / 60) });
  };

  const sorted = useMemo(() => {
    return [...workspaces].sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1));
  }, [workspaces]);

  const formatRelativeTime = (iso: string) => {
    const tVal = Date.parse(iso);
    if (Number.isNaN(tVal)) return t('home.time.unknownTime');
    const diffMs = Date.now() - tVal;
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return t('home.time.justModified');
    if (mins < 60) return t('home.time.minutesAgoModified', { count: mins });
    const hours = Math.floor(mins / 60);
    if (hours < 24) return t('home.time.hoursAgoModified', { count: hours });
    return t('home.time.daysAgoModified', { count: Math.floor(hours / 24) });
  };

  const renderStatus = (p: any) => {
    const statusKey = `home.projectStatus.${p.statusCode}`;
    const translatedStatus = t(statusKey);
    const status = translatedStatus === statusKey ? p.status || t('home.projectStatus.unknown') : translatedStatus;
    const statusCode = p.statusCode;
    const tone =
      statusCode === 'needs_attention'
        ? 'bg-rose-50 text-rose-700 border-rose-200'
        : statusCode === 'has_issues' || statusCode === 'scope_pending'
          ? 'bg-amber-50 text-amber-700 border-amber-200'
          : statusCode === 'in_progress'
            ? 'bg-sky-50 text-sky-700 border-sky-200'
            : statusCode === 'converged'
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-slate-100 text-slate-600 border-slate-200';

    return (
      <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold ${tone}`}>
        <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
        {status}
        {p.issueCount > 0 ? ` (${p.issueCount})` : ''}
      </span>
    );
  };

  const startEditing = (project: any) => {
    setEditingProject(project);
    setEditName(project.name || '');
    setEditDescription(project.description || project.idea || '');
  };

  const handleDelete = async (project: any) => {
    const ok = window.confirm(t('home.deleteConfirm', { name: project.name }));
    if (!ok) return;
    await deleteProject(project.id);
    await loadWorkspaces();
  };

  const handleOpenWorkspace = async (workspaceId: string) => {
    navigate(buildProjectRoute(workspaceId, '/overview'));
  };

  return (
    <div className="flex-1 h-[100dvh] bg-slate-50 flex flex-col font-sans selection:bg-indigo-100 relative overflow-hidden">
      <header className="h-16 border-b border-slate-200/50 bg-white/70 backdrop-blur-xl flex items-center justify-between px-8 shrink-0 sticky top-0 z-20 shadow-sm">
        <div className="flex items-center gap-3">
          <img src={`${import.meta.env.BASE_URL}plume-gradient.svg`} alt="Plume" className="w-7 h-7 shrink-0" />
          <span className="font-extrabold text-lg tracking-tight bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 bg-clip-text text-transparent">{t('home.title')}</span>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 bg-slate-50 border border-slate-100 px-3 py-1.5 rounded-full text-xs font-bold text-slate-700">
            {user?.role === 'admin' ? (
              <Shield className="w-3.5 h-3.5 text-indigo-600" />
            ) : (
              <User className="w-3.5 h-3.5 text-slate-500" />
            )}
            <span className="max-w-[120px] truncate">{user?.email}</span>
          </div>

          <button
            onClick={() => navigate('/settings')}
            className="p-2 border border-slate-200 bg-white rounded-xl text-slate-500 hover:text-indigo-600 hover:border-indigo-200 shadow-sm transition-all cursor-pointer"
            title={t('home.settingsTitle')}
          >
            <Settings className="w-4 h-4" />
          </button>

          <button
            onClick={async () => {
              await logout();
              navigate('/login');
            }}
            className="p-2 border border-slate-200 bg-white rounded-xl text-slate-500 hover:text-rose-600 hover:border-rose-200 shadow-sm transition-all cursor-pointer"
            title={t('home.logoutTitle')}
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      <main className="flex-1 w-full max-w-7xl mx-auto px-6 sm:px-10 py-8 lg:py-10 overflow-hidden flex flex-col relative z-10 min-h-0">
        {/* Hero Banner Section */}
        <div className="mb-8 shrink-0 animate-in fade-in slide-in-from-top-4 duration-700">
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-black bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 bg-clip-text text-transparent tracking-tight leading-tight mb-3">
            {t('home.heroTitle')}
          </h1>
          <p className="text-slate-500 text-sm sm:text-base leading-relaxed max-w-4xl font-medium">
            {t('home.heroDesc')}
          </p>
        </div>

        {openOnboardingChoiceGroups.length > 0 && (
          <div className="mb-4 shrink-0 animate-in fade-in slide-in-from-top-4 duration-500">
            {openOnboardingChoiceGroups.map((g: any) => (
              <div
                key={g.id}
                className="flex items-center justify-between p-4 rounded-2xl bg-indigo-50 border border-indigo-100"
              >
                <div className="flex items-center gap-3">
                  <Sparkles className="w-5 h-5 text-indigo-600 shrink-0" />
                  <div>
                    <p className="text-sm font-bold text-indigo-900">
                      {t('home.draftRecoverTitle', { count: 1 })}
                    </p>
                    <p className="text-xs text-indigo-600 mt-0.5">
                      {g.userRequirements?.slice(0, 60)} — {formatGroupTime(g.createdAt)}
                    </p>
                  </div>
                </div>
                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={() => handleRecoverGroup(g.id)}
                    className="h-9 px-4 rounded-xl bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-700 transition-colors"
                  >
                    {t('home.draftRecoverBtn')}
                  </button>
                  <button
                    onClick={() => handleDiscardGroup(g.id)}
                    className="h-9 px-4 rounded-xl border border-indigo-200 text-indigo-600 text-xs font-bold hover:bg-indigo-100 transition-colors"
                  >
                    {t('home.draftDiscardBtn')}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Dashboard Main Columns */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 h-full min-h-0 flex-1 overflow-hidden">
          
          {/* Left Column: Create App Premium Panel */}
          <button
            type="button"
            onClick={() => navigate('/onboarding')}
            className="lg:col-span-4 self-start text-left bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 text-white rounded-3xl cursor-pointer transition-all hover:shadow-2xl hover:shadow-indigo-950/20 hover:-translate-y-1 hover:border-indigo-500/30 flex flex-col p-8 group relative overflow-hidden min-h-[340px] border border-slate-800 shadow-xl"
          >
            {/* Ambient Purple Light Inside Card */}
            <div className="absolute -right-16 -top-16 w-36 h-36 bg-indigo-500/15 rounded-full blur-3xl group-hover:bg-indigo-500/25 transition-all duration-500" />
            
            <div className="w-14 h-14 bg-white/10 backdrop-blur-md rounded-2xl flex items-center justify-center mb-16 border border-white/10 group-hover:scale-110 group-hover:border-indigo-400/40 transition-all duration-300 shadow-inner">
              <Plus className="w-7 h-7 text-white" />
            </div>
            
            <div className="mt-auto relative z-10">
              <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2 group-hover:text-indigo-200 transition-colors">
                {t('home.createNewProject')}
                <ArrowRight className="w-5 h-5 opacity-0 -translate-x-3 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300 text-indigo-400" />
              </h2>
            </div>
          </button>

          {/* Right Column: Projects List Panel */}
          <section className="lg:col-span-8 flex min-h-0 flex-col pb-4">
            <div className="flex items-center justify-between mb-4 px-1 shrink-0">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-extrabold text-slate-800 tracking-wider uppercase">{t('home.activeProjects')}</h2>
                <span className="px-2 py-0.5 bg-indigo-50 border border-indigo-100 text-indigo-600 rounded-md text-[10px] font-extrabold">{sorted.length}</span>
              </div>
              <span className="text-xs text-slate-400 font-medium">{t('home.updatedAtSort')}</span>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto rounded-3xl border border-slate-200/60 bg-white/80 backdrop-blur-md shadow-lg p-5 space-y-4">
              {sorted.map((p) => (
                <div
                  key={p.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => void handleOpenWorkspace(String(p.id))}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') void handleOpenWorkspace(String(p.id));
                  }}
                  className="group flex items-start gap-4 border border-slate-100 hover:border-indigo-200 p-5 transition-all duration-300 hover:shadow-md bg-white rounded-2xl hover:bg-indigo-50/10 cursor-pointer"
                >
                  {/* Left Project Avatar Icon */}
                  <div className="mt-1 h-12 w-12 shrink-0 rounded-2xl border border-indigo-50 bg-indigo-50/50 text-indigo-600 flex items-center justify-center transition-colors group-hover:bg-indigo-600 group-hover:text-white shadow-sm">
                    <AppWindow className="h-5.5 w-5.5" />
                  </div>

                  {/* Mid Project Information */}
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-3">
                      <h3 className="truncate text-base font-extrabold text-slate-900 group-hover:text-indigo-600 transition-colors">
                        {p.name}
                      </h3>
                      {renderStatus(p)}
                    </div>
                    <p className="mt-1.5 line-clamp-2 text-xs sm:text-sm leading-relaxed text-slate-500 font-medium">
                      {p.description || p.idea || t('home.noDescription')}
                    </p>
                    <div className="mt-4 flex items-center gap-4 text-[10px] font-bold text-slate-400">
                      <div className="flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5" />
                        {formatRelativeTime(p.updatedAt)}
                      </div>
                    </div>
                  </div>

                  {/* Right Actions Trigger */}
                  <div className="ml-auto flex shrink-0 items-center gap-2 self-center opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        startEditing(p);
                      }}
                      className="rounded-xl border border-slate-200 bg-white p-2.5 text-slate-500 shadow-sm transition-all hover:border-indigo-300 hover:text-indigo-600 hover:bg-indigo-50"
                      title={t('home.editProject')}
                    >
                      <Edit className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        void handleDelete(p);
                      }}
                      className="rounded-xl border border-slate-200 bg-white p-2.5 text-slate-500 shadow-sm transition-all hover:border-rose-300 hover:text-rose-600 hover:bg-rose-50"
                      title={t('home.deleteProject')}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}

              {!isLoading && sorted.length === 0 && (
                <div className="flex h-full min-h-[300px] flex-col items-center justify-center p-10 text-center">
                  <div className="w-16 h-16 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-center text-slate-400 mb-4 shadow-sm">
                    <AppWindow className="h-8 w-8" />
                  </div>
                  <div className="text-sm font-extrabold text-slate-800">{t('home.noProjectsTitle')}</div>
                  <div className="mt-1.5 text-xs text-slate-500 max-w-xs leading-normal">{t('home.noProjectsDesc')}</div>
                </div>
              )}

              {isLoading && sorted.length === 0 && (
                <div className="flex h-full min-h-[300px] flex-col items-center justify-center p-10 text-center">
                  <div className="h-10 w-10 rounded-full border-4 border-slate-100 border-t-indigo-600 animate-spin mb-4" />
                  <div className="text-xs text-slate-500 font-bold">{t('home.loadingProjects')}</div>
                </div>
              )}
            </div>

            {error && <div className="mt-4 text-xs font-bold text-rose-600 bg-rose-50 border border-rose-100 rounded-xl p-3 shadow-inner">{getFriendlyErrorMessage(error)}</div>}
          </section>
        </div>
      </main>

      {editingProject && (
        <div className="fixed inset-0 bg-slate-950/40 backdrop-blur-md flex items-center justify-center z-50 animate-in fade-in duration-350">
          <div className="bg-white rounded-3xl p-7 max-w-lg w-full border border-slate-100 shadow-2xl space-y-6 mx-4 animate-in zoom-in-95 duration-250">
            <div>
              <h3 className="text-lg font-black text-slate-900 tracking-tight">{t('home.editModal.title')}</h3>
              <p className="text-xs text-slate-400 mt-1">{t('home.editModal.subtitle')}</p>
            </div>

            <div className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">{t('home.editModal.nameLabel')}</label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800 font-bold"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">{t('home.editModal.descLabel')}</label>
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  rows={4}
                  className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm text-slate-800 leading-relaxed resize-none font-medium"
                />
              </div>
            </div>

            <div className="flex gap-3 justify-end pt-2">
              <button
                type="button"
                onClick={() => setEditingProject(null)}
                className="px-5 py-2.5 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors shadow-sm"
              >
                {t('home.editModal.cancel')}
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (!editName.trim()) {
                    window.alert(t('home.editModal.nameRequired'));
                    return;
                  }
                  await updateProject(editingProject.id, editName.trim(), editDescription.trim());
                  setEditingProject(null);
                  await loadWorkspaces();
                }}
                className="px-5 py-2.5 bg-indigo-600 text-white text-xs font-bold rounded-xl hover:bg-indigo-700 transition-colors shadow-md shadow-indigo-600/10"
              >
                {t('home.editModal.save')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
