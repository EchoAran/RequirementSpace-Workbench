import { useState, type MouseEvent, useEffect, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ChevronDown, ChevronRight, Sparkles, Check, X, RefreshCw, Plus, Trash2 } from 'lucide-react';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { DraftPreviewModal } from '@/components/shared/DraftPreviewModal';
import { GherkinVisualRenderer, GherkinVisualEditor } from '@/components/shared/GherkinVisualizer';
import { ChoiceGroupPreviewModal } from '@/components/shared/ChoiceGroupPreviewModal';
import { StageGuidanceBanner } from '@/components/shared/StageGuidanceBanner';
import { ConfirmTransitionModal } from '@/components/shared/ConfirmTransitionModal';
import { AIAddObjectDialog, type AIAddTargetType } from '@/components/shared/AIAddObjectDialog';
import { 
  useWorkspaceStore, 
  selectActors, 
} from '@/store/useWorkspaceStore';
import { findingTargetIds } from '@/core/findingPresentation';
import {
  buildProjectRoute,
  getStageIssues,
  getChildCapabilities,
  getRootCapabilities,
} from '@/core/selectors';
import type { ActorNode, FeatureNode } from '@/core/schema';
import { useTranslation } from 'react-i18next';

interface AcInlineEditorProps {
  initialContent: string;
  onSave: (newContent: string) => void | Promise<void>;
  onCancel: () => void;
}

function AcInlineEditor({ initialContent, onSave, onCancel }: AcInlineEditorProps) {
  const { t } = useTranslation();
  const [content, setContent] = useState(initialContent);

  return (
    <div className="border border-indigo-100 rounded-2xl p-4 bg-indigo-50/5 space-y-4 shadow-sm animate-in fade-in duration-200">
      <div className="bg-slate-100/80 p-1 rounded-xl flex gap-1 border border-slate-200/50 shadow-inner max-w-[10rem] select-none">
        <button
          type="button"
          className="grow text-[10px] font-extrabold py-1.5 px-2.5 rounded-lg transition-all flex items-center justify-center bg-white text-indigo-600 shadow-sm border border-slate-200/20"
        >
          {t('what.structuredEdit')}
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-100/80 p-3 shadow-inner">
        <GherkinVisualEditor
          initialText={content}
          onChange={setContent}
        />
      </div>

      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 text-[10px] font-bold border border-slate-200 bg-white rounded-lg hover:bg-slate-50 transition-colors"
        >
          {t('scope.modal.cancel')}
        </button>
        <button
          type="button"
          onClick={async () => {
            await onSave(content);
          }}
          className="px-3.5 py-1.5 bg-indigo-600 text-white text-[10px] font-bold rounded-lg hover:bg-indigo-700 shadow-sm"
        >
          {t('what.confirmSave')}
        </button>
      </div>
    </div>
  );
}

interface UserStoryParsed {
  role: string;
  action: string;
  benefit: string;
}

function parseUserStory(content: string): UserStoryParsed {
  if (!content) {
    return { role: '', action: '', benefit: '' };
  }

  const cnRegex = /作为\s*([^，,]+)[，,]\s*(?:我想要|我想|要)\s*([^，,]+)[，,]\s*(?:以便于|以便|为了|以便能够)\s*(.+)/i;
  const enRegex = /As\s+a\s+([^,]+),\s*I\s+want\s+to\s+([^,]+),\s*(?:So\s+that|so\s+that)\s+(.+)/i;

  const cnMatch = content.match(cnRegex);
  if (cnMatch) {
    return {
      role: cnMatch[1].trim(),
      action: cnMatch[2].trim(),
      benefit: cnMatch[3].trim(),
    };
  }

  const enMatch = content.match(enRegex);
  if (enMatch) {
    return {
      role: enMatch[1].trim(),
      action: enMatch[2].trim(),
      benefit: enMatch[3].trim(),
    };
  }

  return {
    role: '',
    action: '',
    benefit: content
  };
}

interface UserStoryRendererProps {
  content: string;
  performerName?: string;
}

function UserStoryRenderer({ content, performerName }: UserStoryRendererProps) {
  const { t } = useTranslation();
  const parsed = parseUserStory(content);

  if (!parsed.role && !parsed.action) {
    return (
      <div className="text-xs text-slate-600 bg-white p-3 py-2.5 rounded-xl border border-slate-100 italic leading-relaxed">
        "{content}"
      </div>
    );
  }

  return (
    <div className="space-y-2 bg-slate-50/50 p-3 rounded-xl border border-slate-200/60 transition-all hover:border-slate-300">
      <div className="flex flex-wrap items-center gap-1.5 leading-relaxed text-xs text-slate-600 font-medium select-text">
        <span className="text-[10px] text-slate-400 font-bold tracking-wider uppercase">{t('what.userStory.as')}</span>
        <span className="bg-indigo-50 border border-indigo-150 text-indigo-700 px-2 py-0.5 rounded-lg font-extrabold text-[10px] shadow-sm">
          {performerName || parsed.role}
        </span>
        <span className="text-[10px] text-slate-400 font-bold tracking-wider uppercase">{t('what.userStory.want')}</span>
        <span className="text-slate-800 font-extrabold border-b border-dashed border-slate-300 pb-0.5">
          {parsed.action}
        </span>
        <span className="text-[10px] text-slate-400 font-bold tracking-wider uppercase">{t('what.userStory.comma')}</span>
      </div>
      
      <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-sm">
        <div className="text-[9px] text-slate-400 font-bold tracking-wider uppercase mb-0.5">{t('what.userStory.soThat')}</div>
        <p className="text-xs text-slate-700 font-semibold leading-relaxed select-text">
          {parsed.benefit}
        </p>
      </div>
    </div>
  );
}

interface UserStoryEditorProps {
  initialContent: string;
  actors: { actorId: number; actorName: string; actorDescription?: string }[];
  onChange: (newContent: string) => void;
}

function UserStoryEditor({ initialContent, actors, onChange }: UserStoryEditorProps) {
  const { t } = useTranslation();
  const parsed = parseUserStory(initialContent);
  const [role, setRole] = useState(parsed.role || (actors[0]?.actorName || ''));
  const [action, setAction] = useState(parsed.action || '');
  const [benefit, setBenefit] = useState(parsed.benefit || initialContent);

  useEffect(() => {
    if (actors.length === 0) {
      setRole('');
      return;
    }
    if (!actors.some((actor) => actor.actorName === role)) {
      setRole(actors[0]?.actorName || '');
    }
  }, [actors, role]);

  useEffect(() => {
    if (role && action && benefit) {
      onChange(`${t('what.userStory.as')} ${role}${t('what.userStory.want')} ${action}${t('what.userStory.soThat')} ${benefit}`);
    } else {
      onChange(benefit);
    }
  }, [role, action, benefit, onChange]);

  return (
    <div className="space-y-3 bg-slate-50/40 p-3.5 border border-slate-200/85 rounded-xl shadow-inner select-none">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600 font-medium">
        <span className="text-[10px] text-slate-400 font-bold tracking-wider uppercase">{t('what.userStory.as')}</span>
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          disabled={actors.length === 0}
          className="bg-white border border-slate-200 hover:border-slate-300 rounded-lg px-2 py-0.5 text-xs font-extrabold text-indigo-700 cursor-pointer focus:ring-1 focus:ring-indigo-500 focus:outline-none transition-all shadow-sm disabled:bg-slate-50 disabled:text-slate-400 disabled:cursor-not-allowed"
        >
          {actors.length === 0 ? (
            <option value="">{t('what.userStory.noActorOption')}</option>
          ) : (
            actors.map((a) => (
              <option key={a.actorId} value={a.actorName}>
                {a.actorName}
              </option>
            ))
          )}
        </select>

        <span className="text-[10px] text-slate-400 font-bold tracking-wider uppercase">{t('what.userStory.want')}</span>
        <input
          type="text"
          value={action}
          onChange={(e) => setAction(e.target.value)}
          placeholder="{t('what.userStory.actionPlaceholder')}"
          className="bg-white border border-slate-200 hover:border-slate-300 rounded-lg px-2.5 py-0.5 text-xs font-bold text-slate-800 focus:ring-1 focus:ring-slate-900 focus:outline-none w-44 transition-all shadow-sm"
        />
        <span className="text-[10px] text-slate-400 font-bold tracking-wider uppercase">{t('what.userStory.comma')}</span>
      </div>

      <div className="space-y-1">
        <label className="text-[10px] text-slate-400 font-bold tracking-wider uppercase block">{t('what.userStory.soThat')}</label>
        <textarea
          value={benefit}
          onChange={(e) => setBenefit(e.target.value)}
          rows={2}
          placeholder="{t('what.userStory.benefitPlaceholder')}"
          className="w-full bg-white border border-slate-200 hover:border-slate-300 rounded-xl p-2.5 text-xs text-slate-700 font-semibold leading-relaxed focus:ring-1 focus:ring-slate-900 focus:outline-none resize-none transition-all shadow-sm"
        />
      </div>
    </div>
  );
}

interface InteractiveStatusBadgeProps {
  nodeId: number;
  nodeKind: 'scenario' | 'acceptance_criterion';
  status: 'confirmed' | 'needs_confirmation' | 'ai_assumption';
  setNodeStatus: (id: string, kind: string, status: any) => Promise<void>;
}

function InteractiveStatusBadge({ nodeId, nodeKind, status, setNodeStatus }: InteractiveStatusBadgeProps) {
  const { t } = useTranslation();
  const [val, setVal] = useState(status);

  useEffect(() => {
    setVal(status);
  }, [status]);

  const handleChange = async (newStatus: any) => {
    setVal(newStatus);
    await setNodeStatus(nodeId.toString(), nodeKind, newStatus);
  };

  const statusStyles = {
    confirmed: 'bg-emerald-50 border-emerald-250 text-emerald-800',
    needs_confirmation: 'bg-amber-50 border-amber-250 text-amber-800',
    ai_assumption: 'bg-indigo-50 border-indigo-250 text-indigo-800',
  };

  const currentStyle = statusStyles[val] || 'bg-slate-50 border-slate-200 text-slate-700';

  return (
    <select
      value={val}
      onClick={(e) => e.stopPropagation()}
      onChange={(e) => handleChange(e.target.value as any)}
      className={`border px-2 py-0.5 rounded-lg text-[9px] font-extrabold uppercase cursor-pointer focus:outline-none focus:ring-1 focus:ring-slate-900 transition-all shadow-sm ${currentStyle}`}
    >
      <option value="confirmed" className="bg-white text-emerald-800 font-extrabold">{t('what.status.confirmed')}</option>
      <option value="needs_confirmation" className="bg-white text-amber-800 font-extrabold">{t('what.status.needs_confirmation')}</option>
      <option value="ai_assumption" className="bg-white text-indigo-800 font-extrabold">{t('what.status.ai_assumption')}</option>
    </select>
  );
}

export function WhatToDo() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { 
    setSelectedObject, highlightTarget, selectedObject, ir, setHighlightTarget,
    pendingManualAction, setPendingManualAction,
    generateActors, regenerateActors, confirmActors,
    generateFeatures, regenerateFeatures, confirmFeatures,
    generateScenarios, regenerateScenarios, confirmScenarios,
    generateAcceptanceCriteria, regenerateAcceptanceCriteria, confirmAcceptanceCriteria,
    discardDraft, activeDraft, activeDraftType, isGenerating, isLoading, isDiagnosing,
    addActor, addFeature,
    activeChoiceGroup, isGeneratingChoices, choiceGroupGenerationProgress,
    acceptChoice, discardChoiceGroup, deferOnboardingChoiceGroup,
    addScenario, deleteScenario, addAcceptanceCriterion, deleteAcceptanceCriterion,
    updateScenario, updateAcceptanceCriterion,
    setNodeStatus,
    deleteActor, deleteFeature, expandSlot, runDiagnosis, triggerGateCheck, requestStageTransition,
    confirmRepairDraft,
    discardRepairDraft,
    regenerateRepairDraft,
    executeFindingIssueResolution, updateIssueAttributes, clearPerceptionSlot
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
  const [aiDialogTarget, setAiDialogTarget] = useState<{ targetType: AIAddTargetType; anchor?: Record<string, any> } | null>(null);
  const isAIDialogOpen = aiDialogTarget !== null;

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

  // Inline edit state inside Scenario Manager Modal
  const [editingScenarioId, setEditingScenarioId] = useState<number | null>(null);
  const [editingScenarioName, setEditingScenarioName] = useState('');
  const [editingScenarioContent, setEditingScenarioContent] = useState('');
  const [editingScenarioActorId, setEditingScenarioActorId] = useState<number>(0);
  const [editingAcId, setEditingAcId] = useState<number | null>(null);
  const [editingAcContent, setEditingAcContent] = useState('');
  const [collapsedScenarioIds, setCollapsedScenarioIds] = useState<Record<number, boolean>>({});
  const [collapsedAcScenarioIds, setCollapsedAcScenarioIds] = useState<Record<number, boolean>>({});

  const toggleCap = (e: MouseEvent, id: string) => {
    e.stopPropagation();
    setExpandedCaps(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const leafFeatures = (ir?.features || []).filter(f => {
    const isParent = (ir?.features || []).some(child => child.parentId === f.featureId);
    return f.parentId !== null && !isParent;
  });
  const hasScenarios = (ir?.features || []).some(feature => (feature.scenarios || []).length > 0);

  const managedFeatObj = ir?.features?.find(f => f.featureId === scenarioManagerFeature?.featureId);
  const managedFeatureActors = useMemo(
    () =>
      (ir?.actors || []).filter((actor: any) =>
        (managedFeatObj?.actorIds || []).includes(actor.actorId)
      ),
    [ir?.actors, managedFeatObj]
  );


  const executeManualAction = (kind: string, targetId?: number, focusMode?: string) => {
    if (kind === 'missing_actor' || kind === 'what_onboarding') {
      setIsAddActorModalOpen(true);
    } else if (kind === 'missing_feature') {
      setIsAddFeatureModalOpen(true);
    } else if (kind === 'stage_gate_transition_confirm') {
      setIsTransitionModalOpen(true);
    } else if (targetId) {
      const featIdStr = targetId.toString();
      const featObj = ir?.features?.find((f: FeatureNode) => f.featureId === targetId);
      if (featObj) {
        // Expand parent capability
        const parentId = featObj.parentId;
        if (parentId !== null && parentId !== undefined) {
          setExpandedCaps((prev) => ({ ...prev, [parentId]: true }));
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
          const childNode = ir?.capabilitiesCompatible?.find((c: any) => c.featureId === targetId || c.id === featIdStr);
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
    const targetId = findingTargetIds(issue)[0];
    if (targetId) {
      setHighlightTarget(targetId);
    }
  };

  const openIssueFlow = async (issue: any) => {
    const slotId = await executeFindingIssueResolution(issue.findingId);
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

  // 从 URL 参数解析高亮目标（来自概览页假设账本点击跳转）
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const highlight = params.get('highlight');
    if (!highlight) return;
    const [kind, ...idParts] = highlight.split('-');
    const id = parseInt(idParts.join('-'), 10);
    if (isNaN(id)) return;
    // 清除 URL 参数，防止刷新后重复高亮
    navigate(location.pathname, { replace: true });

    setTimeout(() => {
      // 尝试查找对应的 DOM 元素并滚动到可视区域
      const el = document.getElementById(`${kind}-${id}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('ring-2', 'ring-indigo-400', 'ring-offset-2', 'rounded-xl');
        setTimeout(() => el.classList.remove('ring-2', 'ring-indigo-400', 'ring-offset-2', 'rounded-xl'), 3000);
      }
      // 根据节点类型选中对应对象
      if (kind === 'actor') {
        const actor = actors.find((a: any) => a.actorId === id);
        if (actor) setSelectedObject(actor);
      } else if (kind === 'feature') {
        setHighlightTarget(id.toString());
      } else if (kind === 'scenario') {
        const feat = ir?.features?.find((f: any) => f.scenarios?.some((s: any) => s.scenarioId === id));
        if (feat) setHighlightTarget(feat.featureId.toString());
      } else if (kind === 'acceptance_criterion') {
        const feat = ir?.features?.find((f: any) =>
          f.scenarios?.some((s: any) => s.acceptanceCriteria?.some((a: any) => a.criterionId === id))
        );
        if (feat) setHighlightTarget(feat.featureId.toString());
      }
    }, 200);
  }, [location.search]);

  // Reset scenario manager UI when switching to another feature
  useEffect(() => {
    if (scenarioManagerFeature) {
      setModalNewScenActorId(managedFeatureActors[0]?.actorId || 0);
    }
    setShowAddScenarioForm(false);
    setModalAddingAcForScenId(null);
    setCollapsedScenarioIds({});
    setCollapsedAcScenarioIds({});
  }, [scenarioManagerFeature?.featureId]);

  // Keep selected actor valid when the feature's bound actors change
  useEffect(() => {
    if (!scenarioManagerFeature) return;
    const nextActorId = managedFeatureActors[0]?.actorId || 0;
    setModalNewScenActorId((prev) => (
      managedFeatureActors.some((actor: any) => actor.actorId === prev) ? prev : nextActorId
    ));
  }, [scenarioManagerFeature?.featureId, managedFeatureActors]);

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
              <StageGuidanceBanner stage="what" />
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
                        <h3 className="text-base font-bold text-slate-900">{t('what.ai.actorTitle')}</h3>
                        <p className="text-xs text-slate-500 mt-0.5">{t('what.ai.actorDesc')}</p>
                      </div>
                      <div className="flex gap-2 items-center max-w-md">
                        <input
                          type="text"
                          value={actorFeedback}
                          onChange={(e) => setActorFeedback(e.target.value)}
                          placeholder="{t('what.actors.descPlaceholder')}"
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
                          {t('what.actors.regenerateBtn')}
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
                      {t('onboarding.kbAdoptButton')}
                    </button>
                    <button
                      onClick={discardDraft}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                    >
                      <X className="w-3.5 h-3.5" />
                      {t('scope.modal.discard')}
                    </button>
                  </div>
                </div>

                {/* Actor preview list */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2 border-t border-slate-200/60">
                  {activeDraft.actors?.map((act: any, idx: number) => (
                    <div key={idx} className="bg-white/80 p-4 rounded-xl border border-slate-200/50">
          <span className="font-bold text-xs text-slate-800">{act.actor_name}</span>
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
                        <h3 className="text-base font-bold text-slate-900">{t('what.ai.featureTitle')}</h3>
                        <p className="text-xs text-slate-500 mt-0.5">{t('what.ai.featureDesc')}</p>
                      </div>
                      <div className="flex gap-2 items-center max-w-md">
                        <input
                          type="text"
                          value={featureFeedback}
                          onChange={(e) => setFeatureFeedback(e.target.value)}
                          placeholder="{t('what.ai.featurePlaceholder')}"
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
                          {t('what.actors.regenerateBtn')}
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
                      {t('onboarding.kbAdoptButton')}
                    </button>
                    <button
                      onClick={discardDraft}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                    >
                      <X className="w-3.5 h-3.5" />
                      {t('scope.modal.discard')}
                    </button>
                  </div>
                </div>

                {/* Feature preview tree */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-200/60">
                  {activeDraft.features?.map((feat: any, idx: number) => (
                    <div key={idx} className="bg-white/80 p-4 rounded-xl border border-slate-200/50">
          <span className="font-bold text-xs text-slate-800">{t('what.ai.featureModule', { name: feat.feature_name })}</span>
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
                        <h3 className="text-base font-bold text-slate-900">{t('what.ai.scenarioTitle')}</h3>
                        <p className="text-xs text-slate-500 mt-0.5">{t('what.ai.scenarioDesc')}</p>
                      </div>
                      <div className="flex gap-2 items-center max-w-md">
                        <input
                          type="text"
                          value={scenarioFeedback}
                          onChange={(e) => setScenarioFeedback(e.target.value)}
                          placeholder="{t('what.ai.scenarioPlaceholder')}"
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
                          {t('what.actors.regenerateBtn')}
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
                      {t('what.scenarios.confirmAcAdopt')}
                    </button>
                    <button
                      onClick={discardDraft}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                    >
                      <X className="w-3.5 h-3.5" />
                      {t('scope.modal.discard')}
                    </button>
                  </div>
                </div>

                {/* Scenario preview list */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-200/60">
                  {activeDraft.scenarios?.map((sc: any, idx: number) => (
                    <div key={idx} className="bg-white/80 p-4 rounded-xl border border-slate-200/50 flex flex-col justify-between">
                      <div>
          <span className="font-bold text-xs text-slate-800 block">{sc.scenario_name}</span>
                        <p className="text-xs text-slate-600 bg-slate-50 p-2 rounded border border-slate-100/50 mt-1.5 italic">
                          "{sc.scenario_content}"
                        </p>
                      </div>
                      <div className="mt-3 flex items-center justify-between text-[10px] text-indigo-600 font-bold uppercase">
                        <span>{t('what.ai.featureId', { id: sc.feature_id })}</span>
                        <span>{t('what.ai.actorId', { id: sc.actor_id })}</span>
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
                        <h3 className="text-base font-bold text-slate-900">{t('what.ai.acTitle')}</h3>
                        <p className="text-xs text-slate-500 mt-0.5">{t('what.ai.acDesc')}</p>
                      </div>
                      <div className="flex gap-2 items-center max-w-md">
                        <input
                          type="text"
                          value={acFeedback}
                          onChange={(e) => setAcFeedback(e.target.value)}
                          placeholder="{t('what.ai.acPlaceholder')}"
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
                          {t('what.actors.regenerateBtn')}
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
                      {t('onboarding.kbAdoptButton')}
                    </button>
                    <button
                      onClick={discardDraft}
                      disabled={isGenerating || isLoading}
                      className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                    >
                      <X className="w-3.5 h-3.5" />
                      {t('scope.modal.discard')}
                    </button>
                  </div>
                </div>

                {/* AC preview list */}
                <div className="pt-4 border-t border-slate-200/60 space-y-3 col-span-12">
                  {activeDraft.acceptance_criteria?.map((ac: any, idx: number) => (
                    <GherkinVisualRenderer
                      key={idx}
                      text={ac.criterion_content || ''}
                      title={`{t('what.ai.acTitlePrefix', { index: idx + 1 })}`}
                      badge="{t('what.ai.acBadge')}"
                      rightBadges={[
                        <span key="scen" className="font-mono">{t('what.ai.acScenarioId', { id: ac.scenario_id })}</span>
                      ]}
                    />
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
                    {t('what.actors.title')}
                    <button
                      onClick={() => setIsAddActorModalOpen(true)}
                      className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-md transition-all shadow-sm"
                      title={t('what.actors.manualBtn')}
                    >
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => setAiDialogTarget({ targetType: 'actor' })}
                      className="p-1 text-slate-400 hover:text-amber-600 hover:bg-amber-50 border border-transparent hover:border-amber-100 rounded-md transition-all shadow-sm"
                      title={t('what.actors.aiChatBtn')}
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                    </button>
                  </h3>
                  <button
                    onClick={() => void generateActors()}
                    disabled={isGenerating || isLoading}
                    className="flex items-center gap-1.5 text-[10px] bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold px-3 py-1.5 rounded-xl border border-indigo-100/80 transition-colors shadow-sm disabled:opacity-50"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
                    {actors.length > 0 ? t('what.actors.regenerateBtn') : t('what.actors.generateBtn')}
                  </button>
                </div>
                {actors.length === 0 ? (
                  <div className="text-center py-10 border border-dashed border-slate-100 rounded-xl text-xs text-slate-500 italic">
                    {t('what.actors.emptyText')}
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {actors.map((actor: ActorNode) => {
                      const actorTitle = actor.title || actor.actorName;
                      const actorStatus = actor.status || 'needs_confirmation';

                      return (
                      <div
                        key={actor.id}
                        id={`actor-${actor.actorId}`}
                        onClick={() => setSelectedObject(actor)}
                        className={`bg-white rounded-xl p-4 border transition-all cursor-pointer flex flex-col gap-3 ${selectedObject?.id === actor.id ? 'ring-2 ring-indigo-500 border-transparent shadow-md' : 'border-slate-200 hover:border-indigo-300 hover:shadow-sm shadow-inner bg-slate-50/20'}`}
                      >
                        <div className="flex justify-between items-start">
                          <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600 font-bold border border-indigo-100">
                              {actorTitle.charAt(0)}
                            </div>
                            <div>
                              <h4 className="font-bold text-slate-800 text-sm tracking-wide">{actorTitle}</h4>
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <button
                              onClick={async (e) => {
                                e.stopPropagation();
                                if (window.confirm(t('what.actors.deleteConfirm', { title: actorTitle }))) {
                                  await deleteActor(actor.actorId);
                                  if (selectedObject?.actorId === actor.actorId) {
                                    setSelectedObject(null);
                                  }
                                }
                              }}
                              className="p-1 hover:bg-rose-50 border border-transparent hover:border-rose-100 rounded-md text-slate-400 hover:text-rose-600 transition-all flex items-center justify-center animate-none shadow-sm"
                              title={t('what.actors.deleteBtn')}
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                            <StatusBadge status={actorStatus} className="scale-90 origin-right" />
                          </div>
                        </div>
                        <div className="text-xs text-slate-600 line-clamp-2 leading-relaxed">
                          {actor.description || t('what.actors.noDesc')}
                        </div>
                      </div>
                    )})}
                  </div>
                )}
              </section>

              {/* Tree Section */}
              <section className="flex flex-col">
                <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                  <div className="flex justify-between items-center px-1 mb-4 pb-3 border-b border-slate-100">
                    <h3 className="text-xs font-bold text-slate-800 uppercase tracking-widest flex items-center gap-2">
                      {t('what.features.title')}
                      <button
                        onClick={() => {
                          setNewFeatureParentId(null);
                          setIsParentFixed(false);
                          setIsAddFeatureModalOpen(true);
                        }}
                        className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-md transition-all shadow-sm"
                        title={t('what.features.manualBtn')}
                      >
                        <Plus className="w-3.5 h-3.5" />
                      </button>
                    </h3>
                    <div className="flex gap-2">
                      <button
                        onClick={() => void generateFeatures()}
                        disabled={isGenerating || isLoading}
                        className="flex items-center gap-1.5 text-[10px] bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold px-3 py-1.5 rounded-xl border border-indigo-100/80 transition-colors shadow-sm disabled:opacity-50"
                      >
                        <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
                        {rootCapabilities.length > 0 ? t('what.features.regenerateBtn') : t('what.features.generateBtn')}
                      </button>
                      <button
                        onClick={() => setIsScenarioModalOpen(true)}
                        disabled={isGenerating || isLoading}
                        className="flex items-center gap-1.5 text-[10px] bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold px-3 py-1.5 rounded-xl border border-indigo-100/80 transition-colors shadow-sm disabled:opacity-50"
                        title={t('what.features.scenarioGenerateBtn')}
                      >
                        <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
                        {hasScenarios ? t('what.features.scenarioRegenerateBtn') : t('what.features.scenarioGenerateBtn')}
                      </button>
                    </div>
                  </div>
                  
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
                        {ir?.projectName || t('what.features.defaultRootName')}
                      </h4>
                      <p className="text-xs text-slate-500 mt-1.5 max-w-4xl font-medium">{ir?.projectDescription || t('what.features.defaultRootDesc')}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setNewFeatureParentId(null);
                          setIsParentFixed(true);
                          setIsAddFeatureModalOpen(true);
                        }}
                        className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-md transition-all shadow-sm"
                        title={t('what.features.addRootBtn')}
                      >
                        <Plus className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setAiDialogTarget({ targetType: 'feature_branch', anchor: { parent_feature_id: null } });
                        }}
                        className="p-1 text-slate-400 hover:text-amber-600 hover:bg-amber-50 border border-transparent hover:border-amber-100 rounded-md transition-all shadow-sm"
                        title={t('what.features.aiChatBtn')}
                      >
                        <Sparkles className="w-3.5 h-3.5" />
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
                                  {t('what.features.moduleLabel', { title: cap.title })}
                                </h4>
                              </div>
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    if (window.confirm(t('what.features.deleteConfirm', { title: cap.title }))) {
                                      await deleteFeature(cap.featureId);
                                      if (selectedObject?.id === cap.id || selectedObject?.featureId === cap.featureId) {
                                        setSelectedObject(null);
                                      }
                                    }
                                  }}
                                  className="p-1 hover:bg-rose-50 border border-transparent hover:border-rose-100 rounded-md text-slate-400 hover:text-rose-600 transition-all flex items-center justify-center animate-none shadow-sm"
                                  title={t('what.features.deleteBtn')}
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
                                  className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-md transition-all shadow-sm"
                                  title={t('what.features.addSubBtn')}
                                >
                                  <Plus className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setAiDialogTarget({ targetType: 'feature_leaf', anchor: { parent_feature_id: cap.featureId } });
                                  }}
                                  className="p-1 text-slate-400 hover:text-amber-600 hover:bg-amber-50 border border-transparent hover:border-amber-100 rounded-md transition-all shadow-sm"
                                  title={t('what.features.aiChatSubBtn')}
                                >
                                  <Sparkles className="w-3.5 h-3.5" />
                                </button>
                                <StatusBadge status={cap.status} />
                              </div>
                            </div>
                            
                            <p className="text-xs text-slate-500 ml-6 leading-relaxed mb-2">
                              {cap.description || t('what.features.noDesc')}
                            </p>
                            
                            <div className="flex flex-wrap gap-2 text-[10px] font-medium ml-6">
                              <span className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded border border-slate-200">
                                {t('what.features.childrenCount', { count: children.length })}
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
                                        {t('what.features.leafLabel', { title: child.title })}
                                      </h5>
                                      <div className="flex items-center gap-1.5">
                                        <button
                                          onClick={async (e) => {
                                            e.stopPropagation();
                                            if (window.confirm(t('what.features.deleteLeafConfirm', { title: child.title }))) {
                                              await deleteFeature(child.featureId);
                                              if (selectedObject?.id === child.id || selectedObject?.featureId === child.featureId) {
                                                setSelectedObject(null);
                                              }
                                            }
                                          }}
                                          className="p-1 hover:bg-rose-50 border border-transparent hover:border-rose-100 rounded-md text-slate-400 hover:text-rose-600 transition-all flex items-center justify-center shadow-sm"
                                          title={t('what.features.deleteLeafBtn')}
                                        >
                                          <Trash2 className="w-3 h-3" />
                                        </button>
                                        <StatusBadge status={child.status} className="scale-75 origin-right ml-[-8px]" />
                                      </div>
                                    </div>
                                    <div className="text-xs text-slate-500 line-clamp-2 ml-4 leading-relaxed">
                                      {child.description || t('what.features.noLeafDesc')}
                                    </div>

                                    {/* Leaf capability rich metadata badges + interactive Modal trigger button */}
                                    <div className="flex flex-wrap items-center justify-between ml-4 mt-3 pt-2.5 border-t border-slate-100/60 gap-3">
                                      <div className="flex flex-wrap gap-1.5 text-[10px] font-bold">
                                        <span className="bg-indigo-50 border border-indigo-100 text-indigo-700 px-2 py-0.5 rounded-md shadow-sm">
                                          {t('what.features.scenariosCount', { count: capScenarios.length })}
                                        </span>
                                        <span className="bg-purple-50 border border-purple-100 text-purple-700 px-2 py-0.5 rounded-md shadow-sm">
                                          {t('what.features.acCount', { count: capAcCount })}
                                        </span>
                                        {capActors.length > 0 ? (
                                          <span 
                                            className="bg-blue-50 border border-blue-200 text-blue-700 px-2 py-0.5 rounded-md shadow-sm transition-all"
                                            title={t('what.features.boundActorsLabel', { names: boundActors.map((a: any) => a.actorName).join(', ') })}
                                          >
          {t('what.features.boundActorsCount', { count: capActors.length, names: boundActors.map((a: any) => a.actorName).join(', ') })}
                                          </span>
                                        ) : (
                                          <span className="bg-rose-50 border border-rose-200 text-rose-600 px-2 py-0.5 rounded-md shadow-sm transition-all font-bold">
          {t('what.features.unboundActors')}
                                          </span>
                                        )}
                                      </div>

                                      {capScenarios.length > 0 ? (
                                        <button
                                          type="button"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            setScenarioManagerFeature(child);
                                          }}
                                          className="text-[10px] bg-slate-900 hover:bg-indigo-600 text-white font-bold px-2.5 py-1 rounded-lg transition-colors shadow-sm flex items-center gap-1 shrink-0"
                                        >
        {t('what.scenarios.title')}
                                        </button>
                                      ) : (
                                        <button
                                          type="button"
                                          disabled={isGenerating || isLoading}
                                          onClick={async (e) => {
                                            e.stopPropagation();
                                            await generateScenarios([child.featureId]);
                                          }}
                                          className="text-[10px] bg-indigo-600 hover:bg-indigo-700 text-white font-bold px-2.5 py-1 rounded-lg transition-colors shadow-sm flex items-center gap-1.5 shrink-0 disabled:opacity-50"
                                        >
                                          {isGenerating ? (
                                            <RefreshCw className="w-3 h-3 animate-spin text-indigo-200" />
                                          ) : (
                                            <Sparkles className="w-3 h-3 text-indigo-200" />
                                          )}
                                          {(child.scenarios || []).length > 0 ? t('what.scenarios.regenerateBtn') : t('what.scenarios.generateBtn')}
                                        </button>
                                      )}
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
                  {t('what.scenarios.aiSelectTitle')}
                </h3>
                <p className="text-[10px] text-slate-500 mt-1">{t('what.scenarios.aiSelectDesc')}</p>
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
                      {t('what.scenarios.noLeafNodes')}
                    </div>
                  );
                }

                return (
                  <>
                    <div className="flex justify-between items-center text-[10px] text-slate-400 font-bold bg-slate-50 p-2.5 rounded-xl border border-slate-100/50">
                      <span>{t('what.scenarios.leafSelectTitle', { count: leafFeatures.length })}</span>
                      <div className="flex gap-3">
                        <button 
                          type="button" 
                          onClick={() => setSelectedFeatureIds(leafFeatures.map(f => f.featureId))}
                          className="text-indigo-600 hover:text-indigo-700 transition-colors"
                        >
                          {t('what.scenarios.selectAll')}
                        </button>
                        <button 
                          type="button" 
                          onClick={() => setSelectedFeatureIds([])}
                          className="text-slate-500 hover:text-slate-600 transition-colors"
                        >
                          {t('what.scenarios.clearAll')}
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
                                    {t('what.scenarios.actorsCount', { count: actorCount })}
                                  </span>
                                ) : (
                                  <span className="bg-rose-50 border border-rose-100 text-rose-600 text-[10px] font-extrabold px-1.5 py-0.5 rounded-md">
          {t('what.scenarios.unbound')}
                                  </span>
                                )}
                              </div>
                              <p className="text-[10px] text-slate-400 mt-1 leading-normal truncate">{f.featureDescription || t('what.scenarios.noDesc')}</p>
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
                {t('common.cancel')}
              </button>
              <button
                onClick={async () => {
                  if (selectedFeatureIds.length === 0) return;
                  const ids = [...selectedFeatureIds];
                  setIsScenarioModalOpen(false);
                  setSelectedFeatureIds([]);
                  await generateScenarios(ids);
                }}
                disabled={selectedFeatureIds.length === 0 || isGenerating || isLoading}
                className="px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50 flex items-center gap-1.5"
              >
                <Sparkles className="w-3.5 h-3.5 text-indigo-300" />
                {selectedFeatureIds.some(featureId => (ir?.features || []).some(feature => feature.featureId === featureId && (feature.scenarios || []).length > 0)) ? t('what.scenarios.regenerateBtnAction') : t('what.scenarios.generateBtnAction')} ({selectedFeatureIds.length})
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
        <h3 className="font-extrabold text-sm text-slate-800">{t('what.actors.manualCreateTitle')}</h3>
              <p className="text-[10px] text-slate-500 mt-1">{t('what.actors.manualCreateDesc')}</p>
            </div>
            <div className="p-6 space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">{t('what.actors.nameLabel')}</label>
                <input
                  type="text"
                  value={newActorName}
                  onChange={(e) => setNewActorName(e.target.value)}
                  placeholder={t('what.actors.namePlaceholder')}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">{t('what.actors.descLabel')}</label>
                <textarea
                  value={newActorDesc}
                  onChange={(e) => setNewActorDesc(e.target.value)}
                  placeholder={t('what.actors.descPlaceholder')}
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
                {t('common.cancel')}
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
                {t('scope.modal.confirm')}
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
        {t('what.scenarios.manualCreateTitle')}
              </h3>
              <p className="text-[10px] text-slate-500 mt-1">{t('what.scenarios.manualCreateDesc')}</p>
            </div>
            <div className="p-6 space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">{t('what.scenarios.featureNameLabel')}</label>
                <input
                  type="text"
                  value={newFeatureName}
                  onChange={(e) => setNewFeatureName(e.target.value)}
                  placeholder={t('what.scenarios.featureNamePlaceholder')}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">{t('what.scenarios.featureDescLabel')}</label>
                <textarea
                  value={newFeatureDesc}
                  onChange={(e) => setNewFeatureDesc(e.target.value)}
                  placeholder={t('what.scenarios.featureDescPlaceholder')}
                  rows={3}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium resize-none leading-relaxed"
                />
              </div>
              {!isParentFixed && (
                <div className="space-y-1.5">
                  <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">{t('what.scenarios.parentLabel')}</label>
                  <select
                    value={newFeatureParentId === null ? 'null' : newFeatureParentId}
                    onChange={(e) => {
                      const val = e.target.value;
                      setNewFeatureParentId(val === 'null' ? null : parseInt(val, 10));
                    }}
                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 font-medium cursor-pointer"
                  >
                    <option value="null">{t('what.scenarios.rootOption')}</option>
                    {(() => {
                      const dbRoot = (ir?.features || []).find(f => f.parentId === null);
                      const firstLevelModules = dbRoot 
                        ? (ir?.features || []).filter(f => f.parentId === dbRoot.featureId)
                        : [];
                      return firstLevelModules.map(f => (
                        <option key={f.featureId} value={f.featureId}>
                          {t('what.scenarios.rootOptionFormat', { name: f.featureName })}
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
                {t('common.cancel')}
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
                {t('scope.modal.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* NEW: Dedicated Leaf Feature Scenario & Acceptance Criteria (AC) Management Modal */}
      {managedFeatObj && (
        <div className="fixed inset-0 bg-slate-950/65 backdrop-blur-sm z-[999] flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-white border border-slate-200 shadow-2xl max-w-4xl w-full max-h-[85vh] flex flex-col rounded-3xl animate-in scale-in-95 duration-200 overflow-hidden">
            
            {/* Modal Header */}
            <div className="p-6 border-b border-slate-200/50 flex justify-between items-center bg-slate-50/50">
              <div>
                <h3 className="font-extrabold text-sm text-slate-800 flex items-center gap-1.5">
        {t('what.scenarios.title')}
                </h3>
                <p className="text-[10px] text-indigo-700 mt-1 font-bold">
                  {t('what.scenarios.featureTitlePrefix')} <span className="bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded text-indigo-800 font-extrabold">{managedFeatObj.featureName}</span>
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
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">{t('what.scenarios.scenariosCountPrefix', { count: managedFeatObj.scenarios?.length || 0 })}</span>
                <div className="relative group">
                  <button
                    type="button"
                    onClick={() => {
                      setShowAddScenarioForm(!showAddScenarioForm);
                      setModalNewScenName('');
                        setModalNewScenContent('');
                        setModalNewScenActorId(managedFeatureActors[0]?.actorId || 0);
                    }}
                    className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-md transition-all shadow-sm"
                    aria-label={showAddScenarioForm ? t('what.scenarios.collapseScenarioAria') : t('what.scenarios.addScenarioAria')}
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                  <div className="pointer-events-none absolute left-1/2 top-0 z-20 -translate-x-1/2 -translate-y-[calc(100%+8px)] whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[10px] font-bold text-white opacity-0 shadow-md transition-opacity group-hover:opacity-100">
                    {showAddScenarioForm ? t('what.scenarios.collapseScenarioAria') : t('what.scenarios.addScenarioAria')}
                  </div>
                </div>
              </div>

              {/* Inline Add Scenario Form inside Modal */}
              {showAddScenarioForm && (
                <div className="border border-slate-200 rounded-2xl p-4 bg-slate-50/30 space-y-3 shadow-sm animate-in slide-in-from-top-2 duration-200">
                  <div className="text-[10px] text-slate-400 font-bold tracking-wider uppercase">{t('what.scenarios.addScenarioHeader')}</div>
                  
                  <div className="space-y-1.5">
                    <label className="text-[10px] text-slate-400 font-bold uppercase block">{t('what.scenarios.scenarioNameLabel')}</label>
                    <input
                      type="text"
                      value={modalNewScenName}
                      onChange={(e) => setModalNewScenName(e.target.value)}
                      placeholder={t('what.scenarios.scenarioNamePlaceholder')}
                      className="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-800 focus:ring-1 focus:ring-slate-900 focus:outline-none transition-all shadow-sm"
                    />
                  </div>

                  {/* Interactive first-person user story editor */}
                  <div className="space-y-2 pt-2 border-t border-slate-200/40">
                    <label className="text-[10px] text-slate-400 font-bold uppercase block">{t('what.scenarios.userStoryLabel')}</label>
                    <UserStoryEditor
                      initialContent={modalNewScenContent}
                      actors={managedFeatureActors}
                      onChange={(content) => {
                        setModalNewScenContent(content);
                        const parsed = parseUserStory(content);
                        const actorObj = managedFeatureActors.find((a: any) => a.actorName === parsed.role);
                        if (actorObj) {
                          setModalNewScenActorId(actorObj.actorId);
                        }
                      }}
                    />
                  </div>

                  <div className="flex justify-end gap-2 pt-1.5">
                    <button
                      onClick={() => setShowAddScenarioForm(false)}
                      className="px-3 py-1.5 text-[10px] font-bold border border-slate-200 bg-white rounded-lg hover:bg-slate-50 shadow-sm"
                    >
                      {t('common.cancel')}
                    </button>
                    <button
                      onClick={async () => {
                        if (!modalNewScenName.trim()) return;
                        await addScenario(managedFeatObj.featureId, modalNewScenActorId, modalNewScenName.trim(), modalNewScenContent.trim());
                        setShowAddScenarioForm(false);
                      }}
                      disabled={!modalNewScenName.trim() || !modalNewScenActorId}
                      className="px-3.5 py-1.5 text-[10px] font-bold bg-slate-900 text-white rounded-lg hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50"
                    >
                      {t('what.scenarios.addScenarioConfirm')}
                    </button>
                  </div>
                </div>
              )}

              {/* Scenarios and AC list */}
              {(managedFeatObj.scenarios || []).length === 0 ? (
                <div className="text-center py-16 border border-dashed border-slate-200 rounded-2xl bg-slate-50/40 text-xs text-slate-500 italic leading-relaxed">
                  {t('what.scenarios.emptyText')}
                </div>
              ) : (
                <div className="space-y-4">
                  {(managedFeatObj.scenarios || []).map((s: any) => {
                    const performer = (ir?.actors || []).find((a: any) => a.actorId === s.actorId);
                    const performerName = performer ? performer.actorName : t('what.scenarios.actorPerformerSystem');
                    const isAddingAc = modalAddingAcForScenId === s.scenarioId;
                    const isEditingScenario = editingScenarioId === s.scenarioId;
                    const isScenarioCollapsed = collapsedScenarioIds[s.scenarioId] === true;
                    const isAcCollapsed = collapsedAcScenarioIds[s.scenarioId] === true;
                    const scenarioActors = managedFeatureActors.some((actor: any) => actor.actorId === s.actorId)
                      ? managedFeatureActors
                      : performer
                        ? [...managedFeatureActors, performer]
                        : managedFeatureActors;

                    return (
                      <div key={s.scenarioId} className="border border-slate-200 rounded-2xl p-4 bg-slate-50/20 shadow-sm space-y-3 relative hover:border-slate-300 transition-colors">
                        
                        {isEditingScenario ? (
                          <div className="border border-slate-200 rounded-2xl p-4 bg-slate-50/30 space-y-3 shadow-sm animate-in slide-in-from-top-2 duration-200">
                            <div className="text-[10px] text-slate-400 font-bold tracking-wider uppercase">{t('what.scenarios.editScenarioHeader')}</div>
                            
                            <div className="space-y-1.5">
                              <label className="text-[10px] text-slate-400 font-bold uppercase block">{t('what.scenarios.scenarioNameLabel')}</label>
                              <input
                                type="text"
                                value={editingScenarioName}
                                onChange={(e) => setEditingScenarioName(e.target.value)}
                                placeholder={t('what.scenarios.scenarioNamePlaceholder')}
                                className="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-800 focus:ring-1 focus:ring-slate-900 focus:outline-none transition-all shadow-sm"
                              />
                            </div>

                            {/* Interactive first-person user story editor */}
                            <div className="space-y-2 pt-2 border-t border-slate-200/40">
                              <label className="text-[10px] text-slate-400 font-bold uppercase block">{t('what.scenarios.userStoryLabel')}</label>
                              <UserStoryEditor
                                initialContent={editingScenarioContent}
                                actors={scenarioActors}
                                onChange={(content) => {
                                  setEditingScenarioContent(content);
                                  const parsed = parseUserStory(content);
                                  const actorObj = scenarioActors.find((a: any) => a.actorName === parsed.role);
                                  if (actorObj) {
                                    setEditingScenarioActorId(actorObj.actorId);
                                  }
                                }}
                              />
                            </div>

                            <div className="flex justify-end gap-2 pt-1.5">
                              <button
                                onClick={() => setEditingScenarioId(null)}
                                className="px-3 py-1.5 text-[10px] font-bold border border-slate-200 bg-white rounded-lg hover:bg-slate-50 shadow-sm"
                              >
                                {t('common.cancel')}
                              </button>
                              <button
                                onClick={async () => {
                                  if (!editingScenarioName.trim()) return;
                                  await updateScenario(managedFeatObj.featureId, s.scenarioId, {
                                    scenarioName: editingScenarioName.trim(),
                                    scenarioContent: editingScenarioContent.trim(),
                                    actorId: editingScenarioActorId
                                  });
                                  setEditingScenarioId(null);
                                }}
                                disabled={!editingScenarioName.trim()}
                                className="px-3.5 py-1.5 text-[10px] font-bold bg-slate-900 text-white rounded-lg hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50"
                              >
                                {t('what.confirmSave')}
                              </button>
                            </div>
                          </div>
                        ) : (
                          <>
                            {/* Scenario Header */}
                            <div className="flex justify-between items-start">
                              <div className="space-y-1 min-w-0">
                                <span className="font-extrabold text-xs text-slate-800 tracking-wide block truncate">{s.scenarioName}</span>
                                {!isScenarioCollapsed && (
                                  <div className="flex items-center gap-1.5 flex-wrap mt-1">
                                    <span className="inline-block text-[10px] bg-indigo-50 border border-indigo-100 text-indigo-700 font-extrabold px-1.5 py-0.5 rounded-md">
                                      {t('what.scenarios.actorPerformerFormat', { name: performerName })}
                                    </span>
                                    <InteractiveStatusBadge
                                      nodeId={s.scenarioId}
                                      nodeKind="scenario"
                                      status={s.confirmationStatus || 'confirmed'}
                                      setNodeStatus={setNodeStatus}
                                    />
                                  </div>
                                )}
                              </div>
                              <div className="flex gap-1.5">
                                {!isScenarioCollapsed && (
                                  <>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setEditingScenarioId(s.scenarioId);
                                        setEditingScenarioName(s.scenarioName);
                                        setEditingScenarioContent(s.scenarioContent || '');
                                        setEditingScenarioActorId(s.actorId);
                                      }}
                                      className="p-1 text-slate-400 hover:text-indigo-600 transition-colors"
                                      title={t('what.scenarios.editBtn')}
                                    >
                                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                                    </button>
                                    <button
                                      type="button"
                                      onClick={async () => {
                                        if (confirm(t('what.scenarios.deleteConfirm'))) {
                                          await deleteScenario(managedFeatObj.featureId, s.scenarioId);
                                        }
                                      }}
                                      className="p-1 text-slate-400 hover:text-rose-600 transition-colors"
                                      title={t('what.scenarios.deleteBtn')}
                                    >
                                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                    </button>
                                  </>
                                )}
                                <button
                                  type="button"
                                  onClick={() => {
                                    setCollapsedScenarioIds((prev) => ({ ...prev, [s.scenarioId]: !prev[s.scenarioId] }));
                                  }}
                                  className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-md transition-all shadow-sm"
                                  title={isScenarioCollapsed ? t('what.scenarios.expandScenario') : t('what.scenarios.collapseScenario')}
                                  aria-label={isScenarioCollapsed ? t('what.scenarios.expandScenario') : t('what.scenarios.collapseScenario')}
                                >
                                  {isScenarioCollapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                                </button>
                              </div>
                            </div>

                            {/* Scenario Description */}
                            {!isScenarioCollapsed && (
                              <UserStoryRenderer
                                content={s.scenarioContent || ''}
                                performerName={performerName}
                              />
                            )}
                          </>
                        )}

                        {/* Acceptance Criteria Section */}
                        {!isScenarioCollapsed && (
                          <div className="space-y-2 pt-2 border-t border-slate-200/50">
                            <div className="flex justify-between items-center text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                              <span>{t('what.scenarios.acCountLabel', { count: s.acceptanceCriteria?.length || 0 })}</span>
                              <div className="flex items-center gap-1.5">
                                <div className="relative group">
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setCollapsedAcScenarioIds((prev) => ({ ...prev, [s.scenarioId]: !prev[s.scenarioId] }));
                                    }}
                                    className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-md transition-all shadow-sm"
                                    aria-label={isAcCollapsed ? t('what.scenarios.expandAc') : t('what.scenarios.collapseAc')}
                                  >
                                    {isAcCollapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                                  </button>
                                  <div className="pointer-events-none absolute right-0 top-0 z-20 -translate-y-[calc(100%+8px)] whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[10px] font-bold text-white opacity-0 shadow-md transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                                    {isAcCollapsed ? t('what.scenarios.expandAc') : t('what.scenarios.collapseAc')}
                                  </div>
                                </div>
                                <div className="relative group">
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setCollapsedAcScenarioIds((prev) => ({ ...prev, [s.scenarioId]: false }));
                                      setModalAddingAcForScenId(isAddingAc ? null : s.scenarioId);
                                    }}
                                    className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-md transition-all shadow-sm"
                                    aria-label={isAddingAc ? t('what.scenarios.collapseAcAria') : t('what.scenarios.addAcAria')}
                                  >
                                    <Plus className="w-3.5 h-3.5" />
                                  </button>
                                  <div className="pointer-events-none absolute right-0 top-0 z-20 -translate-y-[calc(100%+8px)] whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[10px] font-bold text-white opacity-0 shadow-md transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                                    {isAddingAc ? t('what.scenarios.collapseAcAria') : t('what.scenarios.addAcAria')}
                                  </div>
                                </div>
                              </div>
                            </div>

                            {!isAcCollapsed && (
                              <>
                                {/* Add AC Form using AcInlineEditor */}
                                {isAddingAc && (
                                  <div className="mt-2.5 animate-in slide-in-from-top-1 duration-150">
                                    <AcInlineEditor
                                      initialContent=""
                                      onSave={async (content) => {
                                        if (!content.trim()) return;
                                        await addAcceptanceCriterion(managedFeatObj.featureId, s.scenarioId, content.trim());
                                        setModalAddingAcForScenId(null);
                                      }}
                                      onCancel={() => setModalAddingAcForScenId(null)}
                                    />
                                  </div>
                                )}

                                {/* AC Items list */}
                                {(s.acceptanceCriteria || []).length === 0 ? (
                                  <div className="text-[10px] text-slate-500 italic bg-white/50 p-2 rounded-xl border border-dashed border-slate-200/50 leading-relaxed">
                                    {t('what.scenarios.acEmptyText')}
                                  </div>
                                ) : (
                                  <div className="space-y-3">
                                    {(s.acceptanceCriteria || []).map((ac: any, acIdx: number) => {
                                      const isEditingAc = editingAcId === ac.criterionId;
                                      return isEditingAc ? (
                                        <AcInlineEditor
                                          key={ac.criterionId}
                                          initialContent={ac.criterionContent || ''}
                                          onSave={async (newContent) => {
                                            if (!newContent.trim()) return;
                                            await updateAcceptanceCriterion(managedFeatObj.featureId, s.scenarioId, ac.criterionId, newContent.trim());
                                            setEditingAcId(null);
                                          }}
                                          onCancel={() => setEditingAcId(null)}
                                        />
                                      ) : (
                                        <GherkinVisualRenderer
                                          key={ac.criterionId}
                                          text={ac.criterionContent || ''}
                                          title={t('what.scenarios.acTitlePrefix', { index: acIdx + 1 })}
                                          statusBadge={
                                            <span className="scale-75 origin-left inline-block">
                                              <InteractiveStatusBadge
                                                nodeId={ac.criterionId}
                                                nodeKind="acceptance_criterion"
                                                status={ac.confirmationStatus || 'confirmed'}
                                                setNodeStatus={setNodeStatus}
                                              />
                                            </span>
                                          }
                                          rightBadges={[
                                            <button
                                              key="edit"
                                              type="button"
                                              onClick={(e) => {
                                                e.stopPropagation();
                                                setEditingAcId(ac.criterionId);
                                              }}
                                              className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 rounded-md transition-all shadow-sm"
                                              title={t('what.scenarios.editAc')}
                                              aria-label={t('what.scenarios.editAc')}
                                            >
                                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                                            </button>,
                                            <button
                                              key="delete"
                                              type="button"
                                              onClick={async (e) => {
                                                e.stopPropagation();
                                                if (confirm(t('what.scenarios.deleteAcConfirm'))) {
                                                  await deleteAcceptanceCriterion(managedFeatObj.featureId, s.scenarioId, ac.criterionId);
                                                }
                                              }}
                                              className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 border border-transparent hover:border-rose-100 rounded-md transition-all shadow-sm"
                                              title={t('what.scenarios.deleteAc')}
                                              aria-label={t('what.scenarios.deleteAc')}
                                            >
                                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                            </button>
                                          ]}
                                        />
                                      );
                                    })}
                                  </div>
                                )}
                              </>
                            )}
                          </div>
                        )}
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
                {t('what.scenarios.confirmClose')}
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
        confirmLabel={activeDraftType === 'scenario' ? t('what.scenarios.confirmAcAdopt') : t('what.scenarios.confirmAdopt')}
      />

      <ChoiceGroupPreviewModal
        group={activeChoiceGroup}
        isWorking={isGeneratingChoices || isLoading}
        isGeneratingChoices={isGeneratingChoices}
        generationProgress={choiceGroupGenerationProgress}
        onAccept={async (choiceId) => {
          await acceptChoice(choiceId);
        }}
        onDiscard={async () => {
          if (activeChoiceGroup) {
            await discardChoiceGroup(activeChoiceGroup.id);
          }
        }}
        onDefer={() => useWorkspaceStore.setState({ activeChoiceGroup: null })}
      />

      <AIAddObjectDialog
        isOpen={isAIDialogOpen}
        onClose={() => setAiDialogTarget(null)}
        projectId={ir?.projectId ?? ''}
        targetType={aiDialogTarget?.targetType ?? 'actor'}
        anchor={aiDialogTarget?.anchor}
        onConfirm={async () => {
          setAiDialogTarget(null);
          // Refresh workspace data after confirm
          const { refreshWorkspace } = useWorkspaceStore.getState();
          await refreshWorkspace();
        }}
      />

      <ConfirmTransitionModal
        isOpen={isTransitionModalOpen}
        onClose={() => setIsTransitionModalOpen(false)}
        stage="what"
        isWorking={isLoading}
        onAIDiagnose={async () => {
          // Don't close modal — it handles its own diagnosing state
          await runDiagnosis('what');
        }}
        onForceUnlock={async () => {
          setIsTransitionModalOpen(false);
          await requestStageTransition('enter_how', { navigate });
        }}
      />

      <RightObjectPanel />
    </div>
  );
}
