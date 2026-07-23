import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { X, UserPlus, Trash2, ShieldAlert, Loader2, Users } from 'lucide-react';
import { ProjectMember } from '@/core/schema';
import { workspaceApi } from '@/lib/api';

interface ProjectMembersModalProps {
  projectId: string;
  currentUserId: number;
  onClose: () => void;
}

export default function ProjectMembersModal({ projectId, currentUserId, onClose }: ProjectMembersModalProps) {
  const { t, i18n } = useTranslation();
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('viewer');
  const [submitting, setSubmitting] = useState(false);

  const fetchMembers = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await workspaceApi.listProjectMembers(projectId);
      setMembers(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || t('projectMembers.errorLoadMembers'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMembers();
  }, [projectId]);

  // Find the role of the current logged-in user in this project
  const currentMember = members.find(m => m.userId === currentUserId);
  const currentUserRole = currentMember?.role || 'viewer';
  const canManage = currentUserRole === 'owner' || currentUserRole === 'admin';

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;

    try {
      setSubmitting(true);
      setError(null);
      await workspaceApi.addProjectMember(projectId, email.trim(), role);
      setEmail('');
      setRole('viewer');
      await fetchMembers();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (detail === 'user_not_found') {
        setError(t('projectMembers.errorInviteNotFound'));
      } else if (detail === 'member_already_exists') {
        setError(t('projectMembers.errorInviteDuplicate'));
      } else {
        setError(detail || err?.message || t('projectMembers.errorInviteFailed'));
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleRoleChange = async (memberId: number, newRole: string, currentStatus: string) => {
    try {
      setError(null);
      await workspaceApi.updateProjectMember(projectId, memberId, newRole, currentStatus);
      await fetchMembers();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (detail === 'cannot_remove_last_owner') {
        setError(t('projectMembers.errorUpdateRoleMinOwner'));
      } else {
        setError(detail || err?.message || t('projectMembers.errorUpdateRoleFailed'));
      }
    }
  };

  const handleRemoveMember = async (memberId: number) => {
    if (!confirm(t('projectMembers.confirmRemove'))) return;

    try {
      setError(null);
      await workspaceApi.removeProjectMember(projectId, memberId);
      await fetchMembers();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (detail === 'cannot_remove_last_owner') {
        setError(t('projectMembers.errorRemoveMinOwner'));
      } else {
        setError(detail || err?.message || t('projectMembers.errorRemoveFailed'));
      }
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fade-in">
      <div className="bg-white rounded-3xl max-w-2xl w-full shadow-2xl overflow-hidden border border-slate-100 flex flex-col max-h-[85vh] animate-scale-up">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-indigo-600" />
            <h2 className="text-base font-black text-slate-800">{t('projectMembers.modalTitle')}</h2>
          </div>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-slate-200 text-slate-400 hover:text-slate-600 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {error && (
            <div className="bg-rose-50 border border-rose-100 text-rose-600 rounded-xl p-3.5 text-xs font-bold flex items-start gap-2">
              <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
              <div>{error}</div>
            </div>
          )}

          {/* Add Member Form (For Owners and Admins) */}
          {canManage && (
            <form onSubmit={handleAddMember} className="bg-slate-50 border border-slate-200/60 rounded-2xl p-4 space-y-3">
              <h3 className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                <UserPlus className="w-4 h-4 text-slate-500" />
                {t('projectMembers.inviteHeader')}
              </h3>
              <div className="flex flex-col sm:flex-row gap-3">
                <input
                  type="email"
                  placeholder={t('projectMembers.invitePlaceholder')}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="flex-1 bg-white border border-slate-200 rounded-xl px-3.5 py-2 text-xs focus:outline-none focus:border-indigo-500 shadow-sm"
                  required
                />
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="bg-white border border-slate-200 rounded-xl px-3.5 py-2 text-xs focus:outline-none focus:border-indigo-500 shadow-sm min-w-[120px]"
                >
                  <option value="viewer">{t('projectMembers.roleViewer')}</option>
                  <option value="reviewer">{t('projectMembers.roleReviewer')}</option>
                  <option value="editor">{t('projectMembers.roleEditor')}</option>
                  <option value="admin">{t('projectMembers.roleAdmin')}</option>
                  <option value="owner">{t('projectMembers.roleOwner')}</option>
                </select>
                <button
                  type="submit"
                  disabled={submitting}
                  className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white rounded-xl px-4 py-2 text-xs font-bold transition-all shadow-md active:scale-95 flex items-center justify-center gap-1.5 shrink-0 cursor-pointer"
                >
                  {submitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{t('projectMembers.inviteBtn')}</span>
                </button>
              </div>
            </form>
          )}

          {/* Members List */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-slate-500">{t('projectMembers.membersListHeader', { count: members.length })}</h3>
            {loading ? (
              <div className="flex flex-col items-center justify-center py-12 text-slate-400 gap-2">
                <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
                <span className="text-xs font-medium">{t('projectMembers.loadingMembers')}</span>
              </div>
            ) : (
              <div className="border border-slate-200 rounded-2xl overflow-hidden divide-y divide-slate-100 bg-white">
                {members.map((member) => {
                  const isSelf = member.userId === currentUserId;
                  
                  return (
                    <div key={member.memberId} className="px-4 py-3.5 flex items-center justify-between gap-4 hover:bg-slate-50/50 transition-colors">
                      <div className="space-y-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-slate-800 truncate block max-w-[240px]">{member.email}</span>
                          {isSelf && (
                            <span className="text-[10px] px-1.5 py-0.5 bg-indigo-50 text-indigo-600 rounded-full font-bold border border-indigo-100">
                              {t('projectMembers.currentUserSelf')}
                            </span>
                          )}
                          {member.status !== 'active' && (
                            <span className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded-full font-bold border border-slate-200">
                              {member.status === 'invited' ? t('projectMembers.statusInvited') : t('projectMembers.statusRemoved')}
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-slate-400 font-medium">
                          {member.joinedAt ? t('projectMembers.joinedAtLabel', { date: new Date(member.joinedAt).toLocaleDateString(i18n.language) }) : t('projectMembers.notJoinedYet')}
                        </div>
                      </div>

                      <div className="flex items-center gap-3 shrink-0">
                        {/* Role selector */}
                        {canManage && !isSelf ? (
                          <select
                            value={member.role}
                            disabled={member.status !== 'active'}
                            onChange={(e) => handleRoleChange(member.memberId, e.target.value, member.status)}
                            className="bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:border-indigo-500 shadow-sm"
                          >
                            <option value="viewer">Viewer</option>
                            <option value="reviewer">Reviewer</option>
                            <option value="editor">Editor</option>
                            <option value="admin">Admin</option>
                            <option value="owner">Owner</option>
                          </select>
                        ) : (
                          <span className="text-xs px-2.5 py-1 bg-slate-100 text-slate-700 border border-slate-200 rounded-lg font-bold">
                            {member.role.toUpperCase()}
                          </span>
                        )}

                        {/* Remove button */}
                        {canManage && !isSelf && member.status === 'active' && (
                          <button
                            onClick={() => handleRemoveMember(member.memberId)}
                            className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg border border-transparent hover:border-rose-100 transition-all cursor-pointer"
                            title={t('projectMembers.removeTooltip')}
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-slate-50/50 border-t border-slate-100 flex justify-end">
          <button
            onClick={onClose}
            className="text-xs px-5 py-2.5 rounded-xl border border-slate-200 hover:bg-slate-100 text-slate-600 font-bold transition-colors shadow-sm cursor-pointer"
          >
            {t('projectMembers.closeBtn')}
          </button>
        </div>
      </div>
    </div>
  );
}
