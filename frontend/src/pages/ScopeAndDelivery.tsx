import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { RangeKanbanColumn } from '@/components/shared/RangeKanbanColumn';
import { RightObjectPanel } from '@/components/shared/RightObjectPanel';
import { ImpactPreview, ImpactGroup } from '@/components/shared/ImpactPreview';
import { DraftPreviewModal } from '@/components/shared/DraftPreviewModal';
import { workspaceApi } from '@/lib/api';
import { Sparkles, RefreshCw, CheckSquare } from 'lucide-react';
import { StageGuidanceBanner } from '@/components/shared/StageGuidanceBanner';
import { useWorkspaceStore } from '@/store/useWorkspaceStore';
import { ChoiceGroupPreviewModal } from '@/components/shared/ChoiceGroupPreviewModal';

import { buildProjectRoute, groupScopeItems } from '@/core/selectors';
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
    selectedObject, highlightTarget,
    setSelectedObject, ir, updateScope,
    generateScope, confirmScope, discardDraft, regenerateScope,
    activeDraft, activeDraftType, isGenerating, isLoading,
    resetKano,
    confirmRepairDraft, discardRepairDraft, regenerateRepairDraft,
    activeChoiceGroup, isGeneratingChoices, choiceGroupGenerationProgress, acceptChoice, discardChoiceGroup
  } = useWorkspaceStore();

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

  return (
    <div className="flex-1 flex w-full relative">
      <div className="flex-1 p-6 pb-24 overflow-y-auto">
        <div className="max-w-[1200px] mx-auto space-y-8 animate-in fade-in">
          
          <StageGuidanceBanner stage="scope" />

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
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id?.toString()}
                  onItemClick={(item) => setSelectedObject(buildScopeSelectionObject(item))}
                  onMoveItem={previewScopeMove}
                />
                <RangeKanbanColumn 
                  columnKey="current"
                  title={t('scope.columns.current')}
                  items={inScope}
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id?.toString()}
                  onItemClick={(item) => setSelectedObject(buildScopeSelectionObject(item))}
                  onMoveItem={previewScopeMove}
                />
                <RangeKanbanColumn 
                  columnKey="postponed"
                  title={t('scope.columns.postponed')}
                  items={deferred}
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id?.toString()}
                  onItemClick={(item) => setSelectedObject(buildScopeSelectionObject(item))}
                  onMoveItem={previewScopeMove}
                />
                <RangeKanbanColumn 
                  columnKey="exclude"
                  title={t('scope.columns.exclude')}
                  items={excluded}
                  highlightTarget={highlightTarget}
                  selectedTarget={selectedObject?.id?.toString()}
                  onItemClick={(item) => setSelectedObject(buildScopeSelectionObject(item))}
                  onMoveItem={previewScopeMove}
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
