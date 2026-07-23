import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { RangeKanbanColumn } from '@/components/shared/RangeKanbanColumn';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { ImpactPreview, ImpactGroup } from '@/components/shared/ImpactPreview';
import { DraftPreviewModal } from '@/components/shared/DraftPreviewModal';
import { workspaceApi } from '@/lib/api';
import { Sparkles, Check, X, RefreshCw, CheckSquare } from 'lucide-react';
import { StageGuidanceBanner } from '@/components/shared/StageGuidanceBanner';
import { getScopeStatusText } from '@/core/presentationLabels';
import { 
  useWorkspaceStore, 
  selectScopeItems,
} from '@/store/useWorkspaceStore';
import { ChoiceGroupPreviewModal } from '@/components/shared/ChoiceGroupPreviewModal';

import { buildProjectRoute, getStageIssues, groupScopeItems } from '@/core/selectors';
import { findingTargetIds } from '@/core/findingPresentation';
import { useTranslation } from 'react-i18next';
import i18n from '@/i18n';

const SCOPE_COLUMNS = [
  { key: 'undecided', get label() { return i18n.t('scope.columns.undecided') || 'Undecided'; }, warning: true },
  { key: 'current', get label() { return i18n.t('scope.columns.current') || 'Current'; } },
  { key: 'postponed', get label() { return i18n.t('scope.columns.postponed') || 'Postponed'; } },
  { key: 'exclude', get label() { return i18n.t('scope.columns.exclude') || 'Excluded'; }, danger: true },
] as const;

export function ScopeAndDelivery() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { 
    selectedObject, highlightTarget, setHighlightTarget,
    setSelectedObject, ir, updateScope, addFeature,
    generateScope, confirmScope, discardDraft, regenerateScope,
    activeDraft, activeDraftType, isGenerating, isLoading,
    setPendingManualAction, resetKano, runDiagnosis,
    confirmRepairDraft, discardRepairDraft, regenerateRepairDraft,
    executeFindingIssueResolution, expandSlot, updateIssueAttributes, clearPerceptionSlot,
    activeChoiceGroup, isGeneratingChoices, choiceGroupGenerationProgress, acceptChoice, discardChoiceGroup
  } = useWorkspaceStore();
  
  const [scopeFeedback, setScopeFeedback] = useState('');

  // 从 URL 参数解析高亮目标（来自概览页假设账本点击跳转）
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const highlight = params.get('highlight');
    if (!highlight) return;
    const [kind, ...idParts] = highlight.split('-');
    const id = parseInt(idParts.join('-'), 10);
    if (isNaN(id)) return;
    navigate(location.pathname, { replace: true });

    setTimeout(() => {
      const el = document.getElementById(`${kind}-${id}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('ring-2', 'ring-indigo-400', 'ring-offset-2', 'rounded-xl');
        setTimeout(() => el.classList.remove('ring-2', 'ring-indigo-400', 'ring-offset-2', 'rounded-xl'), 3000);
      }
      if (kind === 'scope') {
        const scopeItem = ir?.features?.find((feature: any) => feature.scope?.scopeId === id);
        if (scopeItem) setSelectedObject(buildScopeSelectionObject(scopeItem));
      }
    }, 200);
  }, [location.search]);


  const handleManualAction = (slot: any) => {
    if (slot.kind === 'generative_perception_slot') {
      void clearPerceptionSlot();
      return;
    }

    const targetId = slot.targetId || slot.actions?.manual?.targetId;
    const targetRoute = slot.actions?.manual?.targetRoute;
    if (targetId) {
      const targetKey = targetId.toString();
      setHighlightTarget(targetKey);
      const feature = ir?.features?.find((item: any) => item.featureId === targetId);
      setSelectedObject(feature || null);
    }
    if (targetRoute && targetRoute !== '/scope') {
      navigate(buildProjectRoute(ir?.projectId, targetRoute));
    }
  };

  const handleAIAction = async (slot: any) => {
    const kind = slot.kind;
    if (kind === 'missing_scope_decision' || kind === 'missing_kano_analysis' || kind === 'kano_failed_retry') {
      await generateScope();
    }
  };
  
  const scopeItems = useWorkspaceStore(selectScopeItems);
  const scopeIssues = getStageIssues(ir, 'scope');
  const [impactGroups, setImpactGroups] = useState<ImpactGroup[]>([]);
  const [pendingMove, setPendingMove] = useState<{ itemId: string; targetKey: string } | null>(null);
  const [pendingMoveLabel, setPendingMoveLabel] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [isImpactLoading, setIsImpactLoading] = useState(false);

  const buildScopeSelectionObject = (item: any) => {
    if (!item) return null;
    const featureId = item.featureId ?? parseInt(item.id, 10);
    if (isNaN(featureId)) return item;

    const feature = ir?.features?.find((candidate: any) => candidate.featureId === featureId);
    const scope = feature?.scope || item.scope || null;

    return {
      kind: 'scope' as const,
      id: featureId.toString(),
      featureId,
      featureName: feature?.featureName || item.featureName || item.title || '',
      featureDescription: feature?.featureDescription || item.featureDescription || item.description || '',
      parentId: feature?.parentId ?? item.parentId ?? null,
      scopeId: scope?.scopeId,
      title: feature?.featureName || item.title || '',
      description: feature?.featureDescription || item.description || '',
      status: scope?.confirmationStatus || item.confirmationStatus || item.status,
      confirmationStatus: scope?.confirmationStatus || item.confirmationStatus || item.status,
      scopeStatus: scope?.scopeStatus || item.scopeStatus,
      parentModuleName: item.parentModuleName,
      scope: scope || item.scope || null,
    };
  };

  // Group items based on our four-column status mapping
  const grouped = ir
    ? (groupScopeItems(ir) as { inScope: any[]; deferred: any[]; excluded: any[]; undecided: any[] })
    : { inScope: [] as any[], deferred: [] as any[], excluded: [] as any[], undecided: [] as any[] };
  const inScope = grouped.inScope;
  const deferred = grouped.deferred;
  const excluded = grouped.excluded;
  const undecided = grouped.undecided || [];

  const totalLeafs = inScope.length + deferred.length + excluded.length + undecided.length;
  const isScopeComplete = totalLeafs > 0;

  if (!isScopeComplete) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 bg-slate-50 min-h-[80vh] w-full">
        <div className="max-w-md w-full bg-white rounded-3xl p-8 border border-slate-200 shadow-lg text-center space-y-6 animate-in fade-in duration-300">
          <div className="mx-auto w-16 h-16 rounded-2xl bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-500 shadow-sm animate-pulse">
            <CheckSquare className="w-8 h-8" />
          </div>
          <div className="space-y-2">
            <h3 className="text-lg font-black text-slate-900 tracking-tight">{t('scope.dependencyNotMetTitle')}</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              {t('scope.dependencyNotMetDesc')}
            </p>
            <p className="text-xs text-slate-400 leading-relaxed bg-slate-50 p-3 rounded-xl border border-slate-100/60">
              {t('scope.dependencyNotMetHelp')}
            </p>
          </div>
          <button
            onClick={() => navigate(buildProjectRoute(ir?.projectId, '/what'))}
            className="w-full py-2.5 px-4 rounded-xl bg-slate-900 text-white text-xs font-bold hover:bg-slate-800 transition-colors shadow-sm"
          >
          {t('scope.goToWhatBtn')}
          </button>
        </div>
      </div>
    );
  }

  const buildImpactGroups = (resp: any): ImpactGroup[] => {
    const groups: ImpactGroup[] = [];
    const scenarios = resp.affectedScenarios || resp.affected_scenarios || [];
    const flows = resp.affectedFlows || resp.affected_flows || [];
    const objects = resp.affectedBusinessObjects || resp.affected_business_objects || [];
    
    if (scenarios.length > 0) {
      groups.push({
        type: 'info',
        title: t('scope.affectedScenarios', { count: scenarios.length }),
        items: scenarios
      });
    }
    if (flows.length > 0) {
      groups.push({
        type: 'process',
        title: t('scope.affectedFlows', { count: flows.length }),
        items: flows
      });
    }
    if (objects.length > 0) {
      groups.push({
        type: 'info',
        title: t('scope.affectedObjects', { count: objects.length }),
        items: objects
      });
    }

    if (groups.length === 0) {
      groups.push({
        type: 'info',
        title: t('scope.impactAnalysisComplete'),
        items: [resp.summary === 'scope_impact_summary'
          ? t('scope.impactSummaryCounts', {
              scenarios: scenarios.length,
              flows: flows.length,
              objects: objects.length,
            })
          : resp.summary || t('scope.impactAnalysisNone')]
      });
    }
    return groups;
  };

  const createScopeItem = async (columnKey: string) => {
    const scopeStatus = columnKey;
    const tempName = `${t('scope.manualFeaturePlaceholder')}-${Math.floor(1000 + Math.random() * 9000)}`;
    
    // Add feature node (default to '本期' containing empty scope)
    await addFeature(tempName, t('scope.manualFeatureDesc'), null);
    
    // Find the feature by name in state and update its scope status if not 'current'
    const space = useWorkspaceStore.getState().ir;
    const created = space?.features.find(f => f.featureName === tempName);
    if (created) {
      if (scopeStatus !== 'current') {
        await updateScope(created.featureId, { scopeStatus: scopeStatus as any });
      }
      setSelectedObject(buildScopeSelectionObject(created));
    }
  };

  const previewScopeMove = async (itemId: string, targetKey: string) => {
    if (!ir?.projectId) return;
    const sourceItem = [...inScope, ...deferred, ...excluded, ...undecided].find((item: any) => item.id === itemId);
    if (targetKey === 'undecided' && sourceItem?.scopeStatus) return;
    const targetLabel = SCOPE_COLUMNS.find((column) => column.key === targetKey)?.label || targetKey;
    const scopeStatus = targetKey;
    const featureId = parseInt(itemId, 10);

    setPendingMove({ itemId, targetKey });
    setPendingMoveLabel(targetLabel);
    setIsImpactLoading(true);
    setImpactGroups([]);
    setPreviewError(null);

    try {
      const resp = await workspaceApi.impactPreview(ir.projectId, featureId, scopeStatus);
      setImpactGroups(buildImpactGroups(resp));
    } catch (error) {
      setPreviewError(error instanceof Error ? error.message : t('scope.impactAnalysisError'));
    } finally {
      setIsImpactLoading(false);
    }
  };

  const applyPendingMove = async () => {
    if (!pendingMove) return;
    const { itemId, targetKey } = pendingMove;
    const numId = parseInt(itemId, 10);
    const scopeStatus = targetKey;
    
    await updateScope(numId, { scopeStatus: scopeStatus as any });
    setPendingMove(null);
    setPendingMoveLabel(null);
    setImpactGroups([]);
  };

  const isWorking = isGenerating || isLoading;

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

  return (
    <div className="flex-1 flex w-full relative">
      <div className="flex-1 p-6 pb-24 overflow-y-auto">
        <div className="max-w-[1200px] mx-auto space-y-8 animate-in fade-in">
          
          <StageGuidanceBanner stage="scope" />

          {/* AI Scope Draft Preview Banner */}
          {false && activeDraft && activeDraftType === 'scope' && (
            <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-6 border border-amber-200/80 shadow-md animate-in slide-in-from-top-4 duration-500 space-y-4">
              <div className="flex justify-between items-start">
                <div className="flex items-center gap-2 flex-1 mr-4">
                  <span className="p-1.5 bg-amber-100 text-amber-700 rounded-lg shrink-0">
                    <Sparkles className="w-5 h-5 animate-pulse" />
                  </span>
                  <div className="flex-1 space-y-2">
                    <div>
                      <h3 className="text-base font-bold text-slate-900">{t('scope.board.kanoGeneratedTitle')}</h3>
                      <p className="text-xs text-slate-500 mt-0.5">{t('scope.board.kanoGeneratedDesc')}</p>
                    </div>
                    <div className="flex gap-2 items-center max-w-md">
                      <input
                        type="text"
                        value={scopeFeedback}
                        onChange={(e) => setScopeFeedback(e.target.value)}
                        placeholder={t('scope.board.feedbackPlaceholder')}
                        className="flex-1 px-3 py-1.5 bg-white border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800"
                        disabled={isWorking}
                      />
                      <button
                        onClick={async () => {
                          await regenerateScope(scopeFeedback || undefined);
                          setScopeFeedback('');
                        }}
                        disabled={isWorking}
                        className="flex items-center gap-1 px-3 py-1.5 border border-slate-200 bg-white text-slate-700 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                      >
                        <RefreshCw className={`w-3 h-3 text-indigo-500 ${isWorking ? 'animate-spin' : ''}`} />
                        {t('scope.board.regenerateBtn')}
                      </button>
                    </div>
                  </div>
                </div>
                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={confirmScope}
                    disabled={isWorking}
                    className="flex items-center gap-1.5 px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl hover:bg-slate-800 transition-colors shadow-sm disabled:opacity-50"
                  >
                    <Check className="w-3.5 h-3.5" />
                    {t('onboarding.kbAdoptButton')}
                  </button>
                  <button
                    onClick={discardDraft}
                    disabled={isWorking}
                    className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
                  >
                    <X className="w-3.5 h-3.5" />
                    {t('scope.modal.discard')}
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-200/60">
                {activeDraft.scopes?.map((sc: any, idx: number) => {
                  const scopeStatusText = getScopeStatusText(sc.scope_status);
                  return (
                  <div key={idx} className="bg-white/80 p-4 rounded-xl border border-slate-200/50 flex flex-col justify-between">
                    <div>
                      <div className="flex justify-between items-center mb-1.5">
                        <h4 className="font-bold text-slate-800 text-xs">{sc.feature_name}</h4>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          sc.scope_status === 'current' || sc.scope_status === 'in_scope'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-100'
                            : sc.scope_status === 'postponed' || sc.scope_status === 'deferred'
                            ? 'bg-sky-50 text-sky-700 border border-sky-100'
                            : 'bg-rose-50 text-rose-700 border border-rose-100'
                        }`}>{scopeStatusText}</span>
                      </div>
                      <p className="text-xs text-slate-500 leading-relaxed mb-3">{sc.reason}</p>
                    </div>
                    {sc.positive_summary && (
                      <div className="text-[10px] text-slate-600 bg-slate-50 p-2 rounded-lg border border-slate-100 font-medium">
                {sc.positive_summary}
                      </div>
                    )}
                  </div>
                  );
                })}
              </div>
            </div>
          )}

          <section className="bg-white rounded-3xl p-8 border border-slate-200 shadow-md">
             <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4 mb-8">
                <div>
                   <h2 className="text-xl font-black text-slate-900 tracking-tight mb-2">{t('scope.board.title')}</h2>
                  <p className="text-xs text-slate-500 flex flex-wrap items-center gap-1.5">
                    {ir?.kanoStatus === 'skipped' && (
                      <span className="inline-block px-2 py-0.5 bg-amber-50 border border-amber-200/60 text-amber-700 text-[10px] font-extrabold rounded">
                        {t('scope.board.kanoSkipped')}
                      </span>
                    )}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {(!ir?.kanoStatus || ir.kanoStatus === 'missing' || ir.kanoStatus === 'failed') && (
                    <>
                      <button
                        onClick={() => void generateScope()}
                        disabled={isWorking}
                        className="flex items-center gap-1.5 text-[10px] bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold px-3 py-1.5 rounded-xl border border-indigo-100/80 transition-colors shadow-sm disabled:opacity-50"
                      >
                        <Sparkles className={`w-3.5 h-3.5 text-indigo-500 ${isWorking ? 'animate-pulse' : ''}`} />
                        {t('scope.board.generateBtn')}
                      </button>
                    </>
                  )}

                  {ir?.kanoStatus === 'generating' && (
                    <button
                      disabled={true}
                      className="flex items-center gap-1.5 text-xs bg-slate-100 text-slate-500 font-bold px-4 py-2.5 rounded-xl border border-slate-200/50"
                    >
                      <RefreshCw className="w-3.5 h-3.5 animate-spin text-slate-400" />
                      {t('scope.board.generatingStatus')}
                    </button>
                  )}

                  {activeDraft && activeDraftType === 'scope' && (
                    <>
                      <button
                        onClick={confirmScope}
                        className="flex items-center gap-1.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-4 py-2.5 rounded-xl transition-all shadow-md active:scale-95"
                      >
                        {t('scope.board.confirmBtn')}
                      </button>
                    </>
                  )}

                  {(ir?.kanoStatus === 'generated' || ir?.kanoStatus === 'skipped') && (
                    <button
                      onClick={async () => {
                        if (window.confirm(t('scope.board.resetConfirm'))) {
                          await resetKano();
                        }
                      }}
                      disabled={isWorking}
                      className="flex items-center gap-1.5 text-[10px] bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold px-3 py-1.5 rounded-xl border border-indigo-100/80 transition-colors shadow-sm disabled:opacity-50"
                    >
                      <Sparkles className={`w-3.5 h-3.5 text-indigo-500 ${isWorking ? 'animate-pulse' : ''}`} />
                      {t('scope.board.resetBtn')}
                    </button>
                  )}
                </div>
             </div>

             <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
                <RangeKanbanColumn 
                  columnKey="undecided"
                  title={t('scope.columns.undecided')}
                  items={undecided}
                  moveTargets={SCOPE_COLUMNS.filter(c => c.key !== 'undecided').map((column) => ({ key: column.key, label: column.label, danger: column.key === 'exclude' }))}
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id?.toString()}
                  onItemClick={(item) => setSelectedObject(buildScopeSelectionObject(item))}
                  onMoveItem={previewScopeMove}
                />
                <RangeKanbanColumn 
                  columnKey="current"
                  title={t('scope.columns.current')}
                  items={inScope}
                  moveTargets={SCOPE_COLUMNS.filter(c => c.key !== 'undecided').map((column) => ({ key: column.key, label: column.label, danger: column.key === 'exclude' }))}
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id?.toString()}
                  onItemClick={(item) => setSelectedObject(buildScopeSelectionObject(item))}
                  onMoveItem={previewScopeMove}
                  onAddItem={createScopeItem}
                />
                <RangeKanbanColumn 
                  columnKey="postponed"
                  title={t('scope.columns.postponed')}
                  items={deferred}
                  moveTargets={SCOPE_COLUMNS.filter(c => c.key !== 'undecided').map((column) => ({ key: column.key, label: column.label, danger: column.key === 'exclude' }))}
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id?.toString()}
                  onItemClick={(item) => setSelectedObject(buildScopeSelectionObject(item))}
                  onMoveItem={previewScopeMove}
                  onAddItem={createScopeItem}
                />
                <RangeKanbanColumn 
                  columnKey="exclude"
                  title={t('scope.columns.exclude')}
                  items={excluded}
                  moveTargets={SCOPE_COLUMNS.filter(c => c.key !== 'undecided').map((column) => ({ key: column.key, label: column.label, danger: column.key === 'exclude' }))}
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id?.toString()}
                  onItemClick={(item) => setSelectedObject(buildScopeSelectionObject(item))}
                  onMoveItem={previewScopeMove}
                  onAddItem={createScopeItem}
                />
             </div>
          </section>

        </div>
      </div>
      
      {/* 范围调整影响评估确认弹窗 */}
      {pendingMove && (
        <div className="fixed inset-0 bg-slate-950/45 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div 
            className="absolute inset-0" 
            onClick={() => { setPendingMove(null); setPendingMoveLabel(null); setImpactGroups([]); }}
          ></div>
          
          <div className="bg-white rounded-3xl border border-slate-100/50 shadow-2xl w-[min(540px,100%)] p-6 relative z-10 space-y-5 animate-in zoom-in-95 duration-200 flex flex-col">
            <div className="text-center">
              <div className="mx-auto w-12 h-12 bg-indigo-50 border border-indigo-100 rounded-full flex items-center justify-center text-indigo-600 mb-3 shadow-sm">
                <RefreshCw className={`w-5 h-5 ${isImpactLoading ? 'animate-spin' : ''}`} />
              </div>
              <h3 className="text-base font-black text-slate-900 tracking-tight">{t('scope.modal.title')}</h3>
              <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                {t('scope.modal.desc', { label: pendingMoveLabel })}
              </p>
            </div>

            {isImpactLoading ? (
              <div className="flex flex-col items-center justify-center py-8 space-y-3 bg-slate-50 rounded-2xl border border-slate-200/50">
                <RefreshCw className="w-8 h-8 text-indigo-600 animate-spin" />
                <span className="text-xs text-slate-500 font-bold">{t('scope.modal.calculating')}</span>
              </div>
            ) : previewError ? (
              <div className="text-xs text-rose-600 font-medium py-4 text-center bg-rose-50 rounded-2xl border border-rose-200/50">
                {previewError}
              </div>
            ) : (
              <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200/80 shadow-inner max-h-[250px] overflow-y-auto">
                <ImpactPreview impacts={impactGroups} />
              </div>
            )}

            <div className="flex gap-3 justify-end pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => { setPendingMove(null); setPendingMoveLabel(null); setImpactGroups([]); }}
                className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-xl text-xs font-bold transition-colors"
              >
                {t('scope.modal.cancel')}
              </button>
              <button
                type="button"
                onClick={applyPendingMove}
                disabled={isImpactLoading}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold transition-colors shadow-sm shadow-indigo-100 disabled:opacity-50"
              >
                {t('scope.modal.confirm')}
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
          } else {
            regenerateScope(feedback)
          };
        }}
        onConfirm={async () => {
          if (activeDraftType === 'repair') {
            const dId = activeDraft?.draftId || activeDraft?.draft_id;
            if (dId) await confirmRepairDraft(dId);
          } else {
            await confirmScope();
          }
        }}
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

      <RightObjectPanel />
    </div>
  );
}
