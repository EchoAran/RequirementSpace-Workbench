import { useTranslation } from 'react-i18next';
import i18n from 'i18next';
import React, { useEffect, useState } from 'react';
import {
  Check,
  RefreshCw,
  Sparkles,
  X,
  AlertTriangle,
  Loader2,
  Trash2,
} from 'lucide-react';
import { ChoicePreviewRenderer, ExpandableFeatureTree, DetailedActorList } from './ChoicePreviewRenderer';
import { getFriendlyErrorMessage, useWorkspaceStore } from '@/store/useWorkspaceStore';
import { resolveLocalizedMessage } from '@/core/localizedMessage';
import { getChoiceGenerationStrategyLabel } from '@/core/generationStrategyPresentation';
import { getChoicePresentation } from '@/core/choicePresentation';

function asArray(value: any): any[] {
  return Array.isArray(value) ? value : [];
}

function getChoiceStrategyLabel(choice: any, fallback: string): string {
  return getChoiceGenerationStrategyLabel(
    choice?.strategyId ?? choice?.strategy_id,
    choice?.strategyLabel ?? choice?.strategy_label,
    fallback,
    i18n,
  );
}

function getFailedChoiceTitle(choice: any, generationType: string | undefined, t: any): string {
  return getChoicePresentation(
    { ...choice, draftType: choice?.draftType ?? choice?.draft_type ?? generationType },
    t,
    i18n,
  ).title;
}

function getFailedChoiceError(choice: any, fallback: string, t: any): string {
  const rawError = choice?.error?.message || '';
  if (!rawError) return fallback;
  const message = getFriendlyErrorMessage(rawError);
  if (message !== rawError) return resolveLocalizedMessage(t, message);
  return i18n.language === 'en-US' && /[\u4e00-\u9fff]/.test(rawError) ? fallback : rawError;
}

function confirmRegeneration(draftType: string): boolean {
  const targets: Record<string, string> = {
    actor: i18n.t('choiceGroupPreview.targets.actor'),
    feature: i18n.t('choiceGroupPreview.targets.feature'),
    scenario: i18n.t('choiceGroupPreview.targets.scenario'),
    acceptance_criteria: i18n.t('choiceGroupPreview.targets.acceptance_criteria'),
    flow: i18n.t('choiceGroupPreview.targets.flow'),
    scope: i18n.t('choiceGroupPreview.targets.scope'),
  };
  const target = targets[draftType];
  return !target || window.confirm(i18n.t('choiceGroupPreview.confirmAdopt', { target }));
}

function CandidateComparisonView({
  choices,
  draftType,
  onAccept,
  isWorking,
}: {
  choices: any[];
  draftType: string;
  onAccept: (choiceId: string) => void | Promise<void>;
  isWorking: boolean;
}) {
  const [submittingId, setSubmittingId] = useState<string | null>(null);

  const handleAcceptClick = async (choiceId: string) => {
    if (!confirmRegeneration(draftType)) return;
    setSubmittingId(choiceId);
    try {
      await onAccept(choiceId);
    } finally {
      setSubmittingId(null);
    }
  };
  const hasActors = choices.some(c => asArray(c.payload?.actors || c.preview?.actors).length > 0);
  const hasFeatures = choices.some(c => asArray(c.payload?.features || c.preview?.features).length > 0);
  const hasFlows = choices.some(c => asArray(c.preview?.flows || c.payload?.flows).length > 0);
  const hasScenarios = choices.some(c => asArray(c.payload?.scenarios || c.preview?.scenarios).length > 0);
  const hasCriteria = choices.some(c => asArray(c.payload?.acceptance_criteria || c.preview?.criteria).length > 0);
  const hasScopes = choices.some(c => asArray(c.payload?.scopes || c.preview?.scopes).length > 0);

  // Safely cast to array helper
  function getActorsArray(choice: any): any[] {
    return asArray(choice?.payload?.actors || choice?.preview?.actors);
  }

  function getFeaturesArray(choice: any): any[] {
    return asArray(choice?.payload?.features || choice?.preview?.features);
  }

  function getFlowsArray(choice: any): any[] {
    return asArray(choice?.preview?.flows || choice?.payload?.flows);
  }

  function getScenariosArray(choice: any): any[] {
    return asArray(choice?.payload?.scenarios || choice?.preview?.scenarios);
  }

  function getCriteriaArray(choice: any): any[] {
    return asArray(choice?.payload?.acceptance_criteria || choice?.preview?.criteria);
  }

  function getScopesArray(choice: any): any[] {
    return asArray(choice?.payload?.scopes || choice?.preview?.scopes);
  }

  function getObjectStats(choice: any) {
    const actors = getActorsArray(choice).length;
    const features = getFeaturesArray(choice).length;
    const flows = getFlowsArray(choice).length;
    const scenarios = getScenariosArray(choice).length;
    const criteria = getCriteriaArray(choice).length;
    const scopes = getScopesArray(choice).length;
    const businessObjects = choice?.preview?.business_object_count
      || asArray(choice?.payload?.business_objects || choice?.payload?.businessObjects).length;

    if (draftType === 'actor') {
      return [i18n.t('choiceGroupPreview.stats.actors', { count: actors })];
    }
    if (draftType === 'feature') {
      return [i18n.t('choiceGroupPreview.stats.features', { count: features })];
    }
    if (draftType === 'flow') {
      return [
        i18n.t('choiceGroupPreview.stats.flows', { count: flows }),
        i18n.t('choiceGroupPreview.stats.businessObjects', { count: businessObjects })
      ];
    }
    if (draftType === 'scenario') {
      return [i18n.t('choiceGroupPreview.stats.scenarios', { count: scenarios })];
    }
    if (draftType === 'acceptance_criteria') {
      return [i18n.t('choiceGroupPreview.stats.criteria', { count: criteria })];
    }
    if (draftType === 'scope') {
      return [i18n.t('choiceGroupPreview.stats.scopes', { count: scopes })];
    }
    return [
      i18n.t('choiceGroupPreview.stats.actors', { count: actors }),
      i18n.t('choiceGroupPreview.stats.features', { count: features }),
      ...(flows > 0 ? [i18n.t('choiceGroupPreview.stats.flows', { count: flows })] : []),
      ...(businessObjects > 0 ? [i18n.t('choiceGroupPreview.stats.businessObjects', { count: businessObjects })] : []),
      ...(scenarios > 0 ? [i18n.t('choiceGroupPreview.stats.scenarios', { count: scenarios })] : []),
      ...(criteria > 0 ? [i18n.t('choiceGroupPreview.stats.criteria', { count: criteria })] : []),
    ];
  }

  // Diffing algorithms
  function getDiffActors(currentChoice: any, allChoices: any[]) {
    const currentActors = getActorsArray(currentChoice);
    const otherChoices = allChoices.filter(c => c.id !== currentChoice.id);

    return currentActors.map(act => {
      const actName = (act.actor_name || act.name || '').trim();
      const actDesc = (act.actor_description || act.description || '').trim();

      let isUnique = true;
      let hasDescriptionDiff = false;

      for (const other of otherChoices) {
        const otherActors = getActorsArray(other);
        const matched = otherActors.find(oa => (oa.actor_name || oa.name || '').trim() === actName);
        if (matched) {
          isUnique = false;
          const otherDesc = (matched.actor_description || matched.description || '').trim();
          if (otherDesc !== actDesc) {
            hasDescriptionDiff = true;
          }
        }
      }

      if (isUnique || hasDescriptionDiff) {
        return {
          ...act,
          _diffType: isUnique ? 'unique' : 'modified'
        };
      }
      return null;
    }).filter(Boolean);
  }

  function getDiffFeatures(currentChoice: any, allChoices: any[]) {
    const currentFeatures = getFeaturesArray(currentChoice);
    const otherChoices = allChoices.filter(c => c.id !== currentChoice.id);

    return currentFeatures.map(feat => {
      const featName = (feat.feature_name || feat.name || feat.featureName || feat.title || '').trim();
      const featNum = (feat.feature_number || feat.featureNumber || '').trim();
      const featDesc = (feat.feature_description || feat.description || feat.featureDescription || '').trim();
      const featActors = asArray(feat.actor_names || feat.actorNames).map(n => String(n).trim()).sort().join(',');

      let isUnique = true;
      let hasDiff = false;

      for (const other of otherChoices) {
        const otherFeatures = getFeaturesArray(other);
        const matched = otherFeatures.find(of => {
          const ofNum = (of.feature_number || of.featureNumber || '').trim();
          const ofName = (of.feature_name || of.name || of.featureName || of.title || '').trim();
          if (featNum && ofNum) return featNum === ofNum;
          return featName === ofName;
        });

        if (matched) {
          isUnique = false;
          const otherDesc = (matched.feature_description || matched.description || matched.featureDescription || '').trim();
          const otherActors = asArray(matched.actor_names || matched.actorNames).map(n => String(n).trim()).sort().join(',');
          if (otherDesc !== featDesc || otherActors !== featActors) {
            hasDiff = true;
          }
        }
      }

      if (isUnique || hasDiff) {
        return {
          ...feat,
          _diffType: isUnique ? 'unique' : 'modified'
        };
      }
      return null;
    }).filter(Boolean);
  }

  function getDiffFlows(currentChoice: any, allChoices: any[]) {
    const currentFlows = getFlowsArray(currentChoice);
    const otherChoices = allChoices.filter(c => c.id !== currentChoice.id);

    return currentFlows.map(flow => {
      const flowName = (flow.flow_name || '').trim();
      const stepCount = flow.step_count || 0;
      const stepsStr = JSON.stringify(flow.flow_steps || flow.flowSteps || flow.step_names || []);

      let isUnique = true;
      let hasDiff = false;

      for (const other of otherChoices) {
        const otherFlows = getFlowsArray(other);
        const matched = otherFlows.find(of => (of.flow_name || '').trim() === flowName);
        if (matched) {
          isUnique = false;
          const otherStepCount = matched.step_count || 0;
          const otherStepsStr = JSON.stringify(matched.flow_steps || matched.flowSteps || matched.step_names || []);
          if (stepCount !== otherStepCount || stepsStr !== otherStepsStr) {
            hasDiff = true;
          }
        }
      }

      if (isUnique || hasDiff) {
        return {
          ...flow,
          _diffType: isUnique ? 'unique' : 'modified'
        };
      }
      return null;
    }).filter(Boolean);
  }

  function getDiffScenarios(currentChoice: any, allChoices: any[]) {
    const currentScenarios = getScenariosArray(currentChoice);
    const otherChoices = allChoices.filter(c => c.id !== currentChoice.id);

    return currentScenarios.map(sc => {
      const scName = (sc.scenario_name || '').trim();
      const scContent = (sc.scenario_content || '').trim();

      let isUnique = true;
      let hasDiff = false;

      for (const other of otherChoices) {
        const otherScenarios = getScenariosArray(other);
        const matched = otherScenarios.find(osc => (osc.scenario_name || '').trim() === scName);
        if (matched) {
          isUnique = false;
          const otherContent = (matched.scenario_content || '').trim();
          if (scContent !== otherContent) {
            hasDiff = true;
          }
        }
      }

      if (isUnique || hasDiff) {
        return {
          ...sc,
          _diffType: isUnique ? 'unique' : 'modified'
        };
      }
      return null;
    }).filter(Boolean);
  }

  function getDiffCriteria(currentChoice: any, allChoices: any[]) {
    const currentCriteria = getCriteriaArray(currentChoice);
    const otherChoices = allChoices.filter(c => c.id !== currentChoice.id);

    return currentCriteria.map(ac => {
      const content = (ac.content || ac.criterion_content || '').trim();

      let isUnique = true;
      for (const other of otherChoices) {
        const otherCriteria = getCriteriaArray(other);
        const matched = otherCriteria.some(oc => (oc.content || oc.criterion_content || '').trim() === content);
        if (matched) {
          isUnique = false;
        }
      }

      if (isUnique) {
        return {
          ...ac,
          _diffType: 'unique'
        };
      }
      return null;
    }).filter(Boolean);
  }

  function getDiffScopes(currentChoice: any, allChoices: any[]) {
    const currentScopes = getScopesArray(currentChoice);
    const otherChoices = allChoices.filter(c => c.id !== currentChoice.id);

    return currentScopes.map(sc => {
      const featName = (sc.feature_name || '').trim();
      const scopeStatus = (sc.scope_status || '').trim();
      const reason = (sc.reason || '').trim();

      let isUnique = true;
      let hasStatusDiff = false;
      let hasReasonDiff = false;

      for (const other of otherChoices) {
        const otherScopes = getScopesArray(other);
        const matched = otherScopes.find(os => (os.feature_name || '').trim() === featName);
        if (matched) {
          isUnique = false;
          const otherStatus = (matched.scope_status || '').trim();
          const otherReason = (matched.reason || '').trim();
          if (otherStatus.toLowerCase() !== scopeStatus.toLowerCase()) {
            hasStatusDiff = true;
          }
          if (otherReason !== reason) {
            hasReasonDiff = true;
          }
        }
      }

      if (isUnique || hasStatusDiff || hasReasonDiff) {
        return {
          ...sc,
          _diffType: isUnique ? 'unique' : 'diff',
          _hasStatusDiff: hasStatusDiff,
          _hasReasonDiff: hasReasonDiff,
        };
      }
      return null;
    }).filter(Boolean);
  }

  return (
    <div className="overflow-x-auto border border-slate-200 rounded-2xl shadow-inner bg-slate-50/20 max-w-full">
      <table className="min-w-full divide-y divide-slate-200 text-left text-xs border-collapse bg-white">
        <thead className="bg-slate-50/80 sticky top-0 z-10 backdrop-blur-sm">
          <tr>
            <th className="px-4 py-3.5 font-extrabold text-slate-500 w-[140px] border-r border-slate-200 bg-slate-50/90 tracking-wider">{i18n.t('choiceGroupPreview.compDimension')}</th>
            {choices.map((c, i) => {
              const compTitle = getChoiceStrategyLabel(c, i18n.t('choiceGroupPreview.planLabel', { index: i + 1 }));
              return (
                <th key={c.id || i} className="px-5 py-3.5 font-extrabold text-slate-800 border-r border-slate-200 last:border-r-0 min-w-[240px]">
                  <div className="flex flex-col gap-2.5">
                    <div className="flex items-center gap-1.5">
                      <span className="inline-flex h-2 w-2 rounded-full bg-indigo-500 shrink-0 animate-pulse" />
                      <span className="text-sm font-extrabold text-slate-900 truncate max-w-[160px]" title={compTitle}>
                        {compTitle}
                      </span>
                    </div>
                    <button
                      type="button"
                      disabled={isWorking}
                      onClick={() => void handleAcceptClick(c.id)}
                      className={`inline-flex items-center justify-center gap-1 w-full py-1.5 text-white rounded-lg text-[10px] font-bold transition-all shadow-sm active:scale-[0.98] ${
                        isWorking
                          ? 'bg-slate-400 cursor-not-allowed'
                          : 'bg-indigo-600 hover:bg-indigo-750'
                      }`}
                    >
                      {isWorking && submittingId === String(c.id) ? (
                        <RefreshCw className="w-3 h-3 animate-spin" />
                      ) : (
                        <Check className="w-3.5 h-3.5" />
                      )}
                      {isWorking && submittingId === String(c.id) ? i18n.t('choiceGroupPreview.adoptingBtn') : i18n.t('choiceGroupPreview.adoptBtn')}
                    </button>
                  </div>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 text-xs">
          {/* Row 1: Object Stats */}
          <tr className="hover:bg-slate-50/40 transition-colors">
            <td className="px-4 py-3 font-extrabold text-slate-500 border-r border-slate-200 align-top bg-slate-50/50">{i18n.t('choiceGroupPreview.stats.title')}</td>
            {choices.map((c, i) => {
              const stats = getObjectStats(c);
              return (
                <td key={c.id || i} className="px-5 py-3 border-r border-slate-200 last:border-r-0 align-top">
                  <div className="flex flex-wrap gap-1.5">
                    {stats.map((item, idx) => (
                      <span key={idx} className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] font-bold text-slate-700">
                        {item}
                      </span>
                    ))}
                  </div>
                </td>
              );
            })}
          </tr>

          {/* Row 2: Actor Differences */}
          {hasActors && (
            <tr className="hover:bg-slate-50/40 transition-colors">
              <td className="px-4 py-3 font-extrabold text-slate-500 border-r border-slate-200 align-top bg-slate-50/50">{i18n.t('choiceGroupPreview.actorsDiffTitle')}</td>
              {choices.map((c, i) => {
                const diffActors: any[] = getDiffActors(c, choices);
                return (
                  <td key={c.id || i} className="px-5 py-3 border-r border-slate-200 last:border-r-0 align-top space-y-2 max-h-[300px] overflow-y-auto">
                    {diffActors.length > 0 ? (
                      diffActors.map((actor: any, actIdx: number) => (
                        <div key={actIdx} className="p-2.5 rounded-xl border border-indigo-100 bg-indigo-50/10 space-y-1 hover:border-indigo-250 transition-colors shadow-sm text-left">
                          <div className="flex flex-wrap items-center gap-1.5">
                            {actor._diffType === 'unique' ? (
                              <span className="text-[8px] bg-amber-50 border border-amber-100 text-amber-700 font-extrabold px-1 py-0.2 rounded-md leading-none select-none">{i18n.t('choiceGroupPreview.actorsDiffUnique')}</span>
                            ) : (
                              <span className="text-[8px] bg-sky-50 border border-sky-100 text-sky-700 font-extrabold px-1 py-0.2 rounded-md leading-none select-none">{i18n.t('choiceGroupPreview.actorsDiffModified')}</span>
                            )}
                            <span className="text-[11px] font-extrabold text-slate-800 leading-none">{actor.actor_name || actor.name}</span>
                          </div>
                          {(actor.actor_description || actor.description) && (
                            <p className="text-[10px] text-slate-500 leading-relaxed font-medium">
                              {actor.actor_description || actor.description}
                            </p>
                          )}
                        </div>
                      ))
                    ) : (
                      <div className="text-[10px] text-emerald-600 font-semibold flex items-center gap-1 select-none py-2">
      {i18n.t('choiceGroupPreview.actorsDiffIdentical')}
                      </div>
                    )}
                  </td>
                );
              })}
            </tr>
          )}

          {/* Row 3: Feature Differences */}
          {hasFeatures && (
            <tr className="hover:bg-slate-50/40 transition-colors">
              <td className="px-4 py-3 font-extrabold text-slate-500 border-r border-slate-200 align-top bg-slate-50/50">{i18n.t('choiceGroupPreview.featuresDiffTitle')}</td>
              {choices.map((c, i) => {
                const diffFeatures: any[] = getDiffFeatures(c, choices);
                return (
                  <td key={c.id || i} className="px-5 py-3 border-r border-slate-200 last:border-r-0 align-top space-y-2 max-h-[300px] overflow-y-auto">
                    {diffFeatures.length > 0 ? (
                      diffFeatures.map((feat: any, featIdx: number) => {
                        const featNum = feat.feature_number || feat.featureNumber || '';
                        const featName = feat.feature_name || feat.name || feat.featureName || feat.title || '';
                        const featDesc = feat.feature_description || feat.description || feat.featureDescription || '';
                        const featActors = asArray(feat.actor_names || feat.actorNames);
                        return (
                          <div key={featIdx} className="p-2.5 rounded-xl border border-emerald-100 bg-emerald-50/10 space-y-1 hover:border-emerald-250 transition-colors shadow-sm text-left">
                            <div className="flex flex-wrap items-center gap-1.5">
                              {feat._diffType === 'unique' ? (
                                <span className="text-[8px] bg-amber-50 border border-amber-100 text-amber-700 font-extrabold px-1 py-0.2 rounded-md leading-none select-none">{i18n.t('choiceGroupPreview.featuresDiffUnique')}</span>
                              ) : (
                                <span className="text-[8px] bg-sky-50 border border-sky-100 text-sky-700 font-extrabold px-1 py-0.2 rounded-md leading-none select-none">{i18n.t('choiceGroupPreview.featuresDiffModified')}</span>
                              )}
                              {featNum && (
                                <span className="rounded bg-slate-100 border border-slate-200/50 px-1 py-0.2 text-[8px] font-bold text-slate-500 font-mono tracking-tighter leading-none select-none">
                                  {featNum}
                                </span>
                              )}
                              <span className="text-[11px] font-extrabold text-slate-800 leading-none">{featName}</span>
                            </div>
                            {featDesc && (
                              <p className="text-[10px] text-slate-500 leading-relaxed font-medium">
                                {featDesc}
                              </p>
                            )}
                            {featActors.length > 0 && (
                              <div className="flex flex-wrap gap-1 mt-1">
                                {featActors.map((an: string, actorIdx: number) => (
                                  <span key={actorIdx} className="inline-flex rounded-full border border-indigo-150 bg-indigo-50/50 px-1.5 py-0.2 text-[8px] font-bold text-indigo-755 leading-none select-none">
                                    {an}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })
                    ) : (
                      <div className="text-[10px] text-emerald-600 font-semibold flex items-center gap-1 select-none py-2">
      {i18n.t('choiceGroupPreview.featuresDiffIdentical')}
                      </div>
                    )}
                  </td>
                );
              })}
            </tr>
          )}

          {/* Row 4: Flow Differences */}
          {hasFlows && (
            <tr className="hover:bg-slate-50/40 transition-colors">
              <td className="px-4 py-3 font-extrabold text-slate-500 border-r border-slate-200 align-top bg-slate-50/50">{i18n.t('choiceGroupPreview.flowsDiffTitle')}</td>
              {choices.map((c, i) => {
                const diffFlows: any[] = getDiffFlows(c, choices);
                return (
                  <td key={c.id || i} className="px-5 py-3 border-r border-slate-200 last:border-r-0 align-top space-y-2 max-h-[300px] overflow-y-auto">
                    {diffFlows.length > 0 ? (
                      diffFlows.map((flow: any, flowIdx: number) => (
                        <div key={flowIdx} className="p-2.5 rounded-xl border border-indigo-100 bg-indigo-50/10 space-y-1 hover:border-indigo-250 transition-colors shadow-sm text-left">
                          <div className="flex flex-wrap items-center gap-1.5">
                            {flow._diffType === 'unique' ? (
                              <span className="text-[8px] bg-amber-50 border border-amber-100 text-amber-700 font-extrabold px-1 py-0.2 rounded-md leading-none select-none">{i18n.t('choiceGroupPreview.flowsDiffUnique')}</span>
                            ) : (
                              <span className="text-[8px] bg-sky-50 border border-sky-100 text-sky-700 font-extrabold px-1 py-0.2 rounded-md leading-none select-none">{i18n.t('choiceGroupPreview.flowsDiffModified')}</span>
                            )}
                            <span className="text-[11px] font-extrabold text-slate-800 leading-none">{flow.flow_name}</span>
                          </div>
                          <p className="text-[10px] text-slate-400 font-extrabold uppercase mt-1 tracking-wider leading-none">
                            {flow.step_count || 0} Steps
                          </p>
                        </div>
                      ))
                    ) : (
                      <div className="text-[10px] text-emerald-600 font-semibold flex items-center gap-1 select-none py-2">
      {i18n.t('choiceGroupPreview.flowsDiffIdentical')}
                      </div>
                    )}
                  </td>
                );
              })}
            </tr>
          )}

          {/* Row 5: Scenario Differences */}
          {hasScenarios && (
            <tr className="hover:bg-slate-50/40 transition-colors">
              <td className="px-4 py-3 font-extrabold text-slate-500 border-r border-slate-200 align-top bg-slate-50/50">{i18n.t('choiceGroupPreview.scenariosDiffTitle')}</td>
              {choices.map((c, i) => {
                const diffScenarios: any[] = getDiffScenarios(c, choices);
                return (
                  <td key={c.id || i} className="px-5 py-3 border-r border-slate-200 last:border-r-0 align-top space-y-2 max-h-[300px] overflow-y-auto">
                    {diffScenarios.length > 0 ? (
                      diffScenarios.map((sc: any, scIdx: number) => (
                        <div key={scIdx} className="p-2.5 rounded-xl border border-amber-100 bg-amber-50/10 space-y-1 hover:border-amber-250 transition-colors shadow-sm text-left">
                          <div className="flex flex-wrap items-center gap-1.5">
                            {sc._diffType === 'unique' ? (
                              <span className="text-[8px] bg-amber-50 border border-amber-100 text-amber-700 font-extrabold px-1 py-0.2 rounded-md leading-none select-none">{i18n.t('choiceGroupPreview.scenariosDiffUnique')}</span>
                            ) : (
                              <span className="text-[8px] bg-sky-50 border border-sky-100 text-sky-700 font-extrabold px-1 py-0.2 rounded-md leading-none select-none">{i18n.t('choiceGroupPreview.scenariosDiffModified')}</span>
                            )}
                            <span className="text-[11px] font-extrabold text-slate-800 leading-none">{sc.scenario_name}</span>
                          </div>
                          {(sc.scenario_content || sc.description) && (
                            <p className="text-[10px] text-slate-500 leading-relaxed font-medium line-clamp-3">
                              {sc.scenario_content || sc.description}
                            </p>
                          )}
                        </div>
                      ))
                    ) : (
                      <div className="text-[10px] text-emerald-600 font-semibold flex items-center gap-1 select-none py-2">
      {i18n.t('choiceGroupPreview.scenariosDiffIdentical')}
                      </div>
                    )}
                  </td>
                );
              })}
            </tr>
          )}

          {/* Row 6: Acceptance Criteria Differences */}
          {hasCriteria && (
            <tr className="hover:bg-slate-50/40 transition-colors">
              <td className="px-4 py-3 font-extrabold text-slate-500 border-r border-slate-200 align-top bg-slate-50/50">{i18n.t('choiceGroupPreview.criteriaDiffTitle')}</td>
              {choices.map((c, i) => {
                const diffCriteria: any[] = getDiffCriteria(c, choices);
                return (
                  <td key={c.id || i} className="px-5 py-3 border-r border-slate-200 last:border-r-0 align-top space-y-2 max-h-[300px] overflow-y-auto">
                    {diffCriteria.length > 0 ? (
                      diffCriteria.map((ac: any, acIdx: number) => {
                        const text = ac.content || ac.criterion_content || '';
                        return (
                          <div key={acIdx} className="p-2.5 rounded-xl border border-indigo-100 bg-indigo-50/10 space-y-1 hover:border-indigo-250 transition-colors shadow-sm text-left">
                            <div className="flex items-center gap-1.5">
                              <span className="text-[8px] bg-indigo-50 border border-indigo-100 text-indigo-650 font-extrabold px-1.5 py-0.2 rounded-md leading-none select-none">{i18n.t('choiceGroupPreview.criteriaDiffModified')}</span>
                            </div>
                            <p className="text-[10px] text-slate-600 font-mono mt-1 whitespace-pre-wrap leading-relaxed">
                              {text}
                            </p>
                          </div>
                        );
                      })
                    ) : (
                      <div className="text-[10px] text-emerald-600 font-semibold flex items-center gap-1 select-none py-2">
      {i18n.t('choiceGroupPreview.criteriaDiffIdentical')}
                      </div>
                    )}
                  </td>
                );
              })}
            </tr>
          )}

          {/* Row 7: Scope Differences */}
          {hasScopes && (
            <tr className="hover:bg-slate-50/40 transition-colors">
              <td className="px-4 py-3 font-extrabold text-slate-500 border-r border-slate-200 align-top bg-slate-50/50">{i18n.t('choiceGroupPreview.scopesDiffTitle')}</td>
              {choices.map((c, i) => {
                const diffScopes: any[] = getDiffScopes(c, choices);
                return (
                  <td key={c.id || i} className="px-5 py-3 border-r border-slate-200 last:border-r-0 align-top space-y-2 max-h-[300px] overflow-y-auto">
                    {diffScopes.length > 0 ? (
                      diffScopes.map((sc: any, scIdx: number) => {
                        const rawStatus = String(sc.scope_status || '').toLowerCase();
                        const statusZh = rawStatus === 'current' || rawStatus === i18n.t('choiceGroupPreview.scopeStatus.current')
                          ? i18n.t('choiceGroupPreview.scopeStatus.current')
                          : rawStatus === 'postponed' || rawStatus === i18n.t('choiceGroupPreview.scopeStatus.postponed')
                          ? i18n.t('choiceGroupPreview.scopeStatus.postponed')
                          : i18n.t('choiceGroupPreview.scopeStatus.exclude');
                        return (
                          <div key={scIdx} className="p-2.5 rounded-xl border border-indigo-150 bg-indigo-50/10 space-y-1 hover:border-indigo-250 transition-colors shadow-sm text-left animate-in fade-in duration-200">
                            <div className="flex flex-wrap items-center gap-1.5">
                              {sc._diffType === 'unique' ? (
                                <span className="text-[8px] bg-amber-50 border border-amber-100 text-amber-700 font-extrabold px-1.5 py-0.2 rounded-md leading-none select-none">{i18n.t('choiceGroupPreview.scopesDiffUnique')}</span>
                              ) : (
                                <span className="text-[8px] bg-sky-50 border border-sky-100 text-sky-700 font-extrabold px-1.5 py-0.2 rounded-md leading-none select-none">{i18n.t('choiceGroupPreview.scopesDiffModified')}</span>
                              )}
                              <span className="text-[11px] font-extrabold text-slate-800 leading-none">{sc.feature_name}</span>
                              <span className={`text-[9px] font-extrabold px-1.5 py-0.2 rounded-md ${
                                statusZh === i18n.t('choiceGroupPreview.scopeStatus.current')
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-100'
                                  : statusZh === i18n.t('choiceGroupPreview.scopeStatus.postponed')
                                  ? 'bg-sky-50 text-sky-700 border border-sky-100'
                                  : 'bg-rose-50 text-rose-700 border border-rose-100'
                              }`}>{statusZh}</span>
                            </div>
                            {sc.reason && (
                              <p className="text-[10px] text-slate-500 leading-normal mt-1.5 font-medium">
                                {sc.reason}
                              </p>
                            )}
                          </div>
                        );
                      })
                    ) : (
                      <div className="text-[10px] text-emerald-600 font-semibold flex items-center gap-1 select-none py-2">
      {i18n.t('choiceGroupPreview.scopesDiffIdentical')}
                      </div>
                    )}
                  </td>
                );
              })}
            </tr>
          )}

        </tbody>
      </table>
    </div>
  );
}

interface ChoiceGroupPreviewModalProps {
  /** The choice group from any generation type (project_creation, actor, scenario, …) */
  group: any | null;
  isWorking: boolean;
  isGeneratingChoices: boolean;
  generationProgress: {
    totalCandidates: number;
    candidateLabels: string[];
    completedCandidates: number;
    candidateStatuses: Record<number, 'pending' | 'generating' | 'complete' | 'failed'>;
  } | null;
  initialChoiceId?: string | number | null;
  onAccept: (choiceId: string) => void | Promise<void>;
  onDiscard: () => void | Promise<void>;
  onDefer: () => void;
  onRegenerate?: (choiceId?: string) => void | Promise<void>;
}

const subtasksRecord: Record<string, string[]> = {
  project: ["vision", "benchmarking", "outline", "actors", "featureTree", "candidates", "tuning"],
  actor: ["context", "roles", "responsibilities", "roleDiff", "refiningRoles"],
  feature: ["domainModel", "partitioning", "leafNodes", "treeDiff", "coupling"],
  flow: ["skeleton", "mainFlow", "io", "complexity", "swimlanes"],
  scenario: ["events", "mocking", "branches", "usability", "goldenPath"],
  acceptance_criteria: ["boundary", "bdd", "coverage", "strictness", "gherkin"],
  scope: ["mvp", "kano", "cost", "mvpDiff", "kanoMatrix"]
};

const genericSubtasks = ["llm", "분기", "deepDigging", "validation", "formatting"];

export function ChoiceGroupPreviewModal({
  group,
  isWorking,
  isGeneratingChoices,
  generationProgress,
  initialChoiceId,
  onAccept,
  onDiscard,
  onDefer,
  onRegenerate,
}: ChoiceGroupPreviewModalProps) {
  const { t } = useTranslation();
  const [activeChoiceIndex, setActiveChoiceIndex] = useState(0);
  const [isCompareMode, setIsCompareMode] = useState(true);
  const [simulatedProgress, setSimulatedProgress] = useState(0);

  useEffect(() => {
    if (!isGeneratingChoices) {
      setSimulatedProgress(0);
      return;
    }

    const timer = setInterval(() => {
      setSimulatedProgress(prev => {
        if (prev < 45) {
          return Math.min(prev + Math.floor(Math.random() * 3) + 2, 45);
        } else if (prev < 85) {
          return Math.min(prev + Math.floor(Math.random() * 2) + 1, 85);
        } else if (prev < 98) {
          return Math.min(prev + 0.5, 98);
        }
        return prev;
      });
    }, 300);

    return () => clearInterval(timer);
  }, [isGeneratingChoices]);

  useEffect(() => {
    const successfulChoices = ((group?.choices || []) as any[]).filter(choice => choice.status === 'candidate');
    if (successfulChoices.length === 0) {
      setActiveChoiceIndex(0);
      return;
    }

    // Default to comparison view if multiple choices exist
    setIsCompareMode(successfulChoices.length > 1);

    if (initialChoiceId === undefined || initialChoiceId === null) {
      setActiveChoiceIndex(0);
      return;
    }

    const nextIndex = successfulChoices.findIndex(choice => String(choice.id) === String(initialChoiceId));
    setActiveChoiceIndex(nextIndex >= 0 ? nextIndex : 0);
    if (nextIndex >= 0) {
      setIsCompareMode(false);
    }
  }, [group, initialChoiceId]);

  /* ── Progress overlay during generation (show even without group) ── */
  const lastActionMessageToken = useWorkspaceStore(s => s.lastActionMessageToken);
  const messageInterpolation = useWorkspaceStore(s => s.lastActionMessageTokenInterpolation);
  const generatingChoiceGroupType = useWorkspaceStore(s => s.generatingChoiceGroupType);

  if (isGeneratingChoices) {
    const total = generationProgress?.totalCandidates || 2;
    const progressStatuses = generationProgress?.candidateStatuses || {};
    const hasRealCandidateProgress = Object.values(progressStatuses).some(
      status => status === 'generating' || status === 'complete' || status === 'failed'
    );
    const useSimulatedProgress = !generationProgress || (
      (generationProgress.completedCandidates || 0) === 0 && !hasRealCandidateProgress
    );

    let completed = generationProgress?.completedCandidates || 0;
    if (useSimulatedProgress) {
      completed = Math.min(
        Math.floor(simulatedProgress / (90 / total)),
        Math.max(0, total - 1)
      );
    }
    const progressPercent = useSimulatedProgress
      ? Math.round(simulatedProgress)
      : Math.round((completed / total) * 100);

    // Determine the display title for loading dynamically
    let loadingTitle = t('choiceGroupPreview.loadingSteps.generic');
    const type = group?.generationType || generatingChoiceGroupType;
    
    if (type === 'actor') {
      loadingTitle = t('choiceGroupPreview.loadingSteps.genericActor');
    } else if (type === 'scenario') {
      loadingTitle = t('choiceGroupPreview.loadingSteps.genericScenario');
    } else if (type === 'feature') {
      loadingTitle = t('choiceGroupPreview.loadingSteps.genericFeature');
    } else if (type === 'flow') {
      loadingTitle = t('choiceGroupPreview.loadingSteps.genericFlow');
    } else if (type === 'scope') {
      loadingTitle = t('choiceGroupPreview.loadingSteps.genericScope');
    } else if (type === 'acceptance_criteria') {
      loadingTitle = t('choiceGroupPreview.loadingSteps.genericAc');
    } else if (type === 'project') {
      loadingTitle = t('choiceGroupPreview.loadingSteps.genericDraft');
    } else {
      // If group is null and type is null, infer from lastActionMessageToken
      const msg = String(lastActionMessageToken || '').toLowerCase();
      if (msg.includes('actor')) {
        loadingTitle = t('choiceGroupPreview.loadingSteps.genericActor');
      } else if (msg.includes('scenario')) {
        loadingTitle = t('choiceGroupPreview.loadingSteps.genericScenario');
      } else if (msg.includes('feature')) {
        loadingTitle = t('choiceGroupPreview.loadingSteps.genericFeature');
      } else if (msg.includes('flow')) {
        loadingTitle = t('choiceGroupPreview.loadingSteps.genericFlow');
      } else if (msg.includes('scope') || msg.includes('kano')) {
        loadingTitle = t('choiceGroupPreview.loadingSteps.genericScope');
      } else if (msg.includes('acceptance') || msg.includes('.ac')) {
        loadingTitle = t('choiceGroupPreview.loadingSteps.genericAc');
      } else if (msg.includes('project')) {
        loadingTitle = t('choiceGroupPreview.loadingSteps.genericDraft');
      } else if (lastActionMessageToken) {
        loadingTitle = resolveLocalizedMessage(t, lastActionMessageToken, messageInterpolation);
      }
    }

    // Determine subtask list to show based on type
    const typeKey = (type || '') as string;
    const subtasks = subtasksRecord[typeKey] || genericSubtasks;
    const subtaskIndex = Math.min(
      Math.floor((progressPercent / 100) * subtasks.length),
      subtasks.length - 1
    );
    const activeSubtask = subtasks[subtaskIndex];

    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 backdrop-blur-md transition-all duration-300">
        <div className="bg-white rounded-3xl shadow-2xl border border-slate-100 w-full max-w-md mx-4 p-8 scale-in duration-300 animate-in">
          <div className="text-center">
            {/* Clean Halo Spinner */}
            <div className="relative w-16 h-16 mx-auto mb-6 flex items-center justify-center">
              <div className="absolute inset-0 rounded-full border-4 border-slate-100 border-t-indigo-600 animate-spin" />
            </div>

            {/* Dynamic Refined Loading Title */}
            <h3 className="text-base font-extrabold text-slate-800 mb-2 leading-relaxed">
              {loadingTitle}
            </h3>
            <p className="text-[10px] text-slate-400 font-medium px-4 mb-6 leading-normal">
              {t('choiceGroupPreview.panelSubTitle')}
            </p>

            {/* Dynamic Active Sub-task Ticker */}
            <div className="mb-6 bg-slate-50 border border-slate-100 rounded-2xl p-4 flex items-start gap-2.5 text-left">
              <div className="mt-1 flex h-1.5 w-1.5 rounded-full bg-indigo-500 shrink-0" />
              <div className="text-xs font-bold text-slate-600 leading-relaxed font-sans">
                {t('choiceGroupPreview.loadingSteps.' + activeSubtask)}
              </div>
            </div>

            {/* Sleek Progress Bar */}
            <div className="space-y-1.5 text-left bg-slate-50 border border-slate-100/50 rounded-2xl p-4">
              <div className="flex justify-between items-center text-[10px] font-bold text-slate-400 font-mono px-0.5">
                <span className="uppercase tracking-widest text-slate-400">{t('choiceGroupPreview.progressLabel')}</span>
                <span className="text-indigo-600 font-extrabold">{progressPercent}% ({completed}/{total})</span>
              </div>
              <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden shadow-inner">
                <div 
                  className="h-full bg-indigo-600 rounded-full transition-all duration-500 ease-out shadow-[0_0_8px_rgba(79,70,229,0.4)]" 
                  style={{ width: `${progressPercent || 8}%` }}
                />
              </div>
            </div>

            {/* Individual Candidate States Cards */}
            <div className="space-y-2 mt-6">
              {Array.from({ length: total }).map((_, i) => {
                let status = 'pending';
                if (!useSimulatedProgress && generationProgress) {
                  status = generationProgress.candidateStatuses?.[i] || 'generating';
                } else {
                  status = i < completed ? 'complete' : i === completed ? 'generating' : 'pending';
                }
                const label = generationProgress?.candidateLabels?.[i] || i18n.t('choiceGroupPreview.planLabel', { index: i + 1 });
                
                return (
                  <div 
                    key={i} 
                    className={`flex items-center justify-between p-3.5 rounded-2xl border transition-all duration-300 ${
                      status === 'complete'
                        ? 'bg-emerald-50/40 border-emerald-100 text-emerald-800'
                        : status === 'failed'
                          ? 'bg-rose-50/40 border-rose-100 text-rose-800'
                          : status === 'generating'
                            ? 'bg-indigo-50/40 border-indigo-150 text-indigo-850 shadow-sm font-bold'
                            : 'bg-slate-50/40 border-slate-100 text-slate-400'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`inline-block h-2 w-2 rounded-full shrink-0 ${
                        status === 'complete'
                          ? 'bg-emerald-500'
                          : status === 'failed'
                            ? 'bg-rose-500'
                            : status === 'generating'
                              ? 'bg-indigo-500 animate-pulse'
                              : 'bg-slate-300'
                      }`} />
                      <span className="text-xs font-bold font-sans tracking-tight">{label}</span>
                    </div>
                    <span className="text-[10px] font-bold uppercase tracking-wider font-mono">
                      {status === 'complete' && t('choiceGroupPreview.status.ready')}
                      {status === 'failed' && t('choiceGroupPreview.status.failed')}
                      {status === 'generating' && t('choiceGroupPreview.status.generating')}
                      {status === 'pending' && t('choiceGroupPreview.status.pending')}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!group) return null;

  const choices = (group.choices || []) as any[];
  const successfulChoices = choices.filter(c => c.status === 'candidate');
  const failedChoices = choices.filter(c => c.status === 'failed');

  const activeChoice = successfulChoices[activeChoiceIndex] || successfulChoices[0];
  const totalSuccessful = successfulChoices.length;
  const totalFailed = failedChoices.length;

  /* ── All-failed state ────────────────────────────────── */
  if (successfulChoices.length === 0) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
        <div className="bg-white rounded-3xl shadow-2xl border border-slate-200 w-full max-w-lg mx-4 p-8 text-center">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h3 className="text-lg font-bold text-slate-800 mb-2">{t('choiceGroupPreview.failTitle')}</h3>
          <p className="text-sm text-slate-500 mb-6">
            {i18n.language === 'en-US' && /[\u4e00-\u9fff]/.test(group.statusDetail?.error_summary || '')
              ? t('choiceGroupPreview.failDesc')
              : group.statusDetail?.error_summary || t('choiceGroupPreview.failDesc')}
          </p>
          {failedChoices.length > 0 && (
            <div className="text-left space-y-2 mb-6">
              {failedChoices.map((fc: any) => (
                <div key={fc.id} className="p-3 rounded-xl bg-rose-50 border border-rose-100 text-xs text-rose-600">
                  <strong>{getFailedChoiceTitle(fc, group.generationType, t)}</strong>:{' '}
                  {getFailedChoiceError(fc, t('choiceGroupPreview.unknownError'), t)}
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-3 justify-center">
            {onRegenerate && (
              <button onClick={() => onRegenerate()} className="inline-flex items-center gap-2 h-11 px-6 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700 transition-colors">
                <RefreshCw className="w-4 h-4" />
                {t('choiceGroupPreview.retryBtn')}
              </button>
            )}
            <button onClick={onDiscard} className="inline-flex items-center gap-2 h-11 px-6 rounded-xl border border-slate-200 text-slate-700 text-sm font-bold hover:bg-slate-50 transition-colors">
              <X className="w-4 h-4" />
              {t('choiceGroupPreview.closeDialog')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const hasPartialFailure = totalFailed > 0;
  const draftType = activeChoice?.draftType || group.generationType || '';
  const showCompareOption = totalSuccessful > 1;
  const compareActive = isCompareMode && showCompareOption;
  const handleAcceptClick = (choiceId: string) => {
    if (confirmRegeneration(draftType)) {
      void onAccept(choiceId);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm select-text">
      <div className={`bg-white rounded-3xl shadow-2xl border border-slate-200 w-full mx-4 max-h-[90vh] flex flex-col transition-all duration-300 max-w-5xl`}>
        {/* Header */}
        <div className="p-6 border-b border-slate-100 shrink-0 bg-slate-50/50 rounded-t-3xl">
          <div className="flex items-center justify-between mb-1">
            <h3 className="text-lg font-bold text-slate-800">
              {draftType === 'actor' ? t('choiceGroupPreview.draftTypes.actor') :
               draftType === 'scenario' ? t('choiceGroupPreview.draftTypes.scenario') :
               draftType === 'feature' ? t('choiceGroupPreview.draftTypes.feature') :
               draftType === 'flow' ? t('choiceGroupPreview.draftTypes.flow') :
               draftType === 'scope' ? t('choiceGroupPreview.draftTypes.scope') :
               draftType === 'acceptance_criteria' ? t('choiceGroupPreview.draftTypes.acceptance_criteria') :
               t('choiceGroupPreview.draftTypes.generic')}
            </h3>
            <button onClick={onDefer} className="text-slate-400 hover:text-slate-600 transition-colors" title={t('choiceGroupPreview.deferTitle')}>
              <X className="w-5 h-5" />
            </button>
          </div>
          {hasPartialFailure && (
            <div className="mt-2 p-2 bg-amber-50 border border-amber-100 rounded-xl text-[10px] text-amber-700 flex items-center gap-2 font-semibold">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
              {t('choiceGroupPreview.resultDesc', { success: totalSuccessful, failed: totalFailed })}
            </div>
          )}
        </div>

        {/* Candidate tabs with Compare option */}
        {showCompareOption && (
          <div className="flex items-center justify-between gap-3 px-6 pt-4 pb-2 border-b border-slate-100 shrink-0 bg-slate-50/10">
            <div className="flex items-center gap-1.5 overflow-x-auto select-none">
              <button
                type="button"
                onClick={() => setIsCompareMode(true)}
                className={`shrink-0 min-w-[220px] h-10 px-4 rounded-xl text-xs font-extrabold transition-all border inline-flex items-center justify-center ${
                  compareActive
                    ? 'bg-indigo-600 text-white shadow-sm border-indigo-650'
                    : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                }`}
              >
                {t('choiceGroupPreview.diffTable')}
              </button>
              
              <div className="w-[1px] h-5 bg-slate-200 self-center mx-1 shrink-0" />

              {successfulChoices.map((c: any, i: number) => {
                const tabTitle = getChoiceStrategyLabel(c, i18n.t('choiceGroupPreview.planLabel', { index: i + 1 }));
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => {
                      setIsCompareMode(false);
                      setActiveChoiceIndex(i);
                    }}
                    className={`shrink-0 min-w-[220px] h-10 px-4 rounded-xl text-xs font-extrabold transition-all border inline-flex items-center justify-center ${
                      !compareActive && i === activeChoiceIndex
                        ? 'bg-indigo-100 text-indigo-700 border-indigo-250'
                        : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    {tabTitle}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Preview Viewport */}
        <div className="flex-1 overflow-y-auto p-6 min-h-0 bg-white">
          {compareActive ? (
            <CandidateComparisonView
              choices={successfulChoices}
              draftType={draftType}
              onAccept={onAccept}
              isWorking={isWorking}
            />
          ) : (
            activeChoice && (
              <ChoicePreviewRenderer
                draftType={draftType}
                preview={activeChoice.preview}
                payload={activeChoice.payload}
                comparisonSummary={activeChoice.comparisonSummary}
              />
            )
          )}
        </div>

        {/* Failed choices if any */}
        {failedChoices.length > 0 && (
          <div className="px-6 pb-2 shrink-0 bg-white border-t border-slate-50 pt-2">
            <details className="group">
              <summary className="text-xs text-slate-400 cursor-pointer hover:text-slate-600 select-none">
                {t('choiceGroupPreview.failedChoicesTitle', { count: failedChoices.length })}
              </summary>
              <div className="mt-2 space-y-2">
                {failedChoices.map((fc: any) => (
                  <div key={fc.id} className="flex items-center justify-between p-2.5 rounded-xl bg-rose-50 border border-rose-100">
                    <div className="text-xs text-rose-600 font-medium">
                      <strong>{getFailedChoiceTitle(fc, group.generationType, t)}</strong>:{' '}
                      {getFailedChoiceError(fc, t('choiceGroupPreview.failedChoicesDesc'), t)}
                    </div>
                    {onRegenerate && (
                      <button
                        type="button"
                        onClick={() => onRegenerate(fc.id)}
                        className="text-xs text-indigo-600 hover:text-indigo-800 font-bold shrink-0 ml-2"
                      >
                        {t('choiceGroupPreview.retryBtn')}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </details>
          </div>
        )}

        {/* Actions Footer */}
        <div className="p-6 border-t border-slate-100 bg-slate-50/50 shrink-0 rounded-b-3xl">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onDefer}
                disabled={isWorking}
                className="inline-flex items-center gap-1.5 h-10 px-4 rounded-xl border border-slate-200 bg-white text-xs font-bold text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-50 shadow-sm"
              >
                {t('choiceGroupPreview.laterBtn')}
              </button>
              <button
                type="button"
                onClick={onDiscard}
                disabled={isWorking}
                className="inline-flex items-center gap-1.5 h-10 px-4 rounded-xl border border-red-200 bg-white text-xs font-bold text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50 shadow-sm"
              >
                <Trash2 className="w-3.5 h-3.5" />
                {t('choiceGroupPreview.discardAllBtn')}
              </button>
            </div>
            <div className="flex gap-2">
              {onRegenerate && (
                <button
                  type="button"
                  onClick={() => onRegenerate()}
                  disabled={isWorking}
                  className="inline-flex items-center gap-1.5 h-10 px-4 rounded-xl border border-slate-200 bg-white text-xs font-bold text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-50 shadow-sm"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-indigo-500" />
                  {t('choiceGroupPreview.retryAllBtn')}
                </button>
              )}
              {!compareActive && activeChoice && (
                <button
                  type="button"
                  onClick={() => handleAcceptClick(activeChoice.id)}
                  disabled={isWorking}
                  className="inline-flex items-center gap-1.5 h-10 px-6 rounded-xl bg-indigo-600 hover:bg-indigo-750 text-xs font-bold text-white shadow-lg shadow-indigo-100 transition-colors disabled:opacity-50 active:scale-[0.98]"
                >
                  {isWorking ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="w-3.5 h-3.5 animate-pulse" />
                  )}
                  {isWorking ? t('choiceGroupPreview.adoptingPlanBtn') : t('choiceGroupPreview.adoptPlanBtn')}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
