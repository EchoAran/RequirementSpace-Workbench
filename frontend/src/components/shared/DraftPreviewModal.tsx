import { useTranslation } from 'react-i18next';
import i18n from 'i18next';
import { useState } from 'react';
import { Check, RefreshCw, Sparkles, X } from 'lucide-react';
import { GherkinVisualRenderer } from './GherkinVisualizer';
import { ExpandableFeatureTree, DetailedActorList } from './ChoicePreviewRenderer';
import { getScopeStatusText } from '@/core/presentationLabels';

type DraftType = 'project' | 'actor' | 'feature' | 'flow' | 'scenario' | 'ac' | 'scope' | 'repair' | null;

interface DraftPreviewModalProps {
  draft: any | null;
  draftType: DraftType;
  isWorking: boolean;
  onConfirm: () => void | Promise<void>;
  onDiscard: () => void | Promise<void>;
  onRegenerate?: (feedback?: string) => void | Promise<void>;
  confirmLabel?: string;
}

const titles: Record<Exclude<DraftType, null>, string> = {
  get project() { return i18n.t('draftPreview.titles.project') || 'Project Creation Draft'; },
  get actor() { return i18n.t('draftPreview.titles.actor') || 'Actors Draft'; },
  get feature() { return i18n.t('draftPreview.titles.feature') || 'Feature capability tree Draft'; },
  get flow() { return i18n.t('draftPreview.titles.flow') || 'Flow & Business Objects Draft'; },
  get scenario() { return i18n.t('draftPreview.titles.scenario') || 'Scenarios Draft'; },
  get ac() { return i18n.t('draftPreview.titles.ac') || 'AC Draft'; },
  get scope() { return i18n.t('draftPreview.titles.scope') || 'Scope Draft'; },
  get repair() { return i18n.t('draftPreview.titles.repair') || 'AI Repair Draft'; },
} as unknown as Record<Exclude<DraftType, null>, string>;

function asArray(value: any): any[] {
  return Array.isArray(value) ? value : [];
}

function getDraftItems(draft: any, draftType: DraftType) {
  if (!draft) return [];
  if (draftType === 'actor') return asArray(draft.actors);
  if (draftType === 'feature') return asArray(draft.features);
  if (draftType === 'flow') return [...asArray(draft.flows), ...asArray(draft.business_objects)];
  if (draftType === 'scenario') return asArray(draft.scenarios);
  if (draftType === 'ac') return asArray(draft.acceptance_criteria || draft.criteria || draft.scenario_acceptance_criteria);
  if (draftType === 'scope') return asArray(draft.scopes);
  if (draftType === 'project') return [draft.project_preview || draft].filter(Boolean);
  // P5: repair draft — title + rationale (truncated) + structured patch summary + risk level
  if (draftType === 'repair') {
    const items: any[] = [];
    if (draft.title) items.push({ _kind: 'title', _label: i18n.t('draftPreview.repairItems.title'), name: draft.title });
    if (draft.rationale) {
      const text = draft.rationale.length > 200 ? draft.rationale.slice(0, 200) + '…' : draft.rationale;
      items.push({ _kind: 'rationale', _label: i18n.t('draftPreview.repairItems.rationale'), name: text });
    }
    const report = draft.validation_report || draft.proposal || {};
    const preview = report.impact_preview || {};
    if (preview.affected_nodes?.length > 0) {
      preview.affected_nodes.forEach((n: any) => {
        items.push({ _kind: 'node', _label: n.change || i18n.t('draftPreview.repairItems.change'), name: n.name || `${n.kind} (id=${n.id})` });
      });
    }
    if (preview.affected_relations?.length > 0) {
      preview.affected_relations.forEach((r: any) => {
  items.push({ _kind: 'relation', _label: r.change || i18n.t('draftPreview.repairItems.relationChange'), name: `${r.source || '?'} to ${r.target || '?'}` });
      });
    }
    if (preview.risk_level) {
  const riskLabel = preview.risk_level === 'high' ? i18n.t('draftPreview.riskLevels.high') : preview.risk_level === 'medium' ? i18n.t('draftPreview.riskLevels.medium') : i18n.t('draftPreview.riskLevels.low');
      items.push({ _kind: 'risk', _label: i18n.t('draftPreview.repairItems.riskLevel'), name: riskLabel });
    }
    if (preview.summary && items.length === 0) {
      items.push({ _kind: 'summary', _label: i18n.t('draftPreview.repairItems.impactSummary'), name: preview.summary });
    }
    return items;
  }
  return [];
}

function itemTitle(item: any, index: number) {
  return (
    item.name ||
    item.title ||
    item.actor_name ||
    item.feature_name ||
    item.flow_name ||
    item.business_object_name ||
    item.scenario_name ||
    item.criterion_name ||
    item.featureName ||
    item.actorName ||
    item.project_name ||
    i18n.t('draftPreview.draftItemFallback', { index: index + 1 })
  );
}

function itemDescription(item: any) {
  return (
    item.description ||
    item.reason ||
    item.actor_description ||
    item.feature_description ||
    item.flow_description ||
    item.business_object_description ||
    item.scenario_content ||
    item.criterion_content ||
    item.content ||
    item.project_description ||
    ''
  );
}

function ProjectDraftPreview({ draft }: { draft: any }) {
  const { t } = useTranslation();
  const project = draft.project_preview || draft;
  const actors = asArray(draft.actors);
  const features = asArray(draft.features);

  return (
    <div className="space-y-6">
      <section>
        <h4 className="text-xs font-black uppercase tracking-wide text-slate-500">{t('draftPreview.projectOverview')}</h4>
        <div className="mt-2 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h5 className="text-sm font-extrabold text-slate-900">{project.project_name}</h5>
          {project.project_description && (
            <p className="mt-2 text-xs leading-relaxed text-slate-650 font-medium">{project.project_description}</p>
          )}
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between gap-3 mb-2">
          <h4 className="text-xs font-black uppercase tracking-wide text-slate-500">{t('draftPreview.stakeholdersTitle')}</h4>
          <span className="text-xs font-bold text-slate-400">{t('draftPreview.stakeholdersCount', { count: actors.length })}</span>
        </div>
        <DetailedActorList actors={actors} />
      </section>

      <section>
        <div className="flex items-center justify-between gap-3 mb-2">
          <h4 className="text-xs font-black uppercase tracking-wide text-slate-500">{t('draftPreview.featuresTitle')}</h4>
          <span className="text-xs font-bold text-slate-400">{t('draftPreview.featuresCount', { count: features.length })}</span>
        </div>
        <ExpandableFeatureTree features={features} />
      </section>
    </div>
  );
}

function DetailChips({ items, tone = 'slate' }: { items: string[]; tone?: 'slate' | 'indigo' | 'emerald' | 'amber' }) {
  if (!items?.length) return null;

  const toneClass = {
    slate: 'border-slate-200 bg-slate-50 text-slate-600',
    indigo: 'border-indigo-100 bg-indigo-50 text-indigo-700',
    emerald: 'border-emerald-100 bg-emerald-50 text-emerald-700',
    amber: 'border-amber-100 bg-amber-50 text-amber-700',
  }[tone];

  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span key={item} className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${toneClass}`}>
          {item}
        </span>
      ))}
    </div>
  );
}

function pickField(item: any, snakeKey: string, camelKey: string) {
  return item?.[snakeKey] ?? item?.[camelKey];
}

function pickArray(item: any, snakeKey: string, camelKey: string) {
  return asArray(pickField(item, snakeKey, camelKey));
}

function FlowDraftPreview({ draft }: { draft: any }) {
  const { t } = useTranslation();
  const flows = asArray(draft.flows);
  const businessObjects = asArray(draft.business_objects || draft.businessObjects);
  const normalizedFlows = flows.map((flow: any) => ({
    ...flow,
    flow_name: pickField(flow, 'flow_name', 'flowName'),
    flow_description: pickField(flow, 'flow_description', 'flowDescription'),
    feature_names: pickArray(flow, 'feature_names', 'featureNames'),
    flow_steps: pickArray(flow, 'flow_steps', 'flowSteps').map((step: any) => ({
      ...step,
      step_number: pickField(step, 'step_number', 'stepNumber'),
      step_name: pickField(step, 'step_name', 'stepName'),
      step_description: pickField(step, 'step_description', 'stepDescription'),
      step_type: pickField(step, 'step_type', 'stepType'),
      actor_names: pickArray(step, 'actor_names', 'actorNames'),
      input_business_object_names: pickArray(step, 'input_business_object_names', 'inputBusinessObjectNames'),
      output_business_object_names: pickArray(step, 'output_business_object_names', 'outputBusinessObjectNames'),
      next_step_names: pickArray(step, 'next_step_names', 'nextStepNames'),
    })),
  }));
  const normalizedBusinessObjects = businessObjects.map((businessObject: any) => ({
    ...businessObject,
    business_object_id: pickField(businessObject, 'business_object_id', 'businessObjectId'),
    business_object_name: pickField(businessObject, 'business_object_name', 'businessObjectName'),
    business_object_description: pickField(businessObject, 'business_object_description', 'businessObjectDescription'),
    is_existing: pickField(businessObject, 'is_existing', 'isExisting'),
    business_object_attributes: pickArray(businessObject, 'business_object_attributes', 'businessObjectAttributes').map((attribute: any) => ({
      ...attribute,
      business_object_attribute_name: pickField(attribute, 'business_object_attribute_name', 'businessObjectAttributeName'),
      business_object_attribute_description: pickField(attribute, 'business_object_attribute_description', 'businessObjectAttributeDescription'),
      business_object_attribute_type: pickField(attribute, 'business_object_attribute_type', 'businessObjectAttributeType'),
    })),
  }));

  return (
    <div className="space-y-5">
      <section>
        <div className="flex items-center justify-between gap-3">
          <h4 className="text-xs font-black uppercase tracking-wide text-slate-500">{t('draftPreview.flowsTitle')}</h4>
          <span className="text-[11px] font-bold text-slate-400">{t('draftPreview.flowsCount', { count: normalizedFlows.length })}</span>
        </div>
        <div className="mt-2 space-y-3">
          {normalizedFlows.map((flow: any, flowIndex: number) => (
            <div key={flow.flow_name || flowIndex} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h5 className="text-sm font-extrabold text-slate-900">{flow.flow_name || t('draftPreview.draftItemFallback', { index: flowIndex + 1 })}</h5>
                  {flow.flow_description && (
                    <p className="mt-2 text-xs leading-relaxed text-slate-600">{flow.flow_description}</p>
                  )}
                </div>
                {flow.feature_names?.length > 0 && <DetailChips items={flow.feature_names} tone="indigo" />}
              </div>

              {asArray(flow.flow_steps).length > 0 && (
                <div className="mt-4 space-y-2">
                  {asArray(flow.flow_steps).map((step: any, stepIndex: number) => (
                    <div key={step.step_number || step.step_name || stepIndex} className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-md bg-white px-1.5 py-0.5 text-[10px] font-black text-slate-500">
                          {step.step_number || t('draftPreview.flowStepNum', { num: String(stepIndex + 1).padStart(3, '0') })}
                        </span>
                        <span className="rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] font-bold text-slate-500">
                          {step.step_type || 'step'}
                        </span>
                        <h6 className="min-w-0 text-xs font-extrabold text-slate-900">{step.step_name}</h6>
                      </div>
                      {step.step_description && (
                        <p className="mt-2 text-xs leading-relaxed text-slate-600">{step.step_description}</p>
                      )}
                      <div className="mt-3 grid gap-2 text-[11px] sm:grid-cols-2">
                        {step.actor_names?.length > 0 && (
                          <div>
                            <div className="mb-1 font-black text-slate-400">{t('draftPreview.flowStepRole')}</div>
                            <DetailChips items={step.actor_names} tone="amber" />
                          </div>
                        )}
                        {step.input_business_object_names?.length > 0 && (
                          <div>
                            <div className="mb-1 font-black text-slate-400">{t('draftPreview.flowStepInput')}</div>
                            <DetailChips items={step.input_business_object_names} />
                          </div>
                        )}
                        {step.output_business_object_names?.length > 0 && (
                          <div>
                            <div className="mb-1 font-black text-slate-400">{t('draftPreview.flowStepOutput')}</div>
                            <DetailChips items={step.output_business_object_names} tone="emerald" />
                          </div>
                        )}
                        {step.next_step_names?.length > 0 && (
                          <div>
                            <div className="mb-1 font-black text-slate-400">{t('draftPreview.flowStepNext')}</div>
                            <DetailChips items={step.next_step_names} tone="indigo" />
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between gap-3">
          <h4 className="text-xs font-black uppercase tracking-wide text-slate-500">{t('draftPreview.businessObjectsTitle')}</h4>
          <span className="text-[11px] font-bold text-slate-400">{t('draftPreview.businessObjectsCount', { count: normalizedBusinessObjects.length })}</span>
        </div>
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {normalizedBusinessObjects.map((businessObject: any, index: number) => (
            <div key={businessObject.business_object_id || businessObject.business_object_name || index} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <h5 className="min-w-0 text-sm font-extrabold text-slate-900">{businessObject.business_object_name}</h5>
                {businessObject.is_existing && (
                  <span className="shrink-0 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-bold text-slate-500">
                    {t('draftPreview.businessObjectExisting')}
                  </span>
                )}
              </div>
              {businessObject.business_object_description && (
                <p className="mt-2 text-xs leading-relaxed text-slate-600">{businessObject.business_object_description}</p>
              )}
              {asArray(businessObject.business_object_attributes).length > 0 && (
                <div className="mt-3 space-y-1.5">
                  {asArray(businessObject.business_object_attributes).map((attribute: any, attributeIndex: number) => (
                    <div key={attribute.business_object_attribute_name || attributeIndex} className="rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-black text-slate-800">{attribute.business_object_attribute_name}</span>
                        <span className="rounded bg-white px-1.5 py-0.5 text-[10px] font-bold text-slate-500">
                          {attribute.business_object_attribute_type}
                        </span>
                      </div>
                      {attribute.business_object_attribute_description && (
                        <p className="mt-1 text-[11px] leading-relaxed text-slate-500">{attribute.business_object_attribute_description}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}export function DraftPreviewModal({
  draft,
  draftType,
  isWorking,
  onConfirm,
  onDiscard,
  onRegenerate,
  confirmLabel,
}: DraftPreviewModalProps) {
  const { t } = useTranslation();
  const [feedback, setFeedback] = useState('');

  if (!draftType) return null;
  const actualConfirmLabel = confirmLabel || t('draftPreview.confirmLabel');
  if (!draft) {
    if (isWorking) {
      return (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-slate-950/40 backdrop-blur-md transition-all duration-300">
          <div className="bg-white rounded-3xl shadow-2xl border border-slate-100 w-full max-w-md mx-4 p-8 scale-in duration-300 animate-in">
            <div className="text-center">
              <div className="relative w-16 h-16 mx-auto mb-6 flex items-center justify-center">
                <div className="absolute inset-0 rounded-full border-4 border-slate-100 border-t-indigo-600 animate-spin" />
              </div>
              <h3 className="text-base font-extrabold text-slate-800 mb-2 leading-relaxed">
                {t('draftPreview.generatingDraftTitle', { title: titles[draftType] })}
              </h3>
              <p className="text-[10px] text-slate-400 font-medium px-4 mb-6 leading-normal">
                {t('draftPreview.generatingDraftDesc')}
              </p>
            </div>
          </div>
        </div>
      );
    }
    return null;
  }

  const items = getDraftItems(draft, draftType);

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-slate-950/55 p-4 backdrop-blur-sm">
      <div className="flex max-h-[86vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 bg-slate-50 px-6 py-5">
          <div className="flex min-w-0 items-start gap-3">
            <span className="mt-0.5 rounded-xl bg-amber-100 p-2 text-amber-700">
              <Sparkles className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <h3 className="text-base font-extrabold text-slate-900">{titles[draftType]}</h3>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void onDiscard()}
            disabled={isWorking}
            className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-white hover:text-slate-700 disabled:opacity-50"
            title={t('draftPreview.closeDiscardTooltip')}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {draftType === 'project' ? (
            <ProjectDraftPreview draft={draft} />
          ) : draftType === 'actor' ? (
            <div className="space-y-3">
              <h4 className="text-xs font-black uppercase tracking-wide text-slate-500 mb-2">{t('draftPreview.stakeholdersTitle')}</h4>
              <DetailedActorList actors={items} />
            </div>
          ) : draftType === 'feature' ? (
            <div className="space-y-3">
              <h4 className="text-xs font-black uppercase tracking-wide text-slate-500 mb-2">{t('draftPreview.featuresTitle')}</h4>
              <ExpandableFeatureTree features={items} />
            </div>
          ) : draftType === 'flow' ? (
            <FlowDraftPreview draft={draft} />
          ) : draftType === 'ac' ? (
            <div className="space-y-4">
              {items.map((item, index) => {
                const text = item.criterion_content || item.content || '';
                return (
                  <GherkinVisualRenderer
                    key={item.id || item.criterion_id || index}
                    text={text}
                    title={itemTitle(item, index)}
                    badge={t('draftPreview.acBadge')}
                  />
                );
              })}
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm text-slate-500">
              {t('draftPreview.emptyDraft')}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {items.map((item, index) => (
                <div key={item.id || item.draft_id || index} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <h4 className="text-sm font-extrabold text-slate-900">{itemTitle(item, index)}</h4>
                    {(item.scope_status || item.scopeStatus) && (
                      <span className="shrink-0 rounded-full border border-indigo-100 bg-indigo-50 px-2 py-0.5 text-[10px] font-bold text-indigo-700">
                        {getScopeStatusText(item.scope_status || item.scopeStatus)}
                      </span>
                    )}
                  </div>
                  {itemDescription(item) && (
                    <p className="mt-2 line-clamp-4 text-xs leading-relaxed text-slate-600">{itemDescription(item)}</p>
                  )}

                  {(item.positive_summary || item.negative_summary) && (
                    <div className="mt-3 grid gap-2 text-xs leading-relaxed text-slate-600 sm:grid-cols-2">
                      {item.positive_summary && (
                        <div className="rounded-lg border border-emerald-100 bg-emerald-50/60 p-2">
                          <div className="mb-1 font-bold text-emerald-700">{t('draftPreview.positiveSummaryLabel')}</div>
                          {item.positive_summary}
                        </div>
                      )}
                      {item.negative_summary && (
                        <div className="rounded-lg border border-rose-100 bg-rose-50/60 p-2">
                          <div className="mb-1 font-bold text-rose-700">{t('draftPreview.negativeSummaryLabel')}</div>
                          {item.negative_summary}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Kano Distribution Charts */}
                  {(item.positive_picture_base64 || item.positivePictureBase64 || item.negative_picture_base64 || item.negativePictureBase64) && (
                    <div className="mt-3 pt-3 border-t border-slate-100 grid grid-cols-2 gap-3">
                      {(item.positive_picture_base64 || item.positivePictureBase64) && (
                        <div className="space-y-1">
                          <span className="text-[10px] text-indigo-600 font-bold block text-center">{t('draftPreview.positiveChartLabel')}</span>
                          <div className="border border-slate-200 rounded-lg overflow-hidden bg-white max-h-[100px] flex items-center justify-center p-1 shadow-sm">
                            <img
                              src={`data:image/png;base64,${item.positive_picture_base64 || item.positivePictureBase64}`}
                              alt={t('draftPreview.positiveChartLabel')}
                              className="max-h-full max-w-full object-contain"
                            />
                          </div>
                        </div>
                      )}
                      {(item.negative_picture_base64 || item.negativePictureBase64) && (
                        <div className="space-y-1">
                          <span className="text-[10px] text-slate-500 font-bold block text-center">{t('draftPreview.negativeChartLabel')}</span>
                          <div className="border border-slate-200 rounded-lg overflow-hidden bg-white max-h-[100px] flex items-center justify-center p-1 shadow-sm">
                            <img
                              src={`data:image/png;base64,${item.negative_picture_base64 || item.negativePictureBase64}`}
                              alt={t('draftPreview.negativeChartLabel')}
                              className="max-h-full max-w-full object-contain"
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="border-t border-slate-100 bg-slate-50 px-6 py-4">
          {onRegenerate && (
            <div className="mb-3 flex flex-col gap-2 sm:flex-row">
              <input
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                disabled={isWorking}
                placeholder={t('draftPreview.feedbackPlaceholder')}
                className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
              />
              <button
                type="button"
                onClick={async () => {
                  await onRegenerate(feedback || undefined);
                  setFeedback('');
                }}
                disabled={isWorking}
                className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-700 transition-colors hover:bg-slate-100 disabled:opacity-50"
              >
                <RefreshCw className={`h-3.5 w-3.5 text-indigo-500 ${isWorking ? 'animate-spin' : ''}`} />
                {t('draftPreview.regenerateBtn')}
              </button>
            </div>
          )}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => void onDiscard()}
              disabled={isWorking}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-600 transition-colors hover:bg-slate-100 disabled:opacity-50"
            >
              {t('draftPreview.discardDraftBtn')}
            </button>
            <button
              type="button"
              onClick={() => void onConfirm()}
              disabled={isWorking}
              className="inline-flex items-center gap-1.5 rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold text-white shadow-sm transition-colors hover:bg-slate-800 disabled:opacity-50"
            >
              <Check className="h-3.5 w-3.5" />
              {actualConfirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
