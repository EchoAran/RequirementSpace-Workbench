import { useTranslation } from 'react-i18next';
import i18n from 'i18next';
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { ActorNode, Choice, ChoiceGroup, Finding, RequirementSpaceIR, RequirementSlot, NodeStatus, ProjectMember } from '@/core/schema';
import { selectSelectedObject, useWorkspaceStore } from '@/store/useWorkspaceStore';
import { ChoiceGroupPanel } from '../right-panel/ChoiceGroupPanel';
import { ChoicePanel } from '../right-panel/ChoicePanel';
import { IssuePanel } from '../right-panel/IssuePanel';
import { NodePanel } from '../right-panel/NodePanel';
import { PanelShell, Section, TextField, SelectField, ActionRow, ActionButton } from '../right-panel/shared';
import { SlotPanel } from '../right-panel/SlotPanel';
import { StatusBadge } from './StatusBadge';
import { ChevronLeft, ChevronRight, UserCheck, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { normalizeScopeStatus } from '@/core/selectors';
import { GherkinVisualRenderer, GherkinVisualEditor } from './GherkinVisualizer';
import { useAuthStore } from '@/store/useAuthStore';
import { workspaceApi } from '@/lib/api';
import { TaskDecisionModal } from './TaskDecisionModal';

const findChoiceById = (ir: RequirementSpaceIR | null, choiceId: string | null): Choice | null => {
  if (!ir || !choiceId) return null;
  for (const group of Object.values(ir.choiceGroups || {})) {
    const choice = (group.choices || []).find((item: Choice) => item.id === choiceId);
    if (choice) return choice;
  }
  return null;
};

class PanelErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("PanelErrorBoundary caught an error", error, errorInfo);
  }

  render() {
    const t = (key: string) => i18n.t(key);
    if (this.state.hasError) {
      return (
        <PanelShell title={t ? t("rightPanel.renderErrorTitle") : "Render Error"} subtitle={t ? t("rightPanel.renderErrorDesc") : "Component render error"}>
          <div className="p-4 border border-rose-200 bg-rose-50/50 rounded-2xl space-y-4">
            <div className="text-sm font-bold text-rose-700">{t ? t("rightPanel.editError") : "Panel render component crashed"}</div>
            <div className="text-xs text-rose-600 font-medium leading-relaxed">
              {t ? t('rightPanel.errorMsg') : 'Error Message'}: {this.state.error?.message || (t ? t('rightPanel.unknownException') : 'Unknown exception')}
            </div>
            <pre className="text-[10px] text-slate-700 bg-slate-50 border border-slate-100 rounded-xl p-3 max-h-[300px] overflow-auto font-mono">
              {this.state.error?.stack || (t ? t('rightPanel.noStack') : 'No stack trace')}
            </pre>
            <div className="text-[10px] text-slate-500">
              {t ? t('rightPanel.reportErrorTip') : 'Please screenshot or copy this error to development team.'}
            </div>
          </div>
        </PanelShell>
      );
    }

    return this.props.children;
  }
}

// Confirmation status options




// Common confirmation status edit section
function ConfirmationStatusSection({
  nodeKind,
  selectedObject,
  fallbackStatus = 'confirmed',
  disabled = false,
  value,
  onChange,
}: {
  nodeKind: string;
  selectedObject: any;
  fallbackStatus?: string;
  disabled?: boolean;
  value?: string;
  onChange?: (value: string) => void;
}) {
  const { t } = useTranslation();
  const setNodeStatus = useWorkspaceStore((state) => state.setNodeStatus);
  const projectId = useWorkspaceStore((state) => state.ir?.projectId);
  const tasks = useWorkspaceStore((state) => state.tasks || []);
  const loadProjectTasks = useWorkspaceStore((state) => state.loadProjectTasks);
  const createConfirmationTask = useWorkspaceStore((state) => state.createConfirmationTask);
  const user = useAuthStore((state) => state.user);

  const [projectMembers, setProjectMembers] = useState<ProjectMember[]>([]);
  const [showAssignForm, setShowAssignForm] = useState(false);
  const [showDecisionModal, setShowDecisionModal] = useState(false);
  const [assigneeId, setAssigneeId] = useState<number | ''>('');
  const [taskTitle, setTaskTitle] = useState('');
  const [taskDesc, setTaskDesc] = useState('');
  const [priority, setPriority] = useState('normal');
  const [dueAt, setDueAt] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);

  const nodeId = selectedObject.actorId ?? selectedObject.featureId ?? selectedObject.scenarioId
    ?? selectedObject.criterionId ?? selectedObject.businessObjectId ?? selectedObject.flowId
    ?? selectedObject.businessObjectAttributeId ?? selectedObject.stepId ?? selectedObject.scopeId;

  const displayStatus = value ?? selectedObject.confirmationStatus ?? fallbackStatus;

  useEffect(() => {
    if (projectId) {
      loadProjectTasks(projectId);
      workspaceApi.listProjectMembers(projectId).then(setProjectMembers).catch(console.error);
    }
  }, [projectId, loadProjectTasks]);

  const openTask = useMemo(() => {
    if (!nodeId) return null;
    return tasks.find(
      (t) =>
        t.targetType === nodeKind &&
        t.targetId === String(nodeId) &&
        t.status === 'open'
    );
  }, [tasks, nodeKind, nodeId]);

  const currentMember = useMemo(() => {
    if (!user) return null;
    return projectMembers.find((m) => m.userId === user.id);
  }, [projectMembers, user]);

  const currentUserRole = currentMember?.role || 'viewer';
  const canAssign = currentUserRole === 'owner' || currentUserRole === 'admin' || currentUserRole === 'editor';
  const potentialAssignees = useMemo(() => {
    return projectMembers.filter((m) => m.status === 'active' && m.role !== 'viewer');
  }, [projectMembers]);

  const handleChange = useCallback((nextValue: string) => {
    if (disabled || (currentUserRole === 'reviewer' && displayStatus !== 'confirmed')) return;
    if (onChange) {
      onChange(nextValue);
      return;
    }
    if (nodeId != null) {
      void setNodeStatus(nodeId.toString(), nodeKind, nextValue as NodeStatus);
    }
  }, [disabled, nodeKind, onChange, selectedObject, setNodeStatus, currentUserRole, displayStatus, nodeId]);

  const handleAssign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectId || !nodeId || !assigneeId) return;
    try {
      setSubmitting(true);
      setAssignError(null);
      await createConfirmationTask(projectId, {
        nodeKind,
        nodeId,
        assignedToUserId: Number(assigneeId),
        title: taskTitle.trim() || undefined,
        description: taskDesc.trim() || undefined,
        priority,
        dueAt: dueAt || undefined,
      });
      setShowAssignForm(false);
      setAssigneeId('');
      setTaskTitle('');
      setTaskDesc('');
      setPriority('normal');
      setDueAt('');
    } catch (err: any) {
      setAssignError(err?.response?.data?.detail || err?.message || t('rightPanel.assignError'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Section title={t("rightPanel.nodeReviewAndAssign")}>
      <div className="space-y-4">
        {/* Core Dropdown */}
        <SelectField
          label={t("rightPanel.confirmStatusTitle")}
          value={displayStatus}
          options={[
            { value: 'confirmed', label: t('panel.nodeStatus.confirmed') },
            { value: 'needs_confirmation', label: t('panel.nodeStatus.needs_confirmation') },
            { value: 'ai_assumption', label: t('panel.nodeStatus.ai_assumption') },
          ]}
          onChange={handleChange}
          disabled={disabled || (currentUserRole === 'reviewer' && displayStatus !== 'confirmed')}
        />

        {/* Active open task notice */}
        {openTask ? (
          <div className="bg-indigo-50/50 border border-indigo-100 rounded-xl p-3.5 space-y-3">
            <div className="flex items-start gap-2.5">
              <div className="bg-indigo-100 text-indigo-700 p-1 rounded-lg mt-0.5">
                <UserCheck className="w-3.5 h-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-bold text-indigo-900 leading-none">{t("rightPanel.pendingConfirmTask")}</div>
                <div className="text-[11px] text-indigo-700 mt-1 leading-normal">
                  {t('rightPanel.assignerLabel')}: <span className="font-semibold">{openTask.creatorEmail || openTask.createdByUserId}</span> <br />
                  {t('rightPanel.assigneeLabel')}: <span className="font-semibold">{openTask.assigneeEmail || openTask.assignedToUserId}</span>
                </div>
                {openTask.contentChanged && (
                  <div className="text-[10px] text-amber-700 mt-1.5 flex items-center gap-1 font-medium bg-amber-50 border border-amber-100 px-2 py-0.5 rounded-lg w-fit">
                    <AlertTriangle className="w-3 h-3 text-amber-600" />
                    <span>{t("rightPanel.contentModified")} ({t("rightPanel.historyStatusSuperseded")})</span>
                  </div>
                )}
              </div>
            </div>

            {/* Decide action button if assignee or admin/owner */}
            {(openTask.assignedToUserId === user?.id || currentUserRole === 'owner' || currentUserRole === 'admin') && (
              <button
                onClick={() => setShowDecisionModal(true)}
                className="w-full py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition-colors cursor-pointer"
              >
                {t('rightPanel.handleAssignTask')}
              </button>
            )}
          </div>
        ) : (
          /* Button to toggle assign form if canAssign */
          canAssign && !showAssignForm && (
            <button
              onClick={() => setShowAssignForm(true)}
              className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold flex items-center gap-1 transition-colors bg-indigo-50/30 border border-indigo-100 hover:border-indigo-200 px-3 py-1.5 rounded-xl cursor-pointer w-full justify-center"
            >
              {t('rightPanel.assignOthersToConfirm')}
            </button>
          )
        )}

        {/* Assign Form */}
        {showAssignForm && (
          <form onSubmit={handleAssign} className="bg-slate-50 rounded-xl p-4 border border-slate-200/60 space-y-3.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-700">{t("rightPanel.assignConfirmTask")}</span>
              <button
                type="button"
                onClick={() => { setShowAssignForm(false); setAssignError(null); }}
                className="text-slate-400 hover:text-slate-600 text-xs font-medium"
              >
                {t('rightPanel.cancelBtn')}
              </button>
            </div>

            {assignError && (
              <div className="text-[10px] text-rose-600 bg-rose-50 border border-rose-100 p-2 rounded-lg leading-normal">
                {assignError}
              </div>
            )}

            {/* Assignee selection */}
            <label className="block space-y-1">
              <div className="text-[10px] font-semibold text-slate-500">{t("rightPanel.assigneeLabel")}</div>
              <select
                value={assigneeId}
                onChange={(e) => setAssigneeId(e.target.value ? Number(e.target.value) : '')}
                required
                className="w-full text-xs text-slate-700 border border-slate-200 rounded-lg px-2 py-1.5 bg-white"
              >
                <option value="">{t("rightPanel.selectAssignee")}</option>
                {potentialAssignees.map((member) => (
                  <option key={member.memberId} value={member.userId}>
                    {member.email} ({member.role})
                  </option>
                ))}
              </select>
            </label>

            {/* Custom title */}
            <label className="block space-y-1">
              <div className="text-[10px] font-semibold text-slate-500">{t("rightPanel.taskTitleOptional")}</div>
              <input
                type="text"
                value={taskTitle}
                onChange={(e) => setTaskTitle(e.target.value)}
                placeholder={t("rightPanel.taskTitlePlaceholder")}
                className="w-full text-xs text-slate-700 border border-slate-200 rounded-lg px-2.5 py-1.5"
              />
            </label>

            {/* Custom description */}
            <label className="block space-y-1">
              <div className="text-[10px] font-semibold text-slate-500">{t("rightPanel.assignNotesOptional")}</div>
              <textarea
                value={taskDesc}
                onChange={(e) => setTaskDesc(e.target.value)}
                placeholder={t("rightPanel.assignNotesPlaceholder")}
                className="w-full text-xs text-slate-700 border border-slate-200 rounded-lg px-2.5 py-1.5 min-h-[50px]"
              />
            </label>

            {/* Priority and Due Date */}
            <div className="grid grid-cols-2 gap-3">
              <label className="block space-y-1">
                <div className="text-[10px] font-semibold text-slate-500">{t('rightPanel.assignPriority')}</div>
                <select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  className="w-full text-xs text-slate-700 border border-slate-200 rounded-lg px-2 py-1.5 bg-white"
                >
                  <option value="low">{t('rightPanel.assignLow')}</option>
                  <option value="normal">{t('rightPanel.assignNormal')}</option>
                  <option value="high">{t('rightPanel.assignHigh')}</option>
                </select>
              </label>

              <label className="block space-y-1">
                <div className="text-[10px] font-semibold text-slate-500">{t("rightPanel.deadlineLabel")}</div>
                <input
                  type="date"
                  value={dueAt}
                  onChange={(e) => setDueAt(e.target.value)}
                  className="w-full text-xs text-slate-700 border border-slate-200 rounded-lg px-2 py-1 bg-white"
                />
              </label>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm disabled:opacity-50 transition-colors cursor-pointer"
            >
              {submitting ? t('rightPanel.submittingAssign') : t('rightPanel.submitAssign')}
            </button>
          </form>
        )}

        {/* Historical tasks */}
        {(() => {
          const historicalTasks = tasks.filter(
            (task: any) =>
              task.status !== 'open' && (
                (task.targetType === nodeKind && String(task.targetId) === String(nodeId)) ||
                (task.taskType === 'confirm_nodes' && Array.isArray(task.targets) && task.targets.some((target: any) => target.node_kind === nodeKind && String(target.node_id) === String(nodeId)))
              )
          );
          if (historicalTasks.length === 0) return null;
          return (
            <div className="mt-4 pt-4 border-t border-slate-100 space-y-2.5">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">{t("rightPanel.historyLogsTitle")}</div>
              <div className="space-y-2 max-h-48 overflow-y-auto pr-1 scrollbar-thin">
                {historicalTasks.map((task: any) => (
                  <div key={task.id} className="border border-slate-150 rounded-xl p-3 bg-slate-50/30 text-xs space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-700 truncate max-w-[150px]">{task.title}</span>
                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${
                        task.status === 'done'
                          ? 'bg-emerald-50 text-emerald-600'
                          : task.status === 'rejected'
                          ? 'bg-rose-50 text-rose-600'
                          : 'bg-slate-100 text-slate-500'
                      }`}>
                        {task.status === 'done' ? t('rightPanel.historyStatusDone') : task.status === 'rejected' ? t('rightPanel.historyStatusRejected') : task.status === 'superseded' ? t('rightPanel.historySuperseded') : t('rightPanel.historyCancelled')}
                      </span>
                    </div>
                    <div className="text-[10px] text-slate-400">
                      {t("rightPanel.assigneeLabel")}: <span className="font-medium text-slate-500">{task.assigneeEmail || task.assignedToUserId}</span>
                    </div>
                    {task.decisionNote && (
                      <div className="bg-white border border-slate-100 rounded-lg p-2 text-[11px] text-slate-600 leading-relaxed whitespace-pre-wrap">
                        {task.decisionNote}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          );
        })()}
      </div>

      {/* Decision Modal */}
      {showDecisionModal && openTask && (
        <TaskDecisionModal
          task={openTask}
          projectId={projectId || ''}
          onClose={() => setShowDecisionModal(false)}
          onDecided={async () => {
            setShowDecisionModal(false);
            if (projectId) {
              await loadProjectTasks(projectId);
            }
          }}
        />
      )}
    </Section>
  );
}

// 0. Dedicated Project Panel
function ProjectObjectPanel({ selectedObject }: { selectedObject: any }) {
  const { t } = useTranslation();
  const ir = useWorkspaceStore((state) => state.ir);
  const updateProject = useWorkspaceStore((state) => state.updateProject);
  const [projName, setProjName] = useState(ir?.projectName || '');
  const [projDesc, setProjDesc] = useState(ir?.projectDescription || '');

  useEffect(() => {
    setProjName(ir?.projectName || '');
    setProjDesc(ir?.projectDescription || '');
  }, [ir]);

  const handleSave = async () => {
    if (ir) {
      await updateProject(ir.projectId, projName, projDesc);
    }
  };

  return (
    <PanelShell title={projName} subtitle={t('rightPanel.systemRootNode')}>
      <Section title={t("rightPanel.systemRootEdit")}>
        <TextField label={t("rightPanel.systemNameLabel")} value={projName} onChange={setProjName} />
        <TextField label={t("rightPanel.systemDescLabel")} value={projDesc} onChange={setProjDesc} multiline />
        <ActionRow>
          <ActionButton onClick={() => void handleSave()}>{t("rightPanel.saveAttrChanges")}</ActionButton>
          <ActionButton variant="secondary" onClick={() => { setProjName(ir?.projectName || ''); setProjDesc(ir?.projectDescription || ''); }}>
            {t('rightPanel.resetBtn')}
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}

// 1. Dedicated Actor Panel
function ActorObjectPanel({ selectedObject }: { selectedObject: any }) {
  const { t } = useTranslation();
  const updateActor = useWorkspaceStore((state) => state.updateActor);
  const [actorName, setActorName] = useState(selectedObject.actorName || '');
  const [actorDesc, setActorDesc] = useState(selectedObject.actorDescription || '');

  useEffect(() => {
    setActorName(selectedObject.actorName || '');
    setActorDesc(selectedObject.actorDescription || '');
  }, [selectedObject]);

  const handleSave = async () => {
    await updateActor(selectedObject.actorId, { 
      actorName, 
      actorDescription: actorDesc 
    });
  };

  return (
    <PanelShell title={actorName} subtitle={t("rightPanel.actorSubtitle")}>
      <ConfirmationStatusSection nodeKind="actor" selectedObject={selectedObject} />
      <Section title={t("rightPanel.actorBaseAttrs")}>
        <TextField label={t("rightPanel.actorName")} value={actorName} onChange={setActorName} />
        <TextField label={t("rightPanel.actorDesc")} value={actorDesc} onChange={setActorDesc} multiline />
        <ActionRow>
          <ActionButton onClick={() => void handleSave()}>{t("rightPanel.saveBtn")}</ActionButton>
          <ActionButton variant="secondary" onClick={() => { setActorName(selectedObject.actorName || ''); setActorDesc(selectedObject.actorDescription || ''); }}>
            {t('rightPanel.resetBtn')}
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}

// 2. Dedicated Feature Panel
function FeatureObjectPanel({ selectedObject }: { selectedObject: any }) {
  const { t } = useTranslation();
  const ir = useWorkspaceStore((state) => state.ir);
  const activePage = useWorkspaceStore((state) => state.activePage);
  const updateFeature = useWorkspaceStore((state) => state.updateFeature);
  const updateScope = useWorkspaceStore((state) => state.updateScope);
  const setSelectedObject = useWorkspaceStore((state) => state.setSelectedObject);
  const actors = ir?.actors || [];

  // Find original feature in ir to get its scope/reason and complete fields
  const originalFeature = useMemo(() => {
    if (!ir || !ir.features) return null;
    return ir.features.find((f: any) => f.featureId.toString() === selectedObject.id?.toString() || f.featureId === selectedObject.featureId);
  }, [ir, selectedObject.id, selectedObject.featureId]);

  const feat = originalFeature || selectedObject;
  const isRoot = feat.parentId === null;

  const [featName, setFeatName] = useState(isRoot ? (ir?.projectName || feat.featureName || feat.title || '') : (feat.featureName || feat.title || ''));
  const [featDesc, setFeatDesc] = useState(isRoot ? (ir?.projectDescription || feat.featureDescription || feat.description || '') : (feat.featureDescription || feat.description || ''));
  const [featScopeStatus, setFeatScopeStatus] = useState(normalizeScopeStatus(feat.scope?.scopeStatus || feat.scopeStatus));
  const [featScopeReason, setFeatScopeReason] = useState(feat.scope?.reason || feat.reason || '');
  const [selectedActorIds, setSelectedActorIds] = useState<number[]>(feat.actorIds || []);

  useEffect(() => {
    const f = originalFeature || selectedObject;
    const isRootNode = f.parentId === null;
    setFeatName(isRootNode ? (ir?.projectName || f.featureName || f.title || '') : (f.featureName || f.title || ''));
    setFeatDesc(isRootNode ? (ir?.projectDescription || f.featureDescription || f.description || '') : (f.featureDescription || f.description || ''));
    setFeatScopeStatus(normalizeScopeStatus(f.scope?.scopeStatus || f.scopeStatus));
    setFeatScopeReason(f.scope?.reason || f.reason || '');
    setSelectedActorIds(f.actorIds || []);
  }, [selectedObject, originalFeature, ir]);

  const handleSave = async () => {
    const fId = selectedObject.featureId || feat.featureId || parseInt(selectedObject.id, 10);
    if (isNaN(fId)) return;
    await updateFeature(fId, { 
      featureName: featName, 
      featureDescription: featDesc,
      actorIds: selectedActorIds
    });
    if (activePage === '/scope') {
      await updateScope(fId, {
        scopeStatus: featScopeStatus as any,
        reason: featScopeReason
      });
    }
  };

  // Find parent capability
  const parentCap = useMemo(() => {
    if (!ir || !ir.features || selectedObject.parentId === null) return null;
    return ir.features.find((f: any) => f.featureId === selectedObject.parentId);
  }, [ir, selectedObject.parentId]);

  // Find child capabilities
  const childCaps = useMemo(() => {
    if (!ir || !ir.features) return [];
    return ir.features.filter((f: any) => f.parentId === selectedObject.featureId);
  }, [ir, selectedObject.featureId]);

  // Find associated actors
  const associatedActors = useMemo(() => {
    if (!ir || !ir.actors) return [];
    const actorIds = selectedObject.actorIds || [];
    return actorIds.map((aid: number) => ir.actors.find((a: any) => a.actorId === aid)).filter(Boolean);
  }, [ir, selectedObject.actorIds]);

  return (
    <PanelShell title={featName} subtitle={t('rightPanel.coreFeatureNode')}>
      {activePage === '/scope' && (
        <Section title={t("rightPanel.scopeAndDecision")}>
          <SelectField 
            label={t('rightPanel.scopeStatus')}
            value={featScopeStatus} 
            options={[
              { value: 'current', label: t('rightPanel.scopeOptionsCurrent') },
              { value: 'postponed', label: t('rightPanel.scopeOptionsPostponed') },
              { value: 'exclude', label: t('rightPanel.scopeOptionsExclude') }
            ]} 
            onChange={(val) => setFeatScopeStatus(normalizeScopeStatus(val))} 
          />
          <TextField label={t("rightPanel.featScopeReasonLabel")} value={featScopeReason} onChange={setFeatScopeReason} multiline />
        </Section>
      )}

      {activePage === '/scope' && feat.scope && (feat.scope.positiveSummary || feat.scope.negativeSummary || feat.scope.positivePictureBase64 || feat.scope.negativePictureBase64) && (
      <Section title={t("rightPanel.kanoSmartAnalysis")}>
          {feat.scope.positiveSummary && (
            <div className="mb-4 space-y-2">
              <div>
                <span className="text-[10px] text-emerald-600 font-extrabold uppercase tracking-wider block">{t("rightPanel.kanoPositiveUserExperience")}</span>
                <p className="text-xs text-slate-600 italic bg-emerald-50/20 border border-emerald-100/50 p-2.5 rounded-xl mt-1">
                  "{feat.scope.positiveSummary}"
                </p>
              </div>
              {feat.scope.negativeSummary && (
                <div>
                  <span className="text-[10px] text-rose-600 font-extrabold uppercase tracking-wider block">{t("rightPanel.kanoNegativeUserExperience")}</span>
                  <p className="text-xs text-slate-600 italic bg-rose-50/20 border border-rose-100/50 p-2.5 rounded-xl mt-1">
                    "{feat.scope.negativeSummary}"
                  </p>
                </div>
              )}
            </div>
          )}

          {(feat.scope.positivePictureBase64 || feat.scope.negativePictureBase64) && (
            <div className="space-y-3 pt-2 border-t border-slate-100">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">{t("rightPanel.kanoDistributionMetric")}</span>
              <div className="grid grid-cols-2 gap-2">
                {feat.scope.positivePictureBase64 && (
                  <div className="space-y-1">
                    <span className="text-[10px] text-indigo-600 font-bold block text-center">{t("rightPanel.kanoChartPositiveExperience")}</span>
                    <div className="border border-slate-200 rounded-xl overflow-hidden bg-white max-h-[140px] flex items-center justify-center p-1.5 shadow-sm hover:scale-105 transition-all cursor-zoom-in">
                      <img 
                        src={`data:image/png;base64,${feat.scope.positivePictureBase64}`} 
                        alt="Positive Distribution" 
                        className="max-h-full max-w-full object-contain"
                        onClick={() => {
                          const w = window.open();
                          w?.document.write(`<img src="data:image/png;base64,${feat.scope.positivePictureBase64}" style="max-width:100%"/>`);
                        }}
                      />
                    </div>
                  </div>
                )}
                {feat.scope.negativePictureBase64 && (
                  <div className="space-y-1">
                    <span className="text-[10px] text-slate-500 font-bold block text-center">{t("rightPanel.kanoChartNegativeExperience")}</span>
                    <div className="border border-slate-200 rounded-xl overflow-hidden bg-white max-h-[140px] flex items-center justify-center p-1.5 shadow-sm hover:scale-105 transition-all cursor-zoom-in">
                      <img 
                        src={`data:image/png;base64,${feat.scope.negativePictureBase64}`} 
                        alt="Negative Distribution" 
                        className="max-h-full max-w-full object-contain"
                        onClick={() => {
                          const w = window.open();
                          w?.document.write(`<img src="data:image/png;base64,${feat.scope.negativePictureBase64}" style="max-width:100%"/>`);
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </Section>
      )}

      <ConfirmationStatusSection nodeKind="feature" selectedObject={selectedObject} />
      <Section title={t('rightPanel.featureBaseAttrs')}>
        <TextField label={t("rightPanel.featureNameLabel")} value={featName} onChange={setFeatName} />
        <TextField label={t("rightPanel.descriptionLabel")} value={featDesc} onChange={setFeatDesc} multiline />
        <ActionRow>
          <ActionButton onClick={() => void handleSave()}>{t("rightPanel.saveAttrChanges")}</ActionButton>
          <ActionButton variant="secondary" onClick={() => { 
            const f = originalFeature || selectedObject;
            const isRootNode = f.parentId === null;
            setFeatName(isRootNode ? (ir?.projectName || f.featureName || '') : (f.featureName || '')); 
            setFeatDesc(isRootNode ? (ir?.projectDescription || f.featureDescription || '') : (f.featureDescription || '')); 
            setFeatScopeStatus(normalizeScopeStatus(f.scope?.scopeStatus));
            setFeatScopeReason(f.scope?.reason || '');
            setSelectedActorIds(f.actorIds || []);
          }}>
            {t('rightPanel.resetBtn')}
          </ActionButton>
        </ActionRow>
      </Section>

      <Section title={t("rightPanel.archRelationDefinition")}>
        <div className="space-y-3">
          <div>
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">{t("rightPanel.parentModuleLabel")}</span>
            {parentCap ? (
              <button
                type="button"
                onClick={() => setSelectedObject(parentCap)}
                className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold bg-indigo-50/50 border border-indigo-100/60 rounded-lg px-2.5 py-1.5 transition-all text-left w-full truncate"
              >
              {parentCap.parentId === null ? (ir?.projectName || parentCap.featureName) : parentCap.featureName}
              </button>
            ) : (
              <span className="text-xs text-slate-400 italic">{t('rightPanel.noParentRootFeature')}</span>
            )}
          </div>

          <div>
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">{t("rightPanel.childFeaturesLabel")}</span>
            {childCaps.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {childCaps.map((c: any) => (
                  <button
                    key={c.featureId}
                    type="button"
                    onClick={() => setSelectedObject(c)}
                    className="text-[10px] bg-slate-50 border border-slate-200 text-slate-700 hover:border-indigo-300 hover:text-indigo-700 hover:bg-white rounded-md px-2 py-0.5 font-medium transition-all"
                  >
                  {c.featureName}
                  </button>
                ))}
              </div>
            ) : (
              <span className="text-xs text-slate-400 italic">{t('rightPanel.noChildLeafFeature')}</span>
            )}
          </div>
        </div>
      </Section>

      <Section title={t("rightPanel.actorRelations")}>
        {actors.length > 0 ? (
          <div className="space-y-2 border border-slate-200/60 rounded-xl p-3 bg-slate-50/50 max-h-[160px] overflow-y-auto">
            {actors.map((actor: ActorNode) => {
              const isChecked = selectedActorIds.includes(actor.actorId);
              return (
                <label 
                  key={actor.actorId} 
                  className="flex items-center space-x-2.5 text-xs text-slate-700 font-semibold cursor-pointer select-none py-1 hover:text-indigo-600 transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    className="w-3.5 h-3.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500/20 focus:ring-offset-0 cursor-pointer"
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedActorIds([...selectedActorIds, actor.actorId]);
                      } else {
                        setSelectedActorIds(selectedActorIds.filter((id) => id !== actor.actorId));
                      }
                    }}
                  />
                <span>{actor.actorName}</span>
                </label>
              );
            })}
          </div>
        ) : (
          <span className="text-xs text-slate-500 italic">{t('rightPanel.actorRelationEmpty')}</span>
        )}
      </Section>
    </PanelShell>
  );
}

function ScopeObjectPanel({ selectedObject }: { selectedObject: any }) {
  const { t } = useTranslation();
  const ir = useWorkspaceStore((state) => state.ir);
  const updateScope = useWorkspaceStore((state) => state.updateScope);
  const setNodeStatus = useWorkspaceStore((state) => state.setNodeStatus);

  const featureId = selectedObject.featureId ?? parseInt(selectedObject.id || '', 10);
  const feature = useMemo(() => {
    if (!ir?.features || Number.isNaN(featureId)) return null;
    return ir.features.find((item: any) => item.featureId === featureId) || null;
  }, [featureId, ir]);

  const scope = feature?.scope || selectedObject.scope || null;
  const scopeId = scope?.scopeId ?? selectedObject.scopeId;
  const featureName = feature?.featureName || selectedObject.featureName || selectedObject.title || t('rightPanel.unnamedObj');
  const confirmationStatus = scope?.confirmationStatus || selectedObject.confirmationStatus || selectedObject.status || '';
  const initialScopeStatus = scope?.scopeStatus ? normalizeScopeStatus(scope.scopeStatus) : '';

  const [scopeStatus, setScopeStatus] = useState(initialScopeStatus);
  const [draftConfirmationStatus, setDraftConfirmationStatus] = useState(confirmationStatus);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setScopeStatus(scope?.scopeStatus ? normalizeScopeStatus(scope.scopeStatus) : '');
    setDraftConfirmationStatus(scope?.confirmationStatus || selectedObject.confirmationStatus || selectedObject.status || '');
  }, [scope?.scopeStatus, scope?.confirmationStatus, scopeId, featureId, selectedObject.confirmationStatus, selectedObject.status]);

  const handleSave = async () => {
    if (!featureId || !scopeStatus || isSaving) return;

    setIsSaving(true);
    try {
      await updateScope(featureId, {
        scopeStatus: scopeStatus as any,
        reason: scope?.reason || '',
        positiveSummary: scope?.positiveSummary || null,
        negativeSummary: scope?.negativeSummary || null,
      });

      const latestFeature = useWorkspaceStore.getState().ir?.features?.find((item: any) => item.featureId === featureId);
      const latestScopeId = latestFeature?.scope?.scopeId;
      const latestConfirmationStatus = latestFeature?.scope?.confirmationStatus || '';

      if (
        latestScopeId &&
        draftConfirmationStatus &&
        draftConfirmationStatus !== latestConfirmationStatus
      ) {
        await setNodeStatus(latestScopeId.toString(), 'scope', draftConfirmationStatus as NodeStatus);
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    setScopeStatus(scope?.scopeStatus ? normalizeScopeStatus(scope.scopeStatus) : '');
    setDraftConfirmationStatus(scope?.confirmationStatus || selectedObject.confirmationStatus || selectedObject.status || '');
  };

  return (
    <PanelShell title={featureName} subtitle={t("rightPanel.scopeSubtitle") + " / " + t("rightPanel.scopeDecisionSubtitle")}>
      <Section title={t("rightPanel.statusAndScope")}>
        <div className="flex flex-wrap gap-2">
          {draftConfirmationStatus ? <StatusBadge status={draftConfirmationStatus} /> : null}
          <span className="inline-flex px-2 py-1 rounded-full bg-slate-100 text-slate-600 text-xs font-semibold">
            {scopeStatus
              ? [
    { value: '', label: t('rightPanel.scopeOptionsNotDecided') },
    { value: 'current', label: t('rightPanel.scopeOptionsCurrent') },
    { value: 'postponed', label: t('rightPanel.scopeOptionsPostponed') },
    { value: 'exclude', label: t('rightPanel.scopeOptionsExclude') },
  ].find((option) => option.value === scopeStatus)?.label || scopeStatus
              : t('rightPanel.scopeOptionsNotDecided')}
          </span>
        </div>
      </Section>

      <ConfirmationStatusSection
        nodeKind="scope"
        selectedObject={{ ...selectedObject, scopeId, confirmationStatus: draftConfirmationStatus }}
        fallbackStatus="needs_confirmation"
        disabled={!scopeId || isSaving}
        value={draftConfirmationStatus}
        onChange={setDraftConfirmationStatus}
      />

      <Section title={t('rightPanel.scopeTitle')}>
        <SelectField
          label={t('rightPanel.scopeStatus')}
          value={scopeStatus}
          options={[
    { value: '', label: t('rightPanel.scopeOptionsNotDecided') },
    { value: 'current', label: t('rightPanel.scopeOptionsCurrent') },
    { value: 'postponed', label: t('rightPanel.scopeOptionsPostponed') },
    { value: 'exclude', label: t('rightPanel.scopeOptionsExclude') },
  ]}
          onChange={setScopeStatus}
        />
        {!scopeId && (
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500 leading-relaxed">
            {t('rightPanel.scopeKanoDesc')}
          </div>
        )}
        <ActionRow>
          <ActionButton onClick={() => void handleSave()}>
            {isSaving ? t('panel.saving') : t('rightPanel.saveBtn')}
          </ActionButton>
          <ActionButton variant="secondary" onClick={handleReset}>
            {t('rightPanel.resetBtn')}
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}

// 3. Dedicated Business Object Panel
function BusinessObjectPanel({ selectedObject }: { selectedObject: any }) {
  const { t } = useTranslation();
  const updateBusinessObject = useWorkspaceStore((state) => state.updateBusinessObject);
  const [boName, setBoName] = useState(selectedObject.businessObjectName || '');
  const [boDesc, setBoDesc] = useState(selectedObject.businessObjectDescription || '');

  useEffect(() => {
    setBoName(selectedObject.businessObjectName || '');
    setBoDesc(selectedObject.businessObjectDescription || '');
  }, [selectedObject]);

  const handleSave = async () => {
    await updateBusinessObject(selectedObject.businessObjectId, boName, boDesc);
  };

  return (
    <PanelShell title={boName} subtitle={t("rightPanel.coreBoSubtitle")}>
      <Section title={t("rightPanel.boBaseAttrs")}>
        <TextField label={t("rightPanel.boName")} value={boName} onChange={setBoName} />
        <TextField label={t('rightPanel.boDesc')} value={boDesc} onChange={setBoDesc} multiline />
        <ActionRow>
          <ActionButton onClick={() => void handleSave()}>{t("rightPanel.saveBtn")}</ActionButton>
          <ActionButton variant="secondary" onClick={() => { setBoName(selectedObject.businessObjectName || ''); setBoDesc(selectedObject.businessObjectDescription || ''); }}>
            {t('rightPanel.resetBtn')}
          </ActionButton>
        </ActionRow>
      </Section>

      <ConfirmationStatusSection nodeKind="business_object" selectedObject={selectedObject} />
      <Section title={t("rightPanel.boAttrSubtitle") + t("rightPanel.boAttrDefinition")}>
        {(selectedObject.businessObjectAttributes || []).length === 0 ? (
          <div className="text-xs text-slate-400 italic">{t('rightPanel.boNoFields')}</div>
        ) : (
          <div className="space-y-3 select-text">
            {(selectedObject.businessObjectAttributes || []).map((attr: any) => (
              <div key={attr.businessObjectAttributeId} className="border border-slate-200 rounded-xl p-3 bg-slate-50/50 space-y-1.5 shadow-sm">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-slate-800 text-xs">{attr.businessObjectAttributeName}</span>
                  <div className="flex items-center gap-1.5">
                    <StatusBadge status={attr.confirmationStatus || 'ai_assumption'} />
                    <span className="text-[10px] bg-slate-100 border border-slate-200 rounded px-1.5 py-0.5 font-mono text-slate-500 font-bold">{attr.businessObjectAttributeType}</span>
                  </div>
                </div>
                <div className="text-xs text-slate-500 font-medium leading-relaxed">{attr.businessObjectAttributeDescription}</div>
                {attr.businessObjectAttributeExample && (
                  <div className="text-[10px] text-indigo-600 bg-indigo-50/40 p-1.5 rounded font-mono leading-none">
                    {t('rightPanel.fieldExample')}: {attr.businessObjectAttributeExample}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Section>
    </PanelShell>
  );
}

function BusinessObjectAttributePanel({ selectedObject }: { selectedObject: any }) {
  const { t } = useTranslation();
  return (
    <PanelShell title={selectedObject.businessObjectAttributeName || (t('rightPanel.unnamedObj') + t('rightPanel.boAttrSubtitle2'))} subtitle={t('rightPanel.boSubtitle') + t('rightPanel.boAttrSubtitle2')}>
      <ConfirmationStatusSection nodeKind="business_object_attribute" selectedObject={selectedObject} />
      <Section title={t("rightPanel.boAttrDetailTitle")}>
        <div className="space-y-3 text-xs text-slate-600">
          <div>
            <div className="font-bold text-slate-400">{t("rightPanel.boAttrTypeTitle")}</div>
            <div className="mt-1 font-mono text-slate-800">{selectedObject.businessObjectAttributeType || '-'}</div>
          </div>
          <div>
            <div className="font-bold text-slate-400">{t("rightPanel.boAttrDesc")}</div>
            <div className="mt-1 leading-relaxed text-slate-800">{selectedObject.businessObjectAttributeDescription || '-'}</div>
          </div>
          <div>
            <div className="font-bold text-slate-400">{t("rightPanel.boAttrExample")}</div>
            <div className="mt-1 font-mono text-indigo-700">{selectedObject.businessObjectAttributeExample || '-'}</div>
          </div>
        </div>
      </Section>
    </PanelShell>
  );
}

// 4. Dedicated Flow Step Panel
function FlowStepObjectPanel({ selectedObject, ir }: { selectedObject: any; ir: any }) {
  const { t } = useTranslation();
  const updateFlowStep = useWorkspaceStore((state) => state.updateFlowStep);
  const [stepName, setStepName] = useState(selectedObject.stepName || '');
  const [stepDesc, setStepDesc] = useState(selectedObject.stepDescription || '');
  const [stepType, setStepType] = useState(selectedObject.stepType || 'actorAction');
  
  const [selectedActorIds, setSelectedActorIds] = useState<number[]>(selectedObject.actorIds || []);
  const [selectedInputBoIds, setSelectedInputBoIds] = useState<number[]>(selectedObject.inputBusinessObjectIds || []);
  const [selectedOutputBoIds, setSelectedOutputBoIds] = useState<number[]>(selectedObject.outputBusinessObjectIds || []);

  useEffect(() => {
    setStepName(selectedObject.stepName || '');
    setStepDesc(selectedObject.stepDescription || '');
    setStepType(selectedObject.stepType || 'actorAction');
    setSelectedActorIds(selectedObject.actorIds || []);
    setSelectedInputBoIds(selectedObject.inputBusinessObjectIds || []);
    setSelectedOutputBoIds(selectedObject.outputBusinessObjectIds || []);
  }, [selectedObject]);

  const handleSave = async () => {
    if (!stepName.trim()) {
      alert(t('rightPanel.stepNameEmptyAlert'));
      return;
    }
    if (stepType === 'actorAction' && selectedActorIds.length === 0) {
      alert(t('rightPanel.stepActorEmptyAlert'));
      return;
    }
    const flow = ir.flows?.find((f: any) => (f.flowSteps || []).some((s: any) => s.stepId === selectedObject.stepId));
    if (!flow) return;
    await updateFlowStep(flow.flowId, selectedObject.stepId, {
      stepName,
      stepDescription: stepDesc,
      stepType: stepType as any,
      actorIds: selectedActorIds,
      inputBusinessObjectIds: selectedInputBoIds,
      outputBusinessObjectIds: selectedOutputBoIds
    });
  };

  const handleReset = () => {
    setStepName(selectedObject.stepName || '');
    setStepDesc(selectedObject.stepDescription || '');
    setStepType(selectedObject.stepType || 'actorAction');
    setSelectedActorIds(selectedObject.actorIds || []);
    setSelectedInputBoIds(selectedObject.inputBusinessObjectIds || []);
    setSelectedOutputBoIds(selectedObject.outputBusinessObjectIds || []);
  };

  return (
    <PanelShell title={stepName} subtitle={t("rightPanel.stepSubtitle") + t("rightPanel.stepNodeSubtitle")}>
      <ConfirmationStatusSection nodeKind="flow_step" selectedObject={selectedObject} />
      <Section title={t("rightPanel.stepSubtitle") + t("rightPanel.stepBaseAttrs")}>
        <TextField label={t("rightPanel.stepName")} value={stepName} onChange={setStepName} />
        <SelectField 
          label={t("rightPanel.stepCollabType")}
          value={stepType} 
          options={[
            { value: 'actorAction', label: t('rightPanel.stepCollabUser') },
            { value: 'systemAction', label: t('rightPanel.stepCollabSystem') },
            { value: 'judgment', label: t('rightPanel.stepCollabJudgment') }
          ]} 
          onChange={setStepType} 
        />
        <TextField label={t("rightPanel.stepExecDesc")} value={stepDesc} onChange={setStepDesc} multiline />
      </Section>

      <Section title={t("rightPanel.stepActorsSection")}>
        <div className="space-y-2 max-h-[150px] overflow-y-auto border border-slate-100 rounded-xl p-3 bg-slate-50/50 select-none">
          {(ir.actors || []).length === 0 ? (
            <div className="text-xs text-slate-400 italic">{t("rightPanel.stepNoActorsAvailable")}</div>
          ) : (
            (ir.actors || []).map((actor: any) => (
              <label key={actor.actorId} className="flex items-center space-x-2 text-xs font-semibold text-slate-700 cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={selectedActorIds.includes(actor.actorId)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedActorIds([...selectedActorIds, actor.actorId]);
                    } else {
                      setSelectedActorIds(selectedActorIds.filter(id => id !== actor.actorId));
                    }
                  }}
                  className="w-3.5 h-3.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span>{actor.actorName}</span>
              </label>
            ))
          )}
        </div>
        {stepType === 'actorAction' && selectedActorIds.length === 0 && (
          <div className="text-[10px] text-amber-600 font-bold mt-1.5 flex items-center gap-1">
            {t("rightPanel.stepActorWarning")}
          </div>
        )}
      </Section>

      <Section title={t("rightPanel.stepInputBoSection")}>
        <div className="space-y-2 max-h-[150px] overflow-y-auto border border-slate-100 rounded-xl p-3 bg-slate-50/50 select-none">
          {(ir.businessObjects || []).length === 0 ? (
            <div className="text-xs text-slate-400 italic">{t('rightPanel.stepNoBoAvailable')}</div>
          ) : (
            (ir.businessObjects || []).map((bo: any) => (
              <label key={bo.businessObjectId} className="flex items-center space-x-2 text-xs font-semibold text-slate-700 cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={selectedInputBoIds.includes(bo.businessObjectId)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedInputBoIds([...selectedInputBoIds, bo.businessObjectId]);
                    } else {
                      setSelectedInputBoIds(selectedInputBoIds.filter(id => id !== bo.businessObjectId));
                    }
                  }}
                  className="w-3.5 h-3.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span>{bo.businessObjectName}</span>
              </label>
            ))
          )}
        </div>
      </Section>

      <Section title={t("rightPanel.stepOutputBoSection")}>
        <div className="space-y-2 max-h-[150px] overflow-y-auto border border-slate-100 rounded-xl p-3 bg-slate-50/50 select-none">
          {(ir.businessObjects || []).length === 0 ? (
            <div className="text-xs text-slate-400 italic">{t('rightPanel.stepNoBoAvailable')}</div>
          ) : (
            (ir.businessObjects || []).map((bo: any) => (
              <label key={bo.businessObjectId} className="flex items-center space-x-2 text-xs font-semibold text-slate-700 cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={selectedOutputBoIds.includes(bo.businessObjectId)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedOutputBoIds([...selectedOutputBoIds, bo.businessObjectId]);
                    } else {
                      setSelectedOutputBoIds(selectedOutputBoIds.filter(id => id !== bo.businessObjectId));
                    }
                  }}
                  className="w-3.5 h-3.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span>{bo.businessObjectName}</span>
              </label>
            ))
          )}
        </div>
      </Section>

      <div className="px-5 pb-5">
        <ActionRow>
          <ActionButton onClick={() => void handleSave()}>{t("rightPanel.saveBtn")}</ActionButton>
          <ActionButton variant="secondary" onClick={handleReset}>
            {t('rightPanel.resetBtn')}
          </ActionButton>
        </ActionRow>
      </div>
    </PanelShell>
  );
}

// 5. Dedicated Flow Panel
function FlowObjectPanel({ selectedObject }: { selectedObject: any }) {
  const { t } = useTranslation();
  const updateFlow = useWorkspaceStore((state) => state.updateFlow);
  const [flowName, setFlowName] = useState(selectedObject.flowName || '');
  const [flowDesc, setFlowDesc] = useState(selectedObject.flowDescription || '');

  useEffect(() => {
    setFlowName(selectedObject.flowName || '');
    setFlowDesc(selectedObject.flowDescription || '');
  }, [selectedObject]);

  const handleSave = async () => {
    await updateFlow(selectedObject.flowId, {
      flowName,
      flowDescription: flowDesc
    });
  };

  return (
    <PanelShell title={flowName} subtitle={t("rightPanel.flowSubtitle")}>
      <ConfirmationStatusSection nodeKind="flow" selectedObject={selectedObject} />
      <Section title={t("rightPanel.flowSubtitle") + t("rightPanel.stepBaseAttrs")}>
        <TextField label={t("rightPanel.flowName")} value={flowName} onChange={setFlowName} />
        <TextField label={t("rightPanel.flowScenarioDesc")} value={flowDesc} onChange={setFlowDesc} multiline />
        <ActionRow>
          <ActionButton onClick={() => void handleSave()}>{t("rightPanel.saveBtn")}</ActionButton>
          <ActionButton variant="secondary" onClick={() => { setFlowName(selectedObject.flowName || ''); setFlowDesc(selectedObject.flowDescription || ''); }}>
            {t('rightPanel.resetBtn')}
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}

// 6. Dedicated Scenario Panel
function ScenarioObjectPanel({ selectedObject }: { selectedObject: any }) {
  const { t } = useTranslation();
  const updateScenario = useWorkspaceStore((state) => state.updateScenario);
  const setSelectedObject = useWorkspaceStore((state) => state.setSelectedObject);
  const [scenName, setScenName] = useState(selectedObject.scenarioName || '');
  const [scenContent, setScenContent] = useState(selectedObject.scenarioContent || '');

  useEffect(() => {
    setScenName(selectedObject.scenarioName || '');
    setScenContent(selectedObject.scenarioContent || '');
  }, [selectedObject]);

  const handleSave = async () => {
    await updateScenario(selectedObject.featureId, selectedObject.scenarioId, {
      scenarioName: scenName,
      scenarioContent: scenContent
    });
  };

  return (
    <PanelShell title={scenName} subtitle={t("rightPanel.scenarioSubtitle")}>
      <Section title={t("rightPanel.scenBaseAttrs")}>
        <TextField label={t("rightPanel.scenarioName")} value={scenName} onChange={setScenName} />
        <TextField label={t('rightPanel.scenUserStoryDesc')} value={scenContent} onChange={setScenContent} multiline />
        <ActionRow>
          <ActionButton onClick={() => void handleSave()}>{t("rightPanel.saveBtn")}</ActionButton>
          <ActionButton variant="secondary" onClick={() => { setScenName(selectedObject.scenarioName || ''); setScenContent(selectedObject.scenarioContent || ''); }}>
            {t('rightPanel.resetBtn')}
          </ActionButton>
        </ActionRow>
      </Section>

      <ConfirmationStatusSection nodeKind="scenario" selectedObject={selectedObject} />
      <Section title={t("rightPanel.scenSystemDelivery")}>
        {(selectedObject.acceptanceCriteria || []).length === 0 ? (
          <div className="text-xs text-slate-400 italic">{t("rightPanel.scenNoAcAssociated")}</div>
        ) : (
          <div className="space-y-4">
            {(selectedObject.acceptanceCriteria || []).map((ac: any) => (
              <GherkinVisualRenderer
                key={ac.criterionId}
                text={ac.criterionContent || ''}
                title={`${t('rightPanel.acSubtitle')} #${ac.criterionId}`}
                badge={t("rightPanel.acSubtitle")}
                statusBadge={<StatusBadge status={ac.confirmationStatus} />}
                onClick={() => setSelectedObject({ ...ac, kind: 'acceptance_criterion' })}
              />
            ))}
          </div>
        )}
      </Section>
    </PanelShell>
  );
}

// 7. Dedicated Acceptance Criterion Panel
function ACObjectPanel({ selectedObject, ir }: { selectedObject: any; ir: any }) {
  const { t } = useTranslation();
  const updateAcceptanceCriterion = useWorkspaceStore((state) => state.updateAcceptanceCriterion);
  const setSelectedObject = useWorkspaceStore((state) => state.setSelectedObject);
  const [acContent, setAcContent] = useState(selectedObject.criterionContent || '');
  const [activeTab, setActiveTab] = useState<'visual' | 'raw'>('visual');

  useEffect(() => {
    setAcContent(selectedObject.criterionContent || '');
  }, [selectedObject]);

  const parent = useMemo(() => {
    for (const f of ir.features || []) {
      for (const s of f.scenarios || []) {
        if ((s.acceptanceCriteria || []).some((ac: any) => ac.criterionId === selectedObject.criterionId)) {
          return { featureId: f.featureId, scenarioId: s.scenarioId, scenario: s };
        }
      }
    }
    return null;
  }, [ir, selectedObject.criterionId]);

  const handleSave = async () => {
    if (!parent) return;
    await updateAcceptanceCriterion(parent.featureId, parent.scenarioId, selectedObject.criterionId, acContent);
  };

  return (
    <PanelShell title={`${t('rightPanel.acSubtitle')} #${selectedObject.criterionId}`} subtitle={t("rightPanel.acSubtitle")}>
      <ConfirmationStatusSection nodeKind="acceptance_criterion" selectedObject={selectedObject} />
      
      <div className="px-5 py-3.5 border-b border-slate-100 select-none">
        <div className="bg-slate-100/80 p-1 rounded-xl flex gap-1 border border-slate-200/50 shadow-inner">
          <button
            type="button"
            onClick={() => setActiveTab('visual')}
            className={`grow text-[10px] font-extrabold uppercase py-1.5 px-3 rounded-lg transition-all flex items-center justify-center gap-1 ${
              activeTab === 'visual'
                ? 'bg-white text-indigo-600 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {t('rightPanel.acVisualDesigner')}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('raw')}
            className={`grow text-[10px] font-extrabold uppercase py-1.5 px-3 rounded-lg transition-all flex items-center justify-center gap-1 ${
              activeTab === 'raw'
                ? 'bg-white text-indigo-600 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {t('rightPanel.acRawText')}
          </button>
        </div>
      </div>

      <Section title={t("rightPanel.acDetailDescSection")}>
        {activeTab === 'visual' ? (
          <div className="border border-slate-200/80 rounded-2xl p-4 bg-slate-50/10 mb-4 shadow-sm">
            <GherkinVisualEditor
              initialText={acContent}
              onChange={setAcContent}
            />
          </div>
        ) : (
          <TextField 
            label={t("rightPanel.acContentLabel")}
            value={acContent} 
            onChange={setAcContent} 
            multiline 
          />
        )}
        
        {parent ? (
          <ActionRow>
            <ActionButton onClick={() => void handleSave()}>{t("rightPanel.saveBtn")}</ActionButton>
            <ActionButton variant="secondary" onClick={() => {
              setAcContent(selectedObject.criterionContent || '');
              // To reset the visual editor as well, we trigger selectedObject reload
              setSelectedObject({ ...selectedObject });
            }}>
              {t('rightPanel.resetBtn')}
            </ActionButton>
          </ActionRow>
        ) : (
          <div className="text-xs text-rose-500 italic mt-2 font-medium">{t("rightPanel.acNoBindingWarning")}</div>
        )}
      </Section>
    </PanelShell>
  );
}

export function RightObjectPanel() {
  const { t } = useTranslation();
  const ir = useWorkspaceStore((state) => state.ir);
  const selectedObject: any = useWorkspaceStore(selectSelectedObject);

  const [width, setWidth] = useState(() => {
    const saved = localStorage.getItem('right-panel-width');
    return saved ? parseInt(saved, 10) : 360;
  });
  const [collapsed, setCollapsed] = useState(true);

  const [isResizing, setIsResizing] = useState(false);

  const handleWidthChange = (newWidth: number) => {
    const clamped = Math.max(300, Math.min(600, newWidth));
    setWidth(clamped);
    localStorage.setItem('right-panel-width', clamped.toString());
  };

  const handleCollapsedChange = (newCollapsed: boolean) => {
    setCollapsed(newCollapsed);
  };

  useEffect(() => {
    const handleSelectedObject = () => {
      handleCollapsedChange(false);
    };
    window.addEventListener('workspace:selected-object', handleSelectedObject);
    return () => window.removeEventListener('workspace:selected-object', handleSelectedObject);
  }, []);

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = window.innerWidth - e.clientX;
      handleWidthChange(newWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  if (!ir) return null;

  const renderContent = () => {
    if (!selectedObject) {
      return (
        <PanelShell title={t('rightPanel.editTitle')} subtitle={t('rightPanel.editPanelSubtitle')}>
          <div className="text-sm text-slate-500 leading-relaxed font-medium">
            {t('rightPanel.editDesc')}
          </div>
        </PanelShell>
      );
    }

    // Intercept active refactored RequirementSpace node kinds
    const kind = selectedObject.kind || (
      selectedObject.scenarioId !== undefined ? 'scenario' :
      selectedObject.criterionId !== undefined ? 'acceptance_criterion' :
      selectedObject.actorId !== undefined ? 'actor' :
      selectedObject.featureId !== undefined ? 'feature' :
      selectedObject.businessObjectId !== undefined ? 'business_object' :
      selectedObject.businessObjectAttributeId !== undefined ? 'business_object_attribute' :
      selectedObject.stepId !== undefined ? 'flow_step' :
      selectedObject.flowId !== undefined ? 'flow' : undefined
    );

    if (kind === 'project') {
      return <ProjectObjectPanel selectedObject={selectedObject} />;
    }
    if (kind === 'actor') {
      return <ActorObjectPanel selectedObject={selectedObject} />;
    }
    if (kind === 'feature') {
      return <FeatureObjectPanel selectedObject={selectedObject} />;
    }
    if (kind === 'scope') {
      return <ScopeObjectPanel selectedObject={selectedObject} />;
    }
    if (kind === 'scenario') {
      return <ScenarioObjectPanel selectedObject={selectedObject} />;
    }
    if (kind === 'acceptance_criterion') {
      return <ACObjectPanel selectedObject={selectedObject} ir={ir} />;
    }
    if (kind === 'business_object') {
      return <BusinessObjectPanel selectedObject={selectedObject} />;
    }
    if (kind === 'business_object_attribute') {
      return <BusinessObjectAttributePanel selectedObject={selectedObject} />;
    }
    if (kind === 'flow_step') {
      return <FlowStepObjectPanel selectedObject={selectedObject} ir={ir} />;
    }
    if (kind === 'flow') {
      return <FlowObjectPanel selectedObject={selectedObject} />;
    }
    if (kind === 'finding' || selectedObject.findingId) {
      return <IssuePanel issue={selectedObject as Finding} ir={ir} />;
    }

    // Fallback for legacy indexing kinds
    const objId = selectedObject.id || selectedObject.perceptionSlotId?.toString();

    if (objId) {
      if (ir.nodes && ir.nodes[objId]) {
        return <NodePanel node={ir.nodes[objId]} ir={ir} />;
      }
      if (ir.issues && ir.issues[objId]) {
        return <IssuePanel issue={ir.issues[objId] as Finding} ir={ir} />;
      }
      if (ir.slots && ir.slots[objId]) {
        return <SlotPanel slot={ir.slots[objId] as RequirementSlot} ir={ir} />;
      }
      if (ir.choiceGroups && ir.choiceGroups[objId]) {
        return <ChoiceGroupPanel choiceGroup={ir.choiceGroups[objId] as ChoiceGroup} ir={ir} />;
      }

      const choice = findChoiceById(ir, objId);
      if (choice) {
        return <ChoicePanel choice={choice} ir={ir} />;
      }
    }

    return (
      <PanelShell title={selectedObject.title || selectedObject.name || selectedObject.id || t('rightPanel.unknownObject')} subtitle={t("rightPanel.objectAttrDetail")}>
        <pre className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 overflow-auto">
          {JSON.stringify(selectedObject, null, 2)}
        </pre>
      </PanelShell>
    );
  };

  return (
    <div
      className={`relative shrink-0 transition-all duration-300 flex bg-white ${
        collapsed ? '' : 'border-l border-slate-200'
      }`}
      style={{
        width: collapsed ? '0px' : `${width}px`,
      }}
    >
      {/* Resizing Handle */}
      {!collapsed && (
        <div
          onMouseDown={(e) => {
            e.preventDefault();
            setIsResizing(true);
          }}
          className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-indigo-500/20 active:bg-indigo-500 transition-colors z-30"
          style={{ transform: 'translateX(-50%)' }}
        />
      )}

      {/* Collapse/Expand Toggle Button aligned with LeftNav collapse button */}
      <button
        onClick={() => handleCollapsedChange(!collapsed)}
        className="absolute -translate-y-1/2 bg-white border border-slate-200 rounded-full w-6 h-6 flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-300 shadow-sm hover:shadow z-40 transition-all"
        style={{ 
          top: 'calc(50vh - 2rem)',
          left: collapsed ? '-36px' : '-12px'
        }}
        title={collapsed ? t('rightPanel.expandTitle') : t('rightPanel.collapseTitle')}
      >
        {collapsed ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
      </button>

      {/* Actual Panel Content */}
      <div className="w-full h-full overflow-hidden bg-white">
        <PanelErrorBoundary key={selectedObject?.id || selectedObject?.scenarioId || selectedObject?.criterionId || 'empty'}>
          {renderContent()}
        </PanelErrorBoundary>
      </div>
    </div>
  );
}
