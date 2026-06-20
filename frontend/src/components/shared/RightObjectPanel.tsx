import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Choice, ChoiceGroup, Finding, RequirementSpaceIR, RequirementSlot, NodeStatus, NodeStatusToText } from '@/core/schema';
import { selectSelectedObject, useWorkspaceStore } from '@/store/useWorkspaceStore';
import { ChoiceGroupPanel } from '../right-panel/ChoiceGroupPanel';
import { ChoicePanel } from '../right-panel/ChoicePanel';
import { IssuePanel } from '../right-panel/IssuePanel';
import { NodePanel } from '../right-panel/NodePanel';
import { PanelShell, Section, TextField, SelectField, ActionRow, ActionButton } from '../right-panel/shared';
import { SlotPanel } from '../right-panel/SlotPanel';
import { StatusBadge } from './StatusBadge';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { normalizeScopeStatus } from '@/core/selectors';
import { GherkinVisualRenderer, GherkinVisualEditor } from './GherkinVisualizer';

const findChoiceById = (ir: RequirementSpaceIR | null, choiceId: string | null): Choice | null => {
  if (!ir || !choiceId) return null;
  for (const group of Object.values(ir.choiceGroups || {})) {
    const choice = (group.choices || []).find((item) => item.id === choiceId);
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
    if (this.state.hasError) {
      return (
        <PanelShell title="审查面板渲染发生错误" subtitle="智能审查面板错误">
          <div className="p-4 border border-rose-200 bg-rose-50/50 rounded-2xl space-y-4">
            <div className="text-sm font-bold text-rose-700">抽屉面板渲染组件崩溃</div>
            <div className="text-xs text-rose-600 font-medium leading-relaxed">
              错误信息: {this.state.error?.message || '未知异常'}
            </div>
            <pre className="text-[10px] text-slate-700 bg-slate-50 border border-slate-100 rounded-xl p-3 max-h-[300px] overflow-auto font-mono">
              {this.state.error?.stack || '无堆栈追踪'}
            </pre>
            <div className="text-[10px] text-slate-500">
              请将该报错截图或复制发给开发人员进行排查。
            </div>
          </div>
        </PanelShell>
      );
    }

    return this.props.children;
  }
}

// 确认状态选项
const CONFIRMATION_STATUS_OPTIONS = [
  { value: 'confirmed', label: '已确认' },
  { value: 'needs_confirmation', label: '待确认' },
  { value: 'ai_assumption', label: 'AI 推测' },
];

const SCOPE_DECISION_OPTIONS = [
  { value: '', label: '未交付决策' },
  { value: 'current', label: '本期包含' },
  { value: 'postponed', label: '暂缓处理' },
  { value: 'exclude', label: '已排除' },
];

// 通用确认状态编辑区块
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
  const setNodeStatus = useWorkspaceStore((state) => state.setNodeStatus);
  const displayStatus = value ?? selectedObject.confirmationStatus ?? fallbackStatus;

  const handleChange = useCallback((nextValue: string) => {
    if (disabled) return;
    if (onChange) {
      onChange(nextValue);
      return;
    }
    const nodeId = selectedObject.actorId ?? selectedObject.featureId ?? selectedObject.scenarioId
      ?? selectedObject.criterionId ?? selectedObject.businessObjectId ?? selectedObject.flowId
      ?? selectedObject.scopeId;
    if (nodeId != null) {
      void setNodeStatus(nodeId.toString(), nodeKind, nextValue as NodeStatus);
    }
  }, [disabled, nodeKind, onChange, selectedObject, setNodeStatus]);

  return (
    <Section title="节点审查状态">
      <SelectField
        label="确认状态"
        value={displayStatus}
        options={CONFIRMATION_STATUS_OPTIONS}
        onChange={handleChange}
        disabled={disabled}
      />
    </Section>
  );
}

// 0. Dedicated Project Panel
function ProjectObjectPanel({ selectedObject }: { selectedObject: any }) {
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
    <PanelShell title={projName} subtitle="系统根结点">
      <Section title="系统根属性编辑">
        <TextField label="系统名称" value={projName} onChange={setProjName} />
        <TextField label="系统描述说明" value={projDesc} onChange={setProjDesc} multiline />
        <ActionRow>
          <ActionButton onClick={() => void handleSave()}>保存属性更改</ActionButton>
          <ActionButton variant="secondary" onClick={() => { setProjName(ir?.projectName || ''); setProjDesc(ir?.projectDescription || ''); }}>
            重置修改
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}

// 1. Dedicated Actor Panel
function ActorObjectPanel({ selectedObject }: { selectedObject: any }) {
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
    <PanelShell title={actorName} subtitle="参与者">
      <ConfirmationStatusSection nodeKind="actor" selectedObject={selectedObject} />
      <Section title="参与者基本属性">
        <TextField label="参与者名称" value={actorName} onChange={setActorName} />
        <TextField label="职责说明 / 描述" value={actorDesc} onChange={setActorDesc} multiline />
        <ActionRow>
          <ActionButton onClick={() => void handleSave()}>保存更改</ActionButton>
          <ActionButton variant="secondary" onClick={() => { setActorName(selectedObject.actorName || ''); setActorDesc(selectedObject.actorDescription || ''); }}>
            重置修改
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}

// 2. Dedicated Feature Panel
function FeatureObjectPanel({ selectedObject }: { selectedObject: any }) {
  const ir = useWorkspaceStore((state) => state.ir);
  const activePage = useWorkspaceStore((state) => state.activePage);
  const updateFeature = useWorkspaceStore((state) => state.updateFeature);
  const updateScope = useWorkspaceStore((state) => state.updateScope);
  const setSelectedObject = useWorkspaceStore((state) => state.setSelectedObject);

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
    <PanelShell title={featName} subtitle="核心功能结点">
      {activePage === '/scope' && (
        <Section title="交付范围与决策">
          <SelectField 
            label="交付范围" 
            value={featScopeStatus} 
            options={[
              { value: 'current', label: '本期包含' },
              { value: 'postponed', label: '暂缓处理' },
              { value: 'exclude', label: '已排除' }
            ]} 
            onChange={(val) => setFeatScopeStatus(normalizeScopeStatus(val))} 
          />
          <TextField label="决策缘由 / 卡诺分析说明" value={featScopeReason} onChange={setFeatScopeReason} multiline />
        </Section>
      )}

      {activePage === '/scope' && feat.scope && (feat.scope.positiveSummary || feat.scope.negativeSummary || feat.scope.positivePictureBase64 || feat.scope.negativePictureBase64) && (
        <Section title="📊 Kano 智能需求分析">
          {feat.scope.positiveSummary && (
            <div className="mb-4 space-y-2">
              <div>
                <span className="text-[10px] text-emerald-600 font-extrabold uppercase tracking-wider block">有该功能时的用户感受</span>
                <p className="text-xs text-slate-600 italic bg-emerald-50/20 border border-emerald-100/50 p-2.5 rounded-xl mt-1">
                  "{feat.scope.positiveSummary}"
                </p>
              </div>
              {feat.scope.negativeSummary && (
                <div>
                  <span className="text-[10px] text-rose-600 font-extrabold uppercase tracking-wider block">缺少该功能时的用户感受</span>
                  <p className="text-xs text-slate-600 italic bg-rose-50/20 border border-rose-100/50 p-2.5 rounded-xl mt-1">
                    "{feat.scope.negativeSummary}"
                  </p>
                </div>
              )}
            </div>
          )}

          {(feat.scope.positivePictureBase64 || feat.scope.negativePictureBase64) && (
            <div className="space-y-3 pt-2 border-t border-slate-100">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">AI 仿真功能分布度量</span>
              <div className="grid grid-cols-2 gap-2">
                {feat.scope.positivePictureBase64 && (
                  <div className="space-y-1">
                    <span className="text-[10px] text-indigo-600 font-bold block text-center">有该功能时的体验影响图</span>
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
                    <span className="text-[10px] text-slate-500 font-bold block text-center">缺少该功能时的体验影响图</span>
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
      <Section title="功能结点基本属性">
        <TextField label="功能名称" value={featName} onChange={setFeatName} />
        <TextField label="描述说明" value={featDesc} onChange={setFeatDesc} multiline />
        <ActionRow>
          <ActionButton onClick={() => void handleSave()}>保存属性更改</ActionButton>
          <ActionButton variant="secondary" onClick={() => { 
            const f = originalFeature || selectedObject;
            const isRootNode = f.parentId === null;
            setFeatName(isRootNode ? (ir?.projectName || f.featureName || '') : (f.featureName || '')); 
            setFeatDesc(isRootNode ? (ir?.projectDescription || f.featureDescription || '') : (f.featureDescription || '')); 
            setFeatScopeStatus(normalizeScopeStatus(f.scope?.scopeStatus));
            setFeatScopeReason(f.scope?.reason || '');
            setSelectedActorIds(f.actorIds || []);
          }}>
            重置修改
          </ActionButton>
        </ActionRow>
      </Section>

      <Section title="架构关系定义">
        <div className="space-y-3">
          <div>
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">父级模块 / 能力</span>
            {parentCap ? (
              <button
                type="button"
                onClick={() => setSelectedObject(parentCap)}
                className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold bg-indigo-50/50 border border-indigo-100/60 rounded-lg px-2.5 py-1.5 transition-all text-left w-full truncate"
              >
                📁 {parentCap.parentId === null ? (ir?.projectName || parentCap.featureName) : parentCap.featureName}
              </button>
            ) : (
              <span className="text-xs text-slate-400 italic">无（当前是顶级功能结点）</span>
            )}
          </div>

          <div>
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">子级能力点 / 叶子功能</span>
            {childCaps.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {childCaps.map((c: any) => (
                  <button
                    key={c.featureId}
                    type="button"
                    onClick={() => setSelectedObject(c)}
                    className="text-[10px] bg-slate-50 border border-slate-200 text-slate-700 hover:border-indigo-300 hover:text-indigo-700 hover:bg-white rounded-md px-2 py-0.5 font-medium transition-all"
                  >
                    📄 {c.featureName}
                  </button>
                ))}
              </div>
            ) : (
              <span className="text-xs text-slate-400 italic">无（当前是具体叶子结点）</span>
            )}
          </div>
        </div>
      </Section>

      <Section title="关联参与者">
        {ir.actors && ir.actors.length > 0 ? (
          <div className="space-y-2 border border-slate-200/60 rounded-xl p-3 bg-slate-50/50 max-h-[160px] overflow-y-auto">
            {ir.actors.map((actor: any) => {
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
                  <span>👤 {actor.actorName}</span>
                </label>
              );
            })}
          </div>
        ) : (
          <span className="text-xs text-slate-500 italic">当前项目暂无系统参与者。请先在左侧定义参与者。</span>
        )}
      </Section>
    </PanelShell>
  );
}

function ScopeObjectPanel({ selectedObject }: { selectedObject: any }) {
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
  const featureName = feature?.featureName || selectedObject.featureName || selectedObject.title || '未命名功能';
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
    <PanelShell title={featureName} subtitle="交付范围 / 叶子功能决策">
      <Section title="状态与交付范围">
        <div className="flex flex-wrap gap-2">
          {draftConfirmationStatus ? <StatusBadge status={draftConfirmationStatus} /> : null}
          <span className="inline-flex px-2 py-1 rounded-full bg-slate-100 text-slate-600 text-xs font-semibold">
            {scopeStatus
              ? SCOPE_DECISION_OPTIONS.find((option) => option.value === scopeStatus)?.label || scopeStatus
              : '未交付决策'}
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

      <Section title="交付范围决策">
        <SelectField
          label="本期交付范围"
          value={scopeStatus}
          options={SCOPE_DECISION_OPTIONS}
          onChange={setScopeStatus}
        />
        {!scopeId && (
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500 leading-relaxed">
            当前功能尚未生成独立的范围记录。首次选择交付范围后，会自动创建该 `scope` 记录，并默认标记为 `AI 推测`。
          </div>
        )}
        <ActionRow>
          <ActionButton onClick={() => void handleSave()}>
            {isSaving ? '保存中...' : '保存更改'}
          </ActionButton>
          <ActionButton variant="secondary" onClick={handleReset}>
            重置修改
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}

// 3. Dedicated Business Object Panel
function BusinessObjectPanel({ selectedObject }: { selectedObject: any }) {
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
    <PanelShell title={boName} subtitle="核心业务对象">
      <Section title="数据实体基本属性">
        <TextField label="实体名称" value={boName} onChange={setBoName} />
        <TextField label="实体描述说明" value={boDesc} onChange={setBoDesc} multiline />
        <ActionRow>
          <ActionButton onClick={() => void handleSave()}>保存更改</ActionButton>
          <ActionButton variant="secondary" onClick={() => { setBoName(selectedObject.businessObjectName || ''); setBoDesc(selectedObject.businessObjectDescription || ''); }}>
            重置修改
          </ActionButton>
        </ActionRow>
      </Section>

      <ConfirmationStatusSection nodeKind="business_object" selectedObject={selectedObject} />
      <Section title="数据字段及属性定义">
        {(selectedObject.businessObjectAttributes || []).length === 0 ? (
          <div className="text-xs text-slate-400 italic">该实体暂未定义任何数据字段属性。</div>
        ) : (
          <div className="space-y-3 select-text">
            {(selectedObject.businessObjectAttributes || []).map((attr: any) => (
              <div key={attr.businessObjectAttributeId} className="border border-slate-200 rounded-xl p-3 bg-slate-50/50 space-y-1.5 shadow-sm">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-slate-800 text-xs">{attr.businessObjectAttributeName}</span>
                  <span className="text-[10px] bg-slate-100 border border-slate-200 rounded px-1.5 py-0.5 font-mono text-slate-500 font-bold">{attr.businessObjectAttributeType}</span>
                </div>
                <div className="text-xs text-slate-500 font-medium leading-relaxed">{attr.businessObjectAttributeDescription}</div>
                {attr.businessObjectAttributeExample && (
                  <div className="text-[10px] text-indigo-600 bg-indigo-50/40 p-1.5 rounded font-mono leading-none">
                    字段示例值: {attr.businessObjectAttributeExample}
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

// 4. Dedicated Flow Step Panel
function FlowStepObjectPanel({ selectedObject, ir }: { selectedObject: any; ir: any }) {
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
      alert('步骤名称为必填项！');
      return;
    }
    if (stepType === 'actorAction' && selectedActorIds.length === 0) {
      alert('用户参与者交互步骤必须选择至少一个参与者！');
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
    <PanelShell title={stepName} subtitle="流程步骤结点">
      <Section title="流程步骤基本属性">
        <TextField label="步骤名称" value={stepName} onChange={setStepName} />
        <SelectField 
          label="步骤协作类型" 
          value={stepType} 
          options={[
            { value: 'actorAction', label: '用户参与者交互步骤' },
            { value: 'systemAction', label: '系统后台自动步骤' },
            { value: 'judgment', label: '逻辑分支判定步骤' }
          ]} 
          onChange={setStepType} 
        />
        <TextField label="步骤执行说明" value={stepDesc} onChange={setStepDesc} multiline />
      </Section>

      <Section title="参与执行参与者">
        <div className="space-y-2 max-h-[150px] overflow-y-auto border border-slate-100 rounded-xl p-3 bg-slate-50/50 select-none">
          {(ir.actors || []).length === 0 ? (
            <div className="text-xs text-slate-400 italic">暂无可用参与者，请先在 What 阶段定义。</div>
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
            ⚠️ 交互类型步骤必须至少勾选一个关联参与者。
          </div>
        )}
      </Section>

      <Section title="输入业务数据实体">
        <div className="space-y-2 max-h-[150px] overflow-y-auto border border-slate-100 rounded-xl p-3 bg-slate-50/50 select-none">
          {(ir.businessObjects || []).length === 0 ? (
            <div className="text-xs text-slate-400 italic">暂无可用业务对象，请在下方或 How 页面新增。</div>
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

      <Section title="输出业务数据实体">
        <div className="space-y-2 max-h-[150px] overflow-y-auto border border-slate-100 rounded-xl p-3 bg-slate-50/50 select-none">
          {(ir.businessObjects || []).length === 0 ? (
            <div className="text-xs text-slate-400 italic">暂无可用业务对象，请在下方或 How 页面新增。</div>
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
          <ActionButton onClick={() => void handleSave()}>保存更改</ActionButton>
          <ActionButton variant="secondary" onClick={handleReset}>
            重置修改
          </ActionButton>
        </ActionRow>
      </div>
    </PanelShell>
  );
}

// 5. Dedicated Flow Panel
function FlowObjectPanel({ selectedObject }: { selectedObject: any }) {
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
    <PanelShell title={flowName} subtitle="业务流程">
      <ConfirmationStatusSection nodeKind="flow" selectedObject={selectedObject} />
      <Section title="流程基本属性">
        <TextField label="流程名称" value={flowName} onChange={setFlowName} />
        <TextField label="流程场景描述" value={flowDesc} onChange={setFlowDesc} multiline />
        <ActionRow>
          <ActionButton onClick={() => void handleSave()}>保存更改</ActionButton>
          <ActionButton variant="secondary" onClick={() => { setFlowName(selectedObject.flowName || ''); setFlowDesc(selectedObject.flowDescription || ''); }}>
            重置修改
          </ActionButton>
        </ActionRow>
      </Section>
    </PanelShell>
  );
}

// 6. Dedicated Scenario Panel
function ScenarioObjectPanel({ selectedObject }: { selectedObject: any }) {
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
    <PanelShell title={scenName} subtitle="业务成功场景">
      <Section title="成功场景基本属性">
        <TextField label="场景名称" value={scenName} onChange={setScenName} />
        <TextField label="场景交互过程 / 用户故事描述" value={scenContent} onChange={setScenContent} multiline />
        <ActionRow>
          <ActionButton onClick={() => void handleSave()}>保存更改</ActionButton>
          <ActionButton variant="secondary" onClick={() => { setScenName(selectedObject.scenarioName || ''); setScenContent(selectedObject.scenarioContent || ''); }}>
            重置修改
          </ActionButton>
        </ActionRow>
      </Section>

      <ConfirmationStatusSection nodeKind="scenario" selectedObject={selectedObject} />
      <Section title="系统交付验收标准">
        {(selectedObject.acceptanceCriteria || []).length === 0 ? (
          <div className="text-xs text-slate-400 italic">该场景暂无关联的交付验收标准。</div>
        ) : (
          <div className="space-y-4">
            {(selectedObject.acceptanceCriteria || []).map((ac: any) => (
              <GherkinVisualRenderer
                key={ac.criterionId}
                text={ac.criterionContent || ''}
                title={`验收标准 #${ac.criterionId}`}
                badge="验收标准"
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
    <PanelShell title={`验收标准 #${selectedObject.criterionId}`} subtitle="交付验收标准">
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
            ⚡ 可视化设计器
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
            📝 原生 Gherkin 文本
          </button>
        </div>
      </div>

      <Section title="验收标准详细说明">
        {activeTab === 'visual' ? (
          <div className="border border-slate-200/80 rounded-2xl p-4 bg-slate-50/10 mb-4 shadow-sm">
            <GherkinVisualEditor
              initialText={acContent}
              onChange={setAcContent}
            />
          </div>
        ) : (
          <TextField 
            label="交付验收标准具体内容" 
            value={acContent} 
            onChange={setAcContent} 
            multiline 
          />
        )}
        
        {parent ? (
          <ActionRow>
            <ActionButton onClick={() => void handleSave()}>保存更改</ActionButton>
            <ActionButton variant="secondary" onClick={() => {
              setAcContent(selectedObject.criterionContent || '');
              // To reset the visual editor as well, we trigger selectedObject reload
              setSelectedObject({ ...selectedObject });
            }}>
              重置修改
            </ActionButton>
          </ActionRow>
        ) : (
          <div className="text-xs text-rose-500 italic mt-2 font-medium">⚠️ 无法定位该验收标准所属的父级功能及场景，属性只读。</div>
        )}
      </Section>
    </PanelShell>
  );
}

export function RightObjectPanel() {
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
        <PanelShell title="建模资产编辑面板" subtitle="建模资产面板">
          <div className="text-sm text-slate-500 leading-relaxed font-medium">
            右侧面板统一审阅和编辑参与者、功能树、业务流程步骤、数据对象等项目模型资产。
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
    if (kind === 'flow_step') {
      return <FlowStepObjectPanel selectedObject={selectedObject} ir={ir} />;
    }
    if (kind === 'flow') {
      return <FlowObjectPanel selectedObject={selectedObject} />;
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
      <PanelShell title={selectedObject.title || selectedObject.name || selectedObject.id || '未知对象'} subtitle="对象属性详情">
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
        title={collapsed ? '展开面板' : '折叠面板'}
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
