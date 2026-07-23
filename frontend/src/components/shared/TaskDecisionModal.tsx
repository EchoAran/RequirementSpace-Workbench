import { useTranslation } from 'react-i18next';
import i18n from 'i18next';
import React, { useState } from 'react';
import { X, CheckCircle2, AlertTriangle, MessageSquare, ShieldAlert } from 'lucide-react';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { getScopeStatusText } from '@/core/presentationLabels';
import { getCollaborationTaskDescription, getCollaborationTaskTitle } from '@/core/collaborationPresentation';

interface TaskDecisionModalProps {
  task: any;
  projectId: string;
  onClose: () => void;
  onDecided: () => void;
}

const fieldLabels: Record<string, string> = {
  get name() { return i18n.t('taskDecision.fieldLabels.name') || 'Name'; },
  get description() { return i18n.t('taskDecision.fieldLabels.description') || 'Description'; },
  get content() { return i18n.t('taskDecision.fieldLabels.content') || 'Content'; },
  get data_type() { return i18n.t('taskDecision.fieldLabels.data_type') || 'Data Type'; },
  get example() { return i18n.t('taskDecision.fieldLabels.example') || 'Example'; },
  get position() { return i18n.t('taskDecision.fieldLabels.position') || 'Position'; },
  get step_type() { return i18n.t('taskDecision.fieldLabels.step_type') || 'Step Type'; },
  get status() { return i18n.t('taskDecision.fieldLabels.status') || 'Status'; },
  get positive_summary() { return i18n.t('taskDecision.fieldLabels.positive_summary') || 'In Scope'; },
  get negative_summary() { return i18n.t('taskDecision.fieldLabels.negative_summary') || 'Out of Scope'; },
  get reason() { return i18n.t('taskDecision.fieldLabels.reason') || 'Reason'; },
  get kano_category() { return i18n.t('taskDecision.fieldLabels.kano_category') || 'Kano Category'; },
} as unknown as Record<string, string>;

const nodeKindLabels: Record<string, string> = {
  get actor() { return i18n.t('taskDecision.nodeKindLabels.actor') || 'Actor'; },
  get feature() { return i18n.t('taskDecision.nodeKindLabels.feature') || 'Feature'; },
  get scenario() { return i18n.t('taskDecision.nodeKindLabels.scenario') || 'Scenario'; },
  get acceptance_criterion() { return i18n.t('taskDecision.nodeKindLabels.acceptance_criterion') || 'Acceptance Criterion'; },
  get business_object() { return i18n.t('taskDecision.nodeKindLabels.business_object') || 'Business Object'; },
  get business_object_attribute() { return i18n.t('taskDecision.nodeKindLabels.business_object_attribute') || 'Attribute'; },
  get flow() { return i18n.t('taskDecision.nodeKindLabels.flow') || 'Business Flow'; },
  get flow_step() { return i18n.t('taskDecision.nodeKindLabels.flow_step') || 'Flow Step'; },
  get scope() { return i18n.t('taskDecision.nodeKindLabels.scope') || 'Scope Plan'; },
} as unknown as Record<string, string>;

const formatValue = (val: unknown) => {
  if (Array.isArray(val) && val.length === 0) return i18n.t('taskDecision.none') || 'None';
  if (val && typeof val === 'object') return JSON.stringify(val, null, 2);
  if (val === null || val === undefined || val === '') return i18n.t('taskDecision.unfilled') || 'Unfilled';
  return String(val);
};

const DetailLine = ({ label, value }: { label: string; value: unknown }) => (
  <div className="space-y-1">
    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">{label}</div>
    <div className="text-xs text-slate-700 leading-relaxed whitespace-pre-wrap break-words">{formatValue(value)}</div>
  </div>
);

type ResolveName = (kind: string, id: unknown) => string | undefined;

const formatRef = (kind: string, id: unknown, resolveName: ResolveName) => {
  if (id === null || id === undefined || id === '') return formatValue(id);
  return resolveName(kind, id) || `#${String(id)}`;
};

const RefList = ({ label, kind, values, resolveName }: { label: string; kind: string; values: unknown; resolveName: ResolveName }) => {
  if (!Array.isArray(values) || values.length === 0) return null;
  return (
    <div className="space-y-1">
      <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">{label}</div>
      <div className="flex flex-wrap gap-1.5">
        {values.map((value) => (
          <span key={String(value)} className="px-2 py-0.5 rounded-full bg-slate-100 text-[11px] font-semibold text-slate-600">
            {formatRef(kind, value, resolveName)}
          </span>
        ))}
      </div>
    </div>
  );
};

const FieldTable = ({ snapshot }: { snapshot: Record<string, unknown> }) => {
  const entries = Object.entries(snapshot);
  return (
    <table className="w-full border-collapse">
      <tbody>
        {entries.map(([key, val]) => (
          <tr key={key} className="border-b border-slate-100 last:border-b-0">
            <td className="px-3.5 py-2 text-[11px] font-semibold text-slate-500 bg-slate-50/50 w-1/3 border-r border-slate-100">
              {fieldLabels[key] || key}
            </td>
            <td className="px-3.5 py-2 text-slate-700 break-all leading-normal whitespace-pre-wrap">
              {formatValue(val)}
            </td>
          </tr>
        ))}
        {entries.length === 0 && (
          <tr>
            <td className="px-4 py-3 text-slate-400 text-center italic">
              {i18n.t('taskDecision.noFieldsToShow') || 'No fields to display'}
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
};

const SnapshotPreview = ({ nodeKind, snapshot, resolveName }: { nodeKind?: string; snapshot: Record<string, unknown>; resolveName: ResolveName }) => {
  if (nodeKind === 'actor') {
    return <div className="p-4 space-y-3"><DetailLine label={i18n.t('taskDecision.actorName') || 'Actor Name'} value={snapshot.name} /><DetailLine label={i18n.t('taskDecision.actorDuties') || 'Actor Description'} value={snapshot.description} /></div>;
  }
  if (nodeKind === 'feature') {
    return (
      <div className="p-4 space-y-3">
        <DetailLine label={i18n.t('taskDecision.featureName') || 'Feature Name'} value={snapshot.name} />
        <DetailLine label={i18n.t('taskDecision.featureDesc') || 'Feature Description'} value={snapshot.description} />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <DetailLine label={i18n.t('taskDecision.parentFeature') || 'Parent Feature'} value={formatRef('feature', snapshot.parent_id, resolveName)} />
          <RefList label={i18n.t('taskDecision.relatedActors') || 'Related Actors'} kind="actor" values={snapshot.actor_ids} resolveName={resolveName} />
        </div>
      </div>
    );
  }
  if (nodeKind === 'scenario') {
    return (
      <div className="p-4 space-y-3">
        <DetailLine label={i18n.t('taskDecision.scenarioName') || 'Scenario Name'} value={snapshot.name} />
        <DetailLine label={i18n.t('taskDecision.scenarioContent') || 'Scenario Content'} value={snapshot.content} />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <DetailLine label={i18n.t('taskDecision.belongingFeature') || 'Belonging Feature'} value={formatRef('feature', snapshot.feature_id, resolveName)} />
          <DetailLine label={i18n.t('taskDecision.execActors') || 'Actors'} value={formatRef('actor', snapshot.actor_id, resolveName)} />
        </div>
      </div>
    );
  }
  if (nodeKind === 'acceptance_criterion') {
    return <div className="p-4 space-y-3"><DetailLine label={i18n.t('taskDecision.acTitle') || 'Acceptance Criterion'} value={snapshot.content} /><DetailLine label={i18n.t('taskDecision.belongingScenario') || 'Belonging Scenario'} value={formatRef('scenario', snapshot.scenario_id, resolveName)} /></div>;
  }
  if (nodeKind === 'business_object') {
    const attrs = Array.isArray(snapshot.attributes) ? snapshot.attributes : [];
    return (
      <div className="p-4 space-y-3">
        <DetailLine label={i18n.t('taskDecision.businessObject') || 'Business Object'} value={snapshot.name} />
        <DetailLine label={i18n.t('taskDecision.businessObjectDesc') || 'Description'} value={snapshot.description} />
        {attrs.length > 0 && (
          <div className="space-y-2">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">{i18n.t('taskDecision.fieldsLabel') || 'Fields'}</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {attrs.map((attr: any, idx: number) => (
                <div key={`${attr.name || 'attr'}-${idx}`} className="rounded-lg border border-slate-150 bg-white p-2.5">
                  <div className="text-xs font-bold text-slate-700">{formatValue(attr.name)}</div>
                  <div className="text-[11px] text-slate-500 mt-1">{formatValue(attr.data_type)}</div>
                  {attr.description && <div className="text-[11px] text-slate-600 mt-1 leading-relaxed">{attr.description}</div>}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }
  if (nodeKind === 'business_object_attribute') {
    return <div className="p-4 space-y-3"><DetailLine label={i18n.t('taskDecision.fieldName') || 'Field Name'} value={snapshot.name} /><DetailLine label={i18n.t('taskDecision.fieldDesc') || 'Field Description'} value={snapshot.description} /><DetailLine label={i18n.t('taskDecision.dataType') || 'Data Type'} value={snapshot.data_type} /><DetailLine label={i18n.t('taskDecision.exampleLabel') || 'Example'} value={snapshot.example} /></div>;
  }
  if (nodeKind === 'flow') {
    const steps = Array.isArray(snapshot.steps) ? snapshot.steps : [];
    return (
      <div className="p-4 space-y-3">
        <DetailLine label={i18n.t('taskDecision.flowName') || 'Flow Name'} value={snapshot.name} />
        <DetailLine label={i18n.t('taskDecision.flowDesc') || 'Flow Description'} value={snapshot.description} />
        {steps.length > 0 && (
          <ol className="space-y-2">
            {steps.map((step: any, idx: number) => (
              <li key={`${step.position ?? idx}-${step.name || idx}`} className="rounded-lg border border-slate-150 bg-white p-2.5">
                <div className="text-[11px] font-bold text-indigo-600">{i18n.t('taskDecision.stepNum', { num: formatValue(step.position ?? idx + 1) })}</div>
                <div className="text-xs font-bold text-slate-700 mt-1">{formatValue(step.name)}</div>
                <div className="text-[11px] text-slate-600 mt-1 leading-relaxed">{formatValue(step.description)}</div>
              </li>
            ))}
          </ol>
        )}
      </div>
    );
  }
  if (nodeKind === 'flow_step') {
    return (
      <div className="p-4 space-y-3">
        <DetailLine label={i18n.t('taskDecision.stepName') || 'Step Name'} value={snapshot.name} />
        <DetailLine label={i18n.t('taskDecision.stepDesc') || 'Step Description'} value={snapshot.description} />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <DetailLine label={i18n.t('taskDecision.stepPos') || 'Step Position'} value={snapshot.position} />
          <DetailLine label={i18n.t('taskDecision.stepType') || 'Step Type'} value={snapshot.step_type} />
          <RefList label={i18n.t('taskDecision.execActors') || 'Actors'} kind="actor" values={snapshot.actor_ids} resolveName={resolveName} />
          <RefList label={i18n.t('taskDecision.inputObjects') || 'Input Objects'} kind="business_object" values={snapshot.input_business_object_ids} resolveName={resolveName} />
          <RefList label={i18n.t('taskDecision.outputObjects') || 'Output Objects'} kind="business_object" values={snapshot.output_business_object_ids} resolveName={resolveName} />
        </div>
      </div>
    );
  }
  if (nodeKind === 'scope') {
    return (
      <div className="p-4 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="px-2 py-0.5 rounded-full bg-indigo-50 text-[11px] font-bold text-indigo-700">{getScopeStatusText(snapshot.status) || formatValue(snapshot.status)}</span>
          {snapshot.kano_category && <span className="px-2 py-0.5 rounded-full bg-slate-100 text-[11px] font-semibold text-slate-600">Kano: {formatValue(snapshot.kano_category)}</span>}
        </div>
        <DetailLine label={i18n.t('taskDecision.positiveReason') || 'In Scope Rationale'} value={snapshot.positive_summary} />
        <DetailLine label={i18n.t('taskDecision.negativeImpact') || 'Out of Scope Impact'} value={snapshot.negative_summary} />
        <DetailLine label={i18n.t('taskDecision.decisionReason') || 'Decision Reason'} value={snapshot.reason} />
      </div>
    );
  }
  return <FieldTable snapshot={snapshot} />;
};

const inferNodeKind = (snapshot: Record<string, unknown>) => {
  if ('positive_summary' in snapshot || 'negative_summary' in snapshot || 'kano_category' in snapshot) return 'scope';
  if ('steps' in snapshot) return 'flow';
  if ('parent_id' in snapshot) return 'feature';
  if ('actor_ids' in snapshot || 'input_business_object_ids' in snapshot || 'output_business_object_ids' in snapshot) return 'flow_step';
  if ('attributes' in snapshot) return 'business_object';
  if ('data_type' in snapshot || 'example' in snapshot) return 'business_object_attribute';
  if ('content' in snapshot && 'scenario_id' in snapshot) return 'acceptance_criterion';
  if ('content' in snapshot) return 'scenario';
  if ('name' in snapshot && 'description' in snapshot) return 'actor';
  return undefined;
};

const toNumber = (value: unknown) => {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
};

const makeNameResolver = (ir: any): ResolveName => {
  return (kind, id) => {
    const numId = toNumber(id);
    if (!ir || numId === null) return undefined;

    if (kind === 'actor') {
      return (ir.actors || []).find((actor: any) => actor.actorId === numId)?.actorName;
    }

    if (kind === 'feature') {
      return (ir.features || []).find((feature: any) => feature.featureId === numId)?.featureName;
    }

    if (kind === 'scenario') {
      for (const feature of ir.features || []) {
        const scenario = (feature.scenarios || []).find((item: any) => item.scenarioId === numId);
        if (scenario) return scenario.scenarioName;
      }
    }

    if (kind === 'acceptance_criterion') {
      for (const feature of ir.features || []) {
        for (const scenario of feature.scenarios || []) {
          const criterion = (scenario.acceptanceCriteria || []).find((item: any) => item.criterionId === numId);
          if (criterion) return criterion.criterionContent;
        }
      }
    }

    if (kind === 'business_object') {
      return (ir.businessObjects || []).find((item: any) => item.businessObjectId === numId)?.businessObjectName;
    }

    if (kind === 'business_object_attribute') {
      for (const object of ir.businessObjects || []) {
        const attrs = object.attributes || object.businessObjectAttributes || [];
        const attr = attrs.find((item: any) => item.attributeId === numId || item.businessObjectAttributeId === numId);
        if (attr) return attr.attributeName || attr.businessObjectAttributeName;
      }
    }

    if (kind === 'flow') {
      return (ir.flows || []).find((item: any) => item.flowId === numId)?.flowName;
    }

    if (kind === 'flow_step') {
      for (const flow of ir.flows || []) {
        const steps = flow.steps || flow.flowSteps || [];
        const step = steps.find((item: any) => item.stepId === numId);
        if (step) return step.stepName;
      }
    }

    if (kind === 'scope') {
      const feature = (ir.features || []).find((item: any) => {
        const scope = item.scope;
        return scope && (scope.scopeId === numId || scope.id === numId || scope.scope_id === numId);
      });
      return feature ? `${feature.featureName} - ${i18n.t('taskDecision.scopeSuffix')}` : undefined;
    }

    return undefined;
  };
};

const getSnapshotTitle = (task: any, target?: any, index?: number) => {
  const snapshot = target?.snapshot || task.contentSnapshot || {};
  const snapshotName = snapshot.name || snapshot.content;
  if (target) {
    const kindLabel = nodeKindLabels[target.node_kind] || target.node_kind || (i18n.t('taskDecision.objectFallback') || 'Object');
    return target.node_name || snapshotName || `${kindLabel} #${target.node_id ?? (index ?? 0) + 1}`;
  }
  return task.nodeName || snapshotName || getCollaborationTaskTitle(task, i18n.t) || (i18n.t('taskDecision.confirmTargetFallback') || 'Confirm Target');
};

const getSnapshotGroups = (task: any) => {
  if (Array.isArray(task.targets) && task.targets.length > 0) {
    return task.targets.map((target: any, index: number) => ({
      title: getSnapshotTitle(task, target, index),
      nodeKind: target.node_kind || inferNodeKind(target.snapshot || {}),
      snapshot: target.snapshot || {},
    }));
  }

  const snapshot = task.contentSnapshot || {};
  return [{
    title: getSnapshotTitle(task),
    nodeKind: task.targetType || task.target_type || inferNodeKind(snapshot),
    snapshot,
  }];
};

export function TaskDecisionModal({ task, projectId, onClose, onDecided }: TaskDecisionModalProps) {
  const { t } = useTranslation();
  const decideTask = useWorkspaceStore((state) => state.decideTask);
  const ir = useWorkspaceStore((state) => state.ir);
  const [decisionNote, setDecisionNote] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const snapshotGroups = getSnapshotGroups(task);
  const resolveName = makeNameResolver(ir);

  const handleDecision = async (decision: 'approve' | 'reject') => {
    try {
      setLoading(true);
      setError(null);
      await decideTask(projectId, task.id, {
        decision,
        decisionNote: decisionNote.trim() || undefined,
      });
      onDecided();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (detail === 'task_content_changed') {
        setError(t('taskDecision.errorContentChanged'));
      } else if (detail && typeof detail === 'object' && detail.message === 'task_content_changed') {
        const mismatches = detail.mismatches || [];
        const mismatchStr = mismatches.map((m: any) => `${m.node_kind} (ID: ${m.node_id})`).join(', ');
        setError(t('taskDecision.errorContentChangedDetail', { mismatches: mismatchStr }));
      } else {
        setError(detail || err?.message || t('taskDecision.errorFallback'));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden border border-slate-200">
        <div className="px-6 py-4 border-b border-slate-150 flex items-center justify-between bg-slate-50/50">
          <div>
            <span className="text-[10px] font-bold tracking-wider uppercase bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full">
              {t('taskDecision.approvalHeader')}
            </span>
            <h3 className="text-base font-bold text-slate-800 mt-1">{getCollaborationTaskTitle(task, t)}</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1 hover:bg-slate-100 rounded-lg transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {error && (
            <div className="bg-rose-50 border border-rose-100 text-rose-700 px-4 py-3 rounded-xl text-xs flex items-start gap-2">
              <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {task.contentChanged && (
            <div className="bg-amber-50 border border-amber-100 text-amber-800 px-4 py-3 rounded-xl text-xs flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <strong className="block font-semibold mb-0.5">{t('taskDecision.contentChangedWarningTitle')}</strong>
                <span>{t('taskDecision.contentChangedWarningDesc')}</span>
              </div>
            </div>
          )}

          {getCollaborationTaskDescription(task, t) && (
            <div className="bg-slate-50 rounded-xl p-3 border border-slate-200/60">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">{t('taskDecision.assignNote')}</div>
              <div className="text-xs text-slate-600 mt-1 leading-relaxed whitespace-pre-wrap">{getCollaborationTaskDescription(task, t)}</div>
            </div>
          )}

          <div className="space-y-2.5">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">{t('taskDecision.snapshotRecordTitle')}</div>
            <div className="space-y-3">
              {snapshotGroups.map((group, index) => {
                return (
                  <div key={`${group.title}-${index}`} className="border border-slate-150 rounded-xl overflow-hidden bg-slate-50/30 text-xs">
                    {snapshotGroups.length > 1 && (
                      <div className="px-3.5 py-2 bg-slate-50 border-b border-slate-100 font-semibold text-slate-700">
                        {group.title}
                      </div>
                    )}
                    <SnapshotPreview nodeKind={group.nodeKind} snapshot={group.snapshot} resolveName={resolveName} />
                  </div>
                );
              })}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wide flex items-center gap-1">
              <MessageSquare className="w-3.5 h-3.5 text-slate-400" />
              <span>{t('taskDecision.decisionNoteLabel')}</span>
            </label>
            <textarea
              value={decisionNote}
              onChange={(e) => setDecisionNote(e.target.value)}
              placeholder={t('taskDecision.decisionNotePlaceholder')}
              className="w-full text-xs text-slate-700 border border-slate-200 rounded-xl px-3.5 py-2.5 min-h-[70px] focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>
        </div>

        <div className="px-6 py-4 border-t border-slate-150 bg-slate-50/30 flex items-center justify-between gap-3 shrink-0">
          <div className="text-[10px] text-slate-400">
            {t('taskDecision.handlerLabel')} <span className="font-semibold text-slate-500">{task.assigneeEmail}</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => handleDecision('reject')}
              disabled={loading}
              className="px-4 py-2 rounded-xl text-xs font-semibold border border-rose-200 text-rose-600 bg-white hover:bg-rose-50/50 transition-colors cursor-pointer disabled:opacity-50"
            >
              {t('taskDecision.rejectBtn')}
            </button>
            <button
              onClick={() => handleDecision('approve')}
              disabled={loading}
              className="px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>{t('taskDecision.approveBtn')}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
