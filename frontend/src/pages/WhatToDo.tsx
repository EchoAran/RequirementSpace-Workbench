import { useState, type MouseEvent, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, ChevronRight, Sparkles, Check, X, RefreshCw, Plus, Trash2 } from 'lucide-react';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { DraftPreviewModal } from '@/components/shared/DraftPreviewModal';
import { StageGuidanceBanner } from '@/components/shared/StageGuidanceBanner';
import { ConfirmTransitionModal } from '@/components/shared/ConfirmTransitionModal';
import { 
  useWorkspaceStore, 
  selectActors, 
  selectPageHealth,
} from '@/store/useWorkspaceStore';
import {
  buildProjectRoute,
  getStageIssues,
  getChildCapabilities,
  getRootCapabilities,
} from '@/core/selectors';

export function WhatToDo() {
  const navigate = useNavigate();
  const { 
    setSelectedObject, highlightTarget, selectedObject, ir, setHighlightTarget,
    pendingManualAction, setPendingManualAction,
    generateActors, regenerateActors, confirmActors,
    generateFeatures, regenerateFeatures, confirmFeatures,
    generateScenarios, regenerateScenarios, confirmScenarios,
    generateAcceptanceCriteria, regenerateAcceptanceCriteria, confirmAcceptanceCriteria,
    discardDraft, activeDraft, activeDraftType, isGenerating, isLoading, isDiagnosing,
    addActor, addFeature, lastActionMessage,
    addScenario, deleteScenario, addAcceptanceCriterion, deleteAcceptanceCriterion,
    deleteActor, deleteFeature, expandSlot, runDiagnosis, unlockStageGate,
    confirmRepairDraft,
    discardRepairDraft,
    regenerateRepairDraft,
    createSlotFromIssue, updateIssueAttributes, clearPerceptionSlot
  } = useWorkspaceStore();
  
  const actors = useWorkspaceStore(selectActors);

  const rootCapabilities = getRootCapabilities(ir as any) as any[];
  
  const [expandedCaps, setExpandedCaps] = useState<Record<string, boolean>>({});
  const [actorFeedback, setActorFeedback] = useState('');
  const [featureFeedback, setFeatureFeedback] = useState('');
  const [scenarioFeedback, setScenarioFeedback] = useState('');
  const [acFeedback, setAcFeedback] = useState('');

  const [isScenarioModalOpen, setIsScenarioModalOpen] = useState(false);
  const [selectedFeatureIds, setSelectedFeatureIds] = useState<number[]>([]);
  
  const [isAddActorModalOpen, setIsAddActorModalOpen] = useState(false);
  const [newActorName, setNewActorName] = useState('');
  const [newActorDesc, setNewActorDesc] = useState('');

  const [isAddFeatureModalOpen, setIsAddFeatureModalOpen] = useState(false);
  const [newFeatureName, setNewFeatureName] = useState('');
  const [newFeatureDesc, setNewFeatureDesc] = useState('');
  const [newFeatureParentId, setNewFeatureParentId] = useState<number | null>(null);
  const [isParentFixed, setIsParentFixed] = useState(false);

  // Scenario Manager Modal Local State
  const [scenarioManagerFeature, setScenarioManagerFeature] = useState<any | null>(null);
  const [modalNewScenName, setModalNewScenName] = useState('');
  const [modalNewScenContent, setModalNewScenContent] = useState('');
  const [modalNewScenActorId, setModalNewScenActorId] = useState<number>(0);
  const [modalAddingAcForScenId, setModalAddingAcForScenId] = useState<number | null>(null);
  const [modalNewAcContent, setModalNewAcContent] = useState('');
  const [showAddScenarioForm, setShowAddScenarioForm] = useState(false);
  const [isTransitionModalOpen, setIsTransitionModalOpen] = useState(false);

  const toggleCap = (e: MouseEvent, id: string) => {
    e.stopPropagation();
    setExpandedCaps(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const leafFeatures = (ir?.features || []).filter(f => {
    const isParent = (ir?.features || []).some(child => child.parentId === f.featureId);
    return f.parentId !== null && !isParent;
  });

  const managedFeatObj = ir?.features?.find(f => f.featureId === scenarioManagerFeature?.featureId);

  const pageHealth = selectPageHealth({ ir } as any, '/what');

  const executeManualAction = (kind: string, targetId?: number, focusMode?: string) => {
    if (kind === 'missing_actor' || kind === 'what_onboarding') {
      setIsAddActorModalOpen(true);
    } else if (kind === 'missing_feature') {
      setIsAddFeatureModalOpen(true);
    } else if (kind === 'stage_gate_transition_confirm') {
      setIsTransitionModalOpen(true);
    } else if (targetId) {
      const featIdStr = targetId.toString();
      const featObj = ir?.features?.find((f: any) => f.featureId === targetId);
      if (featObj) {
        // Expand parent capability
        if (featObj.parentId) {
          setExpandedCaps((prev) => ({ ...prev, [featObj.parentId]: true }));
        }

        // Set highlight target to trigger the 3-second temporary border
        setHighlightTarget(featIdStr);

        if (kind === 'missing_scenario') {
          // Open scenarios modal
          setScenarioManagerFeature({ featureId: targetId });
        } else if (kind === 'missing_acceptance_criteria') {
          // Open scenarios modal
          setScenarioManagerFeature({ featureId: targetId });
        } else {
          // Open right drawer
          const childNode = ir.capabilitiesCompatible?.find((c: any) => c.featureId === targetId || c.id === featIdStr);
          setSelectedObject(childNode || featObj);
        }
      }
    }
  };

  const handleManualAction = (slot: any) => {
    if (slot.kind === 'generative_perception_slot') {
      void clearPerceptionSlot();
      return;
    }
    executeManualAction(slot.kind, slot.targetId || slot.actions?.manual?.targetId, slot.actions?.manual?.focusMode);
  };

  const handleAIAction = async (slot: any) => {
    const kind = slot.kind;
    if (kind === 'stage_gate_transition_confirm') {
      await runDiagnosis();
    } else if (kind === 'what_onboarding' || kind === 'missing_actor') {
      await generateActors();
    } else if (kind === 'missing_feature') {
      await generateFeatures();
    } else if (kind === 'missing_scenario' && slot.targetId) {
      await generateScenarios([slot.targetId]);
    } else if (kind === 'missing_acceptance_criteria' && slot.targetId) {
      const featObj = ir?.features?.find((f: any) => f.featureId === slot.targetId);
      const badScenIds = (featObj?.scenarios || [])
        .filter((s: any) => !s.acceptanceCriteria || s.acceptanceCriteria.length === 0)
        .map((s: any) => s.scenarioId);
      if (badScenIds.length > 0) {
        await generateAcceptanceCriteria(badScenIds);
      }
    } else {
      if (slot.id) {
        await expandSlot(slot.id);
      }
    }
  };

  const whatIssues = getStageIssues(ir, 'what');

  const handleIssueClick = (issue: any) => {
    setSelectedObject(issue);
    const targetId = issue.relatedNodeIds?.[0];
    if (targetId) {
      setHighlightTarget(targetId);
    }
  };

  const openIssueFlow = async (issue: any) => {
    const slotId = await createSlotFromIssue(issue.id);
    if (slotId) {
      await expandSlot(slotId);
    }
  };

  // Consume pendingManualAction on mount or action change
  useEffect(() => {
    if (pendingManualAction && ir) {
      const { kind, targetId, focusMode } = pendingManualAction;
      setPendingManualAction(null);
      executeManualAction(kind, targetId, focusMode);
    }
  }, [pendingManualAction, ir]);

  // Temporary 3-second highlight scroll
  useEffect(() => {
    if (highlightTarget) {
      setTimeout(() => {
        const element = document.getElementById(`feature-card-${highlightTarget}`);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 100);

      const timer = setTimeout(() => {
        setHighlightTarget(null);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [highlightTarget]);

  // Initialize actor select inside modal when opened
  useEffect(() => {
    if (scenarioManagerFeature && ir?.actors && ir.actors.length > 0) {
      setModalNewScenActorId(ir.actors[0].actorId);
    }
    setShowAddScenarioForm(false);
    setModalAddingAcForScenId(null);
  }, [scenarioManagerFeature, ir]);

  // Auto-focus AC input for first scenario missing AC in managedFeatObj
  useEffect(() => {
    if (managedFeatObj && highlightTarget) {
      const firstBadScen = (managedFeatObj.scenarios || []).find(
        (s: any) => !s.acceptanceCriteria || s.acceptanceCriteria.length === 0
      );
      if (firstBadScen) {
        setModalAddingAcForScenId(firstBadScen.scenarioId);
        setModalNewAcContent('');
      }
    }
  }, [managedFeatObj, highlightTarget]);

  return (
    <div className="flex-1 flex w-full relative">
      <div className="flex-1 p-6 pb-24 overflow-y-auto w-full">
        <div className="max-w-[1240px] mx-auto animate-in fade-in duration-500">
          
          <div className="grid grid-cols-12 gap-6 h-full content-start">
            
            <div className="col-span-12">
              <StageGuidanceBanner 
                slot={pageHealth.nextSlot} 
                issues={whatIssues as any}
                onManualAction={handleManualAction} 
                onAIAction={handleAIAction}
                onReDiagnose={runDiagnosis}
                onIssueClick={handleIssueClick}
                onIssueCreateSlot={(issue) => void openIssueFlow(issue)}
                onIssueIgnore={(issue) => void updateIssueAttributes(issue.id, { status: 'ignored' })}
                isWorking={isGenerating || isLoading || isDiagnosing}
              />
            </div>

            {/* AI Actor Draft Preview Banner */}
            {activeDraft && activeDraftType === 'actor' && (
              <div className="col-span-12 bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-6 border border-amber-200/80 shadow-md animate-in slide-in-from-top-4 duration-500 space-y-4">
                <div className="flex justify-between items-start">
                  <div className="flex items-center gap-2 flex-1 mr-4">
                    <span className="p-1.5 bg-amber-100 text-amber-700 rounded-lg shrink-0">
                      <Sparkles className="w-5 h-5 animate-pulse" />
                    </span>
                    <div className="flex-1 space-y-2">
                      <div>
                        <h3 className="text-base font-bold text-slate-900">AI 推荐的参与者定义已生成</h3>
                        <p className="text-xs text-slate-500 mt-0.5">AI 根据您的业务规划，推演了潜在的系统交互参与者与职责划分。</p>
                      </div>
                      <div className="flex gap-2 items-center max-w-md">
                        <input
                          type="text"
                          value={actorFeedback}
                          onChange={(e) => setActorFeedback(e.target.value)}
                          placeholder="补充参与者调整意见，例如：'增加审核经理参与者' (可选)"
                          className="flex-1 px-3 py-1.5 bg-white border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800"
                          disabled={isGenerating || isLoading}
                        />
                        <button
                          onClick={async () => {
                            await regenerateActors(actorFeedback || undefined);
                            setActorFeedback('');
                          }}
                          disabled={isGenerating || isLoading}
                          className="flex items-center gap-1 px-3 py-1.5 border border-slate-200 bg-white text-slate-700 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                        >
                          <RefreshCw className={`w-3 h-3 text-indigo-500 ${isGenerating || isLoading ? 'animate-spin' : ''}`} />
                          重新推演
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={confirmActors}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50"
                    >
                      <Check className="w-3.5 h-3.5" />
                      采纳并合并推荐
                    </button>
                    <button
                      onClick={discardDraft}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                    >
                      <X className="w-3.5 h-3.5" />
                      放弃
                    </button>
                  </div>
                </div>

                {/* Actor preview list */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2 border-t border-slate-200/60">
                  {activeDraft.actors?.map((act: any, idx: number) => (
                    <div key={idx} className="bg-white/80 p-4 rounded-xl border border-slate-200/50">
                      <span className="font-bold text-xs text-slate-800">👤 {act.actor_name}</span>
                      <p className="text-xs text-slate-500 mt-1 leading-normal">{act.actor_description}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* AI Feature Draft Preview Banner */}
            {activeDraft && activeDraftType === 'feature' && (
              <div className="col-span-12 bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-6 border border-amber-200/80 shadow-md animate-in slide-in-from-top-4 duration-500 space-y-4">
                <div className="flex justify-between items-start">
                  <div className="flex items-center gap-2 flex-1 mr-4">
                    <span className="p-1.5 bg-amber-100 text-amber-700 rounded-lg shrink-0">
                      <Sparkles className="w-5 h-5 animate-pulse" />
                    </span>
                    <div className="flex-1 space-y-2">
                      <div>
                        <h3 className="text-base font-bold text-slate-900">AI 推荐的功能分解树已生成</h3>
                        <p className="text-xs text-slate-500 mt-0.5">AI 根据主应用目标，将核心功能分解为具体的二级模块与三级叶子结点。</p>
                      </div>
                      <div className="flex gap-2 items-center max-w-md">
                        <input
                          type="text"
                          value={featureFeedback}
                          onChange={(e) => setFeatureFeedback(e.target.value)}
                          placeholder="补充功能调整意见 (可选)"
                          className="flex-1 px-3 py-1.5 bg-white border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800"
                          disabled={isGenerating || isLoading}
                        />
                        <button
                          onClick={async () => {
                            await regenerateFeatures(featureFeedback || undefined);
                            setFeatureFeedback('');
                          }}
                          disabled={isGenerating || isLoading}
                          className="flex items-center gap-1 px-3 py-1.5 border border-slate-200 bg-white text-slate-700 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                        >
                          <RefreshCw className={`w-3 h-3 text-indigo-500 ${isGenerating || isLoading ? 'animate-spin' : ''}`} />
                          重新推演
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={confirmFeatures}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50"
                    >
                      <Check className="w-3.5 h-3.5" />
                      采纳并合并推荐
                    </button>
                    <button
                      onClick={discardDraft}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                    >
                      <X className="w-3.5 h-3.5" />
                      放弃
                    </button>
                  </div>
                </div>

                {/* Feature preview tree */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-200/60">
                  {activeDraft.features?.map((feat: any, idx: number) => (
                    <div key={idx} className="bg-white/80 p-4 rounded-xl border border-slate-200/50">
                      <span className="font-bold text-xs text-slate-800">🌳 功能模块: {feat.feature_name}</span>
                      <p className="text-xs text-slate-500 mt-1 leading-normal mb-2">{feat.feature_description}</p>
                      {feat.actor_names && feat.actor_names.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {feat.actor_names.map((actName: string, i: number) => (
                            <span key={i} className="text-[10px] bg-slate-100 px-2 py-0.5 rounded text-slate-600 border border-slate-200/50 font-bold">{actName}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* AI Scenario Draft Preview Banner */}
            {activeDraft && activeDraftType === 'scenario' && (
              <div className="col-span-12 bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-6 border border-amber-200/80 shadow-md animate-in slide-in-from-top-4 duration-500 space-y-4">
                <div className="flex justify-between items-start">
                  <div className="flex items-center gap-2 flex-1 mr-4">
                    <span className="p-1.5 bg-amber-100 text-amber-700 rounded-lg shrink-0">
                      <Sparkles className="w-5 h-5 animate-pulse" />
                    </span>
                    <div className="flex-1 space-y-2">
                      <div>
                        <h3 className="text-base font-bold text-slate-900">AI 推荐的典型成功场景已生成</h3>
                        <p className="text-xs text-slate-500 mt-0.5">AI 根据具体功能叶子结点推演了最佳的业务流成功场景。</p>
                      </div>
                      <div className="flex gap-2 items-center max-w-md">
                        <input
                          type="text"
                          value={scenarioFeedback}
                          onChange={(e) => setScenarioFeedback(e.target.value)}
                          placeholder="补充场景调整意见 (可选)"
                          className="flex-1 px-3 py-1.5 bg-white border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800"
                          disabled={isGenerating || isLoading}
                        />
                        <button
                          onClick={async () => {
                            await regenerateScenarios(scenarioFeedback || undefined);
                            setScenarioFeedback('');
                          }}
                          disabled={isGenerating || isLoading}
                          className="flex items-center gap-1 px-3 py-1.5 border border-slate-200 bg-white text-slate-700 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                        >
                          <RefreshCw className={`w-3 h-3 text-indigo-500 ${isGenerating || isLoading ? 'animate-spin' : ''}`} />
                          重新推演
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => confirmScenarios(true)}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50"
                    >
                      <Check className="w-3.5 h-3.5" />
                      采纳并合并推荐 (同步生成 AC)
                    </button>
                    <button
                      onClick={discardDraft}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                    >
                      <X className="w-3.5 h-3.5" />
                      放弃
                    </button>
                  </div>
                </div>

                {/* Scenario preview list */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-200/60">
                  {activeDraft.scenarios?.map((sc: any, idx: number) => (
                    <div key={idx} className="bg-white/80 p-4 rounded-xl border border-slate-200/50 flex flex-col justify-between">
                      <div>
                        <span className="font-bold text-xs text-slate-800 block">🎬 {sc.scenario_name}</span>
                        <p className="text-xs text-slate-600 bg-slate-50 p-2 rounded border border-slate-100/50 mt-1.5 italic">
                          "{sc.scenario_content}"
                        </p>
                      </div>
                      <div className="mt-3 flex items-center justify-between text-[10px] text-indigo-600 font-bold uppercase">
                        <span>功能 ID: {sc.feature_id}</span>
                        <span>参与者 ID: {sc.actor_id}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* AI Acceptance Criteria Draft Preview Banner */}
            {activeDraft && activeDraftType === 'ac' && (
              <div className="col-span-12 bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-6 border border-amber-200/80 shadow-md animate-in slide-in-from-top-4 duration-500 space-y-4">
                <div className="flex justify-between items-start">
                  <div className="flex items-center gap-2 flex-1 mr-4">
                    <span className="p-1.5 bg-amber-100 text-amber-700 rounded-lg shrink-0">
                      <Sparkles className="w-5 h-5 animate-pulse" />
                    </span>
                    <div className="flex-1 space-y-2">
                      <div>
                        <h3 className="text-base font-bold text-slate-900">AI 推荐的验收标准 (AC) 已生成</h3>
                        <p className="text-xs text-slate-500 mt-0.5">AI 根据选定的典型成功场景，全自动推演编写了结构化、可测试的验收标准。</p>
                      </div>
                      <div className="flex gap-2 items-center max-w-md">
                        <input
                          type="text"
                          value={acFeedback}
                          onChange={(e) => setAcFeedback(e.target.value)}
                          placeholder="补充验收标准调整意见 (可选)"
                          className="flex-1 px-3 py-1.5 bg-white border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800"
                          disabled={isGenerating || isLoading}
                        />
                        <button
                          onClick={async () => {
                            await regenerateAcceptanceCriteria(acFeedback || undefined);
                            setAcFeedback('');
                          }}
                          disabled={isGenerating || isLoading}
                          className="flex items-center gap-1 px-3 py-1.5 border border-slate-200 bg-white text-slate-700 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                        >
                          <RefreshCw className={`w-3 h-3 text-indigo-500 ${isGenerating || isLoading ? 'animate-spin' : ''}`} />
                          重新推演
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={confirmAcceptanceCriteria}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50"
                    >
                      <Check className="w-3.5 h-3.5" />
                      采纳并合并推荐
                    </button>
                    <button
                      onClick={discardDraft}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                    >
                      <X className="w-3.5 h-3.5" />
                      放弃
                    </button>
                  </div>
                </div>

                {/* AC preview list */}
                <div className="pt-2 border-t border-slate-200/60 space-y-2 col-span-12">
                  {activeDraft.acceptance_criteria?.map((ac: any, idx: number) => (
                    <div key={idx} className="bg-white/80 p-3 rounded-xl border border-slate-200/50 flex items-start gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0 mt-1.5 animate-pulse"></span>
                      <div className="flex-1">
                        <span className="text-xs text-slate-700 leading-normal font-medium">{ac.criterion_content}</span>
                        <span className="text-[10px] text-slate-400 block mt-1 font-mono">关联场景 ID: {ac.scenario_id}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            


            {/* Tree and other main sections */}
            <div className="col-span-12 space-y-6">
              
              {/* Roles Section (RE-ENABLED) */}
              <section className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                <div className="flex justify-between items-center px-1 mb-4 pb-3 border-b border-slate-100">
                  <h3 className="text-xs font-bold text-slate-800 uppercase tracking-widest flex items-center gap-2">
                    👥 参与者
                    <button
                      onClick={() => setIsAddActorModalOpen(true)}
                      className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-md transition-all shadow-sm"
                      title="手动创建参与者"
                    >
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                  </h3>
                  <button
                    onClick={generateActors}
                    disabled={isGenerating || isLoading}
                    className="flex items-center gap-1.5 text-[10px] bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold px-3 py-1.5 rounded-xl border border-indigo-100/80 transition-colors shadow-sm disabled:opacity-50"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
                    AI 智能生成参与者
                  </button>
                </div>
                {actors.length === 0 ? (
                  <div className="text-center py-10 border border-dashed border-slate-100 rounded-xl text-xs text-slate-500 italic">
                    暂无参与者定义。请点击右上角手动新增或运行 AI 智能生成。
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {actors.map(actor => (
                      <div 
                        key={actor.id} 
                        onClick={() => setSelectedObject(actor)}
                        className={`bg-white rounded-xl p-4 border transition-all cursor-pointer flex flex-col gap-3 ${selectedObject?.id === actor.id ? 'ring-2 ring-indigo-500 border-transparent shadow-md' : 'border-slate-200 hover:border-indigo-300 hover:shadow-sm shadow-inner bg-slate-50/20'}`}
                      >
                        <div className="flex justify-between items-start">
                          <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600 font-bold border border-indigo-100">
                              {actor.title.charAt(0)}
                            </div>
                            <div>
                              <h4 className="font-bold text-slate-800 text-sm tracking-wide">{actor.title}</h4>
                              <span className="text-[10px] text-slate-400">
                                {actor.scopeStatus === 'in_scope'
                                  ? '本期覆盖'
                                  : actor.scopeStatus === 'external_dependency'
                                    ? '外部依赖'
                                    : actor.scopeStatus === 'deferred'
                                      ? '暂缓'
                                      : actor.status === 'excluded' || actor.scopeStatus === 'out_of_scope'
                                        ? '不在范围'
                                        : '待确认范围'}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <button
                              onClick={async (e) => {
                                e.stopPropagation();
                                if (window.confirm(`确定要删除参与者“${actor.title}”吗？此操作将清除该参与者及其所有关联，不可恢复！`)) {
                                  await deleteActor(actor.actorId);
                                  if (selectedObject?.actorId === actor.actorId) {
                                    setSelectedObject(null);
                                  }
                                }
                              }}
                              className="p-1 hover:bg-rose-50 border border-transparent hover:border-rose-100 rounded-lg text-slate-400 hover:text-rose-600 transition-all flex items-center justify-center animate-none"
                              title="删除该参与者"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                            <StatusBadge status={actor.status} className="scale-90 origin-right" />
                          </div>
                        </div>
                        <div className="text-xs text-slate-600 line-clamp-2 leading-relaxed">
                          {actor.description || '无具体描述说明'}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Tree Section */}
              <section>
                <div className="flex justify-between items-center px-1 mb-3">
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                    🌳 核心能力特征树
                    <button
                      onClick={() => {
                        setNewFeatureParentId(null);
                        setIsParentFixed(false);
                        setIsAddFeatureModalOpen(true);
                      }}
                      className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-md transition-all shadow-sm"
                      title="手动创建功能结点"
                    >
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                  </h3>
                  <div className="flex gap-2">
                    <button
                      onClick={generateFeatures}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 text-[10px] bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold px-3 py-1.5 rounded-xl border border-indigo-100/80 transition-colors shadow-sm disabled:opacity-50"
                    >
                      <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
                      AI 智能分解功能
                    </button>
                    <button
                      onClick={() => setIsScenarioModalOpen(true)}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 text-[10px] bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold px-3 py-1.5 rounded-xl border border-indigo-100/80 transition-colors shadow-sm disabled:opacity-50"
                      title="智能推演系统业务场景"
                    >
                      <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
                      AI智能推演场景
                    </button>
                  </div>
                </div>
                <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                  
                  {/* Layer 1: System Root Header */}
                  <div 
                    onClick={() => ir && setSelectedObject({ kind: 'project', id: ir.projectId.toString(), projectId: ir.projectId, projectName: ir.projectName, projectDescription: ir.projectDescription })}
                    className={`bg-gradient-to-r from-indigo-50/80 to-sky-50/80 backdrop-blur-sm text-slate-800 rounded-2xl p-5 mb-6 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between shadow-sm border transition-all cursor-pointer ${
                      selectedObject?.kind === 'project'
                        ? 'ring-2 ring-indigo-500 border-transparent shadow-md bg-indigo-50/10'
                        : 'border-indigo-100 hover:border-indigo-300'
                    }`}
                  >
                    <div className="min-w-0">
                      <h4 className="font-extrabold text-base text-slate-900 tracking-wide flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-pulse"></span>
                        {ir?.projectName || '核心系统'}
                      </h4>
                      <p className="text-xs text-slate-500 mt-1.5 max-w-4xl font-medium">{ir?.projectDescription || '主系统业务空间与架构模型总揽。'}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setNewFeatureParentId(null);
                          setIsParentFixed(true);
                          setIsAddFeatureModalOpen(true);
                        }}
                        className="p-1 hover:bg-slate-200 border border-slate-200 hover:border-indigo-200 rounded-lg text-slate-500 hover:text-indigo-600 transition-all flex items-center justify-center bg-white"
                        title="添加一级模块功能结点"
                      >
                        <Plus className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  <div className="space-y-4 pl-4 border-l-2 border-indigo-100 ml-2">
                    {rootCapabilities.map(cap => {
                      const children = getChildCapabilities(ir as any, cap.id) as any[];
                      return (
                        <div key={cap.id} className="relative">
                          <div className="absolute w-4 h-px bg-indigo-100 -left-4 top-5"></div>
                          
                          {/* Layer 2: Functional Module (Branch Node) */}
                          <div 
                            onClick={() => setSelectedObject(cap)}
                            className={`rounded-xl p-4 cursor-pointer transition-all mb-2 bg-slate-50 border ${selectedObject?.id === cap.id ? 'bg-indigo-50 border-2 border-indigo-500 shadow-sm' : 'border-slate-200 hover:border-indigo-300'}`}
                          >
                            <div className="flex items-center justify-between pb-2 border-b border-slate-200/60 mb-2">
                              <div className="flex items-center gap-2">
                                {children.length > 0 && (
                                  <button onClick={(e) => toggleCap(e, cap.id)} className="p-0.5 hover:bg-slate-200 rounded text-slate-500 transition-colors animate-none">
                                    {expandedCaps[cap.id] !== false ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                                  </button>
                                )}
                                <h4 className="font-bold text-slate-800 text-sm flex items-center gap-1.5">
                                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400"></span>
                                  功能模块: {cap.title}
                                </h4>
                              </div>
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    if (window.confirm(`确定要删除功能结点 “${cap.title}” 吗？此操作将递归删除其所有子级能力和场景，不可恢复！`)) {
                                      await deleteFeature(cap.featureId);
                                      if (selectedObject?.id === cap.id || selectedObject?.featureId === cap.featureId) {
                                        setSelectedObject(null);
                                      }
                                    }
                                  }}
                                  className="p-1 hover:bg-rose-50 border border-transparent hover:border-rose-100 rounded-lg text-slate-400 hover:text-rose-600 transition-all flex items-center justify-center animate-none"
                                  title="删除该功能模块"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setNewFeatureParentId(cap.featureId);
                                    setIsParentFixed(true);
                                    setIsAddFeatureModalOpen(true);
                                  }}
                                  className="p-1 hover:bg-slate-200 border border-slate-200 hover:border-indigo-200 rounded-lg text-slate-500 hover:text-indigo-600 transition-all flex items-center justify-center bg-white"
                                  title="为此模块直接添加子功能结点"
                                >
                                  <Plus className="w-3.5 h-3.5" />
                                </button>
                                <StatusBadge status={cap.status} />
                              </div>
                            </div>
                            
                            <p className="text-xs text-slate-500 ml-6 leading-relaxed mb-2">
                              {cap.description || '暂无该模块的功能说明'}
                            </p>
                            
                            <div className="flex flex-wrap gap-2 text-[10px] font-medium ml-6">
                              <span className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded border border-slate-200">
                                包含 {children.length} 个具体子功能点
                              </span>
                            </div>
                          </div>
                          
                          {/* Layer 3: Leaf Nodes (Specific Features) */}
                          {(children.length > 0 && expandedCaps[cap.id] !== false) && (
                            <div className="pl-6 space-y-2 mt-2 relative">
                              <div className="absolute w-px h-full bg-slate-100 left-3 top-0"></div>
                              {children.map(child => {
                                const featObj = (ir?.features || []).find(f => f.featureId.toString() === child.id || f.featureId === child.featureId);
                                const capScenarios = featObj?.scenarios || [];
                                const capActors = featObj?.actorIds || [];
                                const capAcCount = capScenarios.reduce((acc: number, s: any) => acc + (s.acceptanceCriteria?.length || 0), 0);
                                const boundActors = (ir?.actors || []).filter((a: any) => capActors.includes(a.actorId));

                                return (
                                  <div 
                                    key={child.id} 
                                    id={`feature-card-${child.id}`}
                                    onClick={(e) => { e.stopPropagation(); setSelectedObject(child); }}
                                    className={`relative flex flex-col justify-center rounded-xl p-4 cursor-pointer group transition-all mb-2 border ${
                                      highlightTarget === child.id
                                        ? 'ring-2 ring-amber-400 border-transparent shadow-[0_0_10px_rgba(245,158,11,0.3)] bg-amber-50/10'
                                        : selectedObject?.id === child.id 
                                          ? 'bg-indigo-50 border-2 border-indigo-500 z-10 shadow-sm' 
                                          : 'bg-white border-slate-200 hover:border-indigo-300 hover:shadow-sm'
                                    }`}
                                  >
                                    <div className="absolute w-3 h-px bg-slate-100 -left-3 top-6"></div>
                                    <div className="flex items-center justify-between mb-2">
                                      <h5 className="text-xs font-bold text-slate-800 group-hover:text-indigo-700 transition-colors flex items-center gap-1.5">
                                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                                        具体功能点: {child.title}
                                      </h5>
                                      <div className="flex items-center gap-1.5">
                                        <button
                                          onClick={async (e) => {
                                            e.stopPropagation();
                                            if (window.confirm(`确定要删除功能结点 “${child.title}” 吗？此操作将递归删除其场景和验收标准，不可恢复！`)) {
                                              await deleteFeature(child.featureId);
                                              if (selectedObject?.id === child.id || selectedObject?.featureId === child.featureId) {
                                                setSelectedObject(null);
                                              }
                                            }
                                          }}
                                          className="p-1 hover:bg-rose-50 border border-transparent hover:border-rose-100 rounded-lg text-slate-400 hover:text-rose-600 transition-all flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                                          title="删除该功能点"
                                        >
                                          <Trash2 className="w-3 h-3" />
                                        </button>
                                        <StatusBadge status={child.status} className="scale-75 origin-right" />
                                      </div>
                                    </div>
                                    <div className="text-xs text-slate-500 line-clamp-2 ml-4 leading-relaxed">
                                      {child.description || '暂无功能点描述'}
                                    </div>

                                    {/* Leaf capability rich metadata badges + interactive Modal trigger button */}
                                    <div className="flex flex-wrap items-center justify-between ml-4 mt-3 pt-2.5 border-t border-slate-100/60 gap-3">
                                      <div className="flex flex-wrap gap-1.5 text-[10px] font-bold">
                                        <span className="bg-indigo-50 border border-indigo-100 text-indigo-700 px-2 py-0.5 rounded-md shadow-sm">
                                          {capScenarios.length} 个成功场景
                                        </span>
                                        <span className="bg-purple-50 border border-purple-100 text-purple-700 px-2 py-0.5 rounded-md shadow-sm">
                                          {capAcCount} 个验收标准
                                        </span>
                                        {capActors.length > 0 ? (
                                          <span 
                                            className="bg-blue-50 border border-blue-200 text-blue-700 px-2 py-0.5 rounded-md shadow-sm transition-all"
                                            title={`已关联参与者: ${boundActors.map((a: any) => a.actorName).join(', ')}`}
                                          >
                                            👤 {capActors.length} 个参与者: {boundActors.map((a: any) => a.actorName).join(', ')}
                                          </span>
                                        ) : (
                                          <span className="bg-rose-50 border border-rose-200 text-rose-600 px-2 py-0.5 rounded-md shadow-sm transition-all font-bold">
                                            ⚠️ 未绑定参与者
                                          </span>
                                        )}
                                      </div>

                                      <button
                                        type="button"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          setScenarioManagerFeature(child);
                                        }}
                                        className="text-[10px] bg-slate-900 hover:bg-indigo-600 text-white font-bold px-2.5 py-1 rounded-lg transition-colors shadow-sm flex items-center gap-1 shrink-0"
                                      >
                                        🎬 场景与验收标准
                                      </button>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </section>

            </div>
          </div>
        </div>
      </div>
      
      {/* AI Scenario Selection Modal */}
      {isScenarioModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4 select-none animate-in fade-in duration-200">
          <div className="bg-white/95 border border-slate-200 shadow-2xl max-w-xl w-full max-h-[80vh] flex flex-col rounded-3xl animate-in scale-in-95 duration-200 overflow-hidden">
            
            {/* Modal Header */}
            <div className="p-6 pb-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
              <div>
                <h3 className="font-extrabold text-sm text-slate-800 flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-indigo-500" />
                  AI 智能推演场景功能选择
                </h3>
                <p className="text-[10px] text-slate-500 mt-1">请选择需要进行业务场景及验收标准 (AC) 推演的功能模块。</p>
              </div>
              <button 
                onClick={() => { setIsScenarioModalOpen(false); setSelectedFeatureIds([]); }}
                className="w-6 h-6 rounded-full hover:bg-slate-200 flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {(() => {
                if (leafFeatures.length === 0) {
                  return (
                    <div className="text-center text-xs text-slate-400 italic py-8">
                      暂无可用于推演的具体三级功能结点，请先使用 AI 功能分解或手动创建功能。
                    </div>
                  );
                }

                return (
                  <>
                    <div className="flex justify-between items-center text-[10px] text-slate-400 font-bold bg-slate-50 p-2.5 rounded-xl border border-slate-100/50">
                      <span>待选叶子功能结点 ({leafFeatures.length} 个)</span>
                      <div className="flex gap-3">
                        <button 
                          type="button" 
                          onClick={() => setSelectedFeatureIds(leafFeatures.map(f => f.featureId))}
                          className="text-indigo-600 hover:text-indigo-700 transition-colors"
                        >
                          全选
                        </button>
                        <button 
                          type="button" 
                          onClick={() => setSelectedFeatureIds([])}
                          className="text-slate-500 hover:text-slate-600 transition-colors"
                        >
                          清空
                        </button>
                      </div>
                    </div>
                    
                    <div className="space-y-2 max-h-[45vh] overflow-y-auto pr-1">
                      {leafFeatures.map(f => {
                        const isChecked = selectedFeatureIds.includes(f.featureId);
                        const hasActor = (f.actorIds || []).length > 0;
                        const actorCount = (f.actorIds || []).length;
                        
                        return (
                          <div 
                            key={f.featureId}
                            onClick={() => {
                              setSelectedFeatureIds(prev => 
                                prev.includes(f.featureId) 
                                  ? prev.filter(id => id !== f.featureId)
                                  : [...prev, f.featureId]
                              );
                            }}
                            className={`flex items-start gap-3 p-3 rounded-2xl border cursor-pointer select-none transition-all ${isChecked ? 'bg-indigo-50/40 border-indigo-200 shadow-sm' : 'bg-white border-slate-200 hover:border-indigo-200 hover:bg-slate-50/30'}`}
                          >
                            <input 
                              type="checkbox"
                              checked={isChecked}
                              readOnly
                              className="mt-0.5 w-3.5 h-3.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                            />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-bold text-slate-700 text-xs truncate">{f.featureName}</span>
                                {hasActor ? (
                                  <span className="bg-indigo-50 border border-indigo-100 text-indigo-700 text-[10px] font-extrabold px-1.5 py-0.5 rounded-md">
                                    {actorCount} 个参与者
                                  </span>
                                ) : (
                                  <span className="bg-rose-50 border border-rose-100 text-rose-600 text-[10px] font-extrabold px-1.5 py-0.5 rounded-md">
                                    ⚠️ 未关联参与者
                                  </span>
                                )}
                              </div>
                              <p className="text-[10px] text-slate-400 mt-1 leading-normal truncate">{f.featureDescription || '无描述'}</p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </>
                );
              })()}
            </div>

            {/* Modal Footer */}
            <div className="p-6 pt-4 border-t border-slate-100 flex justify-end gap-2 bg-slate-50/30">
              <button
                onClick={() => { setIsScenarioModalOpen(false); setSelectedFeatureIds([]); }}
                className="px-4 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors shadow-sm"
              >
                取消
              </button>
              <button
                onClick={async () => {
                  if (selectedFeatureIds.length === 0) return;
                  await generateScenarios(selectedFeatureIds);
                  setIsScenarioModalOpen(false);
                  setSelectedFeatureIds([]);
                }}
                disabled={selectedFeatureIds.length === 0 || isGenerating || isLoading}
                className="px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50 flex items-center gap-1.5"
              >
                <Sparkles className="w-3.5 h-3.5 text-indigo-300" />
                开始 AI 推演场景 ({selectedFeatureIds.length})
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Manual Add Actor Modal */}
      {isAddActorModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4 select-none animate-in fade-in duration-200">
          <div className="bg-white/95 border border-slate-200 shadow-2xl max-w-md w-full flex flex-col rounded-3xl animate-in scale-in-95 duration-200 overflow-hidden">
            <div className="p-6 pb-4 border-b border-slate-100 bg-slate-50/50">
              <h3 className="font-extrabold text-sm text-slate-800">👤 手动创建参与者</h3>
              <p className="text-[10px] text-slate-500 mt-1">手动在当前工作区添加业务操作参与者，用以绑定功能节点或流程步骤。</p>
            </div>
            <div className="p-6 space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">参与者名称</label>
                <input
                  type="text"
                  value={newActorName}
                  onChange={(e) => setNewActorName(e.target.value)}
                  placeholder="例如：'仓库管理员'、'财务审核经理'"
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">职责职责描述</label>
                <textarea
                  value={newActorDesc}
                  onChange={(e) => setNewActorDesc(e.target.value)}
                  placeholder="简要说明该参与者的核心业务功能及系统操作权限范围。"
                  rows={3}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium resize-none leading-relaxed"
                />
              </div>
            </div>
            <div className="p-6 pt-4 border-t border-slate-100 flex justify-end gap-2 bg-slate-50/30">
              <button
                onClick={() => { setIsAddActorModalOpen(false); setNewActorName(''); setNewActorDesc(''); }}
                className="px-4 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors shadow-sm"
              >
                取消
              </button>
              <button
                onClick={async () => {
                  if (!newActorName.trim()) return;
                  await addActor(newActorName.trim(), newActorDesc.trim());
                  setIsAddActorModalOpen(false);
                  setNewActorName('');
                  setNewActorDesc('');
                }}
                disabled={!newActorName.trim()}
                className="px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50"
              >
                确定创建
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Manual Add Feature Modal */}
      {isAddFeatureModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4 select-none animate-in fade-in duration-200">
          <div className="bg-white/95 border border-slate-200 shadow-2xl max-w-md w-full flex flex-col rounded-3xl animate-in scale-in-95 duration-200 overflow-hidden">
            <div className="p-6 pb-4 border-b border-slate-100 bg-slate-50/50">
              <h3 className="font-extrabold text-sm text-slate-800 flex items-center gap-1.5">
                🌳 手动创建能力功能结点
              </h3>
              <p className="text-[10px] text-slate-500 mt-1">手动在当前工作区的能力树中添加功能模块或具体的叶子功能结点。</p>
            </div>
            <div className="p-6 space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">功能名称</label>
                <input
                  type="text"
                  value={newFeatureName}
                  onChange={(e) => setNewFeatureName(e.target.value)}
                  placeholder="例如：'提交审批订单'、'查询交易记录'"
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">功能说明描述</label>
                <textarea
                  value={newFeatureDesc}
                  onChange={(e) => setNewFeatureDesc(e.target.value)}
                  placeholder="简述该功能所要达到的业务效果、前置条件或涉及的数据对象。"
                  rows={3}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium resize-none leading-relaxed"
                />
              </div>
              {!isParentFixed && (
                <div className="space-y-1.5">
                  <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">父功能结点归属</label>
                  <select
                    value={newFeatureParentId === null ? 'null' : newFeatureParentId}
                    onChange={(e) => {
                      const val = e.target.value;
                      setNewFeatureParentId(val === 'null' ? null : parseInt(val, 10));
                    }}
                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium cursor-pointer"
                  >
                    <option value="null">作为一级模块结点 (根结点)</option>
                    {(() => {
                      const dbRoot = (ir?.features || []).find(f => f.parentId === null);
                      const firstLevelModules = dbRoot 
                        ? (ir?.features || []).filter(f => f.parentId === dbRoot.featureId)
                        : [];
                      return firstLevelModules.map(f => (
                        <option key={f.featureId} value={f.featureId}>
                          一级模块: {f.featureName}
                        </option>
                      ));
                    })()}
                  </select>
                </div>
              )}
            </div>
            <div className="p-6 pt-4 border-t border-slate-100 flex justify-end gap-2 bg-slate-50/30">
              <button
                onClick={() => { setIsAddFeatureModalOpen(false); setNewFeatureName(''); setNewFeatureDesc(''); setNewFeatureParentId(null); setIsParentFixed(false); }}
                className="px-4 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors shadow-sm"
              >
                取消
              </button>
              <button
                onClick={async () => {
                  if (!newFeatureName.trim()) return;
                  await addFeature(newFeatureName.trim(), newFeatureDesc.trim(), newFeatureParentId);
                  setIsAddFeatureModalOpen(false);
                  setNewFeatureName('');
                  setNewFeatureDesc('');
                  setNewFeatureParentId(null);
                  setIsParentFixed(false);
                }}
                disabled={!newFeatureName.trim()}
                className="px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50"
              >
                确定创建
              </button>
            </div>
          </div>
        </div>
      )}

      {/* NEW: Dedicated Leaf Feature Scenario & Acceptance Criteria (AC) Management Modal */}
      {managedFeatObj && (
        <div className="fixed inset-0 bg-slate-950/65 backdrop-blur-sm z-[999] flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-white border border-slate-200 shadow-2xl max-w-3xl w-full max-h-[85vh] flex flex-col rounded-3xl animate-in scale-in-95 duration-200 overflow-hidden">
            
            {/* Modal Header */}
            <div className="p-6 border-b border-slate-200/50 flex justify-between items-center bg-slate-50/50">
              <div>
                <h3 className="font-extrabold text-sm text-slate-800 flex items-center gap-1.5">
                  🎬 场景与验收标准
                </h3>
                <p className="text-[10px] text-indigo-700 mt-1 font-bold">
                  具体功能特征: <span className="bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded text-indigo-800 font-extrabold">{managedFeatObj.featureName}</span>
                </p>
              </div>
              <button 
                onClick={() => setScenarioManagerFeature(null)}
                className="w-6 h-6 rounded-full hover:bg-slate-200 flex items-center justify-center text-slate-400 hover:text-slate-600 transition-all"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              
              {/* Quick Actions Panel */}
              <div className="flex justify-between items-center bg-slate-50/80 p-3 rounded-2xl border border-slate-200/50 shrink-0">
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">该功能共有 {managedFeatObj.scenarios?.length || 0} 个成功场景</span>
                <div className="relative group">
                  <button
                    type="button"
                    onClick={() => {
                      setShowAddScenarioForm(!showAddScenarioForm);
                      setModalNewScenName('');
                      setModalNewScenContent('');
                      if (ir?.actors && ir.actors.length > 0) {
                        setModalNewScenActorId(ir.actors[0].actorId);
                      }
                    }}
                    className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-md transition-all shadow-sm"
                    aria-label={showAddScenarioForm ? '收起场景表单' : '手动新增场景'}
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                  <div className="pointer-events-none absolute left-1/2 top-0 z-20 -translate-x-1/2 -translate-y-[calc(100%+8px)] whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[10px] font-bold text-white opacity-0 shadow-md transition-opacity group-hover:opacity-100">
                    {showAddScenarioForm ? '收起场景表单' : '手动新增场景'}
                  </div>
                </div>
              </div>

              {/* Inline Add Scenario Form inside Modal */}
              {showAddScenarioForm && (
                <div className="border border-indigo-100 rounded-2xl p-4 bg-indigo-50/15 space-y-3 shadow-inner animate-in slide-in-from-top-2 duration-200">
                  <div className="text-[10px] text-indigo-700 font-extrabold tracking-wider uppercase">✨ 新增交付场景</div>
                  <div className="space-y-1">
                    <label className="text-[10px] text-slate-400 font-bold uppercase">场景名称</label>
                    <input
                      type="text"
                      value={modalNewScenName}
                      onChange={(e) => setModalNewScenName(e.target.value)}
                      placeholder="场景简称，如: '扫码录入成功并匹配'"
                      className="w-full px-3 py-2 border border-slate-200 rounded-xl text-xs font-medium outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] text-slate-400 font-bold uppercase">用户故事交互描述</label>
                    <textarea
                      value={modalNewScenContent}
                      onChange={(e) => setModalNewScenContent(e.target.value)}
                      placeholder="详细流转过程说明，如: '用户扫描产品条码，系统实时校验条码合法性，匹配相应批次信息'"
                      rows={2}
                      className="w-full px-3 py-2 border border-slate-200 rounded-xl text-xs font-medium resize-none leading-relaxed outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] text-slate-400 font-bold uppercase">执行参与者</label>
                    <select
                      value={modalNewScenActorId}
                      onChange={(e) => setModalNewScenActorId(parseInt(e.target.value, 10))}
                      className="w-full px-3 py-2 border border-slate-200 rounded-xl text-xs font-medium cursor-pointer outline-none focus:ring-1 focus:ring-indigo-500"
                    >
                      {(ir?.actors || []).map((a: any) => (
                        <option key={a.actorId} value={a.actorId}>{a.actorName}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex justify-end gap-2 pt-1.5">
                    <button
                      onClick={() => setShowAddScenarioForm(false)}
                      className="px-3 py-1.5 text-[10px] font-bold border border-slate-200 bg-white rounded-lg hover:bg-slate-50 shadow-sm"
                    >
                      取消
                    </button>
                    <button
                      onClick={async () => {
                        if (!modalNewScenName.trim()) return;
                        await addScenario(managedFeatObj.featureId, modalNewScenActorId, modalNewScenName.trim(), modalNewScenContent.trim());
                        setShowAddScenarioForm(false);
                      }}
                      disabled={!modalNewScenName.trim()}
                      className="px-3.5 py-1.5 text-[10px] font-bold bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 shadow-sm disabled:opacity-50"
                    >
                      确定添加场景
                    </button>
                  </div>
                </div>
              )}

              {/* Scenarios and AC list */}
              {(managedFeatObj.scenarios || []).length === 0 ? (
                <div className="text-center py-16 border border-dashed border-slate-200 rounded-2xl bg-slate-50/40 text-xs text-slate-500 italic leading-relaxed">
                  当前功能暂未定义任何交付场景。请在上方手动添加，或使用页面上方的 AI 特征树场景推演。
                </div>
              ) : (
                <div className="space-y-4">
                  {(managedFeatObj.scenarios || []).map((s: any) => {
                    const performer = (ir?.actors || []).find((a: any) => a.actorId === s.actorId);
                    const performerName = performer ? performer.actorName : '系统';
                    const isAddingAc = modalAddingAcForScenId === s.scenarioId;

                    return (
                      <div key={s.scenarioId} className="border border-slate-200 rounded-2xl p-4 bg-slate-50/20 shadow-sm space-y-3 relative hover:border-slate-300 transition-colors">
                        
                        {/* Scenario Header */}
                        <div className="flex justify-between items-start">
                          <div className="space-y-1">
                            <span className="font-extrabold text-xs text-slate-800 tracking-wide block">🎬 {s.scenarioName}</span>
                            <span className="inline-block text-[10px] bg-indigo-50 border border-indigo-100 text-indigo-700 font-extrabold px-1.5 py-0.2 rounded-md">
                              参与者: {performerName}
                            </span>
                          </div>
                          <button
                            onClick={async () => {
                              if (confirm('确认删除该交付成功场景以及包含的所有验收标准 (AC) 吗？')) {
                                await deleteScenario(managedFeatObj.featureId, s.scenarioId);
                              }
                            }}
                            className="p-1 text-slate-400 hover:text-rose-600 transition-colors"
                            title="删除该场景"
                          >
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                          </button>
                        </div>

                        {/* Scenario Description */}
                        <div className="text-xs text-slate-600 bg-white p-2.5 rounded-xl border border-slate-100 italic leading-relaxed">
                          "{s.scenarioContent}"
                        </div>

                        {/* Acceptance Criteria Section */}
                        <div className="space-y-2 pt-2 border-t border-slate-200/50">
                          <div className="flex justify-between items-center text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                            <span>验收标准 ({s.acceptanceCriteria?.length || 0} 项)</span>
                            <button
                              onClick={() => {
                                setModalAddingAcForScenId(isAddingAc ? null : s.scenarioId);
                                setModalNewAcContent('');
                              }}
                              className="text-[10px] text-indigo-600 hover:text-indigo-800 font-bold flex items-center gap-0.5 transition-colors"
                            >
                              {isAddingAc ? '取消添加' : '+ 添加 AC 项'}
                            </button>
                          </div>

                          {/* Add AC Input form */}
                          {isAddingAc && (
                            <div className="flex gap-2 items-center mt-1 animate-in slide-in-from-top-1 duration-150">
                              <input
                                type="text"
                                value={modalNewAcContent}
                                onChange={(e) => setModalNewAcContent(e.target.value)}
                                placeholder="输入具体可校验的系统状态, 如: '提示操作成功并更新主状态'"
                                className="flex-1 px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs outline-none focus:ring-1 focus:ring-indigo-500 font-medium"
                              />
                              <button
                                onClick={async () => {
                                  if (!modalNewAcContent.trim()) return;
                                  await addAcceptanceCriterion(managedFeatObj.featureId, s.scenarioId, modalNewAcContent.trim());
                                  setModalAddingAcForScenId(null);
                                  setModalNewAcContent('');
                                }}
                                disabled={!modalNewAcContent.trim()}
                                className="px-3 py-1.5 bg-slate-900 text-white text-[10px] font-bold rounded-lg hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50 shrink-0"
                              >
                                添加
                              </button>
                            </div>
                          )}

                          {/* AC Items list */}
                          {(s.acceptanceCriteria || []).length === 0 ? (
                            <div className="text-[10px] text-slate-500 italic bg-white/50 p-2 rounded-xl border border-dashed border-slate-200/50 leading-relaxed">
                              暂无交付验收细节。请在上方输入添加，或使用特征树上方的 AI AC 推理生成。
                            </div>
                          ) : (
                            <div className="space-y-1.5">
                              {(s.acceptanceCriteria || []).map((ac: any) => (
                                <div key={ac.criterionId} className="flex justify-between items-start gap-2 bg-white p-2 rounded-xl border border-slate-100 group/ac relative">
                                  <div className="flex-1 flex gap-2 items-start text-xs text-slate-600 font-medium leading-relaxed">
                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0 mt-1.5"></span>
                                    <span>{ac.criterionContent}</span>
                                  </div>
                                  <button
                                    onClick={async () => {
                                      if (confirm('确认删除此条验收标准 (AC) 吗？')) {
                                        await deleteAcceptanceCriterion(managedFeatObj.featureId, s.scenarioId, ac.criterionId);
                                      }
                                    }}
                                    className="p-0.5 text-slate-400 hover:text-rose-600 opacity-0 group-hover/ac:opacity-100 transition-all shrink-0 mt-0.5"
                                    title="删除验收标准"
                                  >
                                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                  </button>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-6 pt-4 border-t border-slate-200/50 flex justify-end bg-slate-50/50">
              <button
                onClick={() => setScenarioManagerFeature(null)}
                className="px-5 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-xl shadow-sm transition-all"
              >
                确定并关闭
              </button>
            </div>
          </div>
        </div>
      )}

      <DraftPreviewModal
        draft={activeDraft}
        draftType={activeDraftType}
        isWorking={isGenerating || isLoading}
        onDiscard={() => {
          if (activeDraftType === 'repair') {
            const dId = activeDraft?.draftId || activeDraft?.draft_id;
            if (dId) discardRepairDraft(dId);
          } else {
            discardDraft();
          }
        }}
        onRegenerate={(feedback) => {
          if (activeDraftType === 'repair') {
            const dId = activeDraft?.draftId || activeDraft?.draft_id;
            if (dId) regenerateRepairDraft(dId);
            return;
          }
          if (activeDraftType === 'actor') return regenerateActors(feedback);
          if (activeDraftType === 'feature') return regenerateFeatures(feedback);
          if (activeDraftType === 'scenario') return regenerateScenarios(feedback);
          if (activeDraftType === 'ac') return regenerateAcceptanceCriteria(feedback);
          return undefined;
        }}
        onConfirm={async () => {
          if (activeDraftType === 'repair') {
            const dId = activeDraft?.draftId || activeDraft?.draft_id;
            if (dId) await confirmRepairDraft(dId);
            return;
          }
          if (activeDraftType === 'actor') return confirmActors();
          if (activeDraftType === 'feature') return confirmFeatures();
          if (activeDraftType === 'scenario') return confirmScenarios(true);
          if (activeDraftType === 'ac') return confirmAcceptanceCriteria();
          return undefined;
        }}
        confirmLabel={activeDraftType === 'scenario' ? '确认并生成验收标准' : '确认采纳'}
      />

      <ConfirmTransitionModal
        isOpen={isTransitionModalOpen}
        onClose={() => setIsTransitionModalOpen(false)}
        stage="what"
        isWorking={isLoading}
        onAIDiagnose={async () => {
          setIsTransitionModalOpen(false);
          await runDiagnosis();
        }}
        onForceUnlock={async () => {
          setIsTransitionModalOpen(false);
          await unlockStageGate('what');
          navigate(buildProjectRoute(ir?.projectId, '/flow'));
        }}
      />

      <RightObjectPanel />
    </div>
  );
}
